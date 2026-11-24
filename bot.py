import asyncio
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import json
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
    or "8956223424:AAHHWlwOx9R1-demq-B7C4cswMuGPaJnxG8"
).strip()
PORT = int(os.getenv("PORT", "10000"))

RENDER_EXTERNAL_URL = (os.getenv("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
KEEP_ALIVE_INTERVAL = int(os.getenv("KEEP_ALIVE_INTERVAL", "240"))

TARGET_GROUP_USERNAME = "kushal_igcc_chats"
TARGET_GROUP_ID = int(os.getenv("ALLOWED_CHAT_ID", "0"))
CHANNEL_JOIN_URL = (
    os.getenv("CHANNEL_JOIN_URL")
    or os.getenv("GROUP_INVITE_URL")
    or f"https://t.me/{TARGET_GROUP_USERNAME}"
).strip()

ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "6632236983"))
_extra_admins_raw = (os.getenv("EXTRA_ADMIN_IDS") or "").strip()
EXTRA_ADMIN_IDS: set[int] = {
    ADMIN_CHAT_ID,
    *{int(x.strip()) for x in _extra_admins_raw.split(",") if x.strip().isdigit()},
}

AUTO_DROP_SECONDS = int(os.getenv("AUTO_DROP_SECONDS", "40"))
DELETE_AFTER_SECONDS = int(os.getenv("DELETE_AFTER_SECONDS", "60"))

DELETE_RESTRICTED_USER_POSTS = True

PREMIUM_EMOJI_IDS: dict[str, tuple[str, str]] = {
    "header": ("5368324170671202286", "✦"),
    "user": ("5373012312141748804", "◈"),
    "ug": ("5350363902611622471", "★"),
    "card": ("5429335758130199375", "❖"),
    "expiry": ("5258093637450866522", "◷"),
    "cvv": ("5370793884794401960", "⚿"),
    "origin": ("5206607081334906820", "⌘"),
    "country": ("5224257773596019498", "◈"),
    "country_detail": ("5368324170671202286", "✦"),
    "zone": ("5373012312141748804", "❖"),
    "datetime": ("5258093637450866522", "◷"),
    "note": ("5206607081334906820", "✦"),
}

AI_GIRL_APIS = [
    "https://api.waifu.pics/sfw/waifu",
    "https://api.waifu.pics/sfw/neko",
    "https://api.waifu.pics/sfw/shinobu",
    "https://api.waifu.pics/sfw/megumin",
]

FALLBACK_AI_GIRL_PHOTOS = [
    "https://i.waifu.pics/S8D0n7-.png",
    "https://i.waifu.pics/r3jQ2c_.png",
    "https://i.waifu.pics/9X7mK2p.jpg",
]

