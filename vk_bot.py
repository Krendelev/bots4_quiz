import logging
import random
import os

import redis
import vk_api as vk
from dotenv import load_dotenv
from vk_api.keyboard import VkKeyboard
from vk_api.longpoll import VkLongPoll, VkEventType

from utils import parse_text

QUIZ_FILES = "quiz-questions.zip"
quiz = parse_text(QUIZ_FILES)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def set_keyboard(keys=[]):
    keyboard = VkKeyboard()
    for i, row in enumerate(keys):
        for key in row:
            keyboard.add_button(key)
        if i != len(keys) - 1:
            keyboard.add_line()
    return keyboard


def start(event, vk_api):
    custom_keyboard = [["Новый вопрос", "Сдаюсь"], ["Мой результат"]]
    keyboard = set_keyboard(custom_keyboard)

    vk_api.messages.send(
        user_id=event.user_id,
        message="Привет! Я бот для викторины",
        keyboard=keyboard.get_keyboard(),
        random_id=random.getrandbits(32),
    )


def get_questions():
    global quiz
    if not quiz:
        quiz = parse_text(QUIZ_FILES)
    return list(quiz)


def handle_new_question_request(event, vk_api, db):
    question = random.choice(get_questions())
    db.set(event.user_id, question)
    vk_api.messages.send(
        user_id=event.user_id,
        message=question,
        random_id=random.getrandbits(32),
    )


def handle_solution_attempt(event, vk_api, db):
    question = db.get(event.user_id).decode()
    answer = quiz[question]

    if event.text.lower() in answer.lower():
        vk_api.messages.send(
            user_id=event.user_id,
            message="Правильно! Поздравляю! Для следующего вопроса нажми «Новый вопрос»",
            random_id=random.getrandbits(32),
        )
        quiz.pop(question)
        return

    vk_api.messages.send(
        user_id=event.user_id,
        message="Неправильно… Попробуешь ещё раз?",
        random_id=random.getrandbits(32),
    )


def give_up(event, vk_api, db):
    question = db.get(event.user_id).decode()
    answer = quiz[question]
    vk_api.messages.send(
        user_id=event.user_id,
        message=f"Правильный ответ: {answer}",
        random_id=random.getrandbits(32),
    )
    quiz.pop(question)
    return handle_new_question_request(event, vk_api, db)


def cancel(event, vk_api):
    keyboard = set_keyboard()
    vk_api.messages.send(
        user_id=event.user_id,
        message="Всего хорошего! Заходи ещё.",
        keyboard=keyboard.get_empty_keyboard(),
        random_id=random.getrandbits(32),
    )


def main():
    load_dotenv()

    db = redis.Redis(
        host=os.environ["REDIS_ENDPOINT"],
        port=os.environ["REDIS_PORT"],
        password=os.environ["REDIS_PASSWORD"],
    )

    vk_session = vk.VkApi(token=os.getenv("VK_ACCESS_TOKEN"))
    vk_api = vk_session.get_api()
    longpoll = VkLongPoll(vk_session)

    try:
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                if event.text in {"/start", "Начать"}:
                    start(event, vk_api)
                elif event.text == "/cancel":
                    cancel(event, vk_api)
                elif event.text == "Новый вопрос":
                    handle_new_question_request(event, vk_api, db)
                elif event.text == "Сдаюсь":
                    give_up(event, vk_api, db)
                else:
                    handle_solution_attempt(event, vk_api, db)
    except Exception as err:
        logger.error(err)


if __name__ == "__main__":
    main()