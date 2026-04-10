import datetime
import os
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

# Ratings storage
driver_ratings = {}    # driver_chat_id -> list of {stars, comment, timestamp, reviewer_chat_id, order_id}
passenger_ratings = {} # passenger_chat_id -> list of {stars, comment, timestamp, reviewer_chat_id, order_id}

# Admin settings
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
admin_authenticated = set()  # set of chat_ids that have authenticated as admin

# Completed orders tracking for commission calculations
completed_orders = []  # list of {order_id, driver_chat_id, passenger_chat_id, completed_at}
driver_commissions = {}  # driver_chat_id -> {paid: int, unpaid: int}
COMMISSION_PER_ORDER = 10  # rubles per completed order


def get_average_rating(ratings_dict, chat_id):
    """Returns (average, count) or (None, 0) if no ratings."""
    ratings = ratings_dict.get(chat_id, [])
    if not ratings:
        return None, 0
    avg = sum(r['stars'] for r in ratings) / len(ratings)
    return round(avg, 1), len(ratings)


def format_rating_text(ratings_dict, chat_id):
    avg, count = get_average_rating(ratings_dict, chat_id)
    if avg is None:
        return "нет оценок"
    stars_emoji = '⭐' * round(avg)
    return f"{stars_emoji} {avg} ({count} отз.)"


def make_star_rating_markup(callback_prefix, order_id, target_chat_id):
    markup = types.InlineKeyboardMarkup(row_width=5)
    buttons = [
        types.InlineKeyboardButton(
            '⭐' * i,
            callback_data=f"{callback_prefix}_{order_id}_{target_chat_id}_{i}"
        )
        for i in range(1, 6)
    ]
    markup.add(*buttons)
    return markup


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
        passenger_rating_text = format_rating_text(passenger_ratings, chat_id)
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
            f"🎯 Куда: {dropoff}\n"
            f"👤 Рейтинг пассажира: {passenger_rating_text}",
            reply_markup=markup
        )


@bot.message_handler(func=lambda message: message.text == 'Доступные заказы')
def show_available_orders(message):
    available = [o for o in pending_orders.values() if o['status'] == 'pending']
    if not available:
        bot.send_message(message.chat.id, "Нет доступных заказов.")
        return

    for order in available:
        passenger_rating_text = format_rating_text(passenger_ratings, order['passenger_chat_id'])
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
            f"🎯 Куда: {order['dropoff']}\n"
            f"👤 Рейтинг пассажира: {passenger_rating_text}",
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
    driver_rating_text = format_rating_text(driver_ratings, driver_chat_id)
    bot.send_message(
        passenger_chat_id,
        f"🚕 Ваш заказ #{order_id} принят!\n"
        f"Водитель: {driver.get('full_name', '')}\n"
        f"📞 Телефон водителя: {driver.get('phone_number', '')}\n"
        f"Автомобиль: {driver.get('car_brand', '')} ({driver.get('car_number', '')})\n"
        f"⭐ Рейтинг водителя: {driver_rating_text}\n"
        f"⏱️ Время прибытия: {eta_minutes} мин."
    )

    order['status'] = 'completed'

    # Track completed order for commission calculations
    completed_orders.append({
        'order_id': order_id,
        'driver_chat_id': driver_chat_id,
        'passenger_chat_id': order['passenger_chat_id'],
        'completed_at': datetime.datetime.now(),
    })
    driver_commissions.setdefault(driver_chat_id, {'paid': 0, 'unpaid': 0})
    driver_commissions[driver_chat_id]['unpaid'] += 1

    # Prompt driver to rate passenger
    markup = make_star_rating_markup('rate_passenger', order_id, passenger_chat_id)
    bot.send_message(
        driver_chat_id,
        "🏁 Поездка завершена! Оцените пассажира:",
        reply_markup=markup
    )

    # Prompt passenger to rate driver
    markup = make_star_rating_markup('rate_driver', order_id, driver_chat_id)
    bot.send_message(
        passenger_chat_id,
        "🏁 Ваша поездка завершена! Оцените водителя:",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('rate_driver_'))
def rate_driver_callback(call):
    parts = call.data.split('_')
    # callback_data: rate_driver_{order_id}_{driver_chat_id}_{stars}
    order_id = int(parts[2])
    driver_chat_id = int(parts[3])
    stars = int(parts[4])
    reviewer_chat_id = call.message.chat.id

    bot.answer_callback_query(call.id, f"Вы поставили {'⭐' * stars}!")

    user_state.setdefault(reviewer_chat_id, {})['pending_rating'] = {
        'type': 'driver',
        'target_id': driver_chat_id,
        'order_id': order_id,
        'stars': stars,
        'reviewer_id': reviewer_chat_id,
    }

    bot.send_message(
        reviewer_chat_id,
        f"Вы поставили {'⭐' * stars}!\nДобавьте комментарий или отправьте /skip:"
    )
    bot.register_next_step_handler(call.message, process_rating_comment)


