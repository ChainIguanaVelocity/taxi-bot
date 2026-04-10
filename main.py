import telebot
from telebot import types

# Initialize the bot with your token
API_TOKEN = 'YOUR_API_TOKEN'
bot = telebot.TeleBot(API_TOKEN)

# Database simulation
users_db = []  # In a real application, this would be a database

# User states
user_state = {}

# Role-based registries
drivers = {}     # chat_id -> driver data dict
passengers = {}  # chat_id -> passenger data dict

# Orders storage
pending_orders = {}  # order_id -> order dict
order_counter = 0


@bot.message_handler(commands=['start'])
def start_command(message):
    markup = types.ReplyKeyboardMarkup(row_width=2)
    passenger_button = types.KeyboardButton('Пассажир')
    driver_button = types.KeyboardButton('Водитель')
    markup.add(passenger_button, driver_button)
    bot.send_message(message.chat.id, "Выберите роль: Пассажир или Водитель", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text in ['Пассажир', 'Водитель'])
def role_choice(message):
    role = 'Passenger' if message.text == 'Пассажир' else 'Driver'
    user_state[message.chat.id] = {'role': role}
    ask_full_name(message)


def ask_full_name(message):
    bot.send_message(message.chat.id, "Введите ваше полное имя (ФИО):")
    bot.register_next_step_handler(message, process_full_name)


def process_full_name(message):
    full_name = message.text
    chat_id = message.chat.id
    user_state[chat_id]['full_name'] = full_name
    ask_phone_number(message)


def ask_phone_number(message):
    bot.send_message(message.chat.id, "Введите ваш номер телефона:")
    bot.register_next_step_handler(message, process_phone_number)


def process_phone_number(message):
    phone_number = message.text
    chat_id = message.chat.id
    user_state[chat_id]['phone_number'] = phone_number
    role = user_state[chat_id]['role']

    if role == 'Passenger':
        passengers[chat_id] = user_state[chat_id].copy()
        users_db.append(passengers[chat_id])
        show_passenger_menu(message)
    elif role == 'Driver':
        ask_car_brand(message)


def ask_car_brand(message):
    bot.send_message(message.chat.id, "Введите марку вашего автомобиля:")
    bot.register_next_step_handler(message, process_car_brand)


def process_car_brand(message):
    car_brand = message.text
    chat_id = message.chat.id
    user_state[chat_id]['car_brand'] = car_brand
    ask_car_number(message)


def ask_car_number(message):
    bot.send_message(message.chat.id, "Введите госномер вашего автомобиля:")
    bot.register_next_step_handler(message, process_car_number)


def process_car_number(message):
    car_number = message.text
    chat_id = message.chat.id
    user_state[chat_id]['car_number'] = car_number
    drivers[chat_id] = user_state[chat_id].copy()
    users_db.append(drivers[chat_id])
    show_driver_menu(message)


def show_passenger_menu(message):
    markup = types.ReplyKeyboardMarkup(row_width=1)
    order_button = types.KeyboardButton('Заказать такси')
    markup.add(order_button)
    bot.send_message(message.chat.id, "Добро пожаловать в меню пассажира!", reply_markup=markup)


def show_driver_menu(message):
    markup = types.ReplyKeyboardMarkup(row_width=1)
    available_button = types.KeyboardButton('Доступные заказы')
    markup.add(available_button)
    bot.send_message(message.chat.id, "Добро пожаловать в меню водителя!", reply_markup=markup)


@bot.message_handler(func=lambda message: message.text == 'Заказать такси')
def order_taxi(message):
    bot.send_message(message.chat.id, "Введите адрес подачи:")
    bot.register_next_step_handler(message, process_pickup)


def process_pickup(message):
    chat_id = message.chat.id
    user_state[chat_id]['pickup'] = message.text
    bot.send_message(chat_id, "Введите адрес назначения:")
    bot.register_next_step_handler(message, process_dropoff)


