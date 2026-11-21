import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import logging
import os
import random
import threading
import time
import urllib.parse
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = (
    os.getenv("BOT_TOKEN")
    or "8952746230:AAG54d6765BiySuKBc11VUbYv2FDq10TJ7E"
).strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", "10000"))

# Optional UPI / QR settings (Render env mein set kar sakte hain)
UPI_ID = (os.getenv("UPI_ID") or "").strip()
UPI_NAME = (os.getenv("UPI_NAME") or "Kushal Store").strip()
QR_CODE_URL = (os.getenv("QR_CODE_URL") or "").strip()

# GitHub repo jajffkaudh-hue/Kushal96 -> Video/ folder ki photos
RAW_BASE = "https://raw.githubusercontent.com/jajffkaudh-hue/Kushal96/main/Video"

PHOTO_FILES = [
    "IMG_20261121_204600_168.jpg",
    "IMG_20261121_204603_721.jpg",
    "IMG_20261121_204849_819.jpg",
    "IMG_20261121_204859_639.jpg",
    "IMG_20261121_204931_068.jpg",
    "IMG_20261121_205105_911.jpg",
    "IMG_20261121_205405_922.jpg",
    "IMG_20261121_205428_884.jpg",
    "IMG_20261121_205434_054.jpg",
    "IMG_20261121_205435_772.jpg",
]

PRICES = [150, 180, 199, 249, 299]

ITEM_TEXTS = [
    "Special random drop ready. Check price & tap Payment to get QR code.",
    "Fresh item selected from Video folder. Instant QR & admin check available.",
    "Limited random selection. Tap Payment below to scan QR & confirm.",
    "Clean item card with price details and fast payment verification.",
]

# 5 buttons with distinct color badges
FIVE_COLOR_BUTTONS = [
    ("⚫ Black Option", "cat_0"),
    ("🔵 Blue Option", "cat_1"),
    ("🟠 Orange Option", "cat_2"),
    ("🟢 Green Option", "cat_3"),
    ("🟡 Yellow / 🟣 Purple", "cat_4"),
]


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            body = b'{"status":"ok","bot":"shop-qr-active"}'
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
    logger.info(f"Health server running on port {port}...")


def build_qr_image_url(amount: int, order_id: str) -> str:
    if QR_CODE_URL:
        return QR_CODE_URL
    if UPI_ID:
        upi_uri = (
            f"upi://pay?pa={urllib.parse.quote(UPI_ID)}"
            f"&pn={urllib.parse.quote(UPI_NAME)}"
            f"&am={amount}&cu=INR&tn={urllib.parse.quote(order_id)}"
        )
        return (
            "https://api.qrserver.com/v1/create-qr-code/?size=400x400&data="
            + urllib.parse.quote(upi_uri)
        )
    qr_payload = f"ORDER:{order_id}|AMOUNT:INR {amount}|PAY TO ADMIN"
    return (
        "https://api.qrserver.com/v1/create-qr-code/?size=400x400&data="
        + urllib.parse.quote(qr_payload)
    )


def build_five_buttons_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=cb_data)]
        for label, cb_data in FIVE_COLOR_BUTTONS
    ]
    return InlineKeyboardMarkup(rows)


def build_item_payment_keyboard(slot_index: int, price: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=f"💳 Payment ₹{price}",
                    callback_data=f"pay_item:{slot_index}",
                )
            ]
        ]
    )


def build_qr_action_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text="🔙 Back", callback_data="go_back"),
                InlineKeyboardButton(
                    text="✅ Check Payment", callback_data=f"check_pay:{order_id}"
                ),
            ]
        ]
    )


async def send_start_screen(
    target_message, user, chat_id: int, context: ContextTypes.DEFAULT_TYPE
) -> None:
    safe_name = html.escape(user.first_name or "User")
    mention = f'<a href="tg://user?id={user.id}">{safe_name}</a>'
    username = f"@{html.escape(user.username)}" if user.username else "Not set"

    banner_file = random.choice(PHOTO_FILES)
    banner_url = f"{RAW_BASE}/{banner_file}"

    caption_text = (
        f"✨ <b>WELCOME, {mention}!</b> ✨\n\n"
        f"👤 <b>User:</b> {mention}\n"
        f"🌐 <b>Username:</b> {username}\n"
        f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n\n"
        f"Neeche diye gaye <b>5 buttons</b> mein se kisi ek par click karein:"
    )

    markup = build_five_buttons_keyboard()
    try:
        await target_message.reply_photo(
            photo=banner_url,
            caption=caption_text,
            parse_mode="HTML",
            reply_markup=markup,
        )
    except Exception as e:
        logger.warning(f"Start photo failed ({banner_url}): {e}")
        await target_message.reply_text(
            text=caption_text,
            parse_mode="HTML",
            reply_markup=markup,
            disable_web_page_preview=True,
        )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return
    await send_start_screen(
        update.message, update.effective_user, update.effective_chat.id, context
    )


async def send_max_three_random_items(
    target_message, context: ContextTypes.DEFAULT_TYPE, category_label: str
) -> None:
    count = min(3, len(PHOTO_FILES))
    chosen_files = random.sample(PHOTO_FILES, k=count)
    dropped_list: list[dict] = []

    for idx, fname in enumerate(chosen_files, start=1):
        price = random.choice(PRICES)
        desc = random.choice(ITEM_TEXTS)
        photo_url = f"{RAW_BASE}/{fname}"
        title = f"{category_label} • Item #{idx}"

        slot_idx = len(dropped_list)
        dropped_list.append(
            {
                "title": title,
                "price": price,
                "desc": desc,
                "photo_url": photo_url,
            }
        )

        caption = (
            f"📦 <b>{html.escape(title)}</b>\n\n"
            f"📝 <b>Text:</b> {html.escape(desc)}\n"
            f"💰 <b>Price:</b> <b>₹{price}</b>"
        )

        markup = build_item_payment_keyboard(slot_idx, price)
        try:
            await target_message.reply_photo(
                photo=photo_url,
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup,
            )
        except Exception as e:
            logger.warning(f"Item photo failed ({photo_url}): {e}")
            await target_message.reply_text(
                text=caption,
                parse_mode="HTML",
                reply_markup=markup,
            )

    context.user_data["last_random_items"] = dropped_list


