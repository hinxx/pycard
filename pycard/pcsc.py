from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import Protocol


LOGGER = logging.getLogger(__name__)


class PcscError(RuntimeError):
    """Base PC/SC error."""


class BackendUnavailableError(PcscError):
    """The Python PC/SC bindings are not installed."""


class ReaderUnavailableError(PcscError):
    """No smart-card reader is available."""


class CardAbsentError(PcscError):
    """No smart card is present in the selected reader."""


class CardCommunicationError(PcscError):
    """The reader or card failed to complete a command."""


class PinVerificationError(CardCommunicationError):
    """The card rejected a PIN and returned its presentation error counter."""

    def __init__(self, error_counter: int) -> None:
        self.error_counter = error_counter & 0xFF
        super().__init__(f"PIN verification failed with error counter {self.error_counter:02X}")


class CardResetError(CardCommunicationError):
    """PC/SC reports that the card reset and the active handle is stale."""


class ReaderFamily(StrEnum):
    UNKNOWN = "unknown"
    ACR38 = "acr38"
    ACR39 = "acr39"


class PcscBackend(Protocol):
    def list_readers(self) -> list[object]:
        ...

    def is_card_present(self, reader_name: str) -> bool:
        ...

    def connect(self, reader: object) -> object:
        ...

    def disconnect(self, connection: object) -> None:
        ...

    def transmit(self, connection: object, payload: list[int]) -> tuple[list[int], int, int]:
        ...


