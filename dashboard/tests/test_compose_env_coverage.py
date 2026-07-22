"""Guardrail: every operator-facing env var settings.py reads is forwarded by
the compose files.

Why this test exists
--------------------
The two compose files (`docker-compose.yml`, `docker-compose.dokploy.yml`)
share a hand-maintained `x-app-env` anchor. That anchor is the ONLY channel by
which an operator's env var reaches the containers: Dokploy (and a plain
`.env`) provide values to compose's *interpolation* context, but a var only
lands in a container if the anchor explicitly references it. So a setting added
to `settings.py` without a matching anchor line is read as unset in production
and silently ignored - exactly how the GBIF download bounding box
(`GBIF_DOWNLOAD_{LAT,LON}_{MIN,MAX}`) shipped broken: the code read the four
vars, but the anchor never forwarded them, so the box vanished from the
download predicate while country/year (which *were* in the anchor) kept working.

This test parses `settings.py` for every `os.environ[...]` / `os.environ.get(...)`
read and asserts each name is either forwarded by both anchors or explicitly
allow-listed below with a reason. It turns "forgot to update the anchor" from a
silent production regression into a failed CI run.

Maintaining the allow-list
--------------------------
When you add a new env-driven setting, the fix is almost always to add a line to
the `x-app-env` anchor in BOTH compose files. Only add a name to `NOT_FORWARDED`
when there is a real reason the container must NOT receive it (see the existing
entries), and write the reason inline.
"""
import ast
import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SETTINGS_PY = _REPO_ROOT / "djangoproject" / "settings.py"
_COMPOSE_FILES = (
    _REPO_ROOT / "docker-compose.yml",
    _REPO_ROOT / "docker-compose.dokploy.yml",
)

# Env vars read by settings.py that are deliberately NOT forwarded by the
# compose anchor. Each needs a reason: forwarding it would either be meaningless
# (host/dev-only) or actively harmful (breaks a smart default).
NOT_FORWARDED = {
    # Host-specific: GeoDjango autodetects GDAL/GEOS on Linux/Docker; these
    # paths only matter for macOS/Homebrew local dev.
    "GDAL_LIBRARY_PATH": "macOS/Homebrew dev only; Linux/Docker autodetects",
    "GEOS_LIBRARY_PATH": "macOS/Homebrew dev only; Linux/Docker autodetects",
    # Set by the image entry points (wsgi/asgi/manage), never by the operator.
    "DJANGO_SETTINGS_MODULE": "set by the image entry points, not the operator",
    # Dev-server-only toggle; production always serves the built manifest.
    "DJANGO_VITE_DEV_MODE": "dev server only; prod serves the built manifest",
    # HTTPS hardening: these default to str(not DEBUG) / a prod value, computed
    # AFTER local_settings so they see the effective DEBUG. Forwarding them via
    # compose would inject an empty string on an unset var, which reads as False
    # and would DISABLE secure cookies / SSL redirect / HSTS on a production
    # HTTPS deploy. The auto-default already does the right thing on every
    # platform; override via local_settings.py for the rare exception.
    "SESSION_COOKIE_SECURE": "auto-hardens from effective DEBUG; empty would disable it",
    "CSRF_COOKIE_SECURE": "auto-hardens from effective DEBUG; empty would disable it",
    "SECURE_SSL_REDIRECT": "auto-hardens from effective DEBUG; empty would disable it",
    "SECURE_HSTS_SECONDS": "auto-hardens from effective DEBUG; empty would disable it",
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": "part of the auto-hardening HSTS group",
    "SECURE_HSTS_PRELOAD": "part of the auto-hardening HSTS group",
    # Derived in settings.py from AWS_SES_REGION_NAME; injecting an empty value
    # would clobber that derivation.
    "AWS_SES_REGION_ENDPOINT": "derived from AWS_SES_REGION_NAME in settings.py",
}


def _string_elements(node: ast.AST) -> set[str]:
    """String constants inside a tuple/list/set literal (else empty)."""
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return {
            e.value
            for e in node.elts
            if isinstance(e, ast.Constant) and isinstance(e.value, str)
        }
    return set()


