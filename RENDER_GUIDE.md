# How to Deploy Zenny Bot on Render.com

## 1. Prerequisites
- A [Render.com](https://render.com/) account.
- Your bot token from [Discord Developer Portal](https://discord.com/developers/applications).
- FFmpeg (This is required for audio playback).

## 2. Deployment Options

### Option A: Using Docker (Recommended for FFmpeg)
The easiest way to get FFmpeg on Render is to use a `Dockerfile`.

**Create a file named `Dockerfile` in your project root:**
```dockerfile
FROM python:3.10-slim

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

# Start the bot
CMD ["python", "zenny_main.py"]
```

### Option B: Native Python Runtime
If you prefer the Native Python runtime, you must add an FFmpeg buildpack or download the binary during the build phase.

## 3. Environment Variables on Render
Go to your **Dashboard > Environment** and add:
- `TOKEN`: Your Discord Bot Token.
- `ALLOWED_CHANNEL_IDS`: (Optional) Comma-separated list of Channel IDs.
- `PYTHON_VERSION`: `3.10.0` (or your preferred version).

## 4. Keeping the Bot Alive
Render's free tier spins down after 15 minutes of inactivity. Since Discord bots are long-running processes, use a service like [cron-job.org](https://cron-job.org/) or [UptimeRobot](https://uptimerobot.com/) to ping your Render URL (e.g., `https://your-app.onrender.com/`) every 10 minutes.

## 5. Build & Start Commands (If not using Docker)
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python zenny_main.py`
