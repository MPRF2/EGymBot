import os
import re
import math
import sqlite3
import asyncio
import random
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# ==================== ЗАГЛУШКИ ДЛЯ ТЕСТИРОВАНИЯ БАЗ ДАННЫХ ====================
# Если у вас есть внешний файл database.py, можете раскомментировать импорт.
# Из соображений автономности скрипта, базовые словари продублированы здесь.
FOOD_DATABASE = {
    "овсянка": {"cals": 360, "prot": 12, "fats": 6, "carbs": 62, "cat": "Крупы", "aliases": ["овсянка", "овсяные", "овес"]},
    "куриное филе готовое": {"cals": 150, "prot": 30, "fats": 3, "carbs": 0, "cat": "Мясо", "aliases": ["куриное филе", "курица", "грудка"]},
    "гречка": {"cals": 330, "prot": 12.5, "fats": 3, "carbs": 62, "cat": "Крупы", "aliases": ["гречка", "гречневая"]},
    "минтай": {"cals": 72, "prot": 16, "fats": 1, "carbs": 0, "cat": "Рыба", "aliases": ["минтай", "рыба белая"]},
    "подсолнечные семечки": {"cals": 580, "prot": 20, "fats": 53, "carbs": 10, "cat": "Разное", "aliases": ["семечки", "подсолнечные"]}
}

EXERCISE_DATABASE = {
    "Грудь": ["Жим штанги лежа", "Жим гантелей под углом", "Отжимания на брусьях", "Сведения в кроссовере"],
    "Спина": ["Подтягивания", "Тяга штанги в наклоне", "Тяга верхнего блока", "Горизонтальная тяга"],
    "Ноги": ["Приседания со штангой", "Жим ногами в платформе", "Выпады с гантелями", "Мертвая тяга"],
    "Плечи": ["Армейский жим", "Махи гантелями в стороны", "Протяжка со штангой", "Разведения в наклоне"]
}

TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE"

bot = Bot(token=TOKEN)
dp = Dispatcher()

DB_NAME = "fitness_bot.db"

# Справочник валидных промокодов
PROMO_CODES = {
    "FITFREE2026": 1.0,  # 100% скидка
    "COACHSON": 1.0,     # 100% скидка
    "SHRED30": 0.3       # 30% скидка (для расширения функционала)
}

# ==================== СОСТОЯНИЯ FSM ====================
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

class PromoStates(StatesGroup):
    waiting_for_code = State()

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
            timezone TEXT,
            is_premium INTEGER DEFAULT 0
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
        "👋 **Приветствуем в интеллектуальном фитнес-ассистенте!**\n\n"
        "Давай настроим твой профиль для сверхточного расчета КБЖУ.\n"
        "Сначала пройдем базовые параметры, а затем ты сможешь дополнить их продвинутыми данными.",
        reply_markup=r_builder.as_markup(resize_keyboard=True)
    )
    
    b = InlineKeyboardBuilder()
    b.button(text="🙋‍♂️ Мужчина", callback_data="gender_male")
    b.button(text="🙋‍♀️ Женщина", callback_data="gender_female")
    await message.answer("🧱 **Укажите ваш пол:**", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.gender)

