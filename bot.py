import asyncio
import logging
import sqlite3
import time
import os
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
if not API_TOKEN or not isinstance(API_TOKEN, str):
    raise ValueError("API_TOKEN is not set or invalid in .env file. Please set a valid bot token (e.g., API_TOKEN=your_bot_token in .env).")

ADMIN_ID = int(os.getenv("ADMIN_ID", 6448909987))
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN", "your_payment_token")  # Click yoki Payme tokeni
REQUIRED_CHANNEL = "@semagency_channel"
REQUIRED_CHANNEL_LINK = "https://t.me/semagency_channel"
PROMO_CODES = {"Samandar06": 0.10, "Semagensy": 0.05}
COMPLEXITY_PRICES = {"oddiy": 100_000, "orta": 150_000, "murakkab": 200_000}
DB_PATH = "orders.db"

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database initialization
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                service TEXT,
                details TEXT,
                colors TEXT,
                complexity TEXT,
                promo_code TEXT,
                promo_discount REAL,
                referral_discount REAL,
                total_price INTEGER,
                timestamp INTEGER,
                status TEXT DEFAULT 'pending',
                payment_status TEXT DEFAULT 'pending'
            )
        """)
        conn.commit()

init_db()

# State definitions
class OrderStates(StatesGroup):
    main_menu = State()
    waiting_details = State()
    waiting_colors = State()
    waiting_complexity = State()
    waiting_promo_choice = State()
    waiting_promo_code = State()
    waiting_payment_confirmation = State()

# Keyboard definitions
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Grafik Dizayn", callback_data="service_design")],
        [InlineKeyboardButton(text="✍️ Telegram bot yaratish", callback_data="service_content")],
        [InlineKeyboardButton(text="💻 Web Dasturlash", callback_data="service_web")],
        [InlineKeyboardButton(text="✍️ Ijtimoiy tarmoqlarni avtomatlashtirish", callback_data="service_content")],
        [InlineKeyboardButton(text="📋 Mening Buyurtmalarim", callback_data="my_orders")]
    ])

def promo_choice_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Ha", callback_data="promo_yes"),
         InlineKeyboardButton(text="❌ Yo‘q", callback_data="promo_no")]
    ])

def complexity_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Oddiy", callback_data="complexity_oddiy")],
        [InlineKeyboardButton(text="O‘rtacha", callback_data="complexity_orta")],
        [InlineKeyboardButton(text="Murakkab", callback_data="complexity_murakkab")]
    ])

def back_to_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Bosh menyuga", callback_data="back_to_menu")]
    ])

def subscription_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Obuna bo‘lish", url=REQUIRED_CHANNEL_LINK)],
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subscription")]
    ])

def payment_confirmation_kb(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 To‘lov qilish", callback_data=f"pay_{order_id}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_order")]
    ])

def admin_order_management_kb(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin_approve_{order_id}")],
        [InlineKeyboardButton(text="❌ Rad etish", callback_data=f"admin_reject_{order_id}")]
    ])

def terms_confirmation_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlayman", callback_data="accept_terms")],
        [InlineKeyboardButton(text="❌ Rad etaman", callback_data="reject_terms")]
    ])

# Bot and Dispatcher setup
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher(storage=MemoryStorage())

# Subscription check
async def check_subscription(user_id: int) -> bool:
    try:
        chat_member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return chat_member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Subscription check failed: {e}")
        return False

# Handlers
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} sent /start command")
    if not await check_subscription(message.from_user.id):
        await message.answer(
            f"Iltimos, avval [kanalga obuna bo‘ling]({REQUIRED_CHANNEL_LINK})!",
            reply_markup=subscription_kb(),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    await state.clear()
    terms = (
        "📋 *FOYDALANISH SHARTLARI*\n\n"
        "Hurmatli mijoz! Buyurtma berishdan avval quyidagi shartlar bilan tanishib chiqing:\n\n"
        "🔹 *To‘lov tartibi:*\n"
        "Buyurtma tasdiqlangach, 25% oldindan to‘lov amalga oshiriladi.\n"
        "Qolgan 75% ish yakunlangandan so‘ng, yakuniy versiyani taqdim etishdan oldin to‘lanadi.\n\n"
        "🔹 *Dizaynni o‘zgartirish:*\n"
        "3 martagacha bepul tahrir (kattaroq o‘zgarishlar emas, faqat kichik tuzatishlar).\n"
        "3 martadan keyingi har bir o‘zgartirish uchun qo‘shimcha to‘lov olinadi (summasi ish murakkabligiga qarab belgilanadi).\n\n"
        "🔹 *Muddatlar:*\n"
        "Har bir buyurtmaning bajarilish muddati uning murakkabligi va mavjud navbatga qarab belgilanadi.\n"
        "Muddati haqida alohida xabar beriladi.\n\n"
        "🔹 *Buyurtmadan voz kechish:*\n"
        "Agar buyurtma bekor qilinsa:\n"
        "- Ish boshlanmagan bo‘lsa, to‘liq pul qaytariladi.\n"
        "- Ish boshlangan bo‘lsa, oldindan to‘lov qaytarilmaydi.\n\n"
        "🔹 *Promokodlar:*\n"
        "Aksiya yoki promokodlardan faqat bir marta foydalanish mumkin.\n"
        "Har bir promokodda alohida amal qilish muddati mavjud.\n\n"
        "🔹 *Materiallar va ma’lumotlar:*\n"
        "Mijoz topshirgan rasm, matn, logotip kabi materiallar sifatli bo‘lishi lozim.\n"
        "Noto‘g‘ri yoki sifatsiz ma’lumot sababli kechikishlar uchun mas’uliyat olinmaydi.\n\n"
        "🔹 *Bog‘lanish:*\n"
        "Har qanday savollar, aniqlik kiritish yoki holatni kuzatib borish uchun biz bilan bog‘lanishingiz mumkin.\n"
    )
    await message.answer(terms, parse_mode=ParseMode.MARKDOWN, reply_markup=terms_confirmation_kb())

@dp.callback_query(F.data == "accept_terms")
async def accept_terms(callback: CallbackQuery, state: FSMContext):
    logger.info(f"User {callback.from_user.id} accepted the terms")
    await state.set_state(OrderStates.main_menu)
    await callback.message.edit_text("Xush kelibsiz! Xizmat turini tanlang:", reply_markup=main_menu_kb())

@dp.callback_query(F.data == "reject_terms")
async def reject_terms(callback: CallbackQuery, state: FSMContext):
    logger.info(f"User {callback.from_user.id} rejected the terms")
    await callback.message.edit_text("Foydalanish shartlarini rad etdingiz. Xizmatlardan foydalanish uchun shartlarni tasdiqlashingiz kerak.")

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, state: FSMContext):
    logger.info(f"User {callback.from_user.id} clicked check_subscription")
    if await check_subscription(callback.from_user.id):
        await state.clear()
        await state.set_state(OrderStates.main_menu)
        await callback.message.edit_text("Xush kelibsiz! Xizmat turini tanlang:", reply_markup=main_menu_kb())
    else:
        await callback.message.edit_text(
            f"Iltimos, avval {REQUIRED_CHANNEL_LINK} kanaliga obuna bo‘ling!",
            reply_markup=subscription_kb()
        )

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    logger.info(f"User {callback.from_user.id} clicked back_to_menu")
    await state.clear()
    await state.set_state(OrderStates.main_menu)
    await callback.message.edit_text("Xush kelibsiz! Xizmat turini tanlang:", reply_markup=main_menu_kb())

@dp.callback_query(F.data.startswith("service_"))
async def service_chosen(callback: CallbackQuery, state: FSMContext):
    logger.info(f"User {callback.from_user.id} chose service: {callback.data}")
    service = callback.data.replace("service_", "")
    await state.update_data(service=service)

    # Customize the next step based on the selected service
    if service == "design":
        await state.set_state(OrderStates.waiting_details)
        await callback.message.edit_text("Buyurtma tafsilotlarini yozing:", reply_markup=back_to_menu_kb())
    elif service == "content":
        await state.set_state(OrderStates.waiting_details)
        await callback.message.edit_text("Telegram bot yoki avtomatlashtirish uchun talablaringizni yozing:", reply_markup=back_to_menu_kb())
    elif service == "web":
        await state.set_state(OrderStates.waiting_details)
        await callback.message.edit_text("Web dasturlash uchun texnik talablaringizni yozing:", reply_markup=back_to_menu_kb())
    else:
        await callback.message.edit_text("Noma'lum xizmat tanlandi. Iltimos, qayta urinib ko‘ring.", reply_markup=back_to_menu_kb())

@dp.message(OrderStates.waiting_details)
async def get_details(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} entered details: {message.text}")
    if not message.text or len(message.text.strip()) < 5:
        await message.answer("Tafsilotlar kamida 5 ta belgidan iborat bo‘lishi kerak. Iltimos, qayta kiriting:")
        return

    data = await state.get_data()
    service = data.get("service")

    await state.update_data(details=message.text)

    # Skip irrelevant questions based on the service
    if service == "design":
        await state.set_state(OrderStates.waiting_colors)
        await message.answer("Dizaynda ishlatiladigan ranglarni kiriting:", reply_markup=back_to_menu_kb())
    elif service in ["content", "web"]:
        await state.set_state(OrderStates.waiting_promo_choice)
        await message.answer("Promokodingiz bormi?", reply_markup=promo_choice_kb())
    else:
        await message.answer("Noma'lum xizmat turi. Iltimos, qayta urinib ko‘ring.")

@dp.message(OrderStates.waiting_colors)
async def get_colors(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} entered colors: {message.text}")
    if not message.text or len(message.text.strip()) < 3:
        await message.answer("Ranglar kamida 3 ta belgidan iborat bo‘lishi kerak. Iltimos, qayta kiriting:")
        return
    await state.update_data(colors=message.text)
    await state.set_state(OrderStates.waiting_promo_choice)
    await message.answer("Promokodingiz bormi?", reply_markup=promo_choice_kb())

@dp.callback_query(F.data.startswith("complexity_"))
async def get_complexity(callback: CallbackQuery, state: FSMContext):
    logger.info(f"User {callback.from_user.id} chose complexity: {callback.data}")
    complexity = callback.data.replace("complexity_", "")
    base_price = COMPLEXITY_PRICES.get(complexity, 100_000)
    await state.update_data(complexity=complexity, base_price=base_price)
    await state.set_state(OrderStates.waiting_promo_choice)
    await callback.message.edit_text("Promokodingiz bormi?", reply_markup=promo_choice_kb())

@dp.callback_query(OrderStates.waiting_promo_choice)
async def promo_choice(callback: CallbackQuery, state: FSMContext):
    if callback.data == "promo_yes":
        await state.set_state(OrderStates.waiting_promo_code)
        await callback.message.edit_text("Promokodingizni kiriting:", reply_markup=back_to_menu_kb())
    elif callback.data == "promo_no":
        await state.update_data(promo_code=None, promo_discount=0)
        # Promokodsiz to'g'ridan-to'g'ri to'lov bosqichiga o'tkaziladi
        await proceed_to_payment(callback.message, state)
    else:
        await callback.answer("Noma'lum amal.", show_alert=True)

@dp.message(OrderStates.waiting_promo_code)
async def promo_code_entered(message: Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} entered promo code: {message.text}, current state: {await state.get_state()}")
    code = message.text.strip()
    if not code:
        await message.answer("Promokod bo‘sh bo‘lmasligi kerak! Iltimos, qayta kiriting:", reply_markup=back_to_menu_kb())
        return
    if code.startswith('/'):
        await message.answer("Iltimos, promokod sifatida buyruq kiritmang. Promokodni qayta kiriting yoki bosh menyuga qayting:", reply_markup=back_to_menu_kb())
        return
    discount = PROMO_CODES.get(code.capitalize(), 0)  # Ensure case-insensitive check
    if not discount:
        await message.answer("Noto‘g‘ri promokod! Iltimos, qayta kiriting yoki bekor qiling:", reply_markup=back_to_menu_kb())
        return
    await state.update_data(promo_code=code, promo_discount=discount)
    logger.info(f"Valid promo code {code} entered by user {message.from_user.id}, proceeding to payment")
    await proceed_to_payment(message, state)

async def proceed_to_payment(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    service = data.get("service", "")
    details = data.get("details", "")
    colors = data.get("colors", "")
    complexity = data.get("complexity", "")
    base_price = data.get("base_price", 100_000)
    promo_code = data.get("promo_code", None)
    promo_discount = data.get("promo_discount", 0)
    referral_discount = 0.05 if user_id % 2 == 0 else 0
    total_discount = promo_discount + referral_discount
    total_price = int(base_price * (1 - total_discount))
    timestamp = int(time.time())

    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO orders (user_id, service, details, colors, complexity, promo_code, promo_discount, referral_discount, total_price, timestamp, status, payment_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'pending')
            """, (user_id, service, details, colors, complexity, promo_code, promo_discount, referral_discount, total_price, timestamp))
            order_id = c.lastrowid
            conn.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        await message.answer("Xatolik yuz berdi, iltimos qayta urinib ko‘ring.")
        return

    text = (
        f"\U0001F9FE *Buyurtma Cheki*\n\n"
        f"🆔 Buyurtma ID: {order_id}\n"
        f"👤 ID: {user_id}\n"
        f"🔧 Xizmat: {service}\n"
        f"🎨 Ranglar: {colors}\n"
        f"📋 Talablar: {details}\n"
        f"📈 Murakkablik: {complexity.capitalize()}\n"
        f"🎟️ Promokod: {promo_code or 'yo‘q'}\n"
        f"💸 Chegirma: {int(total_discount*100)}%\n"
        f"💰 Umumiy narx: {total_price} so‘m\n\n"
        f"✅ Buyurtmani tasdiqlang va to‘lov qiling:"
    )
    await state.update_data(order_id=order_id, total_price=total_price)
    await state.set_state(OrderStates.waiting_payment_confirmation)
    await message.answer(text, reply_markup=payment_confirmation_kb(order_id))
    await bot.send_message(ADMIN_ID, text + "\n\nAdmin tasdiqlashi kutilmoqda:", reply_markup=admin_order_management_kb(order_id))

