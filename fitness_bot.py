import asyncio
import logging
import sqlite3
import sys
import os
import re
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logging.basicConfig(level=logging.INFO)

# =========================================================
# БЕЗОПАСНОЕ ПОЛУЧЕНИЕ ТОКЕНА ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
API_TOKEN = os.getenv("BOT_TOKEN")
# =========================================================

DB_NAME = "/app/data/fitness_bot.db"
bot = Bot(token=API_TOKEN) if API_TOKEN else None
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

def init_db():
    os.makedirs(os.path.dirname(DB_NAME), exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Обновленная таблица пользователей под новые параметры
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            height REAL, 
            weight REAL, 
            age INTEGER, 
            strength_workouts INTEGER, 
            body_fat REAL,
            daily_steps INTEGER,
            cardio_per_week INTEGER,
            cardio_minutes INTEGER,
            cardio_pulse TEXT,
            experience TEXT,
            period_goal TEXT, 
            target_calories REAL, 
            target_proteins REAL, 
            target_fats REAL, 
            target_carbs REAL
        )
    """)
    
    # Таблица templates дней для Календаря питания
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meal_days (
            day_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            day_name TEXT,
            is_active INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)
    
    # Таблица конкретных приемов пищи в шаблоне
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            meal_id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_id INTEGER,
            meal_name TEXT,
            meal_time TEXT, 
            FOREIGN KEY(day_id) REFERENCES meal_days(day_id) ON DELETE CASCADE
        )
    """)

    # Таблица сохраненных тренировок
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            day_of_week TEXT,
            exercise_name TEXT,
            muscle_group TEXT,
            sets TEXT,
            reps TEXT
        )
    """)

    # Таблица лога съеденного за день (счетчик калорий)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_log (
            user_id INTEGER,
            calories REAL DEFAULT 0,
            proteins REAL DEFAULT 0,
            fats REAL DEFAULT 0,
            carbs REAL DEFAULT 0,
            PRIMARY KEY (user_id)
        )
    """)
    
    conn.commit()
    conn.close()

