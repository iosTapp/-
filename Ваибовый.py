import asyncio
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

# ================= КОНФИГУРАЦИЯ =================
BOT_TOKEN = "9209728518:AAHfhPkeNzvOla3WkaljoSr9jWINWiiPZoo"  # Токен от @BotFather
ADMIN_IDS = [6242943729]        # Твой Telegram ID

REQUIRED_CHANNELS = [
    {"name": "Карманный Вайб", "url": "https://t.me/pocket_vibe", "channel_id": "@pocket_vibe"},
    {"name": "IOS ROI", "url": "https://t.me/iosroi", "channel_id": "@iosroi"}
]

# База данных в памяти
db = {
    "users": {},     # user_id: {"stars": int, "purchased_prompts": []}
    "posts": [],     # тексты или словари с photo/caption
    "prompts": [],   # {"text": str, "price": int}
    "files": [],
    "promocodes": {} # code: stars_amount
}

# ================= СОСТОЯНИЯ (FSM) =================
class AdminState(StatesGroup):
    waiting_for_post = State()
    waiting_for_prompt_text = State()
    waiting_for_prompt_price = State()
    waiting_for_file = State()
    waiting_for_broadcast = State()
    waiting_for_promo_code = State()
    waiting_for_promo_stars = State()

class UserState(StatesGroup):
    waiting_for_promo_input = State()

temp_admin_data = {}

# ================= ИНИЦИАЛИЗАЦИЯ =================
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= КЛАВИАТУРЫ =================
def main_keyboard(user_id: int):
    buttons = [
        [KeyboardButton(text="📢 Посты"), KeyboardButton(text="🤖 Промты нейросетей")],
        [KeyboardButton(text="📁 Файлы"), KeyboardButton(text="👤 Профиль")],
        [KeyboardButton(text="⭐ Магазин звезд"), KeyboardButton(text="🎁 Ввести промокод")]
    ]
    if user_id in ADMIN_IDS:
        buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def admin_keyboard():
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить пост (Текст/Фото)", callback_data="add_post")],
        [InlineKeyboardButton(text="➕ Добавить промпт", callback_data="add_prompt")],
        [InlineKeyboardButton(text="➕ Добавить файл", callback_data="add_file")],
        [InlineKeyboardButton(text="📊 Статистика бота", callback_data="bot_stats")],
        [InlineKeyboardButton(text="📢 Сделать рассылку", callback_data="make_broadcast")],
        [InlineKeyboardButton(text="🎁 Создать промокод", callback_data="create_promo")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def sub_keyboard():
    buttons = []
    for ch in REQUIRED_CHANNELS:
        buttons.append([InlineKeyboardButton(text=f"📢 Подписаться: {ch['name']}", url=ch['url'])])
    buttons.append([InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def profile_keyboard():
    buttons = [
        # Пополнение в рублях через @pocket79
        [InlineKeyboardButton(text="⭐ Пополнить (Рубли)", url="https://t.me/pocket79")],
        [InlineKeyboardButton(text="🎁 Активировать промокод", callback_data="enter_promo")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def prompt_action_keyboard(index: int, price: int, user_id: int):
    user_data = db["users"].setdefault(user_id, {"stars": 0, "purchased_prompts": []})
    is_purchased = index in user_data["purchased_prompts"] or price == 0
    
    if is_purchased:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔓 Открыть промпт", callback_data=f"open_prompt_{index}")]
        ])
    else:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🔒 Купить за ⭐ {price}", callback_data=f"buy_prompt_{index}")],
            [InlineKeyboardButton(text="⭐ Пополнить (Рубли)", url="https://t.me/pocket79")]
        ])

# ================= ПРОВЕРКА ПОДПИСКИ =================
async def check_subscriptions(user_id: int) -> bool:
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel["channel_id"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception as e:
            logging.error(f"Ошибка проверки подписки: {e}")
            continue
    return True

def get_or_create_user(user_id: int):
    if user_id not in db["users"]:
        db["users"][user_id] = {"stars": 0, "purchased_prompts": []}
    return db["users"][user_id]

# ================= ОБРАБОТЧИКИ СТАРТА И МЕНЮ =================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    get_or_create_user(user_id)

    if not await check_subscriptions(user_id):
        await message.answer(
            "👋 **Привет! Добро пожаловать в Карманный Вайб!**\n\n"
            "✨ Чтобы получить доступ к эксклюзивным материалам, постам, файлам и промптам, пожалуйста, подпишитесь на наши каналы:",
            reply_markup=sub_keyboard(),
            parse_mode="Markdown"
        )
        return

    await message.answer(
        "✨ **Добро пожаловать в Карманный Вайб!**\n\nВыберите нужный раздел в меню ниже 👇",
        reply_markup=main_keyboard(user_id),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    if await check_subscriptions(user_id):
        await call.message.delete()
        await call.message.answer(
            "✅ **Подписка успешно подтверждена!**\n\nДобро пожаловать в мир полезных файлов и нейросетей.",
            reply_markup=main_keyboard(user_id),
            parse_mode="Markdown"
        )
    else:
        await call.answer("❌ Вы подписались еще не на все каналы!", show_alert=True)

# --- Профиль ---
@dp.message(F.text == "👤 Профиль")
async def show_profile(message: types.Message):
    user_id = message.from_user.id
    if not await check_subscriptions(user_id):
        await message.answer("❌ Сначала подпишитесь на каналы!", reply_markup=sub_keyboard())
        return

    user = get_or_create_user(user_id)
    await message.answer(
        f"👤 **Ваш профиль:**\n\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"⭐ **Баланс звезд:** `{user['stars']} ⭐`\n\n"
        f"💡 Покупайте платные промпты и открывайте лучшие инструменты нейросетей!",
        reply_markup=profile_keyboard(),
        parse_mode="Markdown"
    )

# --- Магазин звезд ---
@dp.message(F.text == "⭐ Магазин звезд")
async def show_star_shop(message: types.Message):
    user_id = message.from_user.id
    if not await check_subscriptions(user_id):
        await message.answer("❌ Сначала подпишитесь на каналы!", reply_markup=sub_keyboard())
        return

    await message.answer(
        "⭐ **Покупка звезд за рубли**\n\n"
        "Здесь вы можете пополнить внутренний баланс звезд для покупки премиальных промптов.\n\n"
        "Напишите нашему менеджеру по кнопке ниже:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Написать @pocket79", url="https://t.me/pocket79")]
        ]),
        parse_mode="Markdown"
    )