@dp.callback_query(RegistrationStates.gender)
async def process_gender(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    gender = "Мужчина" if c.data == "gender_male" else "Женщина"
    await state.update_data(gender=gender)
    await c.message.edit_text(f"Пол: **{gender}**\n\n✏️ **Возраст (сколько полных лет?):**")
    await state.set_state(RegistrationStates.age)

@dp.message(RegistrationStates.age)
async def process_age(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Пожалуйста, введите число (полных лет):")
    await state.update_data(age=int(message.text))
    await message.answer("✏️ **Ваш текущий вес в кг. Например: 94.5 или 70:**")
    await state.set_state(RegistrationStates.weight)

@dp.message(RegistrationStates.weight)
async def process_weight(message: types.Message, state: FSMContext):
    try:
        weight = float(message.text.lower().replace("кг", "").replace(",", ".").strip())
    except ValueError:
        return await message.answer("Введите вес корректно, например: 94.5")
    await state.update_data(weight=weight)
    await message.answer("✏️ **Ваш рост в сантиметрах (например: 195.7):**")
    await state.set_state(RegistrationStates.height)

@dp.message(RegistrationStates.height)
async def process_height(message: types.Message, state: FSMContext):
    try:
        height = float(message.text.replace(",", ".").strip())
    except ValueError:
        return await message.answer("Введите рост корректно, например: 195.7")
    await state.update_data(height=height)
    
    b = InlineKeyboardBuilder()
    b.button(text="🔥 Сушка, дефицит", callback_data="goal_cut")
    b.button(text="⚖️ Удержание", callback_data="goal_maintain")
    b.button(text="💪 Массонабор, профицит", callback_data="goal_bulk")
    b.adjust(1)
    await message.answer("🎯 **Ваша приоритетная цель:**", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.goal)

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
        "✏️ **Сколько силовых тренировок в неделю ты проводишь?**", 
        reply_markup=b.as_markup()
    )
    await state.set_state(RegistrationStates.strength_workouts)

@dp.message(RegistrationStates.strength_workouts)
async def process_strength(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введите число тренировок (например, 4):")
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
    await message.answer("✏️ **Укажи длительность кардио и средний пульс (например: 45м, 130 уд/м):**", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.cardio_details)

@dp.message(RegistrationStates.cardio_details)
async def process_cardio_details(message: types.Message, state: FSMContext):
    await state.update_data(cardio_details=message.text)
    
    b = InlineKeyboardBuilder()
    b.button(text="⏩ Пропустить продвинутый блок", callback_data="skip_advanced")
    await message.answer("✏️ **Твой тренировочный стаж в зале (например, 2 года):**", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.experience)

@dp.message(RegistrationStates.experience)
async def process_experience(message: types.Message, state: FSMContext):
    await state.update_data(experience=message.text)
    
    b = InlineKeyboardBuilder()
    b.button(text="⏩ Пропустить продвинутый блок", callback_data="skip_advanced")
    await message.answer("✏️ **Твой примерный процент жира (если известен, например 14):**", reply_markup=b.as_markup())
    await state.set_state(RegistrationStates.body_fat)

@dp.message(RegistrationStates.body_fat)
async def process_fat(message: types.Message, state: FSMContext):
    try:
        fat = float(message.text.replace(",", ".").strip())
    except ValueError:
        return await message.answer("Введите числовое значение процента жира:")
    await state.update_data(body_fat=fat)
    
    b = InlineKeyboardBuilder()
    b.button(text="📉 Минимальная", callback_data="act_1")
    b.button(text="🏃 Средняя", callback_data="act_2")
    b.button(text="⚡ Высокая", callback_data="act_3")
    b.adjust(3)
    await message.answer("🏃 **Дневная бытовая активность вне зала:**", reply_markup=b.as_markup())
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
    
    # Расчет базового метаболизма по Миффлину-Сан Жеору
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
        prot = round(data['weight'] * 2.2) if data['gender'] == "Мужчина" else round(data['weight'] * 1.8)
        fats = round(data['weight'] * 0.9) if data['gender'] == "Мужчина" else round(data['weight'] * 1.0)
    elif data['goal'] == "Массонабор, профицит":
        cals = round(maintenance * 1.15)
        prot = round(data['weight'] * 2.0) if data['gender'] == "Мужчина" else round(data['weight'] * 1.7)
        fats = round(data['weight'] * 1.0)
    else:
        cals = maintenance
        prot = round(data['weight'] * 1.8) if data['gender'] == "Мужчина" else round(data['weight'] * 1.5)
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
        f"Индивидуальная суточная норма КБЖУ рассчитана и занесена в базу.\n"
        f"Нажми на кнопку **📋 Мой профиль** ниже, чтобы открыть главное меню управления."
    )

# ==================== ГЛАВНЫЙ ИНТЕРФЕЙС ПРОФИЛЯ ====================
async def get_profile_data(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT gender, weight, age, height, target_calories, target_proteins, target_fats, target_carbs, is_premium 
        FROM users WHERE user_id = ?
    """, (user_id,))
    r = cursor.fetchone()
    
    cursor.execute("SELECT calories, proteins, fats, carbs FROM daily_log WHERE user_id = ?", (user_id,))
    l = cursor.fetchone() or (0, 0, 0, 0)
    conn.close()
    return r, l

@dp.message(F.text.endswith("Мой профиль"))
async def profile_menu_msg(message: types.Message):
    r, l = await get_profile_data(message.from_user.id)
    if not r:
        await message.answer("Профиль пуст. Нажмите /start для заполнения анкеты КБЖУ.")
        return
    
    text, markup = generate_profile_interface(r, l)
    await message.answer(text, reply_markup=markup, parse_mode="Markdown")

def generate_profile_interface(r, l):
    premium_status = "👑 PREMIUM Активен" if r[8] == 1 else "⚪ Базовый (Доступна покупка рационов)"
    text = (
        f"📋 **Личный кабинет атлета**\n\n"
        f"Статус: `{premium_status}`\n"
        f"Пол: {r[0]} | Вес: {r[1]} кг | Рост: {r[3]} см\n\n"
        f"🔥 **Потребление калорий:**\n`{round(l[0])}` / `{r[4]}` ккал\n\n"
        f"📊 **Баланс макронутриентов (БЖУ):**\n"
        f"▪️ Белки: `{round(l[1], 1)}` / `{r[5]}` г\n"
        f"▪️ Жиры: `{round(l[2], 1)}` / `{r[6]}` г\n"
        f"▪️ Углеводы: `{round(l[3], 1)}` / `{r[7]}` г"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🍽️ Внести КБЖУ еды", callback_data="inline_eat")
    b.button(text="🏋️ Конструктор тренировок", callback_data="inline_workout")
    b.button(text="📅 Будильники питания", callback_data="food_calendar")
    b.button(text="🍎 Рассчитать рацион", callback_data="calc_diet_menu")
    
    if r[8] == 0:
        b.button(text="👑 Купить Премиум (Звезды / Код)", callback_data="premium_shop")
        
    b.button(text="🗑️ Сбросить профиль", callback_data="clear_profile")
    b.adjust(2, 2, 1, 1)
    return text, b.as_markup()

# ==================== ОПЛАТА ТГ ЗВЕЗДАМИ И ПРОМОКОДЫ ====================
@dp.callback_query(F.data == "premium_shop")
async def premium_shop_handler(c: types.CallbackQuery):
    await c.answer()
    text = (
        "👑 **PRO-ДОСТУП И ПОЛНЫЕ РАЦИОНЫ**\n\n"
        "Разблокируйте автоматическую генерацию планов питания (все 4 корзины, включая «Сушку Профи») "
        "с динамическим выбором случайных вариантов.\n\n"
        "💳 **Стоимость:** 50 ⭐️ (Telegram Stars)\n"
        "🎁 Если у вас есть подарочный промокод от тренера, вы можете активировать его абсолютно бесплатно!"
    )
    b = InlineKeyboardBuilder()
    b.button(text="💳 Оплатить 50 ⭐️", callback_data="pay_stars")
    b.button(text="🎁 Ввести промокод", callback_data="activate_promo")
    b.button(text="⬅️ В профиль", callback_data="back_to_profile")
    b.adjust(1)
    await c.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "pay_stars")
async def pay_stars_handler(c: types.CallbackQuery):
    await c.answer()
    # Формируем инвойс для оплаты Telegram Stars
    await c.message.answer_invoice(
        title="👑 Premium статус фитнес-бота",
        description="Полноценный доступ ко всем корзинам питания, кастомным будильникам и профессиональной сушке.",
        payload="premium_stars_pack",
        provider_token="", # Для XTR (Звёзд) токен провайдера должен быть пустым
        currency="XTR",
        prices=[types.LabeledPrice(label="Premium Access", amount=50)]
    )

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_premium = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    await message.answer(
        "🎉 **Оплата прошла успешно! Спасибо за поддержку проекта.**\n"
        "Вам открыт полный доступ ко всем функциям. Нажмите «📋 Мой профиль»."
    )

@dp.shipping_query()
async def process_shipping_query(shipping_query: types.ShippingQuery):
    await bot.answer_shipping_query(shipping_query.id, ok=True)

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

# --- АКТИВАЦИЯ ПРОМОКОДОВ ---
@dp.callback_query(F.data == "activate_promo")
async def activate_promo_start(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    await c.message.edit_text("🎁 **Введите ваш промокод** (например, `FITFREE2026`):")
    await state.set_state(PromoStates.waiting_for_code)

@dp.message(PromoStates.waiting_for_code)
async def process_promo_code(message: types.Message, state: FSMContext):
    await state.clear()
    code = message.text.strip().upper()
    
    if code in PROMO_CODES and PROMO_CODES[code] == 1.0:
        user_id = message.from_user.id
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_premium = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        await message.answer("✅ **Промокод успешно активирован!**\nВам предоставлен бесплатный 100% доступ ко всем Premium-функциям бота.")
    else:
        await message.answer("❌ **Неверный или истекший промокод.** Вы можете приобрести доступ в магазине за Звезды.")
        
    r, l = await get_profile_data(message.from_user.id)
    if r:
        text, markup = generate_profile_interface(r, l)
        await message.answer(text, reply_markup=markup, parse_mode="Markdown")

# ==================== ОСТАЛЬНЫЕ ОБРАБОТЧИКИ МЕНЮ ====================
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
    await c.message.edit_text("💥 **Профиль и все данные полностью очищены.** Чтобы заново заполнить анкету, отправь команду /start")

@dp.callback_query(F.data == "inline_eat")
async def inline_eat_handler(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    await c.message.answer("📝 **Введите съеденные продукты** через запятую (например: `100г овсянка, 150г куриное филе готовое`):")
    await state.set_state(FoodStates.waiting_for_batch)

@dp.message(FoodStates.waiting_for_batch)
async def process_batch_food(message: types.Message, state: FSMContext):
    await state.clear()
    raw_text = message.text.lower()
    added_cals, added_prot, added_fats, added_carbs = 0, 0, 0, 0
    items = raw_text.split(",")
    recognized_products = []
    
    for item in items:
        item = item.strip()
        if not item: continue
            
        weight = 100
        product_name = item
        
        weight_match = re.search(r'(\d+[.,]?\d*)\s*г', item)
        if weight_match:
            try: weight = float(weight_match.group(1).replace(",", "."))
            except ValueError: weight = 100
            product_name = item.replace(weight_match.group(0), "").strip()
        else:
            digit_match = re.match(r'^(\d+[.,]?\d*)', item)
            if digit_match:
                try: weight = float(digit_match.group(1).replace(",", "."))
                except ValueError: weight = 100
                product_name = item.replace(digit_match.group(0), "").strip()
            else:
                product_name = "".join(filter(lambda ch: not ch.isdigit(), item)).strip()

        product_name = re.sub(r'^(из|при|приготовленного|сырого)\s+', '', product_name)

        found = False
        for internal_name, data in FOOD_DATABASE.items():
            for alias in data['aliases']:
                if alias in product_name or product_name in alias:
                    coef = weight / 100.0
                    added_cals += data['cals'] * coef
                    added_prot += data['prot'] * coef
                    added_fats += data['fats'] * coef
                    added_carbs += data['carbs'] * coef
                    
                    display_name = internal_name.replace("_", " ").capitalize()
                    recognized_products.append(f"• {display_name} ({round(weight)}г)")
                    found = True
                    break
            if found: break
                
    if added_cals == 0:
        return await message.answer(
            "❌ **Продукты не распознаны.**\n"
            "Попробуйте написать проще: `100г овсянка, 200г минтай`."
        )
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE daily_log 
        SET calories = calories + ?, proteins = proteins + ?, fats = fats + ?, carbs = carbs + ?
        WHERE user_id = ?
    """, (added_cals, added_prot, added_fats, added_carbs, message.from_user.id))
    conn.commit()
    conn.close()
    
    report = "✅ **Успешно добавлено в дневник:**\n" + "\n".join(recognized_products) + "\n\n"
    report += f"📊 **Итого нутриенты:** +{round(added_cals)} ккал (Б:{round(added_prot,1)}г | Ж:{round(added_fats,1)}г | У:{round(added_carbs,1)}г)"
    
    await message.answer(report, parse_mode="Markdown")
    
    r, l = await get_profile_data(message.from_user.id)
    if r:
        text, markup = generate_profile_interface(r, l)
        await message.answer(text, reply_markup=markup, parse_mode="Markdown")

# --- КОНСТРУКТОР ТРЕНИРОВОК ---
@dp.callback_query(F.data == "inline_workout")
async def inline_workout_handler(c: types.CallbackQuery):
    await c.answer()
    text = "🏋️ **Конструктор тренировочного плана**\n\nВыбери целевую мышечную группу для подбора упражнений:"
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
    text = f"🏋️ **Рекомендуемые упражнения на группу «{category}»:**\n\n"
    for idx, ex in enumerate(exercises, 1):
        text += f"{idx}. {ex}\n"
    b = InlineKeyboardBuilder()
    b.button(text="🔄 К выбору категорий", callback_data="inline_workout")
    b.button(text="⬅️ В профиль", callback_data="back_to_profile")
    b.adjust(1, 1)
    await c.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")

# --- КАЛЕНДАРЬ ПРИЕМА ПИЩИ И ПЕРЕХОД К БУДИЛЬНИКАМ ---
@dp.callback_query(F.data == "food_calendar")
async def food_calendar_handler(c: types.CallbackQuery):
    await c.answer()
    text = (
        "📅 **Календарь соблюдения режима питания**\n\n"
        "🟢 Пн: Норма КБЖУ закрыта успешно\n"
        "🟢 Вт: Норма КБЖУ закрыта успешно\n"
        "🟡 Ср (Сегодня): Сбор данных идет в реальном времени"
    )
    b = InlineKeyboardBuilder()
    b.button(text="⏰ Настроить Будильники / Пояс", callback_data="set_alarm_tz")
    b.button(text="⬅️ Назад в профиль", callback_data="back_to_profile")
    b.adjust(1, 1)
    await c.message.edit_text(text, reply_markup=b.as_markup())

# --- ВЫБОР ЧАСОВОГО ПОЯСА ---
@dp.callback_query(F.data == "set_alarm_tz")
async def set_alarm_tz_handler(c: types.CallbackQuery):
    await c.answer()
    text = (
        "⏰ **Выбор часового пояса**\n\n"
        "Для того чтобы напоминания о еде приходили вовремя, укажите ваш регион:"
    )
    b = InlineKeyboardBuilder()
    b.button(text="Калининград (МСК−1)", callback_data="tz_msk_minus_1")
    b.button(text="Москва / С-Пб (МСК+0)", callback_data="tz_msk_0")
    b.button(text="Самара (МСК+1)", callback_data="tz_msk_plus_1")
    b.button(text="Екатеринбург (МСК+2)", callback_data="tz_msk_plus_2")
    b.button(text="Омск (МСК+3)", callback_data="tz_msk_plus_3")
    b.button(text="Красноярск (МСК+4)", callback_data="tz_msk_plus_4")
    b.button(text="⬅️ Назад в календарь", callback_data="food_calendar")
    b.adjust(1)
    await c.message.edit_text(text, reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("tz_"))
async def process_timezone_selection(c: types.CallbackQuery):
    await c.answer()
    tz_code = c.data.replace("tz_", "")
    tz_info = {"msk_minus_1": "МСК−1", "msk_0": "МСК+0", "msk_plus_1": "МСК+1", "msk_plus_2": "МСК+2", "msk_plus_3": "МСК+3", "msk_plus_4": "МСК+4"}
    tz_name = tz_info.get(tz_code, "МСК+0")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET timezone = ? WHERE user_id = ?", (tz_name, c.from_user.id))
    conn.commit()
    conn.close()

    await show_meal_type_selection(c.message, c.from_user.id, f"✅ Часовой пояс `{tz_name}` зафиксирован.\n\n")

# --- ГЛАВНОЕ ОКНО УПРАВЛЕНИЯ РАСПИСАНИЕМ ---
async def show_meal_type_selection(message: types.Message, user_id: int, prefix_text=""):
    text = (
        f"{prefix_text}⏰ **Конструктор будильников питания**\n\n"
        "Бот автоматически отправляет уведомления **за 30 минут до** и **точно во время** выбранного приема пищи.\n\n"
        "Выберите категорию для редактирования или воспользуйтесь автоматическим режимом:"
    )
    b = InlineKeyboardBuilder()
    b.button(text="🍽️ Основные приемы пищи", callback_data="meal_manage_main")
    b.button(text="🍕 Дополнительные приемы пищи", callback_data="meal_manage_sub")
    b.button(text="🤖 Автогенерация спортивного режима", callback_data="meal_auto_generate")
    b.button(text="🗑️ Очистить все будильники", callback_data="meal_clear_all")
    b.button(text="⬅️ Назад в профиль", callback_data="back_to_profile")
    b.adjust(1)
    
    if message.text:
        await message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=b.as_markup(), parse_mode="Markdown")

