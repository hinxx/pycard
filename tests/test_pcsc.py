from __future__ import annotations

from collections.abc import Sequence

import pytest

from pycard.pcsc import CardCommunicationError, CardResetError, MemoryCardTransport, PinVerificationError, PyscardBackend, ReaderFamily


class StubBackend:
    def __init__(self, response: Sequence[int], sw1: int, sw2: int) -> None:
        self.response = list(response)
        self.sw1 = sw1
        self.sw2 = sw2
        self.requests: list[list[int]] = []
        self.disconnected: list[object] = []

    def list_readers(self) -> list[object]:
        return []

    def is_card_present(self, reader_name: str) -> bool:
        return True

    def connect(self, reader: object) -> object:
        return object()

    def disconnect(self, connection: object) -> None:
        self.disconnected.append(connection)

    def transmit(self, connection: object, payload: list[int]) -> tuple[list[int], int, int]:
        self.requests.append(payload)
        return self.response, self.sw1, self.sw2


@pytest.mark.parametrize("family", [ReaderFamily.ACR38, ReaderFamily.ACR39])
def test_present_pin_accepts_verified_pin_on_supported_readers(family: ReaderFamily) -> None:
    backend = StubBackend([], 0x90, 0x07)
    transport = MemoryCardTransport(
        backend=backend,
        reader_family=family,
        connection=object(),
    )

    transport.present_pin((0xFF, 0xFF, 0xFF))

    assert backend.requests == [[0xFF, 0x20, 0x00, 0x00, 0x03, 0xFF, 0xFF, 0xFF]]


@pytest.mark.parametrize("error_count", [0x00, 0x01, 0x03, 0x06])
def test_present_pin_rejects_failed_verification(error_count: int) -> None:
    backend = StubBackend([], 0x90, error_count)
    transport = MemoryCardTransport(backend=backend, connection=object())

    with pytest.raises(PinVerificationError) as exc_info:
        transport.present_pin((0xFF, 0xFF, 0xFF))

    assert exc_info.value.error_counter == error_count


def test_present_pin_rejects_reader_error_status() -> None:
    backend = StubBackend([], 0x63, 0x00)
    transport = MemoryCardTransport(backend=backend, connection=object())

    with pytest.raises(CardCommunicationError, match="63 00"):
        transport.present_pin((0xFF, 0xFF, 0xFF))


def test_pyscard_backend_connects_with_explicit_t0_protocol() -> None:
    class FakeConnection:
        def __init__(self) -> None:
            self.protocol: int | None = None

        def connect(self, protocol: int | None = None) -> None:
            self.protocol = protocol

    class FakeReader:
        def __init__(self) -> None:
            self.connection = FakeConnection()

        def createConnection(self) -> FakeConnection:
            return self.connection

        def __str__(self) -> str:
            return "ACS test reader"

    backend = object.__new__(PyscardBackend)
    backend._T0_protocol = 1
    backend._NoCardException = type("NoCard", (Exception,), {})
    backend._CardConnectionException = type("ConnectionError", (Exception,), {})
    reader = FakeReader()

    assert backend.connect(reader) is reader.connection
    assert reader.connection.protocol == 1


def test_pyscard_backend_preserves_card_reset_as_structured_error() -> None:
    class ResetException(Exception):
        hresult = 1234

    class ResetConnection:
        def transmit(self, payload: list[int]) -> tuple[list[int], int, int]:
            raise ResetException("card was reset")

    backend = object.__new__(PyscardBackend)
    backend._SCARD_W_RESET_CARD = 1234

    with pytest.raises(CardResetError):
        backend.transmit(ResetConnection(), [0xFF, 0xA4])


def test_transport_discards_connection_after_card_reset() -> None:
    class ResetBackend(StubBackend):
        def transmit(self, connection: object, payload: list[int]) -> tuple[list[int], int, int]:
            raise CardResetError("card reset")

    backend = ResetBackend([], 0x90, 0x00)
    connection = object()
    transport = MemoryCardTransport(backend=backend, connection=connection)

    with pytest.raises(CardResetError):
        transport.transmit([0xFF, 0xA4])

    assert transport.connection is None
    assert backend.disconnected == [connection]


def test_card_removal_discards_connection() -> None:
    class EmptyReaderBackend(StubBackend):
        reader = object()

        def list_readers(self) -> list[object]:
            return [self.reader]

        def is_card_present(self, reader_name: str) -> bool:
            return False

    backend = EmptyReaderBackend([], 0x90, 0x00)
    connection = object()
    transport = MemoryCardTransport(backend=backend, connection=connection)

    assert not transport.is_card_present()

    assert transport.connection is None
    assert backend.disconnected == [connection]


@pytest.mark.parametrize("invalid_counter", [0xFF, 0x08, 0xF7])
def test_invalid_pin_counter_discards_transient_connection(invalid_counter: int) -> None:
    backend = StubBackend([invalid_counter, 0, 0, 0], 0x90, 0x00)
    connection = object()
    transport = MemoryCardTransport(backend=backend, connection=connection)

    with pytest.raises(CardCommunicationError, match="invalid PIN counter"):
        transport.get_error_count()

    assert transport.connection is None
    assert backend.disconnected == [connection]


@pytest.mark.parametrize("valid_counter", range(0x08))
def test_valid_pin_counters_are_accepted(valid_counter: int) -> None:
    backend = StubBackend([valid_counter, 0, 0, 0], 0x90, 0x00)
    transport = MemoryCardTransport(backend=backend, connection=object())

    assert transport.get_error_count() == valid_counter