class PyscardBackend:
    def __init__(self) -> None:
        try:
            from smartcard.Exceptions import CardConnectionException
            from smartcard.Exceptions import NoCardException
            from smartcard.CardConnection import CardConnection
            from smartcard.System import readers
            from smartcard.scard import SCARD_SCOPE_USER
            from smartcard.scard import SCARD_S_SUCCESS
            from smartcard.scard import SCARD_STATE_CHANGED
            from smartcard.scard import SCARD_STATE_EMPTY
            from smartcard.scard import SCARD_STATE_IGNORE
            from smartcard.scard import SCARD_STATE_INUSE
            from smartcard.scard import SCARD_STATE_MUTE
            from smartcard.scard import SCARD_STATE_PRESENT
            from smartcard.scard import SCARD_STATE_EXCLUSIVE
            from smartcard.scard import SCARD_STATE_UNKNOWN
            from smartcard.scard import SCARD_STATE_UNAWARE
            from smartcard.scard import SCARD_STATE_UNAVAILABLE
            from smartcard.scard import SCARD_STATE_UNPOWERED
            from smartcard.scard import SCARD_W_RESET_CARD
            from smartcard.scard import SCardEstablishContext
            from smartcard.scard import SCardGetErrorMessage
            from smartcard.scard import SCardGetStatusChange
            from smartcard.pcsc.PCSCExceptions import ListReadersException
        except ImportError as exc:  # pragma: no cover - depends on local install
            raise BackendUnavailableError(
                "pyscard is required. Install project dependencies first."
            ) from exc

        hresult, hcontext = SCardEstablishContext(SCARD_SCOPE_USER)
        if hresult != SCARD_S_SUCCESS:
            raise BackendUnavailableError(f"failed to establish PC/SC context: {SCardGetErrorMessage(hresult)}")

        self._CardConnectionException = CardConnectionException
        self._NoCardException = NoCardException
        self._T0_protocol = CardConnection.T0_protocol
        self._readers = readers
        self._ListReadersException = ListReadersException
        self._SCARD_S_SUCCESS = SCARD_S_SUCCESS
        self._SCARD_STATE_CHANGED = SCARD_STATE_CHANGED
        self._SCARD_STATE_EMPTY = SCARD_STATE_EMPTY
        self._SCARD_STATE_IGNORE = SCARD_STATE_IGNORE
        self._SCARD_STATE_INUSE = SCARD_STATE_INUSE
        self._SCARD_STATE_MUTE = SCARD_STATE_MUTE
        self._SCARD_STATE_PRESENT = SCARD_STATE_PRESENT
        self._SCARD_STATE_EXCLUSIVE = SCARD_STATE_EXCLUSIVE
        self._SCARD_STATE_UNKNOWN = SCARD_STATE_UNKNOWN
        self._SCARD_STATE_UNAWARE = SCARD_STATE_UNAWARE
        self._SCARD_STATE_UNAVAILABLE = SCARD_STATE_UNAVAILABLE
        self._SCARD_STATE_UNPOWERED = SCARD_STATE_UNPOWERED
        self._SCARD_W_RESET_CARD = SCARD_W_RESET_CARD
        self._SCardGetStatusChange = SCardGetStatusChange
        self._SCardGetErrorMessage = SCardGetErrorMessage
        self._hcontext = hcontext

    def list_readers(self) -> list[object]:
        try:
            available_readers = list(self._readers())
        except self._ListReadersException as exc:  # pragma: no cover - hardware dependent
            raise ReaderUnavailableError(str(exc)) from exc
        LOGGER.debug("available readers: %s", [str(reader) for reader in available_readers])
        return available_readers

    def _describe_event_state(self, event_state: int) -> str:
        flags: list[str] = []
        if event_state & self._SCARD_STATE_CHANGED:
            flags.append("CHANGED")
        if event_state & self._SCARD_STATE_IGNORE:
            flags.append("IGNORE")
        if event_state & self._SCARD_STATE_UNKNOWN:
            flags.append("UNKNOWN")
        if event_state & self._SCARD_STATE_UNAVAILABLE:
            flags.append("UNAVAILABLE")
        if event_state & self._SCARD_STATE_EMPTY:
            flags.append("EMPTY")
        if event_state & self._SCARD_STATE_PRESENT:
            flags.append("PRESENT")
        if event_state & self._SCARD_STATE_EXCLUSIVE:
            flags.append("EXCLUSIVE")
        if event_state & self._SCARD_STATE_INUSE:
            flags.append("INUSE")
        if event_state & self._SCARD_STATE_MUTE:
            flags.append("MUTE")
        if event_state & self._SCARD_STATE_UNPOWERED:
            flags.append("UNPOWERED")
        if not flags and event_state == self._SCARD_STATE_UNAWARE:
            flags.append("UNAWARE")
        return "|".join(flags) if flags else f"0x{event_state:08X}"

    def is_card_present(self, reader_name: str) -> bool:
        hresult, states = self._SCardGetStatusChange(
            self._hcontext,
            10,
            [(reader_name, self._SCARD_STATE_UNAWARE)],
        )
        if hresult != self._SCARD_S_SUCCESS:  # pragma: no cover - hardware dependent
            raise ReaderUnavailableError(self._SCardGetErrorMessage(hresult))

        _reader_name, event_state, _atr = states[0]
        LOGGER.debug(
            "reader status change: reader=%s event_state=0x%08X flags=%s",
            reader_name,
            event_state,
            self._describe_event_state(event_state),
        )
        if event_state & self._SCARD_STATE_MUTE:
            raise CardCommunicationError(
                "card is physically present but not responding (PC/SC MUTE); "
                "remove and reinsert it or reconnect the reader"
            )
        if event_state & self._SCARD_STATE_PRESENT:
            return True
        if event_state & self._SCARD_STATE_EMPTY:
            return False
        return False

    def connect(self, reader: object) -> object:
        try:
            connection = reader.createConnection()
            # ACS documents T=0 for the memory-card pseudo-APDU command set.
            connection.connect(protocol=self._T0_protocol)
            LOGGER.debug("connected to card via reader %s using T=0", reader)
        except self._NoCardException as exc:  # pragma: no cover - hardware dependent
            raise CardAbsentError(str(exc)) from exc
        except self._CardConnectionException as exc:  # pragma: no cover - hardware dependent
            raise CardCommunicationError(f"failed to connect to card via {reader}: {exc}") from exc
        return connection

    def disconnect(self, connection: object) -> None:
        try:
            connection.disconnect()
        except Exception:  # pragma: no cover - backend cleanup only
            LOGGER.debug("failed to disconnect reader connection cleanly", exc_info=True)

    def transmit(self, connection: object, payload: list[int]) -> tuple[list[int], int, int]:
        try:
            response, sw1, sw2 = connection.transmit(payload)
        except Exception as exc:  # pragma: no cover - hardware dependent
            if getattr(exc, "hresult", None) == self._SCARD_W_RESET_CARD:
                raise CardResetError("card was reset; the PC/SC connection must be reopened") from exc
            raise CardCommunicationError(str(exc)) from exc
        return response, sw1, sw2


