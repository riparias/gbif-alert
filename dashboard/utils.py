import logging
import subprocess

from django.conf import settings
from django.utils.translation import get_supported_language_variant

logger = logging.getLogger(__name__)

_cached_version: str | None = None


def enabled_language(*candidates: str | None) -> str:
    """The first candidate this site enables, as a code from settings.LANGUAGES.

    Candidates are tried in order, then LANGUAGE_CODE; a variant counts as its
    base language ("fr-BE" or "en-us" as "fr" or "en"). With no enabled match,
    the first of GBIF_ALERT["ENABLED_LANGUAGES"] wins, so LANGUAGE_CODE does not
    leak through on a site without English.
    """
    enabled = settings.GBIF_ALERT["ENABLED_LANGUAGES"]
    for candidate in (*candidates, settings.LANGUAGE_CODE):
        if not candidate:
            continue
        try:
            code = get_supported_language_variant(candidate)
        except LookupError:
            continue
        if code in enabled:
            return code
    return enabled[0]


def readable_string(input_string: str) -> str:
    """Remove multiple whitespaces and \n to make a long string more readable"""
    return " ".join(input_string.replace("\n", "").split())


def human_readable_git_version_number() -> str:
    """Return the application version number.

    Uses the first available source:
    1. A VERSION file at the project root (committed at release time)
    2. git describe --always --tags (useful for development between releases)
    3. "unknown" as a last resort

    The result is cached after the first call, so no repeated subprocess/file access.
    """
    global _cached_version

    if _cached_version is not None:
        return _cached_version

    project_root = settings.BASE_DIR

    # 1. Try the VERSION file
    version_file = project_root / "VERSION"
    try:
        _cached_version = version_file.read_text().strip()
        if _cached_version:
            return _cached_version
    except FileNotFoundError:
        pass

    # 2. Try git describe
    try:
        _cached_version = subprocess.check_output(
            ["git", "-C", project_root, "describe", "--always", "--tags"],
            encoding="UTF-8",
            stderr=subprocess.DEVNULL,
        ).strip()
        return _cached_version
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("Could not determine version from VERSION file or git")

    # 3. Last resort
    _cached_version = "unknown"
    return _cached_version
