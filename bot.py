import asyncio
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import logging
import os
import random
import re
import threading
import urllib.request
from zoneinfo import ZoneInfo

from telegram import (
    BotCommand,
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeAllGroupChats,
    BotCommandScopeDefault,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageEntity,
    Update,
)
from telegram.error import BadRequest
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
    os.getenv("BOT_TOKEN")
    or "8635335052:AAHKw190Qhft0s4eTwmimwVZjgkueiysyeI"
).strip()
PORT = int(os.getenv("PORT", "10000"))

RENDER_EXTERNAL_URL = (os.getenv("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
KEEP_ALIVE_INTERVAL = int(os.getenv("KEEP_ALIVE_INTERVAL", "240"))

TARGET_GROUP_USERNAME = (
    os.getenv("TARGET_GROUP_USERNAME") or "kushal_igcc_chats"
).strip().lstrip("@")
TARGET_GROUP_ID = int(os.getenv("ALLOWED_CHAT_ID", "0"))

STORE_LINK_URL = "https://t.me/KUSHALSTORElINK"
GROUP_LINK_URL = "https://t.me/kushal_igcc_chats"

_extra_admins_raw = (os.getenv("EXTRA_ADMIN_IDS") or "").strip()
EXTRA_ADMIN_IDS: set[int] = {
    int(x.strip()) for x in _extra_admins_raw.split(",") if x.strip().isdigit()
}

AUTO_DROP_SECONDS = max(10, int(os.getenv("AUTO_DROP_SECONDS", "40")))
DELETE_AFTER_SECONDS = int(os.getenv("DELETE_AFTER_SECONDS", "60"))
DELETE_RESTRICTED_USER_POSTS = True

# Apne Telegram Premium custom emoji IDs yahan (emoji_id, fallback_emoji) format mein dalein
FIELD_PREMIUM_EMOJI_IDS: dict[str, tuple[str, str]] = {
    "header": ("", "✦"),
    "card": ("", "💳"),
    "cvp": ("", "🔐"),
    "expiry": ("", "📅"),
    "gateway": ("", "⚡"),
    "info": ("", "ℹ️"),
    "issuer": ("", "🏦"),
    "country_default": ("", "🌍"),
    "timezone": ("", "🕒"),
    "dev": ("", "👑"),
    "admin": ("", "🛡️"),
    "auto": ("", "🔁"),
}

# Country ke hisab se alag Telegram Premium custom emoji IDs: "COUNTRY": ("emoji_id", "fallback_flag")
COUNTRY_PREMIUM_EMOJI_IDS: dict[str, tuple[str, str]] = {
    "INDIA": ("", "🇮🇳"),
    "UNITED STATES": ("", "🇺🇸"),
    "UNITED KINGDOM": ("", "🇬🇧"),
    "CANADA": ("", "🇨🇦"),
    "AUSTRALIA": ("", "🇦🇺"),
    "SINGAPORE": ("", "🇸🇬"),
    "GERMANY": ("", "🇩🇪"),
    "FRANCE": ("", "🇫🇷"),
    "JAPAN": ("", "🇯🇵"),
    "UAE": ("", "🇦🇪"),
    "SAUDI ARABIA": ("", "🇸🇦"),
}

GATEWAYS = [
    "Stripe Auth",
    "Braintree Auth",
    "Shopify + PayPal",
    "Adyen 3DS",
    "Authorize.Net",
    "Square Gateway",
    "Worldpay Live",
    "CyberSource",
]

SAMPLE_BINS = [
    ("453201", "VISA - DEBIT - CLASSIC", "HDFC BANK LTD", "INDIA", "Asia/Kolkata", "IST (UTC+5:30)"),
    ("453202", "VISA - CREDIT - PLATINUM", "ICICI BANK LTD", "INDIA", "Asia/Kolkata", "IST (UTC+5:30)"),
    ("541333", "MASTERCARD - DEBIT - GOLD", "STATE BANK OF INDIA", "INDIA", "Asia/Kolkata", "IST (UTC+5:30)"),
    ("652150", "RUPAY - DEBIT - SELECT", "AXIS BANK LTD", "INDIA", "Asia/Kolkata", "IST (UTC+5:30)"),
    ("424242", "VISA - CREDIT - CLASSIC", "STRIPE ISSUER", "UNITED STATES", "America/New_York", "EST (UTC-5:00)"),
    ("541330", "MASTERCARD - CREDIT - WORLD", "JPMORGAN CHASE BANK", "UNITED STATES", "America/New_York", "EST (UTC-5:00)"),
    ("378282", "AMEX - CREDIT - GOLD", "AMERICAN EXPRESS", "UNITED STATES", "America/Chicago", "CST (UTC-6:00)"),
    ("601111", "DISCOVER - CREDIT - IT", "DISCOVER BANK", "UNITED STATES", "America/Denver", "MST (UTC-7:00)"),
    ("510510", "MASTERCARD - CREDIT - PLATINUM", "CITIBANK N.A.", "UNITED STATES", "America/New_York", "EST (UTC-5:00)"),
    ("491612", "VISA - DEBIT - PREMIER", "BARCLAYS BANK UK PLC", "UNITED KINGDOM", "Europe/London", "GMT (UTC+0:00)"),
    ("543211", "MASTERCARD - CREDIT - ADVANCE", "HSBC UK BANK PLC", "UNITED KINGDOM", "Europe/London", "GMT (UTC+0:00)"),
    ("451416", "VISA - CREDIT - INFINITE", "ROYAL BANK OF CANADA", "CANADA", "America/Toronto", "EST (UTC-5:00)"),
    ("520145", "MASTERCARD - CREDIT - CASHBACK", "TD CANADA TRUST", "CANADA", "America/Vancouver", "PST (UTC-8:00)"),
    ("471611", "VISA - DEBIT - SMART", "COMMONWEALTH BANK", "AUSTRALIA", "Australia/Sydney", "AEST (UTC+10:00)"),
    ("402400", "VISA - CREDIT - LIVE", "DBS BANK LTD", "SINGAPORE", "Asia/Singapore", "SGT (UTC+8:00)"),
    ("492911", "VISA - CREDIT - CLASSIC", "DEUTSCHE BANK AG", "GERMANY", "Europe/Berlin", "CET (UTC+1:00)"),
    ("497010", "VISA - DEBIT - PREMIER", "BNP PARIBAS", "FRANCE", "Europe/Paris", "CET (UTC+1:00)"),
    ("453914", "VISA - CREDIT - GOLD", "MUFG BANK LTD", "JAPAN", "Asia/Tokyo", "JST (UTC+9:00)"),
    ("421301", "VISA - CREDIT - PLATINUM", "EMIRATES NBD", "UAE", "Asia/Dubai", "GST (UTC+4:00)"),
    ("457810", "VISA - DEBIT - MADA", "AL RAJHI BANK", "SAUDI ARABIA", "Asia/Riyadh", "AST (UTC+3:00)"),
]

URL_PATTERN = re.compile(
    r"(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+|telegram\.dog/\S+)",
    re.IGNORECASE,
)
USERNAME_PATTERN = re.compile(r"@[A-Za-z0-9_]{4,}")


def _build_emoji_tag(emoji_id: str, fallback: str) -> str:
    clean_id = emoji_id.strip()
    if clean_id.isdigit():
        return (
            '<tg-emoji emoji-id="'
            + html.escape(clean_id)
            + '">'
            + html.escape(fallback)
            + "</tg-emoji>"
        )
    return html.escape(fallback)


def prem_emoji(field_key: str) -> str:
    emoji_id, fallback = FIELD_PREMIUM_EMOJI_IDS.get(field_key, ("", "✦"))
    return _build_emoji_tag(emoji_id, fallback)


def country_prem_emoji(country_name: str) -> str:
    key = country_name.strip().upper()
    emoji_id, fallback = COUNTRY_PREMIUM_EMOJI_IDS.get(
        key, FIELD_PREMIUM_EMOJI_IDS["country_default"]
    )
    return _build_emoji_tag(emoji_id, fallback)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            body = b'{"status":"ok","bot":"premium-emoji-cc-drop-active"}'
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
    url = f"{base_url}/health"
    while True:
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                logger.debug(f"Keep-alive ping: {resp.status}")
        except Exception as e:
            logger.debug(f"Keep-alive skipped: {e}")
        threading.Event().wait(max(60, interval))


def start_24x7_server(port: int) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info(f"24/7 HTTP server running on port {port}...")
    if RENDER_EXTERNAL_URL:
        threading.Thread(
            target=_self_ping_loop,
            args=(RENDER_EXTERNAL_URL, KEEP_ALIVE_INTERVAL),
            daemon=True,
        ).start()


async def resolve_target_group_id(
    bot, context: ContextTypes.DEFAULT_TYPE | None = None, current_chat_id: int | None = None
) -> int | str:
    if current_chat_id is not None and current_chat_id < 0:
        if context:
            context.bot_data["active_group_id"] = current_chat_id
        return current_chat_id

    if context and isinstance(context.bot_data.get("active_group_id"), int):
        return context.bot_data["active_group_id"]

    if TARGET_GROUP_ID != 0:
        return TARGET_GROUP_ID

    try:
        chat = await bot.get_chat(f"@{TARGET_GROUP_USERNAME}")
        if context:
            context.bot_data["active_group_id"] = chat.id
        return chat.id
    except Exception as e:
        logger.debug(f"Could not resolve @{TARGET_GROUP_USERNAME}: {e}")
        return f"@{TARGET_GROUP_USERNAME}"


async def is_user_admin(
    bot,
    chat_id: int | str | None,
    user_id: int | None,
    context: ContextTypes.DEFAULT_TYPE | None = None,
    sender_chat_id: int | None = None,
) -> bool:
    if sender_chat_id is not None and chat_id is not None and sender_chat_id == chat_id:
        return True

    if user_id is None:
        return False

    if user_id == 1087968824:
        return True

    if user_id in EXTRA_ADMIN_IDS:
        return True

    candidate_chats: list[int | str] = []
    if chat_id is not None and isinstance(chat_id, int) and chat_id < 0:
        candidate_chats.append(chat_id)

    target_grp = await resolve_target_group_id(bot, context=context)
    if target_grp not in candidate_chats:
        candidate_chats.append(target_grp)

    for cid in candidate_chats:
        try:
            member = await bot.get_chat_member(chat_id=cid, user_id=user_id)
            if member.status in ("administrator", "creator"):
                return True
        except Exception as e:
            logger.debug(f"Admin check skipped for user {user_id} in {cid}: {e}")
    return False


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
    bin_prefix, info, issuer, country, tz_name, zone_label = random.choice(SAMPLE_BINS)
    is_amex = "AMEX" in info.upper()
    target_len = 15 if is_amex else 16
    body_len = target_len - len(bin_prefix) - 1
    body = "".join(str(random.randint(0, 9)) for _ in range(max(0, body_len)))
    partial = bin_prefix + body
    card_number = partial + _luhn_check_digit(partial)

    month = f"{random.randint(1, 12):02d}"
    year = f"{random.randint(27, 32):02d}"
    cvv_len = 4 if is_amex else 3
    cvv = "".join(str(random.randint(0, 9)) for _ in range(cvv_len))

    try:
        now_local = datetime.now(ZoneInfo(tz_name))
        local_time_str = now_local.strftime("%I:%M:%S %p")
    except Exception:
        local_time_str = datetime.now().strftime("%I:%M:%S %p")

    return {
        "number": card_number,
        "cvv": cvv,
        "expiry": f"{month}/{year}",
        "gateway": random.choice(GATEWAYS),
        "info": info,
        "issuer": issuer,
        "country": country,
        "timezone": f"{zone_label} • {local_time_str}",
    }


def make_blue_button(
    text: str, callback_data: str | None = None, url: str | None = None
) -> InlineKeyboardButton:
    if url:
        return InlineKeyboardButton(
            text=text,
            url=url,
            api_kwargs={"style": "primary"},
        )
    return InlineKeyboardButton(
        text=text,
        callback_data=callback_data or "trigger_cc_drop",
        api_kwargs={"style": "primary"},
    )


# 1st button upar, 2nd button uske niche (upar-niche stacked layout)
def build_blue_action_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [make_blue_button("Channel Join", url=STORE_LINK_URL)],
            [make_blue_button("CC Drop", url=GROUP_LINK_URL)],
        ]
    )