@dataclass(slots=True)
class MemoryCardTransport:
    backend: PcscBackend
    reader: object | None = None
    reader_name: str = ""
    reader_family: ReaderFamily = ReaderFamily.UNKNOWN
    connection: object | None = None

    @staticmethod
    def _detect_reader_family(reader_name: str) -> ReaderFamily:
        normalized = reader_name.upper()
        if "ACR38" in normalized:
            return ReaderFamily.ACR38
        if "ACR39" in normalized:
            return ReaderFamily.ACR39
        return ReaderFamily.UNKNOWN

    def _refresh_reader(self) -> object:
        readers = self.backend.list_readers()
        if not readers:
            self.reader = None
            self.reader_name = ""
            self.reader_family = ReaderFamily.UNKNOWN
            self.disconnect_card()
            raise ReaderUnavailableError("no PC/SC readers available")

        selected = None
        if self.reader_name:
            for candidate in readers:
                if str(candidate) == self.reader_name:
                    selected = candidate
                    break
        if selected is None:
            selected = readers[0]

        selected_name = str(selected)
        if self.reader_name and selected_name != self.reader_name:
            LOGGER.debug(
                "reader changed from %s to %s; discarding card connection",
                self.reader_name,
                selected_name,
            )
            self.disconnect_card()

        self.reader = selected
        self.reader_name = selected_name
        self.reader_family = self._detect_reader_family(self.reader_name)
        LOGGER.debug(
            "selected reader: name=%s family=%s",
            self.reader_name,
            self.reader_family,
        )
        return selected

    def disconnect_card(self) -> None:
        if self.connection is not None:
            LOGGER.debug("discarding card connection for reader %s", self.reader_name or "<unknown>")
            self.backend.disconnect(self.connection)
        self.connection = None

    def is_reader_present(self) -> bool:
        try:
            self._refresh_reader()
        except ReaderUnavailableError:
            return False
        return True

    def is_card_present(self) -> bool:
        if not self.is_reader_present():
            return False
        try:
            if not self.backend.is_card_present(self.reader_name):
                self.disconnect_card()
                return False
            self._ensure_connection()
        except CardAbsentError:
            self.disconnect_card()
            return False
        return True

    def _ensure_connection(self) -> object:
        if self.connection is not None:
            return self.connection
        reader = self._refresh_reader()
        self.connection = self.backend.connect(reader)
        return self.connection

    def transmit(self, payload: list[int]) -> tuple[bytes, tuple[int, int]]:
        connection = self._ensure_connection()
        LOGGER.debug("card request [%d]: %s", len(payload), " ".join(f"{b:02x}" for b in payload))
        try:
            response, sw1, sw2 = self.backend.transmit(connection, payload)
        except CardCommunicationError:
            # A failed/reset PC/SC handle is never reused. The next poll or
            # operation will establish a completely fresh connection.
            if self.connection is connection:
                self.disconnect_card()
            raise
        LOGGER.debug(
            "card response [%d]: %s %02x %02x",
            len(response),
            " ".join(f"{b:02x}" for b in response),
            sw1,
            sw2,
        )
        return bytes(response), (sw1, sw2)

    def _check_sw(self, received: tuple[int, int], expected: tuple[int, int]) -> None:
        if received == expected:
            return
        raise CardCommunicationError(
            f"unexpected status word {received[0]:02X} {received[1]:02X}, "
            f"expected {expected[0]:02X} {expected[1]:02X}"
        )

    def select_memory_card(self) -> None:
        _, sw = self.transmit([0xFF, 0xA4, 0x00, 0x00, 0x01, 0x06])
        self._check_sw(sw, (0x90, 0x00))

    def read_memory_card(self, address: int, length: int) -> bytes:
        response, sw = self.transmit([0xFF, 0xB0, 0x00, address & 0xFF, length & 0xFF])
        self._check_sw(sw, (0x90, 0x00))
        normalized = self._normalize_read_memory_response(response, requested_length=length)
        LOGGER.debug(
            "normalized memory read: family=%s requested=%d raw_len=%d normalized_len=%d",
            self.reader_family,
            length,
            len(response),
            len(normalized),
        )
        return normalized

    def _normalize_read_memory_response(self, response: bytes, requested_length: int) -> bytes:
        # ACR39 appends four protection bytes to SLE44x2 memory-card reads.
        if self.reader_family == ReaderFamily.ACR39 and len(response) == requested_length + 4:
            LOGGER.debug("stripping 4 trailing protection bytes from ACR39 READ_MEMORY_CARD response")
            return response[:requested_length]
        return response

    def write_memory_card(self, address: int, payload: bytes) -> None:
        packet = [0xFF, 0xD0, 0x00, address & 0xFF, len(payload) & 0xFF, *payload]
        _, sw = self.transmit(packet)
        self._check_sw(sw, (0x90, 0x00))

    def get_error_count(self) -> int:
        response, sw = self.transmit([0xFF, 0xB1, 0x00, 0x00, 0x04])
        self._check_sw(sw, (0x90, 0x00))
        if not response:
            self.disconnect_card()
            raise CardCommunicationError("PIN counter response was empty")

        error_count = int(response[0])
        if error_count & ~0x07:
            self.disconnect_card()
            raise CardCommunicationError(
                f"invalid PIN counter {error_count:02X}; discarding transient card connection"
            )
        return error_count

    def present_pin(self, pin: tuple[int, int, int]) -> None:
        _, sw = self.transmit([0xFF, 0x20, 0x00, 0x00, 0x03, *pin])
        # The ACR38x CCID and ACR39 manuals define SW2 as the SLE4442
        # presentation error counter. Only 0x07 means the PIN was accepted.
        if sw[0] != 0x90:
            raise CardCommunicationError(
                f"PIN presentation failed with status word {sw[0]:02X} {sw[1]:02X}"
            )
        if sw[1] != 0x07:
            raise PinVerificationError(sw[1])

    def change_pin(self, pin: tuple[int, int, int]) -> None:
        _, sw = self.transmit([0xFF, 0xD2, 0x00, 0x01, 0x03, *pin])
        self._check_sw(sw, (0x90, 0x00))
