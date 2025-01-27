from fastapi import FastAPI, Request
import logging
import requests
import os

app = FastAPI()

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Ваш токен Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "your_default_token")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Обработка успешных платежей
@app.post("/webhook/yookassa")
async def webhook_yookassa(request: Request):
    try:
        data = await request.json()
        logging.info(f"Получено уведомление: {data}")

        # Проверяем, что платеж успешен
        if data.get("event") == "payment.succeeded":
            payment_info = data.get("object", {})
            chat_id = payment_info.get("metadata", {}).get("chat_id")  # Достаем chat_id из metadata
            if chat_id:
                send_telegram_message(chat_id, "✅ Ваш платеж успешно обработан! Спасибо за оплату. 😊")
            return {"status": "ok"}
        else:
            logging.info("Неуспешное уведомление обработано.")
            return {"status": "ignored"}
    except Exception as e:
        logging.error(f"Ошибка обработки webhook: {e}")
        return {"status": "error"}

# Обработка всех остальных уведомлений
@app.post("/webhook/yookassa/other")
async def webhook_yookassa_other(request: Request):
    try:
        data = await request.json()
        logging.info(f"Получено другое уведомление: {data}")

        event = data.get("event")
        payment_info = data.get("object", {})
        chat_id = payment_info.get("metadata", {}).get("chat_id")  # Достаем chat_id из metadata

        if event == "payment.canceled" and chat_id:
            send_telegram_message(chat_id, "❌ Ваш платеж был отменен. Попробуйте еще раз или свяжитесь с поддержкой.")
        elif event == "refund.succeeded" and chat_id:
            send_telegram_message(chat_id, "💸 Возврат средств успешно выполнен. Если есть вопросы, напишите в поддержку.")

        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Ошибка обработки webhook: {e}")
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