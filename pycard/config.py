from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import tomllib


DEFAULT_CONFIG_PATH = "pycard.toml"
DEFAULT_PERSONALIZED_PIN = (0xFF, 0xFF, 0xFF)


@dataclass(frozen=True, slots=True)
class AppConfig:
    personalized_pin: tuple[int, int, int]
    config_path: Path
    exists: bool


def load_config(config_path: str | None = None) -> AppConfig:
    path = Path(config_path or os.getenv("PYCARD_CONFIG", DEFAULT_CONFIG_PATH))
    if not path.exists():
        return AppConfig(
            personalized_pin=DEFAULT_PERSONALIZED_PIN,
            config_path=path,
            exists=False,
        )

    with path.open("rb") as handle:
        payload = tomllib.load(handle)

    try:
        raw_pin = payload["card"]["personalized_pin"]
    except KeyError as exc:
        raise ValueError(f"missing card.personalized_pin in {path}") from exc

    if not isinstance(raw_pin, list) or len(raw_pin) != 3:
        raise ValueError(f"card.personalized_pin in {path} must contain exactly 3 byte values")

    pin = tuple(_parse_pin_byte(value, path) for value in raw_pin)
    return AppConfig(personalized_pin=pin, config_path=path, exists=True)


def save_personalized_pin(config_path: Path, personalized_pin: tuple[int, int, int]) -> None:
    pin = tuple(_validate_pin_byte(value, config_path) for value in personalized_pin)
    config_path.write_text(
        "[card]\n"
        f'personalized_pin = ["{pin[0]:02X}", "{pin[1]:02X}", "{pin[2]:02X}"]\n',
        encoding="utf-8",
    )


def _parse_pin_byte(value: object, path: Path) -> int:
    if isinstance(value, str):
        try:
            return _validate_pin_byte(int(value, 16), path)
        except ValueError as exc:
            raise ValueError(
                f"card.personalized_pin in {path} must contain hex byte strings like \"C0\" or integers in range 0..255"
            ) from exc
    return _validate_pin_byte(value, path)


def _validate_pin_byte(value: object, path: Path) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"card.personalized_pin in {path} must contain integers in range 0..255")
    if not 0 <= value <= 0xFF:
        raise ValueError(f"card.personalized_pin in {path} must contain integers in range 0..255")
    return value