# === МАСШТАБИРОВАННАЯ БАЗА ДАННЫХ ПРОДУКТОВ ===
FOOD_DATABASE = {
    # --- БЕЛКОВЫЕ ПРОДУКТЫ (МЯСО, ПТИЦА, РЫБА, МОРЕПРОДУКТЫ) ---
    "куриное филе грудка курица куриная грудка сырая": {"cals": 113, "prot": 23.6, "fats": 1.9, "carbs": 0.0, "cat": "Белки"},
    "куриная грудка запеченная готовая вареная": {"cals": 150, "prot": 30.0, "fats": 3.2, "carbs": 0.0, "cat": "Белки"},
    "куриное бедро без кожи филе бедра": {"cals": 130, "prot": 20.0, "fats": 5.5, "carbs": 0.0, "cat": "Белки"},
    "индейка филе грудки индюшка индейки": {"cals": 115, "prot": 24.1, "fats": 1.7, "carbs": 0.0, "cat": "Белки"},
    "индейка запеченная отварная": {"cals": 143, "prot": 28.5, "fats": 3.1, "carbs": 0.0, "cat": "Белки"},
    "говядина вырезка постная постную": {"cals": 158, "prot": 22.2, "fats": 7.1, "carbs": 0.0, "cat": "Белки"},
    "говядина отварная тушеная": {"cals": 220, "prot": 25.0, "fats": 13.0, "carbs": 0.0, "cat": "Белки"},
    "фарш из говядины легкий постный": {"cals": 190, "prot": 20.0, "fats": 12.0, "carbs": 0.0, "cat": "Белки"},
    "минтай филе рыба": {"cals": 72, "prot": 16.0, "fats": 0.9, "carbs": 0.0, "cat": "Белки"},
    "треска филе": {"cals": 78, "prot": 17.5, "fats": 0.6, "carbs": 0.0, "cat": "Белки"},
    "горбуша слабосоленая запеченная": {"cals": 142, "prot": 21.0, "fats": 6.5, "carbs": 0.0, "cat": "Белки"},
    "семга лосось филе форель": {"cals": 203, "prot": 22.5, "fats": 12.5, "carbs": 0.0, "cat": "Белки"},
    "тунец в собственном соку консерва": {"cals": 101, "prot": 23.0, "fats": 1.0, "carbs": 0.0, "cat": "Белки"},
    "crevetki отварные очищенные морепродукты": {"cals": 95, "prot": 22.0, "fats": 1.0, "carbs": 0.0, "cat": "Белки"},
    "кальмар филе кальмара": {"cals": 100, "prot": 18.0, "fats": 2.2, "carbs": 2.0, "cat": "Белки"},
    
    # --- ЯЙЦА И МОЛОЧНЫЕ ПРОДУКТЫ ---
    "яйцо куриное яйца яиц яйцо": {"cals": 157, "prot": 12.7, "fats": 11.5, "carbs": 0.7, "piece_weight": 55, "cat": "Белки"},
    "яичный белок белки от яиц": {"cals": 44, "prot": 11.1, "fats": 0.0, "carbs": 1.0, "piece_weight": 35, "cat": "Белки"},
    "творог 0% 1% обезжиренный": {"cals": 80, "prot": 16.5, "fats": 0.5, "carbs": 2.0, "cat": "Белки"},
    "творог 5%": {"cals": 121, "prot": 17.2, "fats": 5.0, "carbs": 1.8, "cat": "Белки"},
    "творог 9%": {"cals": 159, "prot": 16.0, "fats": 9.0, "carbs": 2.0, "cat": "Белки"},
    "молоко 0.5% 1%": {"cals": 38, "prot": 3.0, "fats": 0.8, "carbs": 4.8, "cat": "Белки"},
    "молоко 2.5%": {"cals": 54, "prot": 2.9, "fats": 2.5, "carbs": 4.7, "cat": "Белки"},
    "кефир 1%": {"cals": 40, "prot": 2.8, "fats": 1.0, "carbs": 4.0, "cat": "Белки"},
    "йогурт греческий 0% Teos теос": {"cals": 55, "prot": 8.0, "fats": 0.0, "carbs": 3.5, "cat": "Белки"},
    "йогурт греческий 2%": {"cals": 66, "prot": 7.0, "fats": 2.0, "carbs": 4.0, "cat": "Белки"},
    "сыр легкий 15% 20%": {"cals": 260, "prot": 30.0, "fats": 15.0, "carbs": 0.0, "cat": "Белки"},
    "сыр сулугуни моцарелла": {"cals": 280, "prot": 22.0, "fats": 20.0, "carbs": 0.0, "cat": "Белки"},
    "сыр российский голландский 45%": {"cals": 350, "prot": 25.0, "fats": 26.0, "carbs": 0.0, "cat": "Жиры"},

    # --- СЛОЖНЫЕ И ПРОСТЫЕ УГЛЕВОДЫ (КРУПЫ, МАКАРОНЫ, ХЛЕБ) ---
    "овсяные хлопья геркулес овсянка сухая": {"cals": 352, "prot": 12.0, "fats": 6.0, "carbs": 62.0, "cat": "Углеводы"},
    "овсянка на воде готовая каша": {"cals": 88, "prot": 3.0, "fats": 1.5, "carbs": 15.0, "cat": "Углеводы"},
    "гречка сухая крупа гречневая": {"cals": 330, "prot": 12.6, "fats": 3.3, "carbs": 62.1, "cat": "Углеводы"},
    "гречка отварная гречневая готовая": {"cals": 110, "prot": 4.2, "fats": 1.1, "carbs": 21.0, "cat": "Углеводы"},
    "рис белый сухой": {"cals": 344, "prot": 6.7, "fats": 0.7, "carbs": 78.9, "cat": "Углеводы"},
    "рис белый отварной рисовая": {"cals": 130, "prot": 2.7, "fats": 0.3, "carbs": 28.0, "cat": "Углеводы"},
    "рис бурый коричневый сухой": {"cals": 331, "prot": 7.5, "fats": 2.5, "carbs": 70.0, "cat": "Углеводы"},
    "рис бурый отварной": {"cals": 115, "prot": 2.6, "fats": 0.8, "carbs": 23.0, "cat": "Углеводы"},
    "макароны твердых сортов сухие спагетти": {"cals": 350, "prot": 12.0, "fats": 1.5, "carbs": 71.0, "cat": "Углеводы"},
    "макароны отварные паста готовые": {"cals": 140, "prot": 5.0, "fats": 0.6, "carbs": 28.0, "cat": "Углеводы"},
    "булгур сухой": {"cals": 342, "prot": 12.0, "fats": 1.5, "carbs": 69.0, "cat": "Углеводы"},
    "булгур отварной": {"cals": 122, "prot": 3.5, "fats": 0.5, "carbs": 25.0, "cat": "Углеводы"},
    "кускус сухой": {"cals": 360, "prot": 12.8, "fats": 0.6, "carbs": 72.0, "cat": "Углеводы"},
    "перловка сухая перловая": {"cals": 320, "prot": 9.5, "fats": 1.0, "carbs": 67.0, "cat": "Углеводы"},
    "картофель сырой": {"cals": 77, "prot": 2.0, "fats": 0.4, "carbs": 16.3, "cat": "Углеводы"},
    "картофель отварной вареный": {"cals": 82, "prot": 2.0, "fats": 0.4, "carbs": 16.7, "cat": "Углеводы"},
    "картофельное пюре с молоком": {"cals": 106, "prot": 2.2, "fats": 4.0, "carbs": 15.0, "cat": "Углеводы"},
    "хлеб цельнозерновой ржаной бородинский": {"cals": 220, "prot": 7.0, "fats": 1.5, "carbs": 43.0, "cat": "Углеводы"},
    "хлеб белый пшеничный батон хлеба": {"cals": 260, "prot": 8.0, "fats": 2.5, "carbs": 50.0, "cat": "Углеводы"},
    "хлебцы доктор кернер хлебец": {"cals": 300, "prot": 9.0, "fats": 2.0, "carbs": 58.0, "piece_weight": 10, "cat": "Углеводы"},
    "банан бананы баре": {"cals": 95, "prot": 1.5, "fats": 0.2, "carbs": 22.0, "piece_weight": 120, "cat": "Углеводы"},
    "яблоко яблоки": {"cals": 47, "prot": 0.4, "fats": 0.4, "carbs": 10.0, "piece_weight": 150, "cat": "Углеводы"},

    # --- ИСТОЧНИКИ ПОЛЕЗНЫХ ЖИРОВ (ОРЕХИ, СЕМЕЧКИ, МАСЛА) ---
    "семечки подсолнечника очищенные подсолнуха жареные": {"cals": 580, "prot": 20.7, "fats": 52.9, "carbs": 10.5, "cat": "Жиры"},
    "семена тыквы тыквенные семечки": {"cals": 556, "prot": 24.5, "fats": 45.8, "carbs": 13.0, "cat": "Жиры"},
    "миндаль орех": {"cals": 609, "prot": 18.5, "fats": 53.0, "carbs": 13.0, "cat": "Жиры"},
    "грецкий орех грецкие орехи": {"cals": 654, "prot": 15.2, "fats": 65.2, "carbs": 7.0, "cat": "Жиры"},
    "арахис": {"cals": 552, "prot": 26.3, "fats": 45.2, "carbs": 10.0, "cat": "Жиры"},
    "арахисовая паста без сахара": {"cals": 590, "prot": 24.0, "fats": 50.0, "carbs": 12.0, "cat": "Жиры"},
    "кешью": {"cals": 600, "prot": 18.0, "fats": 48.0, "carbs": 22.0, "cat": "Жиры"},
    "фундук лесной орех": {"cals": 651, "prot": 15.0, "fats": 61.5, "carbs": 10.0, "cat": "Жиры"},
    "авокадо": {"cals": 160, "prot": 2.0, "fats": 14.7, "carbs": 6.7, "cat": "Жиры"},
    "масло оливковое подсолнечное растительное кокосовое": {"cals": 899, "prot": 0.0, "fats": 99.9, "carbs": 0.0, "cat": "Жиры"},
    "масло сливочное 82%": {"cals": 748, "prot": 0.6, "fats": 82.5, "carbs": 0.8, "cat": "Жиры"},

    # --- СПОРТИВНОЕ ПИТАНИЕ ---
    "протеин сывороточный порошок изолят": {"cals": 390, "prot": 75.0, "fats": 6.0, "carbs": 8.0, "cat": "Спортпит"},
    "гейнер белково-углеводный": {"cals": 380, "prot": 25.0, "fats": 3.0, "carbs": 63.0, "cat": "Спортпит"},
    "казеин ночной протеин": {"cals": 360, "prot": 80.0, "fats": 1.5, "carbs": 3.0, "cat": "Спортпит"},
    "протеиновый батончик протеиновые": {"cals": 350, "prot": 33.0, "fats": 10.0, "carbs": 25.0, "piece_weight": 60, "cat": "Спортпит"},

    # --- БЛЮДА СТОЛОВОЙ / ОБЩЕПИТ / ПЕЛЬМЕНИ ---
    "пельмени отварные": {"cals": 245, "prot": 11.3, "fats": 13.2, "carbs": 20.7, "cat": "Столовая"},
    "борщ с говядиной борща": {"cals": 60, "prot": 4.0, "fats": 3.0, "carbs": 5.0, "cat": "Столовая"},
    "суп куриный с лапшой вермишелевый": {"cals": 50, "prot": 3.5, "fats": 2.0, "carbs": 4.5, "cat": "Столовая"},
    "суп гороховый с копченостями": {"cals": 75, "prot": 4.5, "fats": 3.8, "carbs": 6.5, "cat": "Столовая"},
    "котлета домашняя свино-говяжья мясная": {"cals": 260, "prot": 15.0, "fats": 18.0, "carbs": 9.0, "piece_weight": 90, "cat": "Столовая"},
    "котлета куриная паровая": {"cals": 140, "prot": 18.0, "fats": 6.0, "carbs": 4.0, "piece_weight": 80, "cat": "Столовая"}
}