# --- Посты ---
@dp.message(F.text == "📢 Посты")
async def show_posts(message: types.Message):
    user_id = message.from_user.id
    if not await check_subscriptions(user_id):
        await message.answer("❌ Сначала подпишитесь на каналы!", reply_markup=sub_keyboard())
        return
    
    if not db["posts"]:
        await message.answer("📭 Постов пока нет. Загляните сюда чуть позже!")
        return
    
    for post in db["posts"]:
        if isinstance(post, dict) and "photo" in post:
            await message.answer_photo(photo=post["photo"], caption=post.get("caption", ""))
        else:
            await message.answer(post)

# --- Промты нейросетей ---
@dp.message(F.text == "🤖 Промты нейросетей")
async def show_prompts(message: types.Message):
    user_id = message.from_user.id
    if not await check_subscriptions(user_id):
        await message.answer("❌ Сначала подпишитесь на каналы!", reply_markup=sub_keyboard())
        return

    if not db["prompts"]:
        await message.answer("📭 Промптов пока нет.")
        return
    
    for i, p in enumerate(db["prompts"]):
        price_tag = "Бесплатно 🟢" if p["price"] == 0 else f"Платный ⭐ {p['price']}"
        await message.answer(
            f"🤖 **Промпт #{i+1}**\n🏷 Статус: {price_tag}",
            reply_markup=prompt_action_keyboard(i, p["price"], user_id),
            parse_mode="Markdown"
        )

