# pycard

`pycard` is a Python desktop application for reading and updating a simple smart-card "wallet" value through a PC/SC-compatible card reader.

The project uses:

- `customtkinter` for the GUI
- `pyscard` for PC/SC smart-card access

The UI supports English and Slovenian. English is the default language, and the language can be changed at runtime from the app header. The selected language is saved in `pycard.toml`.
The personalized PIN for initialized cards is loaded from [`pycard.toml`](pycard.toml) instead of being hardcoded in the source.
The config file is optional. If `pycard.toml` is missing, the app starts with the default PIN `FF FF FF` in memory. On startup it asks whether to set a personal PIN and creates the config file only when the user confirms.

## What The Code Does

When you run the app, it:

1. Starts a desktop window.
2. Polls for an attached PC/SC smart-card reader.
3. Tracks reader presence and card presence at runtime.
4. Reads a 16-byte card record from a fixed memory offset on the card.
5. When a blank card is inserted, asks whether to personalize it as a user or admin card.
6. Displays one of two views depending on the card type:
   - a user card view showing current value, requested top-up amount, and computed new total
   - an admin card view with an option to switch the card type back to user
7. Can unlock and rewrite the card record to:
   - top up a user card
   - change a user card into an admin card
   - change an admin card into a user card

The stored record contains four little-endian 32-bit integers:

- `magic`
- `id`
- `total`
- `value`

## Card Behavior

The card data model is defined in [`pycard/models.py`](pycard/models.py).

- Card record offset: `64`
- Card record size: `16` bytes
- Default top-up amount: `2`
- Admin card id: `1`
- User card id: `9999`

The app uses these rules:

- If no reader is present, it starts normally and shows a status message.
- If a reader is present but no card is inserted, it starts normally and shows a status message.
- Reader insertion/removal is handled while the app is running.
- Card insertion/removal is handled while the app is running.
- If the card id is `1`, it is treated as an admin card.
- Any other expected card is shown as a user card with a balance.
- For user cards, entering a positive integer updates the displayed new total.
- Updating a card writes a new record back to the card.
- If a blank/uninitialized card is detected (`magic == 0xFFFFFFFF`), the app requires two consecutive valid blank reads before opening a dialog with User, Admin, and Cancel choices. A cancelled prompt is not shown again until the card is removed and reinserted.
- After User or Admin is chosen, the app verifies the default PIN `FF FF FF`, changes it to the configured personalized PIN, and writes `magic=6970`, the selected id (`9999` or `1`), `total=0`, and `value=0`.
- The app verifies the write and then reselects and rereads the card before displaying the user credit screen or admin screen. Blank-card personalization is blocked while the configured PIN is still `FF FF FF`.
- If PIN verification fails, the app shows the remaining attempts and blocks another update attempt until the card is removed and reinserted. A zero counter is reported as a permanent PIN lockout.
- The SLE4442 PIN counter is a three-bit value (`00` through `07`). A response with upper bits set, such as `FF`, is treated as a transient reader/connection failure, never as card data.
- Card removal, reader changes, resets, and transport failures discard the active PC/SC handle. The next read starts with a fresh connection, and all cached card-specific state is cleared on removal.
- Card presence detection and connection handling behavior is implemented such that the SLE4442 writes work correctly with the ACR38U reader.
- The transport layer detects ACR38- vs ACR39-family readers from the PC/SC reader name and normalizes SLE4442 read responses so the app always receives the expected record payload.

## Project Structure

- [`app.py`](app.py): thin entrypoint that calls `pycard.app.main()`
- [`card_cli.py`](card_cli.py): terminal utility for waiting for a card, dumping the wallet record, and making one confirmed PIN-verification attempt
- [`pycard/app.py`](pycard/app.py): wires together logging, PC/SC backend, reader service, controller, and UI
- [`pycard/config.py`](pycard/config.py): loads optional runtime configuration from `pycard.toml`
- [`pycard/controller.py`](pycard/controller.py): application logic and UI state transitions
- [`pycard/ui.py`](pycard/ui.py): CustomTkinter desktop interface
- [`pycard/reader.py`](pycard/reader.py): high-level card detection, read, unlock, and write operations
- [`pycard/pcsc.py`](pycard/pcsc.py): low-level PC/SC transport and APDU helpers
- [`pycard/models.py`](pycard/models.py): shared constants and record encoding/decoding
- `pycard.toml`: optional runtime configuration, including the personalized card PIN

## Requirements

- Python 3.11+
- A PC/SC-compatible smart-card reader
- System support for PC/SC
- Python dependencies from `pyproject.toml`

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

If you want test dependencies as well:

```bash
pip install -e .[dev]
```

## Run

```bash
python app.py
```

### Card inspection CLI

To wait for a card, dump the 16-byte wallet record, safely make one PIN-verification attempt, and optionally change the PIN:

```bash
python card_cli.py
```

The PIN prompt accepts `default`, `config`, three hexadecimal bytes such as `11 22 33`, or `quit`.
Before verification, the script displays the card's current presentation counter and requires confirmation.
After an incorrect PIN it reports the remaining attempts and exits without offering an immediate retry.

If the initial card read returns a transient invalid response such as PIN counter `FF`, the CLI discards the connection and waits for a clean read. It never retries a PIN presentation automatically.
The transport explicitly connects with T=0 as required by the ACS memory-card command set. Temporary busy, mute, or connection states are logged clearly, and the CLI keeps waiting instead of treating them as card absence.
If PC/SC resets the card during PIN presentation, the CLI reconnects, rereads the attempt counter, and offers a confirmed retry only when the number of remaining attempts is unchanged.
After successful verification, the new-PIN prompt accepts `default`, `config`, explicit hexadecimal bytes, or `skip`.
Setting the PIN to `FF FF FF` requires typing `ERASE`; the CLI then overwrites all 16 wallet-record bytes with `FF`, verifies the erased record, and changes the PIN.
After the PIN is successfully changed to the non-default config value, the CLI offers a separate `INITIALIZE` confirmation that writes `magic=6970`, `id=9999`, `total=0`, and `value=0`, then verifies the record by reading it back. Merely presenting the config PIN does not offer or perform initialization.

Optional arguments:

```bash
python card_cli.py --config /path/to/pycard.toml --poll-interval 0.5 --debug
```

The app reads configuration from `pycard.toml` by default when the file exists.

Example:

```toml
[card]
personalized_pin = ["FF", "FF", "FF"]

[ui]
language = "en"
```

If `pycard.toml` is missing, the app creates it with the default PIN and English language. If `[ui].language` is missing from an existing config, it is added as `en`. If the PIN is still `FF FF FF`, the app prompts for a personal PIN at startup. The dialog expects three hexadecimal bytes separated by spaces, for example `11 22 33`.

Changing the language from the app header immediately saves `en` or `sl` back to `[ui].language` without losing the configured PIN.

Optional one-run startup language override (this does not replace the saved selection until the header selector is used):

```bash
PYCARD_LANG=en python app.py
```

Optional startup config override:

```bash
PYCARD_CONFIG=./pycard.toml python app.py
```

To enable verbose reader/card debugging:

```bash
PYCARD_LOG_LEVEL=DEBUG python app.py
```

## Notes

- The UI updates on a polling loop every 500 ms.
- The code assumes a memory-card workflow supported by the connected reader and card.
- The UI defaults to Slovenian and can be switched between Slovenian and English while the app is running.
- Debug logging is disabled by default and only becomes verbose when `PYCARD_LOG_LEVEL=DEBUG` is set.
- Focused tests cover PIN verification, reader initialization, warning behavior, and CLI input/dump helpers.
