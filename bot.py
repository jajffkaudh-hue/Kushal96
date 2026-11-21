import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import json
import logging
import os
import random
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

BOT_TOKEN = "8991320152:AAFu1Vc5FDKI_YI983V_uzXFT7VXoqxtU2g"
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", "10000"))

USERS_FILE = "users.json"
THEME_DIR = "theme"

BUTTON_STYLES = ["primary", "danger", "success"]

# theme/ folder ke andar jo photos rahengi unke naam yahan dalenge
FREE_PACK_FILES: list[str] = [
    # "photo1.jpg",
    # "photo2.jpg",
    # "photo3.jpg",
]

RANDOM_PACK_ITEMS: list[tuple[str, str]] = [
    # ("rand1.jpg", "✨ <b>Random Photo #1</b>\nYeh aapka random preview text hai."),
    # ("rand2.jpg", "🔥 <b>Random Photo #2</b>\nNaya random image aur text yahan hai."),
    # ("rand3.jpg", "⚡ <b>Random Photo #3</b>\nHar click par naya random result."),
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


def get_theme_path(filename: str) -> str:
    return os.path.join(THEME_DIR, filename)


def build_welcome_caption(mention: str, username: str, chat_id: int) -> str:
    return (
        f"𝙃𝙚𝙮  {mention} 𝙬𝙚𝙡𝙘𝙤𝙢𝙚 𝙆𝙪𝙨𝙝𝙖𝙡 𝙙𝙖𝙩𝙖\n\n"
        f"𝙗𝙤𝙩 𝙪𝙨𝙚𝙙 𝙛𝙤𝙧 𝙘𝙝𝙖𝙩 𝙄𝘿 𝙖𝙣𝙮 𝙥𝙧𝙤𝙗𝙡𝙚𝙢 𝙘𝙤𝙣𝙩𝙖𝙘𝙩 𝙖𝙙𝙢𝙞𝙣 𝙩𝙝𝙖𝙣𝙠𝙨\n\n"
        f"𝙛𝙤𝙧 𝙨𝙪𝙥𝙥𝙤𝙧𝙩\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 USERNAME: {username}\n"
        f"🆔 CHAT ID: <code>{chat_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )


def build_contact_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "Contact Admin",
                callback_data="contact_admin",
                style="primary",
            )
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_random_colored_keyboard() -> InlineKeyboardMarkup:
    # 6 buttons + 1 Payment button — har button ka color random
    labels = [
        ("Button 1", "rand_1"),
        ("Button 2", "rand_2"),
        ("Button 3", "rand_3"),
        ("Button 4", "rand_4"),
        ("Button 5", "rand_5"),
        ("Button 6", "rand_6"),
    ]
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(labels), 2):
        row: list[InlineKeyboardButton] = []
        for text, cb in labels[i : i + 2]:
            row.append(
                InlineKeyboardButton(
                    text,
                    callback_data=cb,
                    style=random.choice(BUTTON_STYLES),
                )
            )
        rows.append(row)

    rows.append(
        [
            InlineKeyboardButton(
                "Payment",
                callback_data="pay_now",
                style=random.choice(BUTTON_STYLES),
            )
        ]
    )
    return InlineKeyboardMarkup(rows)


async def get_user_photo_id(
    context: ContextTypes.DEFAULT_TYPE, user_id: int
) -> str | None:
    try:
        photos = await context.bot.get_user_profile_photos(user_id=user_id, limit=1)
        if photos.total_count > 0 and photos.photos[0]:
            return photos.photos[0][-1].file_id
    except Exception as e:
        logger.warning(f"Could not fetch profile photo for {user_id}: {e}")
    return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id
    save_user(user.id)

    safe_name = html.escape(user.first_name or "User")
    mention = f'<a href="tg://user?id={user.id}">{safe_name}</a>'
    username = f"@{html.escape(user.username)}" if user.username else "Not set"

    caption = build_welcome_caption(
        mention=mention,
        username=username,
        chat_id=chat_id,
    )
    reply_markup = build_contact_admin_keyboard()
    photo_id = await get_user_photo_id(context, user.id)

    if photo_id:
        await update.message.reply_photo(
            photo=photo_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    else:
        await update.message.reply_text(
            text=caption,
            parse_mode="HTML",
            reply_markup=reply_markup,
            disable_web_page_preview=True,
        )


async def pack_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    save_user(update.effective_user.id)

    # theme/ folder se 3 photos bhejna (agar set hain aur file exist karti hai)
    valid_files = [
        get_theme_path(f)
        for f in FREE_PACK_FILES[:3]
        if os.path.isfile(get_theme_path(f))
    ]

    if valid_files:
        opened_files = [open(path, "rb") for path in valid_files]
        try:
            media_group = [InputMediaPhoto(media=fp) for fp in opened_files]
            await update.message.reply_media_group(media=media_group)
        finally:
            for fp in opened_files:
                fp.close()
    else:
        await update.message.reply_text(
            "📁 <b>theme/</b> folder mein abhi free pack photos set nahi hain. "
            "Photo ke naam batate hi yahan set kar diye jayenge.",
            parse_mode="HTML",
        )

    await update.message.reply_text(
        "👇 Neeche buttons par tap karein:",
        parse_mode="HTML",
        reply_markup=build_random_colored_keyboard(),
    )


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return

    user = update.effective_user
    chat_id = update.effective_chat.id
    save_user(user.id)

    await update.message.reply_text(
        f"🆔 <b>Aapki Player Chat ID (UID):</b> <code>{chat_id}</code>",
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
                    f"🆔 <b>Player Chat ID (UID):</b> <code>{chat_id}</code>\n"
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

    if data == "contact_admin":
        if ADMIN_ID != 0:
            admin_info = f"Admin Chat ID: <code>{ADMIN_ID}</code>"
        else:
            admin_info = "Admin ID abhi set nahi ki gayi hai."

        await query.message.reply_text(
            f"📩 <b>Contact Admin</b>\n\n"
            f"Agar aapko koi madad chahiye, to /complaint command se apna message bhejein.\n"
            f"{admin_info}",
            parse_mode="HTML",
        )

    elif data.startswith("rand_"):
        available_items = [
            (get_theme_path(fname), cap)
            for fname, cap in RANDOM_PACK_ITEMS
            if os.path.isfile(get_theme_path(fname))
        ]
        if available_items:
            photo_path, caption_text = random.choice(available_items)
            with open(photo_path, "rb") as fp:
                await query.message.reply_photo(
                    photo=fp,
                    caption=caption_text,
                    parse_mode="HTML",
                )
        else:
            await query.message.reply_text(
                "🎲 Random photo ke liye <b>theme/</b> folder ki photo names set karein.",
                parse_mode="HTML",
            )

    elif data == "pay_now":
        uid = query.from_user.id if query.from_user else 0
        await query.message.reply_text(
            f"💳 <b>Payment</b>\n\n"
            f"🆔 <b>Aapki ID:</b> <code>{uid}</code>\n"
            f"Payment ke baad details /complaint se Admin ko bhejein.",
            parse_mode="HTML",
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)


async def post_init(application: Application) -> None:
    user_commands = [
        BotCommand("start", "Start bot & welcome"),
        BotCommand("pack", "Get photos & random buttons"),
        BotCommand("id", "Get your Player Chat ID"),
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
    start_health_server(PORT)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pack", pack_command))
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