@dp.callback_query(F.data.startswith("open_prompt_"))
async def open_prompt(call: types.CallbackQuery):
    index = int(call.data.split("_")[2])
    prompt_data = db["prompts"][index]
    await call.message.answer(f"🧠 **Текст промпта:**\n\n`{prompt_data['text']}`", parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data.startswith("buy_prompt_"))
async def buy_prompt(call: types.CallbackQuery):
    user_id = call.from_user.id
    index = int(call.data.split("_")[2])
    prompt_data = db["prompts"][index]
    user = get_or_create_user(user_id)

    if user["stars"] >= prompt_data["price"]:
        user["stars"] -= prompt_data["price"]
        user["purchased_prompts"].append(index)
        await call.message.edit_text(
            f"🎉 **Промпт успешно разблокирован!**\n\n`{prompt_data['text']}`",
            parse_mode="Markdown"
        )
        await call.answer("Успешная покупка!")
    else:
        await call.answer(f"❌ Недостаточно звезд! Нужно: {prompt_data['price']} ⭐", show_alert=True)

# --- Файлы ---
@dp.message(F.text == "📁 Файлы")
async def show_files(message: types.Message):
    user_id = message.from_user.id
    if not await check_subscriptions(user_id):
        await message.answer("❌ Сначала подпишитесь на каналы!", reply_markup=sub_keyboard())
        return

    if not db["files"]:
        await message.answer("📭 Файлов пока нет.")
        return
    
    for file_item in db["files"]:
        await message.answer_document(
            document=file_item["file_id"],
            caption=file_item.get("caption", "")
        )

# --- Промокоды ---
@dp.message(F.text == "🎁 Ввести промокод")
@dp.callback_query(F.data == "enter_promo")
async def start_promo_input(event: types.Message | types.CallbackQuery, state: FSMContext):
    message = event.message if isinstance(event, types.CallbackQuery) else event
    await state.set_state(UserState.waiting_for_promo_input)
    await message.answer("🎁 Введите ваш промокод:")
    if isinstance(event, types.CallbackQuery):
        await event.answer()

@dp.message(UserState.waiting_for_promo_input)
async def process_promo_input(message: types.Message, state: FSMContext):
    code = message.text.strip()
    user_id = message.from_user.id
    user = get_or_create_user(user_id)

    if code in db["promocodes"]:
        reward = db["promocodes"].pop(code)
        user["stars"] += reward
        await state.clear()
        await message.answer(f"🎉 Промокод успешно активирован! Вам начислено **{reward} ⭐**.", parse_mode="Markdown", reply_markup=main_keyboard(user_id))
    else:
        await state.clear()
        await message.answer("❌ Неверный или уже использованный промокод.", reply_markup=main_keyboard(user_id))

