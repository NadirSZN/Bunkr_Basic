# Bunkr Downloader

Bunker Downloader is a versatile and completely rewritten GUI-based download manager for bunkr albums and files. It features resilient error management, and an interactive tree-view-based user interface.

## Features


- **Multi-Threading**: Custom concurrent connections for downloading and extracting files.
- **Fail-Safe Mechanism**: Custom retry logic automatically aborts albums generating `404` errors, skips bad servers, and handles retries without crashing.
- **Beautiful Interface**: Developed entirely with `customtkinter` for a modernized, responsive layout. Includes a built-in Dark/Light theme toggle in the sidebar.
- **Download History**: Tracks downloaded items. You can open files/folders directly or clear the visual history without deleting the actual files from your disk.

## Installation

1. Clone or download this repository.
2. Ensure you have Python 3.10+ installed on your computer.
3. Install the required dependencies using the `requirements.txt` file by opening your terminal or command prompt in the folder:

```bash
pip install -r requirements.txt
```

*(Note: Depending on your system, you may need to use `pip3` instead of `pip` or prefix it with `python -m pip`)*

## Usage

Start the application by running the `main.py` file:

```bash
python main.py
```

### Initial Run
Upon running the application for the first time, a clean, modern UI will appear. Settings, error tracking lists, and downloaded album histories are completely localized and easy to navigate.

1. **Active Downloads**: Paste your bunkr album or file link into the input box and press Enter, or simply click "Start Download". You can also add links in bulk via TXT files.
2. **Downloads**: Here you can find a categorized list of everything you've successfully downloaded. Double clicking a file opens it directly on your PC. You can also clear the list visually using the `hidden_history.json` mechanism.
3. **Settings**: Adjust parallel extraction and download workers, download speed limits (Mbit/s), auto-skipping behavior, manual retry limits, and your destination download folder.
4. **Theme Switcher**: Instantly toggle between Dark Theme and Light Theme directly from the sidebar. Your preference is automatically saved.

## Disclaimer
This tool is intended for personal and educational use. Always respect intellectual property rights and follow the terms of service of any host you download files from.

