# pycard

`pycard` is a Python desktop application for reading and updating a simple smart-card "wallet" value through a PC/SC-compatible card reader.

The project uses:

- `customtkinter` for the GUI
- `pyscard` for PC/SC smart-card access

The UI supports Slovenian and English. Slovenian is the default language, and the language can be changed at runtime from the app header.
The personalized PIN for initialized cards is loaded from [`pycard.toml`](pycard.toml) instead of being hardcoded in the source.
The config file is optional. If `pycard.toml` is missing, the app starts with the default PIN `FF FF FF` in memory. On startup it asks whether to set a personal PIN and creates the config file only if the user confirms.

## What The Code Does

When you run the app, it:

1. Starts a desktop window.
2. Polls for an attached PC/SC smart-card reader.
3. Tracks reader presence and card presence at runtime.
4. Reads a 16-byte card record from a fixed memory offset on the card.
5. Displays one of two views depending on the card type:
   - a user card view showing current value, requested top-up amount, and computed new total
   - an admin card view with an option to switch the card type back to user
6. Can unlock and rewrite the card record to:
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
- If a blank/uninitialized card is detected (`magic == 0xFFFFFFFF`), the app first presents the default PIN `FF FF FF` and then changes it to `C0 DE A5`.
- Card presence detection and connection handling behavior is implemented such that the SLE4442 writes work correctly with the ACR38U reader.
- The transport layer detects ACR38- vs ACR39-family readers from the PC/SC reader name and normalizes SLE4442 read responses so the app always receives the expected record payload.

## Project Structure

- [`app.py`](app.py): thin entrypoint that calls `pycard.app.main()`
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

The app reads configuration from `pycard.toml` by default when the file exists.

Example:

```toml
[card]
personalized_pin = ["FF", "FF", "FF"]
```

If `pycard.toml` is missing, or if it still contains `FF FF FF`, the app prompts for a personal PIN at startup and writes `pycard.toml` only when the user confirms. The dialog expects three hexadecimal bytes separated by spaces, for example `11 22 33`.

Optional startup language override:

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
- There is a `pytest` configuration in `pyproject.toml`, but no test suite is present in this repository snapshot.
