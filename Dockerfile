FROM python:3.11-slim

# ติดตั้ง FFmpeg (จำเป็นสำหรับเล่นเพลง)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ติดตั้ง dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# เปิด port สำหรับ keep_alive
EXPOSE 8080

# รันบอท
CMD ["python", "bot.py"]
