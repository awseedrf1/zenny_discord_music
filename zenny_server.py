import os
import logging
from flask import Flask
from threading import Thread

# Disable Flask logging for a cleaner console
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask('')

@app.route('/')
def home():
    return "Zenny Bot is Online! 🚀"

def run():
    # Render.com provides the PORT environment variable
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()
    print("Web server started, ready to keep the bot alive!")
