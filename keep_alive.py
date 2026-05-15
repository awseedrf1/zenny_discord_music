from flask import Flask
from threading import Thread
import os

app = Flask('')


@app.route('/')
def home():
    return "🎵 Discord Music Bot is alive!"


@app.route('/health')
def health():
    return {"status": "ok"}, 200


def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)


def keep_alive():
    """เริ่ม web server ใน thread แยก"""
    t = Thread(target=run)
    t.daemon = True
    t.start()
