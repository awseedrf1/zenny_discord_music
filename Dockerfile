FROM python:3.10-slim

# Install FFmpeg and other dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Expose the port Flask runs on
EXPOSE 8080

# Run the bot
CMD ["python", "zenny_main.py"]