def process_dropoff(message):
    global order_counter
    chat_id = message.chat.id
    pickup = user_state[chat_id].get('pickup', '')
    dropoff = message.text

    order_counter += 1
    order_id = order_counter

    order = {
        'id': order_id,
        'passenger_chat_id': chat_id,
        'pickup': pickup,
        'dropoff': dropoff,
        'status': 'pending',
        'driver_chat_id': None,
        'eta_minutes': None,
    }
    pending_orders[order_id] = order

    bot.send_message(
        chat_id,
        f"✅ Ваш заказ #{order_id} создан!\n"
        f"📍 Откуда: {pickup}\n"
        f"🎯 Куда: {dropoff}\n"
        f"Ожидайте водителя..."
    )

    # Notify all registered drivers about the new order
    for driver_chat_id in drivers:
        markup = types.InlineKeyboardMarkup()
        accept_button = types.InlineKeyboardButton(
            f"Принять заказ #{order_id}",
            callback_data=f"accept_{order_id}"
        )
        markup.add(accept_button)
        bot.send_message(
            driver_chat_id,
            f"🚕 Новый заказ #{order_id}!\n"
            f"📍 Откуда: {pickup}\n"
            f"🎯 Куда: {dropoff}",
            reply_markup=markup
        )


@bot.message_handler(func=lambda message: message.text == 'Доступные заказы')
def show_available_orders(message):
    available = [o for o in pending_orders.values() if o['status'] == 'pending']
    if not available:
        bot.send_message(message.chat.id, "Нет доступных заказов.")
        return

    for order in available:
        markup = types.InlineKeyboardMarkup()
        accept_button = types.InlineKeyboardButton(
            f"Принять заказ #{order['id']}",
            callback_data=f"accept_{order['id']}"
        )
        markup.add(accept_button)
        bot.send_message(
            message.chat.id,
            f"🚕 Заказ #{order['id']}\n"
            f"📍 Откуда: {order['pickup']}\n"
            f"🎯 Куда: {order['dropoff']}",
            reply_markup=markup
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith('accept_'))
def accept_order(call):
    order_id = int(call.data.split('_')[1])
    driver_chat_id = call.message.chat.id

    if order_id not in pending_orders or pending_orders[order_id]['status'] != 'pending':
        bot.answer_callback_query(call.id, "Заказ уже принят другим водителем.")
        return

    order = pending_orders[order_id]
    order['status'] = 'accepted'
    order['driver_chat_id'] = driver_chat_id

    bot.answer_callback_query(call.id, "Вы приняли заказ!")

    # Ask driver for ETA
    markup = types.InlineKeyboardMarkup(row_width=5)
    eta_buttons = [
        types.InlineKeyboardButton(f"{i} мин", callback_data=f"eta_{order_id}_{i}")
        for i in range(1, 11)
    ]
    markup.add(*eta_buttons)
    bot.send_message(
        driver_chat_id,
        f"Вы приняли заказ #{order_id}!\nЧерез сколько минут вы прибудете?",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('eta_'))
def set_eta(call):
    parts = call.data.split('_')
    order_id = int(parts[1])
    eta_minutes = int(parts[2])
    driver_chat_id = call.message.chat.id

    if order_id not in pending_orders:
        bot.answer_callback_query(call.id, "Заказ не найден.")
        return

    order = pending_orders[order_id]
    order['eta_minutes'] = eta_minutes

    driver = drivers.get(driver_chat_id)
    if driver is None:
        bot.answer_callback_query(call.id, "Ошибка: водитель не найден.")
        return

    bot.answer_callback_query(call.id, f"Отлично! Вы указали {eta_minutes} мин.")
    bot.send_message(
        driver_chat_id,
        f"✅ Вы едете к пассажиру. Время прибытия: {eta_minutes} мин."
    )

    # Notify passenger
    passenger_chat_id = order['passenger_chat_id']
    bot.send_message(
        passenger_chat_id,
        f"🚕 Ваш заказ #{order_id} принят!\n"
        f"Водитель: {driver.get('full_name', '')}\n"
        f"Автомобиль: {driver.get('car_brand', '')} ({driver.get('car_number', '')})\n"
        f"⏱️ Время прибытия: {eta_minutes} мин."
    )

    order['status'] = 'completed'


bot.polling()