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
TELEGRAM_BOT_TOKEN_TAROT_RUS = os.getenv("TELEGRAM_BOT_TOKEN_TAROT_RUS", "ВАШ_ТОКЕН_ТАРО_РУС")
TELEGRAM_BOT_TOKEN_SONNIK_RUS = os.getenv("TELEGRAM_BOT_TOKEN_SONNIK_RUS", "ВАШ_ТОКЕН_СОННИК_РУС")
TELEGRAM_BOT_TOKEN_RESHALA = os.getenv("TELEGRAM_BOT_TOKEN_RESHALA", "ВАШ_ТОКЕН_РЕШАЛА")
TELEGRAM_API_URL_TAROT_RUS = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_TAROT_RUS}/sendMessage"
TELEGRAM_API_URL_SONNIK_RUS = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_SONNIK_RUS}/sendMessage"
TELEGRAM_API_URL_RESHALA = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN_RESHALA}/sendMessage"

# Настройки базы данных
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "default_db"),
    "user": os.getenv("DB_USER", "gen_user"),
    "password": os.getenv("DB_PASSWORD", "({Ga:8\\5YFVa9u"),
    "host": os.getenv("DB_HOST", "212.193.26.202"),
    "port": os.getenv("DB_PORT", 5432)
}

# Словарь для отображения нормальных названий товаров
PRODUCT_NAMES_TAROT_RUS = {
    "cards_3": "3 запроса картам",
    "cards_5": "5 запросов картам",
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

PRODUCT_NAMES_SONNIK_RUS = {
    "sonnik_1": "1 толкование сна",
    "sonnik_3": "3 толкования снов",
    "sonnik_5": "5 толкований снов",
    "sonnik_month": "Подписка на 30 дней"
}

# Набор товаров, при покупке которых нужно сразу формировать гороскоп
HOROSCOPE_PRODUCTS = {
    "horoscope_sub_7",
    "horoscope_sub_14",
    "horoscope_sub_30"
}
PRODUCT_NAMES_RESHALA = {
    "reshala_10": "10 токенов",
    "reshala_20": "20 токенов",
    "reshala_50": "50 токенов",
    "reshala_100": "100 токенов"
}

# =========================================
# СЛОВАРИ для обновления полей в БД
# (Тут указываем, какое поле в какой таблице прибавлять)
PRODUCT_UPDATES_TAROT_RUS = {
    "cards_3":       {"field": "request_questions", "value": 3},
    "cards_5":      {"field": "request_questions", "value": 5},
    "cards_10":      {"field": "request_questions", "value": 10},
    "cards_30":      {"field": "request_questions", "value": 30},
    "cards_7d":      {"field": "premium_days_left", "value": 7},
    "cards_30d":     {"field": "premium_days_left", "value": 30},
    "matrix_1":      {"field": "request_matrix", "value": 1},
    "matrix_5":      {"field": "request_matrix", "value": 5},
    "matrix_10":     {"field": "request_matrix", "value": 10},
    "horoscope_sub_7":  {"field": "days_for_horoscope", "value": 7},
    "horoscope_sub_14": {"field": "days_for_horoscope", "value": 14},
    "horoscope_sub_30": {"field": "days_for_horoscope", "value": 30},
    "horoscope_tomorrow": {"field": "day_horoscope", "value": 1},
    "horoscope_week":     {"field": "week_horoscope", "value": 1},
    "horoscope_month":    {"field": "month_horoscope", "value": 1},
    "horoscope_year":     {"field": "year_horoscope", "value": 1}
}

PRODUCT_UPDATES_SONNIK_RUS = {
    "sonnik_1":     {"field": "dream_requests",       "value": 1},
    "sonnik_3":     {"field": "dream_requests",       "value": 3},
    "sonnik_5":     {"field": "dream_requests",       "value": 5},
    "sonnik_month": {"field": "premium_days_sonnik",  "value": 30}  # например, на 30 дней
}

PRODUCT_UPDATES_RESHALA = {
    "reshala_10":     {"field": "tokens_count",       "value": 10},
    "reshala_20":     {"field": "tokens_count",       "value": 20},
    "reshala_50":     {"field": "tokens_count",       "value": 50},
    "reshala_100":    {"field": "tokens_count",       "value": 100}  # например, на 30 дней
}
# =========================================


# Webhook для обработки событий от YooKassa
@app.post("/webhook/yookassa")
async def webhook_yookassa(request: Request):
    try:
        data = await request.json()
        logging.info(f"📩 Получено уведомление от YooKassa: {data}")

        event = data.get("event")
        payment_info = data.get("object", {})
        metadata = payment_info.get("metadata", {}) # Изменения для разделения ботов
        bot_type = metadata.get("bot_type")
        chat_id = payment_info.get("metadata", {}).get("chat_id")
        product_id = payment_info.get("metadata", {}).get("product_id")
        amount = payment_info.get("amount", {}).get("value")  # Получаем сумму платежа

        if bot_type == "reshalbich":
            logging.info(
                "⏭️ Пропускаем legacy webhook Решалыча: платежи обрабатывает новый бот. "
                "event=%s chat_id=%s product_id=%s amount=%s",
                event,
                chat_id,
                product_id,
                amount,
            )
            return {"status": "ok", "skipped": "reshalbich"}

        if event == "payment.succeeded":
            if chat_id and product_id and bot_type:
                # Обновляем данные в базе данных
                success = update_user_data(bot_type, chat_id, product_id)
                if success:
                    # Записываем успешную покупку в базу данных
                    record_sale(bot_type, chat_id, product_id, amount)
                    # Определяем "красивое" имя товара, исходя из bot_type
                    if bot_type == "tarot_rus":
                        product_name = PRODUCT_NAMES_TAROT_RUS.get(product_id, product_id)
                    elif bot_type == "sonnik_rus":
                        product_name = PRODUCT_NAMES_SONNIK_RUS.get(product_id, product_id)
                    elif bot_type == "reshalbich":
                        product_name = PRODUCT_NAMES_RESHALA.get(product_id, product_id)
                    else:
                        product_name = PRODUCT_NAMES_SONNIK_RUS.get(product_id, product_id)
                    send_telegram_message(bot_type, chat_id, escape_markdown(f"✅ Оплата прошла успешно!\nТовар: '{product_name}' зачислен на ваш аккаунт."))
                    
                    # Если это бот Таро и товар входит в список HOROSCOPE_PRODUCTS, формируем гороскоп
                    if bot_type == "tarot_rus" and product_id in HOROSCOPE_PRODUCTS:
                        call_bot_for_horoscope(chat_id)
                else:
                    send_telegram_message(bot_type, chat_id, "❌ Произошла ошибка при зачислении товара. Свяжитесь с поддержкой.")
        elif event == "payment.canceled":
            if chat_id and bot_type:
                send_telegram_message(bot_type, chat_id, "❌ Ваш платеж был отменен. Пожалуйста, попробуйте снова.")
        elif event == "refund.succeeded":
            if chat_id and bot_type:
                send_telegram_message(bot_type, chat_id, "💸 Возврат средств успешно выполнен.")

        return {"status": "ok"}
    except Exception as e:
        logging.error(f"❌ Ошибка обработки вебхука: {e}")
        return {"status": "error"}

# Обновление данных пользователя в базе данных
def update_user_data(bot_type: str, chat_id: int, product_id: str) -> bool:
    """
    Обновляет данные пользователя в базе, исходя из того, к какому боту относится покупка
    и какой именно товар был куплен.
    """
    try:
        # Выбираем нужные словари:
        if bot_type == "tarot_rus":
            product_dict = PRODUCT_UPDATES_TAROT_RUS
            table_name = "users"  # Таблица для бота "Таро"
        elif bot_type == "sonnik_rus":
            product_dict = PRODUCT_UPDATES_SONNIK_RUS
            table_name = "users_sonnik"  # Таблица для бота "Сонник"
        elif bot_type == "reshalbich":
            product_dict = PRODUCT_UPDATES_RESHALA
            table_name = "users_resh"
            user_field = "user_id_resh"
        else:
            logging.error(f"Неизвестный bot_type: {bot_type}")
            return False

        # Если товар не найден в словаре
        if product_id not in product_dict:
            logging.error(f"❌ Неизвестный продукт: {product_id}")
            return False

        # Достаём, какое поле и на сколько надо увеличить
        update_info = product_dict[product_id]
        field = update_info["field"]
        value = update_info["value"]

        query = f"""
            UPDATE {table_name}
            SET {field} = {field} + %s
            WHERE {user_field if bot_type == 'reshalbich' else ('user_id_son' if bot_type == 'sonnik_rus' else 'user_id')} = %s
        """

        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (value, chat_id))
                conn.commit()

        logging.info(
            f"✅ [{bot_type.upper()}] Обновлено поле '{field}' на +{value} для пользователя {chat_id}"
        )
        return True

    except Exception as e:
        logging.error(f"❌ Ошибка при обновлении данных пользователя: {e}")
        return False

