from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
import tkinter as tk

from pycard import __version__
from pycard.config import DEFAULT_PERSONALIZED_PIN, load_config, save_personalized_pin
from pycard.controller import AppController
from pycard.i18n import DEFAULT_LANGUAGE
from pycard.pcsc import MemoryCardTransport, PyscardBackend
from pycard.reader import ReaderService
from pycard.ui import MainWindow


def configure_logging() -> None:
    level_name = os.getenv("PYCARD_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(name)s: %(message)s",
    )


def _resolve_icon_path(filename: str) -> Path | None:
    if getattr(sys, "frozen", False):
        bundle_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
        icon_path = bundle_dir / filename
        return icon_path if icon_path.exists() else None

    project_root = Path(__file__).resolve().parent.parent
    icon_path = project_root / filename
    return icon_path if icon_path.exists() else None


def _apply_window_icon(ui: MainWindow) -> None:
    logger = logging.getLogger(__name__)
    if sys.platform == "win32":
        icon_path = _resolve_icon_path("pycard.ico")
        if icon_path is None:
            logger.debug("window icon not found: pycard.ico")
            return
        try:
            ui.iconbitmap(str(icon_path))
            logger.debug("window icon loaded: %s", icon_path)
        except Exception as exc:  # pragma: no cover - platform dependent Tk behavior
            logger.debug("failed to load window icon %s: %s", icon_path, exc)
        return

    icon_path = _resolve_icon_path("pycard.png")
    if icon_path is None:
        logger.debug("window icon not found: pycard.png")
        return
    try:
        photo = tk.PhotoImage(file=str(icon_path))
        ui.iconphoto(True, photo)
        ui._window_icon_photo = photo
        logger.debug("window icon loaded: %s", icon_path)
    except Exception as exc:  # pragma: no cover - platform dependent Tk behavior
        logger.debug("failed to load window icon %s: %s", icon_path, exc)


def main() -> int:
    configure_logging()
    config = load_config()
    backend = PyscardBackend()
    transport = MemoryCardTransport(backend=backend)
    reader = ReaderService(transport=transport, personalized_pin=config.personalized_pin)
    ui = MainWindow(
        language=os.getenv("PYCARD_LANG", DEFAULT_LANGUAGE),
        version_text=__version__,
    )
    _apply_window_icon(ui)
    if config.personalized_pin == DEFAULT_PERSONALIZED_PIN:
        new_pin = ui.prompt_for_personalized_pin()
        if new_pin is not None:
            save_personalized_pin(config.config_path, new_pin)
            config = load_config(str(config.config_path))
            reader.personalized_pin = config.personalized_pin
            ui.show_message(ui.t("message.pin_saved"), kind="success")
    controller = AppController(reader=reader, ui=ui)
    controller.start()
    ui.mainloop()
    return 0
