import logging
import re
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart


# Загрузка переменных окружения
load_dotenv()

# Настройка логгирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
API_TOKEN = os.getenv('API_TOKEN')

if not API_TOKEN:
    logger.error("Не установлен API_TOKEN!")
    exit(1)


# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher()


# Состояния для FSM
class Form(StatesGroup):
    phone = State()
    waiting_for_phone = State()


# База данных услуг
SERVICES = {
    "landing": {
        "name": "Реферат",
        "description": "5-10 страниц",
        "price": "от 1 000 до 5 000 ₽",
        "details": "Срок написания: 3-5 дней\nВключено: 1 бесплатная доработка"
    },
    "corporate": {
        "name": "Курсовая работа",
        "description": "15-20 страниц",
        "price": "от 5 000 до 10 000 ₽",
        "details": "Срок написания: 5-10 дней\nВключено: 2 бесплатные доработки"
    },
    "seo": {
        "name": "Дипломная работа",
        "description": "50-60 страниц",
        "price": "от 20 000 ₽ ",
        "details": "Срок написания: 7-14 дней\nВключено: 3 бесплатные доработки"
    }
}


# Функции для валидации телефона
def normalize_phone(phone: str) -> str:
    """Нормализует номер телефона к формату +7XXXXXXXXXX"""
    # Удаляем все нецифровые символы, кроме плюса
    cleaned = re.sub(r'[^\d+]', '', phone)

    # Обрабатываем разные форматы
    if cleaned.startswith('8'):
        cleaned = '7' + cleaned[1:]  # 8 -> 7
    elif cleaned.startswith('9') and len(cleaned) == 10:
        cleaned = '7' + cleaned  # 9XXXXXXXXX -> 79XXXXXXXXX

    if cleaned.startswith('7') and not cleaned.startswith('+7'):
        cleaned = '+' + cleaned

    return cleaned


def is_valid_phone(phone: str) -> bool:
    """Проверяет валидность номера телефона"""
    # Нормализуем номер
    normalized = normalize_phone(phone)

    # Проверяем длину и формат
    if len(normalized) != 12 or not normalized.startswith('+7'):
        return False

    # Проверяем, что после +7 идут только цифры
    if not normalized[1:].isdigit():
        return False

    return True


def format_phone_for_display(phone: str) -> str:
    """Форматирует номер для красивого отображения"""
    normalized = normalize_phone(phone)
    if len(normalized) == 12 and normalized.startswith('+7'):
        # Формат: +7 (XXX) XXX-XX-XX
        return f"+7 ({normalized[2:5]}) {normalized[5:8]}-{normalized[8:10]}-{normalized[10:12]}"
    return phone


def get_phone_error_message(phone: str) -> str:
    """Генерирует подробное сообщение об ошибке"""
    normalized = normalize_phone(phone)

    if not normalized:
        return "❌ Вы ввели пустой номер или номер содержит только специальные символы"

    if len(normalized) < 10:
        return f"❌ Слишком короткий номер. Получено {len(normalized)} цифр, нужно 10-11 цифр"

    if len(normalized) > 12:
        return f"❌ Слишком длинный номер. Получено {len(normalized)} цифр, нужно 10-11 цифр"

    if not normalized.startswith(('+7', '7', '8', '9')):
        return "❌ Номер должен начинаться с +7, 7, 8 или 9"

    if not normalized[1:].isdigit():
        return "❌ Номер должен содержать только цифры и знак + в начале"

    return "❌ Неверный формат номера телефона"


# Клавиатура главного меню
def get_main_kb():
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="💰 Узнать стоимость"),
        KeyboardButton(text="📋 Список услуг")
    )
    builder.row(
        KeyboardButton(text="📞 Связаться с менеджером"),
        KeyboardButton(text="ℹ О компании")
    )
    return builder.as_markup(resize_keyboard=True)


# Клавиатура с кнопкой "Отправить номер" и "Отменить"
def get_phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер", request_contact=True)],
            [KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True
    )


# Инлайн-клавиатура услуг
def get_services_ikb():
    builder = InlineKeyboardBuilder()
    for key, service in SERVICES.items():
        builder.button(text=service["name"], callback_data=f"service_{key}")
    builder.button(text="👨‍💼 Консультация", callback_data="consult")
    builder.adjust(1)
    return builder.as_markup()