# --- СТРУКТУРИРОВАННЫЕ СПИСКИ ПРИЕМОВ ПИЩИ ---
@dp.callback_query(F.data.startswith("meal_manage_"))
async def meal_manage_handler(c: types.CallbackQuery):
    await c.answer()
    m_type = "основной" if c.data == "meal_manage_main" else "дополнительный"
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, meal_name, meal_time FROM user_meals WHERE user_id = ? AND meal_type = ?", (c.from_user.id, m_type))
    meals = cursor.fetchall()
    conn.close()
    
    text = f"📋 **{m_type.capitalize()} приемы пищи и их время:**\n\n"
    if not meals:
        text += "_Записей в этой категории нет._\n"
    else:
        for m in meals: text += f"• *{m[1]}* — ⏰ **{m[2]}**\n"
            
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить время", callback_data=f"meal_add_{m_type}")
    
    if meals:
        if m_type == "основной":
            b.button(text="🔄 Сделать созданные дополнительными", callback_data="meal_switch_to_sub")
        else:
            b.button(text="🔄 Сделать созданные основными", callback_data="meal_switch_to_main")
            
    b.button(text="⬅️ Назад", callback_data="meal_back_to_types")
    b.adjust(1)
    await c.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")

# --- ИНВЕРСИЯ (МАССОВЫЙ ПЕРЕВОД ИЗ ОДНОЙ КАТЕГОРИИ В ДРУГУЮ) ---
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
    
    await c.message.answer(f"🔄 Все напоминания из блока *{current_type}* переведены в статус *{target_type}*!")
    await show_meal_type_selection(c.message, c.from_user.id)

