"""Test indice cartelle (film/media)."""
import os
import tempfile

import pytest

from backend.config import settings


@pytest.fixture
def index_env(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        movies_dir = os.path.join(tmp, "Videos")
        os.makedirs(movies_dir)
        index_dir = os.path.join(tmp, "data", "index")
        mem_dir = os.path.join(tmp, "memory")
        os.makedirs(index_dir)
        os.makedirs(mem_dir)

        monkeypatch.setattr(settings, "JANIS_PROJECT_DIR", tmp)
        monkeypatch.setattr(settings, "JANIS_MOVIES_PATH", movies_dir)
        monkeypatch.setattr(settings, "JANIS_SCAN_ROOTS", movies_dir)
        monkeypatch.setattr(settings, "MEMORY_DIR", mem_dir)

        from backend.core import folder_index as fi
        from backend.core.tools import memory_tool as mem

        yield {"fi": fi, "mem": mem, "movies_dir": movies_dir}


def test_parse_year_from_name(index_env):
    fi = index_env["fi"]
    assert fi.parse_year_from_name("Inception (2010).mkv") == 2010
    assert fi.parse_year_from_name("random movie.mkv") is None
    assert fi.parse_year_from_name("Blade Runner 2049.mp4") == 2049


def test_scan_directory(index_env):
    fi = index_env["fi"]
    movies = index_env["movies_dir"]
    open(os.path.join(movies, "Avatar (2009).mkv"), "wb").write(b"x" * 100)
    open(os.path.join(movies, "Dune (2021).mp4"), "wb").write(b"y" * 200)
    open(os.path.join(movies, "notes.txt"), "w", encoding="utf-8").write("skip")

    data = fi.scan_directory(movies, "movies")
    assert data["count"] == 2
    assert data["total_size_bytes"] == 300
    assert data["clusters"]["by_year"]["2009"] == 1
    assert data["clusters"]["by_year"]["2021"] == 1


def test_save_load_index(index_env):
    fi = index_env["fi"]
    movies = index_env["movies_dir"]
    open(os.path.join(movies, "Test (1999).avi"), "wb").write(b"z" * 50)

    data = fi.scan_directory(movies, "movies")
    fi.save_index(data)
    loaded = fi.load_index("movies")
    assert loaded is not None
    assert loaded["count"] == 1
    assert loaded["items"][0]["name"] == "Test (1999).avi"


def test_search_index(index_env):
    fi = index_env["fi"]
    movies = index_env["movies_dir"]
    open(os.path.join(movies, "Matrix (1999).mkv"), "wb").write(b"a")
    open(os.path.join(movies, "Interstellar (2014).mkv"), "wb").write(b"b")

    data = fi.scan_directory(movies, "movies")
    fi.save_index(data)

    hits = fi.search_index("matrix", "movies")
    assert len(hits) == 1
    assert "Matrix" in hits[0]["name"]


def test_sync_index_to_memory(index_env):
    fi = index_env["fi"]
    mem = index_env["mem"]
    movies = index_env["movies_dir"]
    open(os.path.join(movies, "Film A (2001).mkv"), "wb").write(b"a")
    open(os.path.join(movies, "Film B (2001).mkv"), "wb").write(b"b")

    data = fi.scan_directory(movies, "movies")
    updated = fi.sync_index_to_memory(data)
    assert updated >= 1
    entries = mem._load()
    assert any("[indice-movies]" in e.get("text", "") for e in entries)
    assert any("movies" in e.get("tags", []) for e in entries)


def test_scan_path_outside_roots(index_env, monkeypatch):
    fi = index_env["fi"]
    from backend.core.security import validate_scan_path

    with pytest.raises(PermissionError):
        validate_scan_path(r"C:\Windows\System32")


@pytest.mark.asyncio
async def test_scan_folder_tool(index_env):
    fi = index_env["fi"]
    movies = index_env["movies_dir"]
    open(os.path.join(movies, "Local (2020).mp4"), "wb").write(b"x" * 10)

    from backend.core.tools.folder_scanner import scan_folder

    result = await scan_folder({"category": "movies"})
    assert "Scansione completata" in result
    assert "1 file" in result
    stats = fi.get_index_stats("movies")
    assert stats["count"] == 1
