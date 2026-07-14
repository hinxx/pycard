from __future__ import annotations

import argparse
from dataclasses import dataclass
import logging
import string
import sys
import time

from pycard.config import load_config
from pycard.models import (
    CARD_DEFAULT_PIN,
    CARD_MAGIC2,
    CARD_RECORD_OFFSET,
    CARD_RECORD_SIZE,
    USER_CARD_ID,
    CardRecord,
    decode_card_record,
    encode_card_record,
)
from pycard.pcsc import (
    CardCommunicationError,
    CardResetError,
    MemoryCardTransport,
    PcscError,
    PinVerificationError,
    PyscardBackend,
)


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PinSelection:
    pin: tuple[int, int, int]
    source: str
    description: str


def parse_pin(value: str) -> tuple[int, int, int]:
    parts = value.split()
    if len(parts) != 3 or any(
        len(part) != 2 or any(char not in string.hexdigits for char in part)
        for part in parts
    ):
        raise ValueError("enter exactly three hexadecimal bytes, for example 11 22 33")
    return int(parts[0], 16), int(parts[1], 16), int(parts[2], 16)


def format_hex_dump(payload: bytes, start_address: int) -> str:
    lines: list[str] = []
    for offset in range(0, len(payload), 16):
        chunk = payload[offset : offset + 16]
        hex_bytes = " ".join(f"{byte:02X}" for byte in chunk)
        text = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in chunk)
        lines.append(f"{start_address + offset:04X}  {hex_bytes:<47}  |{text}|")
    return "\n".join(lines)


def available_attempts(error_counter: int) -> int:
    return (error_counter & 0x07).bit_count()


def wait_for_card(transport: MemoryCardTransport, poll_interval: float) -> None:
    last_state: str | None = None
    while True:
        try:
            if not transport.is_reader_present():
                state = "reader-missing"
                message = "Waiting for a PC/SC reader..."
            elif not transport.is_card_present():
                state = "card-missing"
                message = f"Reader detected: {transport.reader_name}\nWaiting for a card..."
            else:
                print(f"Card detected in {transport.reader_name}")
                return
        except CardCommunicationError as exc:
            transport.disconnect_card()
            state = "card-connection-error"
            message = f"Card/reader connection is not ready: {exc}\nRetrying..."

        if state != last_state:
            print(message)
            last_state = state
        time.sleep(poll_interval)


def read_card_snapshot(
    transport: MemoryCardTransport,
    poll_interval: float,
) -> tuple[int, bytes]:
    """Read initial card state, rebuilding transiently bad connections."""
    while True:
        try:
            transport.select_memory_card()
            error_counter = transport.get_error_count()
            payload = transport.read_memory_card(CARD_RECORD_OFFSET, CARD_RECORD_SIZE)
            return error_counter, payload
        except CardCommunicationError as exc:
            LOGGER.warning("initial card read was invalid; reconnecting: %s", exc)
            print(f"Card read is not ready: {exc}\nDiscarding the connection and retrying...")
            transport.disconnect_card()
            time.sleep(poll_interval)
            wait_for_card(transport, poll_interval)


def prompt_for_pin(
    config_path: str | None,
    *,
    prompt: str = "PIN [default/config/HH HH HH/quit]: ",
    cancel_choices: frozenset[str] = frozenset({"quit", "q"}),
) -> PinSelection | None:
    while True:
        raw_value = input(prompt).strip()
        choice = raw_value.lower()
        if choice in cancel_choices:
            return None
        if choice == "default":
            return PinSelection(CARD_DEFAULT_PIN, "default", "default PIN")
        if choice == "config":
            config = load_config(config_path)
            if not config.exists:
                print(f"No config file found at {config.config_path}.", file=sys.stderr)
                continue
            return PinSelection(config.personalized_pin, "config", f"PIN from {config.config_path}")
        try:
            return PinSelection(parse_pin(raw_value), "entry", "entered PIN")
        except ValueError as exc:
            print(f"Invalid PIN: {exc}", file=sys.stderr)


