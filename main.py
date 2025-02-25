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

BOT_SERVER_URL = "http://147.45.167.44:8000"

# Токен Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "ВАШ_ТОКЕН")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Настройки базы данных
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "default_db"),
    "user": os.getenv("DB_USER", "gen_user"),
    "password": os.getenv("DB_PASSWORD", "({Ga:8\\5YFVa9u"),
    "host": os.getenv("DB_HOST", "212.193.26.202"),
    "port": os.getenv("DB_PORT", 5432)
}

# Словарь для отображения нормальных названий товаров
PRODUCT_NAMES = {
    "cards_10": "10 запросов картам",
    "cards_30": "30 запросов картам",
    "cards_7d": "Подписка на карты (7 дней)",
    "cards_30d": "Подписка на карты (30 дней)",
    "matrix_1": "1 запрос матрице судьбы",
    "matrix_5": "5 запросов матрице судьбы",
    "matrix_10": "10 запросов матрице судьбы",
    "horoscope_sub_7": "Подписка на индивидуальный гороскоп 7 дней",
    "horoscope_sub_14": "Подписка на индивидуальный гороскоп 14 дней",
    "horoscope_sub_30": "Подписка на индивидуальный гороскоп 30 дней",
    "horoscope_tomorrow": "Индивидуальный гороскоп на завтра",
    "horoscope_week": "Индивидуальный гороскоп на неделю",
    "horoscope_month": "Индивидуальный гороскоп на месяц",
    "horoscope_year": "Индивидуальный гороскоп на год"
}

# Набор товаров, при покупке которых нужно сразу формировать гороскоп
HOROSCOPE_PRODUCTS = {
    "horoscope_sub_7",
    "horoscope_sub_14",
    "horoscope_sub_30"
}

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
        amount = payment_info.get("amount", {}).get("value")  # Получаем сумму платежа

        if event == "payment.succeeded":
            if chat_id and product_id:
                # Обновляем данные в базе данных
                success = update_user_data(chat_id, product_id)
                if success:
                    # Записываем успешную покупку в базу данных
                    record_sale(chat_id, product_id, amount)
                    send_telegram_message(chat_id, escape_markdown(f"✅ Оплата прошла успешно!\nТовар: '{PRODUCT_NAMES.get(product_id, product_id)}' зачислен на ваш аккаунт."))
                    
                    # 4) Если это товар гороскопа, вызываем бота для автоматической отправки гороскопа
                    if product_id in HOROSCOPE_PRODUCTS:
                        call_bot_for_horoscope(chat_id)
                else:
                    send_telegram_message(chat_id, "❌ Произошла ошибка при зачислении товара. Свяжитесь с поддержкой.")
        elif event == "payment.canceled":
            if chat_id:
                send_telegram_message(chat_id, "❌ Ваш платеж был отменен. Пожалуйста, попробуйте снова.")
        elif event == "refund.succeeded":
            if chat_id:
                send_telegram_message(chat_id, "💸 Возврат средств успешно выполнен.")

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
            "matrix_10": {"field": "request_matrix", "value": 10},
            "horoscope_sub_7": {"field": "days_for_horoscope", "value": 7},
            "horoscope_sub_14": {"field": "days_for_horoscope", "value": 14},
            "horoscope_sub_30": {"field": "days_for_horoscope", "value": 30},
            "horoscope_tomorrow": {"field": "day_horoscope", "value": 1},
            "horoscope_week": {"field": "week_horoscope", "value": 1},
            "horoscope_month": {"field": "month_horoscope", "value": 1},
            "horoscope_year": {"field": "year_horoscope", "value": 1}
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

# Запись покупки в таблицу sales
def record_sale(chat_id, product_id, amount):
    try:
        query = """
            INSERT INTO sales (user_id, product_name, amount) 
            VALUES (%s, %s, %s);
        """

        product_name = PRODUCT_NAMES.get(product_id, product_id)  # Получаем нормальное название товара

        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (chat_id, product_name, amount))
                conn.commit()

        logging.info(f"✅ Продажа записана: Пользователь {chat_id} купил '{product_name}' за {amount} руб.")
    except Exception as e:
        logging.error(f"❌ Ошибка записи в таблицу продаж: {e}")

# Функция экранирования спецсимволов в MarkdownV2
def escape_markdown(text):
    escape_chars = r'\_*[]()~`>#+-=|{}'
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
            logging.info(f"\ud83d\udce9 Уведомление отправлено пользователю {chat_id}")
        else:
            logging.error(f"❌ Ошибка отправки сообщения в Telegram: {response.text}")
    except Exception as e:
        logging.error(f"❌ Ошибка при попытке отправить сообщение в Telegram: {e}")

def call_bot_for_horoscope(user_id: int):
    """
    Делает POST-запрос к серверу бота, чтобы сформировать 
    гороскоп для user_id и отправить его в Telegram.
    """
    try:
        # Если эндпоинт в боте называется /internal/activate_horoscope
        endpoint = f"{BOT_SERVER_URL}/internal/activate_horoscope"
        data = {"user_id": user_id}
        resp = requests.post(endpoint, json=data, timeout=10)
        if resp.status_code == 200:
            logging.info(f"✅ Запрос формирования гороскопа отправлен боту для user_id={user_id}.")
        else:
            logging.error(f"❌ Ошибка при запросе к боту: {resp.status_code}, {resp.text}")
    except Exception as e:
        logging.error(f"❌ call_bot_for_horoscope ошибка: {e}")

# Запуск сервера
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)