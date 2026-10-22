from pathlib import Path

import pytest
from PIL import Image

import config
import db
from judge_service import judge_profile
from llm.base import Decision


class SkipBackend:
    def judge(self, images: list[bytes], system_prompt: str, app: str) -> Decision:
        assert len(images) == 1
        assert app == "generic"
        assert "profile" in system_prompt
        return Decision(decision="skip", reasoning="No compatible signal.")


@pytest.fixture
def isolated_workspace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "decisions.db")
    context = tmp_path / "context.md"
    context.write_text("# Your voice\nShort and warm.\n", encoding="utf-8")
    monkeypatch.setattr(config, "CONTEXT_MD_PATH", context)
    db.init_db()
    return tmp_path


def test_judge_persists_a_decision_from_a_local_image(isolated_workspace: Path) -> None:
    image = isolated_workspace / "profile.png"
    Image.new("RGB", (32, 32), color="white").save(image)

    result = judge_profile([str(image)], backend=SkipBackend())

    assert result["decision"] == "skip"
    assert result["app"] == "generic"
    saved = db.get_decision(result["decision_id"])
    assert saved is not None
    assert saved["reasoning"] == "No compatible signal."


def test_judge_rejects_a_missing_image_before_loading_a_backend() -> None:
    with pytest.raises(ValueError, match="not a readable file"):
        judge_profile(["/missing/profile.png"])
