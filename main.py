import telebot
from telebot import types

# Initialize the bot with your token
API_TOKEN = 'YOUR_API_TOKEN'
bot = telebot.TeleBot(API_TOKEN)

# Database simulation
users_db = []    # In a real application, this would be a database
orders_db = []   # In a real application, this would be a database
_order_id_counter = 0  # Auto-incrementing order ID

# User states
user_state = {}

# Available car classes
CAR_CLASSES = ['Эконом', 'Комфорт', 'Премиум']


def get_user_by_chat_id(chat_id):
    return next((u for u in users_db if u.get('chat_id') == chat_id), None)


def get_pending_orders():
    return [o for o in orders_db if o.get('status') == 'ожидание']


@bot.message_handler(commands=['start'])
def start_command(message):
    markup = types.ReplyKeyboardMarkup(row_width=2)
    markup.add(types.KeyboardButton('Пассажир'), types.KeyboardButton('Водитель'))
    bot.send_message(message.chat.id, "Выберите роль: Пассажир или Водитель", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text in ['Пассажир', 'Водитель'])
def role_choice(message):
    user_state[message.chat.id] = {'role': message.text, 'chat_id': message.chat.id}
    ask_full_name(message)


def ask_full_name(message):
    bot.send_message(message.chat.id, "Введите ваше полное имя (ФИО):")
    bot.register_next_step_handler(message, process_full_name)


def process_full_name(message):
    chat_id = message.chat.id
    user_state[chat_id]['full_name'] = message.text

    if user_state[chat_id]['role'] == 'Пассажир':
        ask_passenger_phone(message)
    else:
        ask_driver_phone_number(message)


# --- Passenger registration ---

def ask_passenger_phone(message):
    bot.send_message(message.chat.id, "Введите ваш номер телефона:")
    bot.register_next_step_handler(message, process_passenger_phone)


def process_passenger_phone(message):
    chat_id = message.chat.id
    user_state[chat_id]['phone_number'] = message.text
    users_db.append(user_state[chat_id].copy())
    show_passenger_menu(message)


# --- Driver registration ---

def ask_driver_phone_number(message):
    bot.send_message(message.chat.id, "Введите ваш номер телефона:")
    bot.register_next_step_handler(message, process_driver_phone_number)


def process_driver_phone_number(message):
    chat_id = message.chat.id
    user_state[chat_id]['phone_number'] = message.text
    ask_car_brand(message)


def ask_car_brand(message):
    bot.send_message(message.chat.id, "Введите марку вашего автомобиля:")
    bot.register_next_step_handler(message, process_car_brand)


def process_car_brand(message):
    chat_id = message.chat.id
    user_state[chat_id]['car_brand'] = message.text
    ask_car_number(message)


def ask_car_number(message):
    bot.send_message(message.chat.id, "Введите госномер вашего автомобиля:")
    bot.register_next_step_handler(message, process_car_number)


def process_car_number(message):
    chat_id = message.chat.id
    user_state[chat_id]['car_number'] = message.text
    ask_car_class(message)


def ask_car_class(message):
    markup = types.ReplyKeyboardMarkup(row_width=3)
    for cls in CAR_CLASSES:
        markup.add(types.KeyboardButton(cls))
    bot.send_message(message.chat.id, "Выберите класс вашего автомобиля:", reply_markup=markup)
    bot.register_next_step_handler(message, process_car_class)


def process_car_class(message):
    chat_id = message.chat.id
    if message.text not in CAR_CLASSES:
        bot.send_message(chat_id, "Пожалуйста, выберите класс из предложенных вариантов.")
        ask_car_class(message)
        return
    user_state[chat_id]['car_class'] = message.text
    users_db.append(user_state[chat_id].copy())
    show_driver_menu(message)


# --- Menus ---

def show_passenger_menu(message):
    markup = types.ReplyKeyboardMarkup(row_width=1)
    markup.add(types.KeyboardButton('Заказать такси'))
    bot.send_message(message.chat.id, "Добро пожаловать в меню пассажира!", reply_markup=markup)


def show_driver_menu(message):
    markup = types.ReplyKeyboardMarkup(row_width=1)
    markup.add(types.KeyboardButton('Доступные заказы'))
    bot.send_message(message.chat.id, "Добро пожаловать в меню водителя!", reply_markup=markup)


# --- Passenger: create order ---

@bot.message_handler(func=lambda message: message.text == 'Заказать такси')
def order_taxi(message):
    bot.send_message(message.chat.id, "Введите адрес подачи:")
    bot.register_next_step_handler(message, process_pickup_location)


