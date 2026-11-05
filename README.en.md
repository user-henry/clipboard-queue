**English** | [简体中文](README.md)

# 📋 Clipboard Queue v2

> A Windows tool that turns copy & paste into a FIFO queue. v2 upgrades it with a **tech-style card interface**,
> titled entries, categories, search and **password protection**. All records are stored locally by default and survive restarts.

## Core idea

| Normal clipboard | Clipboard Queue |
|-----------|----------------|
| Every copy overwrites the previous one | FIFO queue, everything is kept |
| Only the last copy can be pasted | Paste them one by one in order |
| Copying something new loses the old content | The queue survives exit and is restored on restart |

## What's new in v2

| Capability | Description |
|------|------|
| Card interface | One display card per entry: title, category badge, time, character count, content preview, image thumbnail |
| Titles and categories | Rename and categorize directly from the card; custom categories and colors; categories can be added / renamed / deleted / locked |
| Search and filtering | Top search box (title / content / category / tags) + category filter chips |
| Password protection | Lock a category (a "Password" category is provided by default) or mark a single entry as protected; PBKDF2-HMAC-SHA256 salted hashing, with an unlock cache |
| Sensitive-content protection | Protected content can be cleared from the clipboard automatically; the clipboard can also be cleared on exit |
| Pin and reorder | Pin any entry to the head of the queue with one click |
| Settings | 5 tabs: General / Queue / Categories & Password / Hotkeys / Storage; saved immediately and applied live |
| Backup | Export / import JSON backups |
| Frosted glass UI | Native blur-behind with real background blur; the main window, settings and unlock dialog share the same material; adjustable under "Settings → General → Interface & Effects" |

## Hotkeys (defaults; editable in "Settings → Hotkeys")

| Hotkey | Action |
|--------|------|
| `Ctrl+Alt+C` | Copy the selection and add it to the queue |
| `Ctrl+Alt+V` | Pop from the queue and paste |
| `Ctrl+Alt+Q` | Clear the queue |
| `Ctrl+Alt+S` | Open the main window |
| Tray icon click | View / manage the queue |

## Data and privacy

| Content | Location |
|------|------|
| Queue and categories | `%APPDATA%\ClipboardQueue\queue_data.json` |
| Preferences and password hash | `%APPDATA%\ClipboardQueue\settings.json` |

- Local saving is enabled by default; you can cap the queue under **Settings → Queue**, or clear everything under **Settings → Storage**.
- Passwords are stored only as PBKDF2 hashes with a random salt — **never in plain text**, and never in the queue data file.

## Installation and running

### Option 1: run the binary (recommended)

1. Download `release/ClipboardQueue.exe`
2. Double-click it; the icon appears in the system tray

### Option 2: run from source

```bash
pip install -r requirements.txt
python src/main.py
```

### Option 3: build it yourself

```bash
pip install pyinstaller
pyinstaller --clean --noconfirm ClipboardQueue.spec
```

## Tests

```bash
python tests\smoke_test.py       # Data layer: settings, password, FIFO, category locking, search, limits, migration, import/export
python tests\gui_smoke_test.py   # UI layer: card window, masking, filtering, delete confirmation, settings, password dialogs
```

## System requirements

- Windows 10 / 11 (64-bit)
- Python 3.8+ to run from source

## Project structure

```text
ClipboardQueue/
├── src/
│   ├── main.py            # Entry: tray, hotkeys, card window, unlock dialog
│   ├── queue_manager.py   # FIFO queue + category / title / password flags + persistence and migration
│   ├── app_settings.py    # Preferences (atomic JSON writes)
│   ├── security.py        # PBKDF2 password setting and verification
│   ├── settings_window.py # Settings page (5 tabs) + autostart
│   ├── ui_theme.py        # Dark tech theme and components
│   ├── clipboard_helper.py, hotkey_manager.py, notify_helper.py
├── tests/                 # Data-layer and UI-layer smoke tests
└── ClipboardQueue.spec    # PyInstaller configuration
```

## License

MIT License