# Запись покупки в таблицу sales
def record_sale(bot_type: str, chat_id: int, product_id: str, amount: str):
    """
    Запись факта покупки в таблицу sales. Можно хранить bot_type отдельным полем.
    """
    try:
        # Выбираем "красивое" название товара
        if bot_type == "tarot_rus":
            product_name = PRODUCT_NAMES_TAROT_RUS.get(product_id, product_id)
        elif bot_type == "sonnik_rus":
            product_name = PRODUCT_NAMES_SONNIK_RUS.get(product_id, product_id)
        elif bot_type == "reshalbich":
            product_name = PRODUCT_NAMES_RESHALA.get(product_id, product_id)
        else:
            product_name = PRODUCT_NAMES_SONNIK_RUS.get(product_id, product_id)

        query = """
            INSERT INTO sales (user_id, product_name, amount, bot_type) 
            VALUES (%s, %s, %s, %s);
        """

        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (chat_id, product_name, amount, bot_type))
                conn.commit()

        logging.info(f"✅ [{bot_type.upper()}] Продажа записана: Пользователь {chat_id} купил '{product_name}' за {amount} руб.")
    except Exception as e:
        logging.error(f"❌ Ошибка записи в таблицу продаж: {e}")

# Функция экранирования спецсимволов в MarkdownV2
def escape_markdown(text):
    escape_chars = r'\_*[]()~`>#+-=|{}'
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)

