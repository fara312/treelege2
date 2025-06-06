import os
import random
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    ContextTypes, ConversationHandler, CallbackQueryHandler
)

CHOOSING_TEST, ANSWERING = range(2)

TESTS = {
    'Дана': 'dana.txt',
    'Шынтасов': 'shintasov.txt'
}

loaded_tests = {}
allowed_users_file = 'allowed_users.txt'
ADMIN_ID = 7366365871  # Замените на свой ID

# Загрузка разрешенных пользователей
def load_allowed_users():
    if not os.path.exists(allowed_users_file):
        return set()
    with open(allowed_users_file, 'r') as f:
        return set(map(int, f.read().splitlines()))

# Сохранение нового пользователя
def save_allowed_user(user_id):
    with open(allowed_users_file, 'a') as f:
        f.write(f"{user_id}\n")

# Проверка доступа
def is_allowed(user_id):
    return user_id in load_allowed_users()

def load_questions(filename):
    with open(filename, encoding='utf-8') as f:
        content = f.read().strip()
    blocks = content.split('\n\n')
    questions = []
    for block in blocks:
        lines = block.strip().split('\n')
        question_text = lines[0]
        options = []
        correct_index = None
        for i, line in enumerate(lines[1:]):
            if line.startswith('+'):
                options.append(line[2:].strip())
                correct_index = i
            elif line.startswith('-'):
                options.append(line[2:].strip())
        questions.append({'question': question_text, 'options': options, 'correct': correct_index})
    return questions

def shuffle_options(question):
    options = question['options']
    correct_idx = question['correct']
    paired = list(enumerate(options))
    random.shuffle(paired)
    for new_idx, (old_idx, opt) in enumerate(paired):
        if old_idx == correct_idx:
            question['correct'] = new_idx
            break
    question['options'] = [opt for _, opt in paired]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        # отправка админу кнопок
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Разрешить", callback_data=f"allow:{user_id}"),
             InlineKeyboardButton("❌ Отклонить", callback_data=f"deny:{user_id}")]
        ])
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"❗ Пользователь {update.effective_user.full_name} ({user_id}) хочет получить доступ.",
            reply_markup=keyboard
        )
        await update.message.reply_text("⏳ Запрос отправлен администратору. Подождите разрешения.")
        return ConversationHandler.END

    keyboard = [[KeyboardButton(name)] for name in TESTS.keys()]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Привет! Выбери тест, который хочешь пройти:", reply_markup=reply_markup)
    return CHOOSING_TEST

async def handle_permission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    action, user_id_str = data.split(':')
    user_id = int(user_id_str)

    if action == 'allow':
        save_allowed_user(user_id)
        await context.bot.send_message(chat_id=user_id, text="✅ Вам разрешен доступ. Напишите /start.")
        await query.edit_message_text("Пользователю разрешен доступ.")
    elif action == 'deny':
        await context.bot.send_message(chat_id=user_id, text="❌ Вам отказано в доступе.")
        await query.edit_message_text("Пользователю отказано.")

    return ConversationHandler.END

async def choose_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    test_name = update.message.text
    if test_name not in TESTS:
        await update.message.reply_text("Пожалуйста, выбери тест из списка кнопок.")
        return CHOOSING_TEST

    if test_name not in loaded_tests:
        questions = load_questions(TESTS[test_name])
        random.shuffle(questions)
        for q in questions:
            shuffle_options(q)
        loaded_tests[test_name] = questions

    context.user_data['test_name'] = test_name
    context.user_data['current'] = 0
    await send_question(update, context)
    return ANSWERING

async def send_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    test_name = context.user_data.get('test_name')
    current = context.user_data.get('current', 0)
    questions = loaded_tests[test_name]
    q = questions[current]

    text = f"Тест: {test_name}\nВопрос {current + 1}:\n{q['question']}\n\n"
    for i, opt in enumerate(q['options'], 1):
        text += f"{i}) {opt}\n"
    await update.message.reply_text(text)

async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    test_name = context.user_data.get('test_name')
    if not test_name or test_name not in loaded_tests:
        await update.message.reply_text("Напишите /start и выберите тест заново.")
        return ConversationHandler.END

    questions = loaded_tests[test_name]
    current = context.user_data.get('current', 0)
    q = questions[current]

    try:
        choice = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Пожалуйста, отправьте номер варианта (цифру).")
        return ANSWERING

    if choice < 1 or choice > len(q['options']):
        await update.message.reply_text("Номер варианта вне диапазона, попробуйте снова.")
        return ANSWERING

    if choice - 1 == q['correct']:
        await update.message.reply_text("✅ Правильно!")
    else:
        correct_answer = q['options'][q['correct']]
        await update.message.reply_text(f"❌ Неправильно. Правильный ответ: {correct_answer}")

    current += 1
    context.user_data['current'] = current

    if current >= len(questions):
        await update.message.reply_text(f"Тест \"{test_name}\" завершен. Спасибо за участие!")
        return ConversationHandler.END
    else:
        await send_question(update, context)
        return ANSWERING

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Тест отменен. Напишите /start чтобы начать заново.")
    return ConversationHandler.END

    def main():
        TOKEN = "7837078905:AAHFan32TZaH14AzZ_JCHTHmhUg3IUHjY6E"
        application = ApplicationBuilder().token(TOKEN).build()

        application.add_handler(CommandHandler("start", start))

        # Запуск бота (блокирующий вызов)
        application.run_polling()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING_TEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_test)],
            ANSWERING: [MessageHandler(filters.TEXT & ~filters.COMMAND, answer)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_permission))

    application.run_polling()

if __name__ == '__main__':
    main()
