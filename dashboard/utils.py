import subprocess

from django.conf import settings


def readable_string(input_string: str) -> str:
    """Remove multiple whitespaces and \n to make a long string more readable"""
    return " ".join(input_string.replace("\n", "").split())


def human_readable_git_version_number() -> str:
    """Return the git tag name (if available) or the git commit hash (if not)"""
    project_root = settings.BASE_DIR

    return subprocess.check_output(
        ["git", "-C", project_root, "describe", "--always", "--tags"], encoding="UTF-8"
    ).strip()
