import random
import zipfile


def get_text(filename):
    arch = zipfile.ZipFile(filename)
    file = random.choice(arch.namelist())
    with arch.open(file) as qf:
        for line in qf:
            yield line.decode("KOI8-R")


def parse_text(filename):
    question = []
    quiz = {}
    q_found = a_found = False

    for line in get_text(filename):
        if line.startswith("Ответ"):
            q_found = False
            a_found = True
        elif a_found:
            quiz["".join(question)] = line.strip()
            a_found = False
            question.clear()
        elif line.startswith("Вопрос"):
            q_found = True
        elif q_found:
            if line.startswith("["):
                continue
            question.append(line.replace("\n", " "))

    return quiz


if __name__ == "__main__":
    questions = "quiz-questions.zip"
    print(parse_text(questions))
