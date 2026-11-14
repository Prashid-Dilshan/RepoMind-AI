import os

import pytest

pytest.importorskip("langchain_core")

from utils.file_loader import build_structure_document, load_files  # noqa: E402


def _write(root, relative, content="print('hi')\n", binary=False):
    path = os.path.join(root, *relative.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if binary else "w") as f:
        f.write(content)
    return path


def test_loader_keeps_source_and_skips_noise(tmp_path):
    root = str(tmp_path)
    _write(root, "src/app.py")
    _write(root, "README.md", "# Title\n")
    _write(root, "package-lock.json", "{}")
    _write(root, "node_modules/lib/index.js", "x")
    _write(root, ".env", "OPENAI_API_KEY=secret")
    _write(root, ".env.production", "SECRET=1")
    _write(root, "logo.png", b"\x89PNG\x00\x00", binary=True)
    _write(root, "data.bin", b"\x00\x01\x02", binary=True)
    _write(root, "notes.txt", b"\x00\x00binary-looking", binary=True)
    _write(root, "dist/app.min.js", "x")
    _write(root, "empty.py", "   \n")

    docs, stats = load_files(root)
    sources = sorted(d.metadata["source"] for d in docs)

    assert sources == ["README.md", "src/app.py"]
    assert stats == {"skipped_large": 0, "truncated": False}


def test_large_files_are_counted_and_skipped(tmp_path, monkeypatch):
    import utils.file_loader as fl

    monkeypatch.setattr(fl, "MAX_FILE_BYTES", 100)
    root = str(tmp_path)
    _write(root, "big.py", "x = 1\n" * 100)
    _write(root, "small.py", "x = 1\n")

    docs, stats = fl.load_files(root)
    assert [d.metadata["source"] for d in docs] == ["small.py"]
    assert stats["skipped_large"] == 1


def test_file_cap_marks_truncated(tmp_path, monkeypatch):
    import utils.file_loader as fl

    monkeypatch.setattr(fl, "MAX_FILES", 2)
    root = str(tmp_path)
    for name in ("a.py", "b.py", "c.py"):
        _write(root, name)

    docs, stats = fl.load_files(root)
    assert len(docs) == 2
    assert stats["truncated"] is True


def test_symlinks_are_never_followed(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("top secret")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "real.py").write_text("x = 1\n")
    try:
        os.symlink(outside, repo / "link.txt")
        os.symlink(tmp_path, repo / "linked_dir")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available on this system")

    docs, _ = load_files(str(repo))
    assert [d.metadata["source"] for d in docs] == ["real.py"]


def test_structure_document_lists_paths_and_truncates():
    paths = [f"src/file{i}.py" for i in range(5)]
    doc = build_structure_document(paths, limit=3)
    assert "src/file0.py" in doc.page_content
    assert "src/file4.py" not in doc.page_content
    assert "2 more files" in doc.page_content
