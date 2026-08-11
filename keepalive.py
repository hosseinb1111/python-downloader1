from flask import Flask
import threading

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

def run():
    app.run(host="0.0.0.0", port=10000)

def start_keepalive():
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()
