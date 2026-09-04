"""Format validation + output artifact path-safety tests."""

import uuid
from pathlib import Path

import pytest

from app.services.artifacts import (
    delete_task_output,
    list_output_files,
    resolve_output_file,
    task_output_dir,
)
from app.services.formats import validate_platforms


class TestValidatePlatforms:
    def test_known_platform_passes(self):
        assert validate_platforms(["instagram-square"]) == ["instagram-square"]

    def test_carousel_slide_passes(self):
        assert validate_platforms(["instagram-carousel-1", "instagram-carousel-portrait-5"]) == [
            "instagram-carousel-1",
            "instagram-carousel-portrait-5",
        ]

    def test_invalid_carousel_slide_rejected(self):
        with pytest.raises(Exception):
            validate_platforms(["instagram-carousel-portrait-0"])
        with pytest.raises(Exception):
            validate_platforms(["not-carousel-1"])

    def test_unknown_platform_rejected(self):
        with pytest.raises(Exception):
            validate_platforms(["not-a-platform"])

    def test_path_traversal_rejected(self):
        for bad in ["../evil", "..", "a/b", "a\\b", " a", "a "]:
            with pytest.raises(Exception):
                validate_platforms([bad])


class TestArtifacts:
    def test_resolve_rejects_traversal(self, tmp_path, monkeypatch):
        from app.config import get_settings
        settings = get_settings()
        monkeypatch.setattr(settings, "output_dir", str(tmp_path))
        task_id = str(uuid.uuid4())
        (task_output_dir(task_id)).mkdir(parents=True)
        with pytest.raises(FileNotFoundError):
            resolve_output_file(task_id, "../../../etc/passwd")

    def test_list_and_resolve_roundtrip(self, tmp_path, monkeypatch):
        from app.config import get_settings
        settings = get_settings()
        monkeypatch.setattr(settings, "output_dir", str(tmp_path))
        task_id = str(uuid.uuid4())
        d = task_output_dir(task_id)
        d.mkdir(parents=True)
        (d / "instagram-square.png").write_bytes(b"PNG")
        (d / "linkedin-post.html").write_text("x")

        files = list_output_files(task_id)
        assert {f["format"] for f in files} == {"instagram-square", "linkedin-post"}
        png = resolve_output_file(task_id, "instagram-square.png")
        assert png.read_bytes() == b"PNG"

    def test_delete_task_output_removes_dir(self, tmp_path, monkeypatch):
        from app.config import get_settings
        settings = get_settings()
        monkeypatch.setattr(settings, "output_dir", str(tmp_path))
        task_id = str(uuid.uuid4())
        d = task_output_dir(task_id)
        d.mkdir(parents=True)
        (d / "a.html").write_text("x")
        delete_task_output(task_id)
        assert not d.exists()

    def test_delete_refuses_outside_root(self, tmp_path, monkeypatch):
        from app.config import get_settings
        settings = get_settings()
        monkeypatch.setattr(settings, "output_dir", str(tmp_path))
        outside = Path(tmp_path) / ".." / "sensitive"
        outside.mkdir(exist_ok=True)
        delete_task_output("sensitive")
        assert outside.exists()
