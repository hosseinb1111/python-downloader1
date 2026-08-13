# 📥 Python Telegram Downloader

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python\&logoColor=white)](https://www.python.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram\&logoColor=white)](https://telegram.org/)
[![yt--dlp](https://img.shields.io/badge/Downloader-yt--dlp-black)](https://github.com/yt-dlp/yt-dlp)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A lightweight Telegram bot that downloads media from supported URLs and sends the downloaded file directly back to the user.

The bot uses **`yt-dlp`** for media extraction and **`python-telegram-bot`** for Telegram integration.

---

## ✨ Features

### 📥 Media Downloading

Send the bot a supported URL and it will attempt to download the media automatically.

The current bot is designed for links from services supported by `yt-dlp`, including examples such as:

* YouTube
* X / Twitter
* TikTok
* Instagram
* Other platforms supported by `yt-dlp`

Support ultimately depends on what `yt-dlp` supports at the time of use.

### 🚦 Per-User Cooldown

Each user has a cooldown between downloads.

The current configuration requires users to wait:

```text
30 seconds
```

before starting another download. This helps reduce abuse and unnecessary resource usage.

### 📏 File Size Protection

Downloaded files are checked before being uploaded to Telegram.

The current maximum is:

```text
50 MB
```

Files larger than that are rejected and the user receives an error message.

### 🗂️ Automatic File Handling

The bot automatically sends downloaded files according to their extension:

| File type               | Telegram method |
| ----------------------- | --------------- |
| MP4 / MOV / WebM        | Video           |
| JPG / JPEG / PNG / WebP | Photo           |
| Everything else         | Document        |

After the upload finishes, the temporary downloaded file is removed from disk.

### 🔗 Automatic URL Detection

The bot searches incoming messages for HTTP/HTTPS URLs using a regular expression.

You don't need to use a special command. Just send a message containing the link.

### ❤️ Keepalive Endpoint

The project includes a small Flask application that exposes:

```text
/
```

and returns:

```text
Bot is alive
```

The Flask server listens on port `10000` and is started in a background thread by `start_keepalive()`.

---

## 🏗️ How It Works

```text
User sends URL
       │
       ▼
Telegram Bot
       │
       ▼
URL Detection
       │
       ▼
Cooldown Check
       │
       ▼
yt-dlp Download
       │
       ▼
File Size Check
       │
       ▼
Choose Telegram Upload Type
       │
       ▼
Send Media
       │
       ▼
Delete Temporary File
```

---

## 🧩 Project Structure

```text
python-downloader1/
│
├── config.py
├── downloader.py
├── handlers.py
├── keepalive.py
├── ratelimit.py
├── requirements.txt
└── README.md
```

### `config.py`

Contains the main runtime configuration:

* Telegram bot token
* Download directory
* Maximum file size
* User cooldown duration

The bot token is read from the `BOT_TOKEN` environment variable.

### `downloader.py`

Contains the actual media downloader.

It uses:

* `yt-dlp`
* `imageio-ffmpeg`

The downloader disables playlists and prefers files under 50 MB when possible.

### `handlers.py`

Handles Telegram messages, extracts URLs, manages downloads, uploads the resulting files, and cleans up temporary files.

### `ratelimit.py`

Implements the per-user cooldown using an in-memory dictionary containing the timestamp of each user's most recent download request.

### `keepalive.py`

Runs a lightweight Flask server used as a health/keepalive endpoint.

---

## 📦 Requirements

The project currently uses:

```text
python-telegram-bot==21.0.1
yt-dlp>=2024.1.1
flask==3.0.3
imageio-ffmpeg==0.5.1
```

These dependencies are listed in `requirements.txt`.

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/hosseinb1111/python-downloader1.git
cd python-downloader1
```

### 2. Create a virtual environment

Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create your Telegram bot

Open **[@BotFather](https://t.me/BotFather)** in Telegram and create a bot.

Copy the generated bot token.

### 5. Set the bot token

The project expects:

```text
BOT_TOKEN
```

as an environment variable.

Windows PowerShell:

```powershell
$env:BOT_TOKEN="YOUR_BOT_TOKEN"
```

Windows CMD:

```cmd
set BOT_TOKEN=YOUR_BOT_TOKEN
```

Linux / macOS:

```bash
export BOT_TOKEN="YOUR_BOT_TOKEN"
```

---

## ▶️ Running the Bot

Start the application using the project's entry point.

For example:

```bash
python main.py
```

> The repository currently does not include a `main.py` file in the visible root file list, so your actual startup file may be located elsewhere in your deployment setup. The listed repository files currently include `config.py`, `downloader.py`, `handlers.py`, `keepalive.py`, `ratelimit.py`, and `requirements.txt`.

---

## 💬 Usage

Start a conversation with the bot and send a URL.

Example:

```text
https://example.com/video
```

The bot will:

```text
🔍 Detect the URL
↓
⏱️ Check cooldown
↓
📥 Download the media
↓
📏 Check file size
↓
📤 Upload it to Telegram
```

You should also receive a temporary:

```text
Downloading...
```

message while the download is in progress.

---

## ⚙️ Configuration

The main settings are defined in `config.py`.

### Download directory

Current value:

```python
DOWNLOAD_DIR = "/tmp/downloads"
```

### Maximum file size

Current value:

```python
MAX_SIZE_MB = 50
```

### Cooldown

Current value:

```python
COOLDOWN_SECONDS = 30
```

These values can be changed to suit your deployment.

---

## 🔐 Security

Never upload your Telegram bot token to GitHub.

Use an environment variable instead:

```text
BOT_TOKEN
```

Also avoid committing local configuration files containing secrets.

A useful `.gitignore` is:

```gitignore
__pycache__/
*.py[cod]
.venv/
venv/
.env
.env.*
.wrangler/
.DS_Store
Thumbs.db
```

---

## ⚠️ Important Notes

This project uses `yt-dlp`, which means supported websites and extraction behavior can change over time.

A URL that works today may stop working later because a website changed its API, authentication requirements, anti-bot systems, or page structure.

The cooldown system currently stores timestamps **in memory**, meaning the rate-limit state is reset when the process restarts and is local to that process.

The project also removes temporary files after attempting to send them, helping prevent the download directory from filling up.

---

## 🛠️ Built With

* 🐍 Python
* 🤖 `python-telegram-bot`
* 📥 `yt-dlp`
* 🎞️ `imageio-ffmpeg`
* 🌐 Flask

---

## 🧑‍💻 Author

Created by [Hossein](https://github.com/hosseinb1111)

---

## 📄 License

This project is licensed under the **MIT License**.

See the [LICENSE](LICENSE) file for the full license text.

Copyright © 2026 [Hossein](https://github.com/hosseinb1111)