def format_cc_drop_text(card: dict[str, str]) -> str:
    hdr_e = prem_emoji("header")
    card_e = prem_emoji("card")
    cvp_e = prem_emoji("cvp")
    exp_e = prem_emoji("expiry")
    gw_e = prem_emoji("gateway")
    info_e = prem_emoji("info")
    iss_e = prem_emoji("issuer")
    cnt_e = country_prem_emoji(card["country"])
    tz_e = prem_emoji("timezone")
    dev_e = prem_emoji("dev")

    return (
        f"{hdr_e} <b>PREMIUM CC DROP</b> {hdr_e}\n"
        f"────────────────────────\n\n"
        f"{card_e} <b>𝗖𝗮𝗿𝗱:</b> <code>{html.escape(card['number'])}</code>\n\n"
        f"{cvp_e} <b>CVP:</b> <code>{html.escape(card['cvv'])}</code>\n\n"
        f"{exp_e} <b>Expiry date:</b> <code>{html.escape(card['expiry'])}</code>\n\n"
        f"{gw_e} <b>𝐆𝐚𝐭𝐞𝐰𝐚𝐲:</b> <b>{html.escape(card['gateway'])}</b>\n\n"
        f"{info_e} <b>𝐈𝐧𝐟𝐨:</b> <code>{html.escape(card['info'])}</code>\n\n"
        f"{iss_e} <b>𝐈𝐬𝐬𝐮𝐞𝐫:</b> <b>{html.escape(card['issuer'])}</b>\n\n"
        f"{cnt_e} <b>𝐂𝐨𝐮𝐧𝐭𝐫𝐲:</b> <b>{html.escape(card['country'])}</b>\n\n"
        f"{tz_e} <b>Time zone:</b> <code>{html.escape(card['timezone'])}</code>\n\n"
        f"{dev_e} <b>Dev:</b> \n\n"
        f"────────────────────────"
    )


