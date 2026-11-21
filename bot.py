import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import json
import logging
import os
import threading
from telegram import (
    BotCommand,
    BotCommandScopeChat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = (
    os.getenv("BOT_TOKEN") or "8533526106:AAGQ75XFB9g6DbwER_tiZi8_AmiuX-8w7Uo"
).strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "6632236983"))
ADMIN_USERNAME = (os.getenv("ADMIN_USERNAME") or "").strip().lstrip("@RAHU_LKING89")
CHANNEL_URL = (os.getenv("CHANNEL_URL") or "https://t.me/telegram").strip()
PORT = int(os.getenv("PORT", "10000"))

DATA_FILE = "bot_data.json"
RAW_BASE = "https://raw.githubusercontent.com/jajffkaudh-hue/Kushal96/main/Video"


DEFAULT_DATA = {
    "users": [],
    "welcome_template": (
        "✨ <b>Swagat Hai, {mention}!</b> ✨\n\n"
        "Yeh bot aapki <b>Chat ID</b>, <b>User Info</b> aur <b>Packs</b> ke liye hai.\n"
        "Neeche diye gaye buttons se apna option chunein.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👤 <b>User:</b> {mention}\n"
        "🌐 <b>Username:</b> {username}\n"
        "🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    ),
    "theme_banner_photo_id": None,
    "shop_items": [
        {
            "title": "Pack #1",
            "price": 180,
            "desc": "Special theme & pack access.",
            "photo": f"{RAW_BASE}/IMG_20261121_115429_138.jpg",
            "is_file_id": False,
        },
        {
            "title": "Pack #2",
            "price": 150,
            "desc": "Fast delivery pack.",
            "photo": f"{RAW_BASE}/IMG_20261121_115429_223.jpg",
            "is_file_id": False,
        },
        {
            "title": "Pack #3",
            "price": 199,
            "desc": "Premium pack option.",
            "photo": f"{RAW_BASE}/IMG_20261121_115432_537.jpg",
            "is_file_id": False,
        },
        {
            "title": "Pack #4",
            "price": 180,
            "desc": "Exclusive custom pack.",
            "photo": f"{RAW_BASE}/IMG_20261121_115432_851.jpg",
            "is_file_id": False,
        },
    ],
}


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            body = b'{"status":"ok","bot":"24x7-active"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args) -> None:
        return


def start_health_server(port: int) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"24/7 health server running on port {port}...")


def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return json.loads(json.dumps(DEFAULT_DATA))
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            merged = json.loads(json.dumps(DEFAULT_DATA))
            if isinstance(loaded, dict):
                merged.update(loaded)
            return merged
    except Exception as e:
        logger.warning(f"Failed to load bot_data.json: {e}")
        return json.loads(json.dumps(DEFAULT_DATA))


def save_data(data: dict) -> None:
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save bot_data.json: {e}")


def register_user(user_id: int) -> bool:
    """Returns True if user is joining for the first time."""
    data = load_data()
    users = set(int(u) for u in data.get("users", []) if str(u).isdigit())
    is_first_time = user_id not in users
    if is_first_time:
        users.add(user_id)
        data["users"] = sorted(list(users))
        save_data(data)
    return is_first_time


def is_admin(user_id: int) -> bool:
    return ADMIN_ID != 0 and user_id == ADMIN_ID


