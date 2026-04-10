import telebot
from telebot import types

# Initialize the bot with your token
API_TOKEN = 'YOUR_API_TOKEN'
bot = telebot.TeleBot(API_TOKEN)

# Database simulation
users_db = []  # In a real application, this would be a database

# User states
user_state = {}

@bot.message_handler(commands=['start'])
def start_command(message):
    markup = types.ReplyKeyboardMarkup(row_width=2)
    passenger_button = types.KeyboardButton('Passenger')
    driver_button = types.KeyboardButton('Driver')
    markup.add(passenger_button, driver_button)
    bot.send_message(message.chat.id, "Choose role: Passenger or Driver", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ['Passenger', 'Driver'])
def role_choice(message):
    user_state[message.chat.id] = {'role': message.text}
    if message.text == 'Passenger':
        ask_full_name(message)
    else:
        ask_driver_details(message)

@bot.message_handler(func=lambda message: message.chat.id in user_state)
def ask_full_name(message):
    bot.send_message(message.chat.id, "Please enter your Full Name (ФИО):")
    bot.register_next_step_handler(message, process_full_name)

def process_full_name(message):
    full_name = message.text
    chat_id = message.chat.id
    role = user_state[chat_id]['role']
    user_data = {'full_name': full_name, 'phone_number': '', 'role': role}

    if role == 'Passenger':
        user_data['phone_number'] = ask_phone_number(message)
        users_db.append(user_data)
        show_passenger_menu(message)
    elif role == 'Driver':
        user_data['car_brand'] = ''
        user_data['car_number'] = ''
        ask_driver_phone_number(message)

# Further implementation of Driver registration and menus here

@bot.message_handler(func=lambda message: message.text.isdigit())
def ask_driver_phone_number(message):
    bot.send_message(message.chat.id, "Please enter your Phone Number:")
    bot.register_next_step_handler(message, process_driver_phone_number)

def process_driver_phone_number(message):
    phone_number = message.text
    chat_id = message.chat.id
    user_state[chat_id]['phone_number'] = phone_number
    ask_car_brand(message)

def ask_car_brand(message):
    bot.send_message(message.chat.id, "Please enter your Car Brand (марка):")
    bot.register_next_step_handler(message, process_car_brand)

def process_car_brand(message):
    car_brand = message.text
    chat_id = message.chat.id
    user_state[chat_id]['car_brand'] = car_brand
    ask_car_number(message)

def ask_car_number(message):
    bot.send_message(message.chat.id, "Please enter your Car Number (госномер):")
    bot.register_next_step_handler(message, process_car_number)

def process_car_number(message):
    car_number = message.text
    chat_id = message.chat.id
    user_data = user_state[chat_id]
    user_data['car_number'] = car_number
    users_db.append(user_data)
    show_driver_menu(message)

def show_passenger_menu(message):
    bot.send_message(message.chat.id, "Welcome to the Passenger menu!")

def show_driver_menu(message):
    bot.send_message(message.chat.id, "Welcome to the Driver menu!")

bot.polling()