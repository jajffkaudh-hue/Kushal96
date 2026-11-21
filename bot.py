import asyncio
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import json
import logging
import os
import random
import threading
import urllib.request
from zoneinfo import ZoneInfo
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
    os.getenv("BOT_TOKEN") or "8533526106:AAGQ75XFB9g6DbwER_tiZi8_AmiuX-8w7Uo"
).strip()
PORT = int(os.getenv("PORT", "10000"))

# 24/7 Render self-ping optional URL
RENDER_EXTERNAL_URL = (os.getenv("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
KEEP_ALIVE_INTERVAL = int(os.getenv("KEEP_ALIVE_INTERVAL", "240"))

# Sirf is group mein drop chalega: https://t.me/kushal_igcc_chats
ALLOWED_CHAT_USERNAME = "kushal_igcc_chats"
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID", "0"))

# Exact timing: 50 seconds baad drop, 60 seconds (1 minute) baad delete
DROP_INTERVAL_SECONDS = 50
DELETE_AFTER_SECONDS = 60

# Dummy / test sample data only (for UI & testing purposes)
SAMPLE_BINS = [
    ("453201", "VISA TEST", "India", "Asia/Kolkata", "IN / South Asia"),
    ("541333", "MASTERCARD TEST", "United States", "America/New_York", "US / North America"),
    ("378282", "AMEX TEST", "United Kingdom", "Europe/London", "UK / Europe"),
    ("601111", "DISCOVER TEST", "Canada", "America/Toronto", "CA / North America"),
    ("510510", "MASTERCARD DEMO", "Germany", "Europe/Berlin", "DE / Central Europe"),
    ("411111", "VISA DEMO", "Singapore", "Asia/Singapore", "SG / Southeast Asia"),
]

SAMPLE_TEXTS = [
    "Auto drop active every 50s • Auto delete in 60s.",
    "Random anime girl drop with full separated card & region details.",
    "Tap FIRST for a fresh card or SECOND for text summary.",
    "Clean automated group drop running in kushal_igcc_chats.",
]

ANIME_GIRL_APIS = [
    "https://api.waifu.pics/sfw/waifu",
    "https://api.waifu.pics/sfw/neko",
    "https://api.waifu.pics/sfw/shinobu",
    "https://api.waifu.pics/sfw/megumin",
]

FALLBACK_ANIME_GIRL_PHOTOS = [
    "https://i.waifu.pics/S8D0n7-.png",
    "https://i.waifu.pics/r3jQ2c_.png",
    "https://i.waifu.pics/9X7mK2p.jpg",
]


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            body = b'{"status":"ok","bot":"24x7-50s-drop-active"}'
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


def _self_ping_loop(base_url: str, interval: int) -> None:
    health_url = f"{base_url}/health"
    while True:
        try:
            with urllib.request.urlopen(health_url, timeout=10) as resp:
                logger.debug(f"Keep-alive ping status: {resp.status}")
        except Exception as e:
            logger.debug(f"Keep-alive ping skipped/failed: {e}")
        threading.Event().wait(max(60, interval))


def start_render_24x7_server(port: int) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"24/7 Render HTTP server running on port {port}...")

    if RENDER_EXTERNAL_URL:
        ping_thread = threading.Thread(
            target=_self_ping_loop,
            args=(RENDER_EXTERNAL_URL, KEEP_ALIVE_INTERVAL),
            daemon=True,
        )
        ping_thread.start()
        logger.info(f"24/7 self-ping enabled for {RENDER_EXTERNAL_URL}/health")


def is_allowed_chat(chat_id: int | None, username: str | None) -> bool:
    if ALLOWED_CHAT_ID != 0 and chat_id == ALLOWED_CHAT_ID:
        return True
    if username and username.strip().lstrip("@").lower() == ALLOWED_CHAT_USERNAME:
        return True
    return False


def is_allowed_update(update: Update) -> bool:
    chat = update.effective_chat
    if not chat:
        return False
    return is_allowed_chat(chat.id, chat.username)


def _fetch_anime_girl_url_sync() -> str:
    endpoints = ANIME_GIRL_APIS[:]
    random.shuffle(endpoints)
    for api_url in endpoints:
        try:
            req = urllib.request.Request(
                api_url,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                img_url = str(data.get("url") or "").strip()
                if img_url.startswith("http"):
                    return img_url
        except Exception as e:
            logger.debug(f"Anime girl API failed ({api_url}): {e}")
    return random.choice(FALLBACK_ANIME_GIRL_PHOTOS)


async def get_anime_girl_photo_url() -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _fetch_anime_girl_url_sync)


def _luhn_check_digit(partial_number: str) -> str:
    digits = [int(ch) for ch in partial_number if ch.isdigit()]
    total = 0
    parity = (len(digits) + 1) % 2
    for idx, d in enumerate(digits):
        if idx % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return str((10 - (total % 10)) % 10)


def generate_random_card() -> dict[str, str]:
    prefix, brand, country, tz_name, zone_label = random.choice(SAMPLE_BINS)
    target_len = 15 if brand.startswith("AMEX") else 16
    body_len = target_len - len(prefix) - 1
    body = "".join(str(random.randint(0, 9)) for _ in range(max(0, body_len)))
    partial = prefix + body
    card_number = partial + _luhn_check_digit(partial)

    month = f"{random.randint(1, 12):02d}"
    year = f"{random.randint(27, 31):02d}"
    cvv_len = 4 if brand.startswith("AMEX") else 3
    cvv = "".join(str(random.randint(0, 9)) for _ in range(cvv_len))

    try:
        now_local = datetime.now(ZoneInfo(tz_name))
    except Exception:
        now_local = datetime.now()

    current_time = now_local.strftime("%I:%M:%S %p")
    note = random.choice(SAMPLE_TEXTS)

    return {
        "brand": brand,
        "number": card_number,
        "expiry": f"{month}/{year}",
        "cvv": cvv,
        "time": current_time,
        "country": country,
        "zone": zone_label,
        "note": note,
    }


def build_two_buttons_keyboard() -> InlineKeyboardMarkup:
    # Donon buttons: First = Blue (primary), Second = Orange style/badge
    keyboard = [
        [
            InlineKeyboardButton(
                "🔵 FIRST",
                callback_data="drop_first",
                style="primary",
            ),
            InlineKeyboardButton(
                "🟠 SECOND",
                callback_data="drop_second",
                style="danger",
            ),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def format_card_detail_caption(
    user_mention: str, card: dict[str, str], design_style: int | None = None
) -> str:
    style_idx = design_style if design_style is not None else random.randint(0, 2)
    b_brand = html.escape(card["brand"])
    b_num = html.escape(card["number"])
    b_exp = html.escape(card["expiry"])
    b_cvv = html.escape(card["cvv"])
    b_time = html.escape(card["time"])
    b_country = html.escape(card["country"])
    b_zone = html.escape(card["zone"])
    b_note = html.escape(card["note"])

    if style_idx == 0:
        return (
            f"✨ <b>CARD DETAIL • STYLE #1</b> ✨\n\n"
            f"👤 <b>User:</b> {user_mention} | <b>Brand:</b> {b_brand}\n\n"
            f"💳 <b>[CARD NUMBER]</b>\n"
            f"<code>{b_num}</code>\n\n"
            f"📅 <b>[EXPIRY DATE]</b>\n"
            f"<code>{b_exp}</code>\n\n"
            f"🔐 <b>[CVV]</b>\n"
            f"<code>{b_cvv}</code>\n\n"
            f"🌍 <b>[COUNTRY]</b>\n"
            f"<b>{b_country}</b>\n\n"
            f"🧭 <b>[ZONE]</b>\n"
            f"<b>{b_zone}</b>\n\n"
            f"🕒 <b>[TIME]</b>\n"
            f"<code>{b_time}</code>\n\n"
            f"📝 <b>Text:</b> {b_note}\n"
            f"⏳ <i>Auto-deletes in 60s</i>"
        )
    elif style_idx == 1:
        return (
            f"🔶 <b>CARD DETAIL • STYLE #2</b> 🔶\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>User:</b> {user_mention} ({b_brand})\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔹 <b>Card Number:</b> <code>{b_num}</code>\n"
            f"🔹 <b>Expiry Date:</b> <code>{b_exp}</code>\n"
            f"🔹 <b>CVV:</b> <code>{b_cvv}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏳️ <b>Country:</b> {b_country}\n"
            f"🗺️ <b>Zone:</b> {b_zone}\n"
            f"⏰ <b>Time:</b> <code>{b_time}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💬 <b>Text:</b> {b_note}\n"
            f"⏳ <i>Auto-deletes in 60s</i>"
        )
    else:
        return (
            f"⚡ <b>CARD DETAIL • STYLE #3</b> ⚡\n\n"
            f"• <b>User:</b> {user_mention}\n"
            f"• <b>Card Type:</b> {b_brand}\n\n"
            f"▸ <b>Card:</b> <code>{b_num}</code>\n"
            f"▸ <b>Expiry:</b> <code>{b_exp}</code>\n"
            f"▸ <b>CVV:</b> <code>{b_cvv}</code>\n"
            f"▸ <b>Country:</b> {b_country}\n"
            f"▸ <b>Zone:</b> {b_zone}\n"
            f"▸ <b>Time:</b> <code>{b_time}</code>\n\n"
            f"📌 <b>Text:</b> {b_note}\n"
            f"⏳ <i>Auto-deletes in 60s</i>"
        )


def format_second_detail_caption(user_mention: str, card: dict[str, str]) -> str:
    return (
        f"📄 <b>SECOND VIEW — CARD DETAIL</b>\n\n"
        f"👤 <b>User:</b> {user_mention}\n"
        f"💳 <b>Card Number:</b> <code>{card['number']}</code>\n"
        f"📅 <b>Expiry Date:</b> <code>{card['expiry']}</code>\n"
        f"🔐 <b>CVV:</b> <code>{card['cvv']}</code>\n"
        f"🌍 <b>Country:</b> {html.escape(card['country'])}\n"
        f"🧭 <b>Zone:</b> {html.escape(card['zone'])}\n"
        f"🕒 <b>Time:</b> <code>{card['time']}</code>\n\n"
        f"📝 <b>Text:</b> {html.escape(card['note'])}\n"
        f"⏳ <i>Auto-deletes in 60s</i>"
    )


async def delete_message_after_delay(
    bot, chat_id: int | str, message_id: int, delay: int = DELETE_AFTER_SECONDS
) -> None:
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.debug(f"Auto-delete skipped for message {message_id}: {e}")


def schedule_auto_delete(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int | str, message_id: int
) -> None:
    if context.job_queue:
        context.job_queue.run_once(
            _job_delete_message,
            when=DELETE_AFTER_SECONDS,
            data={"chat_id": chat_id, "message_id": message_id},
            name=f"del_{chat_id}_{message_id}",
        )
    else:
        asyncio.create_task(
            delete_message_after_delay(context.bot, chat_id, message_id, DELETE_AFTER_SECONDS)
        )


async def _job_delete_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    job_data = context.job.data if context.job else None
    if not isinstance(job_data, dict):
        return
    chat_id = job_data.get("chat_id")
    message_id = job_data.get("message_id")
    if chat_id is not None and message_id is not None:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=int(message_id))
        except Exception as e:
            logger.debug(f"Job auto-delete skipped for {message_id}: {e}")


async def send_photo_card_and_buttons(
    bot,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | str,
    caption: str,
) -> None:
    # Order: Photo (image) -> Card detail (caption) -> Donon buttons (reply_markup)
    photo_url = await get_anime_girl_photo_url()
    markup = build_two_buttons_keyboard()

    sent_msg = None
    try:
        sent_msg = await bot.send_photo(
            chat_id=chat_id,
            photo=photo_url,
            caption=caption,
            parse_mode="HTML",
            reply_markup=markup,
        )
    except Exception as e:
        logger.warning(f"Anime girl photo send failed ({photo_url}): {e}")
        sent_msg = await bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode="HTML",
            reply_markup=markup,
            disable_web_page_preview=True,
        )

    if sent_msg:
        schedule_auto_delete(context, chat_id, sent_msg.message_id)


async def resolve_target_group_chat_id(bot) -> int | str | None:
    if ALLOWED_CHAT_ID != 0:
        return ALLOWED_CHAT_ID
    try:
        chat = await bot.get_chat(f"@{ALLOWED_CHAT_USERNAME}")
        return chat.id
    except Exception as e:
        logger.debug(f"Could not resolve @{ALLOWED_CHAT_USERNAME}: {e}")
        return None


async def auto_drop_loop_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    target_chat_id = await resolve_target_group_chat_id(context.bot)
    if target_chat_id is None:
        return

    card = generate_random_card()
    design_idx = random.randint(0, 2)
    auto_mention = f'<a href="https://t.me/{ALLOWED_CHAT_USERNAME}">Auto Drop</a>'
    caption = format_card_detail_caption(auto_mention, card, design_style=design_idx)

    await send_photo_card_and_buttons(context.bot, context, target_chat_id, caption)


def ensure_auto_drop_running(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.job_queue:
        return
    existing = context.job_queue.get_jobs_by_name("kushal_igcc_50s_auto_drop")
    if existing:
        return
    context.job_queue.run_repeating(
        auto_drop_loop_job,
        interval=DROP_INTERVAL_SECONDS,
        first=1,
        name="kushal_igcc_50s_auto_drop",
    )
    logger.info(
        f"Started 50s auto drop & 60s auto delete for @{ALLOWED_CHAT_USERNAME}"
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return

    if not is_allowed_update(update):
        return

    # Start dabane par 50s automatic card drop shuru/ensure karein
    ensure_auto_drop_running(context)

    user = update.effective_user
    safe_name = html.escape(user.first_name or "User")
    mention = f'<a href="tg://user?id={user.id}">{safe_name}</a>'

    card = generate_random_card()
    context.user_data["last_card"] = card
    prev_design = context.user_data.get("last_design", -1)
    next_design = (prev_design + 1) % 3
    context.user_data["last_design"] = next_design

    caption = format_card_detail_caption(mention, card, design_style=next_design)
    await send_photo_card_and_buttons(
        context.bot, context, update.effective_chat.id, caption
    )


async def on_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message or not query.from_user:
        return

    if not is_allowed_update(update):
        await query.answer("Sirf kushal_igcc_chats group mein chalega.", show_alert=True)
        return

    await query.answer()
    caller = query.from_user
    safe_name = html.escape(caller.first_name or "User")
    mention = f'<a href="tg://user?id={caller.id}">{safe_name}</a>'

    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass

    if query.data == "drop_first":
        card = generate_random_card()
        context.user_data["last_card"] = card
        prev_design = context.user_data.get("last_design", -1)
        next_design = (prev_design + 1) % 3
        context.user_data["last_design"] = next_design

        caption = format_card_detail_caption(mention, card, design_style=next_design)
        await send_photo_card_and_buttons(
            context.bot, context, query.message.chat.id, caption
        )

    elif query.data == "drop_second":
        card = context.user_data.get("last_card") or generate_random_card()
        context.user_data["last_card"] = card
        caption = format_second_detail_caption(mention, card)
        await send_photo_card_and_buttons(
            context.bot, context, query.message.chat.id, caption
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Start 50s auto card drop"),
        ]
    )
    if application.job_queue and not application.job_queue.get_jobs_by_name(
        "kushal_igcc_50s_auto_drop"
    ):
        application.job_queue.run_repeating(
            auto_drop_loop_job,
            interval=DROP_INTERVAL_SECONDS,
            first=10,
            name="kushal_igcc_50s_auto_drop",
        )


def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN missing hai!")

    start_render_24x7_server(PORT)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(on_button_click))
    app.add_error_handler(error_handler)

    logger.info("24/7 Anime Card Drop Bot (50s drop / 60s delete) started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