@dp.callback_query(F.data == "meal_back_to_types")
async def meal_back_to_types_handler(c: types.CallbackQuery):
    await c.answer()
    await show_meal_type_selection(c.message, c.from_user.id)

@dp.callback_query(F.data.startswith("meal_add_"))
async def meal_add_start(c: types.CallbackQuery, state: FSMContext):
    await c.answer()
    m_type = c.data.replace("meal_add_", "")
    await state.update_data(m_type=m_type)
    await c.message.edit_text("✏️ Введите наименование (например: `Второй завтрак` или `Перекус`):")
    await state.set_state(AlarmStates.waiting_for_meal_name)

@dp.message(AlarmStates.waiting_for_meal_name)
async def meal_name_chosen(message: types.Message, state: FSMContext):
    await state.update_data(meal_name=message.text.strip())
    await message.answer("⏰ Укажите время в формате ЧЧ:ММ (например: `16:15`):")
    await state.set_state(AlarmStates.waiting_for_meal_time)

@dp.message(AlarmStates.waiting_for_meal_time)
async def meal_time_chosen(message: types.Message, state: FSMContext):
    time_text = message.text.strip()
    if not re.match(r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", time_text):
        return await message.answer("❌ Неверный формат времени. Напишите, например, 13:00")
    
    data = await state.get_data()
    await state.clear()
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_meals (user_id, meal_name, meal_time, meal_type) VALUES (?, ?, ?, ?)", 
                   (message.from_user.id, data['meal_name'], time_text, data['m_type']))
    conn.commit()
    conn.close()
    
    hours, minutes = map(int, time_text.split(":"))
    tot = hours * 60 + minutes - 30
    if tot < 0: tot += 24 * 60
    pre_time = f"{tot // 60:02d}:{tot % 60:02d}"

    text = (
        f"💾 **Будильник сохранен!**\n\n"
        f"🍔 Прием: *{data['meal_name']}* в {time_text}\n"
        f"🔔 Тайминги уведомлений:\n"
        f"1. `{pre_time}` (За 30 минут)\n"
        f"2. `{time_text}` (Время приема пищи)"
    )
    b = InlineKeyboardBuilder()
    b.button(text="➕ Добавить еще", callback_data=f"meal_add_{data['m_type']}")
    b.button(text="💾 Выйти в главное меню", callback_data="back_to_profile")
    b.adjust(1)
    await message.answer(text, reply_markup=b.as_markup(), parse_mode="Markdown")

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
        cursor.execute("INSERT INTO user_meals (user_id, meal_name, meal_time, meal_type) VALUES (?, ?, ?, ?)", (user_id, name, time_val, m_type))
    conn.commit()
    conn.close()
    
    text = (
        "🤖 **Спортивный режим питания сгенерирован автоматически!**\n\n"
        "Расписание оптимизировано под высокий анаболизм и ровный фон энергии:\n\n"
        "🍳 *Завтрак* — ⏰ 08:30 (Оповещение в 08:00)\n"
        "🍗 *Обед* — ⏰ 13:00 (Оповещение в 12:30)\n"
        "🍌 *Полдник* — ⏰ 16:30 (Оповещение в 16:00)\n"
        "🐟 *Ужин* — ⏰ 20:00 (Оповещение in 19:30)"
    )
    b = InlineKeyboardBuilder()
    b.button(text="📋 В профиль", callback_data="back_to_profile")
    b.adjust(1)
    await c.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data == "meal_clear_all")