@bot.callback_query_handler(func=lambda call: call.data.startswith('rate_passenger_'))
def rate_passenger_callback(call):
    parts = call.data.split('_')
    # callback_data: rate_passenger_{order_id}_{passenger_chat_id}_{stars}
    order_id = int(parts[2])
    passenger_chat_id = int(parts[3])
    stars = int(parts[4])
    reviewer_chat_id = call.message.chat.id

    bot.answer_callback_query(call.id, f"Вы поставили {'⭐' * stars}!")

    user_state.setdefault(reviewer_chat_id, {})['pending_rating'] = {
        'type': 'passenger',
        'target_id': passenger_chat_id,
        'order_id': order_id,
        'stars': stars,
        'reviewer_id': reviewer_chat_id,
    }

    bot.send_message(
        reviewer_chat_id,
        f"Вы поставили {'⭐' * stars}!\nДобавьте комментарий или отправьте /skip:"
    )
    bot.register_next_step_handler(call.message, process_rating_comment)


def process_rating_comment(message):
    chat_id = message.chat.id
    pending = user_state.get(chat_id, {}).get('pending_rating')
    if not pending:
        return

    comment = '' if message.text == '/skip' else message.text

    rating_entry = {
        'stars': pending['stars'],
        'comment': comment,
        'timestamp': datetime.datetime.now().isoformat(),
        'reviewer_chat_id': pending['reviewer_id'],
        'order_id': pending['order_id'],
    }

    target_id = pending['target_id']
    if pending['type'] == 'driver':
        driver_ratings.setdefault(target_id, []).append(rating_entry)
        bot.send_message(chat_id, "✅ Спасибо за оценку водителя!")
    else:
        passenger_ratings.setdefault(target_id, []).append(rating_entry)
        bot.send_message(chat_id, "✅ Спасибо за оценку пассажира!")

    user_state[chat_id].pop('pending_rating', None)


def _russian_month(dt):
    """Return 'Month YYYY' with Russian month name."""
    months = [
        'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
        'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь',
    ]
    return f"{months[dt.month - 1]} {dt.year}"


def show_admin_panel(chat_id):
    """Generate and send the admin panel report."""
    now = datetime.datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_users = len(drivers) + len(passengers)
    total_drivers = len(drivers)
    total_passengers = len(passengers)

    # Monthly orders per driver
    monthly_orders = {}  # driver_chat_id -> count
    for record in completed_orders:
        if record['completed_at'] >= month_start:
            dcid = record['driver_chat_id']
            monthly_orders[dcid] = monthly_orders.get(dcid, 0) + 1

    total_monthly_orders = sum(monthly_orders.values())
    total_revenue = total_monthly_orders * COMMISSION_PER_ORDER

    lines = [
        "🔐 *Админ-панель*",
        f"📅 Дата отчёта: {now.strftime('%d.%m.%Y %H:%M')}",
        "",
        "👥 *Статистика пользователей*",
        f"  Всего зарегистрировано: {total_users}",
        f"  🚕 Водителей: {total_drivers}",
        f"  🧍 Пассажиров: {total_passengers}",
        "",
        f"📊 *Финансовый отчёт за {_russian_month(now)}*",
        f"  Выполнено заказов: {total_monthly_orders}",
        f"  Общая выручка: {total_revenue} руб.",
        "",
        "💰 *Комиссии водителей (10 руб./заказ)*",
    ]

    if monthly_orders:
        for dcid, order_count in monthly_orders.items():
            driver = drivers.get(dcid, {})
            name = driver.get('full_name', f'ID {dcid}')
            commission = order_count * COMMISSION_PER_ORDER
            paid_orders = driver_commissions.get(dcid, {}).get('paid', 0)
            unpaid = (order_count - paid_orders) * COMMISSION_PER_ORDER
            lines.append(
                f"  • {name}: {order_count} зак. → {commission} руб. (не оплачено: {unpaid} руб.)"
            )
    else:
        lines.append("  Нет заказов в этом месяце.")

    bot.send_message(chat_id, "\n".join(lines), parse_mode='Markdown')


@bot.message_handler(commands=['admin'])
def admin_command(message):
    chat_id = message.chat.id
    if chat_id in admin_authenticated:
        show_admin_panel(chat_id)
    else:
        bot.send_message(chat_id, "🔐 Введите пароль администратора:")
        bot.register_next_step_handler(message, process_admin_password)


def process_admin_password(message):
    chat_id = message.chat.id
    if message.text == ADMIN_PASSWORD:
        admin_authenticated.add(chat_id)
        bot.send_message(chat_id, "✅ Авторизация успешна!")
        show_admin_panel(chat_id)
    else:
        bot.send_message(chat_id, "❌ Неверный пароль.")


bot.polling()