# ================= АДМИН-ПАНЕЛЬ =================
@dp.message(F.text == "⚙️ Админ-панель")
async def admin_panel(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("⚙️ **Панель администратора:**\nВыберите действие:", reply_markup=admin_keyboard(), parse_mode="Markdown")

# --- Статистика бота ---
@dp.callback_query(F.data == "bot_stats")
async def bot_stats(call: types.CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    total_users = len(db["users"])
    total_posts = len(db["posts"])
    total_prompts = len(db["prompts"])
    total_files = len(db["files"])

    stats_text = (
        f"📊 **Статистика бота:**\n\n"
        f"👥 Пользователей в базе: `{total_users}`\n"
        f"📢 Постов: `{total_posts}`\n"
        f"🤖 Промптов: `{total_prompts}`\n"
        f"📁 Файлов: `{total_files}`"
    )
    await call.message.answer(stats_text, parse_mode="Markdown")
    await call.answer()

# --- Добавление поста ---
@dp.callback_query(F.data == "add_post")
async def start_add_post(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminState.waiting_for_post)
    await call.message.answer("✍️ Отправьте текст поста или фото с подписью:")
    await call.answer()

@dp.message(AdminState.waiting_for_post)
async def process_add_post(message: types.Message, state: FSMContext):
    if message.photo:
        photo_id = message.photo[-1].file_id
        caption = message.caption or ""
        db["posts"].append({"photo": photo_id, "caption": caption})
    else:
        db["posts"].append(message.text)
        
    await state.clear()
    await message.answer("✅ Пост успешно добавлен!", reply_markup=main_keyboard(message.from_user.id))

# --- Добавление промпта ---
@dp.callback_query(F.data == "add_prompt")
async def start_add_prompt(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminState.waiting_for_prompt_text)
    await call.message.answer("✍️ Отправьте текст промпта:")
    await call.answer()

@dp.message(AdminState.waiting_for_prompt_text)
async def process_prompt_text(message: types.Message, state: FSMContext):
    temp_admin_data[message.from_user.id] = {"text": message.text}
    await state.set_state(AdminState.waiting_for_prompt_price)
    await message.answer("💰 Введите цену промпта в звездах (например `0` или `15`):", parse_mode="Markdown")

@dp.message(AdminState.waiting_for_prompt_price)
async def process_prompt_price(message: types.Message, state: FSMContext):
    try:
        price = int(message.text.strip())
        text = temp_admin_data[message.from_user.id]["text"]
        db["prompts"].append({"text": text, "price": price})
        await state.clear()
        await message.answer(f"✅ Промпт добавлен со стоимостью **{price} ⭐**!", reply_markup=main_keyboard(message.from_user.id), parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Введите число (цену в звездах):")

# --- Добавление файла ---
@dp.callback_query(F.data == "add_file")
async def start_add_file(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminState.waiting_for_file)
    await call.message.answer("📎 Отправьте документ или файл:")
    await call.answer()

@dp.message(AdminState.waiting_for_file, F.document)
async def process_add_file(message: types.Message, state: FSMContext):
    db["files"].append({
        "file_id": message.document.file_id,
        "caption": message.caption or ""
    })
    await state.clear()
    await message.answer("✅ Файл успешно добавлен!", reply_markup=main_keyboard(message.from_user.id))

# --- Рассылка ---
@dp.callback_query(F.data == "make_broadcast")
async def start_broadcast(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminState.waiting_for_broadcast)
    await call.message.answer("📢 Отправьте сообщение (текст, фото) для рассылки всем пользователям:")
    await call.answer()

@dp.message(AdminState.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    await state.clear()
    success_count = 0
    fail_count = 0

    await message.answer("⏳ Рассылка запущена...")
    for user_id in db["users"].keys():
        try:
            if message.photo:
                await bot.send_photo(chat_id=user_id, photo=message.photo[-1].file_id, caption=message.caption or "")
            else:
                await bot.send_message(chat_id=user_id, text=message.text)
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception:
            fail_count += 1

    await message.answer(f"✅ Рассылка завершена!\nУспешно: {success_count}\nОшибок/Заблокировали: {fail_count}", reply_markup=main_keyboard(message.from_user.id))

# --- Создание промокода ---
@dp.callback_query(F.data == "create_promo")
async def start_create_promo(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminState.waiting_for_promo_code)
    await call.message.answer("🎁 Введите текст промокода (например: `VIBE2026`):", parse_mode="Markdown")
    await call.answer()

@dp.message(AdminState.waiting_for_promo_code)
async def process_promo_code(message: types.Message, state: FSMContext):
    temp_admin_data[message.from_user.id] = {"code": message.text.strip()}
    await state.set_state(AdminState.waiting_for_promo_stars)
    await message.answer("⭐ Укажите количество звезд, которое дарит этот промокод:")

@dp.message(AdminState.waiting_for_promo_stars)
async def process_promo_stars(message: types.Message, state: FSMContext):
    try:
        stars = int(message.text.strip())
        code = temp_admin_data[message.from_user.id]["code"]
        db["promocodes"][code] = stars
        await state.clear()
        await message.answer(f"✅ Промокод `{code}` на **{stars} ⭐** успешно создан!", parse_mode="Markdown", reply_markup=main_keyboard(message.from_user.id))
    except ValueError:
        await message.answer("❌ Введите число (количество звезд):")

# ================= ЗАПУСК =================
async def main():
    print("Бот 'Карманный Вайб' запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
