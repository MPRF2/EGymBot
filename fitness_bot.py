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

# === БАЗА ДАННЫХ ПРОДУКТОВ (РАСШИРЕНА НА 700%+) ===
FOOD_DATABASE = {
    # --- Классический Бодибилдинг / Фитнес ---
    "куриное филе грудка курица куриная грудка": {"cals": 113, "prot": 23.6, "fats": 1.9, "carbs": 0.0, "cat": "Фитнес/БЖУ"},
    "куриная грудка запеченная": {"cals": 150, "prot": 30.0, "fats": 3.2, "carbs": 0.0, "cat": "Фитнес/БЖУ"},
    "индейка филе грудки": {"cals": 115, "prot": 24.1, "fats": 2.0, "carbs": 0.0, "cat": "Фитнес/БЖУ"},
    "говядина вырезка постная": {"cals": 158, "prot": 22.2, "fats": 7.1, "carbs": 0.0, "cat": "Фитнес/БЖУ"},
    "яйцо куриное яйца яиц яйцо": {"cals": 157, "prot": 12.7, "fats": 11.5, "carbs": 0.7, "piece_weight": 55, "cat": "Фитнес/БЖУ"},
    "яичный белок жидкий": {"cals": 44, "prot": 11.1, "fats": 0.0, "carbs": 1.0, "cat": "Фитнес/БЖУ"},
    "творог 0% 1% обезжиренный": {"cals": 79, "prot": 16.5, "fats": 0.5, "carbs": 2.0, "cat": "Фитнес/БЖУ"},
    "творог 5%": {"cals": 121, "prot": 17.2, "fats": 5.0, "carbs": 1.8, "cat": "Фитнес/БЖУ"},
    "творог 9% классический": {"cals": 157, "prot": 16.0, "fats": 9.0, "carbs": 2.2, "cat": "Фитнес/БЖУ"},
    "протеин сывороточный порошок": {"cals": 390, "prot": 75.0, "fats": 6.0, "carbs": 8.0, "cat": "Фитнес/БЖУ"},
    "протеиновый батончик": {"cals": 370, "prot": 30.0, "fats": 11.0, "carbs": 25.0, "piece_weight": 60, "cat": "Фитнес/БЖУ"},
    "тунец в собственном соку": {"cals": 96, "prot": 21.0, "fats": 1.2, "carbs": 0.0, "cat": "Фитнес/БЖУ"},
    "горбуша запеченная": {"cals": 142, "prot": 21.0, "fats": 6.0, "carbs": 0.0, "cat": "Фитнес/БЖУ"},
    "лосось семга на гриле": {"cals": 230, "prot": 23.0, "fats": 15.0, "carbs": 0.0, "cat": "Фитнес/БЖУ"},
    "креветки отварные": {"cals": 95, "prot": 22.0, "fats": 1.0, "carbs": 0.2, "cat": "Фитнес/БЖУ"},
    "кальмар отварной": {"cals": 100, "prot": 18.0, "fats": 2.2, "carbs": 2.0, "cat": "Фитнес/БЖУ"},

    # --- Сложные углеводы и Жиры (Полезные добавки) ---
    "овсяные хлопья геркулес овсянка": {"cals": 352, "prot": 12.0, "fats": 6.0, "carbs": 62.0, "cat": "Углеводы/Жиры"},
    "гречка сухая крупа": {"cals": 330, "prot": 12.6, "fats": 3.3, "carbs": 64.0, "cat": "Углеводы/Жиры"},
    "гречка отварная гречневая": {"cals": 110, "prot": 4.2, "fats": 1.1, "carbs": 21.0, "cat": "Углеводы/Жиры"},
    "рис белый отварной рисовая": {"cals": 130, "prot": 2.7, "fats": 0.3, "carbs": 28.0, "cat": "Углеводы/Жиры"},
    "рис бурый коричневый отварной": {"cals": 111, "prot": 2.6, "fats": 0.9, "carbs": 23.0, "cat": "Углеводы/Жиры"},
    "макароны твердых сортов отварные": {"cals": 140, "prot": 5.0, "fats": 0.5, "carbs": 28.0, "cat": "Углеводы/Жиры"},
    "арахисовая паста без сахара": {"cals": 588, "prot": 25.0, "fats": 50.0, "carbs": 13.0, "cat": "Углеводы/Жиры"},
    "миндаль орехи": {"cals": 645, "prot": 18.6, "fats": 57.7, "carbs": 13.0, "cat": "Углеводы/Жиры"},
    "грецкий орех": {"cals": 654, "prot": 15.2, "fats": 65.2, "carbs": 7.0, "cat": "Углеводы/Жиры"},
    "семечки подсолнечника очищенные подсолнуха": {"cals": 580, "prot": 20.7, "fats": 52.9, "carbs": 10.5, "cat": "Углеводы/Жиры"},
    "оливковое масло подсолнечное": {"cals": 899, "prot": 0.0, "fats": 99.9, "carbs": 0.0, "cat": "Углеводы/Жиры"},
    "авокадо": {"cals": 160, "prot": 2.0, "fats": 14.7, "carbs": 6.7, "piece_weight": 140, "cat": "Углеводы/Жиры"},

    # --- Традиционная кухня / Столовая / Домашнее ---
    "борщ с говядиной борща": {"cals": 60, "prot": 4.0, "fats": 3.0, "carbs": 5.0, "cat": "Русская/Столовая"},
    "суп куриный с лапшой": {"cals": 45, "prot": 3.2, "fats": 1.8, "carbs": 4.0, "cat": "Русская/Столовая"},
    "щи из свежей капусты": {"cals": 31, "prot": 1.2, "fats": 1.6, "carbs": 3.2, "cat": "Русская/Столовая"},
    "суп гороховый с копченостями": {"cals": 66, "prot": 4.4, "fats": 2.6, "carbs": 6.8, "cat": "Русская/Столовая"},
    "пельмени отварные": {"cals": 245, "prot": 11.3, "fats": 13.2, "carbs": 20.7, "cat": "Русская/Столовая"},
    "вареники с картошкой": {"cals": 180, "prot": 3.5, "fats": 4.0, "carbs": 32.0, "cat": "Русская/Столовая"},
    "картофельное пюре": {"cals": 90, "prot": 2.0, "fats": 3.3, "carbs": 15.0, "cat": "Русская/Столовая"},
    "котлета домашняя свино-говяжья": {"cals": 245, "prot": 16.0, "fats": 18.0, "carbs": 6.0, "piece_weight": 80, "cat": "Русская/Столовая"},
    "котлета куриная паровая": {"cals": 135, "prot": 18.0, "fats": 5.0, "carbs": 3.5, "piece_weight": 80, "cat": "Русская/Столовая"},
    "блины со свининой или говядиной": {"cals": 195, "prot": 7.5, "fats": 8.0, "carbs": 23.0, "cat": "Русская/Столовая"},
    "сыр российский голландский": {"cals": 360, "prot": 23.0, "fats": 29.0, "carbs": 0.0, "cat": "Русская/Столовая"},
    "сыр моцарелла": {"cals": 240, "prot": 18.0, "fats": 18.0, "carbs": 1.0, "cat": "Русская/Столовая"},
    "хлеб ржаной бородинский": {"cals": 210, "prot": 6.5, "fats": 1.2, "carbs": 40.0, "cat": "Русская/Столовая"},
    "хлеб белый пшеничный тостовый": {"cals": 260, "prot": 8.0, "fats": 2.5, "carbs": 50.0, "cat": "Русская/Столовая"},

    # --- Мировая Кухня & Читмил ---
    "роллы филадельфия": {"cals": 142, "prot": 6.2, "fats": 6.1, "carbs": 15.4, "piece_weight": 35, "cat": "Мировая кухня"},
    "роллы калифорния": {"cals": 176, "prot": 5.0, "fats": 5.0, "carbs": 28.0, "piece_weight": 32, "cat": "Мировая кухня"},
    "суши с лососем": {"cals": 135, "prot": 8.0, "fats": 2.5, "carbs": 20.0, "piece_weight": 30, "cat": "Мировая кухня"},
    "суп рамэн тонкацу": {"cals": 85, "prot": 4.5, "fats": 4.0, "carbs": 8.0, "cat": "Мировая кухня"},
    "пицца маргарита": {"cals": 240, "prot": 10.1, "fats": 8.0, "carbs": 31.4, "cat": "Мировая кухня"},
    "пицца пепперони": {"cals": 290, "prot": 12.5, "fats": 14.0, "car90": 29.0, "cat": "Мировая кухня"},
    "паста карбонара": {"cals": 220, "prot": 9.0, "fats": 11.5, "carbs": 20.0, "cat": "Мировая кухня"},
    "лазанья с мясным фаршем": {"cals": 170, "prot": 9.2, "fats": 8.5, "carbs": 14.0, "cat": "Мировая кухня"},
    "бургер классический говяжий": {"cals": 254, "prot": 12.0, "fats": 10.0, "carbs": 29.0, "piece_weight": 150, "cat": "Мировая кухня"},
    "картофель фри": {"cals": 312, "prot": 3.4, "fats": 15.0, "carbs": 41.0, "cat": "Мировая кухня"},
    "куриные наггетсы": {"cals": 280, "prot": 15.0, "fats": 16.0, "carbs": 19.0, "piece_weight": 20, "cat": "Мировая кухня"},
    "шаурма с курицей донер": {"cals": 175, "prot": 9.0, "fats": 8.0, "carbs": 16.0, "piece_weight": 400, "cat": "Мировая кухня"},
    "кебаб люля из говядины": {"cals": 220, "prot": 18.0, "fats": 16.0, "carbs": 1.5, "cat": "Мировая кухня"},

    # --- Фрукты, Овощи и Напитки ---
    "банан банана бананы": {"cals": 95, "prot": 1.5, "fats": 0.2, "carbs": 21.8, "piece_weight": 120, "cat": "Фрукты/Овощи/Напитки"},
    "яблоко яблока яблоки": {"cals": 47, "prot": 0.4, "fats": 0.4, "carbs": 9.8, "piece_weight": 150, "cat": "Фрукты/Овощи/Напитки"},
    "груша": {"cals": 42, "prot": 0.4, "fats": 0.3, "carbs": 10.3, "piece_weight": 160, "cat": "Фрукты/Овощи/Напитки"},
    "апельсин": {"cals": 43, "prot": 0.9, "fats": 0.2, "carbs": 8.4, "piece_weight": 150, "cat": "Фрукты/Овощи/Напитки"},
    "томаты помидоры свежие": {"cals": 18, "prot": 0.6, "fats": 0.2, "carbs": 3.7, "cat": "Фрукты/Овощи/Напитки"},
    "огурцы свежие": {"cals": 15, "prot": 0.8, "fats": 0.1, "carbs": 2.8, "cat": "Фрукты/Овощи/Напитки"},
    "брокколи отварная": {"cals": 35, "prot": 2.4, "fats": 0.4, "carbs": 6.6, "cat": "Фрукты/Овощи/Напитки"},
    "белокочанная капуста свежая": {"cals": 25, "prot": 1.8, "fats": 0.1, "carbs": 4.7, "cat": "Фрукты/Овощи/Напитки"},
    "кока-кола кони стандарт": {"cals": 42, "prot": 0.0, "fats": 0.0, "carbs": 10.6, "is_liquid": True, "cat": "Фрукты/Овощи/Напитки"},
    "кола зеро zero без сахара": {"cals": 0.3, "prot": 0.0, "fats": 0.0, "carbs": 0.0, "is_liquid": True, "cat": "Фрукты/Овощи/Напитки"},
    "вода питьевая": {"cals": 0.0, "prot": 0.0, "fats": 0.0, "carbs": 0.0, "is_liquid": True, "cat": "Фрукты/Овощи/Напитки"},
    "молоко 2.5%": {"cals": 54, "prot": 2.9, "fats": 2.5, "carbs": 4.8, "is_liquid": True, "cat": "Фрукты/Овощи/Напитки"},
    "водка 40% водку водки": {"cals": 231, "prot": 0.0, "fats": 0.0, "carbs": 0.1, "is_liquid": True, "cat": "Фрукты/Овощи/Напитки"},
    "пиво светлое фильтрованное": {"cals": 43, "prot": 0.5, "fats": 0.0, "carbs": 3.8, "is_liquid": True, "cat": "Фрукты/Овощи/Напитки"}
}