# Клавиатура для возврата в меню
def get_back_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅ Назад в меню")]],
        resize_keyboard=True
    )


# ОДИН обработчик команды /start
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    welcome_text = """
👋 Добро пожаловать в бота компании <b>ДипломМастер</b>!

🚀 Я помогу вам:
• Узнать стоимость работ
• Выбрать подходящую услугу
• Связаться с менеджером

Выберите действие из меню ниже:
"""
    await message.answer(
        welcome_text,
        reply_markup=get_main_kb(),
        parse_mode=ParseMode.HTML
    )


# Обработчик команды /help
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "ℹ <b>Доступные команды:</b>\n\n"
        "/start - Главное меню\n"
        "/help - Эта справка\n\n"
        "Вы также можете использовать кнопки меню для навигации.",
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_kb()
    )


# Обработчик текстовых сообщений
@dp.message(
    F.text.in_(["💰 Узнать стоимость", "📋 Список услуг", "📞 Связаться с менеджером", "ℹ О компании", "⬅ Назад в меню",
                "❌ Отменить"]))
async def handle_text(message: types.Message, state: FSMContext):
    text = message.text

    if text == "💰 Узнать стоимость":
        await message.answer("Выберите услугу:", reply_markup=get_services_ikb())

    elif text == "📋 Список услуг":
        services_list = "\n".join([f"▪ <b>{service['name']}</b> - {service['description']}"
                                   for service in SERVICES.values()])
        await message.answer(
            f"📌 <b>Наши услуги:</b>\n\n{services_list}\n\n"
            "Выберите услугу, чтобы узнать подробности:",
            reply_markup=get_services_ikb(),
            parse_mode=ParseMode.HTML
        )

    elif text == "📞 Связаться с менеджером":
        await message.answer(
            "📞 <b>Связь с менеджером</b>\n\n"
            "Вы можете:\n"
            "• 📩 Написать нашему менеджеру: @webdev_manager\n"
            "• 📞 Позвонить: +7 (123) 456-78-90\n"
            "• 📱 Отправить номер для обратного звонка\n\n"
            "<b>Форматы номеров:</b>\n"
            "• +7 XXX XXX-XX-XX\n"
            "• 8 XXX XXX-XX-XX\n"
            "• XXX-XX-XX\n\n"
            "Или нажмите кнопку ниже чтобы отправить номер автоматически:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_phone_kb()
        )
        await state.set_state(Form.waiting_for_phone)

    elif text == "ℹ О компании":
        await message.answer(
            "<b>ДипломМастер</b>\n\n"
            "🖥 Профессиональные авторы, работаем с 2015 года\n\n"
            "✅ 15000+ успешных проектов\n"
            "✅ Команда из 15 специалистов\n"
            "✅ Гарантия на работы\n\n"
            "Наш сайт: example.com",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_kb()
        )

    elif text == "⬅ Назад в меню" or text == "❌ Отменить":
        await state.clear()
        await message.answer("Главное меню:", reply_markup=get_main_kb())


# Обработчик отправки контакта через кнопку
@dp.message(F.contact)
async def process_contact(message: types.Message, state: FSMContext):
    if message.contact:
        phone_number = message.contact.phone_number
        formatted_phone = format_phone_for_display(phone_number)

        await message.answer(
            f"✅ <b>Спасибо!</b>\n\n"
            f"Мы получили ваш номер: <b>{formatted_phone}</b>\n"
            f"Менеджер свяжется с вами в течение 15 минут.",
            parse_mode=ParseMode.HTML
        )

        # Отправка уведомления менеджеру
        await send_manager_notification(phone_number, message.from_user.username, "контакт", message.date)

        await state.clear()
        await message.answer("Чем еще могу помочь?", reply_markup=get_main_kb())


