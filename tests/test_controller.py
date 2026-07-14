from __future__ import annotations

import pytest

from pycard.controller import AppController
from pycard.i18n import I18n
from pycard.models import ADMIN_CARD_ID, CARD_DEFAULT_PIN, CARD_MAGIC0, CARD_MAGIC2, USER_CARD_ID


class StubReader:
    pass


class StubUi:
    def __init__(self) -> None:
        self.i18n = I18n("en")
        self.messages: list[tuple[str, str]] = []
        self.blank_card_choice: str | None = None
        self.blank_card_prompt_count = 0
        self.user_cards: list[dict[str, object]] = []
        self.admin_cards: list[str] = []

    def bind_controller(self, controller: AppController) -> None:
        self.controller = controller

    def t(self, key: str, **kwargs: object) -> str:
        return self.i18n.t(key, **kwargs)

    def set_presence(self, **kwargs: object) -> None:
        pass

    def show_message(self, text: str, kind: str = "info") -> None:
        self.messages.append((text, kind))

    def show_idle(self) -> None:
        pass

    def set_busy(self, is_busy: bool, status_text: str | None = None) -> None:
        pass

    def prompt_for_blank_card_type(self) -> str | None:
        self.blank_card_prompt_count += 1
        return self.blank_card_choice

    def show_user_card(self, **kwargs: object) -> None:
        self.user_cards.append(kwargs)

    def show_admin_card(self, reader_name: str) -> None:
        self.admin_cards.append(reader_name)


def test_pin_warning_reports_remaining_attempts_and_stays_visible() -> None:
    ui = StubUi()
    controller = AppController(StubReader(), ui)  # type: ignore[arg-type]
    controller.info.present = True
    controller.info.reader_present = True
    controller._pin_warning_counter = 0x03

    controller._render()
    controller._render()

    assert len(ui.messages) == 2
    assert all("Remaining attempts: 2" in message for message, _kind in ui.messages)
    assert all(kind == "error" for _message, kind in ui.messages)


def test_locked_pin_warning_explains_permanent_lockout() -> None:
    ui = StubUi()
    controller = AppController(StubReader(), ui)  # type: ignore[arg-type]
    controller.info.present = True
    controller.info.reader_present = True
    controller._pin_warning_counter = 0x00

    controller._render()

    assert "permanently locked" in ui.messages[-1][0]


def test_pin_warning_clears_after_card_removal() -> None:
    ui = StubUi()
    controller = AppController(StubReader(), ui)  # type: ignore[arg-type]
    controller.info.present = False
    controller.info.reader_present = True
    controller._pin_warning_counter = 0x03

    controller._render()

    assert controller._pin_warning_counter is None


class BlankCardReader:
    def __init__(self, personalized_pin=(0x11, 0x22, 0x33)) -> None:
        self.personalized_pin = personalized_pin
        self.personalized_id: int | None = None
        self.read_calls = 0

    def detect(self, info) -> bool:
        info.reader_present = True
        info.reader_name = "test reader"
        info.present = True
        info.change = True
        return True

    def read(self, info) -> bool:
        self.read_calls += 1
        info.error = False
        info.unlocked = False
        if self.personalized_id is None:
            info.magic = CARD_MAGIC0
            info.id = 0xFFFFFFFF
            info.total = 0xFFFFFFFF
            info.value = 0xFFFFFFFF
        else:
            info.magic = CARD_MAGIC2
            info.id = self.personalized_id
            info.total = 0
            info.value = 0
        return True

    def personalize(self, info, card_id: int) -> bool:
        self.personalized_id = card_id
        info.magic = CARD_MAGIC2
        info.id = card_id
        info.total = 0
        info.value = 0
        return True


@pytest.mark.parametrize(
    ("choice", "expected_id"),
    [("user", USER_CARD_ID), ("admin", ADMIN_CARD_ID)],
)
def test_blank_card_is_personalized_as_selected_then_reread(choice: str, expected_id: int) -> None:
    ui = StubUi()
    ui.blank_card_choice = choice
    reader = BlankCardReader()
    controller = AppController(reader, ui)  # type: ignore[arg-type]

    controller._detect_card()
    controller._detect_card()

    assert reader.personalized_id == expected_id
    assert reader.read_calls == 3
    assert (controller.info.magic, controller.info.id) == (CARD_MAGIC2, expected_id)
    assert (controller.info.total, controller.info.value) == (0, 0)
    assert not controller.info.unlocked


def test_personalized_user_card_replaces_confirmation_with_credit_view() -> None:
    ui = StubUi()
    ui.blank_card_choice = "user"
    reader = BlankCardReader()
    controller = AppController(reader, ui)  # type: ignore[arg-type]

    controller._detect_card()
    controller._render()
    assert "really blank" in ui.messages[-1][0]

    controller._detect_card()
    controller._render()

    assert len(ui.user_cards) == 1
    assert ui.user_cards[0]["current_value"] == 0
    assert ui.user_cards[0]["new_total"] == 2


def test_cancelled_blank_card_prompt_is_not_repeated_until_removal() -> None:
    ui = StubUi()
    reader = BlankCardReader()
    controller = AppController(reader, ui)  # type: ignore[arg-type]

    controller._detect_card()
    controller._detect_card()
    controller._detect_card()
    controller._render()

    assert ui.blank_card_prompt_count == 1
    assert reader.personalized_id is None
    assert "not personalized" in ui.messages[-1][0]


def test_default_configured_pin_blocks_blank_card_personalization() -> None:
    ui = StubUi()
    ui.blank_card_choice = "user"
    reader = BlankCardReader(personalized_pin=CARD_DEFAULT_PIN)
    controller = AppController(reader, ui)  # type: ignore[arg-type]

    controller._detect_card()
    controller._detect_card()
    controller._render()

    assert ui.blank_card_prompt_count == 0
    assert reader.personalized_id is None
    assert "non-default personal PIN" in ui.messages[-1][0]


def test_single_transient_blank_read_does_not_open_personalization_dialog() -> None:
    class TransientBlankReader(BlankCardReader):
        def read(self, info) -> bool:
            self.read_calls += 1
            info.error = False
            info.unlocked = False
            if self.read_calls == 1:
                info.magic = CARD_MAGIC0
                info.id = 0xFFFFFFFF
                info.total = 0xFFFFFFFF
                info.value = 0xFFFFFFFF
            else:
                info.magic = CARD_MAGIC2
                info.id = USER_CARD_ID
                info.total = 0
                info.value = 0
            return True

    ui = StubUi()
    ui.blank_card_choice = "user"
    reader = TransientBlankReader()
    controller = AppController(reader, ui)  # type: ignore[arg-type]

    controller._detect_card()
    controller._detect_card()

    assert ui.blank_card_prompt_count == 0
    assert reader.personalized_id is None
    assert controller.info.magic == CARD_MAGIC2
