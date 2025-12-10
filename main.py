import requests
from flask import Flask, jsonify, request

from omnidisp.app.dispatcher.dispatcher_controller import handle_message
from omnidisp.config.settings import TELEGRAM_BOT_TOKEN

app = Flask(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else ""
seen_chats = set()


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok"})


@app.route("/api/disp", methods=["POST"])
def api_disp():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    is_first_message = bool(data.get("is_first_message", False))

    if not text:
        return jsonify({"error": "empty text"}), 400

    result = handle_message(text=text, is_first_message=is_first_message)
    return jsonify(result), 200


@app.route("/api/tg", methods=["POST"])
def api_telegram():
    update = request.get_json(silent=True) or {}

    try:
        message = update["message"]["text"]
        chat_id = update["message"]["chat"]["id"]
    except Exception:
        return jsonify({"status": "ignored"}), 200

    is_first = chat_id not in seen_chats
    if is_first:
        seen_chats.add(chat_id)

    result = handle_message(message, is_first_message=is_first)

    trace = result.get("internal_trace", "")
    client_answer = result.get("client_answer", "")

    text_to_send = f"{trace}\n\nCLIENT ANSWER:\n{client_answer}"

    if TELEGRAM_API:
        send_url = f"{TELEGRAM_API}/sendMessage"
        payload = {"chat_id": chat_id, "text": text_to_send}
        try:
            requests.post(send_url, json=payload, timeout=10)
        except Exception:
            pass

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
