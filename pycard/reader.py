from __future__ import annotations

import logging

from pycard.models import (
    ADMIN_CARD_ID,
    CARD_DEFAULT_PIN,
    CARD_MAGIC0,
    CARD_MAGIC2,
    CARD_RECORD_OFFSET,
    CARD_RECORD_SIZE,
    USER_CARD_ID,
    CardRecord,
    Info,
    decode_card_record,
    encode_card_record,
)
from pycard.pcsc import (
    CardAbsentError,
    CardCommunicationError,
    MemoryCardTransport,
    PcscError,
    PinVerificationError,
)


LOGGER = logging.getLogger(__name__)


class ReaderService:
    def __init__(self, transport: MemoryCardTransport, personalized_pin: tuple[int, int, int]) -> None:
        self.transport = transport
        self.personalized_pin = personalized_pin

    def detect(self, info: Info) -> bool:
        previous_present = info.present
        previous_reader_present = info.reader_present
        previous_reader_name = info.reader_name
        previous_error = info.error
        previous_error_str = info.error_str

        try:
            info.reader_present = self.transport.is_reader_present()
            info.reader_name = self.transport.reader_name
            info.present = info.reader_present and self.transport.is_card_present()
            info.error = False
            info.error_str = ""
        except PcscError as exc:
            info.reader_present = False
            info.present = False
            info.error = True
            info.error_str = str(exc)
            LOGGER.warning("reader detection failed: %s", exc)

        info.change = any(
            (
                previous_present != info.present,
                previous_reader_present != info.reader_present,
                previous_reader_name != info.reader_name,
                previous_error != info.error,
                previous_error_str != info.error_str,
            )
        )
        if info.change:
            info.unlocked = False
        if not info.present:
            # Card-specific state must never survive removal and be mistaken
            # for the next card inserted into the reader.
            info.unlocked = False
            info.pin_verification_failed = False
            info.personalized_during_unlock = False
            info.pin_error_counter = 0xFF
            info.magic = CARD_MAGIC0
            info.id = USER_CARD_ID
            info.total = 0
            info.value = 0
        return info.present

    def read(self, info: Info) -> bool:
        try:
            LOGGER.debug(
                "reading card: reader=%s offset=%d size=%d",
                info.reader_name,
                CARD_RECORD_OFFSET,
                CARD_RECORD_SIZE,
            )
            self.transport.select_memory_card()
            info.pin_error_counter = self.transport.get_error_count()
            payload = self.transport.read_memory_card(CARD_RECORD_OFFSET, CARD_RECORD_SIZE)
            record = decode_card_record(payload)
        except (PcscError, ValueError) as exc:
            info.error = True
            info.error_str = f"failed to read card: {exc}"
            LOGGER.error("card read failed: %s", exc)
            return False

        info.magic = record.magic
        info.id = record.id
        info.total = record.total
        info.value = record.value
        info.error = False
        info.error_str = ""
        # Selecting the card type power-cycles the card and clears PIN
        # authentication from any earlier operation.
        info.unlocked = False
        info.pin_verification_failed = False
        info.personalized_during_unlock = False
        LOGGER.debug(
            "card read complete: magic=%d id=%d total=%d value=%d pin_errors=%d payload=%s",
            info.magic,
            info.id,
            info.total,
            info.value,
            info.pin_error_counter,
            payload.hex(),
        )
        return True

    def unlock(self, info: Info) -> bool:
        if info.unlocked:
            LOGGER.debug("card already unlocked")
            return True

        info.personalized_during_unlock = False
        try:
            LOGGER.debug(
                "unlocking card: reader=%s magic=%d id=%d unlocked=%s",
                info.reader_name,
                info.magic,
                info.id,
                info.unlocked,
            )
            if info.magic == CARD_MAGIC0:
                raise CardCommunicationError(
                    "blank card must be personalized before it can be updated"
                )
            LOGGER.debug("presenting configured app PIN")
            self.transport.present_pin(self.personalized_pin)
        except PinVerificationError as exc:
            info.pin_error_counter = exc.error_counter
            info.pin_verification_failed = True
            info.error = True
            info.error_str = ""
            LOGGER.error("card PIN verification failed: counter=%02X", exc.error_counter)
            return False
        except (CardCommunicationError, CardAbsentError) as exc:
            info.pin_verification_failed = False
            info.error = True
            info.error_str = f"failed to unlock card: {exc}"
            LOGGER.error("card unlock failed: %s", exc)
            return False

        info.unlocked = True
        info.error = False
        info.error_str = ""
        info.pin_verification_failed = False
        LOGGER.debug("card unlock complete")
        return True

    def personalize(self, info: Info, card_id: int) -> bool:
        """Change a blank card's PIN and initialize its wallet record."""
        if card_id not in (USER_CARD_ID, ADMIN_CARD_ID):
            raise ValueError(f"unsupported card id: {card_id}")

        info.unlocked = False
        info.personalized_during_unlock = False
        pin_changed = False
        try:
            if info.magic != CARD_MAGIC0:
                raise CardCommunicationError("card is already personalized")
            if self.personalized_pin == CARD_DEFAULT_PIN:
                raise CardCommunicationError(
                    "a non-default configured PIN is required to personalize a card"
                )

            LOGGER.debug(
                "personalizing blank card: reader=%s target_id=%d",
                info.reader_name,
                card_id,
            )
            self.transport.present_pin(CARD_DEFAULT_PIN)
            self.transport.change_pin(self.personalized_pin)
            pin_changed = True

            record = CardRecord(magic=CARD_MAGIC2, id=card_id, total=0, value=0)
            payload = encode_card_record(record)
            self.transport.write_memory_card(CARD_RECORD_OFFSET, payload)
            written_payload = self.transport.read_memory_card(CARD_RECORD_OFFSET, CARD_RECORD_SIZE)
            if written_payload != payload:
                raise CardCommunicationError("wallet record verification failed")
        except PinVerificationError as exc:
            info.pin_error_counter = exc.error_counter
            info.pin_verification_failed = True
            info.error = True
            info.error_str = ""
            LOGGER.error("blank card PIN verification failed: counter=%02X", exc.error_counter)
            return False
        except PcscError as exc:
            info.pin_verification_failed = False
            info.error = True
            if pin_changed:
                info.error_str = (
                    "PIN was changed to the configured value, but card personalization failed: "
                    f"{exc}"
                )
            else:
                info.error_str = f"failed to personalize card: {exc}"
            LOGGER.error("card personalization failed: %s", exc)
            return False

        info.magic = record.magic
        info.id = record.id
        info.total = record.total
        info.value = record.value
        info.unlocked = True
        info.error = False
        info.error_str = ""
        info.pin_verification_failed = False
        LOGGER.debug("card personalization complete: id=%d", card_id)
        return True

    def update(self, info: Info) -> bool:
        if not info.unlocked:
            info.error = True
            info.error_str = "card still locked"
            return False

        record = CardRecord(
            magic=info.magic,
            id=info.id,
            total=info.total,
            value=info.value,
        )
        payload = encode_card_record(record)
        LOGGER.debug(
            "writing card: magic=%d id=%d total=%d value=%d payload=%s",
            record.magic,
            record.id,
            record.total,
            record.value,
            payload.hex(),
        )

        try:
            self.transport.write_memory_card(CARD_RECORD_OFFSET, payload)
        except PcscError as exc:
            info.error = True
            info.error_str = f"failed to write card: {exc}"
            LOGGER.error("card update failed: %s", exc)
            return False

        info.error = False
        info.error_str = ""
        LOGGER.debug("card write complete")
        return True
