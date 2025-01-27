from fastapi import FastAPI, Request
import logging
import requests
import os

app = FastAPI()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Ваш токен Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7676861261:AAHjc-5682FoCJ1OEhr8mJycaisy-EpSF6U")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Обработка всех событий от YooKassa
@app.post("/webhook/yookassa")
async def webhook_yookassa(request: Request):
    try:
        data = await request.json()
        logging.info(f"Получено уведомление от YooKassa: {data}")

        # Извлекаем основную информацию
        event = data.get("event")
        payment_info = data.get("object", {})
        chat_id = payment_info.get("metadata", {}).get("chat_id")

        # Обрабатываем события
        if event == "payment.succeeded":
            # Успешный платеж
            if chat_id:
                send_telegram_message(chat_id, "✅ Ваш платеж успешно обработан! Спасибо за оплату. 😊")
            return {"status": "ok"}
        elif event == "payment.canceled":
            # Отмененный платеж
            if chat_id:
                send_telegram_message(chat_id, "❌ Ваш платеж был отменен. Попробуйте еще раз или свяжитесь с поддержкой.")
            return {"status": "ok"}
        elif event == "refund.succeeded":
            # Успешный возврат
            if chat_id:
                send_telegram_message(chat_id, "💸 Возврат средств успешно выполнен. Если есть вопросы, напишите в поддержку.")
            return {"status": "ok"}
        else:
            logging.info(f"Необработанное событие: {event}")
            return {"status": "ignored"}
    except Exception as e:
        logging.error(f"Ошибка обработки вебхука: {e}")
        return {"status": "error"}

# Функция отправки сообщений в Telegram
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

# Добавляем запуск приложения на Render
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))  # Используем порт из переменной окружения PORT
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)