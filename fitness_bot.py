import os
import re
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# Подключаем расширенные базы данных из соседнего файла database.py
from database import FOOD_DATABASE, EXERCISE_DATABASE

# Используем уже вписанный токен или берем его из окружения
TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE"

bot = Bot(token=TOKEN)
dp = Dispatcher()

DB_NAME = "fitness_bot.db"

# ==================== СОСТОЯНИЯ FSM (АНКЕТА И БУДИЛЬНИКИ) ====================
class RegistrationStates(StatesGroup):
    gender = State()
    age = State()
    weight = State()
    height = State()
    goal = State()
    strength_workouts = State()
    cardio_workouts = State()
    cardio_details = State()
    experience = State()
    body_fat = State()
    activity_level = State()

class FoodStates(StatesGroup):
    waiting_for_batch = State()

class AlarmStates(StatesGroup):
    waiting_for_meal_name = State()
    waiting_for_meal_time = State()

# ==================== ИНИЦИАЛИЗАЦИЯ БД ====================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            gender TEXT, age INTEGER, weight REAL, height REAL, goal TEXT,
            strength_workouts INTEGER, cardio_workouts INTEGER, 
            cardio_details TEXT, experience TEXT, body_fat REAL, activity_level TEXT,
            target_calories INTEGER, target_proteins INTEGER, target_fats INTEGER, target_carbs INTEGER,
            timezone TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_log (
            user_id INTEGER PRIMARY KEY,
            calories REAL DEFAULT 0, proteins REAL DEFAULT 0, fats REAL DEFAULT 0, carbs REAL DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            meal_name TEXT,
            meal_time TEXT,
            meal_type TEXT DEFAULT 'основной'
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ==================== СТАРТ И РЕГИСТРАЦИЯ ====================
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    
    r_builder = ReplyKeyboardBuilder()
    r_builder.button(text="📋 Мой профиль")
    r_builder.adjust(1)
    
    await message.answer(
        "👋 Привет! Давай настроим твой профиль для точного расчета КБЖУ.\n"
        "Сначала пройдем обязательные параметры, а затем ты сможешь дополнить их продвинутыми данными.",
        reply_markup=r_builder.as_markup(resize_keyboard=True)
    )
    
    b = InlineKeyboardBuilder()
    b.button(text="Мужчина", callback_data="gender_male")
    b.button(text="Женщина", callback_data="gender_female")
    await message.answer("Укажите ваш пол:", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.gender)

# --- ОБЯЗАТЕЛЬНЫЙ БЛОК ---
@dp.callback_query(RegistrationStates.gender)
async def process_gender(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    gender = "Мужчина" if c.data == "gender_male" else "Женщина"
    await state.update_data(gender=gender)
    await c.message.edit_text(f"Пол: {gender}\n\n✏️ **Возраст (сколько полных лет?):**")
    await state.set_state(RegistrationStates.age)

@dp.message(RegistrationStates.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Пожалуйста, введите число (полных лет):")
    await state.update_data(age=int(message.text))
    await message.answer("✏️ **Ваш вес в кг. Например: 70,5кг:**")
    await state.set_state(RegistrationStates.weight)

@dp.message(RegistrationStates.weight)
async def process_weight(message: types.Message, state: FSMContext):
    try:
        weight = float(message.text.lower().replace("кг", "").replace(",", ".").strip())
    except ValueError:
        return await message.answer("Введите вес корректно, например: 70.5")
    await state.update_data(weight=weight)
    await message.answer("✏️ **Ваш рост в сантиметрах. Например: 180,5:**")
    await state.set_state(RegistrationStates.height)

@dp.message(RegistrationStates.height)
async def process_height(message: types.Message, state: FSMContext):
    try:
        height = float(message.text.replace(",", ".").strip())
    except ValueError:
        return await message.answer("Введите рост корректно, например: 180.5")
    await state.update_data(height=height)
    
    b = InlineKeyboardBuilder()
    b.button(text="Сушка, дефицит", callback_data="goal_cut")
    b.button(text="Удержание", callback_data="goal_maintain")
    b.button(text="Массонабор, профицит", callback_data="goal_bulk")
    b.adjust(1)
    await message.answer("🎯 **Ваша цель:**", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.goal)

# --- ВХОД В ПРОДВИНУТЫЙ БЛОК ---
@dp.callback_query(RegistrationStates.goal)
async def process_goal(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    goals = {"goal_cut": "Сушка, дефицит", "goal_maintain": "Удержание", "goal_bulk": "Массонабор, профицит"}
    await state.update_data(goal=goals[c.data])
    
    b = InlineKeyboardBuilder()
    b.button(text="⏩ Пропустить продвинутый блок", callback_data="skip_advanced")
    
    await c.message.edit_text(
        "✨ **Обязательные данные собраны!**\n\n"
        "Теперь ты можешь ввести продвинутые параметры для более точного подсчета калорий или пропустить их.\n\n"
        "✏️ **Сколько силовых тренировок в неделю?**", 
        reply_markup=b.as_markup()
    )
    await state.set_state(RegistrationStates.strength_workouts)

@dp.message(RegistrationStates.strength_workouts)
async def process_strength(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введите число тренировок (например, 3):")
    await state.update_data(strength_workouts=int(message.text))
    
    b = InlineKeyboardBuilder()
    b.button(text="⏩ Пропустить продвинутый блок", callback_data="skip_advanced")
    await message.answer("✏️ **Сколько кардио тренировок в неделю?**", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.cardio_workouts)

@dp.message(RegistrationStates.cardio_workouts)
async def process_cardio(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введите число кардио сессий:")
    await state.update_data(cardio_workouts=int(message.text))
    
    b = InlineKeyboardBuilder()
    b.button(text="⏩ Пропустить продвинутый блок", callback_data="skip_advanced")
    await message.answer("✏️ **Длительность кардио и средний пульс. Например 60м, 125:**", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.cardio_details)

@dp.message(RegistrationStates.cardio_details)
async def process_cardio_details(message: types.Message, state: FSMContext):
    await state.update_data(cardio_details=message.text)
    
    b = InlineKeyboardBuilder()
    b.button(text="⏩ Пропустить продвинутый блок", callback_data="skip_advanced")
    await message.answer("✏️ **Стаж тренировок в зале. Например 2 года:**", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.experience)

@dp.message(RegistrationStates.experience)
async def process_experience(message: types.Message, state: FSMContext):
    await state.update_data(experience=message.text)
    
    b = InlineKeyboardBuilder()
    b.button(text="⏩ Пропустить продвинутый блок", callback_data="skip_advanced")
    await message.answer("✏️ **Ваш процент жира:**", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.body_fat)

@dp.message(RegistrationStates.body_fat)
async def process_fat(message: types.Message, state: FSMContext):
    try:
        fat = float(message.text.replace(",", ".").strip())
    except ValueError:
        return await message.answer("Введите числовое значение процента жира:")
    await state.update_data(body_fat=fat)
    
    b = InlineKeyboardBuilder()
    b.button(text="Минимальная", callback_data="act_1")
    b.button(text="Средняя", callback_data="act_2")
    b.button(text="Высокая", callback_data="act_3")
    b.adjust(3)
    await message.answer("🏃 **Дневная активность:**", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.activity_level)

@dp.callback_query(RegistrationStates.activity_level)
async def process_activity_click(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    acts = {"act_1": "Минимальная", "act_2": "Средняя", "act_3": "Высокая"}
    await state.update_data(activity_level=acts[c.data])
    await save_and_calculate_user(c.message, state, user_id=c.from_user.id)

@dp.callback_query(F.data == "skip_advanced")
async def skip_advanced_handler(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    data = await state.get_data()
    defaults = {
        "strength_workouts": 0, "cardio_workouts": 0, "cardio_details": "Нет",
        "experience": "Не указан", "body_fat": 0.0, "activity_level": "Средняя"
    }
    for key, val in defaults.items():
        if key not in data:
            await state.update_data(**{key: val})
            
    await save_and_calculate_user(c.message, state, user_id=c.from_user.id)

# ==================== МАТЕМАТИКА РАСЧЕТА СУТОЧНОЙ НОРМЫ ====================
async def save_and_calculate_user(message: types.Message, state: FSMContext, user_id: int):
    data = await state.get_data()
    await state.clear()
    
    if data['gender'] == "Мужчина":
        bmr = 10 * data['weight'] + 6.25 * data['height'] - 5 * data['age'] + 5
    else:
        bmr = 10 * data['weight'] + 6.25 * data['height'] - 5 * data['age'] - 161
        
    total_workouts = data['strength_workouts'] + data['cardio_workouts']
    if total_workouts >= 5: act_coeff = 1.55
    elif total_workouts >= 3: act_coeff = 1.375
    else: act_coeff = 1.2
    
    if data['activity_level'] == "Высокая": act_coeff += 0.1
    elif data['activity_level'] == "Минимальная": act_coeff -= 0.05
    
    maintenance = round(bmr * act_coeff)
    
    if data['goal'] == "Сушка, дефицит":
        cals = round(maintenance * 0.8)
        prot = round(data['weight'] * 2.2)
        fats = round(data['weight'] * 0.9)
    elif data['goal'] == "Массонабор, профицит":
        cals = round(maintenance * 1.15)
        prot = round(data['weight'] * 2.0)
        fats = round(data['weight'] * 1.0)
    else:
        cals = maintenance
        prot = round(data['weight'] * 1.8)
        fats = round(data['weight'] * 1.0)
        
    carbs = round((cals - (prot * 4 + fats * 9)) / 4)
    if carbs < 0: carbs = 0

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO users (user_id, gender, age, weight, height, goal, strength_workouts, cardio_workouts, cardio_details, experience, body_fat, activity_level, target_calories, target_proteins, target_fats, target_carbs)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, data['gender'], data['age'], data['weight'], data['height'], data['goal'],
        data['strength_workouts'], data['cardio_workouts'], data['cardio_details'],
        data['experience'], data['body_fat'], data['activity_level'], cals, prot, fats, carbs
    ))
    cursor.execute("INSERT OR IGNORE INTO daily_log (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

    await message.answer(
        f"🎉 **Профиль успешно настроен!**\n\n"
        f"Твоя суточная норма КБЖУ рассчитана.\n"
        f"Нажми на кнопку **📋 Мой профиль** ниже, чтобы открыть главное меню управления."
    )

# ==================== ГЛАВНЫЙ ИНТЕРФЕЙС ПРОФИЛЯ ====================
async def get_profile_data(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT gender, weight, age, height, target_calories, target_proteins, target_fats, target_carbs 
        FROM users WHERE user_id = ?
    """, (user_id,))
    r = cursor.fetchone()
    
    cursor.execute("SELECT calories, proteins, fats, carbs FROM daily_log WHERE user_id = ?", (user_id,))
    l = cursor.fetchone() or (0, 0, 0, 0)
    conn.close()
    return r, l

@dp.message(F.text == "📋 Мой профиль")
async def profile_menu_msg(message: types.Message):
    r, l = await get_profile_data(message.from_user.id)
    if not r:
        await message.answer("Профиль пуст. Нажмите /start для заполнения анкеты КБЖУ.")
        return
    
    text, markup = generate_profile_interface(r, l)
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")

def generate_profile_interface(r, l):
    text = (
        f"📋 **Профиль**\n\n"
        f"Пол: {r[0]}\n"
        f"Вес: {r[1]} кг\n"
        f"Возраст: {r[2]} лет\n"
        f"Рост: {r[3]} см\n\n"
        f"🔥 Потребление калорий:\n`{round(l[0])}` / `{r[4]}` ккал\n\n"
        f"📊 Потребление БЖУ:\n"
        f"▪️ Белки: `{round(l[1], 1)}` / `{r[5]}` г\n"
        f"▪️ Жиры: `{round(l[2], 1)}` / `{r[6]}` г\n"
        f"▪️ Углеводы: `{round(l[3], 1)}` / `{r[7]}` г"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🗑️ Сбросить профиль", callback_data="clear_profile")
    b.button(text="🍽️ Подсчет КБЖУ", callback_data="inline_eat")
    b.button(text="🏋️ Конструктор тренировок", callback_data="inline_workout")
    b.button(text="📖 Menu еды в базе", callback_data="view_food_db")
    b.button(text="📅 Календарь приема пищи", callback_data="food_calendar")
    b.button(text="🍎 Рассчитать рацион питания", callback_data="calc_diet_menu")
    b.adjust(2, 2, 1, 1)
    return text, b.as_markup()

# ==================== ОБРАБОТЧИКИ ФУНКЦИЙ МЕНЮ ====================
@dp.callback_query(F.data == "clear_profile")
async def clear_profile_handler(c: types.CallbackQuery):
    await c.answer()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = ?", (c.from_user.id,))
    cursor.execute("DELETE FROM daily_log WHERE user_id = ?", (c.from_user.id,))
    cursor.execute("DELETE FROM user_meals WHERE user_id = ?", (c.from_user.id,))
    conn.commit()
    conn.close()
    await c.message.edit_text("💥 Профиль сброшен. Для повторного заполнения анкеты отправь команду /start")

@dp.callback_query(F.data == "inline_eat")
async def inline_eat_handler(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    await c.message.answer("📝 Введите съеденные продукты через запятую (например: `100г овсянка, 150г куриное филе`):")
    await state.set_state(FoodStates.waiting_for_batch)

@dp.message(FoodStates.waiting_for_batch)
async def process_batch_food(message: types.Message, state: FSMContext):
    await state.clear()
    raw_text = message.text.lower()
    added_cals, added_prot, added_fats, added_carbs = 0, 0, 0, 0
    items = raw_text.split(",")
    
    for item in items:
        item = item.strip()
        weight = 100
        if "г" in item:
            parts = item.split("г")
            try:
                weight = float("".join(filter(lambda ch: ch.isdigit() or ch=='.', parts[0])))
            except: weight = 100
            product_name = parts[1].strip()
        else:
            product_name = "".join(filter(lambda ch: not ch.isdigit(), item)).strip()
            
        for db_name, data in FOOD_DATABASE.items():
            if db_name in product_name:
                coef = weight / 100.0
                added_cals += data['cals'] * coef
                added_prot += data['prot'] * coef
                added_fats += data['fats'] * coef
                added_carbs += data['carbs'] * coef
                break
                
    if added_cals == 0:
        return await message.answer("❌ Бот не распознал продукты. Проверьте написание по кнопке «Меню еды в базе».")
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE daily_log 
        SET calories = calories + ?, proteins = proteins + ?, fats = fats + ?, carbs = carbs + ?
        WHERE user_id = ?
    """, (added_cals, added_prot, added_fats, added_carbs, message.from_user.id))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Добавлено: +{round(added_cals)} ккал (Б:{round(added_prot,1)} | Ж:{round(added_fats,1)} | У:{round(added_carbs,1)})")
    
    r, l = await get_profile_data(message.from_user.id)
    if r:
        text, markup = generate_profile_interface(r, l)
        await message.answer(text, reply_markup=markup, parse_mode="Markdown")

# --- КОНСТРУКТОР ТРЕНИРОВОК ---
@dp.callback_query(F.data == "inline_workout")
async def inline_workout_handler(c: types.CallbackQuery):
    await c.answer()
    text = "🏋️ **Конструктор плана тренировок**\n\nВыбери группу мышц для получения списка упражнений:"
    b = InlineKeyboardBuilder()
    for category in EXERCISE_DATABASE.keys():
        b.button(text=f"💪 {category}", callback_data=f"ex_cat_{category}")
    b.button(text="⬅️ Назад в профиль", callback_data="back_to_profile")
    b.adjust(2, 2, 2, 1)
    await c.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("ex_cat_"))
async def show_exercises_by_category(c: types.CallbackQuery):
    await c.answer()
    category = c.data.replace("ex_cat_", "")
    exercises = EXERCISE_DATABASE.get(category, [])
    text = f"🏋️ **15 лучших упражнений на группу «{category}»:**\n\n"
    for idx, ex in enumerate(exercises, 1):
        text += f"{idx}. {ex}\n"
    b = InlineKeyboardBuilder()
    b.button(text="🔄 К выбору категорий", callback_data="inline_workout")
    b.button(text="⬅️ В профиль", callback_data="back_to_profile")
    b.adjust(1, 1)
    await c.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")

# --- ПРОСМОТР МЕНЮ ЕДЫ ---
@dp.callback_query(F.data == "view_food_db")
async def view_food_db_handler(c: types.CallbackQuery):
    await c.answer()
    categories = {}
    for name, info in FOOD_DATABASE.items():
        cat = info.get("cat", "Разное")
        if cat not in categories: categories[cat] = []
        categories[cat].append(f"• {name.capitalize()} ({info['cals']} ккал | Б:{info['prot']} | Ж:{info['fats']} | У:{info['carbs']})")
    
    text = "📖 **Доступные продукты в базе данных (на 100г):**\n\n"
    for cat, items in categories.items():
        text += f"🧱 **{cat}:**\n" + "\n".join(items) + "\n\n"
        
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад в профиль", callback_data="back_to_profile")
    await c.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")

# --- КАЛЕНДАРЬ ПРИЕМА ПИЩИ И ПЕРЕХОД К БУДИЛЬНИКАМ ---
@dp.callback_query(F.data == "food_calendar")
async def food_calendar_handler(c: types.CallbackQuery):
    await c.answer()
    text = (
        "📅 **Календарь приема пищи и статистика**\n\n"
        "🟢 Понедельник: Цель КБЖУ закрыта успешно\n"
        "🟢 Вторник: Цель КБЖУ закрыта успешно\n"
        "🟡 Среда (Сегодня): Прогресс обновляется динамически в профиле."
    )
    b = InlineKeyboardBuilder()
    b.button(text="⏰ Установить Будильник", callback_data="set_alarm_tz")
    b.button(text="⬅️ Назад в профиль", callback_data="back_to_profile")
    b.adjust(1, 1)
    await c.message.edit_text(text, reply_markup=b.as_markup())

# --- ВЫБОР ЧАСОВОГО ПОЯСА ДЛЯ БУДИЛЬНИКА ---
@dp.callback_query(F.data == "set_alarm_tz")
async def set_alarm_tz_handler(c: types.CallbackQuery):
    await c.answer()
    text = (
        "⏰ **Настройка будильника**\n\n"
        "Пожалуйста, выберите часовой пояс вашего региона для корректной отправки уведомлений:"
    )
    
    b = InlineKeyboardBuilder()
    b.button(text="МСК−1 — Калининградское время", callback_data="tz_msk_minus_1")
    b.button(text="МСК+0 — Москва, МО", callback_data="tz_msk_0")
    b.button(text="МСК+1 — Самарское время", callback_data="tz_msk_plus_1")
    b.button(text="МСК+2 — Екатеринбургское время", callback_data="tz_msk_plus_2")
    b.button(text="МСК+3 — Омское время", callback_data="tz_msk_plus_3")
    b.button(text="МСК+4 — Красноярское время", callback_data="tz_msk_plus_4")
    b.button(text="МСК+5 — Иркутское время", callback_data="tz_msk_plus_5")
    b.button(text="МСК+6 — Якутское время", callback_data="tz_msk_plus_6")
    b.button(text="МСК+7 — Владивостокское время", callback_data="tz_msk_plus_7")
    b.button(text="МСК+8 — Магаданское время", callback_data="tz_msk_plus_8")
    b.button(text="МСК+9 — Камчатское время", callback_data="tz_msk_plus_9")
    b.button(text="⬅️ Назад в календарь", callback_data="food_calendar")
    
    b.adjust(1)
    await c.message.edit_text(text, reply_markup=b.as_markup())

# --- ОБРАБОТКА ВЫБРАННОГО ПОЯСА И ПЕРЕХОД К ВЫБОРУ ТИПА ПРИЕМА ---
@dp.callback_query(F.data.startswith("tz_"))
async def process_timezone_selection(c: types.CallbackQuery):
    await c.answer()
    tz_code = c.data.replace("tz_", "")
    
    tz_info = {
        "msk_minus_1": "МСК−1 (UTC+02:00)", "msk_0": "МСК+0 (UTC+03:00)", "msk_plus_1": "МСК+1 (UTC+04:00)",
        "msk_plus_2": "МСК+2 (UTC+05:00)", "msk_plus_3": "МСК+3 (UTC+06:00)", "msk_plus_4": "МСК+4 (UTC+07:00)",
        "msk_plus_5": "МСК+5 (UTC+08:00)", "msk_plus_6": "МСК+6 (UTC+09:00)", "msk_plus_7": "МСК+7 (UTC+10:00)",
        "msk_plus_8": "МСК+8 (UTC+11:00)", "msk_plus_9": "МСК+9 (UTC+12:00)"
    }
    tz_name = tz_info.get(tz_code, "МСК+0 (UTC+03:00)")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET timezone = ? WHERE user_id = ?", (tz_name, c.from_user.id))
    conn.commit()
    conn.close()

    await show_meal_type_selection(c.message, c.from_user.id, f"✅ Часовой пояс `{tz_name}` успешно сохранен!\n\n")

# --- ГЛАВНОЕ ОКНО УПРАВЛЕНИЯ РАСПИСАНИЕМ ---
async def show_meal_type_selection(message: types.Message, user_id: int, prefix_text=""):
    text = (
        f"{prefix_text}⏰ **Настройка расписания будильников**\n\n"
        "Бот будет присылать напоминания **за 30 минут до** и **ровно во время** каждого приема пищи.\n\n"
        "Вы можете настроить всё самостоятельно или доверить это боту:"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🍽️ Основное время приема пищи", callback_data="meal_manage_main")
    b.button(text="🍕 Дополнительное время приема", callback_data="meal_manage_sub")
    b.button(text="🤖 Автоподбор идеального времени под меня", callback_data="meal_auto_generate")
    b.button(text="🗑️ Стереть будильники и начать заново", callback_data="meal_clear_all")
    b.button(text="⬅️ Назад к часовым поясам", callback_data="set_alarm_tz")
    b.adjust(1)
    
    if message.text:
        await message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=b.as_markup(), parse_mode="Markdown")

# --- СТРУКТУРИРОВАННЫЕ СПИСКИ (ОСНОВНЫЕ ИЛИ ДОПОЛНИТЕЛЬНЫЕ) ---
@dp.callback_query(F.data.startswith("meal_manage_"))
async def meal_manage_handler(c: types.CallbackQuery):
    await c.answer()
    m_type = "основной" if c.data == "meal_manage_main" else "дополнительный"
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, meal_name, meal_time FROM user_meals WHERE user_id = ? AND meal_type = ?", (c.from_user.id, m_type))
    meals = cursor.fetchall()
    conn.close()
    
    text = f"📋 **{m_type.capitalize()} время приемов пищи:**\n\n"
    if not meals:
        text += "_Список пока пуст._\n"
    else:
        for m in meals:
            text += f"• *{m[1]}* — ⏰ {m[2]}\n"
            
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить прием пищи", callback_data=f"meal_add_{m_type}")
    
    if meals:
        if m_type == "основной":
            b.button(text="🔄 Сделать созданные дополнительными", callback_data="meal_switch_to_sub")
        else:
            b.button(text="🔄 Сделать созданные основными", callback_data="meal_switch_to_main")
            
    b.button(text="⬅️ Назад", callback_data="meal_back_to_types")
    b.adjust(1)
    await c.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")

# --- СМЕНА СТАТУСА ПРИЕМОВ (ИНВЕРСИЯ КАТЕГОРИЙ) ---
@dp.callback_query(F.data.startswith("meal_switch_to_"))
async def meal_switch_handler(c: types.CallbackQuery):
    await c.answer()
    target_type = "основной" if c.data == "meal_switch_to_main" else "дополнительный"
    current_type = "дополнительный" if target_type == "основной" else "основной"
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE user_meals SET meal_type = ? WHERE user_id = ? AND meal_type = ?", (target_type, c.from_user.id, current_type))
    conn.commit()
    conn.close()
    
    await c.message.edit_text(f"🔄 Все приемы пищи из категории *{current_type}* переведены в статус *{target_type}*!")
    await show_meal_type_selection(c.message, c.from_user.id)

@dp.callback_query(F.data == "meal_back_to_types")
async def meal_back_to_types_handler(c: types.CallbackQuery):
    await c.answer()
    await show_meal_type_selection(c.message, c.from_user.id)

# --- ДОБАВЛЕНИЕ ПРИЕМА ПИЩИ (ПРОЦЕСС FSM) ---
@dp.callback_query(F.data.startswith("meal_add_"))
async def meal_add_start(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    m_type = c.data.replace("meal_add_", "")
    await state.update_data(m_type=m_type)
    
    await c.message.edit_text("✏️ Введите название приема пищи (например: `Обед`):")
    await state.set_state(AlarmStates.waiting_for_meal_name)

@dp.message(AlarmStates.waiting_for_meal_name)
async def meal_name_chosen(message: types.Message, state: FSMContext):
    await state.update_data(meal_name=message.text.strip())
    await message.answer("⏰ Теперь укажите время в формате ЧЧ:ММ (например: `13:00`):")
    await state.set_state(AlarmStates.waiting_for_meal_time)

@dp.message(AlarmStates.waiting_for_meal_time)
async def meal_time_chosen(message: types.Message, state: FSMContext):
    time_text = message.text.strip()
    if not re.match(r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", time_text):
        return await message.answer("❌ Некорректный формат времени. Введите время как в примере (например, 13:00):")
    
    data = await state.get_data()
    await state.clear()
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_meals (user_id, meal_name, meal_time, meal_type) VALUES (?, ?, ?, ?)
    """, (message.from_user.id, data['meal_name'], time_text, data['m_type']))
    conn.commit()
    conn.close()
    
    # Расчет пред-уведомления за 30 минут
    hours, minutes = map(int, time_text.split(":"))
    total_minutes = hours * 60 + minutes - 30
    if total_minutes < 0:
        total_minutes += 24 * 60
    pre_time = f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"

    text = (
        f"💾 **Сохранено!**\n\n"
        f"🍔 Прием пищи: *{data['meal_name']}* — {time_text}\n"
        f"🔔 Напоминания установлены на:\n"
        f"1. `{pre_time}` (За 30 минут)\n"
        f"2. `{time_text}` (Во время приема)\n\n"
        f"Желаете добавить что-то еще или сохранить настройки будильника?"
    )
    
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить еще один прием пищи", callback_data=f"meal_add_{data['m_type']}")
    b.button(text="💾 Сохранить и выйти в профиль", callback_data="back_to_profile")
    b.adjust(1)
    
    await message.answer(text, reply_markup=b.as_markup(), parse_mode="Markdown")

# --- 🤖 АВТОПОДБОРОЧНАЯ СЕТКА ПИТАНИЯ ---
@dp.callback_query(F.data == "meal_auto_generate")
async def meal_auto_generate_handler(c: types.CallbackQuery):
    await c.answer()
    user_id = c.from_user.id
    
    default_meals = [
        ("Завтрак", "08:30", "основной"),
        ("Обед", "13:00", "основной"),
        ("Полдник", "16:30", "дополнительный"),
        ("Ужин", "20:00", "основной")
    ]
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_meals WHERE user_id = ?", (user_id,))
    
    for name, time_val, m_type in default_meals:
        cursor.execute("""
            INSERT INTO user_meals (user_id, meal_name, meal_time, meal_type) 
            VALUES (?, ?, ?, ?)
        """, (user_id, name, time_val, m_type))
    conn.commit()
    conn.close()
    
    text = (
        "🤖 ✨ **Бот подобрал для вас идеальный спортивный режим питания!**\n\n"
        "Расписание сбалансировано для стабильного удержания азотистого баланса и высокого анаболизма:\n\n"
        "🍳 *Завтрак* — ⏰ 08:30 (Напоминание в 08:00)\n"
        "🍗 *Обед* — ⏰ 13:00 (Напоминание в 12:30)\n"
        "🍌 *Полдник* — ⏰ 16:30 (Напоминание в 16:00)\n"
        "🐟 *Ужин* — ⏰ 20:00 (Напоминание в 19:30)\n\n"
        "Вы можете в любой момент изменить или сбросить этот план."
    )
    
    b = InlineKeyboardBuilder()
    b.button(text="📋 В профиль", callback_data="back_to_profile")
    b.button(text="🔄 Скорректировать вручную", callback_data="meal_back_to_types")
    b.adjust(1, 1)
    
    await c.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")

# --- 🗑️ СТИРАНИЕ И ПОЛНЫЙ СБРОС БУДИЛЬНИКОВ ---
@dp.callback_query(F.data == "meal_clear_all")
async def meal_clear_all_handler(c: types.CallbackQuery):
    await c.answer()
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_meals WHERE user_id = ?", (c.from_user.id,))
    conn.commit()
    conn.close()
    
    await show_meal_type_selection(
        c.message, 
        c.from_user.id, 
        prefix_text="💥 **Все ваши будильники успешно стерты!** Окна питания очищены, можно настраивать заново.\n\n"
    )

# --- РАСЧЕТ РАЦИОНА ПИТАНИЯ ---
@dp.callback_query(F.data == "calc_diet_menu")
async def calc_diet_menu_handler(c: types.CallbackQuery):
    await c.answer()
    text = (
        "🍎 **Расчет индивидуального рациона**\n\n"
        "Выберите желаемый вариант продуктовой корзины для генерации меню:\n\n"
        "🔸 **Бюджетный** — простая, доступная и полезная еда с повторяющейся структурой (овсянка, яйца, куриное филе, гречка, подсолнечное масло/семечки).\n"
        "🔸 **Стандартный** — оптимальный баланс цены и комфорта, добавляется больше разнообразия гарниров и источников белка (индейка, рис, творог, бананы).\n"
        "🔸 **Дорогой** — максимальное гастрономическое разнообразие блюд (красная рыба, говядина, орехи, морепродукты, авокадо)."
    )
    b = InlineKeyboardBuilder()
    b.button(text="Бюджетный 💰", callback_data="diet_tier_budget")
    b.button(text="Стандартный ⚖️", callback_data="diet_tier_standard")
    b.button(text="Дорогой 💎", callback_data="diet_tier_luxury")
    b.button(text="⬅️ Назад в профиль", callback_data="back_to_profile")
    b.adjust(1, 1, 1, 1)
    await c.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("diet_tier_"))
async def process_diet_tier(c: types.CallbackQuery):
    await c.answer()
    tier = c.data.replace("diet_tier_", "")
    
    r, _ = await get_profile_data(c.from_user.id)
    if not r:
        return await c.message.edit_text("Ошибка: профиль не найден. Пройдите регистрацию.")
    
    target_cals, target_prot, target_fats, target_carbs = r[4], r[5], r[6], r[7]
    
    p_meal = round(target_prot / 4, 1)
    f_meal = round(target_fats / 4, 1)
    c_meal = round(target_carbs / 4, 1)
    cal_meal = round(target_cals / 4)

    if tier == "budget":
        tier_title = "💰 Бюджетный рацион (Полезно и доступно)"
        menu_text = (
            f"🍳 *Завтрак:*\n• Овсяные хлопья (на воде/молоке) + 2 цельных яйца\n\n"
            f"🍗 *Обед:*\n• Отварное куриное филе + гречневая крупа\n\n"
            f"🌻 *Полдник:*\n• Омлет из белков + горсть жареных очищенных подсолнечных семечек\n\n"
            f"🐟 *Ужин:*\n• Минтай или белая рыба на пару + свежая капуста/огурец\n"
        )
    elif tier == "standard":
        tier_title = "⚖️ Стандартный рацион (Разнообразно и оптимально)"
        menu_text = (
            f"🥞 *Завтрак:*\n• Овсяноблин с сыром + легкий творог 5%\n\n"
            f"🥩 *Обед:*\n• Стейк из грудки индейки + пропаренный рис + томаты\n\n"
            f"🍌 *Полдник:*\n• Банан + протеиновый шейк или йогурт\n\n"
            f"🍗 *Ужин:*\n• Запеченное куриное филе + макароны из твердых сортов + оливковое масло\n"
        )
    else:
        tier_title = "💎 Дорогой рацион (Максимальное разнообразие)"
        menu_text = (
            f"🥑 *Завтрак:*\n• Тосты со слабосоленым лососем, авокадо и яйцом пашот\n\n"
            f"🥩 *Обед:*\n• Постная говядина/телятина на гриле + киноа или бурый рис + брокколи\n\n"
            f"🥜 *Полдник:*\n• Микс элитных орехов (кешью, миндаль) + греческий йогурт\n\n"
            f"🍤 *Ужин:*\n• Тигровые креветки или кальмары + легкий салат с сыром фета\n"
        )

    text = (
        f"📋 *{tier_title}*\n"
        f"🍱 _Сгенерирован под твои параметры нормы КБЖУ_\n\n"
        f"🎯 *Цель на каждый из 4-х приемов пищи:*\n"
        f" Каждый прием должен содержать примерно: *{cal_meal} ккал* | "
        f"*Б: {p_meal}г* | *Ж: {f_meal}г* | *У: {c_meal}г*\n\n"
        f"{menu_text}\n"
        f"💡 _Взвешивай продукты в сухом/сыром виде перед готовкой для соблюдения лимитов БЖУ!_"
    )
    
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Изменить вариант корзины", callback_data="calc_diet_menu")
    b.button(text="⬅️ В профиль", callback_data="back_to_profile")
    await c.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")

# --- ХЭНДЛЕР НАЗАД В ПРОФИЛЬ ---
@dp.callback_query(F.data == "back_to_profile")
async def back_to_profile_handler(c: types.CallbackQuery):
    await c.answer()
    r, l = await get_profile_data(c.from_user.id)
    if r:
        text, markup = generate_profile_interface(r, l)
        await c.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await c.message.edit_text("Профиль пуст. Нажмите /start для заполнения анкеты КБЖУ.")

# ==================== ЗАПУСК БОТА ====================
if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
