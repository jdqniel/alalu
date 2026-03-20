import urllib.request
import urllib.parse
import os


def send(msg: str):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat = os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({'chat_id': chat, 'text': msg}).encode()
        urllib.request.urlopen(url, data, timeout=5)
    except Exception:
        pass