def apply_pin_change(transport: MemoryCardTransport, new_pin: tuple[int, int, int]) -> bool:
    resetting_to_default = new_pin == CARD_DEFAULT_PIN
    if resetting_to_default:
        erased_record = b"\xFF" * CARD_RECORD_SIZE
        try:
            transport.write_memory_card(CARD_RECORD_OFFSET, erased_record)
            written_record = transport.read_memory_card(CARD_RECORD_OFFSET, CARD_RECORD_SIZE)
        except PcscError as exc:
            raise CardCommunicationError(
                "could not verify the wallet-record erase; the PIN was not changed"
            ) from exc
        if written_record != erased_record:
            raise CardCommunicationError(
                "wallet-record erase verification failed; the PIN was not changed"
            )

    try:
        transport.change_pin(new_pin)
    except PcscError as exc:
        if resetting_to_default:
            raise CardCommunicationError(
                "the wallet record was erased, but changing the PIN failed; "
                "retry using the card's previous PIN"
            ) from exc
        raise
    return resetting_to_default


def initialize_wallet_record(transport: MemoryCardTransport) -> bytes:
    payload = encode_card_record(
        CardRecord(
            magic=CARD_MAGIC2,
            id=USER_CARD_ID,
            total=0,
            value=0,
        )
    )
    transport.write_memory_card(CARD_RECORD_OFFSET, payload)
    written_record = transport.read_memory_card(CARD_RECORD_OFFSET, CARD_RECORD_SIZE)
    if written_record != payload:
        raise CardCommunicationError("wallet-record initialization verification failed")
    return payload


def prompt_to_initialize_wallet(transport: MemoryCardTransport) -> bool:
    print(
        f"Personalization will overwrite the wallet record with magic={CARD_MAGIC2}, "
        f"id={USER_CARD_ID}, total=0, value=0."
    )
    confirmation = input("Type INITIALIZE to write and verify this wallet record, or press Enter to skip: ").strip()
    if confirmation != "INITIALIZE":
        print("Wallet-record initialization skipped.")
        return False
    initialize_wallet_record(transport)
    print("Wallet record initialized and verified successfully.")
    return True


def prompt_and_change_pin(
    transport: MemoryCardTransport,
    config_path: str | None,
) -> int:
    selection = prompt_for_pin(
        config_path,
        prompt="New PIN [default/config/HH HH HH/skip]: ",
        cancel_choices=frozenset({"skip", "s", "quit", "q"}),
    )
    if selection is None:
        print("PIN change skipped.")
        return 0
    new_pin = selection.pin

    resetting_to_default = new_pin == CARD_DEFAULT_PIN
    if resetting_to_default:
        print(
            "WARNING: setting FF FF FF will permanently erase all 16 wallet-record bytes "
            "at offset 0x40, including the magic value."
        )
        confirmation = input("Type ERASE to erase the wallet record and set the default PIN: ").strip()
        if confirmation != "ERASE":
            print("PIN change cancelled.")
            return 0
    else:
        answer = input(f"Change the card PIN to the {selection.description}? [y/N]: ").strip().lower()
        if answer not in {"y", "yes"}:
            print("PIN change cancelled.")
            return 0

    record_erased = apply_pin_change(transport, new_pin)
    if record_erased:
        print("Wallet record erased to FF and PIN changed to the default FF FF FF.")
    else:
        print(f"Card PIN changed successfully using the {selection.description}.")
        if selection.source == "config":
            prompt_to_initialize_wallet(transport)
    return 0


