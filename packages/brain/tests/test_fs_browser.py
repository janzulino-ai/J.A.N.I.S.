"""Test esplorazione file system (unità e cartelle)."""
import os
import sys

import pytest

from backend.core.fs_browser import browse_directory, list_drives


@pytest.mark.skipif(sys.platform != "win32", reason="Unità Windows")
def test_list_drives_windows():
    drives = list_drives()
    assert len(drives) >= 1
    assert any(d["path"].endswith(":\\") for d in drives)


def test_browse_home_or_system():
    if sys.platform == "win32":
        start = os.environ.get("SystemDrive", "C:") + "\\"
    else:
        start = os.path.expanduser("~")
    data = browse_directory(start)
    assert data["path"]
    assert "entries" in data
    assert isinstance(data["entries"], list)


def test_browse_missing_raises():
    with pytest.raises(FileNotFoundError):
        browse_directory("Z:\\__janis_missing_test__")
