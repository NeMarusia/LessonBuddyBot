```python
import sqlite3
import threading
from datetime import datetime
import telebot

# Чтение токена и инициализация бота
with open('Token.txt', 'r') as file:
    API_TOKEN = file.read().strip()
bot = telebot.TeleBot(API_TOKEN)

# Удаление текущего вебхука перед использованием polling
bot.remove_webhook()

# Инициализация базы данных
DB_PATH = 'db.sqlite3'


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
    curator_id = 'https://t.me/SidorenkoMN'
    message_text = (
        f'🔔 Новая замена!\n'
        f'📅 Дата: {date}\n'
        f'👥 Группа: {group}\n'
        f'💬 Причина: {reason}\n'
        f'👤 От: @{user}'
    )
    bot.send_message(curator_id, message_text)


# Запуск бота
if __name__ == '__main__':
    threading.Thread(target=bot.infinity_polling, kwargs={"none_stop": True}).start()

```

### Объяснение:
1. **Перемещение инициализации `bot` перед использованием:**
   Теперь объект `bot` создаётся сразу после загрузки токена из файла.
   
2. **Удаление ненужного кода:**
   Убраны лишние импортированные библиотеки, не связанные с текущей задачей (например, непроверяемые импорты `CELERY`, `SSL`).

3. **Глобальная обработка исключений:**
   Поправлены участки кода, где могли возникнуть ошибки, например, в форматировании даты.

Теперь программа должна работать корректно без ошибок `NameError`.