def inspect_and_verify(
    transport: MemoryCardTransport,
    config_path: str | None,
    poll_interval: float = 0.5,
) -> int:
    error_counter, payload = read_card_snapshot(transport, poll_interval)

    print(f"\nWallet record area: offset 0x{CARD_RECORD_OFFSET:02X}, length {CARD_RECORD_SIZE} bytes")
    print(format_hex_dump(payload, CARD_RECORD_OFFSET))
    try:
        record = decode_card_record(payload)
    except ValueError as exc:
        print(f"Could not decode wallet record: {exc}")
    else:
        print("\nDecoded wallet record:")
        print(f"  magic = 0x{record.magic:08X} ({record.magic})")
        print(f"  id    = {record.id}")
        print(f"  total = {record.total}")
        print(f"  value = {record.value}")

    attempts = available_attempts(error_counter)
    print(f"\nPIN presentation counter: 0x{error_counter:02X} ({attempts} attempts available)")
    if attempts == 0:
        print("The card PIN is permanently locked; verification is not possible.", file=sys.stderr)
        return 3

    selection = prompt_for_pin(config_path)
    if selection is None:
        print("PIN verification cancelled.")
        return 0
    pin = selection.pin

    answer = input(
        f"Verify using the {selection.description}? "
        f"A wrong PIN will consume one of {attempts} remaining attempts. [y/N]: "
    ).strip().lower()
    if answer not in {"y", "yes"}:
        print("PIN verification cancelled.")
        return 0

    try:
        reset_recovery_used = False
        while True:
            try:
                transport.present_pin(pin)
                break
            except PinVerificationError as exc:
                remaining = available_attempts(exc.error_counter)
                print(
                    f"PIN INCORRECT. Card counter is now 0x{exc.error_counter:02X}; "
                    f"remaining attempts: {remaining}.",
                    file=sys.stderr,
                )
                if remaining == 0:
                    print("The card PIN is now permanently locked.", file=sys.stderr)
                else:
                    print("Exiting without another attempt. Confirm the PIN before trying again.", file=sys.stderr)
                return 2
            except CardResetError:
                if reset_recovery_used:
                    raise CardCommunicationError(
                        "the card reset repeatedly during PIN presentation; reconnect the reader before retrying"
                    )

                print("The card reset during PIN presentation. Reconnecting and checking the counter...")
                transport.disconnect_card()
                if not transport.is_card_present():
                    raise CardCommunicationError("card disappeared while recovering from a reset")
                transport.select_memory_card()
                recovered_counter = transport.get_error_count()
                recovered_attempts = available_attempts(recovered_counter)
                if recovered_attempts != attempts:
                    print(
                        f"The counter changed from {attempts} to {recovered_attempts} attempts. "
                        "The PIN will not be sent again.",
                        file=sys.stderr,
                    )
                    return 2

                retry = input(
                    f"Counter is unchanged at {recovered_attempts} attempts. "
                    f"Retry the same {selection.description}? [y/N]: "
                ).strip().lower()
                if retry not in {"y", "yes"}:
                    print("PIN verification cancelled after card reset.")
                    return 0
                error_counter = recovered_counter
                attempts = recovered_attempts
                reset_recovery_used = True
    except CardResetError:
        raise

    print("PIN verified successfully; presentation counter restored to 0x07.")
    return prompt_and_change_pin(transport, config_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Wait for an SLE4442 card, dump its wallet record, verify a PIN, and optionally change it."
    )
    parser.add_argument("--config", help="path to pycard.toml for the 'config' PIN choice")
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=0.5,
        metavar="SECONDS",
        help="reader/card polling interval (default: 0.5)",
    )
    parser.add_argument("--debug", action="store_true", help="enable verbose transport logging")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.poll_interval <= 0:
        print("--poll-interval must be greater than zero", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="[%(levelname)s] %(name)s: %(message)s",
    )

    transport: MemoryCardTransport | None = None
    try:
        transport = MemoryCardTransport(backend=PyscardBackend())
        wait_for_card(transport, args.poll_interval)
        return inspect_and_verify(transport, args.config, args.poll_interval)
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 130
    except (PcscError, ValueError) as exc:
        LOGGER.debug("CLI operation failed", exc_info=True)
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if transport is not None:
            transport.disconnect_card()


if __name__ == "__main__":
    raise SystemExit(main())
