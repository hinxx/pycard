from __future__ import annotations

import logging

from pycard.models import (
    CARD_DEFAULT_PIN,
    CARD_MAGIC0,
    CARD_RECORD_OFFSET,
    CARD_RECORD_SIZE,
    CardRecord,
    Info,
    decode_card_record,
    encode_card_record,
)
from pycard.pcsc import CardAbsentError, CardCommunicationError, MemoryCardTransport, PcscError


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

        try:
            LOGGER.debug(
                "unlocking card: reader=%s magic=%d id=%d unlocked=%s",
                info.reader_name,
                info.magic,
                info.id,
                info.unlocked,
            )
            if info.magic == CARD_MAGIC0:
                LOGGER.debug("card appears uninitialized, presenting default PIN and changing to app PIN")
                self.transport.present_pin(CARD_DEFAULT_PIN)
                self.transport.change_pin(self.personalized_pin)
            else:
                LOGGER.debug("presenting configured app PIN")
                self.transport.present_pin(self.personalized_pin)
        except (CardCommunicationError, CardAbsentError) as exc:
            info.error = True
            info.error_str = f"failed to unlock card: {exc}"
            LOGGER.error("card unlock failed: %s", exc)
            return False

        info.unlocked = True
        info.error = False
        info.error_str = ""
        LOGGER.debug("card unlock complete")
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