def _env_vars_read_by_settings() -> set[str]:
    """Every env var name settings.py reads via os.environ[...] or .get(...).

    An AST walk (not a regex) so multi-line `os.environ.get(\n "NAME", ...)`
    calls are caught - the class of read a line-based grep silently misses.

    It also resolves the ONE indirect idiom in settings.py: the bounding box is
    read as `os.environ.get(n) for n in names` where `names` is a tuple of
    string literals. A literal-only extractor would miss exactly the four vars
    whose omission caused this bug, so a `Name` argument is traced back to its
    literal collection - through a direct `names = (...)` assignment or a
    `for n in names` comprehension target.
    """
    tree = ast.parse(_SETTINGS_PY.read_text())

    # var name -> string constants of the collection literal it is bound to.
    assigned_strings: dict[str, set[str]] = {}
    # comprehension target name -> the iterables it is bound over.
    comp_target_iters: dict[str, list[ast.AST]] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            elems = _string_elements(node.value)
            if elems:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assigned_strings.setdefault(target.id, set()).update(elems)
        if isinstance(node, ast.comprehension) and isinstance(node.target, ast.Name):
            comp_target_iters.setdefault(node.target.id, []).append(node.iter)

    def resolve(name: str, _seen: frozenset = frozenset()) -> set[str]:
        if name in _seen:  # guard against pathological cycles
            return set()
        seen = _seen | {name}
        result = set(assigned_strings.get(name, set()))
        for iterable in comp_target_iters.get(name, []):
            if isinstance(iterable, ast.Name):
                result |= resolve(iterable.id, seen)
            else:
                result |= _string_elements(iterable)
        return result

    def key_names(arg: ast.AST) -> set[str]:
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return {arg.value}
        if isinstance(arg, ast.Name):
            return resolve(arg.id)
        return set()

    names: set[str] = set()
    for node in ast.walk(tree):
        # os.environ["NAME"]
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "environ"
        ):
            names |= key_names(node.slice)
        # os.environ.get("NAME", ...)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get"
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "environ"
            and node.args
        ):
            names |= key_names(node.args[0])

    return names


_ANCHOR_HEADER = re.compile(r"^x-app-env:\s*&app-env\b")
# A mapping key line inside the anchor: two-space indented `NAME: value`.
_ANCHOR_KEY = re.compile(r"^  ([A-Za-z_][A-Za-z0-9_]*):")


def _env_vars_forwarded_by(compose_file: Path) -> set[str]:
    """The keys of the `x-app-env` anchor, parsed textually.

    Deliberately not a YAML load: PyYAML is not a project dependency, and the
    anchor is a flat block we control. The block runs from `x-app-env: &app-env`
    to the first line at column 0 (blank lines and `  # ...` comments inside it
    are skipped).
    """
    names: set[str] = set()
    in_anchor = False
    for line in compose_file.read_text().splitlines():
        if _ANCHOR_HEADER.match(line):
            in_anchor = True
            continue
        if not in_anchor:
            continue
        if line and not line.startswith(" "):  # dedented back to column 0: block ended
            break
        match = _ANCHOR_KEY.match(line)
        if match:
            names.add(match.group(1))
    assert names, f"parsed no keys from the x-app-env anchor in {compose_file.name}"
    return names


def test_every_setting_env_var_is_forwarded_or_allowlisted():
    """No env var read by settings.py is silently dropped by the compose files.

    Forward direction only (read-but-not-forwarded) - that is the bug class.
    The reverse (forwarded-but-unread, e.g. GUNICORN_WORKERS, POSTGRES_*) is
    legitimate: those are consumed by the image CMD or the bundled-db service,
    not by settings.py.
    """
    read = _env_vars_read_by_settings()

    for compose_file in _COMPOSE_FILES:
        forwarded = _env_vars_forwarded_by(compose_file)
        missing = read - forwarded - set(NOT_FORWARDED)
        assert not missing, (
            f"{compose_file.name} does not forward these env vars that "
            f"settings.py reads: {sorted(missing)}. Add each to the `x-app-env` "
            f"anchor, or - if the container must NOT receive it - add it to "
            f"NOT_FORWARDED in this test with a reason."
        )


def test_allowlist_entries_are_actually_read():
    """Every NOT_FORWARDED entry must still be a var settings.py reads.

    Keeps the allow-list honest: if a setting is deleted or renamed, its stale
    allow-list entry fails here instead of masking a future omission.
    """
    read = _env_vars_read_by_settings()
    stale = set(NOT_FORWARDED) - read
    assert not stale, (
        f"NOT_FORWARDED lists env vars settings.py no longer reads: "
        f"{sorted(stale)}. Remove them from the allow-list."
    )
