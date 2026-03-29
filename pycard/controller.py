from __future__ import annotations

from datetime import datetime
import logging

from pycard.models import (
    ADMIN_CARD_ID,
    CARD_MAGIC2,
    DEFAULT_TOP_UP,
    Info,
    USER_CARD_ID,
    calculate_new_total,
)
from pycard.reader import ReaderService


LOGGER = logging.getLogger(__name__)


class AppController:
    def __init__(self, reader: ReaderService, ui, poll_interval_ms: int = 500) -> None:
        self.reader = reader
        self.ui = ui
        self.poll_interval_ms = poll_interval_ms
        self.info = Info(force=True)
        self._poll_job = None
        self._busy = False
        self._current_add_text = str(DEFAULT_TOP_UP)
        self._current_new_total = DEFAULT_TOP_UP
        self.ui.bind_controller(self)

    def start(self) -> None:
        self.refresh(force=True)

    def shutdown(self) -> None:
        self._cancel_poll()
        try:
            self.reader.transport.disconnect_card()
        except Exception:
            LOGGER.debug("reader shutdown cleanup failed", exc_info=True)

    def refresh(self, force: bool = False) -> None:
        self._cancel_poll()
        self.info.force = force
        self.ui.set_datetime(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self._detect_card()
        self._render()
        self.info.force = False
        if not self._busy:
            self._schedule_poll()

    def _schedule_poll(self) -> None:
        self._cancel_poll()
        self._poll_job = self.ui.after(self.poll_interval_ms, self._on_poll)

    def _cancel_poll(self) -> None:
        if self._poll_job is not None:
            self.ui.after_cancel(self._poll_job)
            self._poll_job = None

    def _on_poll(self) -> None:
        self._poll_job = None
        self.refresh(force=False)

    def _detect_card(self) -> None:
        self.reader.detect(self.info)
        if self.info.present and (self.info.change or self.info.force):
            self.reader.read(self.info)

    def _render(self) -> None:
        self.ui.set_presence(
            reader_present=self.info.reader_present,
            reader_name=self.info.reader_name,
            card_present=self.info.present,
        )

        if self.info.error:
            self.ui.show_message(self.info.error_str or self.ui.t("message.reader_error"), kind="error")
            return

        if not self.info.reader_present:
            if self.info.change or self.info.force:
                self.ui.show_idle()
            return

        if not self.info.present:
            if self.info.change or self.info.force:
                self.ui.show_idle()
            return

        if self.info.id == ADMIN_CARD_ID:
            if self.info.change or self.info.force:
                self.ui.show_admin_card(self.info.reader_name)
            return

        if self.info.change or self.info.force:
            self._current_add_text = str(DEFAULT_TOP_UP)
            self._current_new_total = calculate_new_total(self.info.value, self._current_add_text)
            self.ui.show_user_card(
                current_value=self.info.value,
                add_value=self._current_add_text,
                new_total=self._current_new_total,
                reader_name=self.info.reader_name,
            )

    def on_amount_changed(self, value: str) -> None:
        self._current_add_text = value
        self._current_new_total = calculate_new_total(self.info.value, value)
        self.ui.update_user_totals(current_value=self.info.value, new_total=self._current_new_total)

    def on_switch_to_admin(self) -> None:
        if not self.ui.confirm_switch_to_admin():
            return
        self.info.id = ADMIN_CARD_ID
        self._update_card()

    def on_switch_to_user(self) -> None:
        if not self.ui.confirm_switch_to_user():
            return
        self.info.id = USER_CARD_ID
        self._update_card()

    def on_card_update_requested(self) -> None:
        LOGGER.debug(
            "card update requested: current_value=%d add_text=%s computed_new_total=%d",
            self.info.value,
            self._current_add_text,
            self._current_new_total,
        )
        self.info.value = self._current_new_total
        self._update_card()

    def _update_card(self) -> None:
        if not self.info.present:
            self.ui.show_message(self.ui.t("message.no_card"), kind="error")
            return

        LOGGER.debug(
            "starting card update: reader=%s card_id=%d old_value=%d target_value=%d",
            self.info.reader_name,
            self.info.id,
            self.info.total,
            self.info.value,
        )
        self._busy = True
        self._cancel_poll()
        self.ui.set_busy(True, self.ui.t("status.card_update_in_progress"))

        if not self.reader.unlock(self.info):
            self._busy = False
            self.ui.set_busy(False)
            self.ui.show_message(self.info.error_str, kind="error")
            self._schedule_poll()
            return

        self.info.magic = CARD_MAGIC2
        if self.info.id == ADMIN_CARD_ID:
            self.info.value = 0
        self.info.total = self.info.value
        LOGGER.debug(
            "prepared card state for write: magic=%d id=%d total=%d value=%d",
            self.info.magic,
            self.info.id,
            self.info.total,
            self.info.value,
        )

        if not self.reader.update(self.info):
            self._busy = False
            self.ui.set_busy(False)
            self.ui.show_message(self.info.error_str, kind="error")
            self._schedule_poll()
            return

        LOGGER.debug("card update finished successfully, forcing refresh")
        self._busy = False
        self.ui.set_busy(False)
        self.ui.show_message(self.ui.t("message.card_update_done"), kind="success")
        self.refresh(force=True)
