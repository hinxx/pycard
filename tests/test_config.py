from __future__ import annotations

from pathlib import Path

import pytest

from pycard.config import (
    DEFAULT_PERSONALIZED_PIN,
    load_config,
    save_language,
    save_personalized_pin,
)


def test_missing_config_defaults_to_english(tmp_path: Path) -> None:
    path = tmp_path / "pycard.toml"

    config = load_config(str(path))

    assert not config.exists
    assert config.personalized_pin == DEFAULT_PERSONALIZED_PIN
    assert config.language == "en"
    assert not config.language_configured


def test_saving_language_migrates_legacy_config_and_preserves_pin(tmp_path: Path) -> None:
    path = tmp_path / "pycard.toml"
    path.write_text(
        '[card]\npersonalized_pin = ["C0", "DE", "A5"]\n',
        encoding="utf-8",
    )

    legacy_config = load_config(str(path))
    save_language(path, legacy_config.language)
    migrated_config = load_config(str(path))

    assert legacy_config.language == "en"
    assert not legacy_config.language_configured
    assert migrated_config.personalized_pin == (0xC0, 0xDE, 0xA5)
    assert migrated_config.language == "en"
    assert migrated_config.language_configured
    assert '[ui]\nlanguage = "en"' in path.read_text(encoding="utf-8")


def test_selected_language_survives_pin_change(tmp_path: Path) -> None:
    path = tmp_path / "pycard.toml"
    save_language(path, "sl")

    save_personalized_pin(path, (0x11, 0x22, 0x33))
    config = load_config(str(path))

    assert config.personalized_pin == (0x11, 0x22, 0x33)
    assert config.language == "sl"


def test_invalid_configured_language_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "pycard.toml"
    path.write_text(
        '[card]\npersonalized_pin = ["11", "22", "33"]\n'
        '\n[ui]\nlanguage = "de"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ui.language"):
        load_config(str(path))
