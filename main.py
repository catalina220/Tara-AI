import telebot
import random
import time
import openai
from telebot import types
import re

#Токены
TOKEN = 'YOUR-BOT-KEY'
openai.api_key = 'YOUR-SECRET-KEY'
# Создаем бота
bot = telebot.TeleBot(TOKEN)

# Данные о запросах
last_request_time = time.time()
requests_made = 0

# Основная встроенная клавиатура
markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)

tells = ['Гадание по книге перемен', 'Гадание на картах таро', 'Расчет матрицы судьбы']
for tell in tells:
    button = types.KeyboardButton(text=tell)
    markup.add(button)

# Функция для отправки сообщения без кнопок
def send_message(message, text):
    bot.send_message(message.chat.id, text)

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    send_message(message, 'Здравствуй! Как тебя зовут?')
    bot.register_next_step_handler(message, start_dialog)

#Начало диалога
def start_dialog(message):
    global username
    username = message.text
    bot.send_message(message.chat.id, f"Приятно познакомиться!\nВыбирай, на чем будем гадать", reply_markup=markup)

#функция запроса к нейросети
def safe_openai_request(prompt):
    global last_request_time, requests_made

    # Проверяем, сколько времени прошло с момента последнего запроса
    elapsed_time = time.time() - last_request_time
    if elapsed_time < 60:  # Проверяем лимит RPM (3 запроса в минуту)
        time.sleep(60 - elapsed_time)  # Если лимит превышен, ждем до конца минуты

    # Проверяем количество запросов в день (RPD)
    if requests_made >= 200:
        raise Exception("Превышен лимит запросов в день")

    # Выполняем запрос к OpenAI API
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": prompt}]
    )

    # Обновляем время последнего запроса и количество запросов
    last_request_time = time.time()
    requests_made += 1

    return response
    
# Расчет ответов:
# Карты таро
def tarot_answer(message):
    if not message.text:
        if_incorrect(message, 'tarot')
        return

    x = random.randint(0, 21)

    with open('meanings.txt', 'r') as file:
        meanings = file.readlines()
        meaning = meanings[x]

    # Отправка вопроса и значения карты в GPT
    prompt = f"У меня вопрос: {message.text}\nзначение моей карты таро: {meaning}\n как это интерпретировать?"

    try:
        # Выполняем безопасный запрос к OpenAI API
        response = safe_openai_request(prompt)
    except Exception as e:
        send_message(message, f"Ошибка при выполнении запроса: {str(e)}")
        return

    # Получение сгенерированного ответа
    generated_text = response.choices[0].message['content']

    # Отправка сгенерированного ответа пользователю
    bot.send_photo(message.chat.id, photo=open(f"card{x}.png", "rb"))
    send_message(message, f"Ответ от карт: {meaning}\n")
    bot.send_message(message.chat.id, 'Для начала нового гадания выбери, на чем будем гадать!', reply_markup=markup)


# Если пользователь ввел вопрос в некорректном формате
def if_incorrect(message, tell):
    if tell == 'matrix':
        send_message(message, 'Не могу расшифровать дату :( попробуйте еще раз в формате ДД.ММ.ГГГГ (число, месяц и год рождения)')
        bot.register_next_step_handler(message, matrix_answer)

    if tell == 'tarot':
        send_message(message, 'Не могу погадать на этот вопрос :( попробуй ввести его текстом')
        bot.register_next_step_handler(message, tarot_answer)

    if tell == 'book of changes':
        send_message(message, 'Не могу погадать на этот вопрос :( попробуй ввести его текстом')
        bot.register_next_step_handler(message, book_of_changes_answer)

# Книга перемен
def book_of_changes_answer(message):
    global user_context_question
    if not message.text:
        if_incorrect(message, 'book of changes')
        return

    user_context_question = message.text
    markup = types.InlineKeyboardMarkup()
    button = types.InlineKeyboardButton(text="Бросить жребий", callback_data="throw_coin")
    markup.add(button)
    bot.send_message(message.chat.id, "Для получения ответа брось жребий", reply_markup=markup)

