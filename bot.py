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
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", "10000"))

# Apna Telegram Channel link yahan daalein (jaise "https://t.me/YourChannelUsername")
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/telegram").strip()

USERS_FILE = "users.json"

# GitHub repo jajffkaudh-hue/Kushal96 -> Video/ folder ki images + prices[cite: 5, 6]
RAW_BASE = "https://raw.githubusercontent.com/jajffkaudh-hue/Kushal96/main/Video"

SHOP_ITEMS = [
    ("IMG_20261121_115429_138.jpg", "Pack #1", 180),
    ("IMG_20261121_115429_223.jpg", "Pack #2", 150),
    ("IMG_20261121_115432_537.jpg", "Pack #3", 199),
    ("IMG_20261121_115432_851.jpg", "Pack #4", 180),
    ("IMG_20261121_115436_731.jpg", "Pack #5", 150),
    ("IMG_20261121_115436_930.jpg", "Pack #6", 199),
]


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


def load_users() -> set[int]:
    if not os.path.exists(USERS_FILE):
        return set()
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(int(uid) for uid in data if str(uid).isdigit())
    except Exception as e:
        logger.warning(f"Failed to load users: {e}")
        return set()


def save_user(user_id: int) -> None:
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        try:
            with open(USERS_FILE, "w", encoding="utf-8") as f:
                json.dump(sorted(list(users)), f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save user: {e}")


def is_admin(user_id: int) -> bool:
    return ADMIN_ID != 0 and user_id == ADMIN_ID


def build_welcome_text(mention: str, username: str, chat_id: int) -> str:
    return (
        f"✨ <b>Swagat Hai, {mention}!</b> ✨\n\n"
        f"Yeh bot aapki <b>Chat ID</b>, <b>User Info</b> aur <b>Packs</b> ke liye banaya gaya hai.\n"
        f"Neeche diye gaye options se apna kaam karein.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>User:</b> {mention}\n"
        f"🌐 <b>Username:</b> {username}\n"
        f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    # Har button ka color alag-alag set (primary blue, danger red, success green)
    keyboard = [
        [
            InlineKeyboardButton(
                "🔵 Channel Join",
                url=CHANNEL_URL,
                style="primary",
            )
        ],
        [
            InlineKeyboardButton(
                "🔴 User Info",
                callback_data="user_info",
                style="danger",
            )
        ],
        [
            InlineKeyboardButton(
                "🟢 User Chat ID",
                callback_data="user_chat_id",
                style="success",
            )
        ],
        [
            InlineKeyboardButton(
                "🔵 Buy (₹180 / ₹150 / ₹199)",
                callback_data="open_buy",
                style="primary",
            )
        ],
        [
            InlineKeyboardButton(
                "🔴 Contact Admin",
                callback_data="contact_admin",
                style="danger",
            )
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_item_action_keyboard(price: int, title: str) -> InlineKeyboardMarkup:
    # Photo + price text ke neeche Contact Admin + Buy buttons alag colors mein
    keyboard = [
        [
            InlineKeyboardButton(
                f"🟢 Buy ₹{price}",
                callback_data=f"select_price:{price}:{title}",
                style="success",
            ),
            InlineKeyboardButton(
                "🔴 Contact Admin",
                callback_data="contact_admin",
                style="danger",
            ),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def send_double_photos_with_prices(message) -> None:
    # Photos ek section mein double-double (2 ek saath) bhejna
    for i in range(0, len(SHOP_ITEMS), 2):
        pair = SHOP_ITEMS[i : i + 2]
        if len(pair) == 2:
            (f1, t1, p1), (f2, t2, p2) = pair
            url1 = f"{RAW_BASE}/{f1}"
            url2 = f"{RAW_BASE}/{f2}"
            pair_caption = (
                f"🛍️ <b>Double Pack Section</b>\n\n"
                f"1️⃣ <b>{html.escape(t1)}</b> — Price: <b>₹{p1}</b>\n"
                f"2️⃣ <b>{html.escape(t2)}</b> — Price: <b>₹{p2}</b>\n\n"
                f"Kisi bhi pack ke liye neeche button tap karein."
            )
            media_group = [
                InputMediaPhoto(media=url1),
                InputMediaPhoto(media=url2, caption=pair_caption, parse_mode="HTML"),
            ]
            try:
                await message.reply_media_group(media=media_group)
            except Exception as e:
                logger.warning(f"Double media group failed: {e}")

            await message.reply_text(
                f"💳 <b>{html.escape(t1)} (₹{p1})</b> & <b>{html.escape(t2)} (₹{p2})</b>",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                f"🔵 Buy ₹{p1}",
                                callback_data=f"select_price:{p1}:{t1}",
                                style="primary",
                            ),
                            InlineKeyboardButton(
                                f"🟢 Buy ₹{p2}",
                                callback_data=f"select_price:{p2}:{t2}",
                                style="success",
                            ),
                        ],
                        [
                            InlineKeyboardButton(
                                "🔴 Contact Admin",
                                callback_data="contact_admin",
                                style="danger",
                            )
                        ],
                    ]
                ),
            )
        else:
            f1, t1, p1 = pair[0]
            url1 = f"{RAW_BASE}/{f1}"
            caption1 = (
                f"🛍️ <b>{html.escape(t1)}</b>\n"
                f"💰 <b>Price:</b> ₹{p1}\n"
                f"Order ke liye neeche button dabayein."
            )
            try:
                await message.reply_photo(
                    photo=url1,
                    caption=caption1,
                    parse_mode="HTML",
                    reply_markup=build_item_action_keyboard(p1, t1),
                )
            except Exception as e:
                logger.warning(f"Single photo failed: {e}")
                await message.reply_text(
                    text=caption1,
                    parse_mode="HTML",
                    reply_markup=build_item_action_keyboard(p1, t1),
                )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id
    save_user(user.id)

    safe_name = html.escape(user.first_name or "User")
    mention = f'<a href="tg://user?id={user.id}">{safe_name}</a>'
    username = f"@{html.escape(user.username)}" if user.username else "Not set"

    welcome_text = build_welcome_text(
        mention=mention,
        username=username,
        chat_id=chat_id,
    )

    await update.message.reply_text(
        text=welcome_text,
        parse_mode="HTML",
        reply_markup=build_main_menu_keyboard(),
        disable_web_page_preview=True,
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id
    save_user(user.id)

    await update.message.reply_text(
        f"🆔 <b>Aapki Chat ID:</b> <code>{chat_id}</code>",
        parse_mode="HTML",
    )


async def complaint_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    save_user(user.id)

    complaint_text = " ".join(context.args).strip() if context.args else ""
    if not complaint_text:
        context.user_data["awaiting_complaint"] = True
        await update.message.reply_text(
            "📝 <b>Complaint System</b>\n\n"
            "Kripya apni complaint likh kar bhejein. Aapka message seedha Admin ko bhej diya jayega.",
            parse_mode="HTML",
        )
        return

    await submit_complaint(update, context, complaint_text)


async def submit_complaint(
    update: Update, context: ContextTypes.DEFAULT_TYPE, complaint_text: str
) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id
    username_display = f"@{html.escape(user.username)}" if user.username else "N/A"
    safe_full_name = html.escape(user.full_name)
    safe_complaint = html.escape(complaint_text)

    if ADMIN_ID != 0:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"🚨 <b>New Complaint Received</b>\n\n"
                    f"👤 <b>User:</b> {safe_full_name} ({username_display})\n"
                    f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n"
                    f"💬 <b>Message:</b> {safe_complaint}"
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"Failed to forward complaint to admin: {e}")

    await update.message.reply_text(
        "✅ <b>Aapki complaint darj kar li gayi hai.</b> Admin jald hi is par action lenge.",
        parse_mode="HTML",
    )


async def broadcast_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.message or not update.effective_user:
        return

    user = update.effective_user

    if not is_admin(user.id):
        await update.message.reply_text("⛔ Yeh command sirf Admin ke liye hai.")
        return

    broadcast_text = " ".join(context.args).strip() if context.args else ""
    if not broadcast_text:
        await update.message.reply_text(
            "📢 <b>Broadcast Usage:</b>\n<code>/broadcast Aapka message yahan likhein</code>",
            parse_mode="HTML",
        )
        return

    users = load_users()
    if not users:
        await update.message.reply_text("Koi registered user nahi mila.")
        return

    safe_msg = html.escape(broadcast_text)
    sent_count = 0
    failed_count = 0

    for uid in users:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"📢 <b>Announcement</b>\n\n{safe_msg}",
                parse_mode="HTML",
            )
            sent_count += 1
        except Exception:
            failed_count += 1

    await update.message.reply_text(
        f"✅ Broadcast complete!\n• Sent: {sent_count}\n• Failed: {failed_count}"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    save_user(user.id)

    if context.user_data.get("awaiting_complaint"):
        context.user_data["awaiting_complaint"] = False
        text = (update.message.text or "").strip()
        if text:
            await submit_complaint(update, context, text)
        else:
            await update.message.reply_text("Kripya valid complaint text bhejein.")


async def on_button_click(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    if not query or not query.message:
        return

    await query.answer()
    data = query.data or ""
    caller = query.from_user

    if data == "user_info" and caller:
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

    elif data == "user_chat_id" and caller:
        chat_id = query.message.chat.id
        await query.message.reply_text(
            f"🆔 <b>User Chat ID:</b> <code>{chat_id}</code>",
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

    elif data == "open_buy":
        await send_double_photos_with_prices(query.message)

    elif data.startswith("select_price:"):
        parts = data.split(":", 2)
        price_val = parts[1] if len(parts) > 1 else "180"
        pack_name = html.escape(parts[2]) if len(parts) > 2 else "Pack"
        uid = caller.id if caller else 0

        await query.message.reply_text(
            f"💰 <b>Selected Pack & Price</b>\n\n"
            f"📦 <b>Item:</b> {pack_name}\n"
            f"💵 <b>Price:</b> <b>₹{price_val}</b>\n"
            f"🆔 <b>Your ID:</b> <code>{uid}</code>\n\n"
            f"Aage ki process ke liye neeche <b>Contact Admin</b> dabayein.",
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

    elif data == "contact_admin":
        admin_line = (
            f"Admin ID: <code>{ADMIN_ID}</code>"
            if ADMIN_ID != 0
            else "Admin contact available via /complaint."
        )
        await query.message.reply_text(
            f"📩 <b>Contact Admin</b>\n\n"
            f"Apna message bhejne ke liye /complaint likhein ya apni details bhejein.\n"
            f"{admin_line}",
            parse_mode="HTML",
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)


async def post_init(application: Application) -> None:
    user_commands = [
        BotCommand("start", "Start bot & menu"),
        BotCommand("id", "Get your Chat ID"),
        BotCommand("complaint", "Submit a complaint"),
    ]
    await application.bot.set_my_commands(user_commands)

    if ADMIN_ID != 0:
        admin_commands = user_commands + [
            BotCommand("broadcast", "Broadcast message to users (Admin only)")
        ]
        try:
            await application.bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=ADMIN_ID),
            )
        except Exception as e:
            logger.warning(f"Could not set admin menu commands: {e}")


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
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("complaint", complaint_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(on_button_click))
    app.add_error_handler(error_handler)

    logger.info("Bot is running 24/7...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
