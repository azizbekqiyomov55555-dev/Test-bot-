import asyncio
import sqlite3
import logging
from datetime import datetime
import pytz
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton,
    WebAppInfo
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart, Command

# ================== SOZLAMALAR ==================
BOT_TOKEN = "8754943455:AAF9epI3TVDOHy-U9FGaPxxU7cOjZ7MVufg"
ADMIN_ID = 8537782289
MAIN_CHANNEL_ID = "@sevaraakkk"
# ================================================

# ================== BAZA SOZLAMALARI ==================
DB_NAME = "bot_data.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id INTEGER PRIMARY KEY, full_name TEXT, username TEXT, join_date TEXT,
                      posted_ads INTEGER DEFAULT 0, paid_slots INTEGER DEFAULT 0, pending_approval INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings 
                     (key TEXT PRIMARY KEY, value TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS channels 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT, url TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS ads 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, video_id TEXT, text TEXT, status TEXT DEFAULT 'pending')''')
        # UC narxlari jadvali
        c.execute('''CREATE TABLE IF NOT EXISTS uc_prices 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, uc_amount INTEGER, price INTEGER, position INTEGER DEFAULT 0)''')
        # UC buyurtmalar jadvali
        c.execute('''CREATE TABLE IF NOT EXISTS uc_orders 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, full_name TEXT, username TEXT,
                      uc_amount INTEGER, price INTEGER, pubg_id TEXT, screenshot_id TEXT,
                      status TEXT DEFAULT 'pending', order_date TEXT)''')

        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('price', '50000')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('card', '8600 0000 0000 0000 (Ism Familiya)')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('start_msg', 'Salom {name}! Siz bu botdan PUBG Mobile akkauntingizni obzorini joylashingiz mumkin va u video kanalga joylanadi.')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('site_url', 'https://azizbekqiyomov55555-dev.github.io/Test-bot-')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('uc_card', '8600 0000 0000 0000 (Ism Familiya)')")
        conn.commit()

def db_query(query, params=(), fetchone=False, fetchall=False):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute(query, params)
        if fetchone: return c.fetchone()
        if fetchall: return c.fetchall()
        conn.commit()
        return c.lastrowid

init_db()

# ================== FSM HOLATLAR ==================
class AdForm(StatesGroup):
    video = State()
    level = State()
    guns = State()
    xsuits = State()
    rp = State()
    cars = State()
    price = State()
    phone = State()

class PaymentForm(StatesGroup):
    receipt = State()

class SupportForm(StatesGroup):
    msg = State()

class AdminForm(StatesGroup):
    start_msg = State()
    price = State()
    card = State()
    add_channel_id = State()
    add_channel_url = State()
    reply_msg = State()
    uc_card = State()
    uc_price_amount = State()
    uc_price_value = State()

# UC buyurtma FSM
class UCOrderForm(StatesGroup):
    pubg_screenshot = State()  # PUBG ID rasmi
    receipt = State()          # To'lov cheki

# ================== BOT VA ROUTER ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# ================== YORDAMCHI FUNKSIYALAR ==================
def get_time_tashkent():
    tz = pytz.timezone('Asia/Tashkent')
    return datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

def get_setting(key):
    res = db_query("SELECT value FROM settings WHERE key=?", (key,), fetchone=True)
    return res[0] if res else ""

async def check_subscription(user_id):
    channels = db_query("SELECT channel_id, url FROM channels", fetchall=True)
    unsubbed = []
    for ch_id, url in channels:
        try:
            member = await bot.get_chat_member(ch_id, user_id)
            if member.status in ['left', 'kicked']:
                unsubbed.append(url)
        except:
            pass
    return unsubbed

# ================== ASOSIY MENU — RANGLI REPLYKEYBOARD ==================
# Bot API 9.4 — style parametri:
#   'primary'     → KO'K  rang
#   'success'     → YASHIL rang
#   'danger'      → QIZIL rang
#
# user_id berilsa va ADMIN_ID ga teng bo'lsa → "🔧 Boshqarish" tugmasi ko'rinadi
def get_main_menu(user_id=None):
    keyboard = [
        [
            KeyboardButton(text="📝 E'lon berish", style="primary"),
            KeyboardButton(text="🆘 Yordam", style="danger"),
        ],
        [
            KeyboardButton(text="🎮 PUBG MOBILE UC OLISH 💎", style="success"),
        ]
    ]
    # Faqat adminga "Boshqarish" tugmasi ko'rinadi
    if user_id == ADMIN_ID:
        keyboard.append([
            KeyboardButton(text="🔧 Boshqarish", style="primary")
        ])
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Quyidagi tugmalardan birini tanlang 👇"
    )

# ================== ADMIN MENU — REPLYKEYBOARD ==================
def get_admin_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika", style="primary"),
                KeyboardButton(text="📦 UC buyurtmalar", style="primary"),
            ],
            [
                KeyboardButton(text="💰 Narx o'zgartirish", style="primary"),
                KeyboardButton(text="💳 Karta o'zgartirish", style="primary"),
            ],
            [
                KeyboardButton(text="📝 Start xabar", style="primary"),
            ],
            [
                KeyboardButton(text="➕ Kanal qo'shish", style="success"),
                KeyboardButton(text="➖ Kanal o'chirish", style="danger"),
            ],
            [
                KeyboardButton(text="💎 UC narxi qo'shish", style="success"),
                KeyboardButton(text="📋 UC narxlari", style="primary"),
            ],
            [
                KeyboardButton(text="💳 UC karta", style="primary"),
            ],
            [
                KeyboardButton(text="🔙 Asosiy menyu", style="danger"),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="⚙️ Admin panel 👇"
    )

# ================== UC NARXLARI INLINE KLAVIATURA ==================
def get_uc_prices_keyboard(page=0):
    """UC narxlarini chap/o'ng tugmalar bilan ko'rsatadi"""
    prices = db_query("SELECT id, uc_amount, price FROM uc_prices ORDER BY position ASC, uc_amount ASC", fetchall=True)
    
    if not prices:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Hozircha narxlar kiritilmagan", callback_data="uc_no_prices")]
        ])
    
    ITEMS_PER_PAGE = 5
    total_pages = (len(prices) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_prices = prices[start:end]
    
    # 3 xil rang navbatma-navbat: yashil, ko'k, qizil
    color_cycle = ["success", "primary", "danger"]

    rows = []
    for i, (pid, uc_amount, price) in enumerate(current_prices):
        style = color_cycle[i % 3]
        rows.append([
            InlineKeyboardButton(
                text=f"💎 {uc_amount} UC — {price:,} so'm".replace(",", " "),
                callback_data=f"buy_uc_{pid}_{uc_amount}_{price}",
                style=style
            )
        ])

    # Navigatsiya tugmalari
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"uc_page_{page-1}", style="primary"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"uc_page_{page+1}", style="primary"))

    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="uc_back", style="danger")])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ================== START VA OBUNA ==================
@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    await state.clear()
    user = db_query("SELECT user_id FROM users WHERE user_id=?", (message.from_user.id,), fetchone=True)
    if not user:
        db_query("INSERT INTO users (user_id, full_name, username, join_date) VALUES (?, ?, ?, ?)",
                 (message.from_user.id, message.from_user.full_name, message.from_user.username, get_time_tashkent()))

    unsubbed = await check_subscription(message.from_user.id)
    if unsubbed:
        btn = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Kanal {i+1} — Obuna bo'lish", url=url)]
            for i, url in enumerate(unsubbed)
        ] + [[InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="check_sub")]])
        await message.answer("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=btn)
        return

    start_text = get_setting('start_msg').replace("{name}", message.from_user.full_name)
    id_text = f"\n\n🆔 Sizning Telegram ID: <code>{message.from_user.id}</code>\n(To'lov sahifasida shu ID ni kiriting)"
    await message.answer(start_text + id_text, reply_markup=get_main_menu(message.from_user.id), parse_mode="HTML")

@router.callback_query(F.data == "check_sub")
async def check_sub_cb(call: CallbackQuery):
    unsubbed = await check_subscription(call.from_user.id)
    if unsubbed:
        await call.answer("Hali hamma kanallarga obuna bo'lmadingiz!", show_alert=True)
    else:
        await call.message.delete()
        start_text = get_setting('start_msg').replace("{name}", call.from_user.full_name)
        await call.message.answer(
            f"Rahmat! Obuna tasdiqlandi.\n\n{start_text}",
            reply_markup=get_main_menu(call.from_user.id)
        )

# ================== MENU HANDLERLAR ==================
@router.message(F.text == "📝 E'lon berish")
async def menu_ad_cb(message: Message, state: FSMContext):
    unsubbed = await check_subscription(message.from_user.id)
    if unsubbed:
        await message.answer("Iltimos, oldin kanallarga obuna bo'ling. /start ni bosing.")
        return

    user = db_query("SELECT posted_ads, paid_slots, pending_approval FROM users WHERE user_id=?", (message.from_user.id,), fetchone=True)
    posted, paid, pending = user[0], user[1], (user[2] if len(user) > 2 else 0)

    if pending:
        await message.answer(
            "⏳ Sizning oldingi e'loningiz admin tomonidan ko'rib chiqilmoqda.\n"
            "Admin tasdiqlaganidan so'ng yangi e'lon berishingiz mumkin."
        )
        return

    if posted >= (1 + paid):
        price = get_setting('price')
        btn = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💳 To'lov qilish", callback_data="pay_ad", style="success")
        ]])
        await message.answer(
            f"Sizning bepul e'lonlar limitingiz tugagan.\n"
            f"1-video bepul, 2-sidan boshlab pullik.\n"
            f"E'lon narxi: {price} so'm.", reply_markup=btn)
        return

    await message.answer("E'loningizni boshlaymiz.\nIltimos, akkaunt obzori videosini yuboring:")
    await state.set_state(AdForm.video)

@router.message(F.text == "🆘 Yordam")
async def menu_help_cb(message: Message, state: FSMContext):
    await message.answer("Adminga xabaringizni yozib qoldiring:")
    await state.set_state(SupportForm.msg)

# ================== 🎮 PUBG MOBILE UC OLISH ==================
@router.message(F.text == "🎮 PUBG MOBILE UC OLISH 💎")
async def uc_menu(message: Message, state: FSMContext):
    await state.clear()
    prices = db_query("SELECT id FROM uc_prices", fetchall=True)
    
    text = (
        "🎮 <b>PUBG MOBILE UC OLISH</b>\n\n"
        "💎 Quyidagi narxlardan birini tanlang va to'lov qiling!\n"
        "⚡️ To'lov tasdiqlangandan so'ng UC tez yuboriladi.\n\n"
        "👇 UC miqdorini tanlang:"
    )
    
    await message.answer(text, reply_markup=get_uc_prices_keyboard(0), parse_mode="HTML")

@router.callback_query(F.data == "uc_no_prices")
async def uc_no_prices(call: CallbackQuery):
    await call.answer("Admin hali UC narxlarini kiritmagan!", show_alert=True)

@router.callback_query(F.data.startswith("uc_page_"))
async def uc_page_cb(call: CallbackQuery):
    page = int(call.data.split("_")[2])
    try:
        await call.message.edit_reply_markup(reply_markup=get_uc_prices_keyboard(page))
    except:
        pass
    await call.answer()

@router.callback_query(F.data == "uc_back")
async def uc_back_cb(call: CallbackQuery):
    await call.message.delete()
    await call.answer()

@router.callback_query(F.data.startswith("buy_uc_"))
async def buy_uc_cb(call: CallbackQuery, state: FSMContext):
    """Foydalanuvchi UC tanladi — PUBG ID rasmini so'raydi"""
    parts = call.data.split("_")
    # buy_uc_{pid}_{uc_amount}_{price}
    uc_amount = int(parts[3])
    price = int(parts[4])
    
    card = get_setting('uc_card')
    
    await state.update_data(uc_amount=uc_amount, uc_price=price)
    
    text = (
        f"💎 <b>{uc_amount} UC — {price:,} so'm</b>\n\n".replace(",", " ") +
        f"💳 <b>To'lov uchun karta:</b>\n<code>{card}</code>\n\n"
        f"📋 <b>Buyurtma berish bosqichlari:</b>\n"
        f"1️⃣ Yuqoridagi kartaga <b>{price:,} so'm</b> o'tkazing\n".replace(",", " ") +
        f"2️⃣ PUBG Mobile ga kiring va <b>profil rasmingizni</b> screenshot oling\n"
        f"   (ID raqami ko'rinib tursin!)\n"
        f"3️⃣ O'sha rasmni shu yerga yuboring\n\n"
        f"📸 <b>Iltimos, PUBG ID ko'ringan profil rasmingizni yuboring:</b>"
    )
    
    await call.message.edit_text(text, parse_mode="HTML")
    await state.set_state(UCOrderForm.pubg_screenshot)

@router.message(UCOrderForm.pubg_screenshot, F.photo)
async def get_pubg_screenshot(message: Message, state: FSMContext):
    """PUBG ID rasmi olindi — to'lov chekini so'raydi"""
    photo_id = message.photo[-1].file_id
    await state.update_data(pubg_screenshot=photo_id)
    
    data = await state.get_data()
    card = get_setting('uc_card')
    uc_amount = data['uc_amount']
    price = data['uc_price']
    
    text = (
        f"✅ <b>PUBG ID rasmi qabul qilindi!</b>\n\n"
        f"💳 Endi to'lovni amalga oshiring:\n\n"
        f"<b>Karta raqami:</b>\n<code>{card}</code>\n\n"
        f"<b>Summa:</b> {price:,} so'm\n\n".replace(",", " ") +
        f"💰 To'lov qilgach, <b>to'lov cheki (skrinshot)</b>ni yuboring:"
    )
    
    await message.answer(text, parse_mode="HTML")
    await state.set_state(UCOrderForm.receipt)

@router.message(UCOrderForm.pubg_screenshot)
async def get_pubg_screenshot_wrong(message: Message):
    await message.answer("❗️ Iltimos, <b>rasm (photo)</b> yuboring!", parse_mode="HTML")

@router.message(UCOrderForm.receipt, F.photo)
async def get_uc_receipt(message: Message, state: FSMContext):
    """To'lov cheki olindi — adminga yuboradi"""
    data = await state.get_data()
    receipt_id = message.photo[-1].file_id
    pubg_screenshot = data.get('pubg_screenshot')
    uc_amount = data['uc_amount']
    price = data['uc_price']
    now = get_time_tashkent()
    
    # DB ga saqlash
    order_id = db_query(
        "INSERT INTO uc_orders (user_id, full_name, username, uc_amount, price, pubg_id, screenshot_id, order_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (message.from_user.id, message.from_user.full_name, message.from_user.username or "—",
         uc_amount, price, "screenshot", receipt_id, now)
    )
    
    # Admin uchun xabar
    admin_text = (
        f"🛒 <b>YANGI UC BUYURTMA!</b>\n\n"
        f"👤 Foydalanuvchi: {message.from_user.full_name}\n"
        f"🔗 Username: @{message.from_user.username or '—'}\n"
        f"🆔 Telegram ID: <code>{message.from_user.id}</code>\n\n"
        f"💎 UC miqdori: <b>{uc_amount} UC</b>\n"
        f"💰 To'lov summasi: <b>{price:,} so'm</b>\n\n".replace(",", " ") +
        f"📅 Xabar yuborilgan vaqt: <b>{now}</b> (Toshkent)\n\n"
        f"📸 PUBG ID rasmi quyida keladi ⬇️"
    )
    
    # Admin paneli tugmalari
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"uc_approve_{message.from_user.id}_{order_id}", style="success"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"uc_reject_{message.from_user.id}_{order_id}", style="danger")
    ]])
    
    # Avval PUBG ID rasmini yuborish
    await bot.send_photo(
        ADMIN_ID,
        photo=pubg_screenshot,
        caption=admin_text,
        parse_mode="HTML"
    )
    
    # Keyin to'lov chekini yuborish
    await bot.send_photo(
        ADMIN_ID,
        photo=receipt_id,
        caption=f"💳 <b>TO'LOV CHEKI</b>\n\n"
                f"Buyurtma #{order_id}\n"
                f"👤 {message.from_user.full_name} (ID: <code>{message.from_user.id}</code>)\n"
                f"💎 {uc_amount} UC — {price:,} so'm\n".replace(",", " ") +
                f"⏰ {now}",
        parse_mode="HTML",
        reply_markup=btn
    )
    
    # Foydalanuvchiga tasdiq
    await message.answer(
        f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"💎 <b>{uc_amount} UC</b> — {price:,} so'm\n\n".replace(",", " ") +
        f"⏳ Admin chekni ko'rib chiqib, UC ni tez orada yuboradi.\n"
        f"📞 Savollar bo'lsa: 🆘 Yordam tugmasini bosing.",
        parse_mode="HTML",
        reply_markup=get_main_menu(message.from_user.id)
    )
    await state.clear()

@router.message(UCOrderForm.receipt)
async def get_uc_receipt_wrong(message: Message):
    await message.answer("❗️ Iltimos, <b>to'lov cheki rasmini</b> yuboring!", parse_mode="HTML")

# ================== ADMIN UC BUYURTMA CALLBACKLAR ==================
@router.callback_query(F.data.startswith("uc_approve_"))
async def uc_approve_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    parts = call.data.split("_")
    user_id = int(parts[2])
    order_id = int(parts[3])
    
    order = db_query("SELECT uc_amount, price FROM uc_orders WHERE id=?", (order_id,), fetchone=True)
    if order:
        uc_amount, price = order
        db_query("UPDATE uc_orders SET status='approved' WHERE id=?", (order_id,))
        await bot.send_message(
            user_id,
            f"🎉 <b>UC YUBORILDI!</b>\n\n"
            f"💎 <b>{uc_amount} UC</b> akkauntingizga yuborildi!\n"
            f"O'yiningizni oching va UC ni tekshiring.\n\n"
            f"🙏 Xarid uchun rahmat!",
            parse_mode="HTML",
            reply_markup=get_main_menu(user_id)
        )
    
    caption = call.message.caption or ""
    try:
        await call.message.edit_caption(
            caption=caption + "\n\n✅ TASDIQLANDI — UC YUBORILDI",
            reply_markup=None
        )
    except:
        pass
    await call.answer("✅ Buyurtma tasdiqlandi!", show_alert=True)

@router.callback_query(F.data.startswith("uc_reject_"))
async def uc_reject_cb(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    parts = call.data.split("_")
    user_id = int(parts[2])
    order_id = int(parts[3])
    
    db_query("UPDATE uc_orders SET status='rejected' WHERE id=?", (order_id,))
    await bot.send_message(
        user_id,
        "❌ <b>Buyurtmangiz bekor qilindi.</b>\n\n"
        "To'lov cheki tasdiqlanmadi. Iltimos, qayta urinib ko'ring yoki "
        "🆘 Yordam orqali admin bilan bog'laning.",
        parse_mode="HTML",
        reply_markup=get_main_menu(user_id)
    )
    
    caption = call.message.caption or ""
    try:
        await call.message.edit_caption(
            caption=caption + "\n\n❌ BEKOR QILINDI",
            reply_markup=None
        )
    except:
        pass
    await call.answer("❌ Buyurtma bekor qilindi.", show_alert=True)

# ================== TO'LOV ==================
@router.callback_query(F.data == "pay_ad")
async def pay_ad_cb(call: CallbackQuery, state: FSMContext):
    card = get_setting('card')
    price = get_setting('price')
    await call.message.edit_text(
        f"💳 To'lov uchun karta raqam:\n\n`{card}`\nSumma: {price} so'm\n\n"
        f"To'lov qilgach, chekni rasm (skrinshot) qilib yuboring.",
        parse_mode="Markdown")
    await state.set_state(PaymentForm.receipt)

@router.message(PaymentForm.receipt, F.photo)
async def get_receipt(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_pay_{message.from_user.id}", style="success"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"rej_pay_{message.from_user.id}", style="danger")
    ]])
    await bot.send_photo(ADMIN_ID, photo_id,
        caption=f"💰 Yangi to'lov cheki.\n"
                f"Foydalanuvchi: {message.from_user.full_name} (@{message.from_user.username})\n"
                f"ID: {message.from_user.id}",
        reply_markup=btn)
    await message.answer(
        "Chek adminga yuborildi. Tasdiqlanishini kuting.",
        reply_markup=get_main_menu(message.from_user.id)
    )
    await state.clear()

# ================== E'LON BERISH BOSQICHLARI ==================
@router.message(AdForm.video, F.video)
async def get_video(message: Message, state: FSMContext):
    await state.update_data(video=message.video.file_id)
    await message.answer("Akkaunt levelini (darajasini) kiriting:")
    await state.set_state(AdForm.level)

@router.message(AdForm.level)
async def get_level(message: Message, state: FSMContext):
    await state.update_data(level=message.text)
    await message.answer("Nechta qurol (upgradable) bor? Faqat raqamda kiriting:")
    await state.set_state(AdForm.guns)

@router.message(AdForm.guns, F.text.regexp(r'^\d+$'))
async def get_guns(message: Message, state: FSMContext):
    await state.update_data(guns=message.text)
    await message.answer("Nechta X-suit bor? Raqamda kiriting:")
    await state.set_state(AdForm.xsuits)

@router.message(AdForm.xsuits, F.text.regexp(r'^\d+$'))
async def get_xsuits(message: Message, state: FSMContext):
    await state.update_data(xsuits=message.text)
    await message.answer("Nechta RP olingan? Raqamda kiriting:")
    await state.set_state(AdForm.rp)

@router.message(AdForm.rp, F.text.regexp(r'^\d+$'))
async def get_rp(message: Message, state: FSMContext):
    await state.update_data(rp=message.text)
    await message.answer("Nechta mashina (skin) bor? Raqamda kiriting:")
    await state.set_state(AdForm.cars)

@router.message(AdForm.cars, F.text.regexp(r'^\d+$'))
async def get_cars(message: Message, state: FSMContext):
    await state.update_data(cars=message.text)
    await message.answer("Narxini so'mda kiriting (masalan: 150000):")
    await state.set_state(AdForm.price)

@router.message(AdForm.price)
async def get_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Murojaat uchun telefon raqamingizni kiriting:")
    await state.set_state(AdForm.phone)

@router.message(AdForm.phone)
async def get_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    me = await bot.get_me()

    text = (f"🎮 Yangi Akkaunt Sotuvda!\n\n"
            f"📊 Level: {data['level']}\n"
            f"🔫 Qurollar: {data['guns']} ta\n"
            f"🥋 X-Suit: {data['xsuits']} ta\n"
            f"🎟 RP: {data['rp']} ta\n"
            f"🚗 Mashinalar: {data['cars']} ta\n"
            f"💰 Narxi: {data['price']} so'm\n"
            f"📞 Tel: {message.text}\n\n"
            f"➖➖➖➖➖➖➖➖➖➖\n"
            f"👨‍💻 Admin: @SEVARA_20o5\n"
            f"🤖 Botimiz: @{me.username}")

    ad_id = db_query("INSERT INTO ads (user_id, video_id, text) VALUES (?, ?, ?)",
                     (message.from_user.id, data['video'], text))
    db_query("UPDATE users SET pending_approval=1 WHERE user_id=?", (message.from_user.id,))

    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"app_ad_{ad_id}", style="success"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"rej_ad_{ad_id}", style="danger")
    ]])

    await bot.send_video(ADMIN_ID, video=data['video'],
        caption=text + f"\n\n👤 Sotuvchi: {message.from_user.full_name} (ID: {message.from_user.id})",
        reply_markup=btn)
    await message.answer(
        "Ma'lumotlaringiz adminga yuborildi. Tasdiqlanganidan so'ng kanalga joylanadi.",
        reply_markup=get_main_menu(message.from_user.id))
    await state.clear()

# ================== YORDAM (SUPPORT) ==================
@router.message(SupportForm.msg)
async def send_support(message: Message, state: FSMContext):
    btn = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Javob yozish", callback_data=f"reply_{message.from_user.id}", style="primary")
    ]])
    await bot.send_message(ADMIN_ID,
        f"📩 Yangi xabar!\n"
        f"Kimdan: {message.from_user.full_name} (ID: {message.from_user.id})\n\n"
        f"Xabar: {message.text}",
        reply_markup=btn)
    await message.answer(
        "Xabaringiz adminga yetkazildi.",
        reply_markup=get_main_menu(message.from_user.id)
    )
    await state.clear()

# ================== ADMIN TO'LOV CALLBACKLAR ==================
@router.callback_query(F.data.startswith("app_pay_"))
async def approve_pay(call: CallbackQuery):
    user_id = int(call.data.split("_")[2])
    db_query("UPDATE users SET paid_slots = paid_slots + 1 WHERE user_id=?", (user_id,))
    await bot.send_message(
        user_id,
        "✅ To'lovingiz admin tomonidan tasdiqlandi!\n"
        "Endi yana e'lon joylashingiz mumkin.",
        reply_markup=get_main_menu(user_id)
    )
    await call.message.edit_caption(caption=call.message.caption + "\n\n✅ TASDIQLANGAN")

@router.callback_query(F.data.startswith("rej_pay_"))
async def reject_pay(call: CallbackQuery):
    user_id = int(call.data.split("_")[2])
    await bot.send_message(
        user_id,
        "❌ To'lovingiz admin tomonidan bekor qilindi.",
        reply_markup=get_main_menu(user_id)
    )
    await call.message.edit_caption(caption=call.message.caption + "\n\n❌ BEKOR QILINGAN")

# ================== ADMIN E'LON CALLBACKLAR ==================
@router.callback_query(F.data.startswith("app_ad_"))
async def approve_ad(call: CallbackQuery):
    ad_id = int(call.data.split("_")[2])
    ad = db_query("SELECT user_id, video_id, text FROM ads WHERE id=?", (ad_id,), fetchone=True)

    if not ad:
        await call.answer("❌ E'lon topilmadi (allaqachon o'chirilgan?)", show_alert=True)
        return

    user_id, video_id, text = ad
    me = await bot.get_me()

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Sotuvchi bilan aloqa", url=f"tg://user?id={user_id}", style="success")],
        [InlineKeyboardButton(text="📢 Reklama berish", url=f"https://t.me/{me.username}?start=ad", style="primary")]
    ])

    # 1) Kanalga yuborish
    try:
        await bot.send_video(MAIN_CHANNEL_ID, video=video_id, caption=text, reply_markup=btn)
    except Exception as e:
        await call.answer(f"❌ Kanalga yuborishda XATO:\n{e}", show_alert=True)
        return

    # 2) DB yangilash
    db_query("UPDATE users SET posted_ads = posted_ads + 1, pending_approval=0 WHERE user_id=?", (user_id,))
    db_query("UPDATE ads SET status='approved' WHERE id=?", (ad_id,))

    # 3) Sotuvchiga xabar
    try:
        await bot.send_message(
            user_id,
            "✅ E'loningiz kanalga joylandi!",
            reply_markup=get_main_menu(user_id)
        )
    except Exception:
        pass

    # 4) Admin xabarini yangilash
    try:
        old_caption = call.message.caption or ""
        await call.message.edit_caption(
            caption=old_caption + "\n\n✅ KANALGA JOYLANDI",
            reply_markup=None
        )
    except Exception:
        pass

    await call.answer("✅ E'lon kanalga joylandi!", show_alert=True)

@router.callback_query(F.data.startswith("rej_ad_"))
async def reject_ad(call: CallbackQuery):
    ad_id = int(call.data.split("_")[2])
    ad = db_query("SELECT user_id FROM ads WHERE id=?", (ad_id,), fetchone=True)

    if not ad:
        await call.answer("❌ E'lon topilmadi!", show_alert=True)
        return

    db_query("UPDATE ads SET status='rejected' WHERE id=?", (ad_id,))
    db_query("UPDATE users SET pending_approval=0 WHERE user_id=?", (ad[0],))

    try:
        await bot.send_message(
            ad[0],
            "❌ E'loningiz admin tomonidan rad etildi.",
            reply_markup=get_main_menu(ad[0])
        )
    except Exception:
        pass

    try:
        old_caption = call.message.caption or ""
        await call.message.edit_caption(
            caption=old_caption + "\n\n❌ BEKOR QILINGAN",
            reply_markup=None
        )
    except Exception:
        pass

    await call.answer("❌ E'lon bekor qilindi.", show_alert=True)

# ================== SAYTDAN KELGAN E'LON CALLBACKLAR ==================
@router.callback_query(F.data == "webad_ok")
async def approve_web_ad(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return

    me = await bot.get_me()
    msg = call.message

    video_id = None
    if msg.video:
        video_id = msg.video.file_id
    elif msg.document:
        video_id = msg.document.file_id

    caption = msg.caption or msg.text or ""

    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Reklama berish", url=f"https://t.me/{me.username}?start=ad")]
    ])

    try:
        if video_id:
            await bot.send_video(MAIN_CHANNEL_ID, video=video_id, caption=caption, reply_markup=btn)
        else:
            await bot.send_message(MAIN_CHANNEL_ID, text=caption, reply_markup=btn)

        await call.message.edit_caption(caption=caption + "\n\n✅ KANALGA JOYLANDI", reply_markup=None)
        await call.answer("✅ Kanalga joylandi!", show_alert=True)
    except Exception as e:
        await call.answer(f"❌ Xatolik: {e}", show_alert=True)

@router.callback_query(F.data == "webad_no")
async def reject_web_ad(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    caption = call.message.caption or call.message.text or ""
    await call.message.edit_caption(caption=caption + "\n\n❌ BEKOR QILINGAN", reply_markup=None)
    await call.answer("❌ E'lon bekor qilindi.", show_alert=True)

# ================== SAYTDAN KELGAN TO'LOV CALLBACKLAR ==================
@router.callback_query(F.data.startswith("webpay_ok"))
async def approve_web_pay(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return

    caption = call.message.caption or ""
    parts = call.data.split("_")
    tg_id = parts[-1] if len(parts) > 2 and parts[-1].isdigit() else None

    username = None
    for line in caption.split("\n"):
        if "Kimdan:" in line:
            p = line.split("Kimdan:")
            if len(p) > 1:
                username = p[1].strip().replace("@", "")
            break

    import random, time
    code = str(random.randint(100000, 999999))

    db_query("CREATE TABLE IF NOT EXISTS unlock_codes (code TEXT PRIMARY KEY, used INTEGER DEFAULT 0, created INTEGER)")
    db_query("INSERT OR REPLACE INTO unlock_codes (code, used, created) VALUES (?, 0, ?)", (code, int(time.time())))

    site_url = get_setting('site_url') or ""

    sent = False
    send_to = tg_id or (f"@{username}" if username else None)
    if send_to:
        try:
            if site_url:
                unlock_url = f"{site_url}?code={code}"
                markup = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="📝 Saytga kirib e'lon joylash", web_app=WebAppInfo(url=unlock_url))
                ]])
                await bot.send_message(
                    send_to,
                    f"✅ <b>To'lovingiz tasdiqlandi!</b>\n\n"
                    f"Quyidagi tugmani bosing — sayt ochiladi:\n\n"
                    f"🔑 Kod: <code>{code}</code>",
                    parse_mode="HTML",
                    reply_markup=markup
                )
            else:
                await bot.send_message(
                    send_to,
                    f"✅ <b>To'lovingiz tasdiqlandi!</b>\n\n🔑 <code>{code}</code>",
                    parse_mode="HTML"
                )
            sent = True
        except Exception:
            pass

    note = f"\n\n✅ TO'LOV TASDIQLANDI\n🔑 Kod: {code}"
    note += f"\n📨 yuborildi" if sent else f"\n⚠️ Yuborib bo'lmadi — kodni qo'lda yuboring: {code}"

    await call.message.edit_caption(caption=caption + note, reply_markup=None)
    await call.answer(f"✅ Kod: {code}" + (" — yuborildi" if sent else " — qo'lda yuboring!"), show_alert=True)

@router.callback_query(F.data.startswith("webpay_no"))
async def reject_web_pay(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Sizda ruxsat yo'q!", show_alert=True)
        return
    caption = call.message.caption or ""
    await call.message.edit_caption(caption=caption + "\n\n❌ TO'LOV BEKOR QILINDI", reply_markup=None)
    await call.answer("❌ To'lov bekor qilindi.", show_alert=True)

# ================== SAYTDAN KOD TEKSHIRISH ==================
@router.message(F.text.regexp(r'^/check_\d{6}$'))
async def check_site_code(message: Message):
    code = message.text.split("_")[1]
    row = db_query("SELECT used FROM unlock_codes WHERE code=?", (code,), fetchone=True)
    if not row:
        await message.answer("invalid")
    elif row[0] == 1:
        await message.answer("used")
    else:
        db_query("UPDATE unlock_codes SET used=1 WHERE code=?", (code,))
        await message.answer("valid")

# ================== SAYT URL SOZLASH ==================
@router.message(Command("checkbot"), F.from_user.id == ADMIN_ID)
async def check_bot_status(message: Message):
    """Bot kanal admini ekanligini tekshiradi"""
    me = await bot.get_me()
    try:
        member = await bot.get_chat_member(MAIN_CHANNEL_ID, me.id)
        status = member.status
        can_post = getattr(member, 'can_post_messages', False)
        ha = "✅ Ha"
        yoq = "❌ Yo'q"
        ok = "✅ Hammasi yaxshi!"
        xato = "❌ Botni kanalga ADMIN qilib qo'shish kerak!"
        await message.answer(
            f"🤖 Bot: @{me.username}\n"
            f"📢 Kanal: {MAIN_CHANNEL_ID}\n"
            f"👤 Status: {status}\n"
            f"✉️ Post yuborish huquqi: {ha if can_post else yoq}\n\n"
            f"{ok if can_post else xato}"
        )
    except Exception as e:
        await message.answer(
            f"❌ Xatolik: {e}\n\n"
            f"Botni {MAIN_CHANNEL_ID} kanaliga admin sifatida qo'shing!\n"
            f"Kerakli huquq: 'Post yuborish'"
        )


async def set_site_url(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        current = get_setting('site_url') or "Kiritilmagan"
        await message.answer(f"Hozirgi sayt URL: {current}\n\nO'zgartirish:\n/setsite https://sizning-sayt.com")
        return
    url = parts[1].strip().rstrip('/')
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('site_url', ?)", (url,))
    await message.answer(f"✅ Sayt URL saqlandi:\n{url}")

# ================== ADMIN JAVOB CALLBACKLAR ==================
@router.callback_query(F.data.startswith("reply_"))
async def reply_support_cb(call: CallbackQuery, state: FSMContext):
    user_id = int(call.data.split("_")[1])
    await state.update_data(reply_to=user_id)
    await call.message.answer("Foydalanuvchiga javob matnini kiriting:")
    await state.set_state(AdminForm.reply_msg)

@router.message(AdminForm.reply_msg)
async def send_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('reply_to')
    await bot.send_message(user_id, f"👨‍💻 Admin javobi:\n\n{message.text}")
    await message.answer("Javob yuborildi.")
    await state.clear()

# ================== ADMIN PANEL — /admin BUYRUQ ==================
@router.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel_cmd(message: Message):
    await message.answer(
        "⚙️ <b>Admin panelga xush kelibsiz!</b>\n\nQuyidagi tugmalardan birini tanlang:",
        reply_markup=get_admin_menu(),
        parse_mode="HTML"
    )

# ================== 🔧 BOSHQARISH TUGMASI — faqat adminga ko'rinadi ==================
@router.message(F.text == "🔧 Boshqarish", F.from_user.id == ADMIN_ID)
async def admin_panel_btn(message: Message):
    await message.answer(
        "⚙️ <b>Admin panelga xush kelibsiz!</b>\n\nQuyidagi tugmalardan birini tanlang:",
        reply_markup=get_admin_menu(),
        parse_mode="HTML"
    )

# ================== ADMIN MENYU TUGMALARI — TEXT HANDLERLAR ==================

# 🔙 Asosiy menyu
@router.message(F.text == "🔙 Asosiy menyu", F.from_user.id == ADMIN_ID)
async def admin_back_main(message: Message):
    await message.answer(
        "✅ Asosiy menyuga qaytdingiz.",
        reply_markup=get_main_menu(message.from_user.id)
    )

# 📊 Statistika
@router.message(F.text == "📊 Statistika", F.from_user.id == ADMIN_ID)
async def admin_stats_btn(message: Message):
    await message.answer("⏳ Statistika tayyorlanmoqda, kuting...")
    bio = generate_stats_image()
    file = BufferedInputFile(bio.read(), filename="stats.png")
    await bot.send_photo(
        message.from_user.id,
        photo=file,
        caption="📈 Botning to'liq statistikasi (TOP 30 foydalanuvchi)"
    )

# 📦 UC buyurtmalar
@router.message(F.text == "📦 UC buyurtmalar", F.from_user.id == ADMIN_ID)
async def admin_uc_orders_btn(message: Message):
    orders = db_query(
        "SELECT id, full_name, uc_amount, price, status, order_date FROM uc_orders ORDER BY id DESC LIMIT 20",
        fetchall=True
    )
    if not orders:
        await message.answer("📦 Hozircha UC buyurtmalar yo'q.")
        return
    text = "📦 <b>OXIRGI 20 UC BUYURTMA:</b>\n\n"
    for oid, name, uc_amount, price, status, date in orders:
        emoji = "⏳" if status == "pending" else ("✅" if status == "approved" else "❌")
        text += f"{emoji} #{oid} | {name} | {uc_amount} UC | {price:,} so'm | {date}\n".replace(",", " ")
    await message.answer(text, parse_mode="HTML")

# 💰 Narx o'zgartirish
@router.message(F.text == "💰 Narx o'zgartirish", F.from_user.id == ADMIN_ID)
async def admin_price_btn(message: Message, state: FSMContext):
    await message.answer("Yangi narxni kiriting (faqat raqam):")
    await state.set_state(AdminForm.price)

@router.message(AdminForm.price)
async def save_price(message: Message, state: FSMContext):
    db_query("UPDATE settings SET value=? WHERE key='price'", (message.text,))
    await message.answer("✅ Narx yangilandi!", reply_markup=get_admin_menu())
    await state.clear()

# 💳 Karta o'zgartirish
@router.message(F.text == "💳 Karta o'zgartirish", F.from_user.id == ADMIN_ID)
async def admin_card_btn(message: Message, state: FSMContext):
    await message.answer("Yangi karta raqamini kiriting:")
    await state.set_state(AdminForm.card)

@router.message(AdminForm.card)
async def save_card(message: Message, state: FSMContext):
    db_query("UPDATE settings SET value=? WHERE key='card'", (message.text,))
    await message.answer("✅ Karta yangilandi!", reply_markup=get_admin_menu())
    await state.clear()

# 📝 Start xabar
@router.message(F.text == "📝 Start xabar", F.from_user.id == ADMIN_ID)
async def admin_startmsg_btn(message: Message, state: FSMContext):
    await message.answer("Yangi start xabarini kiriting. (Foydalanuvchi ismi uchun {name} ishlating):")
    await state.set_state(AdminForm.start_msg)

@router.message(AdminForm.start_msg)
async def save_start(message: Message, state: FSMContext):
    db_query("UPDATE settings SET value=? WHERE key='start_msg'", (message.text,))
    await message.answer("✅ Start xabar yangilandi!", reply_markup=get_admin_menu())
    await state.clear()

# ➕ Kanal qo'shish
@router.message(F.text == "➕ Kanal qo'shish", F.from_user.id == ADMIN_ID)
async def admin_add_ch_btn(message: Message, state: FSMContext):
    await message.answer("Kanal ID sini kiriting (masalan: @kanal_useri yoki -100123...):")
    await state.set_state(AdminForm.add_channel_id)

@router.message(AdminForm.add_channel_id)
async def add_ch_url(message: Message, state: FSMContext):
    await state.update_data(ch_id=message.text)
    await message.answer("Kanal ssilkasini kiriting (https://t.me/...):")
    await state.set_state(AdminForm.add_channel_url)

@router.message(AdminForm.add_channel_url)
async def save_ch(message: Message, state: FSMContext):
    data = await state.get_data()
    db_query("INSERT INTO channels (channel_id, url) VALUES (?, ?)", (data['ch_id'], message.text))
    await message.answer("✅ Kanal qo'shildi!", reply_markup=get_admin_menu())
    await state.clear()

# ➖ Kanal o'chirish
@router.message(F.text == "➖ Kanal o'chirish", F.from_user.id == ADMIN_ID)
async def admin_del_ch_btn(message: Message):
    channels = db_query("SELECT id, channel_id FROM channels", fetchall=True)
    if not channels:
        await message.answer("Kanallar yo'q.")
        return
    btn = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"O'chirish: {ch[1]}", callback_data=f"delch_{ch[0]}")]
        for ch in channels
    ])
    await message.answer("Qaysi kanalni o'chirasiz?", reply_markup=btn)

@router.callback_query(F.data.startswith("delch_"))
async def del_ch_action(call: CallbackQuery):
    c_id = int(call.data.split("_")[1])
    db_query("DELETE FROM channels WHERE id=?", (c_id,))
    await call.message.edit_text("✅ Kanal o'chirildi.")

# 💎 UC narxi qo'shish
@router.message(F.text == "💎 UC narxi qo'shish", F.from_user.id == ADMIN_ID)
async def admin_add_uc_price_btn(message: Message, state: FSMContext):
    await message.answer(
        "💎 <b>UC miqdorini kiriting</b>\n\nMasalan: <code>60</code> yoki <code>300</code> yoki <code>600</code>",
        parse_mode="HTML"
    )
    await state.set_state(AdminForm.uc_price_amount)

@router.message(AdminForm.uc_price_amount)
async def add_uc_price_step2(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗️ Faqat raqam kiriting!")
        return
    await state.update_data(uc_amount=int(message.text))
    await message.answer(
        f"💰 <b>{message.text} UC narxini kiriting (so'mda)</b>\n\nMasalan: <code>25000</code>",
        parse_mode="HTML"
    )
    await state.set_state(AdminForm.uc_price_value)

@router.message(AdminForm.uc_price_value)
async def add_uc_price_save(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❗️ Faqat raqam kiriting!")
        return
    data = await state.get_data()
    uc_amount = data['uc_amount']
    price = int(message.text)
    existing = db_query("SELECT id FROM uc_prices WHERE uc_amount=?", (uc_amount,), fetchone=True)
    if existing:
        db_query("UPDATE uc_prices SET price=? WHERE uc_amount=?", (price, uc_amount))
        await message.answer(
            f"✅ <b>{uc_amount} UC</b> narxi yangilandi: <b>{price:,} so'm</b>".replace(",", " "),
            parse_mode="HTML",
            reply_markup=get_admin_menu()
        )
    else:
        db_query("INSERT INTO uc_prices (uc_amount, price) VALUES (?, ?)", (uc_amount, price))
        await message.answer(
            f"✅ <b>{uc_amount} UC — {price:,} so'm</b> qo'shildi!".replace(",", " "),
            parse_mode="HTML",
            reply_markup=get_admin_menu()
        )
    await state.clear()

# 📋 UC narxlari
@router.message(F.text == "📋 UC narxlari", F.from_user.id == ADMIN_ID)
async def admin_uc_list_btn(message: Message):
    prices = db_query("SELECT id, uc_amount, price FROM uc_prices ORDER BY uc_amount ASC", fetchall=True)
    if not prices:
        await message.answer("❌ Hozircha UC narxlari kiritilmagan.\n\nQo'shish uchun: 💎 UC narxi qo'shish")
        return
    text = "💎 <b>UC NARXLARI RO'YXATI:</b>\n\n"
    rows = []
    for pid, uc_amount, price in prices:
        text += f"• {uc_amount} UC — {price:,} so'm\n".replace(",", " ")
        rows.append([
            InlineKeyboardButton(
                text=f"🗑 {uc_amount} UC o'chirish",
                callback_data=f"del_uc_price_{pid}"
            )
        ])
    rows.append([InlineKeyboardButton(text="🔙 Admin panel", callback_data="back_to_admin")])
    btn = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(text, reply_markup=btn, parse_mode="HTML")

# 💳 UC karta
@router.message(F.text == "💳 UC karta", F.from_user.id == ADMIN_ID)
async def admin_uc_card_btn(message: Message, state: FSMContext):
    current = get_setting('uc_card')
    await message.answer(
        f"💳 Hozirgi UC karta:\n<code>{current}</code>\n\nYangi karta raqamini kiriting:",
        parse_mode="HTML"
    )
    await state.set_state(AdminForm.uc_card)

@router.message(AdminForm.uc_card)
async def save_uc_card(message: Message, state: FSMContext):
    db_query("INSERT OR REPLACE INTO settings (key, value) VALUES ('uc_card', ?)", (message.text,))
    await message.answer(
        f"✅ UC karta yangilandi!\n<code>{message.text}</code>",
        parse_mode="HTML",
        reply_markup=get_admin_menu()
    )
    await state.clear()

# ================== INLINE CALLBACK — back_to_admin ==================
@router.callback_query(F.data == "back_to_admin")
async def back_to_admin(call: CallbackQuery):
    await call.message.answer(
        "⚙️ <b>Admin panel:</b>",
        reply_markup=get_admin_menu(),
        parse_mode="HTML"
    )
    await call.answer()

@router.callback_query(F.data == "uc_settings_title")
async def uc_settings_title(call: CallbackQuery):
    await call.answer("💎 UC Sozlamalari bo'limi", show_alert=False)

# ================== UC NARX O'CHIRISH CALLBACK ==================
@router.callback_query(F.data.startswith("del_uc_price_"))
async def del_uc_price(call: CallbackQuery):
    pid = int(call.data.split("_")[3])
    price_row = db_query("SELECT uc_amount FROM uc_prices WHERE id=?", (pid,), fetchone=True)
    if price_row:
        db_query("DELETE FROM uc_prices WHERE id=?", (pid,))
        await call.answer(f"✅ {price_row[0]} UC narxi o'chirildi!", show_alert=True)
        try:
            await call.message.delete()
        except:
            pass
    else:
        await call.answer("Topilmadi!", show_alert=True)

# ================== STATISTIKA GENERATSIYA ==================
def generate_stats_image():
    users = db_query("SELECT user_id, full_name, join_date, posted_ads FROM users ORDER BY posted_ads DESC", fetchall=True)
    total_users = len(users)
    uc_orders_count = len(db_query("SELECT id FROM uc_orders", fetchall=True))
    uc_approved = len(db_query("SELECT id FROM uc_orders WHERE status='approved'", fetchall=True))
    show_users = users[:30]
    img_height = 200 + (len(show_users) * 35)

    img = Image.new('RGB', (900, img_height), color=(25, 25, 35))
    d = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arial.ttf", 24)
        font_text = ImageFont.truetype("arial.ttf", 16)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    d.text((30, 20), "📊 BOT STATISTIKASI", fill=(255, 200, 0), font=font_title)
    d.text((30, 60), f"Umumiy a'zolar: {total_users} ta", fill=(255, 255, 255), font=font_text)
    d.text((30, 85), f"UC buyurtmalar: {uc_orders_count} ta (tasdiqlangan: {uc_approved})", fill=(0, 200, 255), font=font_text)
    d.text((30, 110), f"Vaqt: {get_time_tashkent()}", fill=(150, 150, 150), font=font_text)
    d.line([(30, 135), (870, 135)], fill=(100, 100, 100), width=2)

    y = 150
    d.text((30, y), "ID", fill=(200, 200, 200), font=font_text)
    d.text((200, y), "ISMI", fill=(200, 200, 200), font=font_text)
    d.text((550, y), "QO'SHILGAN VAQTI", fill=(200, 200, 200), font=font_text)
    d.text((800, y), "E'LONLAR", fill=(200, 200, 200), font=font_text)

    y += 30
    for u in show_users:
        uid, name, date, ads = u
        name_trunc = name[:30] + "..." if len(name) > 30 else name
        d.text((30, y), str(uid), fill=(255, 255, 255), font=font_text)
        d.text((200, y), str(name_trunc), fill=(255, 255, 255), font=font_text)
        d.text((550, y), str(date), fill=(255, 255, 255), font=font_text)
        d.text((800, y), str(ads), fill=(0, 255, 0), font=font_text)
        y += 35

    bio = BytesIO()
    img.save(bio, 'PNG')
    bio.seek(0)
    return bio

# ================== STATISTIKA CALLBACK (inline orqali ham ishlaydi) ==================
@router.callback_query(F.data == "admin_stats")
async def send_stats_img(call: CallbackQuery):
    await call.message.answer("Statistika tayyorlanmoqda, kuting...")
    bio = generate_stats_image()
    file = BufferedInputFile(bio.read(), filename="stats.png")
    await bot.send_photo(call.from_user.id, photo=file,
        caption="📈 Botning to'liq statistikasi (TOP 30 foydalanuvchi)")
    await call.answer()

# ================== ASOSIY ISHGA TUSHIRISH ==================
async def main():
    db_query("CREATE TABLE IF NOT EXISTS unlock_tokens (token TEXT PRIMARY KEY, used INTEGER DEFAULT 0, created INTEGER)")

    dp.include_router(router)
    print("✅ Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())