# Матрица судьбы
def matrix_answer(message):
    global user_portret
    global user_talant
    global user_finance
    global user_carma

    pattern = r'^\d{2}\.\d{2}\.\d{4}$'

    if not message.text or not re.match(pattern, message.text):
        if_incorrect(message, 'matrix')
        return

    date = message.text
    with open('matrix.txt', 'rb') as file:
        arcans = file.read().decode('utf-8')
        arcans = arcans.split('\n')

    day, mounth, year = [int(i) for i in date.split('.')]
    talant = arcans[mounth - 1]
    if day <= 22:
        day_index = day - 1
    else:
        day_index = day - 23
    portret = arcans[day_index]
    if sum([int(i) for i in list(str(year))]) <= 22:
        mat_carma_index = sum([int(i) for i in list(str(year))]) - 1
    else:
        mat_carma_index = sum([int(i) for i in list(str(year))]) - 23
    mat_carma = arcans[mat_carma_index]
    carma_index = sum([int(i) for i in list(str(year))]) + day + mounth
    while carma_index > 22:
        carma_index = sum([int(i) for i in list(str(carma_index))])
    carma = arcans[carma_index]

    user_portret = portret
    user_talant = talant
    user_finance = mat_carma
    user_carma = carma

    main_answers = f'''Портрет личности в {day_index + 1}-ом аркане: {portret}
        Талант в {mounth}-ом аркане: {talant}
        Материальная карма (финансы) в {mat_carma_index + 1}-ом аркане: {mat_carma}
        Кармический хвост в {carma_index + 1}-ом аркане: {carma}'''

    matrix_markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)

    tells = ['Начать новое гадание', 'Расшифровать значения']
    for tell in tells:
        button = types.KeyboardButton(text=tell)
        matrix_markup.add(button)

    bot.send_message(message.chat.id, main_answers, reply_markup=matrix_markup)

#Блок для расшифровки значений и советов с помощью нейросети
@bot.message_handler(func=lambda message: message.text in ['Расшифровать значения'])
def unpacking(message):
    unpack_markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)

    tells = ['Портрет', 'Талант', 'Финансы', 'Кармический хвост', 'Начать новое гадание']
    for tell in tells:
        button = types.KeyboardButton(text=tell)
        unpack_markup.add(button)

    bot.send_message(message.chat.id, 'Выбери, что хочешь расшифровать', reply_markup=unpack_markup)

@bot.message_handler(func=lambda message: message.text in ['Портрет', 'Талант', 'Финансы', 'Кармический хвост'])
def one_unpack(message):
    new_unpack_markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)

    tells = ['Портрет', 'Талант', 'Финансы', 'Кармический хвост', 'Начать новое гадание']
    for tell in tells:
        button = types.KeyboardButton(text=tell)
        new_unpack_markup.add(button)

    user_context_matrix = ''

    if message.text == 'Портрет':
        user_contex_matrix = user_portret
    if message.text == 'Талант':
        user_contex_matrix = user_talant
    if message.text == 'Финансы':
        user_contex_matrix = user_finance
    if message.text == 'Кармический хвост':
        user_contex_matrix = user_carma

    #расшифровка чата gpt
    prompt = f"В матрице судьбы на {message.text}\nвыпало значение {user_context_matrix}\n как это интерпретировать?"

    try:
        # Выполняем безопасный запрос к OpenAI API
        response = safe_openai_request(prompt)
    except Exception as e:
        send_message(message, f"Ошибка при выполнении запроса: {str(e)}")
        return

    # Получение сгенерированного ответа
    generated_text = response.choices[0].message['content']
    send_message(message, f'Расшифровка: {generated_text}')

    bot.send_message(message.chat.id, 'Выбери, что хочешь расшифровать', reply_markup=new_unpack_markup)