# === АТЛАС ТРЕНИРОВОК (РАСШИРЕН НА 700%+) ===
WORKOUT_DATABASE = {
    "aesthetic": {
        "title": "🏆 Эстетика и Пропорции (Classic Physique)",
        "groups": {
            "Грудь (Ширина, Объем и Верх)": [
                "Жим штанги на наклонной скамье 30° (Акцент на верх груди)",
                "Разведение гантелей на горизонтальной или наклонной скамье",
                "Кроссовер на блоках через верх / Сведение рук в пег-дек",
                "Жим в тренажере Hammer горизонтальный / под углом",
                "Отжимания на брусьях с дополнительным весом (Низ груди)"
            ],
            "Спина (V-силуэт, Толщина и Широчайшие)": [
                "Подтягивания на турнике широким хватом с весом",
                "Тяга верхнего блока к груди (средний или параллельный хват)",
                "Тяга штанги в наклоне хватом сверху/снизу",
                "Тяга Т-грифа с упором в грудь (Толщина верха спины)",
                "Пуловер на верхнем блоке прямыми руками (Изоляция широчайших)",
                "Горизонтальная тяга в рычажном тренажере одной рукой"
            ],
            "Плечи (Дельты для визуальной ширины)": [
                "Махи гантелями в стороны стоя / сидя (Боковая дельта)",
                "Жим гантелей сидя на скамье под углом 80°",
                "Армейский жим штанги стоя от груди",
                "Махи гантелями в наклоне / Тяга на заднюю дельту в кроссовере",
                "Протяжка штанги или гантелей вдоль туловища к подбородку",
                "Махи в сторону на нижнем блоке (Постоянное напряжение)"
            ],
            "Руки (Пик бицепса и объем трицепса)": [
                "Подъем штанги на бицепс стоя (Прямой или EZ-гриф)",
                "Французский жим лежа со штангой за голову",
                "Сгибания рук «Молот» с гантелями попеременно (Брахиалис)",
                "Разгибания рук на верхнем блоке с канатной рукоятью",
                "Концентрированные сгибания на скамье Скотта",
                "Отжимания на брусьях узким хватом на трицепс"
            ],
            "Квадрицепсы и Бицепс бедра (Симметрия)": [
                "Приседания со штангой на груди (Фронтальные приседания)",
                "Гакк-приседания в тренажере (Глубокий сед)",
                "Жим ногами в платформе (Широкая/узкая постановка ног)",
                "Румынская становая тяга с гантелями или штангой",
                "Разгибания ног в тренажере сидя (Каплевидная мышца)",
                "Сгибания ног в тренажере лежа или сидя"
            ]
        }
    },
    "strength": {
        "title": "⚡ Силовой Тренинг (Пауэрлифтинг & База)",
        "groups": {
            "Приседания (Абсолютная сила)": [
                "Классический присед со штангой на низкой/высокой спине",
                "Приседания со штангой на тумбу (Пауза в нижней точке)",
                "Присед с паузой 2-3 секунды в седе",
                "Полуприседы с тяжелым весом в силовой раме"
            ],
            "Жим лежа (Сила грудных и трицепса)": [
                "Классический жим штанги лежа на горизонтальной скамье",
                "Жим лежа с соревновательной паузой на груди",
                "Жим штанги узким хватом (Развитие дожима)",
                "Жим штанги с досок / с брусков разной высоты"
            ],
            "Становая тяга (Мощь задней цепи)": [
                "Становая тяга в соревновательном стиле Сумо",
                "Классическая становая тяга с пола",
                "Тяга штанги с плинтов / с ограничителей (Выше колен)",
                "Тяга штанги стоя на подставке / из ямы (Дефицитная тяга)"
            ]
        }
    },
    "endurance": {
        "title": "🏃 Выносливость & Функционал (Кроссфит)",
        "groups": {
            "Гимнастика (Работа с весом тела)": [
                "Выходы силой на гимнастических кольцах или турнике",
                "Отжимания в стойке на руках у стены (или в киппинге)",
                "Подносы ног к перекладине в висе (Toes-to-Bar)",
                "Прыжки на тумбу 60/70 см на скорость"
            ],
            "Тяжелая атлетика (Взрывная сила)": [
                "Взятие штанги на грудь с виса или с пола (Clean)",
                "Рывок штанги тяжелоатлетический (Snatch)",
                "Трастеры со штангой или тяжелыми гантелями",
                "Швунг толчковый / классический толчок штанги"
            ],
            "Кардио / Метаболические циклы": [
                "Бёрпи с прыжком через штангу или с хлопком",
                "Двойные прыжки на скоростной скакалке (Double Unders)",
                "Гребля на эргометре Concept2 (Интервалы)",
                "Бег на средние дистанции или челночный бег"
            ]
        }
    }
}

