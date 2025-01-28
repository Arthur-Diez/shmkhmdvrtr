from fastapi import FastAPI, Request
import logging
import requests
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import re

app = FastAPI()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "ВАШ_ТОКЕН")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Настройки базы данных
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "tarot_bot"),
    "user": os.getenv("DB_USER", "main"),
    "password": os.getenv("DB_PASSWORD", "parole228"),
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": os.getenv("DB_PORT", 5432)
}

# Webhook для обработки событий от YooKassa
@app.post("/webhook/yookassa")
async def webhook_yookassa(request: Request):
    try:
        data = await request.json()
        logging.info(f"\ud83d\udce9 Получено уведомление от YooKassa: {data}")

        event = data.get("event")
        payment_info = data.get("object", {})
        chat_id = payment_info.get("metadata", {}).get("chat_id")
        product_id = payment_info.get("metadata", {}).get("product_id")

        if event == "payment.succeeded":
            if chat_id and product_id:
                # Обновляем данные в базе данных
                success = update_user_data(chat_id, product_id)
                if success:
                    send_telegram_message(chat_id, f"✅ Оплата прошла успешно! Товар ({product_id}) зачислен на ваш аккаунт.")
                else:
                    send_telegram_message(chat_id, "❌ Произошла ошибка при зачислении товара. Свяжитесь с поддержкой.")
        elif event == "payment.canceled":
            if chat_id:
                send_telegram_message(chat_id, "❌ Ваш платеж был отменен. Попробуйте снова.")
        elif event == "refund.succeeded":
            if chat_id:
                send_telegram_message(chat_id, "\ud83d\udcb8 Возврат средств успешно выполнен.")

        return {"status": "ok"}
    except Exception as e:
        logging.error(f"❌ Ошибка обработки вебхука: {e}")
        return {"status": "error"}

# Обновление данных пользователя в базе данных
def update_user_data(chat_id, product_id):
    try:
        # Привязка товаров к обновлению полей
        product_updates = {
            "cards_10": {"field": "request_questions", "value": 10},
            "cards_30": {"field": "request_questions", "value": 30},
            "cards_7d": {"field": "premium_days_left", "value": 7},
            "cards_30d": {"field": "premium_days_left", "value": 30},
            "matrix_1": {"field": "request_matrix", "value": 1},
            "matrix_5": {"field": "request_matrix", "value": 5},
            "matrix_10": {"field": "request_matrix", "value": 10}
        }

        if product_id not in product_updates:
            logging.error(f"❌ Неизвестный продукт: {product_id}")
            return False

        update = product_updates[product_id]
        field = update["field"]
        value = update["value"]

        query = f"""
            UPDATE users
            SET {field} = {field} + %s
            WHERE user_id = %s;
        """

        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (value, chat_id))
                conn.commit()

        logging.info(f"✅ Обновлено поле {field} для пользователя {chat_id}, добавлено значение: {value}")
        return True

    except Exception as e:
        logging.error(f"❌ Ошибка обновления данных пользователя: {e}")
        return False

# Экранирование спецсимволов в Telegram Markdown
def escape_markdown(text):
    escape_chars = r'\\*_`[]()~>#+-=|{}.!'
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\\\\1", text)

# Отправка сообщений в Telegram
def send_telegram_message(chat_id, text):
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        response = requests.post(TELEGRAM_API_URL, json=payload)
        if response.status_code == 200:
            logging.info(f"\ud83d\udce9 Уведомление отправлено пользователю {chat_id}")
        else:
            logging.error(f"❌ Ошибка отправки сообщения в Telegram: {response.text}")
    except Exception as e:
        logging.error(f"❌ Ошибка при попытке отправить сообщение в Telegram: {e}")

# Запуск сервера
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)