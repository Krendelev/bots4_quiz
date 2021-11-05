import logging
import os
import random
from enum import Enum
from functools import partial

import redis
import telegram
from dotenv import load_dotenv
from telegram.ext import (
    CommandHandler,
    ConversationHandler,
    Filters,
    MessageHandler,
    Updater,
)

from utils import parse_text

QUIZ = "quiz-questions.zip"

State = Enum("State", "CHOOSING ATTEMPT")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)


def start(update, context):
    custom_keyboard = [["Новый вопрос", "Сдаюсь"], ["Мой результат"]]
    reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Привет! Я бот для викторины",
        reply_markup=reply_markup,
    )
    context.user_data["quiz"] = parse_text(QUIZ)
    return State.CHOOSING


def get_questions(context):
    if not context.user_data["quiz"]:
        context.user_data["quiz"] = parse_text(QUIZ)
    return list(context.user_data["quiz"])


def handle_new_question_request(update, context, db):
    question = random.choice(get_questions(context))
    db.set(update.effective_chat.id, question)
    update.message.reply_text(question)
    return State.ATTEMPT


def handle_solution_attempt(update, context, db):
    question = db.get(update.effective_chat.id).decode()
    answer = context.user_data["quiz"][question]

    if update.message.text.lower() in answer.lower():
        update.message.reply_text(
            "Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»"
        )
        context.user_data["quiz"].pop(question)
        return State.CHOOSING

    update.message.reply_text("Неправильно… Попробуешь ещё раз?")
    return State.CHOOSING


def give_up(update, context, db):
    question = db.get(update.effective_chat.id).decode()
    answer = context.user_data["quiz"][question]
    update.message.reply_text(f"Правильный ответ: {answer}")
    context.user_data["quiz"].pop(question)
    return handle_new_question_request(update, context, db)


def get_result(update, context):
    # TODO implement tally and final score calculation
    update.message.reply_text("Пока не работает")
    return State.CHOOSING


def cancel(update, context):
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Всего хорошего! Заходи ещё.",
        reply_markup=telegram.ReplyKeyboardRemove(),
    )


def error(update, context):
    logger.warning(f'Update "{update}" caused error "{context.error}"')


def unknown(update, context):
    update.message.reply_text("Sorry, I didn't understand that command.")


def main():
    load_dotenv()

    db = redis.Redis(
        host=os.environ["REDIS_ENDPOINT"],
        port=os.environ["REDIS_PORT"],
        password=os.environ["REDIS_PASSWORD"],
    )

    updater = Updater(os.environ["TELEGRAM_TOKEN"])
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            State.CHOOSING: [
                MessageHandler(
                    Filters.regex("^Новый вопрос$"),
                    partial(handle_new_question_request, db=db),
                ),
                MessageHandler(Filters.regex("^Сдаюсь$"), partial(give_up, db=db)),
                MessageHandler(Filters.regex("^Мой результат$"), get_result),
            ],
            State.ATTEMPT: [
                MessageHandler(
                    Filters.text & ~Filters.command,
                    partial(handle_solution_attempt, db=db),
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(MessageHandler(Filters.command, unknown))
    dispatcher.add_error_handler(error)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
