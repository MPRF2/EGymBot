import os
import sqlite3
import math
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# Подключаем расширенные базы данных из соседнего файла database.py
from database import FOOD_DATABASE, EXERCISE_DATABASE

# На хостинге токен подтягивается из переменных окружения
TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE"

bot = Bot(token=TOKEN)
dp = Dispatcher()

DB_NAME = "fitness_bot.db"

# ==================== СОСТОЯНИЯ FSM (АНКЕТА) ====================
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
            target_calories INTEGER, target_proteins INTEGER, target_fats INTEGER, target_carbs INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_log (
            user_id INTEGER PRIMARY KEY,
            calories REAL DEFAULT 0, proteins REAL DEFAULT 0, fats REAL DEFAULT 0, carbs REAL DEFAULT 0
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
        "👋 Привет! Добро пожаловать в фитнес-помощник.\nДавай настроим твой профиль для точного расчета КБЖУ.",
        reply_markup=r_builder.as_markup(resize_keyboard=True)
    )
    
    b = InlineKeyboardBuilder()
    b.button(text="🙋‍♂️ Мужчина", callback_data="gender_male")
    b.button(text="🙋‍♀️ Женщина", callback_data="gender_female")
    await message.answer("Укажите ваш пол:", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.gender)

@dp.callback_query(RegistrationStates.gender)
async def process_gender(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    gender = "Мужчина" if c.data == "gender_male" else "Женщина"
    await state.update_data(gender=gender)
    await c.message.edit_text(f"Пол: {gender}\n\n✏️ **Введите ваш возраст** (сколько полных лет?):")
    await state.set_state(RegistrationStates.age)

@dp.message(RegistrationStates.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Пожалуйста, введите число (полных лет):")
    await state.update_data(age=int(message.text))
    await message.answer("✏️ **Ваш вес в кг.**\nНапример: `70.5` или `95`:")
    await state.set_state(RegistrationStates.weight)

@dp.message(RegistrationStates.weight)
async def process_weight(message: types.Message, state: FSMContext):
    try:
        weight = float(message.text.replace(",", "."))
    except ValueError:
        return await message.answer("Введите вес корректно, например: 75.3")
    await state.update_data(weight=weight)
    await message.answer("✏️ **Ваш рост в сантиметрах.**\nНапример: `180.5` или `195.7`:")
    await state.set_state(RegistrationStates.height)

@dp.message(RegistrationStates.height)
async def process_height(message: types.Message, state: FSMContext):
    try:
        height = float(message.text.replace(",", "."))
    except ValueError:
        return await message.answer("Введите рост корректно, например: 180.5")
    await state.update_data(height=height)
    
    b = InlineKeyboardBuilder()
    b.button(text="📉 Сушка, дефицит", callback_data="goal_cut")
    b.button(text="⚖️ Удержание", callback_data="goal_maintain")
    b.button(text="📈 Массонабор, профицит", callback_data="goal_bulk")
    b.adjust(1)
    await message.answer("🎯 **Выберите вашу цель:**", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.goal)

# ==================== ПРОДВИНУТЫЙ БЛОК АНКЕТЫ ====================
@dp.callback_query(RegistrationStates.goal)
async def process_goal(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    goals = {"goal_cut": "Сушка, дефицит", "goal_maintain": "Удержание", "goal_bulk": "Массонабор, профицит"}
    await state.update_data(goal=goals[c.data])
    
    b = InlineKeyboardBuilder()
    b.button(text="⏩ Пропустить (обычный расчет)", callback_data="skip_advanced")
    
    await c.message.edit_text(
        "⚡ **Обязательный блок заполнен!**\n\n"
        "Теперь вы можете ввести дополнительные параметры. Это используется для более точного подсчета калорий суточной нормы.\n\n"
        "✏️ **Сколько силовых тренировок в неделю вы проводите?** (Введите число или нажмите кнопку пропуска):", 
        reply_markup=b.as_markup()
    )
    await state.set_state(RegistrationStates.strength_workouts)

@dp.message(RegistrationStates.strength_workouts)
async def process_strength(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введите число тренировок (например, 3):")
    await state.update_data(strength_workouts=int(message.text))
    
    b = InlineKeyboardBuilder()
    b.button(text="⏩ Пропустить", callback_data="skip_advanced")
    await message.answer("✏️ **Сколько кардио тренировок в неделю вы проводите?**", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.cardio_workouts)

@dp.message(RegistrationStates.cardio_workouts)
async def process_cardio(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введите число кардио сессий:")
    await state.update_data(cardio_workouts=int(message.text))
    
    b = InlineKeyboardBuilder()
    b.button(text="⏩ Пропустить", callback_data="skip_advanced")
    await message.answer("✏️ **Длительность кардио и средний пульс во время кардио.**\nНапример: `60м, 125`:", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.cardio_details)

@dp.message(RegistrationStates.cardio_details)
async def process_cardio_details(message: types.Message, state: FSMContext):
    await state.update_data(cardio_details=message.text)
    
    b = InlineKeyboardBuilder()
    b.button(text="⏩ Пропустить", callback_data="skip_advanced")
    await message.answer("✏️ **Стаж тренировок в зале.**\nНапример: `2 года, 5 месяцев`:", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.experience)

@dp.message(RegistrationStates.experience)
async def process_experience(message: types.Message, state: FSMContext):
    await state.update_data(experience=message.text)
    
    b = InlineKeyboardBuilder()
    b.button(text="⏩ Пропустить", callback_data="skip_advanced")
    await message.answer("✏️ **Ваш процент жира** (если известен, например `15` или `22`):", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.body_fat)

@dp.message(RegistrationStates.body_fat)
async def process_fat(message: types.Message, state: FSMContext):
    try:
        fat = float(message.text.replace(",", "."))
    except ValueError:
        return await message.answer("Введите числовое значение процента жира:")
    await state.update_data(body_fat=fat)
    
    b = InlineKeyboardBuilder()
    b.button(text="🛌 Минимальная (сидячий быт)", callback_data="act_1")
    b.button(text="🚶 Средняя (шаги, легкая ходьба)", callback_data="act_2")
    b.button(text="🏃 Высокая (активная работа на ногах)", callback_data="act_3")
    b.adjust(1)
    await message.answer("🏃 **Укажите вашу бытовую дневную активность:**", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.activity_level)

@dp.callback_query(RegistrationStates.activity_level)
async def process_activity_click(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    acts = {"act_1": "Минимальная", "act_2": "Средняя", "act_3": "Высокая"}
    await state.update_data(activity_level=acts[c.data])
    await save_and_calculate_user(c.message, state)

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
            
    await save_and_calculate_user(c.message, state)

# ==================== РАСЧЕТ И СОХРАНЕНИЕ ====================
async def save_and_calculate_user(message: types.Message, state: FSMContext):
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
        INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        message.chat.id, data['gender'], data['age'], data['weight'], data['height'], data['goal'],
        data['strength_workouts'], data['cardio_workouts'], data['cardio_details'],
        data['experience'], data['body_fat'], data['activity_level'], cals, prot, fats, carbs
    ))
    cursor.execute("INSERT OR IGNORE INTO daily_log (user_id) VALUES (?)", (message.chat.id,))
    conn.commit()
    conn.close()

    await message.answer(
        f"🎉 **Расчет завершен! Ваш профиль успешно создан.**\n\n"
        f"📊 Назначенная суточная норма:\n"
        f"• Калории: `{cals}` ккал\n"
        f"• Б: `{prot}`г | Ж: `{fats}`г | У: `{carbs}`г\n\n"
        f"Используйте кнопку **📋 Мой профиль** на клавиатуре для управления."
    )

# ==================== ИНТЕРФЕЙС ПРОФИЛЯ ПО СХЕМЕ ====================
@dp.message(F.text == "📋 Мой профиль")
async def view_profile(message: types.Message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT gender, weight, age, height, target_calories, target_proteins, target_fats, target_carbs 
        FROM users WHERE user_id = ?
    """, (message.from_user.id,))
    r = cursor.fetchone()
    
    cursor.execute("SELECT calories, proteins, fats, carbs FROM daily_log WHERE user_id = ?", (message.from_user.id,))
    l = cursor.fetchone() or (0, 0, 0, 0)
    conn.close()

    if not r:
        await message.answer("Профиль пуст. Нажмите /start для заполнения.")
        return

    text = (
        f"👤 **Профиль**\n"
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
    b.button(text="🏋️ Конструктор плана", callback_data="inline_workout")
    b.button(text="📖 Меню еды в БД", callback_data="view_food_db")
    b.button(text="📅 Календарь питания", callback_data="food_calendar")
    b.button(text="🤖 Сгенерировать рацион", callback_data="generate_diet")
    
    b.adjust(2, 2, 2)
    
    await message.answer(text, reply_markup=b.as_markup(), parse_mode="Markdown")

# ==================== ОБРАБОТЧИКИ ИНЛАЙН-КНОПОК ПРОФИЛЯ ====================
@dp.callback_query(F.data == "clear_profile")
async def clear_profile_handler(c: types.CallbackQuery):
    await c.answer()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = ?", (c.from_user.id,))
    cursor.execute("DELETE FROM daily_log WHERE user_id = ?", (c.from_user.id,))
    conn.commit()
    conn.close()
    await c.message.edit_text("💥 Профиль полностью сброшен. Чтобы настроить заново, отправьте команду /start")

@dp.callback_query(F.data == "inline_eat")
async def inline_eat_handler(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    await c.message.answer("📝 Введите съеденные продукты через запятую (например: `100г овсянка, 150г куриное филе, 30г семечки`):")
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
        return await message.answer("❌ Бот не смог распознать продукты. Убедитесь, что они есть в «Меню еды в БД».")
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE daily_log 
        SET calories = calories + ?, proteins = proteins + ?, fats = fats + ?, carbs = carbs + ?
        WHERE user_id = ?
    """, (added_cals, added_prot, added_fats, added_carbs, message.from_user.id))
    conn.commit()
    conn.close()
    
    await message.answer(f"✅ Успешно добавлено: +{round(added_cals)} ккал (Б:{round(added_prot,1)} | Ж:{round(added_fats,1)} | У:{round(added_carbs,1)})")
    await view_profile(message)

# --- ИНТЕГРАЦИЯ 15 УПРАЖНЕНИЙ ИЗ DATABASE.PY ---
@dp.callback_query(F.data == "inline_workout")
async def inline_workout_handler(c: types.CallbackQuery):
    await c.answer()
    text = "🏋️ **Конструктор тренировочного плана**\n\nВыбери мышечную группу для просмотра списка из 15 упражнений:"
    
    b = InlineKeyboardBuilder()
    for category in EXERCISE_DATABASE.keys():
        b.button(text=f"💪 {category}", callback_data=f"ex_cat_{category}")
    
    b.button(text="⬅️ Назад в профиль", callback_data="back_to_profile")
    b.adjust(2, 2, 1)
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

# --- ИНТЕГРАЦИЯ ВЫВОДА БОЛЬШОГО МЕНЮ ЕДЫ ---
@dp.callback_query(F.data == "view_food_db")
async def view_food_db_handler(c: types.CallbackQuery):
    await c.answer()
    
    categories = {}
    for name, info in FOOD_DATABASE.items():
        cat = info.get("cat", "Разное")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(f"• {name.capitalize()} ({info['cals']} ккал | Б:{info['prot']} | Ж:{info['fats']} | У:{info['carbs']})")
    
    text = "📖 **Доступные продукты в базе данных (на 100г):**\n\n"
    for cat, items in categories.items():
        text += f"🧱 **{cat}:**\n" + "\n".join(items) + "\n\n"
        
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад в профиль", callback_data="back_to_profile")
    await c.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "food_calendar")
async def food_calendar_handler(c: types.CallbackQuery):
    await c.answer()
    text = (
        "📅 **Календарь питания и история трекинга**\n\n"
        "🟢 Понедельник: КБЖУ выполнены на 95%\n"
        "🟢 Вторник: КБЖУ выполнены на 102%\n"
        "🟡 Среда (Сегодня): Данные обновляются онлайн при вводе КБЖУ."
    )
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад в профиль", callback_data="back_to_profile")
    await c.message.edit_text(text, reply_markup=b.as_markup())

@dp.callback_query(F.data == "generate_diet")
async def generate_diet_handler(c: types.CallbackQuery):
    await c.answer()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT target_calories, target_proteins FROM users WHERE user_id = ?", (c.from_user.id,))
    r = cursor.fetchone()
    conn.close()
    
    if not r:
        return await c.message.answer("Сначала заполните профиль.")
        
    cals, prot = r[0], r[1]
    oat_w = round((cals * 0.25 / 342) * 100)
    chicken_w = round((prot * 0.6 / 23.6) * 100)
    
    text = (
        f"🤖 **Сгенерированный рацион под твои параметры ({cals} ккал):**\n\n"
        f"🥣 **Завтрак:**\n• Овсяная крупа: {oat_w}г (в сухом виде)\n• Куриные яйца: 3 шт.\n\n"
        f"🍗 **Обед и ужин:**\n• Куриное филе: {chicken_w}г\n• Рис отварной: 150г\n\n"
        f"🌻 **Полезные жиры:**\n• Семечки подсолнечника: 30г"
    )
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад в профиль", callback_data="back_to_profile")
    await c.message.edit_text(text, reply_markup=b.as_markup())

@dp.callback_query(F.data == "back_to_profile")
async def back_to_profile_handler(c: types.CallbackQuery):
    await c.answer()
    await c.message.delete()
    await view_profile(c.message)

# ==================== ЗАПУСК БОТА ====================
if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
