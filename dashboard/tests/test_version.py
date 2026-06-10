from pathlib import Path

import dashboard.utils
from dashboard.utils import human_readable_git_version_number


def test_version_file_is_read(tmp_path: Path, monkeypatch):
    """A VERSION file at BASE_DIR takes precedence and is returned verbatim."""
    monkeypatch.setattr(dashboard.utils, "_cached_version", None)
    monkeypatch.setattr(dashboard.utils.settings, "BASE_DIR", tmp_path)
    (tmp_path / "VERSION").write_text("v9.9.9-test\n")

    assert human_readable_git_version_number() == "v9.9.9-test"


def test_empty_version_file_falls_through(tmp_path: Path, monkeypatch):
    """An empty VERSION file is treated as absent (does not return "")."""
    monkeypatch.setattr(dashboard.utils, "_cached_version", None)
    monkeypatch.setattr(dashboard.utils.settings, "BASE_DIR", tmp_path)
    (tmp_path / "VERSION").write_text("")

    # No VERSION value and no usable git repo at tmp_path -> "unknown", never "".
    assert human_readable_git_version_number() != ""
