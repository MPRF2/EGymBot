import asyncio
import logging
import sqlite3
import sys
import os
import re
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
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
    
    # Таблица пользователей
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, height REAL, weight REAL, age INTEGER, body_type TEXT,
            strength_workouts INTEGER, cardio_workouts INTEGER, cardio_pulse INTEGER, daily_steps INTEGER,
            period_goal TEXT, target_calories REAL, target_proteins REAL, target_fats REAL, target_carbs REAL
        )
    """)
    
    # Таблица шаблонов дней для Календаря питания
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

# === БАЗА ДАННЫХ ПРОДУКТОВ ===
FOOD_DATABASE = {
    "куриное филе грудка курица куриная грудка": {"cals": 113, "prot": 23.6, "fats": 1.9, "carbs": 0.0, "cat": "Белки"},
    "куриная грудка запеченная": {"cals": 150, "prot": 30.0, "fats": 3.2, "carbs": 0.0, "cat": "Белки"},
    "яйцо куриное яйца яиц яйцо": {"cals": 157, "prot": 12.7, "fats": 11.5, "carbs": 0.7, "piece_weight": 55, "cat": "Белки"},
    "творог 5%": {"cals": 121, "prot": 17.2, "fats": 5.0, "carbs": 1.8, "cat": "Белки"},
    "протеин сывороточный порошок изолят": {"cals": 390, "prot": 75.0, "fats": 6.0, "carbs": 8.0, "cat": "Спортпит"},
    "семечки подсолнечника очищенные подсолнуха": {"cals": 580, "prot": 20.7, "fats": 52.9, "carbs": 10.5, "cat": "Жиры"},
    "овсяные хлопья геркулес овсянка": {"cals": 352, "prot": 12.0, "fats": 6.0, "carbs": 62.0, "cat": "Углеводы"},
    "гречка отварная гречневая": {"cals": 110, "prot": 4.2, "fats": 1.1, "carbs": 21.0, "cat": "Углеводы"},
    "рис белый отварной рисовая": {"cals": 130, "prot": 2.7, "fats": 0.3, "carbs": 28.0, "cat": "Углеводы"},
    "пельмени отварные": {"cals": 245, "prot": 11.3, "fats": 13.2, "carbs": 20.7, "cat": "Столовая"},
    "борщ с говядиной борща": {"cals": 60, "prot": 4.0, "fats": 3.0, "carbs": 5.0, "cat": "Столовая"}
}

CONSTRUCTOR_EXERCISES = {
    "Грудь": ["Жим штанги на наклонной 30° (Верх груди)", "Жим гантелей на горизонталке (Общая масса)", "Сведения в пег-дек / Баттерфляй (Изоляция)"],
    "Спина": ["Подтягивания с весом широким хватом", "Тяга верхнего блока к груди (Ширина спины)", "Тяга Т-грифа с упором в грудь"],
    "Плечи": ["Махи гантелями в стороны стоя (Средняя дельта)", "Жим гантелей сидя под углом 80°", "Махи в наклоне на заднюю дельту"],
    "Руки": ["Подъем штанги на бицепс с EZ-грифом", "Французский жим лежа на скамье", "Разгибания рук на верхнем блоке с канатом"],
    "Ноги": ["Приседания со штангой на спине", "Жим ногами в платформе 45 градусов", "Румынская становая тяга с гантелями"]
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
    builder.button(text="📅 Календарь питания")
    builder.button(text="📋 Мой профиль")
    builder.button(text="🏋️ Тренировки / Сплит")
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)

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

class CalendarStates(StatesGroup):
    waiting_for_day_name = State()
    waiting_for_meal_name = State()
    waiting_for_meal_time = State()

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
    except ValueError: await message.answer("Введи число:")

@dp.message(RegistrationStates.waiting_for_weight)
async def process_weight(message: types.Message, state: FSMContext):
    try:
        val = float(message.text.replace(",", "."))
        await state.update_data(weight=val)
        await message.answer("Шаг 3: Введи возраст:")
        await state.set_state(RegistrationStates.waiting_for_age)
    except ValueError: await message.answer("Введи число:")

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
    except ValueError: await message.answer("Введи число:")

@dp.callback_query(RegistrationStates.waiting_for_body_type)
async def process_bt(c: types.CallbackQuery, state: FSMContext):
    await state.update_data(body_type=c.data.split("_")[1])
    await c.message.answer("Шаг 5: Сколько силовых тренировок в неделю?")
    await state.set_state(RegistrationStates.waiting_for_strength)
    await c.answer()

@dp.message(RegistrationStates.waiting_for_strength)
async def process_str(message: types.Message, state: FSMContext):
    try:
        await state.update_data(strength_workouts=int(message.text))
        await message.answer("Шаг 6: Сколько кардио тренировок в неделю?")
        await state.set_state(RegistrationStates.waiting_for_cardio)
    except ValueError: await message.answer("Введи число:")

@dp.message(RegistrationStates.waiting_for_cardio)
async def process_card(message: types.Message, state: FSMContext):
    try:
        await state.update_data(cardio_workouts=int(message.text))
        await message.answer("Шаг 7: Укажи средний целевой пульс на кардио:")
        await state.set_state(RegistrationStates.waiting_for_pulse)
    except ValueError: await message.answer("Введи число:")

@dp.message(RegistrationStates.waiting_for_pulse)
async def process_pls(message: types.Message, state: FSMContext):
    try:
        await state.update_data(cardio_pulse=int(message.text), daily_steps=0)
        b = InlineKeyboardBuilder()
        b.button(text="🔥 Сушка / Жиросжигание", callback_data="goal_cutting")
        b.button(text="⚖️ Удержание", callback_data="goal_maintenance")
        b.button(text="💪 Массонабор", callback_data="goal_bulking")
        await message.answer("Шаг 8: Выбери цель текущего периода:", reply_markup=b.as_markup())
        await state.set_state(RegistrationStates.waiting_for_goal)
    except ValueError: await message.answer("Укажи число:")

@dp.callback_query(RegistrationStates.waiting_for_goal)
async def process_gl(c: types.CallbackQuery, state: FSMContext):
    g = c.data.split("_")[1]
    d = await state.get_data()
    bmr = (10 * d['weight']) + (6.25 * d['height']) - (5 * d['age']) + 5
    cals = bmr * 1.4
    
    if g == "cutting":
        cals -= 450
        p, j, u = d['weight'] * 2.3, d['weight'] * 0.8, (cals - (d['weight'] * 2.3 * 4) - (d['weight'] * 0.8 * 9)) / 4
        gt = "Сушка"
    elif g == "bulking":
        cals += 350
        p, j, u = d['weight'] * 2.0, d['weight'] * 1.0, (cals - (d['weight'] * 2.0 * 4) - (d['weight'] * 1.0 * 9)) / 4
        gt = "Массонабор"
    else:
        p, j, u = d['weight'] * 2.0, d['weight'] * 0.9, (cals - (d['weight'] * 2.0 * 4) - (d['weight'] * 0.9 * 9)) / 4
        gt = "Удержание"

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                   (c.from_user.id, d['height'], d['weight'], d['age'], d['body_type'], d['strength_workouts'], d['cardio_workouts'], d['cardio_pulse'], d['daily_steps'], gt, round(cals), round(p), round(j), round(u)))
    cursor.execute("INSERT OR IGNORE INTO daily_log (user_id) VALUES (?)", (c.from_user.id,))
    cursor.execute("SELECT day_id FROM meal_days WHERE user_id = ? AND is_active = 1", (c.from_user.id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO meal_days (user_id, day_name, is_active) VALUES (?, 'Основной день', 1)", (c.from_user.id,))
    conn.commit()
    conn.close()
    
    await c.message.answer(f"🎉 Профиль сохранен!\n🔥 Рекомендуемый КБЖУ: {round(cals)} ккал | Б: {round(p)}г | Ж: {round(j)}г | У: {round(u)}г", reply_markup=get_main_keyboard())
    await state.clear()
    await c.answer()

# ==================== УПРАВЛЕНИЕ ПРОФИЛЕМ И КБЖУ ====================
@dp.message(F.text == "📋 Мой профиль")
async def view_profile(message: types.Message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT height, weight, age, body_type, period_goal, target_calories, target_proteins, target_fats, target_carbs FROM users WHERE user_id = ?", (message.from_user.id,))
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
    await c.message.answer("Твой профиль полностью очищен. Давай заполним его заново!\nВведи рост в см:")
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

# --- Вариант 1: Вручную (ИСПРАВЛЕННЫЙ ХЭНДЛЕР ВЕРНУТ ТЕБЯ В МЕНЮ КНОПОК) ---
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
    
    # Сразу подтягиваем обновленные данные по этому дню, чтобы вернуть пользователя в меню
    cursor.execute("SELECT day_name, is_active FROM meal_days WHERE day_id = ?", (day_id,))
    day_info = cursor.fetchone()
    cursor.execute("SELECT meal_id, meal_name, meal_time FROM meals WHERE day_id = ? ORDER BY meal_time ASC", (day_id,))
    meals = cursor.fetchall()
    conn.close()
    
    update_scheduler_tasks()
    await state.clear()
    
    # Формируем меню дня заново, как при обычном просмотре
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
    
    # Отправляем сообщение со встроенной клавиатурой, чтобы можно было кликать дальше
    await message.answer(text, reply_markup=b.as_markup())

# --- Вариант 2: Автонастройка ботом ---
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

# Поддержка роутинга кнопок календаря
@dp.callback_query(F.data == "cal_add_day")
async def add_new_day_template(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer("Введи название шаблона:")
    await state.set_state(CalendarStates.waiting_for_day_name)
@dp.message(CalendarStates.waiting_for_day_name)
async def save_new_day_template(message: types.Message, state: FSMContext):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("INSERT INTO meal_days (user_id, day_name, is_active) VALUES (?, ?, 0)", (message.from_user.id, message.text.strip()))
    conn.commit(); conn.close()
    await message.answer("Шаблон добавлен!", reply_markup=get_main_keyboard()); await state.clear()
@dp.callback_query(F.data.startswith("calactivate_"))
async def act_day(c: types.CallbackQuery):
    d_id = int(c.data.split("_")[1])
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("UPDATE meal_days SET is_active = 0 WHERE user_id = ?", (c.from_user.id,))
    cursor.execute("UPDATE meal_days SET is_active = 1 WHERE day_id = ?", (d_id,))
    conn.commit(); conn.close(); update_scheduler_tasks()
    await manage_single_day(c)
@dp.callback_query(F.data.startswith("calclear_"))
async def clear_meals(c: types.CallbackQuery):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("DELETE FROM meals WHERE day_id = ?", (int(c.data.split("_")[1]),))
    conn.commit(); conn.close(); update_scheduler_tasks(); await manage_single_day(c)
@dp.callback_query(F.data.startswith("caldelete_"))
async def del_day(c: types.CallbackQuery):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    cursor.execute("DELETE FROM meal_days WHERE day_id = ? AND is_active = 0", (int(c.data.split("_")[1]),))
    conn.commit(); conn.close(); await show_calendar_root(c.message)
@dp.callback_query(F.data == "cal_back_root")
async def cb_root(c: types.CallbackQuery): await show_calendar_root(c.message)

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
    for idx, ex in enumerate(CONSTRUCTOR_EXERCISES.get(muscle, [])): b.button(text=ex, callback_data=f"cex_{idx}")
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
    await message.answer("📝 Введи съеденные продукты через запятую (например: `2шт яиц, 100г овсянка`):", reply_markup=types.ReplyKeyboardRemove())
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
        await message.answer("❌ Продукты не найдены в базе.", reply_markup=get_main_keyboard())
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
    if not API_TOKEN: sys.exit("[ОШИБКА]: BOT_TOKEN пуст!")
    scheduler.start()
    update_scheduler_tasks()
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: asyncio.run(main())
    except (KeyboardInterrupt, SystemExit): pass
