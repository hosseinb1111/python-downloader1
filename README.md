# 📥 Telegram Media Downloader

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)](https://telegram.org/)
[![yt-dlp](https://img.shields.io/badge/Downloader-yt--dlp-black)](https://github.com/yt-dlp/yt-dlp)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A Telegram bot that turns links into files. Send a URL, get the video back — or an MP3 with `/audio`.
Built on [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) and [`python-telegram-bot`](https://python-telegram-bot.org/).

---

## ✨ Features

| | |
|---|---|
| 🎬 **Video** | Send any supported link. The bot replies with the video, a caption (title, uploader, duration, source link) and streaming support. |
| 🎵 **Audio** | `/audio <link>` (or reply to a link with `/audio`) returns an MP3 with title/artist tags. |
| 📊 **Live progress** | One status message updates as it goes: queued → fetching → `▰▰▰▰▱▱▱▱▱▱ 42%` with speed and ETA → uploading. |
| 📉 **Auto quality fallback** | Too big for Telegram's 50 MB limit? The bot retries at 720p → 480p → 360p before giving up. |
| ⚡ **Non-blocking** | Downloads run in worker threads and updates are processed concurrently, so one long download never freezes the bot for everyone else. |
| 🚦 **Limits that make sense** | Per-user cooldown, max duration, max file size, and a cap on simultaneous downloads. |
| 🛡️ **Safer by default** | Blocks links to private/internal addresses (SSRF), disables yt-dlp's "any page" extractor unless you opt in, never echoes raw errors to users. |
| 🔒 **Private mode** | Set `ALLOWED_USER_IDS` and only those users can use the bot. |
| 🩺 **Health endpoint** | `GET /` → `Bot is alive`, `GET /health` → JSON with uptime and counters. Works with Render/UptimeRobot-style monitors. |
| 🧹 **Self-cleaning** | Every job gets its own temp folder that is deleted afterwards (leftovers from a crash are swept on startup). |

---

## 🚀 Quick start

```bash
git clone https://github.com/hosseinb1111/python-downloader1.git
cd python-downloader1

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then edit .env and paste your token
python main.py
```

Get a token from [@BotFather](https://t.me/BotFather) (`/newbot`). Alternatively, skip the `.env` file and export it:

```bash
export BOT_TOKEN="123456:ABC..."   # PowerShell: $env:BOT_TOKEN="..."
```

Python **3.10+** is required. FFmpeg is bundled through `imageio-ffmpeg`, so there's nothing else to install.

---

## 💬 Usage

| Command | What it does |
|---|---|
| *(just send a link)* | Downloads the video |
| `/audio <link>` | Downloads the audio as MP3 (also works as a reply to a message containing a link) |
| `/start`, `/help` | Welcome message and limits |

In group chats the bot only reacts to links when privacy mode is off; it stays silent on non-link messages there. Use `/audio` explicitly in groups.

---

## ⚙️ Configuration

Everything is configured with environment variables (or a `.env` file).

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | — **(required)** | Token from @BotFather |
| `MAX_SIZE_MB` | `50` | Largest file to send. 50 MB is Telegram's limit for bots using the cloud Bot API |
| `COOLDOWN_SECONDS` | `30` | Time a user must wait between downloads |
| `MAX_DURATION_SECONDS` | `3600` | Reject videos longer than this (live streams are always rejected) |
| `MAX_CONCURRENT_DOWNLOADS` | `3` | How many downloads run at once; the rest wait in a queue |
| `AUDIO_BITRATE_KBPS` | `192` | MP3 quality for `/audio` |
| `ALLOW_GENERIC_EXTRACTOR` | `false` | Let yt-dlp try *any* web page, not only sites it has a dedicated extractor for. Convenient, but widens what the bot will fetch |
| `ALLOWED_USER_IDS` | *(empty)* | Comma-separated Telegram user IDs. If set, the bot is private |
| `DOWNLOAD_DIR` | system temp `/downloads` | Where temporary job folders are created |
| `PORT` | `10000` | Port for the health endpoint (Render sets this automatically) |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`… |

---

## ☁️ Deployment

**Docker**

```bash
docker build -t telegram-downloader .
docker run -d --restart unless-stopped -e BOT_TOKEN="123456:ABC..." -p 10000:10000 telegram-downloader
```

**Render** — a ready-made [`render.yaml`](render.yaml) is included. Create a *Blueprint* from the repo, set `BOT_TOKEN`, and deploy. The health check path is `/health`.

> The bot uses long polling, so it needs no public URL or webhook. The HTTP endpoint exists only so hosts and uptime monitors can see that the process is alive. Run **one instance per token** — two pollers on the same bot will fight each other.

---

## 🏗️ How it works

```text
message ──► extract URL ──► allowed user? ──► cooldown ──► queue (max N at once)
                                                              │
                      ┌───────────────────────────────────────┘
                      ▼
          safety check (public host only)
                      ▼
          yt-dlp in a worker thread ◄── live progress ──► status message
          (duration / live / size filters, quality ladder)
                      ▼
          upload as video / audio / photo / document
                      ▼
               delete temp folder
```

### Project layout

```text
├── main.py          # entry point: builds the bot, starts the health server
├── handlers.py      # /start /help /audio + link handling, progress, upload
├── downloader.py    # yt-dlp wrapper: filters, quality ladder, temp folders
├── security.py      # URL validation (blocks private/internal addresses)
├── ratelimit.py     # per-user cooldown
├── utils.py         # URL extraction, captions, friendly error messages
├── keepalive.py     # stdlib HTTP server for / and /health
├── stats.py         # in-memory counters for /health
├── errors.py        # exceptions with user-safe messages
├── config.py        # environment-based settings
├── tests/           # unit tests (no network or Telegram needed)
├── Dockerfile · render.yaml · .env.example
└── requirements.txt
```

---

## 🧪 Development

```bash
python -m unittest discover -s tests -t .
```

The tests use fakes for yt-dlp and Telegram, so they run offline and fast. They cover URL extraction, cooldowns, SSRF protection, the download pipeline (limits, quality fallback, cleanup) and the full message flow.

---

## ⚠️ Good to know

* **Sites change.** yt-dlp support depends on each website. If a site stops working, update it first: `pip install -U yt-dlp`.
* **Some content is out of reach**: private, age-restricted, login-only or region-locked media — and some platforms block datacenter IPs. The bot will say so rather than show a stack trace.
* **Cooldowns live in memory** and reset when the process restarts.
* **SSRF protection** checks the address a link resolves to before downloading. A public page that *redirects* to an internal address is not caught by that check; keeping `ALLOW_GENERIC_EXTRACTOR` off (the default) is the main defence there. Don't expose the bot's host to internal services you can't afford to leak.
* **Respect copyright and each site's terms of service.** You're responsible for what your bot is used for.

---

## 🛠️ Built with

🐍 Python · 🤖 python-telegram-bot · 📥 yt-dlp · 🎞️ imageio-ffmpeg

## 🧑‍💻 Author

Created by [Hossein](https://github.com/hosseinb1111)

## 📄 License

MIT — see [LICENSE](LICENSE). Copyright © 2026 [Hossein](https://github.com/hosseinb1111)