def _strip_premium_emoji_tags(text: str) -> str:
    return re.sub(r"<tg-emoji[^>]*>(.*?)</tg-emoji>", r"\1", text, flags=re.DOTALL)


async def _delete_after_delay(
    bot, chat_id: int | str, message_id: int, delay: int
) -> None:
    if delay <= 0:
        return
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.debug(f"Delete skipped for {message_id}: {e}")


def schedule_delete(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int | str, message_id: int
) -> None:
    if DELETE_AFTER_SECONDS <= 0:
        return
    asyncio.create_task(
        _delete_after_delay(context.bot, chat_id, message_id, DELETE_AFTER_SECONDS)
    )


async def send_text_with_blue_buttons(
    bot,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | str,
    text: str,
    auto_delete: bool = False,
) -> bool:
    markup = build_blue_action_buttons()
    msg = None
    try:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=markup,
            disable_web_page_preview=True,
        )
    except BadRequest as e:
        logger.warning(f"Premium emoji tag fallback in {chat_id}: {e}")
        clean_text = _strip_premium_emoji_tags(text)
        try:
            msg = await bot.send_message(
                chat_id=chat_id,
                text=clean_text,
                parse_mode="HTML",
                reply_markup=markup,
                disable_web_page_preview=True,
            )
        except Exception as e2:
            logger.error(f"Failed fallback message to {chat_id}: {e2}")
            return False
    except Exception as e:
        logger.error(f"Failed to send message to {chat_id}: {e}")
        return False

    if msg and auto_delete:
        schedule_delete(context, chat_id, msg.message_id)
    return True