# === МАСШТАБИРОВАННАЯ БАЗА УПРАЖНЕНИЙ (МАСШТАБ УВЕЛИЧЕН В 50+ РАЗ) ===
CONSTRUCTOR_EXERCISES = {
    "Грудь (Верхний пучок)": [
        "Жим штанги на наклонной скамье 30°",
        "Жим гантелей на наклонной скамье",
        "Жим в тренажере Смита на наклонной скамье",
        "Разведение гантелей на наклонной скамье",
        "Сведения рук в кроссовере снизу вверх",
        "Жим в наклонном хаммере на верх груди",
        "Жим гантелей хватом 'хаммер' под углом",
        "Наклонные отжимания от пола (ноги на скамье)",
        "Сведения рук на наклонной скамье в кроссовере",
        "Жим штанги обратным хватом на наклонной скамье",
        "Разведение рук с амортизатором снизу вверх",
        "Жим гири одной рукой на наклонной скамье",
        "Пуловер на наклонной скамье с гантелью",
        "Жим Свенда с блином перед собой под углом",
        "Сведения в наклонном тренажере Pec-Deck"
    ],
    "Грудь (Средний/Нижний пучок)": [
        "Жим штанги лежа горизонтально",
        "Жим гантелей лежа на горизонтальной скамье",
        "Жим в тренажере Hammer (Хаммер) на грудь",
        "Сведения в тренажере Пег-Дек (Баттерфляй)",
        "Отжимания на брусьях с акцентом на грудь",
        "Жим штанги на скамье с обратным наклоном",
        "Жим гантелей на скамье с обратным наклоном",
        "Сведения рук в кроссовере сверху вниз",
        "Отжимания от пола широким хватом",
        "Жим в Смите горизонтально",
        "Жим Свенда стоя с двумя блинами",
        "Сведения рук в кроссовере параллельно полу",
        "Отжимания от пола с весом на спине",
        "Жим в изоляционном тренажере на нижнюю часть груди",
        "Разведение гантелей на горизонтальной скамье"
    ],
    "Спина (Ширина / Лат.)": [
        "Подтягивания широким хватом с весом",
        "Тяга верхнего блока к груди широким хватом",
        "Тяга верхнего блока параллельным хватом",
        "Пуловер на верхнем блоке с канатом / рукоятью",
        "Тяга блока за голову",
        "Тяга верхнего блока одной рукой сидя",
        "Подтягивания узким обратным хватом",
        "Тяга в вертикальном Хаммере на широчайшие",
        "Пуловер с гантелью лежа горизонтально",
        "Тяга верхнего блока к груди обратным хватом",
        "Подтягивания параллельным хватом",
        "Тяга горизонтального блока к поясу широким хватом",
        "Тяга верхнего блока с изогнутой рукоятью (коромысло)",
        "Австралийские подтягивания широким хватом",
        "Пуловер на блоке прямой рукоятью стоя"
    ],
    "Спина (Толщина / Плотность)": [
        "Тяга штанги в наклоне (прямой/обратный хват)",
        "Тяга Т-грифа с упором в грудь",
        "Тяга гантели к поясу в наклоне одной рукой",
        "Горизонтальная тяга в Смите / рычажная тяга",
        "Становая тяга со стоек (Rack Pulls)",
        "Становая тяга классическая с пола",
        "Тяга Т-грифа без упора (свободный вес)",
        "Тяга Пендли (штанга с пола в каждом повторе)",
        "Тяга горизонтального блока к поясу узким хватом",
        "Рычажная тяга в Хаммере поочередно",
        "Гиперэкстензия с весом в руках",
        "Тяга двух гантелей в наклоне на скамье животом вниз",
        "Тяга Крока (тяжелая тяга гантели с читингом)",
        "Шраги со штангой перед собой (трапеции)",
        "Шраги с гантелями стоя"
    ],
    "Плечи (Средняя дельта — Пропорции)": [
        "Махи гантелями в стороны стоя",
        "Махи в стороны на среднюю дельту в кроссовере",
        "Отводы рук в стороны в тренажере",
        "Тяга штанги к подбородку широким хватом",
        "Махи гантелями в стороны сидя",
        "Махи одной рукой в сторону у нижнего блока",
        "Тяга за тросы в кроссовере на среднюю дельту",
        "Махи гантелями в стороны лежа на боку (наклонная скамья)",
        "Тяга Ли Хейни сзади со штангой (акцент на среднюю/заднюю)",
        "Махи гирями в стороны стоя",
        "Махи в стороны с удержанием в пиковой точке 2 секунды",
        "Частичные махи тяжелыми гантелями в стороны (метод ковбоя)",
        "Махи из-за спины на нижнем блоке одной рукой",
        "Тяга к подбородку с гантелями широким хватом",
        "Подъем блина в стороны двумя руками (редкое движение)"
    ],
    "Плечи (Передняя/Задняя дельта)": [
        "Жим гантелей сидя под углом 75-80°",
        "Армейский жим штанги стоя / сидя",
        "Махи гантелями в наклоне на заднюю дельту",
        "Разведения рук назад в тренажере (Reverse Fly)",
        "Тяга Ли Хейни на заднюю дельту",
        "Жим Арнольда сидя",
        "Махи перед собой с гантелями попеременно",
        "Подъем блина перед собой на переднюю дельту",
        "Разведение рук назад в кроссовере (Face Pulls / Тяга к лицу)",
        "Махи гантелями на заднюю дельту лежа на животе (на скамье)",
        "Жим штанги из-за головы сидя",
        "Махи перед собой на нижнем блоке с канатом",
        "Разведения назад у пег-дек одной рукой",
        "Жим гантелей стоя параллельным хватом",
        "Махи назад с тросом в кроссовере без рукояток"
    ],
    "Руки (Бицепс)": [
        "Подъем штанги на бицепс с EZ-грифом стоя",
        "Подъем гантелей на бицепс на наклонной скамье",
        "Сгибания Скотта с EZ-штангой / гантелью",
        "Молотковые сгибания с гантелями (Хаммер)",
        "Концентрированные сгибания рук с гантелью",
        "Подъем штанги на бицепс прямым грифом стоя",
        "Сгибания рук в кроссовере у верхних блоков (Братья КУ)",
        "Сгибания 'Паук' (лежишь животом на наклонной скамье)",
        "Подъем гантелей на бицепс стоя с супинацией",
        "Сгибания рук на нижнем блоке с канатом (Хаммер-блок)",
        "Сгибания рук в тренажере Скотта (блочный тренажер)",
        "Молотковые сгибания с уводом руки вовнутрь (Cross Body)",
        "Подъем штанги на бицепс обратным хватом (брахиарадиалис)",
        "Сгибания Зоттмана с гантелями",
        "Подъем гантелей на бицепс сидя на горизонтальной скамье"
    ],
    "Руки (Трицепс)": [
        "Французский жим лежа со штангой / гантелями",
        "Разгибания рук на верхнем блоке с канатом",
        "Жим штанги узким хватом горизонтально",
        "Разгибание руки из-за головы с гантелью / блока",
        "Отжимания на брусьях на трицепс (вертикально)",
        "Французский жим стоя с EZ-грифом из-за головы",
        "Разгибания рук на блоке прямой рукоятью книзу",
        "Разгибания одной руки обратным хватом на блоке",
        "Кикбэк (Kickback) с гантелью в наклоне",
        "Отжимания от скамьи сзади (провалы)",
        "Калифорнийский жим штанги (гибрид жима узким и фр. жима)",
        "Разгибания рук с канатом из-за головы у нижнего блока",
        "Кикбэк в кроссовере у нижнего блока",
        "Жим Смита узким хватом",
        "Отжимания от пола узким хватом (алмазные)"
    ],
    "Ноги (Квадрицепс / Общий объем)": [
        "Приседания со штангой на спине (низкий/высокий гриф)",
        "Жим ногами в платформе 45 градусов",
        "Гакк-приседания в тренажере",
        "Разгибания ног сидя в тренажере (Изоляция)",
        "Выпады с гантелями на месте / в шаге",
        "Фронтальные приседания со штангой на груди",
        "Сисси-приседания (Sissy Squats)",
        "Приседания в тренажере Смита с выносом ног вперед",
        "Болгарские сплит-приседания с гантелями",
        "Шаги на тумбу с гантелями в руках",
        "Приседания плие с гирей / гантелью между ног",
        "Кубковые приседания (Goblet Squat) с гантелью перед грудью",
        "Выпады назад попеременно",
        "Жим ногами в платформе одной рукой / одной ногой",
        "Приседания со штангой над головой (оверхед)"
    ],
    "Ноги (Бицепс бедра / Голень)": [
        "Румынская становая тяга со штангой / гантелями",
        "Сгибания ног лежа в тренажере",
        "Сгибания ног сидя в тренажере",
        "Подъемы на носки стоя в тренажере (голень)",
        "Подъемы на носки сидя в тренажере",
        "Мертвая тяга (на прямых ногах)",
        "Сгибания ног стоя поочередно в тренажере",
        "Гиперэкстензия с акцентом на бицепс бедра и ягодицы",
        "Подъемы 'Ослик' на голень (с партнером или в тренажере)",
        "Подъемы на носки в тренажере для жима ногами",
        "Ягодичный мостик со штангой на скамье",
        "Тяга Кинга (приседания на одной ноге в наклоне)",
        "Сгибания ног с фитболом лежа на полу",
        "Подъемы на носки стоя на одной ноге с гантелью",
        "Разведение ног в тренажере сидя (ягодичные)"
    ]
}