@dp.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[1])
    data = await state.get_data()
    total_price = data.get("total_price", 0)

    # Your card details
    card_number = "9860 3501 4351 9071"  # Replace with your actual card number
    payment_url = f"https://click.uz/pay?order_id={order_id}&amount={total_price}"  # Example Click payment URL

    try:
        text = (
            f"💳 To‘lov uchun karta raqami: `{card_number}`\n\n"
            f"Yoki quyidagi havola orqali to‘lovni amalga oshiring:\n"
            f"[To‘lov qilish]({payment_url})\n\n"
            f"💰 To‘lov miqdori: {total_price} so‘m"
        )
        await callback.message.edit_text(
            text,
            reply_markup=back_to_menu_kb(),
            parse_mode=ParseMode.MARKDOWN
        )
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("UPDATE orders SET payment_status = 'processing' WHERE id = ?", (order_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Payment error: {e}")
        await callback.message.edit_text("To‘lov jarayonida xatolik yuz berdi. Iltimos, qayta urinib ko‘ring.", reply_markup=back_to_menu_kb())
    await state.clear()

@dp.callback_query(F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("order_id")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Cancel order error: {e}")
        await callback.message.edit_text("Buyurtmani bekor qilishda xatolik yuz berdi.")
        return
    await callback.message.edit_text("Buyurtma bekor qilindi.", reply_markup=back_to_menu_kb())
    await state.clear()

@dp.callback_query(F.data == "my_orders")
async def show_my_orders(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT id, service, total_price, status FROM orders WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
            orders = c.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Error fetching orders for user {user_id}: {e}")
        await callback.message.edit_text("Buyurtmalarni ko‘rishda xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko‘ring.")
        return

    if not orders:
        await callback.message.edit_text("Sizda hali buyurtmalar yo‘q.", reply_markup=back_to_menu_kb())
        return

    text = "📋 *Sizning Buyurtmalaringiz*\n\n"
    for order in orders:
        text += (
            f"🆔 Buyurtma ID: {order[0]}\n"
            f"🔧 Xizmat: {order[1]}\n"
            f"💰 Narx: {order[2]} so‘m\n"
            f"📈 Holat: {order[3].capitalize()}\n\n"
        )
    await callback.message.edit_text(text.strip(), reply_markup=back_to_menu_kb())

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("Sizda admin huquqlari yo‘q!")
        return
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT id, user_id, service, total_price, status FROM orders WHERE status = 'pending' ORDER BY timestamp ASC")
            orders = c.fetchall()
    except sqlite3.Error as e:
        logger.error(f"Admin panel error: {e}")
        await message.answer("Buyurtmalarni ko‘rishda xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko‘ring.")
        return

    if not orders:
        await message.answer("Hozirda tasdiqlanmagan buyurtmalar yo‘q.")
        return

    for order in orders:
        text = (
            f"🆔 Buyurtma ID: {order[0]}\n"
            f"👤 Foydalanuvchi ID: {order[1]}\n"
            f"🔧 Xizmat: {order[2]}\n"
            f"💰 Narx: {order[3]} so‘m\n"
            f"📈 Holat: {order[4].capitalize()}\n"
        )
        await message.answer(text.strip(), reply_markup=admin_order_management_kb(order[0]))

@dp.callback_query(F.data.startswith("admin_approve_"))
async def admin_approve_order(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.message.edit_text("Sizda admin huquqlari yo‘q!")
        return
    order_id = int(callback.data.split("_")[2])
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("UPDATE orders SET status = 'approved' WHERE id = ?", (order_id,))
            conn.commit()
            c.execute("SELECT user_id, total_price FROM orders WHERE id = ?", (order_id,))
            user_id, total_price = c.fetchone()
    except Exception as e:
        logger.error(f"Approve order error: {e}")
        await callback.message.edit_text("Buyurtmani tasdiqlashda xatolik yuz berdi.")
        return

    # Notify the user about the approval and ask for confirmation
    text = (
        f"Sizning buyurtmangiz #{order_id} tasdiqlandi!\n\n"
        f"💰 Umumiy narx: {total_price} so‘m\n\n"
        f"✅ Buyurtmani tasdiqlash uchun pastdagi tugmani bosing."
    )
    await bot.send_message(
        user_id,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"user_confirm_{order_id}")],
            [InlineKeyboardButton(text="⬅️ Bosh menyuga", callback_data="back_to_menu")]
        ])
    )
    await callback.message.edit_text(f"Buyurtma #{order_id} tasdiqlandi.")

@dp.callback_query(F.data.startswith("user_confirm_"))
async def user_confirm_order(callback: CallbackQuery, state: FSMContext):
    order_id = int(callback.data.split("_")[2])
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT total_price FROM orders WHERE id = ?", (order_id,))
            total_price = c.fetchone()[0]
    except Exception as e:
        logger.error(f"Error fetching order details: {e}")
        await callback.message.edit_text("Xatolik yuz berdi. Iltimos, qayta urinib ko‘ring.")
        return

    # Proceed to payment instructions
    card_number = "9860 3501 4351 9071"  # Replace with your actual card number
    payment_url = f"https://click.uz/pay?order_id={order_id}&amount={total_price}"  # Example Click payment URL
    text = (
        f"💳 To‘lov uchun karta raqami: `{card_number}`\n\n"
        f"Yoki quyidagi havola orqali to‘lovni amalga oshiring:\n"
        f"[To‘lov qilish]({payment_url})\n\n"
        f"💰 To‘lov miqdori: {total_price} so‘m\n\n"
        f"✅ To‘lovni amalga oshirgandan so‘ng, iltimos, to‘lov chekini suratga olib jo‘nating."
    )
    await callback.message.edit_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_to_menu_kb()
    )
    await state.clear()

