from fastapi import FastAPI, Request
import logging
import requests
import os
import re

app = FastAPI()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "ВАШ_ТОКЕН")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# URL для API-метода бота
BOT_API_URL = os.getenv("BOT_API_URL", "http://localhost:8000/process_payment")  # Замените на URL вашего бота

# Webhook для обработки событий от YooKassa
@app.post("/webhook/yookassa")
async def webhook_yookassa(request: Request):
    try:
        data = await request.json()
        logging.info(f"📩 Получено уведомление от YooKassa: {data}")

        event = data.get("event")
        payment_info = data.get("object", {})
        chat_id = payment_info.get("metadata", {}).get("chat_id")
        product_id = payment_info.get("metadata", {}).get("product_id")

        if event == "payment.succeeded":
            if chat_id and product_id:
                # Отправляем данные об оплате в бот
                success = notify_bot(chat_id, product_id)
                if success:
                    logging.info(f"✅ Уведомление успешно отправлено в бота для пользователя {chat_id}")
                else:
                    logging.error(f"❌ Ошибка отправки уведомления в бота для пользователя {chat_id}")
        elif event == "payment.canceled":
            if chat_id:
                send_telegram_message(chat_id, "❌ Ваш платеж был отменен. Попробуйте снова.")
        elif event == "refund.succeeded":
            if chat_id:
                send_telegram_message(chat_id, "💸 Возврат средств успешно выполнен.")

        return {"status": "ok"}
    except Exception as e:
        logging.error(f"❌ Ошибка обработки вебхука: {e}")
        return {"status": "error"}

# Функция уведомления бота об успешной оплате
def notify_bot(chat_id, product_id):
    try:
        payload = {"chat_id": chat_id, "product_id": product_id}
        response = requests.post(BOT_API_URL, json=payload)
        if response.status_code == 200:
            return True
        else:
            logging.error(f"❌ Ошибка отправки данных в бот: {response.text}")
            return False
    except Exception as e:
        logging.error(f"❌ Ошибка при отправке данных в бот: {e}")
        return False

# Корневой маршрут
@app.get("/")
async def root():
    return {"message": "✅ Сайт работает. Используйте Telegram-бот для взаимодействия."}

# Маршрут для успешного платежа
@app.post("/success")
async def payment_success():
    logging.info("🔗 Пользователь вернулся после успешного платежа")
    return {"message": "Оплата успешно завершена! Вернитесь в Telegram-бот."}

# Заглушка для favicon.ico
@app.get("/favicon.ico")
async def favicon():
    return {"message": "Favicon запрошен. Игнорируем."}

# Экранирование спецсимволов в Telegram Markdown
def escape_markdown(text):
    escape_chars = r'\*_`[]()~>#+-=|{}.!'
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

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
            logging.info(f"📩 Уведомление отправлено пользователю {chat_id}")
        else:
            logging.error(f"❌ Ошибка отправки сообщения в Telegram: {response.text}")
    except Exception as e:
        logging.error(f"❌ Ошибка при попытке отправить сообщение в Telegram: {e}")

# Запуск сервера
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)