def Лемматизатор_Мини(text):
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
    builder.button(text="📖 Атлас тренировок")
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
        await message.answer("Пожалуйста, введи корректное число (например, 95.5):")

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
    
    # Расчет базового метаболизма по Миффлину-Сан Жеору
    bmr = (10 * d['weight']) + (6.25 * d['height']) - (5 * d['age']) + 5
    cals = bmr * 1.4  # Учитываем средний коэффициент активности
    
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
    await message.answer(f"📋 **Ваш фитнес-профиль:**\n▪️ Рост: {r[0]} см\n▪️ Вес: {r[1]} кг\n▪️ Возраст: {r[2]} лет\n▪️ Тип тела: {r[3]}\n▪️ Тренировки: Силовые {r[4]}р/нед, Кардио {r[5]}р/нед (Пульс: {r[6]} уд/м)\n\n🎯 **Текущий период:** {r[7]}\n📈 **Ваша целевая норма КБЖУ:**\n🔥 {r[8]} ккал | Б: {r[9]}г | Ж: {r[10]}г | У: {r[11]}г", reply_markup=get_main_keyboard())

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
        text += f"• {i.split()[0].capitalize()}: {inf['cals']}ккал (Б:{inf['prot']}|Ж:{inf['fats']}|У:{inf['carbs']})\n"
    await c.message.answer(text, reply_markup=get_main_keyboard())
    await c.answer()