def Лемматизатор_Мини(text):
    text = text.lower().strip()
    text = re.sub(r'(ой|и|ы|а|я|у|е|ом|ам|ами|ях|кой|ной|ки|ка|ку|цы|ца|цу|ей|ьями|ьях|ов|ей|ным|ное|ная)$', '', text)
    return text

def find_food_in_db(raw_part):
    clean_text = raw_part.lower().strip()
    clean_text = re.sub(r'[\d.]+', '', clean_text)
    clean_text = re.sub(r'\b(шт|грамм|грамма|граммов|г|кг|мл|л|литр|литра|литров)\b', '', clean_text)
    words = [Лемматизатор_Мини(w) for w in re.findall(r'[а-яА-Яa-zada-zA-Z0-9%]+', clean_text) if len(w) > 1]
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
    builder.button(text="📅 Календарь питания")
    builder.button(text="📋 Мой профиль")
    builder.button(text="🏋️ Тренировки / Сплит")
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)

def get_skip_keyboard(options: list, show_skip: bool = True):
    builder = ReplyKeyboardBuilder()
    for opt in options:
        builder.button(text=opt)
    builder.adjust(1)
    if show_skip:
        builder.row(types.KeyboardButton(text="⏩ Пропустить"))
    return builder.as_markup(resize_keyboard=True, one_time_keyboard=True)

async def send_meal_reminder(user_id: int, text: str):
    try:
        await bot.send_message(user_id, text)
    except Exception as e:
        logging.error(f"Ошибка отправки уведомления {user_id}: {e}")

