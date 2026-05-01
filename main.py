import os
import sqlite3
import threading
from datetime import datetime

import telebot

API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not API_TOKEN:
    raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

CURATOR_ID = int(os.getenv("CURATOR_ID", "143612737"))
DB_PATH = os.getenv("DB_PATH", "db.sqlite3")

bot = telebot.TeleBot(API_TOKEN)

# Удаление текущего вебхука перед использованием polling
bot.remove_webhook()

# Инициализация базы данных

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS swaps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        "group" TEXT,
        lesson_date TEXT,
        reason TEXT,
        body TEXT,
        user TEXT,
        status INTEGER,
        created_at TEXT,
        updated_at TEXT,
        details TEXT
    )''')
    conn.commit()
    conn.close()


init_db()


# Хэндлер старта
@bot.message_handler(commands=['start'])
def start_handler(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('Нужна замена!', 'Замена не нужна!', 'Просмотр статусов замен')
    bot.send_message(message.chat.id, 'Привет! Если тебе необходима замена, выбери действие:', reply_markup=markup)


# Пользовательские состояния
user_states = {}


@bot.message_handler(func=lambda msg: msg.text == 'Нужна замена!')
def need_swap_step_1(message):
    bot.send_message(message.chat.id, 'Выбери дату замены (в формате ДД.ММ.ГГГГ):')
    user_states[message.chat.id] = {'step': 'awaiting_date'}


@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('step') == 'awaiting_date')
def need_swap_step_2(message):
    try:
        date = datetime.strptime(message.text, '%d.%m.%Y')
        user_states[message.chat.id]['lesson_date'] = date
        user_states[message.chat.id]['step'] = 'awaiting_reason'
        bot.send_message(message.chat.id, 'Напиши причину замены:')
    except ValueError:
        bot.send_message(message.chat.id, 'Неверный формат даты. Попробуй снова.')


@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('step') == 'awaiting_reason')
def need_swap_step_3(message):
    user_states[message.chat.id]['reason'] = message.text
    user_states[message.chat.id]['step'] = 'awaiting_group'
    bot.send_message(message.chat.id, 'Укажи группу, которой нужна замена:')


@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id, {}).get('step') == 'awaiting_group')
def need_swap_finalize(message):
    data = user_states.pop(message.chat.id)
    group = message.text
    date = data['lesson_date'].strftime('%Y-%m-%d')
    reason = data['reason']
    user = message.from_user.username or str(message.from_user.id)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO swaps ("group", lesson_date, reason, user, status, created_at, updated_at)
                      VALUES (?, ?, ?, ?, ?, ?, ?)''',
                   (group, date, reason, user, 0, datetime.now(), datetime.now()))
    conn.commit()
    conn.close()

    bot.send_message(message.chat.id, 'Спасибо! Твой запрос отправлен куратору.')
    notify_curator(group, date, reason, user)


# Уведомление куратора (заглушка)
def notify_curator(group, date, reason, user):
    curator_id = CURATOR_ID
    message_text = (
        f'🔔 Новая замена!\n'
        f'📅 Дата: {date}\n'
        f'👥 Группа: {group}\n'
        f'💬 Причина: {reason}\n'
        f'👤 От: @{user}'
    )
    bot.send_message(curator_id, message_text)

# Модифицируем стартовый хэндлер, чтобы создавалось уникальное меню для куратора
@bot.message_handler(commands=['start'])
def start_handler(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('Нужна замена!', 'Замена не нужна!', 'Просмотр статусов замен')

    # Если пользователь - куратор, добавляем кнопку "Просмотр всех замен"
    if message.from_user.id == CURATOR_ID:
        markup.add('Просмотр всех замен')

    bot.send_message(message.chat.id, 'Привет! Если тебе необходима замена, выбери действие:', reply_markup=markup)


# Хэндлер для кнопки "Просмотр всех замен"
@bot.message_handler(func=lambda msg: msg.text == 'Просмотр всех замен' and msg.from_user.id == CURATOR_ID)
def view_all_swaps_handler(message):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Извлекаем все данные из таблицы "swaps"
    cursor.execute(
        'SELECT "id", "group", "lesson_date", "reason", "user", "status" FROM swaps ORDER BY created_at DESC')
    rows = cursor.fetchall()
    conn.close()

    # Формируем сообщение
    if rows:
        response = "📋 Все замены:\n"
        for row in rows:
            swap_id, group, lesson_date, reason, user, status = row
            status_text = 'В обработке' if status == 0 else 'Обработано'
            response += (
                f"➖ Замена #{swap_id}\n"
                f"👥 Группа: {group}\n"
                f"📅 Дата: {lesson_date}\n"
                f"💬 Причина: {reason}\n"
                f"👤 Пользователь: {user}\n"
                f"📌 Статус: {status_text}\n\n"
            )
    else:
        response = "📋 Список замен пуст."

    # Отправляем список замен куратору
    bot.send_message(message.chat.id, response)


# Добавляем заглушку для доступа другим пользователям
@bot.message_handler(func=lambda msg: msg.text == 'Просмотр всех замен' and msg.from_user.id != CURATOR_ID)
def view_all_swaps_access_denied(message):
    bot.send_message(message.chat.id, '❌ У вас нет доступа к этой функции.')


# Запуск бота
if __name__ == '__main__':
    threading.Thread(target=bot.infinity_polling, kwargs={"none_stop": True}).start()