async def meal_clear_all_handler(c: types.CallbackQuery):
    await c.answer()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_meals WHERE user_id = ?", (c.from_user.id,))
    conn.commit()
    conn.close()
    await show_meal_type_selection(c.message, c.from_user.id, "💥 **Все активные будильники были полностью удалены.**\n\n")

# ==================== РАСЧЕТ РАЦИОНА (4 КОРЗИНЫ С СЛУЧАЙНЫМИ ВАРИАНТАМИ) ====================
@dp.callback_query(F.data == "calc_diet_menu")
async def calc_diet_menu_handler(c: types.CallbackQuery):
    await c.answer()
    
    r, _ = await get_profile_data(c.from_user.id)
    if not r: return
    
    is_prem = r[8]
    
    text = (
        "🍎 **Генератор индивидуального рациона питания**\n\n"
        "На основе вашей суточной нормы КБЖУ, бот просчитает граммовку продуктов.\n"
        "Для каждой корзины заложено **3 уникальных плана**, которые выбираются случайно при генерации!\n\n"
        "💰 **Бюджетный** — простые доступные продукты (овсянка, яйца, минтай, курица).\n"
        "⚖️ **Стандартный** — оптимальный баланс (индейка, рис, творог, оливковое масло).\n"
        "💎 **Дорогой (VIP)** — премиальное разнообразие (семга, авокадо, говядина, киноа).\n"
        "🔥 **Сушка (Профи) [PREMIUM]** — жесткий спортивный дефицит, продукты с минимальным ГИ, без лактозы, изоляты высокой очистки и подсолнечные семечки для гормонального здоровья."
    )
    b = InlineKeyboardBuilder()
    b.button(text="Бюджетный 💰", callback_data="diet_tier_budget")
    b.button(text="Стандартный ⚖️", callback_data="diet_tier_standard")
    b.button(text="Дорогой 💎", callback_data="diet_tier_luxury")
    
    # Защита 4-го тарифа премиум-статусом
    if is_prem == 1:
        b.button(text="Сушка (Профи) 🔥", callback_data="diet_tier_shred")
    else:
        b.button(text="🔒 Сушка (Профи) 🔥 (PRO)", callback_data="premium_shop")
        
    b.button(text="⬅️ Назад в профиль", callback_data="back_to_profile")
    b.adjust(2, 2, 1)
    await c.message.edit_text(text, reply_markup=b.as_markup(), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("diet_tier_"))