async def on_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message or not query.from_user:
        return

    await query.answer()
    data = query.data or ""
    caller = query.from_user
    chat_id = query.message.chat.id

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    if data == "go_back":
        await send_start_screen(query.message, caller, chat_id, context)
        return

    if data.startswith("cat_"):
        try:
            cat_idx = int(data.split("_", 1)[1])
        except ValueError:
            cat_idx = 0
        label = (
            FIVE_COLOR_BUTTONS[cat_idx][0]
            if 0 <= cat_idx < len(FIVE_COLOR_BUTTONS)
            else "Random Drop"
        )
        await send_max_three_random_items(query.message, context, label)
        return

    if data.startswith("pay_item:"):
        try:
            slot_idx = int(data.split(":", 1)[1])
        except ValueError:
            slot_idx = 0

        items = context.user_data.get("last_random_items") or []
        if 0 <= slot_idx < len(items):
            item = items[slot_idx]
        else:
            item = {
                "title": "Selected Pack",
                "price": random.choice(PRICES),
                "desc": "Scan QR code below to complete payment.",
                "photo_url": f"{RAW_BASE}/{random.choice(PHOTO_FILES)}",
            }

        price = int(item["price"])
        title = str(item["title"])
        order_id = f"PAY{int(time.time())}{caller.id % 1000}"

        orders_map: dict = context.bot_data.setdefault("orders", {})
        orders_map[order_id] = {
            "order_id": order_id,
            "user_id": caller.id,
            "chat_id": chat_id,
            "full_name": caller.full_name,
            "username": caller.username or "Not set",
            "title": title,
            "price": price,
        }

        qr_url = build_qr_image_url(price, order_id)
        upi_line = (
            f"🏦 <b>UPI ID:</b> <code>{html.escape(UPI_ID)}</code>\n" if UPI_ID else ""
        )

        qr_caption = (
            f"📲 <b>SCAN QR CODE FOR PAYMENT</b>\n\n"
            f"🆔 <b>Order ID:</b> <code>{html.escape(order_id)}</code>\n"
            f"📦 <b>Item:</b> {html.escape(title)}\n"
            f"💰 <b>Amount:</b> <b>₹{price}</b>\n"
            f"{upi_line}"
            f"📝 <b>Text:</b> QR scan karke payment karein, phir neeche <b>Check Payment</b> dabayein ya wapas jaane ke liye <b>Back</b> dabayein."
        )

        qr_markup = build_qr_action_keyboard(order_id)
        try:
            await query.message.reply_photo(
                photo=qr_url,
                caption=qr_caption,
                parse_mode="HTML",
                reply_markup=qr_markup,
            )
        except Exception as e:
            logger.warning(f"QR photo failed ({qr_url}): {e}")
            await query.message.reply_text(
                text=qr_caption,
                parse_mode="HTML",
                reply_markup=qr_markup,
            )
        return

    if data.startswith("check_pay:"):
        order_id = data.split(":", 1)[1].strip()
        orders_map: dict = context.bot_data.get("orders") or {}
        order = orders_map.get(order_id) or {
            "order_id": order_id,
            "user_id": caller.id,
            "chat_id": chat_id,
            "full_name": caller.full_name,
            "username": caller.username or "Not set",
            "title": "Selected Item",
            "price": random.choice(PRICES),
        }

        uname = (
            f"@{html.escape(str(order['username']))}"
            if order.get("username") and order.get("username") != "Not set"
            else "Not set"
        )
        safe_name = html.escape(str(order.get("full_name") or "User"))

        if ADMIN_ID != 0:
            admin_alert = (
                f"🔔 <b>PAYMENT CHECK REQUEST</b>\n\n"
                f"User ne payment kar diya hai / check karne ke liye request bheji hai:\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>User:</b> {safe_name}\n"
                f"🌐 <b>Username:</b> {uname}\n"
                f"🆔 <b>User ID:</b> <code>{order['user_id']}</code>\n"
                f"💬 <b>Chat ID:</b> <code>{order['chat_id']}</code>\n"
                f"🧾 <b>Order ID:</b> <code>{html.escape(order_id)}</code>\n"
                f"📦 <b>Item:</b> {html.escape(str(order['title']))}\n"
                f"💰 <b>Amount:</b> <b>₹{order['price']}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=admin_alert,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Failed sending payment check to ADMIN_ID {ADMIN_ID}: {e}")

        await query.message.reply_text(
            f"✅ <b>Payment Check Request Sent!</b>\n\n"
            f"Order ID: <code>{html.escape(order_id)}</code>\n"
            f"Amount: <b>₹{order['price']}</b>\n\n"
            f"Aapki payment check request <b>Admin</b> ko bhej di gayi hai. Admin jald hi verify karke reply denge.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="🔙 Back",
                            callback_data="go_back",
                        )
                    ]
                ]
            ),
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Start shop menu"),
        ]
    )


def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN missing hai!")

    start_health_server(PORT)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(on_button_click))
    app.add_error_handler(error_handler)

    logger.info("Shop & QR Bot running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
