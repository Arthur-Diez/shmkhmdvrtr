from fastapi import FastAPI, Request
import logging
import requests
import os

app = FastAPI()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "ВАШ_ТОКЕН")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Webhook для событий YooKassa
@app.post("/webhook/yookassa")
async def webhook_yookassa(request: Request):
    try:
        data = await request.json()
        logging.info(f"Получено уведомление от YooKassa: {data}")

        event = data.get("event")
        payment_info = data.get("object", {})
        chat_id = payment_info.get("metadata", {}).get("chat_id")

        if event == "payment.succeeded":
            if chat_id:
                send_telegram_message(chat_id, "✅ Ваш платеж успешно обработан! Спасибо за оплату. 😊")
        elif event == "payment.canceled":
            if chat_id:
                send_telegram_message(chat_id, "❌ Ваш платеж был отменен. Попробуйте еще раз или свяжитесь с поддержкой.")
        elif event == "refund.succeeded":
            if chat_id:
                send_telegram_message(chat_id, "💸 Возврат средств успешно выполнен. Если есть вопросы, напишите в поддержку.")

        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Ошибка обработки вебхука: {e}")
        return {"status": "error"}

# Корневой маршрут
@app.get("/")
async def root():
    return {"message": "Сайт работает. Используйте Telegram-бот для взаимодействия."}

# Успешная оплата
@app.get("/success")
async def payment_success():
    return {"message": "Оплата успешно завершена! Возвращайтесь в Telegram для продолжения работы."}

# Обработка favicon
@app.get("/favicon.ico")
async def favicon():
    return {"message": "Favicon запрошен. Игнорируем."}

# Отправка сообщений в Telegram
def send_telegram_message(chat_id, text):
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        response = requests.post(TELEGRAM_API_URL, json=payload)
        if response.status_code != 200:
            logging.error(f"Ошибка отправки сообщения в Telegram: {response.text}")
    except Exception as e:
        logging.error(f"Ошибка при попытке отправить сообщение в Telegram: {e}")

# Запуск приложения
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)