async def perform_group_cc_drop(
    context: ContextTypes.DEFAULT_TYPE,
    current_chat_id: int | None = None,
) -> tuple[bool, int | str]:
    group_id = await resolve_target_group_id(
        context.bot, context=context, current_chat_id=current_chat_id
    )
    card = generate_random_card()
    text = format_cc_drop_text(card)
    ok = await send_text_with_blue_buttons(
        context.bot,
        context,
        group_id,
        text,
        auto_delete=True,
    )
    return ok, group_id


async def _background_auto_drop_loop(application: Application) -> None:
    await asyncio.sleep(8)
    while True:
        try:
            if application.bot_data.get("group_auto_cc_drop_enabled", True):
                ctx = ContextTypes.DEFAULT_TYPE(application=application)
                await perform_group_cc_drop(ctx)
        except Exception as e:
            logger.warning(f"Background group auto CC drop error: {e}")
        await asyncio.sleep(AUTO_DROP_SECONDS)


def ensure_group_auto_drop_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.bot_data["group_auto_cc_drop_enabled"] = True
    if not context.application.bot_data.get("auto_drop_task_started"):
        context.application.bot_data["auto_drop_task_started"] = True
        asyncio.create_task(_background_auto_drop_loop(context.application))


def is_forwarded_or_restricted_message(msg) -> bool:
    if not msg:
        return False
    if getattr(msg, "forward_origin", None) is not None:
        return True
    if getattr(msg, "forward_date", None) is not None:
        return True

    combined_text = " ".join(
        part
        for part in (getattr(msg, "text", None), getattr(msg, "caption", None))
        if part
    )
    if combined_text:
        if URL_PATTERN.search(combined_text) or USERNAME_PATTERN.search(combined_text):
            return True

    entities = list(getattr(msg, "entities", None) or []) + list(
        getattr(msg, "caption_entities", None) or []
    )
    for ent in entities:
        if ent.type in (
            MessageEntity.URL,
            MessageEntity.TEXT_LINK,
            MessageEntity.MENTION,
            MessageEntity.TEXT_MENTION,
        ):
            return True
        if getattr(ent, "url", None):
            return True

    return False