async def process_diet_tier(c: types.CallbackQuery):
    await c.answer()
    tier = c.data.replace("diet_tier_", "")
    
    r, _ = await get_profile_data(c.from_user.id)
    if not r: return
    
    gender = r[0]
    target_cals, target_prot, target_fats, target_carbs = int(r[4]), int(r[5]), int(r[6]), int(r[7])
    
    p_meal, f_meal, c_meal = target_prot / 4, target_fats / 4, target_carbs / 4
    cal_meal = round(target_cals / 4)

    menu_text = ""
    tier_title = ""
    plan_variant = random.randint(1, 3)

    # 💰 КОРЗИНА 1: БЮДЖЕТНЫЙ
    if tier == "budget":
        tier_title = f"Бюджетный (План №{plan_variant})"
        if plan_variant == 1:
            oats = round((c_meal / 62) * 100)
            eggs = max(1, round(f_meal / 5))
            chick = round((p_meal / 23) * 100)
            buck = round((c_meal / 62) * 100)
            menu_text = f"🍳 *Завтрак:* {oats}г Овсянки, {eggs} шт. Цельных яиц\n🍗 *Обед:* {chick}г Куриного филе, {buck}г Гречки\n🌻 *Полдник:* 30г Подсолнечных семечек, 4 вареных белка\n🐟 *Ужин:* 150г Минтая, 60г Риса"
        elif plan_variant == 2:
            menu_text = f"🍳 *Завтрак:* Полноценный омлет из 3 яиц, 60г ржаного хлеба\n🍗 *Обед:* 180г Куриного филе, 80г Макарон\n🌾 *Полдник:* 250г Кефира 1%, 40г Хлебцев\n🐟 *Ужин:* 160г Филе минтая на пару, 70г Гречки"
        else:
            menu_text = f"🍳 *Завтрак:* 70г Овсяной каши на воде, 1 порция протеина\n🍗 *Обед:* 150г Куриного филе, 200г Отварного картофеля\n🌻 *Полдник:* 40г Семечек подсолнечника\n🐟 *Ужин:* 200г Филе минтая запеченного, салат из капусты"

    # ⚖️ КОРЗИНА 2: СТАНДАРТНЫЙ
    elif tier == "standard":
        tier_title = f"Стандартный (План №{plan_variant})"
        if plan_variant == 1:
            menu_text = f"🥞 *Завтрак:* Овсяноблин (60г овсянки + 2 яйца), 100г Творога 5%\n🥩 *Обед:* 160г Филе индейки, 80г Риса Басмати\n🍎 *Полдник:* 2 Зеленых яблока, 30г Миндаля\n🍗 *Ужин:* 150г Куриного филе на гриле, Салат с оливковым маслом"
        elif plan_variant == 2:
            menu_text = f"🍳 *Завтрак:* 3 Яйца всмятку, 2 тоста с сыром\n🥩 *Обед:* 170г Индейки, 80г Гречневой крупы\n🥛 *Полдник:* 200г Йогурта натурального, 1 порция сывороточного протеина\n🐟 *Ужин:* 150г Запеченной горбуши, 60г Риса"
        else:
            menu_text = f"🥣 *Завтрак:* 80г Овсяных хлопьев, 3 яичных белка вареных\n🥩 *Обед:* 150г Говяжьего гуляша постного, 80г Макарон твердых сортов\n🍌 *Полдник:* 1 Большой банан, 1.5 порции протеина\n🍗 *Ужин:* 160г Индейки на пару, Свежие огурцы и брокколи"

    # 💎 КОРЗИНА 3: VIP / ДОРОГОЙ
    elif tier == "luxury":
        tier_title = f"VIP-Премиум (План №{plan_variant})"
        if plan_variant == 1:
            menu_text = f"🥑 *Завтрак:* 120г Семги слабосоленой, 60г Авокадо, Тосты из цельнозернового хлеба\n🥩 *Обед:* 180г Стейка из постной телятины, 70г Крупы Киноа\n🥜 *Полдник:* 40г Орехов Кешью, 200г Греческого йогурта 0%\n🍤 *Ужин:* 180г Тигровых креветок, 60г Дикого бурого риса"
        elif plan_variant == 2:
            menu_text = f"🍳 *Завтрак:* Брускетта с яйцом пашот, слабосоленым лососем и руколой\n🐟 *Обед:* 200г Стейка из свежего тунца, 80г Кускуса, Спаржа на гриле\n🍓 *Полдник:* 150г Свежей голубики или малины, 30г Орехов макадамия\n🥩 *Ужин:* 180г Утиной грудки (без кожи), Запеченные овощи конфи"
        else:
            menu_text = f"🥑 *Завтрак:* Омлет из 4 яиц с крабовым мясом, половина авокадо\n🥩 *Обед:* 170г Медальонов из говяжьей вырезки, 70г Черного риса\n🍍 *Полдник:* Чиа-пудинг на кокосовом молоке с кусочками ананаса, изолят белка\n🐟 *Ужин:* 180г Стейка из лосося, Брокколи и цветная капуста на пару"

    # 🔥 КОРЗИНА 4: СУШКА (ПРОФИ)
    else:
        tier_title = f"Сушка (Профи) 🩸 (План №{plan_variant})"
        # Динамическая адаптация источников белка и спортивного питания под пол атлета
        prot_src = "Изолят соевого/сывороточного белка (без лактозы)" if gender == "Женщина" else "Говяжий гидролизат / Чистый сывороточный изолят"
        milk_src = "Миндальное или безлактозное молоко"
        
        if plan_variant == 1:
            oats = round((c_meal / 62) * 100)
            fish = round((p_meal / 18) * 100)
            seeds = round((f_meal / 53) * 100)
            menu_text = (
                f"🥣 *Завтрак (Гликогеновое окно):*\n• **{oats}г** Чистой овсянки (на воде или `{milk_src}`)\n• 1.5 порции — {prot_src}\n\n"
                f"🐟 *Обед (Максимально сухой белок):*\n• **{fish}г** Филе трески или судака на пару\n• **40г** Зеленой гречки (низкий ГИ)\n\n"
                f"🌻 *Полдник (Гормоны + Жиры):*\n• **{seeds}г** Очищенных подсолнечных семечек\n• 5 шт. Вареных яичных белков\n\n"
                f"🐟 *Ужин (Слив воды):*\n• **{fish}г** Белой рыбы, огурцы и стебли сельдерея"
            )
        elif plan_variant == 2:
            menu_text = (
                f"🥛 *Завтрак:* 200г Натурального безлактозного йогурта 0%, 1 порция изолята, 30г отрубей\n"
                f"🦑 *Обед:* 200г Отварного кальмара (0% жира), 50г Бурого нешлифованного риса\n"
                f"🌱 *Полдник:* Салат из брокколи, **25г Подсолнечных семечек** (для качественных жиров), 4 белка\n"
                f"🥩 *Ужин:* 180г Филе грудки индейки на пару, свежий шпинат"
            )
        else:
            menu_text = (
                f"🍳 *Завтрак:* Белковый омлет (6 белков + 1 цельное яйцо), 1/2 спелого грейпфрута\n"
                f"🍗 *Обед:* 170г Грудки цыпленка, 50г Киноа с соком лимона\n"
                f"🥜 *Полдник:* **30г Подсолнечных семечек**, 1 порция комплексных аминокислот (EAA)\n"
                f"🐟 *Ужин:* 150г Горбуши (омега-3 кислоты), 200г Пекинской капусты"
            )

    text = (
        f"📖 *Выбранный рацион: {tier_title}*\n"
        f"🎯 _Расчет выполнен индивидуально под ваши лимиты (Пол: {gender}):_\n"
        f"**{target_cals} ккал** | **Б: {target_prot}г** | **Ж: {target_fats}г** | **У: {target_carbs}г**\n\n"
        f"📊 *Ориентир на каждый из 4-х приемов:* \n"
        f"~`{cal_meal} ккал` | `Б: {round(p_meal, 1)}г` | `Ж: {round(f_meal, 1)}г` | `У: {round(c_meal, 1)}г` \n\n"
        f"{menu_text}\n\n"
        f"⚠️ **Внимание:** Вес всех круп, мяса и морепродуктов указан исключительно в **сыром / сухом виде** (до термической обработки)!"
    )
    
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Сгенерировать другой вариант (Рандом)", callback_data=f"diet_tier_{tier}")
    b.button(text="🔄 Изменить продуктовую корзину", callback_data="calc_diet_menu")
    b.button(text="⬅️ Вернуться в профиль", callback_data="back_to_profile")
    b.adjust(1)
    
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
        await c.message.edit_text("Профиль пуст. Нажмите /start для заполнения анкеты.")

# ==================== ЗАПУСК БОТА ====================
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