def get_admin_dm_url() -> str | None:
    if ADMIN_USERNAME:
        return f"https://t.me/{ADMIN_USERNAME}"
    if ADMIN_ID != 0:
        return f"tg://user?id={ADMIN_ID}"
    return None


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(" CHANNEl JOiN", url=CHANNEL_URL, style="primary"),
        ],
        [
            InlineKeyboardButton(" USER INTO", callback_data="user_info", style="danger"),
        ],
        [
            InlineKeyboardButton(" USER CHAT ID", callback_data="user_chat_id", style="success"),
        ],
        [
            InlineKeyboardButton(" BUY PACKS", callback_data="open_buy", style="primary"),
        ],
        [
            InlineKeyboardButton(" CONTACT ADMIN", callback_data="contact_admin", style="danger"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_buy_action_keyboard(item_index: int, price: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton(
                f"🟢 Buy ₹{price}",
                callback_data=f"buy_item:{item_index}",
                style="success",
            )
        ]
    ]
    dm_url = get_admin_dm_url()
    if dm_url:
        rows.append(
            [
                InlineKeyboardButton(
                    f"🔵 DM Admin (@{ADMIN_USERNAME})" if ADMIN_USERNAME else "🔵 DM ADMIN",
                    url=dm_url,
                    style="primary",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "🔴 Contact ADMIN",
                callback_data="contact_admin",
                style="danger",
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


def build_admin_panel_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✏️ Set Welcome Text", callback_data="adm_set_welcome", style="primary"),
            InlineKeyboardButton("🖼️ Set Theme Photo", callback_data="adm_set_theme_photo", style="success"),
        ],
        [
            InlineKeyboardButton("➕ Add Shop Item", callback_data="adm_add_item", style="success"),
            InlineKeyboardButton("🗑️ Reset Shop Items", callback_data="adm_reset_items", style="danger"),
        ],
        [
            InlineKeyboardButton("📊 Bot Stats", callback_data="adm_stats", style="primary"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def get_user_profile_photo_id(
    context: ContextTypes.DEFAULT_TYPE, user_id: int
) -> str | None:
    try:
        photos = await context.bot.get_user_profile_photos(user_id=user_id, limit=1)
        if photos.total_count > 0 and photos.photos[0]:
            return photos.photos[0][-1].file_id
    except Exception as e:
        logger.warning(f"Could not fetch user profile photo for {user_id}: {e}")
    return None


async def clear_previous_buttons(query) -> None:
    """Jis button ko dabaya gaya hai, us message ke buttons turant hata deta hai."""
    if not query:
        return
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass


async def send_welcome_message(
    message, context: ContextTypes.DEFAULT_TYPE, user, chat_id: int
) -> None:
    is_first_time = register_user(user.id)
    data = load_data()

    safe_name = html.escape(user.first_name or "User")
    mention = f'<a href="tg://user?id={user.id}">{safe_name}</a>'
    username = f"@{html.escape(user.username)}" if user.username else "Not set"

    template = data.get("welcome_template") or DEFAULT_DATA["welcome_template"]
    try:
        text = template.format(
            mention=mention,
            username=username,
            chat_id=chat_id,
            name=safe_name,
        )
    except Exception:
        text = (
            f"✨ <b>Swagat Hai, {mention}!</b> ✨\n\n"
            f"🌐 <b>Username:</b> {username}\n"
            f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>"
        )

    if is_first_time:
        text = f"🆕 <b>First Time Welcome!</b>\n\n{text}"

    markup = build_main_menu_keyboard()

    # First-time start par user ki apni profile photo ke saath message
    photo_to_send = None
    if is_first_time:
        photo_to_send = await get_user_profile_photo_id(context, user.id)
    if not photo_to_send:
        photo_to_send = data.get("theme_banner_photo_id")

    if photo_to_send:
        try:
            await message.reply_photo(
                photo=photo_to_send,
                caption=text,
                parse_mode="HTML",
                reply_markup=markup,
            )
            return
        except Exception as e:
            logger.warning(f"Photo send failed, falling back to text menu: {e}")

    await message.reply_text(
        text=text,
        parse_mode="HTML",
        reply_markup=markup,
        disable_web_page_preview=True,
    )


async def send_shop_double_sections(message) -> None:
    data = load_data()
    items = data.get("shop_items") or []
    if not items:
        await message.reply_text("Abhi koi shop item set nahi hai.")
        return

    for i in range(0, len(items), 2):
        pair = items[i : i + 2]
        if len(pair) == 2:
            it1, it2 = pair[0], pair[1]
            p1, p2 = it1.get("price", 180), it2.get("price", 150)
            t1 = html.escape(str(it1.get("title", "Pack")))
            t2 = html.escape(str(it2.get("title", "Pack")))

            caption = (
                f"🛍️ <b>Double Pack Section</b>\n\n"
                f"1️⃣ <b>{t1}</b> — <b>₹{p1}</b>\n"
                f"2️⃣ <b>{t2}</b> — <b>₹{p2}</b>\n\n"
                f"Kisi bhi pack par tap karein ya neeche button use karein."
            )
            media = [
                InputMediaPhoto(media=it1["photo"]),
                InputMediaPhoto(media=it2["photo"], caption=caption, parse_mode="HTML"),
            ]
            try:
                await message.reply_media_group(media=media)
            except Exception as e:
                logger.warning(f"Media group send failed: {e}")

            buttons_row = [
                InlineKeyboardButton(f"🟢 Buy ₹{p1}", callback_data=f"buy_item:{i}", style="success"),
                InlineKeyboardButton(f"🟡 Buy ₹{p2}", callback_data=f"buy_item:{i + 1}", style="primary"),
            ]
            rows = [buttons_row]
            dm_url = get_admin_dm_url()
            if dm_url:
                rows.append(
                    [
                        InlineKeyboardButton(
                            f"🔵 Admin DM (@{ADMIN_USERNAME})" if ADMIN_USERNAME else "🔵 Admin DM",
                            url=dm_url,
                            style="danger",
                        )
                    ]
                )
            await message.reply_text(
                f"💰 <b>{t1} (₹{p1})</b> | <b>{t2} (₹{p2})</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(rows),
            )
        else:
            it1 = pair[0]
            p1 = it1.get("price", 199)
            t1 = html.escape(str(it1.get("title", "Pack")))
            d1 = html.escape(str(it1.get("desc", "")))
            cap1 = f"🛍️ <b>{t1}</b>\n💵 <b>Price:</b> <b>₹{p1}</b>\n{d1}"
            try:
                await message.reply_photo(
                    photo=it1["photo"],
                    caption=cap1,
                    parse_mode="HTML",
                    reply_markup=build_buy_action_keyboard(i, p1),
                )
            except Exception as e:
                logger.warning(f"Single item photo failed: {e}")
                await message.reply_text(
                    text=cap1,
                    parse_mode="HTML",
                    reply_markup=build_buy_action_keyboard(i, p1),
                )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return
    await send_welcome_message(
        update.message, context, update.effective_user, update.effective_chat.id
    )


async def admin_panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Yeh panel sirf Admin ke liye hai.")
        return

    await update.message.reply_text(
        "🛠️ <b>Admin Panel</b>\n\n"
        "Yahan se aap bina storage bhare welcome text, theme photo aur shop items manage kar sakte hain:",
        parse_mode="HTML",
        reply_markup=build_admin_panel_keyboard(),
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return
    register_user(update.effective_user.id)
    await update.message.reply_text(
        f"🆔 <b>Aapki Chat ID:</b> <code>{update.effective_chat.id}</code>",
        parse_mode="HTML",
    )


async def complaint_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    register_user(update.effective_user.id)
    msg_text = " ".join(context.args).strip() if context.args else ""
    if not msg_text:
        context.user_data["awaiting_complaint"] = True
        await update.message.reply_text(
            "📩 <b>Contact Admin / Complaint</b>\n\n"
            "Kripya apni complaint ya message likh kar bhejein. Yeh seedha Admin ko bhej diya jayega.",
            parse_mode="HTML",
        )
        return
    await forward_complaint_to_admin(update, context, msg_text)


async def forward_complaint_to_admin(
    update: Update, context: ContextTypes.DEFAULT_TYPE, complaint_text: str
) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id
    uname = f"@{html.escape(user.username)}" if user.username else "Not set"
    safe_name = html.escape(user.full_name)
    safe_text = html.escape(complaint_text)

    if ADMIN_ID == 0:
        await update.message.reply_text(
            "⚠️ Admin ID abhi environment variable (`ADMIN_ID`) mein set nahi hai."
        )
        return

    admin_msg = (
        f"🚨 <b>New User Complaint</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Name:</b> {safe_name}\n"
        f"🌐 <b>Username:</b> {uname}\n"
        f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 <b>Message:</b>\n{safe_text}"
    )

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "↩️ Reply to User",
                    callback_data=f"admin_reply:{chat_id}",
                    style="success",
                )
            ]
        ]
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_msg,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
        await update.message.reply_text(
            "✅ <b>Aapka message Admin ko bhej diya gaya hai.</b> Jald hi jawab milega.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Failed sending complaint to ADMIN_ID {ADMIN_ID}: {e}")
        await update.message.reply_text(
            "❌ Message Admin tak pahunchane mein dikkat aayi. Kripya thodi der baad try karein."
        )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Yeh command sirf Admin ke liye hai.")
        return

    msg = " ".join(context.args).strip() if context.args else ""
    if not msg:
        await update.message.reply_text(
            "📢 <b>Usage:</b> <code>/broadcast Aapka message</code>",
            parse_mode="HTML",
        )
        return

    data = load_data()
    users = data.get("users") or []
    safe_msg = html.escape(msg)
    sent = 0
    failed = 0

    for uid in users:
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=f"📢 <b>Announcement</b>\n\n{safe_msg}",
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(f"✅ Broadcast done! Sent: {sent}, Failed: {failed}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    user = update.effective_user
    register_user(user.id)

    if not is_admin(user.id):
        return

    admin_mode = context.user_data.get("admin_mode")
    photo = update.message.photo[-1] if update.message.photo else None
    if not photo:
        return

    file_id = photo.file_id
    data = load_data()

    if admin_mode == "set_theme_photo":
        context.user_data["admin_mode"] = None
        data["theme_banner_photo_id"] = file_id
        save_data(data)
        await update.message.reply_text(
            "✅ <b>Theme Banner Photo</b> save ho gayi hai (Telegram `file_id` se—disk storage nahi bharega).",
            parse_mode="HTML",
        )
    elif admin_mode == "awaiting_item_photo":
        pending = context.user_data.get("pending_item") or {}
        context.user_data["admin_mode"] = None
        context.user_data["pending_item"] = None
        items = data.get("shop_items") or []
        items.append(
            {
                "title": pending.get("title", f"Pack #{len(items) + 1}"),
                "price": pending.get("price", 180),
                "desc": pending.get("desc", "Custom admin item"),
                "photo": file_id,
                "is_file_id": True,
            }
        )
        data["shop_items"] = items
        save_data(data)
        await update.message.reply_text(
            "✅ <b>Naya Shop Item</b> photo aur price ke saath add ho gaya hai!",
            parse_mode="HTML",
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    register_user(user.id)
    text = (update.message.text or "").strip()
    if not text:
        return

    if is_admin(user.id) and context.user_data.get("reply_to_chat_id"):
        target_chat_id = context.user_data.pop("reply_to_chat_id")
        try:
            await context.bot.send_message(
                chat_id=target_chat_id,
                text=f"📩 <b>Admin Reply:</b>\n\n{html.escape(text)}",
                parse_mode="HTML",
            )
            await update.message.reply_text(
                f"✅ Reply user <code>{target_chat_id}</code> ko bhej diya gaya.",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Admin reply failed: {e}")
            await update.message.reply_text("❌ User ko reply bhejne mein error aaya.")
        return

    if is_admin(user.id):
        admin_mode = context.user_data.get("admin_mode")
        if admin_mode == "set_welcome":
            context.user_data["admin_mode"] = None
            data = load_data()
            data["welcome_template"] = text
            save_data(data)
            await update.message.reply_text(
                "✅ <b>Welcome Text</b> update ho gaya hai!",
                parse_mode="HTML",
            )
            return

        if admin_mode == "add_item_details":
            parts = [p.strip() for p in text.split("|")]
            title = parts[0] if len(parts) >= 1 and parts[0] else "Custom Pack"
            try:
                price = int(parts[1]) if len(parts) >= 2 else 180
            except ValueError:
                price = 180
            desc = parts[2] if len(parts) >= 3 else "Custom item"

            context.user_data["pending_item"] = {
                "title": title,
                "price": price,
                "desc": desc,
            }
            context.user_data["admin_mode"] = "awaiting_item_photo"
            await update.message.reply_text(
                f"📸 Ab is item (<b>{html.escape(title)} - ₹{price}</b>) ke liye ek <b>photo</b> bhejein:",
                parse_mode="HTML",
            )
            return

    if context.user_data.get("awaiting_complaint"):
        context.user_data["awaiting_complaint"] = False
        await forward_complaint_to_admin(update, context, text)


async def on_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message:
        return

    await query.answer()
    data_str = query.data or ""
    caller = query.from_user

    # Button dabate hi purane message ke buttons automatic hata dena
    await clear_previous_buttons(query)

    if data_str == "contact_admin":
        context.user_data["awaiting_complaint"] = True
        dm_url = get_admin_dm_url()
        rows = []
        if dm_url:
            rows.append(
                [
                    InlineKeyboardButton(
                        f"🔵 Direct DM (@{ADMIN_USERNAME})" if ADMIN_USERNAME else "🔵 Direct DM",
                        url=dm_url,
                        style="primary",
                    )
                ]
            )
        await query.message.reply_text(
            "📩 <b>Contact Admin</b>\n\n"
            "Kripya apna message / complaint yahin type karke bhejein—yeh seedha Admin ke paas pahunch jayega.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows) if rows else None,
        )

    elif data_str == "user_info" and caller:
        uname = f"@{html.escape(caller.username)}" if caller.username else "Not set"
        fname = html.escape(caller.first_name or "N/A")
        lname = html.escape(caller.last_name or "N/A")
        lang = html.escape(caller.language_code or "N/A")
        chat_id = query.message.chat.id

        info_text = (
            f"📋 <b>User Complete Info</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Full Name:</b> {html.escape(caller.full_name)}\n"
            f"🏷️ <b>First Name:</b> {fname}\n"
            f"🏷️ <b>Last Name:</b> {lname}\n"
            f"🌐 <b>Username:</b> {uname}\n"
            f"🆔 <b>User ID:</b> <code>{caller.id}</code>\n"
            f"💬 <b>Chat ID:</b> <code>{chat_id}</code>\n"
            f"🌍 <b>Language:</b> {lang}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        await query.message.reply_text(
            info_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔴 Contact Admin",
                            callback_data="contact_admin",
                            style="danger",
                        )
                    ]
                ]
            ),
        )

    elif data_str == "user_chat_id":
        chat_id = query.message.chat.id
        await query.message.reply_text(
            f"🆔 <b>Aapki Chat ID:</b> <code>{chat_id}</code>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔴 Contact Admin",
                            callback_data="contact_admin",
                            style="danger",
                        )
                    ]
                ]
            ),
        )

    elif data_str == "open_buy":
        await send_shop_double_sections(query.message)

    elif data_str.startswith("buy_item:"):
        idx_str = data_str.split(":", 1)[1]
        db = load_data()
        items = db.get("shop_items") or []
        try:
            idx = int(idx_str)
            item = items[idx]
        except Exception:
            await query.message.reply_text("Item nahi mila.")
            return

        title = html.escape(str(item.get("title", "Pack")))
        price = item.get("price", 180)
        desc = html.escape(str(item.get("desc", "")))
        uid = caller.id if caller else 0

        details_text = (
            f"💳 <b>Buy Details</b>\n\n"
            f"📦 <b>Pack:</b> {title}\n"
            f"💵 <b>Price:</b> <b>₹{price}</b>\n"
            f"📝 <b>Info:</b> {desc}\n"
            f"🆔 <b>Your ID:</b> <code>{uid}</code>\n\n"
            f"Direct baat karne ke liye neeche Admin DM button par click karein:"
        )

        rows: list[list[InlineKeyboardButton]] = []
        dm_url = get_admin_dm_url()
        if dm_url:
            rows.append(
                [
                    InlineKeyboardButton(
                        f"🟢 Message Admin (@{ADMIN_USERNAME})" if ADMIN_USERNAME else "🟢 Message Admin",
                        url=dm_url,
                        style="success",
                    )
                ]
            )
        rows.append(
            [
                InlineKeyboardButton(
                    "🔴 Contact Admin Here",
                    callback_data="contact_admin",
                    style="danger",
                )
            ]
        )

        try:
            await query.message.reply_photo(
                photo=item["photo"],
                caption=details_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(rows),
            )
        except Exception:
            await query.message.reply_text(
                text=details_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(rows),
            )

    elif data_str.startswith("admin_reply:") and caller and is_admin(caller.id):
        target_id = int(data_str.split(":", 1)[1])
        context.user_data["reply_to_chat_id"] = target_id
        await query.message.reply_text(
            f"✍️ Ab apna reply message likh kar bhejein—yeh user <code>{target_id}</code> ko jayega:",
            parse_mode="HTML",
        )

    elif data_str.startswith("adm_") and caller and is_admin(caller.id):
        if data_str == "adm_set_welcome":
            context.user_data["admin_mode"] = "set_welcome"
            await query.message.reply_text(
                "✏️ Naya welcome text bhejein (aap <code>{mention}</code>, <code>{username}</code>, <code>{chat_id}</code> use kar sakte hain):",
                parse_mode="HTML",
            )
        elif data_str == "adm_set_theme_photo":
            context.user_data["admin_mode"] = "set_theme_photo"
            await query.message.reply_text(
                "🖼️ Theme banner ke liye ek photo bhejein:",
                parse_mode="HTML",
            )
        elif data_str == "adm_add_item":
            context.user_data["admin_mode"] = "add_item_details"
            await query.message.reply_text(
                "➕ Item ki details is format mein bhejein:\n"
                "<code>Pack Name | Price | Description</code>\n"
                "Example: <code>VIP Pack | 199 | Full access</code>",
                parse_mode="HTML",
            )
        elif data_str == "adm_reset_items":
            db = load_data()
            db["shop_items"] = json.loads(json.dumps(DEFAULT_DATA["shop_items"]))
            save_data(db)
            await query.message.reply_text("✅ Default shop items reset ho gaye.")
        elif data_str == "adm_stats":
            db = load_data()
            u_count = len(db.get("users") or [])
            i_count = len(db.get("shop_items") or [])
            await query.message.reply_text(
                f"📊 <b>Bot Stats</b>\n\n"
                f"• Total Users: <b>{u_count}</b>\n"
                f"• Shop Items: <b>{i_count}</b>\n"
                f"• Admin ID: <code>{ADMIN_ID}</code>",
                parse_mode="HTML",
            )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)


async def post_init(application: Application) -> None:
    user_commands = [
        BotCommand("start", "Start bot & menu"),
        BotCommand("id", "Get your Chat ID"),
        BotCommand("complaint", "Contact admin / complaint"),
    ]
    await application.bot.set_my_commands(user_commands)

    if ADMIN_ID != 0:
        admin_commands = user_commands + [
            BotCommand("admin", "Open Admin Panel"),
            BotCommand("broadcast", "Broadcast message to users"),
        ]
        try:
            await application.bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=ADMIN_ID),
            )
        except Exception as e:
            logger.warning(f"Could not set admin commands: {e}")


def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN missing hai!")

    start_health_server(PORT)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("complaint", complaint_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(on_button_click))
    app.add_error_handler(error_handler)

    logger.info("Bot is running 24/7...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()