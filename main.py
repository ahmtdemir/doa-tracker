import os
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

payload = {
    "chat_id": CHAT_ID,
    "text": "✅ GitHub Actions başarıyla çalışıyor!"
}

response = requests.post(url, json=payload)

print(response.status_code)
print(response.text)