def update_scheduler_tasks():
    scheduler.remove_all_jobs()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT md.user_id, m.meal_name, m.meal_time 
        FROM meals m
        JOIN meal_days md ON m.day_id = md.day_id
        WHERE md.is_active = 1
    """)
    reminders = cursor.fetchall()
    conn.close()

    for user_id, name, time_str in reminders:
        try:
            t = datetime.strptime(time_str, "%H:%M")
            scheduler.add_job(send_meal_reminder, CronTrigger(hour=t.hour, minute=t.minute), args=[user_id, f"⏰ Время пришло! Пора кушать: **{name}** ({time_str})"])
            t_minus_30 = t - timedelta(minutes=30)
            scheduler.add_job(send_meal_reminder, CronTrigger(hour=t_minus_30.hour, minute=t_minus_30.minute), args=[user_id, f"🔔 Напоминание: Через 30 минут прием пищи — **{name}** ({time_str})."])
        except Exception as e:
            logging.error(f"Ошибка планирования {user_id}: {e}")

class RegistrationStates(StatesGroup):
    waiting_for_height = State()
    waiting_for_weight = State()
    waiting_for_age = State()
    waiting_for_strength = State()
    waiting_for_body_fat = State()
    waiting_for_steps = State()
    waiting_for_cardio_per_week = State()
    waiting_for_cardio_minutes = State()
    waiting_for_cardio_pulse = State()
    waiting_for_experience = State()
    waiting_for_goal = State()

class FoodStates(StatesGroup):
    waiting_for_batch = State()

class ConstructorStates(StatesGroup):
    waiting_for_day = State()
    waiting_for_muscle = State()
    waiting_for_exercise = State()
    waiting_for_sets = State()
    waiting_for_reps = State()

class CalendarStates(StatesGroup):
    waiting_for_day_name = State()
    waiting_for_meal_name = State()
    waiting_for_meal_time = State()

dp = Dispatcher(storage=MemoryStorage())

# ==================== МОДУЛЬ РЕГИСТРАЦИИ (АНКЕТА) ====================

@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
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
        await message.answer("Пожалуйста, введи корректное число:")

@dp.message(RegistrationStates.waiting_for_weight)
async def process_weight(message: types.Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        await state.update_data(weight=val)
        await message.answer("Шаг 3: Введи возраст:")
        await state.set_state(RegistrationStates.waiting_for_age)
    except ValueError: 
        await message.answer("Пожалуйста, введи корректное число:")

@dp.message(RegistrationStates.waiting_for_age)
async def process_age(message: types.Message, state: FSMContext):
    try:
        val = int(message.text)
        await state.update_data(age=val)
        await message.answer("Шаг 4: Сколько силовых тренировок в неделю?")
        await state.set_state(RegistrationStates.waiting_for_strength)
    except ValueError: 
        await message.answer("Пожалуйста, введи целое число:")

@dp.message(RegistrationStates.waiting_for_strength)
async def process_strength(message: types.Message, state: FSMContext):
    try:
        val = int(message.text)
        await state.update_data(strength_workouts=val)
        kb = get_skip_keyboard(["10%", "15%", "20%", "25%"], show_skip=True)
        await message.answer("Шаг 5: Укажи процент жира в организме (опционально):", reply_markup=kb)
        await state.set_state(RegistrationStates.waiting_for_body_fat)
    except ValueError:
        await message.answer("Пожалуйста, введи число:")

@dp.message(RegistrationStates.waiting_for_body_fat)
async def process_body_fat(message: types.Message, state: FSMContext):
    if message.text != "⏩ Пропустить":
        try:
            val = float(message.text.replace("%", "").replace(",", "."))
            await state.update_data(body_fat=val)
        except ValueError:
            return await message.answer("Выбери вариант из меню или введи число.")
            
    kb = get_skip_keyboard(["5000", "10000", "15000"], show_skip=True)
    await message.answer("Шаг 6: Укажи среднее количество шагов в день (опционально):", reply_markup=kb)
    await state.set_state(RegistrationStates.waiting_for_steps)

@dp.message(RegistrationStates.waiting_for_steps)
async def process_steps(message: types.Message, state: FSMContext):
    if message.text != "⏩ Пропустить":
        try:
            val = int(message.text.replace(" ", ""))
            await state.update_data(daily_steps=val)
        except ValueError:
            return await message.answer("Выбери вариант или введи число шагов.")
            
    kb = get_skip_keyboard(["1", "2", "3", "4"], show_skip=True)
    await message.answer("Шаг 7: Сколько кардио-тренировок в неделю? (опционально):", reply_markup=kb)
    await state.set_state(RegistrationStates.waiting_for_cardio_per_week)

@dp.message(RegistrationStates.waiting_for_cardio_per_week)
async def process_cardio_week(message: types.Message, state: FSMContext):
    if message.text != "⏩ Пропустить":
        try:
            val = int(message.text)
            await state.update_data(cardio_per_week=val)
            kb = get_skip_keyboard(["30 минут", "45 минут", "60 минут"], show_skip=True)
            await message.answer("Шаг 8: Сколько минут длится ОДНА кардио-сессия? (опционально):", reply_markup=kb)
            await state.set_state(RegistrationStates.waiting_for_cardio_minutes)
        except ValueError:
            return await message.answer("Введи число.")
    else:
        kb = get_skip_keyboard(["Новичок (до 1 года)", "Средний (1-3 года)", "Продвинутый (3+ лет)"], show_skip=True)
        await message.answer("Шаг 10: Укажи свой стаж тренировок (опционально):", reply_markup=kb)
        await state.set_state(RegistrationStates.waiting_for_experience)

@dp.message(RegistrationStates.waiting_for_cardio_minutes)
async def process_cardio_minutes(message: types.Message, state: FSMContext):
    if message.text != "⏩ Пропустить":
        try:
            val = int(message.text.split()[0])
            await state.update_data(cardio_minutes=val)
            kb = get_skip_keyboard(["110-120", "120-130", "130-140"], show_skip=True)
            await message.answer("Шаг 9: Укажи средний целевой пульс на кардио (опционально):", reply_markup=kb)
            await state.set_state(RegistrationStates.waiting_for_cardio_pulse)
        except ValueError:
            return await message.answer("Укажи время в минутах.")
    else:
        kb = get_skip_keyboard(["Новичок (до 1 года)", "Средний (1-3 года)", "Продвинутый (3+ лет)"], show_skip=True)
        await message.answer("Шаг 10: Укажи свой стаж тренировок (опционально):", reply_markup=kb)
        await state.set_state(RegistrationStates.waiting_for_experience)

@dp.message(RegistrationStates.waiting_for_cardio_pulse)
async def process_cardio_pulse(message: types.Message, state: FSMContext):
    if message.text != "⏩ Пропустить":
        await state.update_data(cardio_pulse=message.text.strip())
        
    kb = get_skip_keyboard(["Новичок (до 1 года)", "Средний (1-3 года)", "Продвинутый (3+ лет)"], show_skip=True)
    await message.answer("Шаг 10: Укажи свой стаж тренировок (опционально):", reply_markup=kb)
    await state.set_state(RegistrationStates.waiting_for_experience)

@dp.message(RegistrationStates.waiting_for_experience)
async def process_experience(message: types.Message, state: FSMContext):
    if message.text != "⏩ Пропустить":
        await state.update_data(experience=message.text.strip())
        
    b = InlineKeyboardBuilder()
    b.button(text="🔥 Сушка / Жиросжигание", callback_data="goal_cutting")
    b.button(text="⚖️ Удержание", callback_data="goal_maintenance")
    b.button(text="💪 Массонабор", callback_data="goal_bulking")
    await message.answer("Шаг 11: Выбери цель текущего периода (обязательно):", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.waiting_for_goal)

@dp.callback_query(RegistrationStates.waiting_for_goal)
async def process_final_calculations(c: types.CallbackQuery, state: FSMContext):
    g = c.data.split("_")[1]
    d = await state.get_data()
    
    height = d['height']
    weight = d['weight']
    age = d['age']
    strength_workouts = d['strength_workouts']
    body_fat = d.get('body_fat', None)
    daily_steps = d.get('daily_steps', 6000)
    cardio_per_week = d.get('cardio_per_week', 0)
    cardio_minutes = d.get('cardio_minutes', 0)
    cardio_pulse = d.get('cardio_pulse', "Не указан")
    experience = d.get('experience', "Средний")

    if body_fat is not None:
        lbm = weight * (1 - body_fat / 100)
        bmr = 370 + (21.6 * lbm)
        method = "Кэтча-МакАрдла (по сухой массе)"
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        method = "Миффлина-Сан Жеора (базовая)"

    exp_modifier = 1.0
    if "Средний" in experience: exp_modifier = 1.2
    elif "Продвинутый" in experience: exp_modifier = 1.4

    strength_energy = (strength_workouts * 350 * exp_modifier) / 7
    steps_energy = (daily_steps - 4000) * 0.04 if daily_steps > 4000 else 0
    cardio_energy = (cardio_per_week * cardio_minutes * 8) / 7
    
    tdee = bmr + strength_energy + steps_energy + cardio_energy
    tdee = tdee * 1.1

    if g == "cutting":
        cals = tdee - 450
        p = weight * 2.3
        j = weight * 0.8
        u = (cals - (p * 4) - (j * 9)) / 4
        gt = "Сушка"
    elif g == "bulking":
        cals = tdee + 350
        p = weight * 2.0
        j = weight * 1.0
        u = (cals - (p * 4) - (j * 9)) / 4
        gt = "Массонабор"
    else:
        cals = tdee
        p = weight * 2.0
        j = weight * 0.9
        u = (cals - (p * 4) - (j * 9)) / 4
        gt = "Удержание"

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (c.from_user.id, height, weight, age, strength_workouts, body_fat, daily_steps, 
          cardio_per_week, cardio_minutes, cardio_pulse, experience, gt, round(cals), round(p), round(j), round(u)))
    
    cursor.execute("INSERT OR IGNORE INTO daily_log (user_id) VALUES (?)", (c.from_user.id,))
    
    cursor.execute("SELECT day_id FROM meal_days WHERE user_id = ? AND is_active = 1", (c.from_user.id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO meal_days (user_id, day_name, is_active) VALUES (?, 'Основной день', 1)", (c.from_user.id,))
    conn.commit()
    conn.close()
    
    update_scheduler_tasks()
    
    report_text = (
        f"🎉 **Профиль успешно сохранен!**\n\n"
        f"• Метод расчета: {method}\n"
        f"• Твой стаж: {experience}\n"
        f"• Цель периода: **{gt}**\n\n"
        f"📊 **Рекомендуемый КБЖУ:**\n"
        f"🔥 Калории: `{round(cals)}` ккал\n"
        f"▪️ Белки: `{round(p)}`г | Жиры: `{round(j)}`г | Углеводы: `{round(u)}`г"
    )
    
    await c.message.answer(report_text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
    await state.clear()
    await c.answer()

# ==================== УПРАВЛЕНИЕ ПРОФИЛЕМ И КБЖУ ====================
@dp.message(F.text == "📋 Мой профиль")
async def view_profile(message: types.Message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT height, weight, age, experience, period_goal, target_calories, target_proteins, target_fats, target_carbs 
        FROM users WHERE user_id = ?
    """, (message.from_user.id,))
    r = cursor.fetchone()
    cursor.execute("SELECT calories, proteins, fats, carbs FROM daily_log WHERE user_id = ?", (message.from_user.id,))
    l = cursor.fetchone() or (0, 0, 0, 0)
    conn.close()

    if not r:
        await message.answer("Профиль пуст. Нажмите /start для заполнения.")
        return

    text = (f"📋 **Твой фитнес-профиль:**\n"
            f"▪️ Рост: {r[0]} см | Вес: {r[1]} кг | Возраст: {r[2]} лет ({r[3]})\n"
            f"🎯 Цель периода: **{r[4]}**\n\n"
            f"📊 **Дневной прогресс КБЖУ:**\n"
            f"🔥 Калории: {round(l[0])} / {r[5]} ккал\n"
            f"▪️ Б: {round(l[1])}/{r[6]}г | Ж: {round(l[2])}/{r[7]}г | У: {round(l[3])}/{r[8]}г\n")

    b = InlineKeyboardBuilder()
    b.button(text="🗑️ Очистить съеденное (КБЖУ)", callback_data="clear_calories")
    b.button(text="🔄 Сбросить профиль (Стереть всё)", callback_data="clear_profile")
    b.adjust(1)
    await message.answer(text, reply_markup=b.as_markup())

