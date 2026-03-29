# AGENTS.md

## Current App State

This repository contains a small desktop application for reading and updating a smart-card wallet record through a PC/SC-compatible reader.

Primary modules:

- [`app.py`](app.py): process entrypoint
- [`pycard/app.py`](pycard/app.py): app composition
- [`pycard/config.py`](pycard/config.py): optional runtime config loading
- [`pycard/controller.py`](pycard/controller.py): polling loop and UI orchestration
- [`pycard/reader.py`](pycard/reader.py): reader/card detection and card read-write workflow
- [`pycard/pcsc.py`](pycard/pcsc.py): PC/SC transport and APDU helpers
- [`pycard/models.py`](pycard/models.py): card constants and record encoding
- [`pycard/ui.py`](pycard/ui.py): `customtkinter` UI
- `pycard.toml`: optional runtime configuration file

## Card Model

The application reads and writes a 16-byte record at offset `64` made of four little-endian `uint32` values:

- `magic`
- `id`
- `total`
- `value`

Relevant constants:

- admin id: `1`
- user id: `9999`
- default top-up: `2`
- uninitialized magic: `0xFFFFFFFF`
- initialized magic written by updates: `6970`

## Runtime Behavior

The app polls hardware state every `500 ms`.

Normal runtime states are:

- no reader connected
- reader connected, no card inserted
- reader connected, admin card inserted
- reader connected, user card inserted
- transport/read/write error

Reader and card absence are expected states and must not prevent the UI from launching.

## Improvements Added

The following runtime behavior is now implemented:

- the app can start with no reader connected
- the app can start with a reader connected but no card inserted
- the app can continue running while the reader is added or removed
- the app can continue running while the smart card is inserted or removed
- the UI now shows reader presence and card presence continuously
- reader/card hot-plugging now triggers a UI refresh because detection changes include reader state changes, not only card state changes
- card writes now work with the ACR38U/SLE4442 combination after fixing presence handling
- the transport now detects ACR38 vs ACR39 reader families and normalizes ACR39 SLE4442 read responses by stripping the trailing protection bytes
- the UI supports Slovenian and English, with Slovenian as the default and an in-app language switcher in the header
- the personalized PIN for initialized cards is loaded from `pycard.toml`
- if `pycard.toml` is missing, the app starts with the default PIN in memory and prompts at startup to save a personal PIN

## Debugging

Verbose logging is opt-in.

- default log level: `INFO`
- debug log level: set `PYCARD_LOG_LEVEL=DEBUG`

The current debug output is concentrated around:

- card detection
- card read
- PIN presentation / unlock
- card write
- post-write refresh

## Notes For Future Changes

- `Info.present` currently means "card present"; `Info.reader_present` tracks reader availability separately.
- `ReaderService.detect()` is responsible for translating PC/SC conditions into app state and for setting `info.change`.
- `AppController._render()` is the main place where raw hardware state is mapped into UI states.
- `MemoryCardTransport.is_card_present()` should continue to use reader status checks rather than reconnecting the card handle on every poll.
- `MemoryCardTransport._normalize_read_memory_response()` is where ACR38/ACR39 SLE4442 read-layout differences should be handled.
- `pycard/i18n.py` contains the translatable UI strings. Add new user-facing strings there instead of hardcoding them in the UI.
- `pycard/config.py` accepts `card.personalized_pin` in `pycard.toml` as either three hex byte strings like `["11", "22", "33"]` or three decimal byte integers for backward compatibility.
- `pycard/app.py` prompts the user to set a personal PIN when `pycard.toml` is missing or still contains the default `FF FF FF`, then writes the new value back to the config file as hex byte strings.
- The repository currently has no tests; any behavior changes should be validated manually or by adding focused unit tests around `ReaderService.detect()` and controller rendering decisions.