async def guard_forwarded_posts_and_links(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not DELETE_RESTRICTED_USER_POSTS:
        return
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat or chat.id > 0:
        return

    sender_chat_id = msg.sender_chat.id if msg.sender_chat else None
    sender_is_admin = await is_user_admin(
        context.bot,
        chat.id,
        user.id if user else None,
        context=context,
        sender_chat_id=sender_chat_id,
    )
    if sender_is_admin:
        return

    if is_forwarded_or_restricted_message(msg):
        try:
            await msg.delete()
            logger.info(f"Deleted forwarded/link/username post in chat {chat.id}")
        except Exception as e:
            logger.debug(f"Could not delete restricted message {msg.message_id}: {e}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat:
        return

    sender_chat_id = msg.sender_chat.id if msg.sender_chat else None
    allowed = await is_user_admin(
        context.bot,
        chat.id,
        user.id if user else None,
        context=context,
        sender_chat_id=sender_chat_id,
    )
    if not allowed:
        try:
            await msg.reply_text(
                "Sirf Admin hi /start command aur iske buttons use kar sakte hain."
            )
        except Exception:
            pass
        return

    if chat.id < 0:
        context.bot_data["active_group_id"] = chat.id

    ensure_group_auto_drop_job(context)

    safe_name = html.escape(
        (user.first_name if user else None)
        or (msg.sender_chat.title if msg.sender_chat else None)
        or "Admin"
    )

    hdr_e = prem_emoji("header")
    adm_e = prem_emoji("admin")
    auto_e = prem_emoji("auto")
    dev_e = prem_emoji("dev")

    start_text = (
        f"{hdr_e} <b>ADMIN PANEL • CC DROP ACTIVE</b> {hdr_e}\n"
        f"────────────────────────\n\n"
        f"{adm_e} <b>Admin:</b> {safe_name}\n\n"
        f"{auto_e} <b>Auto Drop:</b> Every <code>{AUTO_DROP_SECONDS}s</code>\n\n"
        f"{dev_e} <b>Dev:</b> @RAHU_LKING89\n\n"
        f"────────────────────────"
    )

    await send_text_with_blue_buttons(
        context.bot,
        context,
        chat.id,
        start_text,
        auto_delete=False,
    )

    await perform_group_cc_drop(
        context,
        current_chat_id=chat.id if chat.id < 0 else None,
    )


async def on_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message or not query.from_user:
        return

    caller = query.from_user
    chat_id = query.message.chat.id if query.message.chat else None
    allowed = await is_user_admin(context.bot, chat_id, caller.id, context=context)
    if not allowed:
        await query.answer(
            "Sirf Admin hi is button ko use kar sakte hain!", show_alert=True
        )
        return

    if chat_id is not None and chat_id < 0:
        context.bot_data["active_group_id"] = chat_id

    ensure_group_auto_drop_job(context)

    if query.data == "trigger_cc_drop":
        ok, target_grp = await perform_group_cc_drop(
            context,
            current_chat_id=chat_id if (chat_id is not None and chat_id < 0) else None,
        )
        if ok:
            await query.answer(f"CC Drop sent to {target_grp}!")
        else:
            await query.answer(
                "Group mein bhejne mein dikkat aayi — bot ko group mein Admin banayein.",
                show_alert=True,
            )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception:", exc_info=context.error)


async def post_init(application: Application) -> None:
    application.bot_data["group_auto_cc_drop_enabled"] = True
    start_cmd = [BotCommand("start", "Admin start CC drop panel")]
    for scope in (
        BotCommandScopeDefault(),
        BotCommandScopeAllGroupChats(),
        BotCommandScopeAllChatAdministrators(),
    ):
        try:
            await application.bot.set_my_commands(start_cmd, scope=scope)
        except Exception as e:
            logger.debug(f"Command scope skipped ({scope}): {e}")

    if not application.bot_data.get("auto_drop_task_started"):
        application.bot_data["auto_drop_task_started"] = True
        asyncio.create_task(_background_auto_drop_loop(application))


def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN missing!")

    start_24x7_server(PORT)

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(on_button_click))
    app.add_handler(
        MessageHandler(
            ~filters.COMMAND,
            guard_forwarded_posts_and_links,
        )
    )
    app.add_error_handler(error_handler)

    logger.info("Premium Emoji CC Drop Bot running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