SAMPLE_BINS = [
    ("453201", "VISA", "HDFC Sample Bank", "India", "Republic of India (+91 / INR)", "Asia/Kolkata", "South Asia / IST"),
    ("453202", "VISA", "ICICI Sample Bank", "India", "Republic of India (+91 / INR)", "Asia/Kolkata", "South Asia / IST"),
    ("541333", "MASTERCARD", "SBI Sample Card", "India", "Republic of India (+91 / INR)", "Asia/Kolkata", "South Asia / IST"),
    ("652150", "RUPAY", "Axis Sample Network", "India", "Republic of India (+91 / INR)", "Asia/Kolkata", "South Asia / IST"),
    ("424242", "VISA", "Stripe Sample Issuer", "United States", "United States of America (+1 / USD)", "America/New_York", "North America / EST"),
    ("541330", "MASTERCARD", "Chase Sample Bank", "United States", "United States of America (+1 / USD)", "America/New_York", "North America / EST"),
    ("378282", "AMEX", "Amex US Sample", "United States", "United States of America (+1 / USD)", "America/Chicago", "North America / CST"),
    ("371449", "AMEX", "Amex Corporate Test", "United States", "United States of America (+1 / USD)", "America/Los_Angeles", "North America / PST"),
    ("601111", "DISCOVER", "Discover Sample Network", "United States", "United States of America (+1 / USD)", "America/Denver", "North America / MST"),
    ("510510", "MASTERCARD", "Citi Sample Card", "United States", "United States of America (+1 / USD)", "America/New_York", "North America / EST"),
    ("491612", "VISA", "Barclays UK Sample", "United Kingdom", "United Kingdom (+44 / GBP)", "Europe/London", "Western Europe / GMT"),
    ("543211", "MASTERCARD", "HSBC UK Sample", "United Kingdom", "United Kingdom (+44 / GBP)", "Europe/London", "Western Europe / GMT"),
    ("455611", "VISA", "Lloyds Sample Bank", "United Kingdom", "United Kingdom (+44 / GBP)", "Europe/London", "Western Europe / GMT"),
    ("451416", "VISA", "RBC Sample Bank", "Canada", "Canada (+1 / CAD)", "America/Toronto", "North America / EST"),
    ("520145", "MASTERCARD", "TD Sample Canada", "Canada", "Canada (+1 / CAD)", "America/Vancouver", "North America / PST"),
    ("471611", "VISA", "CBA Sample Bank", "Australia", "Commonwealth of Australia (+61 / AUD)", "Australia/Sydney", "Oceania / AEST"),
    ("531122", "MASTERCARD", "ANZ Sample Bank", "Australia", "Commonwealth of Australia (+61 / AUD)", "Australia/Melbourne", "Oceania / AEST"),
    ("402400", "VISA", "DBS Sample Bank", "Singapore", "Republic of Singapore (+65 / SGD)", "Asia/Singapore", "Southeast Asia / SGT"),
    ("546781", "MASTERCARD", "OCBC Sample Card", "Singapore", "Republic of Singapore (+65 / SGD)", "Asia/Singapore", "Southeast Asia / SGT"),
    ("492911", "VISA", "Deutsche Sample Bank", "Germany", "Federal Republic of Germany (+49 / EUR)", "Europe/Berlin", "Central Europe / CET"),
    ("524123", "MASTERCARD", "Commerz Sample Card", "Germany", "Federal Republic of Germany (+49 / EUR)", "Europe/Berlin", "Central Europe / CET"),
    ("497010", "VISA", "BNP Sample Bank", "France", "French Republic (+33 / EUR)", "Europe/Paris", "Central Europe / CET"),
    ("535120", "MASTERCARD", "Societe Sample Card", "France", "French Republic (+33 / EUR)", "Europe/Paris", "Central Europe / CET"),
    ("454812", "VISA", "Santander Sample", "Spain", "Kingdom of Spain (+34 / EUR)", "Europe/Madrid", "Central Europe / CET"),
    ("540122", "MASTERCARD", "BBVA Sample Card", "Spain", "Kingdom of Spain (+34 / EUR)", "Europe/Madrid", "Central Europe / CET"),
    ("401200", "VISA", "Intesa Sample Bank", "Italy", "Italian Republic (+39 / EUR)", "Europe/Rome", "Central Europe / CET"),
    ("516730", "MASTERCARD", "UniCredit Sample", "Italy", "Italian Republic (+39 / EUR)", "Europe/Rome", "Central Europe / CET"),
    ("453914", "VISA", "MUFG Sample Card", "Japan", "Japan (+81 / JPY)", "Asia/Tokyo", "East Asia / JST"),
    ("352800", "JCB", "JCB Japan Sample", "Japan", "Japan (+81 / JPY)", "Asia/Tokyo", "East Asia / JST"),
    ("356600", "JCB", "JCB Tokyo Sample", "Japan", "Japan (+81 / JPY)", "Asia/Tokyo", "East Asia / JST"),
    ("436312", "VISA", "KB Sample Card", "South Korea", "Republic of Korea (+82 / KRW)", "Asia/Seoul", "East Asia / KST"),
    ("529410", "MASTERCARD", "Shinhan Sample", "South Korea", "Republic of Korea (+82 / KRW)", "Asia/Seoul", "East Asia / KST"),
    ("622126", "UNIONPAY", "China Union Sample", "China", "People's Republic of China (+86 / CNY)", "Asia/Shanghai", "East Asia / CST"),
    ("456331", "VISA", "HSBC HK Sample", "Hong Kong", "Hong Kong SAR (+852 / HKD)", "Asia/Hong_Kong", "East Asia / HKT"),
    ("521044", "MASTERCARD", "Hang Seng Sample", "Hong Kong", "Hong Kong SAR (+852 / HKD)", "Asia/Hong_Kong", "East Asia / HKT"),
    ("421301", "VISA", "Emirates Sample Bank", "UAE", "United Arab Emirates (+971 / AED)", "Asia/Dubai", "Middle East / GST"),
    ("517912", "MASTERCARD", "FAB Sample Card", "UAE", "United Arab Emirates (+971 / AED)", "Asia/Dubai", "Middle East / GST"),
    ("457810", "VISA", "Al Rajhi Sample", "Saudi Arabia", "Kingdom of Saudi Arabia (+966 / SAR)", "Asia/Riyadh", "Middle East / AST"),
    ("530011", "MASTERCARD", "SNB Sample Card", "Saudi Arabia", "Kingdom of Saudi Arabia (+966 / SAR)", "Asia/Riyadh", "Middle East / AST"),
    ("455021", "VISA", "Itau Sample Bank", "Brazil", "Federative Republic of Brazil (+55 / BRL)", "America/Sao_Paulo", "South America / BRT"),
    ("548120", "MASTERCARD", "Bradesco Sample", "Brazil", "Federative Republic of Brazil (+55 / BRL)", "America/Sao_Paulo", "South America / BRT"),
    ("415231", "VISA", "BBVA MX Sample", "Mexico", "United Mexican States (+52 / MXN)", "America/Mexico_City", "North America / CST"),
    ("526130", "MASTERCARD", "Banorte Sample", "Mexico", "United Mexican States (+52 / MXN)", "America/Mexico_City", "North America / CST"),
    ("450799", "VISA", "Galicia Sample", "Argentina", "Argentine Republic (+54 / ARS)", "America/Argentina/Buenos_Aires", "South America / ART"),
    ("512345", "MASTERCARD", "Santander AR Sample", "Argentina", "Argentine Republic (+54 / ARS)", "America/Argentina/Buenos_Aires", "South America / ART"),
    ("422011", "VISA", "Capitec Sample", "South Africa", "Republic of South Africa (+27 / ZAR)", "Africa/Johannesburg", "Southern Africa / SAST"),
    ("532190", "MASTERCARD", "FNB Sample Bank", "South Africa", "Republic of South Africa (+27 / ZAR)", "Africa/Johannesburg", "Southern Africa / SAST"),
    ("419012", "VISA", "GTBank Sample", "Nigeria", "Federal Republic of Nigeria (+234 / NGN)", "Africa/Lagos", "West Africa / WAT"),
    ("539983", "MASTERCARD", "Access Sample NG", "Nigeria", "Federal Republic of Nigeria (+234 / NGN)", "Africa/Lagos", "West Africa / WAT"),
    ("426012", "VISA", "KCB Sample Bank", "Kenya", "Republic of Kenya (+254 / KES)", "Africa/Nairobi", "East Africa / EAT"),
    ("454742", "VISA", "Garanti Sample", "Turkey", "Republic of Turkiye (+90 / TRY)", "Europe/Istanbul", "Eurasia / TRT"),
    ("542110", "MASTERCARD", "Isbank Sample", "Turkey", "Republic of Turkiye (+90 / TRY)", "Europe/Istanbul", "Eurasia / TRT"),
    ("458012", "VISA", "PKO Sample Bank", "Poland", "Republic of Poland (+48 / PLN)", "Europe/Warsaw", "Central Europe / CET"),
    ("533120", "MASTERCARD", "mBank Sample PL", "Poland", "Republic of Poland (+48 / PLN)", "Europe/Warsaw", "Central Europe / CET"),
    ("453712", "VISA", "ING Sample NL", "Netherlands", "Kingdom of the Netherlands (+31 / EUR)", "Europe/Amsterdam", "Central Europe / CET"),
    ("540512", "MASTERCARD", "Rabobank Sample", "Netherlands", "Kingdom of the Netherlands (+31 / EUR)", "Europe/Amsterdam", "Central Europe / CET"),
    ("457101", "VISA", "Nordea Sample SE", "Sweden", "Kingdom of Sweden (+46 / SEK)", "Europe/Stockholm", "Northern Europe / CET"),
    ("522110", "MASTERCARD", "SEB Sample Card", "Sweden", "Kingdom of Sweden (+46 / SEK)", "Europe/Stockholm", "Northern Europe / CET"),
    ("459012", "VISA", "DNB Sample Bank", "Norway", "Kingdom of Norway (+47 / NOK)", "Europe/Oslo", "Northern Europe / CET"),
    ("518910", "MASTERCARD", "Danske Sample DK", "Denmark", "Kingdom of Denmark (+45 / DKK)", "Europe/Copenhagen", "Northern Europe / CET"),
    ("406112", "VISA", "OP Sample Bank", "Finland", "Republic of Finland (+358 / EUR)", "Europe/Helsinki", "Northern Europe / EET"),
    ("451910", "VISA", "UBS Sample Card", "Switzerland", "Swiss Confederation (+41 / CHF)", "Europe/Zurich", "Central Europe / CET"),
    ("543012", "MASTERCARD", "Credit Sample CH", "Switzerland", "Swiss Confederation (+41 / CHF)", "Europe/Zurich", "Central Europe / CET"),
    ("476173", "VISA", "Erste Sample AT", "Austria", "Republic of Austria (+43 / EUR)", "Europe/Vienna", "Central Europe / CET"),
    ("412134", "VISA", "KBC Sample BE", "Belgium", "Kingdom of Belgium (+32 / EUR)", "Europe/Brussels", "Central Europe / CET"),
    ("454312", "VISA", "AIB Sample Bank", "Ireland", "Ireland (+353 / EUR)", "Europe/Dublin", "Western Europe / GMT"),
    ("454611", "VISA", "Millennium Sample", "Portugal", "Portuguese Republic (+351 / EUR)", "Europe/Lisbon", "Western Europe / WET"),
    ("450875", "VISA", "Alpha Sample GR", "Greece", "Hellenic Republic (+30 / EUR)", "Europe/Athens", "Eastern Europe / EET"),
    ("428110", "VISA", "OTP Sample HU", "Hungary", "Hungary (+36 / HUF)", "Europe/Budapest", "Central Europe / CET"),
    ("451014", "VISA", "BCR Sample RO", "Romania", "Romania (+40 / RON)", "Europe/Bucharest", "Eastern Europe / EET"),
    ("471912", "VISA", "CSOB Sample CZ", "Czechia", "Czech Republic (+420 / CZK)", "Europe/Prague", "Central Europe / CET"),
    ("425110", "VISA", "Kasikorn Sample", "Thailand", "Kingdom of Thailand (+66 / THB)", "Asia/Bangkok", "Southeast Asia / ICT"),
    ("544112", "MASTERCARD", "Bangkok Sample", "Thailand", "Kingdom of Thailand (+66 / THB)", "Asia/Bangkok", "Southeast Asia / ICT"),
    ("455110", "VISA", "Maybank Sample", "Malaysia", "Malaysia (+60 / MYR)", "Asia/Kuala_Lumpur", "Southeast Asia / MYT"),
    ("519012", "MASTERCARD", "CIMB Sample MY", "Malaysia", "Malaysia (+60 / MYR)", "Asia/Kuala_Lumpur", "Southeast Asia / MYT"),
    ("451210", "VISA", "BCA Sample Bank", "Indonesia", "Republic of Indonesia (+62 / IDR)", "Asia/Jakarta", "Southeast Asia / WIB"),
    ("531812", "MASTERCARD", "Mandiri Sample", "Indonesia", "Republic of Indonesia (+62 / IDR)", "Asia/Jakarta", "Southeast Asia / WIB"),
    ("471110", "VISA", "BDO Sample Bank", "Philippines", "Republic of the Philippines (+63 / PHP)", "Asia/Manila", "Southeast Asia / PHT"),
    ("549112", "MASTERCARD", "BPI Sample PH", "Philippines", "Republic of the Philippines (+63 / PHP)", "Asia/Manila", "Southeast Asia / PHT"),
    ("423110", "VISA", "Vietcombank Sample", "Vietnam", "Socialist Republic of Vietnam (+84 / VND)", "Asia/Ho_Chi_Minh", "Southeast Asia / ICT"),
    ("451510", "VISA", "HBL Sample Bank", "Pakistan", "Islamic Republic of Pakistan (+92 / PKR)", "Asia/Karachi", "South Asia / PKT"),
    ("541112", "MASTERCARD", "Meezan Sample", "Pakistan", "Islamic Republic of Pakistan (+92 / PKR)", "Asia/Karachi", "South Asia / PKT"),
    ("451710", "VISA", "Dutch-Bangla Test", "Bangladesh", "People's Republic of Bangladesh (+880 / BDT)", "Asia/Dhaka", "South Asia / BST"),
    ("429110", "VISA", "Commercial Sample", "Sri Lanka", "Democratic Socialist Republic of Sri Lanka (+94 / LKR)", "Asia/Colombo", "South Asia / IST"),
    ("410110", "VISA", "QNB Sample Bank", "Qatar", "State of Qatar (+974 / QAR)", "Asia/Qatar", "Middle East / AST"),
    ("521112", "MASTERCARD", "NBK Sample Card", "Kuwait", "State of Kuwait (+965 / KWD)", "Asia/Kuwait", "Middle East / AST"),
    ("457510", "VISA", "Bank Muscat Test", "Oman", "Sultanate of Oman (+968 / OMR)", "Asia/Muscat", "Middle East / GST"),
    ("459112", "VISA", "CIB Sample EG", "Egypt", "Arab Republic of Egypt (+20 / EGP)", "Africa/Cairo", "North Africa / EET"),
    ("532510", "MASTERCARD", "NBE Sample EG", "Egypt", "Arab Republic of Egypt (+20 / EGP)", "Africa/Cairo", "North Africa / EET"),
    ("411111", "VISA", "Demo Global 01", "United States", "United States of America (+1 / USD)", "America/New_York", "North America / EST"),
    ("400001", "VISA", "Demo Global 02", "United Kingdom", "United Kingdom (+44 / GBP)", "Europe/London", "Western Europe / GMT"),
    ("550001", "MASTERCARD", "Demo Global 03", "Germany", "Federal Republic of Germany (+49 / EUR)", "Europe/Berlin", "Central Europe / CET"),
    ("370001", "AMEX", "Demo Global 04", "India", "Republic of India (+91 / INR)", "Asia/Kolkata", "South Asia / IST"),
    ("601100", "DISCOVER", "Demo Global 05", "Canada", "Canada (+1 / CAD)", "America/Toronto", "North America / EST"),
    ("453271", "VISA", "Demo Global 06", "Australia", "Commonwealth of Australia (+61 / AUD)", "Australia/Sydney", "Oceania / AEST"),
    ("453272", "VISA", "Demo Global 07", "Singapore", "Republic of Singapore (+65 / SGD)", "Asia/Singapore", "Southeast Asia / SGT"),
    ("541331", "MASTERCARD", "Demo Global 08", "Japan", "Japan (+81 / JPY)", "Asia/Tokyo", "East Asia / JST"),
    ("541332", "MASTERCARD", "Demo Global 09", "UAE", "United Arab Emirates (+971 / AED)", "Asia/Dubai", "Middle East / GST"),
    ("491601", "VISA", "Demo Global 10", "France", "French Republic (+33 / EUR)", "Europe/Paris", "Central Europe / CET"),
    ("491602", "VISA", "Demo Global 11", "Spain", "Kingdom of Spain (+34 / EUR)", "Europe/Madrid", "Central Europe / CET"),
    ("491603", "VISA", "Demo Global 12", "Italy", "Italian Republic (+39 / EUR)", "Europe/Rome", "Central Europe / CET"),
    ("510511", "MASTERCARD", "Demo Global 13", "Brazil", "Federative Republic of Brazil (+55 / BRL)", "America/Sao_Paulo", "South America / BRT"),
    ("510512", "MASTERCARD", "Demo Global 14", "Mexico", "United Mexican States (+52 / MXN)", "America/Mexico_City", "North America / CST"),
    ("453275", "VISA", "Demo Global 15", "South Africa", "Republic of South Africa (+27 / ZAR)", "Africa/Johannesburg", "Southern Africa / SAST"),
]