def process_pickup_location(message):
    user_state[message.chat.id]['pickup'] = message.text
    bot.send_message(message.chat.id, "Введите адрес назначения:")
    bot.register_next_step_handler(message, process_dropoff_location)


def process_dropoff_location(message):
    global _order_id_counter
    chat_id = message.chat.id
    pickup = user_state[chat_id].get('pickup', '')
    dropoff = message.text

    _order_id_counter += 1
    order = {
        'id': _order_id_counter,
        'passenger_chat_id': chat_id,
        'pickup': pickup,
        'dropoff': dropoff,
        'status': 'ожидание',
    }
    orders_db.append(order)

    bot.send_message(chat_id,
                     f"Заказ создан!\n📍 Откуда: {pickup}\n🏁 Куда: {dropoff}\nОжидайте водителя...")
    notify_drivers_about_order(order)


def notify_drivers_about_order(order):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "✅ Принять заказ",
        callback_data=f"accept_{order['id']}"
    ))
    text = (f"🚖 Новый заказ #{order['id']}!\n"
            f"📍 Откуда: {order['pickup']}\n"
            f"🏁 Куда: {order['dropoff']}")

    for user in users_db:
        if user.get('role') == 'Водитель':
            driver_chat_id = user.get('chat_id')
            if driver_chat_id:
                try:
                    bot.send_message(driver_chat_id, text, reply_markup=markup)
                except Exception:
                    pass


# --- Driver: view and accept orders ---

@bot.message_handler(func=lambda message: message.text == 'Доступные заказы')
def show_available_orders(message):
    pending = get_pending_orders()
    if not pending:
        bot.send_message(message.chat.id, "Нет доступных заказов.")
        return

    markup = types.InlineKeyboardMarkup()
    for order in pending:
        markup.add(types.InlineKeyboardButton(
            f"Заказ #{order['id']}: {order['pickup']} → {order['dropoff']}",
            callback_data=f"accept_{order['id']}"
        ))
    bot.send_message(message.chat.id, "Доступные заказы:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('accept_'))
def accept_order(call):
    order_id = int(call.data.split('_')[1])
    order = next((o for o in orders_db if o['id'] == order_id), None)

    if order is None or order['status'] != 'ожидание':
        bot.answer_callback_query(call.id, "Заказ уже принят другим водителем.")
        return

    # Mark as accepted immediately to prevent race conditions
    order['status'] = 'принят'
    order['driver_chat_id'] = call.message.chat.id

    bot.answer_callback_query(call.id, "Вы приняли заказ!")

    # Ask driver for ETA
    markup = types.ReplyKeyboardMarkup(row_width=5)
    row1 = [types.KeyboardButton(str(i)) for i in range(1, 6)]
    row2 = [types.KeyboardButton(str(i)) for i in range(6, 11)]
    markup.add(*row1)
    markup.add(*row2)

    driver_chat_id = call.message.chat.id
    user_state.setdefault(driver_chat_id, {})
    user_state[driver_chat_id]['waiting_eta'] = True
    user_state[driver_chat_id]['current_order_id'] = order_id

    bot.send_message(driver_chat_id,
                     "Заказ принят! Через сколько минут вы прибудете? (от 1 до 10):",
                     reply_markup=markup)


# --- Driver: ETA response ---

@bot.message_handler(func=lambda message: (
    user_state.get(message.chat.id, {}).get('waiting_eta') and
    message.text.isdigit()
))
def process_eta(message):
    eta = int(message.text)
    chat_id = message.chat.id

    if eta < 1 or eta > 10:
        bot.send_message(chat_id, "Пожалуйста, укажите время от 1 до 10 минут.")
        return

    user_state[chat_id]['waiting_eta'] = False
    order_id = user_state[chat_id].get('current_order_id')
    order = next((o for o in orders_db if o['id'] == order_id), None)

    if order:
        order['eta'] = eta

        driver = get_user_by_chat_id(chat_id)
        driver_info = ""
        if driver:
            driver_info = (
                f"\n🚗 Водитель: {driver.get('full_name', 'Неизвестно')}"
                f"\n🚙 Марка: {driver.get('car_brand', '')}"
                f"\n🔢 Номер: {driver.get('car_number', '')}"
                f"\n⭐ Класс: {driver.get('car_class', '')}"
            )

        passenger_chat_id = order.get('passenger_chat_id')
        if passenger_chat_id:
            bot.send_message(passenger_chat_id,
                             f"✅ Ваш заказ принят!{driver_info}\n⏱️ Водитель прибудет примерно через {eta} мин.")

    bot.send_message(chat_id, f"Отлично! Пассажир уведомлён о вашем прибытии через {eta} мин.")
    show_driver_menu(message)


bot.polling()