# Отправка сообщений в Telegram
def send_telegram_message(bot_type: str, chat_id: int, text: str):
    """
    Отправляет сообщение пользователю через соответствующий токен/URL.
    """
    if bot_type == "tarot_rus":
        url = TELEGRAM_API_URL_TAROT_RUS
    elif bot_type == "sonnik_rus":
        url = TELEGRAM_API_URL_SONNIK_RUS
    elif bot_type == "reshalbich":
        url = TELEGRAM_API_URL_RESHALA
    else:
        logging.error(f"Неизвестный bot_type при отправке в Telegram: {bot_type}")
        return

    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logging.info(f"📩 Сообщение отправлено пользователю {chat_id} в бота '{bot_type}'")
        else:
            logging.error(f"❌ Ошибка отправки сообщения: {response.text}")
    except Exception as e:
        logging.error(f"❌ Ошибка при отправке сообщения в Telegram: {e}")

def call_bot_for_horoscope(user_id: int):
    """
    Делает POST-запрос к серверу бота, чтобы сформировать 
    гороскоп для user_id и отправить его в Telegram.
    """
    try:
        # Если эндпоинт в боте называется /internal/activate_horoscope
        endpoint = f"{BOT_SERVER_URL}/internal/activate_horoscope"
        data = {"user_id": user_id}
        resp = requests.post(endpoint, json=data, timeout=30)
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