SAMPLE_TEXTS = [
    "All Premium UG active • 105+ BIN pool • Auto drop every 40s • Delete in 60s.",
    "AI girl visual + separated card, expiry, CVV, date/time, country & zone sections.",
    "Group CC drop active for kushal_igcc_chats.",
]

URL_PATTERN = re.compile(
    r"(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+|telegram\.dog/\S+)",
    re.IGNORECASE,
)
USERNAME_PATTERN = re.compile(r"@[A-Za-z0-9_]{3,}")


def tg_pe(section_key: str) -> str:
    emoji_id, fallback = PREMIUM_EMOJI_IDS.get(
        section_key, ("5368324170671202286", "✦")
    )
    return (
        '<tg-emoji emoji-id="'
        + html.escape(emoji_id)
        + '">'
        + html.escape(fallback)
        + "</tg-emoji>"
    )


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            body = b'{"status":"ok","bot":"kushal-cc-drop-active"}'
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


async def resolve_target_group_id(bot, active_chat_id: int | str | None = None) -> int | str:
    if TARGET_GROUP_ID != 0:
        return TARGET_GROUP_ID
    try:
        chat = await bot.get_chat(f"@{TARGET_GROUP_USERNAME}")
        return chat.id
    except Exception as e:
        logger.debug(f"Could not resolve @{TARGET_GROUP_USERNAME}: {e}")
        if active_chat_id is not None and str(active_chat_id).startswith("-"):
            return active_chat_id
        return f"@{TARGET_GROUP_USERNAME}"