@dp.callback_query(F.data.startswith("admin_reject_"))
async def admin_reject_order(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.message.edit_text("Sizda admin huquqlari yo‘q!")
        return
    order_id = int(callback.data.split("_")[2])
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("UPDATE orders SET status = 'rejected' WHERE id = ?", (order_id,))
            conn.commit()
            c.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
            user_id = c.fetchone()[0]
    except Exception as e:
        logger.error(f"Reject order error: {e}")
        await callback.message.edit_text("Buyurtmani rad etishda xatolik yuz berdi.")
        return
    await callback.message.edit_text(f"Buyurtma #{order_id} rad etildi.")
    await bot.send_message(user_id, f"Sizning buyurtmangiz #{order_id} rad etildi.")

# Fallback handler for unexpected commands
@dp.message()
async def handle_unexpected(message: Message, state: FSMContext):
    current_state = await state.get_state()
    logger.warning(f"Unexpected message from user {message.from_user.id} in state {current_state}: {message.text}")
    await message.answer("Iltimos, jarayonni davom ettiring yoki /start buyrug‘i bilan qayta boshlang.")

async def finish_order(msg, state: FSMContext):
    data = await state.get_data()
    if data.get("order_completed"):
        return  # oldin bajarilgan bo‘lsa, takrorlamaslik uchun chiqamiz
    await state.update_data(order_completed=True)

# Main execution
if __name__ == "__main__":
    logger.info("Bot started polling")
    asyncio.run(dp.start_polling(bot))