# Обработчик ввода номера телефона вручную
@dp.message(Form.waiting_for_phone)
async def process_phone_input(message: types.Message, state: FSMContext):
    phone_text = message.text

    # Проверяем валидность номера
    if is_valid_phone(phone_text):
        formatted_phone = format_phone_for_display(phone_text)

        await message.answer(
            f"✅ <b>Спасибо!</b>\n\n"
            f"Мы получили ваш номер: <b>{formatted_phone}</b>\n"
            f"Менеджер свяжется с вами в течение 15 минут.",
            parse_mode=ParseMode.HTML
        )

        # Отправка уведомления менеджеру
        await send_manager_notification(phone_text, message.from_user.username, "ручной ввод", message.date)

        await state.clear()
        await message.answer("Чем еще могу помочь?", reply_markup=get_main_kb())
    else:
        # Номер невалидный - показываем подробное сообщение об ошибке
        error_message = get_phone_error_message(phone_text)

        await message.answer(
            f"{error_message}\n\n"
            "📋 <b>Правильные форматы номеров:</b>\n"
            "• +7 (900) 123-45-67\n"
            "• 8 (900) 123-45-67\n"
            "• 79001234567\n"
            "• 9001234567\n\n"
            "<b>Советы:</b>\n"
            "• Убедитесь, что номер содержит 10-11 цифр\n"
            "• Можно использовать пробелы, скобки и дефисы\n"
            "• Или нажмите кнопку ниже для автоматической отправки\n\n"
            "Попробуйте ввести номер еще раз:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_phone_kb()
        )


# Функция отправки уведомления менеджеру
async def send_manager_notification(phone: str, username: str, source: str, date):
    try:
        formatted_phone = format_phone_for_display(phone)
        username_display = f"@{username}" if username else "не указан"

        await bot.send_message(
            chat_id=1169059987,
            text=f"📞 <b>Новая заявка на обратный звонок</b>\n\n"
                 f"📱 Номер: {formatted_phone}\n"
                 f"👤 Пользователь: {username_display}\n"
                 f"📝 Способ: {source}\n"
                 f"⏰ Время: {date.strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления менеджеру: {e}")


# Обработчик инлайн-кнопок услуг
@dp.callback_query(F.data.startswith('service_'))
async def process_service(callback: types.CallbackQuery):
    service_key = callback.data.split('_')[1]
    service = SERVICES.get(service_key)

    if service:
        text = (
            f"<b>{service['name']}</b>\n\n"
            f"{service['description']}\n\n"
            f"💵 <b>Стоимость:</b> {service['price']}\n\n"
            f"<u>Что включено:</u>\n{service['details']}\n\n"
            "Для заказа или консультации нажмите кнопку ниже:"
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="🛒 Заказать услугу", callback_data=f"order_{service_key}")
        builder.button(text="👨‍💼 Консультация", callback_data="consult")
        builder.adjust(1)

        await callback.message.edit_text(
            text=text,
            reply_markup=builder.as_markup(),
            parse_mode=ParseMode.HTML
        )
    await callback.answer()


# Обработчик кнопки заказа
@dp.callback_query(F.data.startswith('order_'))
async def process_order(callback: types.CallbackQuery, state: FSMContext):
    service_key = callback.data.split('_')[1]
    service = SERVICES.get(service_key)

    if service:
        await callback.message.answer(
            f"✅ Вы выбрали услугу <b>{service['name']}</b>\n\n"
            "Для оформления заказа напишите нашему менеджеру: @webdev_manager\n"
            "Или оставьте ваш номер телефона для обратного звонка:\n\n"
            "Нажмите кнопку ниже чтобы отправить номер автоматически:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_phone_kb()
        )
        await state.set_state(Form.waiting_for_phone)
    await callback.answer()


# Обработчик кнопки консультации
@dp.callback_query(F.data == 'consult')
async def process_consult(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "👨‍💼 <b>Консультация специалиста</b>\n\n"
        "Наши менеджеры ответят на все ваши вопросы:\n\n"
        "📩 Написать: @webdev_manager\n"
        "📞 Позвонить: +7 (123) 456-78-90\n\n"
        "Или оставьте ваш номер телефона, и мы вам перезвоним.\n\n"
        "Нажмите кнопку ниже чтобы отправить номер автоматически:",
        parse_mode=ParseMode.HTML,
        reply_markup=get_phone_kb()
    )
    await state.set_state(Form.waiting_for_phone)
    await callback.answer()


# Запуск бота
async def main():
    logger.info("Бот запускается...")
    await dp.start_polling(bot)


if __name__ == '__main__':
    import asyncio

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")