async def is_user_admin(
    bot, chat_id: int | str | None, user_id: int | None
) -> bool:
    if user_id is None:
        return False
    if user_id == ADMIN_CHAT_ID or user_id in EXTRA_ADMIN_IDS:
        return True
    candidate_chats: list[int | str] = []
    if chat_id is not None and str(chat_id).startswith("-"):
        candidate_chats.append(chat_id)
    target_grp = await resolve_target_group_id(bot, chat_id)
    if str(target_grp).startswith("-") and target_grp not in candidate_chats:
        candidate_chats.append(target_grp)

    for cid in candidate_chats:
        try:
            member = await bot.get_chat_member(chat_id=cid, user_id=user_id)
            if member.status in ("administrator", "creator"):
                return True
        except Exception as e:
            logger.debug(f"Admin check skipped for user {user_id} i
def generate_random_card() -> dict[str, str]:
    bin_prefix, brand, origin, country, country_detail, tz_name, zone = random.choice(
        SAMPLE_BINS
    )
    target_len = 15 if brand == "AMEX" else 16
    body_len = target_len - len(bin_prefix) - 1
    body = "".join(str(random.randint(0, 9)) for _ in range(max(0, body_len)))
    partial = bin_prefix + body
    card_number = partial + _luhn_check_digit(partial)

    month = f"{random.randint(1, 12):02d}"
    year = f"{random.randint(27, 32):02d}"
    cvv_len = 4 if brand == "AMEX" else 3
    cvv = "".join(str(random.randint(0, 9)) for _ in range(cvv_len))

    try:
        now_local = datetime.now(ZoneInfo(tz_name))
    except Exception:
        now_local = datetime.now()

    return {
        "bin": bin_prefix,
        "brand": brand,
        "origin": origin,
        "number": card_number,
        "expiry": f"{month}/{year}",
        "cvv": cvv,
        "date": now_local.strftime("%d-%m-%Y"),
        "time": now_local.strftime("%I:%M:%S %p"),
        "country": country,
        "country_detail": country_detail,
        "zone": zone,
        "note": random.choice(SAMPLE_TEXTS),
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


def build_start_button_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                make_blue_button("Start Button", callback_data="trigger_cc_drop"),
            ],
            [
                make_blue_button("Channel Join", url=CHANNEL_JOIN_URL),
                make_blue_button("CC Drop", callback_data="trigger_cc_drop"),
            ],
        ]
    )


