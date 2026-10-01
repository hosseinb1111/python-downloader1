# Telegram Media Downloader

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)](https://telegram.org/)
[![yt-dlp](https://img.shields.io/badge/Downloader-yt--dlp-black)](https://github.com/yt-dlp/yt-dlp)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A Telegram bot that turns links into files. Send a URL and get the video back, or use `/audio` for an MP3.
Built on [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) and [`python-telegram-bot`](https://python-telegram-bot.org/).

<!-- Add a screenshot or short GIF of a real chat here, for example: ![Demo](docs/demo.gif) -->

## Features

- **Video and audio.** Send a link for a video with caption (title, uploader, duration, source link) and streaming support. Use `/audio <link>` for an MP3 with title and artist tags.
- **Live progress.** One status message updates through queued, fetching, `▰▰▰▰▱▱▱▱▱▱ 42%` with speed and ETA, and uploading.
- **Automatic quality fallback.** If a file exceeds Telegram's 50 MB bot limit, the bot retries at 720p, 480p, then 360p before giving up.
- **Non-blocking.** Downloads run in worker threads and updates are handled concurrently, so one long download doesn't freeze the bot for everyone else.
- **Sensible limits.** Per-user cooldown, maximum duration, maximum file size, and a cap on simultaneous downloads.
- **Safer defaults.** Blocks links to private and internal addresses (SSRF), keeps yt-dlp's generic "any page" extractor off unless you opt in, and never shows raw errors to users.
- **Private mode.** Set `ALLOWED_USER_IDS` to restrict the bot to specific users.
- **Health endpoint.** `GET /` returns `Bot is alive`; `GET /health` returns JSON with uptime and counters, suitable for Render or UptimeRobot-style monitors.
- **Self-cleaning.** Each job gets its own temp folder, deleted afterwards. Leftovers from a crash are swept on startup.

## Quick start

```bash
git clone https://github.com/hosseinb1111/python-downloader1.git
cd python-downloader1

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then edit .env and paste your token
python main.py
```

Get a token from [@BotFather](https://t.me/BotFather) (`/newbot`). Instead of a `.env` file you can export it:

```bash
export BOT_TOKEN="123456:ABC..."   # PowerShell: $env:BOT_TOKEN="..."
```

Python 3.10 or newer is required. FFmpeg is bundled through `imageio-ffmpeg`, so nothing else needs installing.

## Usage

| Command | What it does |
| --- | --- |
| *(send a link)* | Downloads the video |
| `/audio <link>` | Downloads the audio as MP3. Also works as a reply to a message containing a link |
| `/start`, `/help` | Welcome message and current limits |

In group chats the bot only reacts to links when privacy mode is off, and stays silent on non-link messages. Use `/audio` explicitly in groups.

## Configuration

Set these as environment variables or in a `.env` file.

| Variable | Default | Description |
| --- | --- | --- |
| `BOT_TOKEN` | required | Token from @BotFather |
| `MAX_SIZE_MB` | `50` | Largest file to send. 50 MB is Telegram's limit for bots on the cloud Bot API |
| `COOLDOWN_SECONDS` | `30` | Time a user must wait between downloads |
| `MAX_DURATION_SECONDS` | `3600` | Reject videos longer than this. Live streams are always rejected |
| `MAX_CONCURRENT_DOWNLOADS` | `3` | Downloads running at once; the rest wait in a queue |
| `AUDIO_BITRATE_KBPS` | `192` | MP3 quality for `/audio` |
| `ALLOW_GENERIC_EXTRACTOR` | `false` | Let yt-dlp try any web page, not only sites with a dedicated extractor. Convenient, but widens what the bot will fetch |
| `ALLOWED_USER_IDS` | empty | Comma-separated Telegram user IDs. If set, the bot is private |
| `DOWNLOAD_DIR` | `<system temp dir>/downloads` | Where temporary job folders are created |
| `PORT` | `10000` | Port for the health endpoint (Render sets this automatically) |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, and so on |

## Deployment

**Docker**

```bash
docker build -t telegram-downloader .
docker run -d --restart unless-stopped -e BOT_TOKEN="123456:ABC..." -p 10000:10000 telegram-downloader
```

**Render.** A ready-made [`render.yaml`](render.yaml) is included. Create a Blueprint from the repo, set `BOT_TOKEN`, and deploy. The health check path is `/health`.

The bot uses long polling, so it needs no public URL or webhook. The HTTP endpoint exists only so hosts and uptime monitors can see the process is alive. Run **one instance per token**, because two pollers on the same bot will conflict.

## How it works

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

```text
├── main.py          # entry point: builds the bot, starts the health server
├── handlers.py      # /start /help /audio, link handling, progress, upload
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

## Development

```bash
python -m unittest discover -s tests -t .
```

Tests use fakes for yt-dlp and Telegram, so they run offline and fast. They cover URL extraction, cooldowns, SSRF protection, the download pipeline (limits, quality fallback, cleanup), and the full message flow.

## Limitations and security notes

- **Sites change.** yt-dlp support depends on each website. If a site stops working, update first: `pip install -U yt-dlp`.
- **Some content is out of reach:** private, age-restricted, login-only, or region-locked media, and platforms that block datacenter IPs. The bot reports this instead of showing a stack trace.
- **Cooldowns live in memory** and reset when the process restarts.
- **SSRF protection** checks the address a link resolves to before downloading. A public page that redirects to an internal address is not caught by that check. Keeping `ALLOW_GENERIC_EXTRACTOR` off (the default) is the main defence, and the bot's host should not have access to internal services you can't afford to leak.
- **Copyright.** Respect copyright and each site's terms of service. You are responsible for how your bot is used.

## License

MIT. See [LICENSE](LICENSE). Copyright © 2026 [Hossein](https://github.com/hosseinb1111)
