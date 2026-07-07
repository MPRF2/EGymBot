import os
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

# Бот автоматически берет токен из переменных окружения хостинга
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Критическая ошибка: Переменная окружения BOT_TOKEN не найдена в настройках хостинга!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# Состояния FSM
class CalorieCalculator(StatesGroup):
    # Обязательные шаги
    height = State()
    weight = State()
    age = State()
    strength_workouts = State()
    # Опциональные шаги (с кнопкой "Пропустить")
    body_fat = State()
    daily_steps = State()
    cardio_minutes = State()
    cardio_heart_rate = State()
    experience = State()
    goal = State()

# Вспомогательная функция для создания клавиатур
def get_keyboard(options: list, show_skip: bool = False) -> ReplyKeyboardMarkup:
    buttons = [[KeyboardButton(text=opt)] for opt in options]
    if show_skip:
        buttons.append([KeyboardButton(text="⏩ Пропустить")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

# --- НАЧАЛО ДИАЛОГА (ОБЯЗАТЕЛЬНЫЕ ШАГИ) ---

@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    await message.answer("Добро пожаловать в фитнес-помощник!\nШаг 1: Введи рост в см:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(CalorieCalculator.height)

@router.message(CalorieCalculator.height)
async def process_height(message: Message, state: FSMContext):
    if not message.text.replace('.', '', 1).isdigit():
        return await message.answer("Пожалуйста, введи число.")
    await state.update_data(height=float(message.text))
    await message.answer("Шаг 2: Введи текущий вес в кг:")
    await state.set_state(CalorieCalculator.weight)

@router.message(CalorieCalculator.weight)
async def process_weight(message: Message, state: FSMContext):
    if not message.text.replace('.', '', 1).isdigit():
        return await message.answer("Пожалуйста, введи число.")
    await state.update_data(weight=float(message.text))
    await message.answer("Шаг 3: Введи возраст:")
    await state.set_state(CalorieCalculator.age)

@router.message(CalorieCalculator.age)
async def process_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Пожалуйста, введи целое число.")
    await state.update_data(age=int(message.text))
    await message.answer("Шаг 4: Сколько силовых тренировок в неделю?")
    await state.set_state(CalorieCalculator.strength_workouts)

# --- ПЕРЕХОД К ОПЦИОНАЛЬНЫМ ШАГАМ (С КНОПКОЙ ПРОПУСТИТЬ) ---

@router.message(CalorieCalculator.strength_workouts)
async def process_strength(message: Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Пожалуйста, введи число.")
    await state.update_data(strength_workouts=int(message.text))
    
    kb = get_keyboard(["10%", "15%", "20%", "25%"], show_skip=True)
    await message.answer("Шаг 5: Укажи процент жира в организме (опционально):", reply_markup=kb)
    await state.set_state(CalorieCalculator.body_fat)

@router.message(CalorieCalculator.body_fat)
async def process_body_fat(message: Message, state: FSMContext):
    if message.text != "⏩ Пропустить":
        val = float(message.text.replace("%", ""))
        await state.update_data(body_fat=val)
    
    kb = get_keyboard(["5000", "10000", "15000"], show_skip=True)
    await message.answer("Шаг 6: Укажи среднее количество шагов в день (опционально):", reply_markup=kb)
    await state.set_state(CalorieCalculator.daily_steps)

@router.message(CalorieCalculator.daily_steps)
async def process_steps(message: Message, state: FSMContext):
    if message.text != "⏩ Пропустить":
        await state.update_data(daily_steps=int(message.text))
    
    kb = get_keyboard(["30 минут", "45 минут", "60 минут"], show_skip=True)
    await message.answer("Шаг 7: Сколько минут длится ОДНА кардио-сессия? (опционально):", reply_markup=kb)
    await state.set_state(CalorieCalculator.cardio_minutes)

@router.message(CalorieCalculator.cardio_minutes)
async def process_cardio_min(message: Message, state: FSMContext):
    if message.text != "⏩ Пропустить":
        val = int(message.text.split()[0])
        await state.update_data(cardio_minutes=val)
        
        kb = get_keyboard(["110-120", "120-130", "130-140"], show_skip=True)
        await message.answer("Шаг 8: Укажи средний целевой пульс на кардио (опционально):", reply_markup=kb)
        await state.set_state(CalorieCalculator.cardio_heart_rate)
    else:
        kb = get_keyboard(["Новичок (до 1 года)", "Средний (1-3 года)", "Продвинутый (3+ лет)"], show_skip=True)
        await message.answer("Шаг 9: Укажи свой стаж тренировок (опционально):", reply_markup=kb)
        await state.set_state(CalorieCalculator.experience)

@router.message(CalorieCalculator.cardio_heart_rate)
async def process_cardio_hr(message: Message, state: FSMContext):
    if message.text != "⏩ Пропустить":
        await state.update_data(cardio_heart_rate=message.text)
    
    kb = get_keyboard(["Новичок (до 1 года)", "Средний (1-3 года)", "Продвинутый (3+ лет)"], show_skip=True)
    await message.answer("Шаг 9: Укажи свой стаж тренировок (опционально):", reply_markup=kb)
    await state.set_state(CalorieCalculator.experience)

@router.message(CalorieCalculator.experience)
async def process_experience(message: Message, state: FSMContext):
    if message.text != "⏩ Пропустить":
        await state.update_data(experience=message.text)
        
    kb = get_keyboard(["🔥 Сушка / Жиросжигание", "⚖️ Удержание", "💪 Массонабор"], show_skip=False)
    await message.answer("Шаг 10: Выбери цель текущего периода:", reply_markup=kb)
    await state.set_state(CalorieCalculator.goal)

# --- ФИНАЛЬНЫЙ РАСЧЕТ ---

@router.message(CalorieCalculator.goal)
async def process_final(message: Message, state: FSMContext):
    goal = message.text
    data = await state.get_data()
    
    # Извлечение обязательных данных
    height = data['height']
    weight = data['weight']
    age = data['age']
    strength_workouts = data['strength_workouts']
    
    # Дефолты для пропущенных параметров
    body_fat = data.get('body_fat', None)
    daily_steps = data.get('daily_steps', 6000)
    cardio_minutes = data.get('cardio_minutes', 0)
    experience = data.get('experience', "Средний")

    # 1. Считаем Базальный метаболизм (BMR)
    if body_fat is not None:
        lbm = weight * (1 - body_fat / 100)
        bmr = 370 + (21.6 * lbm)
        method = "Кэтча-МакАрдла (высокая точность)"
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        method = "Миффлина-Сан Жеора (базовая)"

    # 2. Модификатор стажа
    exp_modifier = 1.0
    if "Средний" in experience: exp_modifier = 1.2
    elif "Продвинутый" in experience: exp_modifier = 1.4

    # Расчет TDEE
    strength_energy = (strength_workouts * 350 * exp_modifier) / 7
    steps_energy = (daily_steps - 4000) * 0.04 if daily_steps > 4000 else 0
    cardio_energy = (cardio_minutes * 8) / 7
    
    tdee = bmr + strength_energy + steps_energy + cardio_energy
    tdee = tdee * 1.1  # Термический эффект пищи (TEF)

    # 3. Корректировка под цель
    if "Сушка" in goal:
        result_calories = tdee - 450
        text_goal = "Сушка (Дефицит)"
    elif "Массонабор" in goal:
        result_calories = tdee + 350
        text_goal = "Массонабор (Профицит)"
    else:
        result_calories = tdee
        text_goal = "Удержание"

    result_text = (
        f"📊 **Итоговый расчет калорийности:**\n\n"
        f"• Используемая формула: {method}\n"
        f"• Твой базовый обмен (BMR): {int(bmr)} ккал\n"
        f"• Общий расход в день (TDEE): {int(tdee)} ккал\n"
        f"• Текущая цель: {text_goal}\n\n"
        f"🎯 **Твоя целевая норма:** `{int(result_calories)}` **ккал/день**"
    )
    
    await message.answer(result_text, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    await state.clear()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dp.include_router(router)
    dp.run_polling(bot)