@dp.callback_query(F.data == "clear_calories")
async def clear_calories_callback(c: types.CallbackQuery):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO daily_log VALUES (?, 0, 0, 0, 0)", (c.from_user.id,))
    conn.commit()
    conn.close()
    await c.answer("Счетчик съеденных калорий сброшен на ноль!", show_alert=True)
    await view_profile(c.message)

@dp.callback_query(F.data == "clear_profile")
async def clear_profile_callback(c: types.CallbackQuery, state: FSMContext):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = ?", (c.from_user.id,))
    cursor.execute("DELETE FROM daily_log WHERE user_id = ?", (c.from_user.id,))
    conn.commit()
    conn.close()
    await c.answer("Данные профиля удалены.", show_alert=True)
    await c.message.answer("Твой профиль полностью очищен. Давай заполним его заново!\nВведи рост в см:", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(RegistrationStates.waiting_for_height)

# ==================== КАЛЕНДАРЬ ПИТАНИЯ ====================
@dp.message(F.text == "📅 Календарь питания")
async def show_calendar_root(message: types.Message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT day_id, day_name, is_active FROM meal_days WHERE user_id = ?", (message.from_user.id,))
    days = cursor.fetchall()
    conn.close()

    text = "📅 **Календарь питания**\nБот присылает уведомления за 30 минут до еды и вовремя.\n\n**Твои шаблоны дней:**\n"
    b = InlineKeyboardBuilder()
    for d_id, name, active in days:
        text += f"• **{name}** — {'🟢 [ОСНОВНОЙ]' if active else '⚪ Пассивный'}\n"
        b.button(text=f"⚙️ {name}", callback_data=f"calday_{d_id}")
    
    b.button(text="➕ Создать новый день", callback_data="cal_add_day")
    b.button(text="🚨 Сбросить весь календарь", callback_data="cal_reset_all")
    b.adjust(2, 1)
    await message.answer(text, reply_markup=b.as_markup())

@dp.callback_query(F.data == "cal_reset_all")
async def cal_reset_all(c: types.CallbackQuery):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM meal_days WHERE user_id = ?", (c.from_user.id,))
    cursor.execute("INSERT INTO meal_days (user_id, day_name, is_active) VALUES (?, 'Основной день', 1)", (c.from_user.id,))
    conn.commit()
    conn.close()
    update_scheduler_tasks()
    await c.answer("Все шаблоны и расписания удалены. Создан чистый 'Основной день'.", show_alert=True)
    await show_calendar_root(c.message)

@dp.callback_query(F.data.startswith("calday_"))
async def manage_single_day(c: types.CallbackQuery):
    day_id = int(c.data.split("_")[1])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT day_name, is_active FROM meal_days WHERE day_id = ?", (day_id,))
    day_info = cursor.fetchone()
    cursor.execute("SELECT meal_id, meal_name, meal_time FROM meals WHERE day_id = ? ORDER BY meal_time ASC", (day_id,))
    meals = cursor.fetchall()
    conn.close()

    if not day_info: return await c.answer("Шаблон не найден.")
    name, is_active = day_info
    
    text = f"⚙️ **День: {name}** ({'Акт.' if is_active else 'Неакт.'})\n\n**Расписание:**\n"
    text += "\n".join([f"▪️ {m_time} — {m_name}" for _, m_name, m_time in meals]) if meals else "❌ Пусто"

    b = InlineKeyboardBuilder()
    if not is_active: b.button(text="⭐ Сделать ОСНОВНЫМ", callback_data=f"calactivate_{day_id}")
    b.button(text="🤖 Автонастройка ботом", callback_data=f"calauto_{day_id}")
    b.button(text="✍️ Вписать вручную", callback_data=f"calmanual_{day_id}")
    b.button(text="🗑️ Очистить это расписание", callback_data=f"calclear_{day_id}")
    b.button(text="❌ Удалить день", callback_data=f"caldelete_{day_id}")
    b.button(text="⬅️ Назад", callback_data="cal_back_root")
    b.adjust(1)
    await c.message.edit_text(text, reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("calmanual_"))
async def manual_add_meal_start(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(target_day_id=int(c.data.split("_")[1]))
    await c.message.answer("Введите название приема пищи (например: `Завтрак`):")
    await state.set_state(CalendarStates.waiting_for_meal_name)
    await c.answer()

@dp.message(CalendarStates.waiting_for_meal_name)
async def manual_add_meal_name(message: types.Message, state: FSMContext):
    await state.update_data(new_meal_name=message.text.strip())
    await message.answer("Укажите время в формате `ЧЧ:ММ` (например: `09:00`):")
    await state.set_state(CalendarStates.waiting_for_meal_time)

@dp.message(CalendarStates.waiting_for_meal_time)
async def manual_add_meal_time(message: types.Message, state: FSMContext):
    t_str = message.text.strip()
    if not re.match(r"^(0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$", t_str):
        await message.answer("Неверный формат. Введи строго ЧЧ:ММ:")
        return
        
    d = await state.get_data()
    day_id = d['target_day_id']
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO meals (day_id, meal_name, meal_time) VALUES (?, ?, ?)", 
                   (day_id, d['new_meal_name'], t_str))
    conn.commit()
    
    cursor.execute("SELECT day_name, is_active FROM meal_days WHERE day_id = ?", (day_id,))
    day_info = cursor.fetchone()
    cursor.execute("SELECT meal_id, meal_name, meal_time FROM meals WHERE day_id = ? ORDER BY meal_time ASC", (day_id,))
    meals = cursor.fetchall()
    conn.close()
    
    update_scheduler_tasks()
    await state.clear()
    
    name, is_active = day_info
    text = f"✅ Прием «{d['new_meal_name']}» добавлен!\n\n⚙️ **День: {name}** ({'Акт.' if is_active else 'Неакт.'})\n\n**Расписание:**\n"
    text += "\n".join([f"▪️ {m_time} — {m_name}" for _, m_name, m_time in meals]) if meals else "❌ Пусто"

    b = InlineKeyboardBuilder()
    if not is_active: 
        b.button(text="⭐ Сделать ОСНОВНЫМ", callback_data=f"calactivate_{day_id}")
    b.button(text="🤖 Автонастройка ботом", callback_data=f"calauto_{day_id}")
    b.button(text="✍️ Вписать еще прием", callback_data=f"calmanual_{day_id}")
    b.button(text="🗑️ Очистить это расписание", callback_data=f"calclear_{day_id}")
    b.button(text="⬅️ Назад в календарь", callback_data="cal_back_root")
    b.adjust(1)
    
    await message.answer(text, reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("calauto_"))
async def auto_configure_meals(c: types.CallbackQuery):
    day_id = int(c.data.split("_")[1])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT period_goal FROM users WHERE user_id = ?", (c.from_user.id,))
    user_info = cursor.fetchone()
    
    if not user_info:
        conn.close()
        return await c.answer("Сначала заполни профиль через /start!", show_alert=True)
        
    goal = user_info[0]
    auto_schedule = [("🍳 Завтрак", "08:30"), ("🥩 Обед", "13:30"), ("☕ Полдник", "17:00"), ("🐟 Ужин", "20:30")] if "Сушка" in goal else [("🥞 Завтрак", "08:00"), ("🍝 Обед", "14:00"), ("🍗 Ужин", "20:00")]
        
    cursor.execute("DELETE FROM meals WHERE day_id = ?", (day_id,))
    for name, m_time in auto_schedule:
        cursor.execute("INSERT INTO meals (day_id, meal_name, meal_time) VALUES (?, ?, ?)", (day_id, name, m_time))
    conn.commit()
    conn.close()
    update_scheduler_tasks()
    await c.answer("Сгенерировано спортивное расписание!", show_alert=True)
    await manage_single_day(c)

@dp.callback_query(F.data == "cal_add_day")
async def add_new_day_template(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("Введи название шаблона:")
    await state.set_state(CalendarStates.waiting_for_day_name)

@dp.message(CalendarStates.waiting_for_day_name)
async def save_new_day_template(message: types.Message, state: FSMContext):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO meal_days (user_id, day_name, is_active) VALUES (?, ?, 0)", (message.from_user.id, message.text.strip()))
    conn.commit()
    conn.close()
    await message.answer("Шаблон добавлен!", reply_markup=get_main_keyboard())
    await state.clear()

@dp.callback_query(F.data.startswith("calactivate_{day_id}"))
async def act_day(c: types.CallbackQuery):
    d_id = int(c.data.split("_")[1])
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE meal_days SET is_active = 0 WHERE user_id = ?", (c.from_user.id,))
    cursor.execute("UPDATE meal_days SET is_active = 1 WHERE day_id = ?", (d_id,))
    conn.commit()
    conn.close()
    update_scheduler_tasks()
    await manage_single_day(c)

@dp.callback_query(F.data.startswith("calclear_"))
async def clear_meals(c: types.CallbackQuery):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM meals WHERE day_id = ?", (int(c.data.split("_")[1]),))
    conn.commit()
    conn.close()
    update_scheduler_tasks()
    await manage_single_day(c)

@dp.callback_query(F.data.startswith("caldelete_"))
async def del_day(c: types.CallbackQuery):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM meal_days WHERE day_id = ? AND is_active = 0", (int(c.data.split("_")[1]),))
    conn.commit()
    conn.close()
    await show_calendar_root(c.message)

@dp.callback_query(F.data == "cal_back_root")
async def cb_root(c: types.CallbackQuery): 
    await show_calendar_root(c.message)

# ==================== КОНСТРУКТОР ТРЕНИРОВОК ====================
@dp.message(F.text == "🏋️ Тренировки / Сплит")
async def show_workout_menu(message: types.Message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT day_of_week, exercise_name, muscle_group, sets, reps FROM workouts WHERE user_id = ?", (message.from_user.id,))
    data = cursor.fetchall()
    conn.close()

    text = "🏋️ **Твой тренировочный сплит:**\n\n"
    if not data:
        text += "Сплит пока пуст. Собери тренировки кнопкой ниже."
    else:
        schedule = {}
        for day, name, muscle, sets, reps in data:
            if day not in schedule: schedule[day] = []
            schedule[day].append(f"▪️ {name} ({muscle}) — {sets}х{reps}")
        for day, ex_list in schedule.items():
            text += f"📅 **{day}**:\n" + "\n".join(ex_list) + "\n\n"

    b = InlineKeyboardBuilder()
    b.button(text="🛠️ Собрать/Добавить упражнение", callback_data="const_start")
    b.button(text="🗑️ Очистить сплит (Стереть всё)", callback_data="const_clear_all")
    b.adjust(1)
    await message.answer(text, reply_markup=b.as_markup())

@dp.callback_query(F.data == "const_clear_all")
async def clear_workout_split(c: types.CallbackQuery):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM workouts WHERE user_id = ?", (c.from_user.id,))
    conn.commit()
    conn.close()
    await c.answer("Тренировочный сплит успешно полностью очищен!", show_alert=True)
    await show_workout_menu(c.message)

@dp.callback_query(F.data == "const_start")
async def start_constructor(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    b = InlineKeyboardBuilder()
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    for day in days: b.button(text=day, callback_data=f"cday_{day}")
    b.adjust(2)
    await c.message.edit_text("🛠️ Выбери день недели для записи тренировки:", reply_markup=b.as_markup())
    await state.set_state(ConstructorStates.waiting_for_day)

@dp.callback_query(ConstructorStates.waiting_for_day, F.data.startswith("cday_"))
async def process_const_day(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(chosen_day=c.data.split("_")[1])
    b = InlineKeyboardBuilder()
    for muscle in CONSTRUCTOR_EXERCISES.keys(): b.button(text=muscle, callback_data=f"cmuscle_{muscle}")
    b.adjust(2)
    await c.message.edit_text("Выбери целевую мышечную группу:", reply_markup=b.as_markup())
    await state.set_state(ConstructorStates.waiting_for_muscle)

@dp.callback_query(ConstructorStates.waiting_for_muscle, F.data.startswith("cmuscle_"))
async def process_const_muscle(c: types.CallbackQuery, state: FSMContext):
    muscle = c.data.split("_")[1]
    await state.update_data(chosen_muscle=muscle)
    b = InlineKeyboardBuilder()
    for idx, ex in enumerate(CONSTRUCTOR_EXERCISES.get(muscle, [])): 
        b.button(text=ex, callback_data=f"cex_{idx}")
    b.adjust(1)
    await c.message.edit_text("Выбери упражнение:", reply_markup=b.as_markup())
    await state.set_state(ConstructorStates.waiting_for_exercise)

@dp.callback_query(ConstructorStates.waiting_for_exercise, F.data.startswith("cex_"))
async def process_const_exercise(c: types.CallbackQuery, state: FSMContext):
    d = await state.get_data()
    ex_name = CONSTRUCTOR_EXERCISES[d['chosen_muscle']][int(c.data.split("_")[1])]
    await state.update_data(chosen_ex_name=ex_name)
    b = InlineKeyboardBuilder()
    for s in ["1", "2", "3", "4", "5"]: b.button(text=f"{s} подх.", callback_data=f"csets_{s}")
    b.adjust(5)
    await c.message.edit_text("Укажи число рабочих подходов:", reply_markup=b.as_markup())
    await state.set_state(ConstructorStates.waiting_for_sets)

@dp.callback_query(ConstructorStates.waiting_for_sets, F.data.startswith("csets_"))
async def process_const_sets(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(chosen_sets=c.data.split("_")[1])
    b = InlineKeyboardBuilder()
    for r_opt in ["1-5", "6-8", "8-12", "12-15"]: b.button(text=r_opt, callback_data=f"creps_{r_opt}")
    b.adjust(2)
    await c.message.edit_text("Выбери рабочий диапазон повторений:", reply_markup=b.as_markup())
    await state.set_state(ConstructorStates.waiting_for_reps)

@dp.callback_query(ConstructorStates.waiting_for_reps, F.data.startswith("creps_"))
async def process_const_reps(c: types.CallbackQuery, state: FSMContext):
    reps = c.data.split("_")[1]
    d = await state.get_data()
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO workouts (user_id, day_of_week, exercise_name, muscle_group, sets, reps) VALUES (?, ?, ?, ?, ?, ?)",
                   (c.from_user.id, d['chosen_day'], d['chosen_ex_name'], d['chosen_muscle'], d['chosen_sets'], reps))
    conn.commit()
    conn.close()

    await c.answer("Упражнение добавлено в сплит!")
    await state.clear()
    await show_workout_menu(c.message)

# ==================== ДНЕВНИК ПИТАНИЯ (ДОБАВЛЕНИЕ ЕДЫ) ====================
@dp.message(F.text == "🍽️ Добавить еду")
async def eat_cmd(message: types.Message, state: FSMContext):
    await message.answer("📝 Введи съеденные продукты через запятую (например: `2шт яиц, 100г овсянка, 30г семечки`):", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(FoodStates.waiting_for_batch)

@dp.message(FoodStates.waiting_for_batch)
async def process_food_batch(message: types.Message, state: FSMContext):
    parts = message.text.split(",")
    tc, tp, tj, tu = 0.0, 0.0, 0.0, 0.0
    found_summary = []
    
    for part in parts:
        part = part.strip().lower().replace(",", ".")
        num_match = re.findall(r'[\d.]+', part)
        if not num_match: continue
        val = float(num_match[0])
        food_name, info = find_food_in_db(part)
        if not food_name: continue
        w = val * info.get("piece_weight", 100.0) if "шт" in part else val
        ratio = w / 100.0
        tc += info['cals'] * ratio
        tp += info['prot'] * ratio
        tj += info['fats'] * ratio
        tu += info.get('carbs', 0.0) * ratio
        found_summary.append(f"• {food_name.split()[0].capitalize()} {int(w)}г")

    if not found_summary:
        await message.answer("❌ Продукты не найдены в базе. Проверь написание (например: курица, овсянка, семечки, яйца).", reply_markup=get_main_keyboard())
        await state.clear()
        return

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT calories, proteins, fats, carbs FROM daily_log WHERE user_id = ?", (message.from_user.id,))
    cur = cursor.fetchone() or (0,0,0,0)
    cursor.execute("INSERT OR REPLACE INTO daily_log VALUES (?, ?, ?, ?, ?)", 
                   (message.from_user.id, cur[0]+tc, cur[1]+tp, cur[2]+tj, cur[3]+tu))
    conn.commit()
    conn.close()
    
    await message.answer(f"➕ Добавлено:\n" + "\n".join(found_summary) + f"\n\n🔥 +{round(tc)} ккал в дневной зачет!", reply_markup=get_main_keyboard())
    await state.clear()

async def main():
    init_db()
    if not API_TOKEN: sys.exit("[ОШИБКА]: BOT_TOKEN пуст! Задай переменную окружения на хостинге.")
    scheduler.start()
    update_scheduler_tasks()
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: 
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): 
        pass
