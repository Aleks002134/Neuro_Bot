import threading
import telebot
import time
import os
from dotenv import load_dotenv
import requests
import base64
from dataclasses import dataclass
from requests.exceptions import RequestException

dotenv_path = os.path.join(os.path.dirname(__file__), 'token.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    print('Путь к файлу или файл не существует')
    exit(-1)
bot_token = os.environ['bot']
StBot = telebot.TeleBot(bot_token, num_threads=1)


class GenSnd:
    def __init__(self, message_in_queue):
        self.chat_id = message_in_queue.chat_id
        self.message_id = message_in_queue.message_id
        self.text = message_in_queue.text
        self.image_64_decode = None

    def generate_image(self):
        url = "http://127.0.0.1:7860/sdapi/v1/txt2img"
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json"
        }
        data = {
            "prompt": self.text,
            "styles": [
                "Midjourney (warm)",
                "+ Base Negative"],
            "sampling_index": "DPM++ 2M Karras",
            "sampling_steps": 30,
            "hires._fix": True,
            "hires_steps": 10,
            "denoising_strength": 0.3,
            "upscaler": "4x_NMKD-Siax_200k",
        }

        response = requests.post(url, headers=headers, json=data)
        result = response.json()

        # Декодируем изображение
        image_read = result['images'][0]
        self.image_64_decode = base64.b64decode(image_read)

    def send_message(self):
        StBot.send_photo(reply_to_message_id=self.message_id, chat_id=self.chat_id,
                         photo=self.image_64_decode)


class Typing(threading.Thread):
    def __init__(self, event):
        super().__init__()
        self.daemon = True
        self.chat_id = event.chat_id

    def run(self):
        while True:
            chat_id_list = [obj.chat_id for obj in message_list]
            if self.chat_id not in chat_id_list:
                break
            StBot.send_chat_action(self.chat_id, 'typing')
            time.sleep(2)


@dataclass
class Message:
    chat_id: int
    message_id: int
    text: str


def work():
    while True:
        if len(list(message_list)) != 0:
            time.sleep(5)
            message_in_queue = message_list[0]

            # Передача данных бэкенду и получение результата
            try:
                user_data = GenSnd(message_in_queue)
                user_data.generate_image()
            except RequestException as b:
                print('Ошибка запроса к беку', type(b), b)
                time.sleep(60)
                continue

            # Отправка сгенерированного изображения пользователю
            try:
                user_data.send_message()
            except telebot.apihelper.ApiException as e:
                print('Не удалось отправить сообщение: ', type(e), e)
                time.sleep(60)
                continue

            # Удаляем сообщение из очереди
            message_list.pop(0)


# Создание списка сообщений
message_list = []



# Обработка сообщений из Telegram, если пользователь написал start.
@StBot.message_handler(commands=['start'])
def start_message(message: telebot.types.Message):
    StBot.send_message(chat_id=message.chat.id, text='Принцип работы этого бота следующий: \n'
                                                     'Бот отправляет картинку в чат по запросу от пользователя \n'
                                                     'Запрос пользователя должен формироваться на английском языке \n')


# Обработка событий из Telegram.
@StBot.message_handler()
def get_message(message):
    a = message.text
    # Проверяем корректность текста от пользователя
    russ_sym = False
    for i in a.lower():
        if i in 'абвгдеёжзыиклмнопрстуфхцчщшэюяьъ!"№;%:?*()_-=+~@#$^&':
            russ_sym = True
            break

    if russ_sym:
        StBot.send_message(chat_id=message.chat.id, text='Запрос требуется формировать на АНГЛИЙСКОМ ЯЗЫКЕ')

    else:
        # Добавляем сообщение в очередь
        message_list.append(Message(message.chat.id, message.id, message.text))

        # Проверяем запущен ли уже поток печати для данного пользователя.
        # Если поток печати отсутствует, то запускаем.
        if [i.chat_id for i in message_list].count(message.chat.id) == 1:
            typing = Typing(message_list[-1])
            typing.start()


if __name__ == "__main__":
    while True:
        try:
            worker_thread = threading.Thread(target=work, daemon=True)
            worker_thread.start()
            StBot.polling(none_stop=True)
        except Exception as e:
            print("Ошибка запуска потоков", type(e), e)