@dp.message(F.text == "📖 Атлас тренировок")
@dp.message(Command("workouts"))
async def show_workout_disciplines(message: types.Message):
    b = InlineKeyboardBuilder()
    b.button(text="🏆 Эстетика и Пропорции", callback_data="discipline_aesthetic")
    b.button(text="⚡ Силовая База", callback_data="discipline_strength")
    b.button(text="🏃 Выносливость & Функционал", callback_data="discipline_endurance")
    b.adjust(1)
    await message.answer("📊 **Атлас тренировок**\n\nВыберите дисциплину для детального просмотра упражнений:", reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("discipline_"))
async def process_discipline_selection(c: types.CallbackQuery):
    disc_key = c.data.split("_")[1]
    discipline_data = WORKOUT_DATABASE.get(disc_key)
    if not discipline_data: return
    b = InlineKeyboardBuilder()
    for group_name in discipline_data["groups"].keys():
        b.button(text=group_name, callback_data=f"wgroup_{disc_key}_{group_name[:20]}")
    b.button(text="⬅️ Назад к дисциплинам", callback_data="workout_back")
    b.adjust(1)
    await c.message.edit_text(f"✨ **{discipline_data['title']}**\n\nВыберите целевую группу:", reply_markup=b.as_markup())
    await c.answer()

