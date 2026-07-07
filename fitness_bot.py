import asyncio
import logging
import sqlite3
import sys
import os
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)

# =========================================================
# БЕЗОПАСНОЕ ПОЛУЧЕНИЕ ТОКЕНА ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ХОСТИНГА
API_TOKEN = os.getenv("BOT_TOKEN")
# =========================================================

DB_NAME = "/app/data/fitness_bot.db"

def init_db():
    os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, height REAL, weight REAL, age INTEGER, body_type TEXT,
            strength_workouts INTEGER, cardio_workouts INTEGER, cardio_pulse INTEGER, daily_steps INTEGER,
            period_goal TEXT, target_calories REAL, target_proteins REAL, target_fats REAL, target_carbs REAL
        )
    """)
    conn.commit()
    conn.close()

# === РАСШИРЕННАЯ НА 600% БАЗА ДАННЫХ ПРОДУКТОВ ===
FOOD_DATABASE = {
    # Фитнес / Источники белка / Спортпит
    "куриное филе грудка курица куриная грудка": {"cals": 113, "prot": 23.6, "fats": 1.9, "carbs": 0.0, "cat": "Белки / Спортпит"},
    "куриная грудка запеченная": {"cals": 150, "prot": 30.0, "fats": 3.2, "carbs": 0.0, "cat": "Белки / Спортпит"},
    "куриное бедро без кожи филе": {"cals": 130, "prot": 20.0, "fats": 5.5, "carbs": 0.0, "cat": "Белки / Спортпит"},
    "индейка филе грудки": {"cals": 115, "prot": 24.1, "fats": 2.0, "carbs": 0.0, "cat": "Белки / Спортпит"},
    "индейка бедро филе": {"cals": 140, "prot": 19.5, "fats": 6.8, "carbs": 0.0, "cat": "Белки / Спортпит"},
    "говядина вырезка постная": {"cals": 158, "prot": 22.2, "fats": 7.1, "carbs": 0.0, "cat": "Белки / Спортпит"},
    "говяжий фарш постный": {"cals": 170, "prot": 20.0, "fats": 10.0, "carbs": 0.0, "cat": "Белки / Спортпит"},
    "свинина вырезка постная": {"cals": 142, "prot": 20.0, "fats": 7.0, "carbs": 0.0, "cat": "Белки / Спортпит"},
    "яйцо куриное яйца яиц яйцо": {"cals": 157, "prot": 12.7, "fats": 11.5, "carbs": 0.7, "piece_weight": 55, "cat": "Белки / Спортпит"},
    "яичный белок жидкий": {"cals": 44, "prot": 11.1, "fats": 0.0, "carbs": 1.0, "cat": "Белки / Спортпит"},
    "яичный желток": {"cals": 352, "prot": 16.0, "fats": 31.0, "carbs": 1.0, "cat": "Белки / Спортпит"},
    "творог 0% 1% обезжиренный": {"cals": 79, "prot": 16.5, "fats": 0.5, "carbs": 2.0, "cat": "Белки / Спортпит"},
    "творог 5%": {"cals": 121, "prot": 17.2, "fats": 5.0, "carbs": 1.8, "cat": "Белки / Спортпит"},
    "творог 9% классический": {"cals": 157, "prot": 16.0, "fats": 9.0, "carbs": 2.2, "cat": "Белки / Спортпит"},
    "протеин сывороточный порошок изолят": {"cals": 390, "prot": 75.0, "fats": 6.0, "carbs": 8.0, "cat": "Белки / Спортпит"},
    "казеин мицеллярный ночной": {"cals": 360, "prot": 80.0, "fats": 1.5, "carbs": 3.0, "cat": "Белки / Спортпит"},
    "протеиновый батончик": {"cals": 370, "prot": 30.0, "fats": 11.0, "carbs": 25.0, "piece_weight": 60, "cat": "Белки / Спортпит"},
    "тунец в собственном соку": {"cals": 96, "prot": 21.0, "fats": 1.2, "carbs": 0.0, "cat": "Белки / Спортпит"},
    "горбуша запеченная": {"cals": 142, "prot": 21.0, "fats": 6.0, "carbs": 0.0, "cat": "Белки / Спортпит"},
    "лосось семга на гриле": {"cals": 230, "prot": 23.0, "fats": 15.0, "carbs": 0.0, "cat": "Белки / Спортпит"},
    "креветки отварные": {"cals": 95, "prot": 22.0, "fats": 1.0, "carbs": 0.2, "cat": "Белки / Спортпит"},
    "кальмар отварной": {"cals": 100, "prot": 18.0, "fats": 2.2, "carbs": 2.0, "cat": "Белки / Спортпит"},
    "треска филе белая рыба": {"cals": 78, "prot": 17.5, "fats": 0.7, "carbs": 0.0, "cat": "Белки / Спортпит"},
    "минтай запеченный": {"cals": 80, "prot": 18.0, "fats": 0.9, "carbs": 0.0, "cat": "Белки / Спортпит"},

    # Медленные и быстрые углеводы
    "овсяные хлопья геркулес овсянка": {"cals": 352, "prot": 12.0, "fats": 6.0, "carbs": 62.0, "cat": "Сложные углеводы"},
    "гречка сухая крупа": {"cals": 330, "prot": 12.6, "fats": 3.3, "carbs": 64.0, "cat": "Сложные углеводы"},
    "гречка отварная гречневая": {"cals": 110, "prot": 4.2, "fats": 1.1, "carbs": 21.0, "cat": "Сложные углеводы"},
    "рис белый отварной рисовая": {"cals": 130, "prot": 2.7, "fats": 0.3, "carbs": 28.0, "cat": "Сложные углеводы"},
    "рис бурый коричневый отварной": {"cals": 111, "prot": 2.6, "fats": 0.9, "carbs": 23.0, "cat": "Сложные углеводы"},
    "рис басмати сухой": {"cals": 340, "prot": 7.5, "fats": 0.5, "carbs": 78.0, "cat": "Сложные углеводы"},
    "макароны твердых сортов отварные": {"cals": 140, "prot": 5.0, "fats": 0.5, "carbs": 28.0, "cat": "Сложные углеводы"},
    "макароны сухие паста": {"cals": 350, "prot": 12.0, "fats": 1.5, "carbs": 72.0, "cat": "Сложные углеводы"},
    "булгур сухой крупа": {"cals": 342, "prot": 12.0, "fats": 1.5, "carbs": 76.0, "cat": "Сложные углеводы"},
    "булгур отварной": {"cals": 83, "prot": 3.0, "fats": 0.2, "carbs": 18.0, "cat": "Сложные углеводы"},
    "кускус сухой": {"cals": 360, "prot": 12.8, "fats": 0.6, "carbs": 77.0, "cat": "Сложные углеводы"},
    "киноа сухая крупа": {"cals": 368, "prot": 14.0, "fats": 6.0, "carbs": 64.0, "cat": "Сложные углеводы"},
    "перловая крупа сухая": {"cals": 320, "prot": 9.3, "fats": 1.1, "carbs": 73.0, "cat": "Сложные углеводы"},
    "картофель запеченный": {"cals": 93, "prot": 2.5, "fats": 0.1, "carbs": 21.0, "cat": "Сложные углеводы"},
    "сладкий картофель батат": {"cals": 86, "prot": 1.6, "fats": 0.1, "carbs": 20.0, "cat": "Сложные углеводы"},
    "хлебцы цельнозерновые ржаные": {"cals": 310, "prot": 11.0, "fats": 2.0, "carbs": 58.0, "cat": "Сложные углеводы"},

    # Полезные жиры / Орехи / Семена
    "арахисовая паста без сахара": {"cals": 588, "prot": 25.0, "fats": 50.0, "carbs": 13.0, "cat": "Полезные жиры"},
    "миндаль орехи": {"cals": 645, "prot": 18.6, "fats": 57.7, "carbs": 13.0, "cat": "Полезные жиры"},
    "грецкий орех": {"cals": 654, "prot": 15.2, "fats": 65.2, "carbs": 7.0, "cat": "Полезные жиры"},
    "кешью": {"cals": 553, "prot": 18.0, "fats": 44.0, "carbs": 30.0, "cat": "Полезные жиры"},
    "фундук лесной орех": {"cals": 651, "prot": 15.0, "fats": 61.5, "carbs": 9.4, "cat": "Полезные жиры"},
    "семечки подсолнечника очищенные подсолнуха": {"cals": 580, "prot": 20.7, "fats": 52.9, "carbs": 10.5, "cat": "Полезные жиры"},
    "семена тыквы тыквенные": {"cals": 556, "prot": 30.0, "fats": 49.0, "carbs": 10.8, "cat": "Полезные жиры"},
    "семена льна": {"cals": 534, "prot": 18.3, "fats": 42.2, "carbs": 1.6, "cat": "Полезные жиры"},
    "семена чиа": {"cals": 486, "prot": 16.5, "fats": 30.7, "carbs": 42.1, "cat": "Полезные жиры"},
    "оливковое масло подсолнечное": {"cals": 899, "prot": 0.0, "fats": 99.9, "carbs": 0.0, "cat": "Полезные жиры"},
    "льняное масло": {"cals": 898, "prot": 0.0, "fats": 99.8, "carbs": 0.0, "cat": "Полезные жиры"},
    "кокосовое масло": {"cals": 892, "prot": 0.0, "fats": 99.0, "carbs": 0.0, "cat": "Полезные жиры"},
    "сливочное масло 82.5%": {"cals": 748, "prot": 0.6, "fats": 82.5, "carbs": 0.8, "cat": "Полезные жиры"},
    "авокадо": {"cals": 160, "prot": 2.0, "fats": 14.7, "carbs": 6.7, "piece_weight": 140, "cat": "Полезные жиры"},

    # Русская кухня / Столовая / Домашняя еда
    "борщ с говядиной борща": {"cals": 60, "prot": 4.0, "fats": 3.0, "carbs": 5.0, "cat": "Столовая и домашняя еда"},
    "суп куриный с лапшой вермишелью": {"cals": 45, "prot": 3.2, "fats": 1.8, "carbs": 4.0, "cat": "Столовая и домашняя еда"},
    "щи из свежей капусты": {"cals": 31, "prot": 1.2, "fats": 1.6, "carbs": 3.2, "cat": "Столовая и домашняя еда"},
    "суп гороховый с копченостями": {"cals": 66, "prot": 4.4, "fats": 2.6, "carbs": 6.8, "cat": "Столовая и домашняя еда"},
    "суп-пюре грибной шампиньоны": {"cals": 75, "prot": 2.0, "fats": 4.8, "carbs": 6.0, "cat": "Столовая и домашняя еда"},
    "пельмени отварные": {"cals": 245, "prot": 11.3, "fats": 13.2, "carbs": 20.7, "cat": "Столовая и домашняя еда"},
    "вареники с картошкой": {"cals": 180, "prot": 3.5, "fats": 4.0, "carbs": 32.0, "cat": "Столовая и домашняя еда"},
    "вареники с творогом сладкие": {"cals": 220, "prot": 9.5, "fats": 5.0, "carbs": 34.0, "cat": "Столовая и домашняя еда"},
    "картофельное пюре с молоком": {"cals": 90, "prot": 2.0, "fats": 3.3, "carbs": 15.0, "cat": "Столовая и домашняя еда"},
    "котлета домашняя свино-говяжья": {"cals": 245, "prot": 16.0, "fats": 18.0, "carbs": 6.0, "piece_weight": 80, "cat": "Столовая и домашняя еда"},
    "котлета куриная паровая": {"cals": 135, "prot": 18.0, "fats": 5.0, "carbs": 3.5, "piece_weight": 80, "cat": "Столовая и домашняя еда"},
    "рыбная котлета минтай": {"cals": 120, "prot": 14.0, "fats": 4.2, "carbs": 6.5, "piece_weight": 80, "cat": "Столовая и домашняя еда"},
    "блины без начинки блинчики": {"cals": 185, "prot": 5.1, "fats": 6.0, "carbs": 28.0, "cat": "Столовая и домашняя еда"},
    "блины со свининой или говядиной фаршем": {"cals": 195, "prot": 7.5, "fats": 8.0, "carbs": 23.0, "cat": "Столовая и домашняя еда"},
    "блины с творогом": {"cals": 190, "prot": 8.0, "fats": 5.5, "carbs": 27.0, "cat": "Столовая и домашняя еда"},
    "сырники из творога запеченные": {"cals": 200, "prot": 16.0, "fats": 6.0, "carbs": 20.0, "cat": "Столовая и домашняя еда"},
    "сыр российский голландский костромской": {"cals": 360, "prot": 23.0, "fats": 29.0, "carbs": 0.0, "cat": "Столовая и домашняя еда"},
    "сыр моцарелла": {"cals": 240, "prot": 18.0, "fats": 18.0, "carbs": 1.0, "cat": "Столовая и домашняя еда"},
    "сыр сулугуни": {"cals": 285, "prot": 20.0, "fats": 22.0, "carbs": 0.0, "cat": "Столовая и домашняя еда"},
    "сыр фета сиртаки": {"cals": 260, "prot": 14.0, "fats": 21.0, "carbs": 4.0, "cat": "Столовая и домашняя еда"},
    "хлеб ржаной бородинский черный": {"cals": 210, "prot": 6.5, "fats": 1.2, "carbs": 40.0, "cat": "Столовая и домашняя еда"},
    "хлеб белый пшеничный тостовый батон": {"cals": 260, "prot": 8.0, "fats": 2.5, "carbs": 50.0, "cat": "Столовая и домашняя еда"},
    "гуляш говяжий с подливой": {"cals": 150, "prot": 16.0, "fats": 9.0, "carbs": 3.5, "cat": "Столовая и домашняя еда"},
    "плов с курицей": {"cals": 170, "prot": 8.5, "fats": 6.0, "carbs": 21.0, "cat": "Столовая и домашняя еда"},

    # Мировая кухня / Фастфуд / Читмил
    "роллы филадельфия лосось": {"cals": 142, "prot": 6.2, "fats": 6.1, "carbs": 15.4, "piece_weight": 35, "cat": "Мировая кухня и Фастфуд"},
    "роллы калифорния краб": {"cals": 176, "prot": 5.0, "fats": 5.0, "carbs": 28.0, "piece_weight": 32, "cat": "Мировая кухня и Фастфуд"},
    "суши с лососем нигири": {"cals": 135, "prot": 8.0, "fats": 2.5, "carbs": 20.0, "piece_weight": 30, "cat": "Мировая кухня и Фастфуд"},
    "суп рамэн тонкацу свинина лапша": {"cals": 85, "prot": 4.5, "fats": 4.0, "carbs": 8.0, "cat": "Мировая кухня и Фастфуд"},
    "суп том ям с креветками кокосовое": {"cals": 95, "prot": 5.0, "fats": 6.2, "carbs": 4.8, "cat": "Мировая кухня и Фастфуд"},
    "пицца маргарита сырная": {"cals": 240, "prot": 10.1, "fats": 8.0, "carbs": 31.4, "cat": "Мировая кухня и Фастфуд"},
    "пицца пепперони острая": {"cals": 290, "prot": 12.5, "fats": 14.0, "carbs": 29.0, "cat": "Мировая кухня и Фастфуд"},
    "пицца четыре сыра": {"cals": 310, "prot": 13.0, "fats": 16.0, "carbs": 30.0, "cat": "Мировая кухня и Фастфуд"},
    "паста карбонара бекон сливки": {"cals": 220, "prot": 9.0, "fats": 11.5, "carbs": 20.0, "cat": "Мировая кухня и Фастфуд"},
    "паста болоньезе мясной фарш": {"cals": 165, "prot": 8.2, "fats": 6.5, "carbs": 19.0, "cat": "Мировая кухня и Фастфуд"},
    "лазанья с мясным фаршем бешамель": {"cals": 170, "prot": 9.2, "fats": 8.5, "carbs": 14.0, "cat": "Мировая кухня и Фастфуд"},
    "бургер классический говяжий котлета": {"cals": 254, "prot": 12.0, "fats": 10.0, "carbs": 29.0, "piece_weight": 150, "cat": "Мировая кухня и Фастфуд"},
    "чизбургер": {"cals": 265, "prot": 13.0, "fats": 11.5, "carbs": 30.0, "piece_weight": 120, "cat": "Мировая кухня и Фастфуд"},
    "картофель фри фритюр": {"cals": 312, "prot": 3.4, "fats": 15.0, "carbs": 41.0, "cat": "Мировая кухня и Фастфуд"},
    "картофельные дольки по-деревенски": {"cals": 140, "prot": 2.5, "fats": 5.0, "carbs": 21.0, "cat": "Мировая кухня и Фастфуд"},
    "куриные наггетсы панировка": {"cals": 280, "prot": 15.0, "fats": 16.0, "carbs": 19.0, "piece_weight": 20, "cat": "Мировая кухня и Фастфуд"},
    "шаурма с курицей донер классическая": {"cals": 175, "prot": 9.0, "fats": 8.0, "carbs": 16.0, "piece_weight": 400, "cat": "Мировая кухня и Фастфуд"},
    "кебаб люля из говядины фарш": {"cals": 220, "prot": 18.0, "fats": 16.0, "carbs": 1.5, "cat": "Мировая кухня и Фастфуд"},
    "шашлык из куриного бедра курица": {"cals": 180, "prot": 19.0, "fats": 11.5, "carbs": 0.0, "cat": "Мировая кухня и Фастфуд"},
    "шашлык свиной шея": {"cals": 270, "prot": 16.0, "fats": 23.0, "carbs": 0.0, "cat": "Мировая кухня и Фастфуд"},

    # Растительные источники / Овощи / Фрукты / Напитки
    "банан банана бананы": {"cals": 95, "prot": 1.5, "fats": 0.2, "carbs": 21.8, "piece_weight": 120, "cat": "Овощи, Фрукты и Напитки"},
    "яблоко яблока яблоки": {"cals": 47, "prot": 0.4, "fats": 0.4, "carbs": 9.8, "piece_weight": 150, "cat": "Овощи, Фрукты и Напитки"},
    "груша": {"cals": 42, "prot": 0.4, "fats": 0.3, "carbs": 10.3, "piece_weight": 160, "cat": "Овощи, Фрукты и Напитки"},
    "апельсин": {"cals": 43, "prot": 0.9, "fats": 0.2, "carbs": 8.4, "piece_weight": 150, "cat": "Овощи, Фрукты и Напитки"},
    "грейпфрут": {"cals": 35, "prot": 0.7, "fats": 0.2, "carbs": 8.0, "piece_weight": 250, "cat": "Овощи, Фрукты и Напитки"},
    "киви": {"cals": 61, "prot": 1.1, "fats": 0.5, "carbs": 14.7, "piece_weight": 75, "cat": "Овощи, Фрукты и Напитки"},
    "голубика черника ягоды": {"cals": 44, "prot": 0.7, "fats": 0.4, "carbs": 11.0, "cat": "Овощи, Фрукты и Напитки"},
    "клубника свежая": {"cals": 32, "prot": 0.7, "fats": 0.4, "carbs": 7.5, "cat": "Овощи, Фрукты и Напитки"},
    "томаты помидоры свежие": {"cals": 18, "prot": 0.6, "fats": 0.2, "carbs": 3.7, "cat": "Овощи, Фрукты и Напитки"},
    "огурцы свежие": {"cals": 15, "prot": 0.8, "fats": 0.1, "carbs": 2.8, "cat": "Овощи, Фрукты и Напитки"},
    "брокколи отварная капуста": {"cals": 35, "prot": 2.4, "fats": 0.4, "carbs": 6.6, "cat": "Овощи, Фрукты и Напитки"},
    "белокочанная капуста свежая": {"cals": 25, "prot": 1.8, "fats": 0.1, "carbs": 4.7, "cat": "Овощи, Фрукты и Напитки"},
    "болгарский перец сладкий": {"cals": 26, "prot": 1.0, "fats": 0.0, "carbs": 5.0, "cat": "Овощи, Фрукты и Напитки"},
    "шпинат зелень свежий": {"cals": 23, "prot": 2.9, "fats": 0.4, "carbs": 3.6, "cat": "Овощи, Фрукты и Напитки"},
    "кока-кола стандартная газировка": {"cals": 42, "prot": 0.0, "fats": 0.0, "carbs": 10.6, "is_liquid": True, "cat": "Овощи, Фрукты и Напитки"},
    "кола зеро zero без сахара диетическая": {"cals": 0.3, "prot": 0.0, "fats": 0.0, "carbs": 0.0, "is_liquid": True, "cat": "Овощи, Фрукты и Напитки"},
    "вода питьевая минеральная": {"cals": 0.0, "prot": 0.0, "fats": 0.0, "carbs": 0.0, "is_liquid": True, "cat": "Овощи, Фрукты и Напитки"},
    "молоко 2.5% коровье": {"cals": 54, "prot": 2.9, "fats": 2.5, "carbs": 4.8, "is_liquid": True, "cat": "Овощи, Фрукты и Напитки"},
    "молоко 3.2%": {"cals": 60, "prot": 3.0, "fats": 3.2, "carbs": 4.7, "is_liquid": True, "cat": "Овощи, Фрукты и Напитки"},
    "молоко миндальное без сахара": {"cals": 13, "prot": 0.4, "fats": 1.1, "carbs": 0.3, "is_liquid": True, "cat": "Овощи, Фрукты и Напитки"},
    "кефир 1% кисломолочный": {"cals": 40, "prot": 3.0, "fats": 1.0, "carbs": 4.0, "is_liquid": True, "cat": "Овощи, Фрукты и Напитки"},
    "йогурт греческий натуральный 2%": {"cals": 66, "prot": 8.0, "fats": 2.0, "carbs": 3.5, "cat": "Овощи, Фрукты и Напитки"},
    "водка 40% алкоголь": {"cals": 231, "prot": 0.0, "fats": 0.0, "carbs": 0.1, "is_liquid": True, "cat": "Овощи, Фрукты и Напитки"},
    "пиво светлое фильтрованное лагер": {"cals": 43, "prot": 0.5, "fats": 0.0, "carbs": 3.8, "is_liquid": True, "cat": "Овощи, Фрукты и Напитки"}
}

# === РАСШИРЕННАЯ НА 600% БАЗА ДАННЫХ ДЛЯ КОНСТРУКТОРА ТРЕНИРОВОК ===
CONSTRUCTOR_EXERCISES = {
    "Грудь": [
        "Жим штанги на наклонной 30° (Верх груди)",
        "Жим гантелей на горизонталке (Общая масса)",
        "Сведения в пег-дек / Баттерфляй (Изоляция)",
        "Кроссовер через верхние блоки (Низ и рассечение)",
        "Отжимания на брусьях с весом (Акцент на грудь)",
        "Жим гантелей на наклонной скамье 45°",
        "Жим в тренажере Смита под углом",
        "Жим штанги лежа на горизонтальной скамье",
        "Жим в хаммере на среднюю / нижнюю часть",
        "Пуловер с гантелью лежа на скамье",
        "Сведения гантелей лежа на горизонталке",
        "Кроссовер через нижние блоки (Акцент на верх)"
    ],
    "Спина": [
        "Подтягивания с весом широким хватом",
        "Тяга верхнего блока к груди (Ширина спины)",
        "Тяга штанги в наклоне прямым/обратным хватом",
        "Тяга Т-грифа с упором в грудь (Толщина спины)",
        "Пуловер на верхнем блоке с канатом / рукоятью",
        "Тяга гантели в наклоне одной рукой к поясу",
        "Тяга горизонтального блока к животу (V-рукоять)",
        "Тяга в хаммере на широчайшие поочередно",
        "Подтягивания параллельным узким хватом",
        "Тяга верхнего блока за голову",
        "Гиперэкстензия с весом (Разгибатели спины)",
        "Становая тяга классическая / с плинтов"
    ],
    "Плечи": [
        "Махи гантелями в стороны стоя (Средняя дельта)",
        "Жим гантелей сидя под углом 80° (Передняя/средняя)",
        "Армейский жим стоя со штангой с груди",
        "Махи в наклоне на заднюю дельту с гантелями",
        "Протяжка штанги / EZ-грифа к подбородку широким",
        "Махи гантелями сидя на скамье (В стороны)",
        "Жим штанги сидя в тренажере Смита",
        "Отведения рук назад в тренажере пег-дек (Задняя)",
        "Махи одной рукой от нижнего блока в сторону",
        "Фронтальные подъемы гантелей перед собой",
        "Подъемы блина перед собой на переднюю дельту",
        "Шраги со штангой или гантелями (Трапеции)"
    ],
    "Руки": [
        "Подъем штанги на бицепс с EZ-грифом standing",
        "Французский жим лежа на скамье со штангой",
        "Молотки с гантелями стоя (Брахиалис и предплечье)",
        "Разгибания рук на верхнем блоке с канатом (Трицепс)",
        "Сгибания рук на скамье Скотта (Изоляция бицепса)",
        "Жим лежа узким хватом на горизонтальной скамье",
        "Концентрированные сгибания рук с гантелью сидя",
        "Отжимания на брусьях с акцентом на трицепс",
        "Сгибания рук с гантелями с супинацией сидя",
        "Разгибание одной руки с гантелью из-за головы",
        "Разгибания рук обратным хватом на блоке",
        "Сгибания рук на нижнем блоке с канатом"
    ],
    "Ноги": [
        "Приседания со штангой на спине (Низкий/высокий бар)",
        "Фронтальные приседания (Акцент на квадрицепс)",
        "Жим ногами в платформе 45 градусов",
        "Румынская становая тяга с гантелями / штангой",
        "Разгибания ног в тренажере сидя (Каплевидная)",
        "Сгибания ног в тренажере лежа (Бицепс бедра)",
        "Гакк-приседания в тренажере (Глубокий сед)",
        "Выпады с гантелями в движении (Ягодицы/квадрицепс)",
        "Болгарские сплит-приседания с гантелями",
        "Подъемы на носки стоя в тренажере (Икроножные)",
        "Подъемы на носки сидя в тренажере (Камбаловидная)",
        "Сведение / Разведение ног в тренажере сидя"
    ]
}

def Lemматизатор_Мини(text):
    text = text.lower().strip()
    text = re.sub(r'(ой|и|ы|а|я|у|е|ом|ам|ами|ях|кой|ной|ки|ка|ку|цы|ца|цу|ей|ьями|ьях|ов|ей|ным|ное|ная)$', '', text)
    return text

def find_food_in_db(raw_part):
    clean_text = raw_part.lower().strip()
    clean_text = re.sub(r'[\d.]+', '', clean_text)
    clean_text = re.sub(r'\b(шт|грамм|грамма|граммов|г|кг|мл|л|литр|литра|литров)\b', '', clean_text)
    words = [Лемматизатор_Мини(w) for w in re.findall(r'[а-яА-Яa-zA-Z0-9%]+', clean_text) if len(w) > 1]
    if not words: return None, None
    best_match, max_matches = None, 0
    for db_key, info in FOOD_DATABASE.items():
        matches = sum(1 for word in words if word in db_key)
        if matches > max_matches:
            max_matches = matches
            best_match = (db_key, info)
    return best_match if max_matches > 0 else (None, None)

def get_main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="🍽️ Добавить еду")
    builder.button(text="📋 Мой профиль")
    builder.button(text="📖 База продуктов")
    builder.button(text="🛠️ Конструктор тренировок")
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)

class RegistrationStates(StatesGroup):
    waiting_for_height = State()
    waiting_for_weight = State()
    waiting_for_age = State()
    waiting_for_body_type = State()
    waiting_for_strength = State()
    waiting_for_cardio = State()
    waiting_for_pulse = State()
    waiting_for_goal = State()

class FoodStates(StatesGroup):
    waiting_for_batch = State()

class ConstructorStates(StatesGroup):
    waiting_for_day = State()
    waiting_for_muscle = State()
    waiting_for_exercise = State()
    waiting_for_sets = State()
    waiting_for_reps = State()

dp = Dispatcher(storage=MemoryStorage())

@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await message.answer("Добро пожаловать в фитнес-помощник!\nШаг 1: Введи рост в см:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(RegistrationStates.waiting_for_height)

@dp.message(RegistrationStates.waiting_for_height)
async def process_height(message: types.Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        await state.update_data(height=val)
        await message.answer("Шаг 2: Введи текущий вес в кг:")
        await state.set_state(RegistrationStates.waiting_for_weight)
    except ValueError:
        await message.answer("Пожалуйста, введи корректное число (например, 195.7):")

@dp.message(RegistrationStates.waiting_for_weight)
async def process_weight(message: types.Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        await state.update_data(weight=val)
        await message.answer("Шаг 3: Введи твой возраст:")
        await state.set_state(RegistrationStates.waiting_for_age)
    except ValueError:
        await message.answer("Пожалуйста, введи корректное число (например, 17):")

@dp.message(RegistrationStates.waiting_for_age)
async def process_age(message: types.Message, state: FSMContext):
    try:
        val = int(message.text)
        await state.update_data(age=val)
        b = InlineKeyboardBuilder()
        b.button(text="Мезоморф", callback_data="bt_mesomorph")
        b.button(text="Эктоморф", callback_data="bt_ectomorph")
        b.button(text="Эндоморф", callback_data="bt_endomorph")
        await message.answer("Шаг 4: Выбери тип телосложения:", reply_markup=b.as_markup())
        await state.set_state(RegistrationStates.waiting_for_body_type)
    except ValueError:
        await message.answer("Введи целое число:")

@dp.callback_query(RegistrationStates.waiting_for_body_type)
async def process_bt(c: types.CallbackQuery, state: FSMContext):
    body_type = c.data.split("_")[1]
    await state.update_data(body_type=body_type)
    await c.message.answer("Шаг 5: Сколько силовых тренировок в неделю?")
    await state.set_state(RegistrationStates.waiting_for_strength)
    await c.answer()

@dp.message(RegistrationStates.waiting_for_strength)
async def process_str(message: types.Message, state: FSMContext):
    try:
        await state.update_data(strength_workouts=int(message.text))
        await message.answer("Шаг 6: Сколько кардио тренировок в неделю?")
        await state.set_state(RegistrationStates.waiting_for_cardio)
    except ValueError:
        await message.answer("Пожалуйста, введите целое число:")

@dp.message(RegistrationStates.waiting_for_cardio)
async def process_card(message: types.Message, state: FSMContext):
    try:
        await state.update_data(cardio_workouts=int(message.text))
        await message.answer("Шаг 7: Укажи средний целевой пульс на кардио:")
        await state.set_state(RegistrationStates.waiting_for_pulse)
    except ValueError:
        await message.answer("Пожалуйста, введите целое число:")

@dp.message(RegistrationStates.waiting_for_pulse)
async def process_pls(message: types.Message, state: FSMContext):
    try:
        await state.update_data(cardio_pulse=int(message.text), daily_steps=0)
        b = InlineKeyboardBuilder()
        b.button(text="🔥 Сушка / Жиросжигание", callback_data="goal_cutting")
        b.button(text="⚖️ Удержание", callback_data="goal_maintenance")
        b.button(text="💪 Массонабор", callback_data="goal_bulking")
        await message.answer("Шаг 8: Выбери цель текущего тренировочного периода:", reply_markup=b.as_markup())
        await state.set_state(RegistrationStates.waiting_for_goal)
    except ValueError:
        await message.answer("Введите число ударов в минуту:")

@dp.callback_query(RegistrationStates.waiting_for_goal)
async def process_gl(c: types.CallbackQuery, state: FSMContext):
    g = c.data.split("_")[1]
    d = await state.get_data()
    
    bmr = (10 * d['weight']) + (6.25 * d['height']) - (5 * d['age']) + 5
    cals = bmr * 1.4
    
    if g == "cutting":
        cals -= 450
        p, j, u = d['weight'] * 2.3, d['weight'] * 0.8, (cals - (d['weight'] * 2.3 * 4) - (d['weight'] * 0.8 * 9)) / 4
        gt = "Сушка / Жиросжигание"
    elif g == "bulking":
        cals += 350
        p, j, u = d['weight'] * 2.0, d['weight'] * 1.0, (cals - (d['weight'] * 2.0 * 4) - (d['weight'] * 1.0 * 9)) / 4
        gt = "Массонабор / Классический профицит"
    else:
        p, j, u = d['weight'] * 2.0, d['weight'] * 0.9, (cals - (d['weight'] * 2.0 * 4) - (d['weight'] * 0.9 * 9)) / 4
        gt = "Удержание формы"

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                   (c.from_user.id, d['height'], d['weight'], d['age'], d['body_type'], d['strength_workouts'], d['cardio_workouts'], d['cardio_pulse'], d['daily_steps'], gt, round(cals), round(p), round(j), round(u)))
    conn.commit()
    conn.close()
    
    await c.message.answer(f"🎉 Профиль успешно настроен!\n🎯 Расчетная цель: {gt}\n\n🔥 Рекомендуемый КБЖУ:\n▪️ Калории: {round(cals)} ккал\n▪️ Белки: {round(p)} г\n▪️ Жиры: {round(j)} г\n▪️ Углеводы: {round(u)} г", reply_markup=get_main_keyboard())
    await state.clear()
    await c.answer()

@dp.message(F.text == "📋 Мой профиль")
@dp.message(Command("profile"))
async def view_profile(message: types.Message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT height, weight, age, body_type, strength_workouts, cardio_workouts, cardio_pulse, period_goal, target_calories, target_proteins, target_fats, target_carbs FROM users WHERE user_id = ?", (message.from_user.id,))
    r = cursor.fetchone()
    conn.close()
    if not r:
        await message.answer("Ваш профиль не найден. Пожалуйста, пройдите первоначальную настройку через /start.")
        return
    await message.answer(f"📋 **Ваш фитнес-профиль:**\n▪️ Рост: {r[0]} см\n▪️ Вес: {r[1]} кг\n▪️ Возраст: {r[2]} лет\n▪️ Тип тела: {r[3]}\n▪️ Тренировки: Силовые {r[4]}р/нед, Кардио {r[5]}р/нед (Пульс: {r[6]} уд/м)\n\n🎯 **Текущий период:** {r[7]}\n📈 **Ваша цель КБЖУ:**\n🔥 {r[8]} ккал | Б: {r[9]}г | Ж: {r[10]}г | У: {r[11]}г", reply_markup=get_main_keyboard())

@dp.message(F.text == "📖 База продуктов")
async def show_categories(message: types.Message):
    categories = sorted(list(set(info["cat"] for info in FOOD_DATABASE.values())))
    b = InlineKeyboardBuilder()
    for cat in categories:
        b.button(text=cat, callback_data=f"showcat_{cat}")
    b.adjust(1)
    await message.answer("Выберите категорию продуктов для просмотра состава на 100 грамм:", reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("showcat_"))
async def process_show_category(c: types.CallbackQuery):
    cat_name = c.data.split("_")[1]
    items = [key for key, info in FOOD_DATABASE.items() if info["cat"] == cat_name]
    text = f"📖 **Категория: {cat_name} (на 100г)**\n\n"
    for i in items:
        inf = FOOD_DATABASE[i]
        text += f"• {i.split()[0].capitalize()}: {inf['cals']}ккал (Б:{inf['prot']}|Ж:{inf['fats']}|У:{inf.get('carbs', inf.get('car90', 0.0))})\n"
    await c.message.answer(text, reply_markup=get_main_keyboard())
    await c.answer()

@dp.message(F.text == "🛠️ Конструктор тренировок")
@dp.message(Command("constructor"))
async def start_constructor(message: types.Message, state: FSMContext):
    await state.clear()
    b = InlineKeyboardBuilder()
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    for day in days:
        b.button(text=day, callback_data=f"cday_{day}")
    b.adjust(2)
    await message.answer("🛠️ **Интерактивный Конструктор планов!**\n\nВыбери день недели для сборки тренировочного сплита:", reply_markup=b.as_markup())
    await state.set_state(ConstructorStates.waiting_for_day)

@dp.callback_query(ConstructorStates.waiting_for_day, F.data.startswith("cday_"))
async def process_const_day(c: types.CallbackQuery, state: FSMContext):
    day = c.data.split("_")[1]
    await state.update_data(chosen_day=day, workout_list=[])
    
    b = InlineKeyboardBuilder()
    for muscle in CONSTRUCTOR_EXERCISES.keys():
        b.button(text=muscle, callback_data=f"cmuscle_{muscle}")
    b.adjust(2)
    
    await c.message.edit_text(f"📆 День: **{day}**\n\nВыбери целевую мышечную группу:", reply_markup=b.as_markup())
    await state.set_state(ConstructorStates.waiting_for_muscle)
    await c.answer()

@dp.callback_query(ConstructorStates.waiting_for_muscle, F.data.startswith("cmuscle_"))
async def process_const_muscle(c: types.CallbackQuery, state: FSMContext):
    muscle = c.data.split("_")[1]
    await state.update_data(chosen_muscle=muscle)
    
    b = InlineKeyboardBuilder()
    exercises = CONSTRUCTOR_EXERCISES.get(muscle, [])
    for idx, ex in enumerate(exercises):
        b.button(text=ex, callback_data=f"cex_{idx}")
    b.button(text="⬅️ Назад к группам", callback_data="back_to_muscles")
    b.adjust(1)
    
    await c.message.edit_text(f"🎯 Группа: **{muscle}**\n\nВыбери конкретное упражнение:", reply_markup=b.as_markup())
    await state.set_state(ConstructorStates.waiting_for_exercise)
    await c.answer()

@dp.callback_query(ConstructorStates.waiting_for_exercise, F.data == "back_to_muscles")
async def back_to_muscles_callback(c: types.CallbackQuery, state: FSMContext):
    d = await state.get_data()
    b = InlineKeyboardBuilder()
    for muscle in CONSTRUCTOR_EXERCISES.keys():
        b.button(text=muscle, callback_data=f"cmuscle_{muscle}")
    b.adjust(2)
    await c.message.edit_text(f"📆 День: **{d['chosen_day']}**\n\nВыбери целевую мышечную группу:", reply_markup=b.as_markup())
    await state.set_state(ConstructorStates.waiting_for_muscle)
    await c.answer()

@dp.callback_query(ConstructorStates.waiting_for_exercise, F.data.startswith("cex_"))
async def process_const_exercise(c: types.CallbackQuery, state: FSMContext):
    idx = int(c.data.split("_")[1])
    d = await state.get_data()
    muscle = d['chosen_muscle']
    ex_name = CONSTRUCTOR_EXERCISES[muscle][idx]
    await state.update_data(chosen_ex_name=ex_name)
    
    b = InlineKeyboardBuilder()
    for s in ["1", "2", "3", "4", "5"]:
        b.button(text=f"{s} подх.", callback_data=f"csets_{s}")
    b.adjust(5)
    
    await c.message.edit_text(f"🏋️ Выбрано: **{ex_name}**\n\nУкажи количество рабочих подходов:", reply_markup=b.as_markup())
    await state.set_state(ConstructorStates.waiting_for_sets)
    await c.answer()

@dp.callback_query(ConstructorStates.waiting_for_sets, F.data.startswith("csets_"))
async def process_const_sets(c: types.CallbackQuery, state: FSMContext):
    sets = c.data.split("_")[1]
    await state.update_data(chosen_sets=sets)
    
    b = InlineKeyboardBuilder()
    reps_options = ["1-5 (Сила)", "6-8 (Плотность)", "8-12 (Гипертрофия)", "12-15 (Пампинг)", "15-20 (Выносливость)"]
    for r_opt in reps_options:
        b.button(text=r_opt, callback_data=f"creps_{r_opt}")
    b.adjust(1)
    
    d = await state.get_data()
    await c.message.edit_text(f"🏋️ {d['chosen_ex_name']}: **{sets} подходов**\n\nВыбери диапазон повторений:", reply_markup=b.as_markup())
    await state.set_state(ConstructorStates.waiting_for_reps)
    await c.answer()

@dp.callback_query(ConstructorStates.waiting_for_reps, F.data.startswith("creps_"))
async def process_const_reps(c: types.CallbackQuery, state: FSMContext):
    reps = c.data.split("_")[1]
    d = await state.get_data()
    
    current_workout = d.get('workout_list', [])
    current_workout.append({
        "muscle": d['chosen_muscle'],
        "name": d['chosen_ex_name'],
        "sets": d['chosen_sets'],
        "reps": reps
    })
    await state.update_data(workout_list=current_workout)
    
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить еще упражнение", callback_data="const_add_more")
    b.button(text="🏁 Завершить и получить план", callback_data="const_finish")
    b.adjust(1)
    
    summary = "\n".join([f"🔹 {item['name']} ({item['muscle']}) — {item['sets']}х{item['reps']}" for item in current_workout])
    await c.message.edit_text(f"📝 **Состав тренировки ({d['chosen_day']}):**\n\n{summary}\n\nПродолжить сборку?", reply_markup=b.as_markup())
    await c.answer()

@dp.callback_query(F.data == "const_add_more")
async def const_add_more_callback(c: types.CallbackQuery, state: FSMContext):
    b = InlineKeyboardBuilder()
    for muscle in CONSTRUCTOR_EXERCISES.keys():
        b.button(text=muscle, callback_data=f"cmuscle_{muscle}")
    b.adjust(2)
    d = await state.get_data()
    await c.message.edit_text(f"📆 День: **{d['chosen_day']}**\n\nВыбери группу для следующего движения:", reply_markup=b.as_markup())
    await state.set_state(ConstructorStates.waiting_for_muscle)
    await c.answer()

@dp.callback_query(F.data == "const_finish")
async def const_finish_callback(c: types.CallbackQuery, state: FSMContext):
    d = await state.get_data()
    workout_list = d.get('workout_list', [])
    
    if not workout_list:
        await c.message.answer("План пуст.", reply_markup=get_main_keyboard())
        await state.clear()
        await c.answer()
        return
        
    total_exercises = len(workout_list)
    tips = "💡 **Аналитика сплита и советы тренера:**\n"
    
    if total_exercises > 6:
        tips += "⚠️ *Внимание:* Слишком высокий объем сессии. Во избежание катаболизма и сильного утомления ЦНС сократите количество упражнений до 4-5 высокоинтенсивных.\n"
    else:
        tips += "✅ *Объем нагрузок:* Отличный баланс! Позволит выложиться в каждом рабочем подходе без переутомления.\n"
        
    has_strength = any("1-5" in i['reps'] for i in workout_list)
    has_hyper = any("8-12" in i['reps'] for i in workout_list)
    
    if has_strength:
        tips += "⚡ *Совет по силе:* В диапазонах 1-5 повт. делайте паузы между подходами 3-4 минуты. Это необходимо для восстановления креатинфосфата.\n"
    if has_hyper:
        tips += "🏆 *Эстетика и профиль:* В сетах на 8-12 повторений удерживайте пиковое сокращение в верхней точке на 1 секунду. Контролируйте негативную фазу!\n"
        
    tips += "💧 *Восстановление:* Закройте анаболическое окно полноценным приемом белка и сложных углеводов в течение 60-90 минут после нагрузок."

    report = f"📋 **Готовый план тренировки на {d['chosen_day']}**\n"
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
    for idx, item in enumerate(workout_list, 1):
        report += f"{idx}. **{item['name']}**\n   └ Группа: {item['muscle']} | {item['sets']} подх. × {item['reps']}\n"
    report += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    report += tips
    
    await c.message.answer(report, reply_markup=get_main_keyboard())
    await state.clear()
    await c.answer()

@dp.message(F.text == "🍽️ Добавить еду")
@dp.message(Command("eat"))
async def eat_cmd(message: types.Message, state: FSMContext):
    await message.answer("📝 Введи съеденные продукты через запятую.\nПример: `2шт яиц, 100г овсянка, 200г куриная грудка, 50г семечки`:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(FoodStates.waiting_for_batch)

@dp.message(FoodStates.waiting_for_batch)
async def process_food_batch(message: types.Message, state: FSMContext):
    raw_text = message.text
    parts = raw_text.split(",")
    total_cals, total_p, total_j, total_c = 0.0, 0.0, 0.0, 0.0
    found_items_summary, failed_items = [], []
    
    for part in parts:
        part = part.strip().lower().replace(",", ".")
        if not part: continue
        num_match = re.findall(r'[\d.]+', part)
        if not num_match: continue
        val = float(num_match[0])
        food_name, info = find_food_in_db(part)
        if not food_name:
            failed_items.append(f"«{part}»")
            continue
        w = val * info.get("piece_weight", 100.0) if "шт" in part else (val * 1000.0 if info.get("is_liquid") and val <= 10.0 else val)
        ratio = w / 100.0
        total_cals += info['cals'] * ratio
        total_p += info['prot'] * ratio
        total_j += info['fats'] * ratio
        total_c += info.get('carbs', info.get('car90', 0.0)) * ratio
        found_items_summary.append(f"• {food_name.split()[0].capitalize()} — {int(w)}г/мл ({round(info['cals']*ratio)} ккал)")

    if not found_items_summary:
        await message.answer("❌ Бот не смог распознать продукты. Попробуйте написать точнее.", reply_markup=get_main_keyboard())
        await state.clear()
        return
        
    report = "📊 **Результаты подсчета КБЖУ:**\n" + "\n".join(found_items_summary) + "\n\n"
    if failed_items: 
        report += "⚠️ **Не удалось найти:**\n" + "\n".join(failed_items) + "\n\n"
    report += f"🔥 **Суммарно за прием:**\n▪️ Калории: {round(total_cals, 1)} ккал\n▪️ Белки: {round(total_p, 1)} г\n▪️ Жиры: {round(total_j, 1)} г\n▪️ Углеводы: {round(total_c, 1)} г"
    await message.answer(report, reply_markup=get_main_keyboard())
    await state.clear()

async def main():
    init_db()
    if not API_TOKEN:
        sys.exit("[ОШИБКА]: Переменная BOT_TOKEN не обнаружена в окружении контейнера!")
    bot = Bot(token=API_TOKEN)
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): pass
