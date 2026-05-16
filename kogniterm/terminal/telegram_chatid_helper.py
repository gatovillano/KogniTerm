import time
import requests

def get_first_private_chat_id(token, timeout=60):
    """
    Hace polling a getUpdates para obtener el primer chat_id privado que envíe un mensaje al bot.
    Devuelve el chat_id o None si no se detecta en el timeout.
    """
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    start = time.time()
    last_update_id = None
    while time.time() - start < timeout:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            for update in data.get("result", []):
                if last_update_id is not None and update["update_id"] <= last_update_id:
                    continue
                last_update_id = update["update_id"]
                msg = update.get("message")
                if msg and msg.get("chat", {}).get("type") == "private":
                    return msg["chat"]["id"]
        time.sleep(2)
    return None