def format_cc_drop_caption(user_mention: str, card: dict[str, str]) -> str:
    pe_hdr = tg_pe("header")
    pe_usr = tg_pe("user")
    pe_ug = tg_pe("ug")
    pe_crd = tg_pe("card")
    pe_exp = tg_pe("expiry")
    pe_cvv = tg_pe("cvv")
    pe_org = tg_pe("origin")
    pe_cnt = tg_pe("country")
    pe_cdt = tg_pe("country_detail")
    pe_zon = tg_pe("zone")
    pe_dt = tg_pe("datetime")
    pe_nt = tg_pe("note")

    return (
        f"{pe_hdr} <b>CC DROP • {html.escape(card['brand'])}</b> {pe_hdr}\n\n"
        f"{pe_usr} <b>Admin:</b> {user_mention}\n"
        f"{pe_ug} <b>UG Tier:</b> <code>ALL PREMIUM UG</code>\n\n"
        f"{pe_crd} <b>[CARD NUMBER]</b>\n"
        f"<code>{html.escape(card['number'])}</code>\n\n"
        f"{pe_exp} <b>[EXPIRY DATE]</b>\n"
        f"<code>{html.escape(card['expiry'])}</code>\n\n"
        f"{pe_cvv} <b>[CVV]</b>\n"
        f"<code>{html.escape(card['cvv'])}</code>\n\n"
        f"{pe_org} <b>[CARD ORIGIN]</b>\n"
        f"<b>{html.escape(card['origin'])}</b> (<code>{html.escape(card['bin'])}</code>)\n\n"
        f"{pe_cnt} <b>[COUNTRY]</b>\n"
        f"<b>{html.escape(card['country'])}</b>\n\n"
        f"{pe_cdt} <b>[COUNTRY DETAIL]</b>\n"
        f"{html.escape(card['country_detail'])}\n\n"
        f"{pe_zon} <b>[ZONE]</b>\n"
        f"<b>{html.escape(card['zone'])}</b>\n\n"
        f"{pe_dt} <b>[DATE & TIME]</b>\n"
        f"<code>{html.escape(card['date'])}</code> • <code>{html.escape(card['time'])}</code>\n\n"
        f"{pe_nt} <b>[TEXT]</b>\n"
        f"{html.escape(card['note'])}"
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
            logger.debug(f"Delete skipped for {message_id}: {e}")


def schedule_delete(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int | str, message_id: int
) -> None:
    if DELETE_AFTER_SECONDS <= 0:
        return
    if context.job_queue:
        context.job_queue.run_once(
            _job_delete_message,
            when=DELETE_AFTER_SECONDS,
            data={"chat_id": chat_id, "message_id": message_id},
            name=f"del_{chat_id}_{message_id}",
        )


async def send_photo_with_caption_and_buttons(
    bot,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int | str,
    photo_url: str,
    caption: str,
    auto_delete: bool = False,
) -> None:
    markup = build_start_button_keyboard()
    msg = None
    try:
        msg = await bot.send_photo(
            chat_id=chat_id,
            photo=photo_url,
            caption=caption,
            parse_mode="HTML",
            reply_markup=markup,
        )
    except Exception as e:
        logger.warning(f"Photo send fallback ({photo_url}): {e}")
        msg = await bot.send_message(
            chat_id=chat_id,
            text=caption,
            parse_mode="HTML",
            reply_markup=markup,
            disable_web_page_preview=True,
        )

    if msg and auto_delete:
        schedule_delete(context, chat_id, msg.message_id)


async def auto_group_cc_drop_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.bot_data.get("group_auto_cc_drop_enabled", True):
        return
    active_group = context.bot_data.get("active_group_chat_id")
    group_id = await resolve_target_group_id(context.bot, active_group)
    card = generate_random_card()
    photo_url = await get_ai_girl_photo_url()
    mention = '<a href="' + html.escape(CHANNEL_JOIN_URL) + '">ALL PREMIUM UG</a>'
    caption = format_cc_drop_caption(mention, card)
    try:
        await send_photo_with_caption_and_buttons(
            context.bot,
            context,
            group_id,
            photo_url,
            caption,
            auto_delete=True,
        )
    except Exception as e:
        logger.warning(f"Group auto CC drop failed: {e}")


def ensure_group_auto_drop_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.bot_data["group_auto_cc_drop_enabled"] = True
    if not context.job_queue:
        return
    if not context.job_queue.get_jobs_by_name("kushal_group_cc_drop_loop"):
        context.job_queue.run_repeating(
            auto_group_cc_drop_job,
            interval=max(10, AUTO_DROP_SECONDS),
            first=5,
            name="kushal_group_cc_drop_loop",
        )


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
    if not msg or not chat:
        return

    if str(chat.id).startswith("-"):
        context.bot_data["active_group_chat_id"] = chat.id

    sender_is_admin = False
    if user and not user.is_bot:
        sender_is_admin = await is_user_admin(context.bot, chat.id, user.id)

    if sender_is_admin:
        return

    if is_forwarded_or_restricted_message(msg):
        try:
            await msg.delete()
            logger.info(f"Deleted forwarded/link/username post in chat {chat.id}")
        except Exception as e:
            logger.debug(f"Could not delete restricted message {msg.message_id}: {e}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return

    user = update.effective_user
    chat = update.effective_chat
    if str(chat.id).startswith("-"):
        context.bot_data["active_group_chat_id"] = chat.id

    allowed = await is_user_admin(context.bot, chat.id, user.id)
    if not allowed:
        try:
            await update.message.reply_text(
                "Sirf Admin hi /start command aur iske buttons use kar sakte hain."
            )
        except Exception:
            pass
        return

    safe_name = html.escape(user.first_name or "Admin")
    mention = '<a href="tg://user?id=' + str(user.id) + '">' + safe_name + "</a>"

    pe_hdr = tg_pe("header")
    pe_usr = tg_pe("user")
    pe_ug = tg_pe("ug")

    photo_url = await get_ai_girl_photo_url()
    start_text = (
        f"{pe_hdr} <b>CC DROP STARTED • ADMIN PANEL</b> {pe_hdr}\n\n"
        f"{pe_usr} <b>Admin:</b> {mention}\n"
        f"{pe_ug} <b>UG Tier:</b> <code>ALL PREMIUM UG</code>\n\n"
        "Group aur DM dono mein <b>/start</b> active hai. Neeche <b>Start Button</b> "
        "ya <b>CC Drop</b> dabakar instant CC drop aur auto-drop loop chalu karein."
    )

    await send_photo_with_caption_and_buttons(
        context.bot,
        context,
        chat.id,
        photo_url,
        start_text,
        auto_delete=False,
    )


async def on_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.message or not query.from_user:
        return

    caller = query.from_user
    chat_id = query.message.chat.id if query.message.chat else None
    if chat_id is not None and str(chat_id).startswith("-"):
        context.bot_data["active_group_chat_id"] = chat_id

    allowed = await is_user_admin(context.bot, chat_id, caller.id)
    if not allowed:
        await query.answer(
            "Sirf Admin hi is button ko use kar sakte hain!", show_alert=True
        )
        return

    await query.answer("Admin verified • CC Drop & Start Button active!")
    safe_name = html.escape(caller.first_name or "Admin")
    mention = '<a href="tg://user?id=' + str(caller.id) + '">' + safe_name + "</a>"

    if query.data == "trigger_cc_drop":
        ensure_group_auto_drop_job(context)
        group_id = await resolve_target_group_id(context.bot, chat_id)
        card = generate_random_card()
        photo_url = await get_ai_girl_photo_url()
        caption = format_cc_drop_caption(mention, card)
        try:
            await send_photo_with_caption_and_buttons(
                context.bot,
                context,
                group_id,
                photo_url,
                caption,
                auto_delete=True,
            )
        except Exception as e:
            logger.warning(f"CC drop button group send failed: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception:", exc_info=context.error)


async def post_init(application: Application) -> None:
    application.bot_data["group_auto_cc_drop_enabled"] = True
    start_cmd = [BotCommand("start", "Start CC drop & admin panel")]
    for scope in (
        BotCommandScopeDefault(),
        BotCommandScopeAllGroupChats(),
        BotCommandScopeAllChatAdministrators(),
    ):
        try:
            await application.bot.set_my_commands(start_cmd, scope=scope)
        except Exception as e:
            logger.debug(f"Command scope skipped ({scope}): {e}")

    if application.job_queue and not application.job_queue.get_jobs_by_name(
        "kushal_group_cc_drop_loop"
    ):
        application.job_queue.run_repeating(
            auto_group_cc_drop_job,
            interval=max(10, AUTO_DROP_SECONDS),
            first=15,
            name="kushal_group_cc_drop_loop",
        )


def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN missing!")

    start_24x7_server(PORT)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

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

    logger.info("Kushal CC Drop Bot running with Admin Chat ID 6632236983...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