@dp.callback_query(F.data.startswith("wgroup_"))
async def process_workout_group(c: types.CallbackQuery):
    data_parts = c.data.split("_")
    disc_key = data_parts[1]
    short_group_name = data_parts[2]
    
    discipline_data = WORKOUT_DATABASE.get(disc_key)
    if not discipline_data: return
    
    full_group_name = next((g for g in discipline_data["groups"].keys() if g.startswith(short_group_name)), None)
    if not full_group_name: return
    
    exercises = discipline_data["groups"][full_group_name]
    text = f"📖 **{discipline_data['title']}**\n📂 **Группа:** {full_group_name}\n\n" + "\n".join(f"🔹 {e}" for e in exercises)
    
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад к группам", callback_data=f"discipline_{disc_key}")
    b.button(text="🔝 К дисциплинам", callback_data="workout_back")
    b.adjust(1)
    await c.message.edit_text(text, reply_markup=b.as_markup())
    await c.answer()

@dp.callback_query(F.data == "workout_back")
async def process_workout_back(c: types.CallbackQuery):
    b = InlineKeyboardBuilder()
    b.button(text="🏆 Эстетика и Пропорции", callback_data="discipline_aesthetic")
    b.button(text="⚡ Силовая База", callback_data="discipline_strength")
    b.button(text="🏃 Выносливость & Функционал", callback_data="discipline_endurance")
    b.adjust(1)
    await c.message.edit_text("📊 **Атлас тренировок**\n\nВыберите дисциплину:", reply_markup=b.as_markup())
    await c.answer()

@dp.message(F.text == "🍽️ Добавить еду")
@dp.message(Command("eat"))
async def eat_cmd(message: types.Message, state: FSMContext):
    await message.answer("📝 Введи съеденные продукты через запятую.\nПример: `2шт яиц, 70г овсянка, 150г куриное филе, 30г семечки`:", reply_markup=types.ReplyKeyboardRemove())
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
        await message.answer("❌ Бот не смог распознать продукты из этого сообщения. Попробуй ввести названия ближе к базе данных бота.", reply_markup=get_main_keyboard())
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