@bot.message_handler(func=lambda message: message.text == 'Получить подробный совет')
def tell_unpack(message):
    new_unpack_markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)

    tells = ['Начать новое гадание']
    for tell in tells:
        button = types.KeyboardButton(text=tell)
        new_unpack_markup.add(button)

    prompt = f"На такой вопрос{user_context_question}\nвыпал такой совет{user_context_tell}\n как это интерпретировать?"

    try:
        # Выполняем безопасный запрос к OpenAI API
        response = safe_openai_request(prompt)
    except Exception as e:
        send_message(message, f"Ошибка при выполнении запроса: {str(e)}")
        return

    # Получение сгенерированного ответа
    generated_text = response.choices[0].message['content']
    send_message(message, f'Подробный совет: {generated_text}')

    bot.send_message(message.chat.id, 'Для начала нового гадания выбери, на чем будем гадать!', reply_markup=markup)

# Обработка команд из встроенной клавиатуры
# Новое гадание
@bot.message_handler(func=lambda message: message.text == 'Начать новое гадание')
def begin_new_tell(message):
    bot.send_message(message.chat.id, 'Для начала нового гадания выбери, на чем будем гадать!', reply_markup=markup)

# Книга перемен
@bot.message_handler(func=lambda message: message.text == 'Гадание по книге перемен')
def begin_book_of_changes_divination(message):
    send_message(message, f'{username}, узнай совет от Книги перемен!\nОпиши мне ситуацию и свой вопрос, а я тебе погадаю')
    bot.register_next_step_handler(message, book_of_changes_answer)

# Карты таро
@bot.message_handler(func=lambda message: message.text == 'Гадание на картах таро')
def begin_tarot_divination(message):
    send_message(message, f'{username}, ты можешь задать любой свой вопрос картам таро!\nОпиши мне ситуацию и свой вопрос, а я тебе погадаю')
    bot.register_next_step_handler(message, tarot_answer)

# Матрица судьбы
@bot.message_handler(func=lambda message: message.text == 'Расчет матрицы судьбы')
def begin_matrix_divination(message):
    send_message(message, f'{username}, напиши свою дату рождения в формате ДД.ММ.ГГГГ, а я расчитаю твои главные арканы!')
    bot.register_next_step_handler(message, matrix_answer)

# Неожиданное сообщение
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.send_message(message.chat.id, 'Для начала нового гадания выбери, на чем будем гадать!', reply_markup=markup)

#Обработка inline команд
@bot.callback_query_handler(func=lambda call: True)
def inline_keyboard_handler(call):
    global user_context_tell
    #Механизм гадания по Книге Перемен
    if call.data == "throw_coin":

        bot.send_message(call.message.chat.id, "Генерация номера гексаграммы:")

        time.sleep(1)

        gex = ''
        gex_elements = ['!', '|']

        for i in range(6):
            random_ch = random.randint(0, 1)
            time.sleep(0.3)
            gex += gex_elements[random_ch]
            bot.edit_message_text(f'Генерация номера гексаграммы: {gex}', call.message.chat.id, call.message.message_id + 1)

        number = int(''.join(['0' if i == '!' else '1' for i in gex]), 2)

        image_path = f'image{number + 1}.jpeg'

        with open(f"{image_path}", 'rb') as photo:
            time.sleep(1)
            bot.send_photo(call.message.chat.id, photo)

        with open('predicts.txt', 'rb') as file:
            text = file.read().decode('utf-8')
            predict = text.split('\n')[number]


        book_of_cahnges_markup = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)

        tells = ['Начать новое гадание', 'Получить подробный совет']
        for tell in tells:
            button = types.KeyboardButton(text=tell)
            book_of_cahnges_markup.add(button)

        user_context_tell = predict

        bot.send_message(call.message.chat.id, f'Номер гексаграмы: {number + 1}\n"{predict}"\n', reply_markup=book_of_cahnges_markup)

# Запуск бота
bot.polling()
