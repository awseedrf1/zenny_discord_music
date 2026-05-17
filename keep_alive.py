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


@app.route('/action=ui')
@app.route('/ui')
def ui_page():
    return '''
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Zenny Discord Music UI</title>
        <style>
            body { font-family: Arial, sans-serif; background: #121212; color: #f4f4f4; margin: 0; padding: 0; }
            .container { max-width: 700px; margin: 40px auto; padding: 24px; background: #1f1f1f; border-radius: 16px; box-shadow: 0 16px 40px rgba(0,0,0,0.35); }
            h1 { margin-top: 0; color: #ffcc33; }
            label { display: block; margin: 18px 0 6px; font-weight: 600; }
            input { width: 100%; padding: 12px 14px; border-radius: 10px; border: 1px solid #333; background: #171717; color: #f4f4f4; }
            button { margin-top: 22px; width: 100%; padding: 14px; border: none; border-radius: 12px; background: #ffcc33; color: #111; font-weight: 700; cursor: pointer; }
            button:hover { background: #e6b800; }
            .note { margin-top: 22px; font-size: 0.95rem; color: #bbbbbb; }
            .code { display: block; padding: 12px; background: #121212; border: 1px solid #333; border-radius: 10px; overflow-x: auto; }
            a { color: #ffcc33; text-decoration: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Zenny Discord Music UI</h1>
            <p>กรอกข้อมูลด้านล่างแล้วกด <strong>Send to Discord</strong> เพื่อสั่งเล่นเพลงผ่าน Web URL.</p>
            <form action="/command" method="get">
                <input type="hidden" name="action" value="!play">
                <label for="guild_id">Guild ID (Server ID)</label>
                <input id="guild_id" name="guild_id" placeholder="123456789012345678" required>
                <label for="text_channel_id">Text Channel ID</label>
                <input id="text_channel_id" name="text_channel_id" placeholder="234567890123456789" required>
                <label for="voice_channel_id">Voice Channel ID</label>
                <input id="voice_channel_id" name="voice_channel_id" placeholder="345678901234567890" required>
                <label for="query">Query / YouTube URL / Search</label>
                <input id="query" name="query" placeholder="https://www.youtube.com/watch?v=... or despacito" required>
                <button type="submit">Send to Discord</button>
            </form>
            <div class="note">
                <p>ถ้าอยากดู API request ให้ใช้ URL แบบนี้:</p>
                <div class="code">/command?action=!play&guild_id=...&text_channel_id=...&voice_channel_id=...&query=...</div>
                <p>หรือเข้าหน้า UI นี้ได้ที่ <a href="/action=ui">/action=ui</a></p>
            </div>
        </div>
    </body>
    </html>
    '''


def run():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)


def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
