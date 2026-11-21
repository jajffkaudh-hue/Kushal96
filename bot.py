import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import html
import json
import logging
import os
import random
import threading
import time
import urllib.parse
import urllib.request
from telegram import (
    BotCommand,
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
    os.getenv("BOT_TOKEN")
    or "8952746230:AAG54d6765BiySuKBc11VUbYv2FDq10TJ7E"
).strip()
ADMIN_ID = int(os.getenv("ADMIN_ID", "6632236983"))
PORT = int(os.getenv("PORT", "10000"))

RENDER_EXTERNAL_URL = (os.getenv("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
KEEP_ALIVE_INTERVAL = int(os.getenv("KEEP_ALIVE_INTERVAL", "240"))

UPI_ID = (os.getenv("UPI_ID") or "").strip()
UPI_NAME = (os.getenv("UPI_NAME") or "Kushal Store").strip()
DEFAULT_QR_URL = (os.getenv("QR_CODE_URL") or "").strip()

# Render disk clean rakhne ke liye sirf chhota state file (koi heavy media disk par save nahi)
STATE_FILE = "bot_state.json"

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

DEFAULT_SLOTS = [
    {
        "num_label": "1st",
        "badge": "⚫",
        "style": "primary",
        "button_name": "1st • Black Pack",
        "text": "1st slot special drop. Tap payment below to scan QR & confirm.",
        "price": 150,
        "qr": "",
    },
    {
        "num_label": "2nd",
        "badge": "🟠",
        "style": "danger",
        "button_name": "2nd • Orange Pack",
        "text": "2nd slot instant drop. Scan QR code after clicking payment.",
        "price": 180,
        "qr": "",
    },
    {
        "num_label": "3rd",
        "badge": "🟢",
        "style": "success",
        "button_name": "3rd • Green Pack",
        "text": "3rd slot premium pack. Complete QR payment & check status.",
        "price": 199,
        "qr": "",
    },
    {
        "num_label": "4th",
        "badge": "🔵",
        "style": "primary",
        "button_name": "4th • Blue Pack",
        "text": "4th slot featured drop. Fast admin verification available.",
        "price": 249,
        "qr": "",
    },
    {
        "num_label": "5th",
        "badge": "🟠",
        "style": "danger",
        "button_name": "5th • Yellow/Purple Pack",
        "text": "5th slot combo drop. Tap payment to get QR code.",
        "price": 299,
        "qr": "",
    },
]

DEFAULT_STATE = {
    "welcome_text": (
        "✨ <b>WELCOME, {mention}!</b> ✨\n\n"
        "👤 <b>User:</b> {mention}\n"
        "🌐 <b>Username:</b> {username}\n"
        "🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n\n"
        "Neeche diye gaye <b>1st se 5th</b> buttons mein se kisi par click karein:"
    ),
    "global_qr": "",
    "slots": DEFAULT_SLOTS,
}


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return json.loads(json.dumps(DEFAULT_STATE))
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        out = json.loads(json.dumps(DEFAULT_STATE))
        if isinstance(raw, dict):
            if isinstance(raw.get("welcome_text"), str) and raw["welcome_text"].strip():
                out["welcome_text"] = raw["welcome_text"]
            if isinstance(raw.get("global_qr"), str):
                out["global_qr"] = raw["global_qr"]
            slots = raw.get("slots")
            if isinstance(slots, list) and len(slots) == 5:
                for idx in range(5):
                    if isinstance(slots[idx], dict):
                        out["slots"][idx].update(slots[idx])
        return out
    except Exception as e:
        logger.warning(f"State load fallback: {e}")
        return json.loads(json.dumps(DEFAULT_STATE))


def save_state(state: dict) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"State save failed: {e}")


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


def make_styled_button(
    text: str, callback_data: str, style: str | None = None
) -> InlineKeyboardButton:
    if style in ("primary", "success", "danger"):
        return InlineKeyboardButton(
            text=text,
            callback_data=callback_data,
            api_kwargs={"style": style},
        )
    return InlineKeyboardButton(text=text, callback_data=callback_data)


def build_five_numbered_buttons(state: dict) -> InlineKeyboardMarkup:
    slots = state.get("slots") or DEFAULT_SLOTS
    rows = []
    for idx, slot in enumerate(slots):
        num_lbl = slot.get("num_label") or ["1st", "2nd", "3rd", "4th", "5th"][idx]
        badge = slot.get("badge") or ""
        b_name = str(slot.get("button_name") or f"{num_lbl} Option").strip()
        display_text = f"{badge} [{num_lbl}] {b_name}".strip()
        rows.append(
            [
                make_styled_button(
                    text=display_text,
                    callback_data=f"slot_pick:{idx}",
                    style=slot.get("style"),
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


def build_single_payment_button(
    slot_idx: int, price: int, style: str | None = "success"
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                make_styled_button(
                    text=f"💳 Payment ₹{price}",
                    callback_data=f"pay_slot:{slot_idx}",
                    style=style,
                )
            ]
        ]
    )


def build_qr_back_check_keyboard(order_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                make_styled_button(
                    text="🔙 Back",
                    callback_data="go_back",
                    style="danger",
                ),
                make_styled_button(
                    text="✅ Check Payment",
                    callback_data=f"check_pay:{order_id}",
                    style="success",
                ),
            ]
        ]
    )


def get_qr_media(state: dict, slot: dict, amount: int, order_id: str) -> str:
    custom_qr = (slot.get("qr") or state.get("global_qr") or DEFAULT_QR_URL or "").strip()
    if custom_qr:
        return custom_qr
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
    payload = f"ORDER:{order_id}|AMOUNT:INR {amount}"
    return (
        "https://api.qrserver.com/v1/create-qr-code/?size=400x400&data="
        + urllib.parse.quote(payload)
    )


async def send_three_random_photos_group(
    target_message, caption_for_group: str = ""
) -> list[str]:
    chosen = random.sample(PHOTO_FILES, k=min(3, len(PHOTO_FILES)))
    urls = [f"{RAW_BASE}/{fname}" for fname in chosen]
    media = []
    for i, u in enumerate(urls):
        if i == len(urls) - 1 and caption_for_group:
            media.append(InputMediaPhoto(media=u, caption=caption_for_group, parse_mode="HTML"))
        else:
            media.append(InputMediaPhoto(media=u))
    try:
        await target_message.reply_media_group(media=media)
    except Exception as e:
        logger.warning(f"3x media group send fallback: {e}")
        for u in urls:
            try:
                await target_message.reply_photo(photo=u)
            except Exception:
                pass
    return urls


async def send_start_screen(target_message, user, chat_id: int) -> None:
    state = load_state()
    safe_name = html.escape(user.first_name or "User")
    mention = f'<a href="tg://user?id={user.id}">{safe_name}</a>'
    username = f"@{html.escape(user.username)}" if user.username else "Not set"

    # Pehle 3 random photos ek saath
    await send_three_random_photos_group(target_message)

    # Uske neeche text aur 5 alag-alag color/numbered buttons
    tpl = state.get("welcome_text") or DEFAULT_STATE["welcome_text"]
    try:
        body_text = tpl.format(
            mention=mention,
            username=username,
            chat_id=chat_id,
            name=safe_name,
        )
    except Exception:
        body_text = (
            f"✨ <b>WELCOME, {mention}!</b> ✨\n"
            f"🆔 <b>Chat ID:</b> <code>{chat_id}</code>\n\n"
            f"Neeche <b>1st se 5th</b> buttons mein se chunein:"
        )

    await target_message.reply_text(
        text=body_text,
        parse_mode="HTML",
        reply_markup=build_five_numbered_buttons(state),
        disable_web_page_preview=True,
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return
    await send_start_screen(update.message, update.effective_user, update.effective_chat.id)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    if ADMIN_ID == 0 or update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Yeh Admin Panel sirf Admin ke liye hai.")
        return

    state = load_state()
    slots = state.get("slots") or DEFAULT_SLOTS
    lines = ["🛠️ <b>ADMIN PANEL — NUMBERED SLOTS (1st - 5th)</b>\n"]
    for idx, s in enumerate(slots):
        num_lbl = s.get("num_label") or ["1st", "2nd", "3rd", "4th", "5th"][idx]
        lines.append(
            f"• <b>{num_lbl} Number:</b> Btn = <code>{html.escape(str(s.get('button_name')))}</code> | "
            f"Price = <b>₹{s.get('price')}</b> | QR = {'Custom' if s.get('qr') else 'Default'}"
        )

    kb = InlineKeyboardMarkup(
        [
            [
                make_styled_button("🖼️ Change QR", "adm_menu:qr", "primary"),
                make_styled_button("🏷️ Change Button Name", "adm_menu:btn", "success"),
            ],
            [
                make_styled_button("✏️ Change Text", "adm_menu:txt", "danger"),
                make_styled_button("🔄 Reset Defaults", "adm_reset", "primary"),
            ],
        ]
    )
    await update.message.reply_text(
        text="\n".join(lines) + "\n\nKya change karna hai? Option chunein:",
        parse_mode="HTML",
        reply_markup=kb,
    )


def build_slot_number_keyboard(action_prefix: str) -> InlineKeyboardMarkup:
    # action_prefix: set_qr | set_btn | set_txt
    labels = [
        ("1️⃣ 1st Number", "primary"),
        ("2️⃣ 2nd Number", "danger"),
        ("3️⃣ 3rd Number", "success"),
        ("4️⃣ 4th Number", "primary"),
        ("5️⃣ 5th Number", "danger"),
    ]
    rows = []
    for idx, (lbl, st) in enumerate(labels):
        rows.append([make_styled_button(lbl, f"{action_prefix}:{idx}", st)])
    if action_prefix == "set_txt":
        rows.append([make_styled_button("✨ Welcome Text", "set_txt:welcome", "success")])
    rows.append([make_styled_button("🔙 Back to Menu", "go_back", "danger")])
    return InlineKeyboardMarkup(rows)


async def handle_admin_text_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> bool:
    if not update.message or not update.effective_user:
        return False
    if ADMIN_ID == 0 or update.effective_user.id != ADMIN_ID:
        return False

    pending = context.user_data.get("adm_pending")
    if not isinstance(pending, dict):
        return False

    mode = pending.get("mode")
    target = pending.get("target")
    context.user_data["adm_pending"] = None

    state = load_state()

    if mode == "qr":
        if target == "global":
            state["global_qr"] = text
            save_state(state)
            await update.message.reply_text("✅ Global QR URL update ho gaya.")
            return True
        idx = int(target)
        num_lbl = state["slots"][idx].get("num_label") or f"#{idx+1}"
        state["slots"][idx]["qr"] = text
        save_state(state)
        await update.message.reply_text(
            f"✅ <b>{html.escape(num_lbl)} Number</b> ka QR update ho gaya!",
            parse_mode="HTML",
        )
        return True

    if mode == "btn":
        idx = int(target)
        num_lbl = state["slots"][idx].get("num_label") or f"#{idx+1}"
        state["slots"][idx]["button_name"] = text
        save_state(state)
        await update.message.reply_text(
            f"✅ <b>{html.escape(num_lbl)} Number</b> button ka naam badal kar <b>{html.escape(text)}</b> ho gaya!",
            parse_mode="HTML",
        )
        return True

    if mode == "txt":
        if target == "welcome":
            state["welcome_text"] = text
            save_state(state)
            await update.message.reply_text("✅ Welcome text update ho gaya!")
            return True
        idx = int(target)
        num_lbl = state["slots"][idx].get("num_label") or f"#{idx+1}"
        state["slots"][idx]["text"] = text
        save_state(state)
        await update.message.reply_text(
            f"✅ <b>{html.escape(num_lbl)} Number</b> ka text update ho gaya!",
            parse_mode="HTML",
        )
        return True

    return False


async def handle_admin_photo_input(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.message or not update.effective_user or not update.message.photo:
        return
    if ADMIN_ID == 0 or update.effective_user.id != ADMIN_ID:
        return

    pending = context.user_data.get("adm_pending")
    if not isinstance(pending, dict) or pending.get("mode") != "qr":
        return

    file_id = update.message.photo[-1].file_id
    target = pending.get("target")
    context.user_data["adm_pending"] = None

    state = load_state()
    if target == "global":
        state["global_qr"] = file_id
        save_state(state)
        await update.message.reply_text("✅ Global QR photo save ho gayi!")
        return

    idx = int(target)
    num_lbl = state["slots"][idx].get("num_label") or f"#{idx+1}"
    state["slots"][idx]["qr"] = file_id
    save_state(state)
    await update.message.reply_text(
        f"✅ <b>{html.escape(num_lbl)} Number</b> ke liye nayi QR photo save ho gayi!",
        parse_mode="HTML",
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if not text:
        return
    await handle_admin_text_input(update, context, text)


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

    state = load_state()
    slots = state.get("slots") or DEFAULT_SLOTS

    if data == "go_back":
        await send_start_screen(query.message, caller, chat_id)
        return

    # Admin Panel actions
    if data.startswith("adm_menu:"):
        if ADMIN_ID == 0 or caller.id != ADMIN_ID:
            return
        kind = data.split(":", 1)[1]
        if kind == "qr":
            kb = build_slot_number_keyboard("set_qr")
            await query.message.reply_text(
                "🖼️ <b>Kis Number ka QR change karna hai?</b>\n"
                "Number chunein, phir naya <b>QR photo</b> ya <b>QR image URL</b> bhejein:",
                parse_mode="HTML",
                reply_markup=kb,
            )
        elif kind == "btn":
            kb = build_slot_number_keyboard("set_btn")
            await query.message.reply_text(
                "🏷️ <b>Kis Number ke button ka naam change karna hai?</b>\n"
                "1st, 2nd, 3rd, 4th ya 5th number chunein:",
                parse_mode="HTML",
                reply_markup=kb,
            )
        elif kind == "txt":
            kb = build_slot_number_keyboard("set_txt")
            await query.message.reply_text(
                "✏️ <b>Kis Number ka text change karna hai?</b>\n"
                "1st, 2nd, 3rd, 4th ya 5th number (ya Welcome Text) chunein:",
                parse_mode="HTML",
                reply_markup=kb,
            )
        return

    if data.startswith("set_qr:"):
        if ADMIN_ID == 0 or caller.id != ADMIN_ID:
            return
        target = data.split(":", 1)[1]
        context.user_data["adm_pending"] = {"mode": "qr", "target": target}
        num_title = "Global QR" if target == "global" else f"{slots[int(target)].get('num_label')} Number QR"
        await query.message.reply_text(
            f"📸 Ab <b>{html.escape(num_title)}</b> ke liye QR photo ya image URL bhejein:",
            parse_mode="HTML",
        )
        return

    if data.startswith("set_btn:"):
        if ADMIN_ID == 0 or caller.id != ADMIN_ID:
            return
        idx = int(data.split(":", 1)[1])
        context.user_data["adm_pending"] = {"mode": "btn", "target": idx}
        num_lbl = slots[idx].get("num_label") or f"#{idx+1}"
        await query.message.reply_text(
            f"✍️ Ab <b>{html.escape(num_lbl)} Number</b> button ka naya naam likh kar bhejein:",
            parse_mode="HTML",
        )
        return

    if data.startswith("set_txt:"):
        if ADMIN_ID == 0 or caller.id != ADMIN_ID:
            return
        target = data.split(":", 1)[1]
        context.user_data["adm_pending"] = {"mode": "txt", "target": target}
        lbl = "Welcome Text" if target == "welcome" else f"{slots[int(target)].get('num_label')} Number Text"
        await query.message.reply_text(
            f"✍️ Ab <b>{html.escape(lbl)}</b> ke liye naya text likh kar bhejein:",
            parse_mode="HTML",
        )
        return

    if data == "adm_reset":
        if ADMIN_ID == 0 or caller.id != ADMIN_ID:
            return
        save_state(json.loads(json.dumps(DEFAULT_STATE)))
        await query.message.reply_text("✅ Sabhi 1st–5th slots, buttons aur text default par reset ho gaye.")
        return

    # 1st - 5th Button Click -> 3 Random Photos + Text + Price + Single Payment Button
    if data.startswith("slot_pick:"):
        try:
            idx = int(data.split(":", 1)[1])
        except ValueError:
            idx = 0
        idx = max(0, min(4, idx))
        slot = slots[idx]
        num_lbl = slot.get("num_label") or f"#{idx+1}"
        btn_title = str(slot.get("button_name") or f"{num_lbl} Pack")
        slot_text = str(slot.get("text") or random.choice([
            "Random selection ready. Tap payment below to view QR code.",
            "Fresh 3x photo drop loaded. Proceed to payment below.",
        ]))
        price = int(slot.get("price") or PRICES[idx % len(PRICES)])

        # 3 random photos ek saath
        await send_three_random_photos_group(query.message)

        # Uske neeche text + price + single payment button
        item_caption = (
            f"📦 <b>[{html.escape(num_lbl)}] {html.escape(btn_title)}</b>\n\n"
            f"📝 <b>Text:</b> {html.escape(slot_text)}\n"
            f"💰 <b>Price:</b> <b>₹{price}</b>"
        )
        await query.message.reply_text(
            text=item_caption,
            parse_mode="HTML",
            reply_markup=build_single_payment_button(idx, price, slot.get("style")),
        )
        return

    # Single Payment Button Click -> QR Code Photo + Text + Back & Check Payment Buttons
    if data.startswith("pay_slot:"):
        try:
            idx = int(data.split(":", 1)[1])
        except ValueError:
            idx = 0
        idx = max(0, min(4, idx))
        slot = slots[idx]
        num_lbl = slot.get("num_label") or f"#{idx+1}"
        title = f"[{num_lbl}] {slot.get('button_name') or 'Pack'}"
        price = int(slot.get("price") or PRICES[idx % len(PRICES)])
        order_id = f"ORD{int(time.time())}{caller.id % 1000}"

        orders_store: dict = context.bot_data.setdefault("orders", {})
        orders_store[order_id] = {
            "order_id": order_id,
            "user_id": caller.id,
            "chat_id": chat_id,
            "full_name": caller.full_name,
            "username": caller.username or "Not set",
            "title": title,
            "price": price,
        }

        qr_media = get_qr_media(state, slot, price, order_id)
        upi_line = f"🏦 <b>UPI ID:</b> <code>{html.escape(UPI_ID)}</code>\n" if UPI_ID else ""

        qr_text = (
            f"📲 <b>PAYMENT QR CODE</b>\n\n"
            f"🆔 <b>Order ID:</b> <code>{html.escape(order_id)}</code>\n"
            f"📦 <b>Option:</b> {html.escape(title)}\n"
            f"💰 <b>Price:</b> <b>₹{price}</b>\n"
            f"{upi_line}"
            f"📝 <b>Text:</b> QR scan karke payment karein aur neeche <b>Check Payment</b> dabayein, ya <b>Back</b> dabayein."
        )

        qr_kb = build_qr_back_check_keyboard(order_id)
        try:
            await query.message.reply_photo(
                photo=qr_media,
                caption=qr_text,
                parse_mode="HTML",
                reply_markup=qr_kb,
            )
        except Exception as e:
            logger.warning(f"QR media send fallback: {e}")
            await query.message.reply_text(
                text=qr_text,
                parse_mode="HTML",
                reply_markup=qr_kb,
            )
        return

    # Check Payment -> Admin ko message bhejna
    if data.startswith("check_pay:"):
        order_id = data.split(":", 1)[1].strip()
        orders_store: dict = context.bot_data.get("orders") or {}
        order = orders_store.get(order_id) or {
            "order_id": order_id,
            "user_id": caller.id,
            "chat_id": chat_id,
            "full_name": caller.full_name,
            "username": caller.username or "Not set",
            "title": "Selected Pack",
            "price": random.choice(PRICES),
        }

        uname = (
            f"@{html.escape(str(order['username']))}"
            if order.get("username") and order.get("username") != "Not set"
            else "Not set"
        )
        safe_name = html.escape(str(order.get("full_name") or "User"))

        if ADMIN_ID != 0:
            admin_msg = (
                f"🔔 <b>USER PAYMENT CHECK ALERT</b>\n\n"
                f"User ne payment kar diya hai / check karne ke liye click kiya hai:\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>User:</b> {safe_name}\n"
                f"🌐 <b>Username:</b> {uname}\n"
                f"🆔 <b>User ID:</b> <code>{order['user_id']}</code>\n"
                f"💬 <b>Chat ID:</b> <code>{order['chat_id']}</code>\n"
                f"🧾 <b>Order ID:</b> <code>{html.escape(order_id)}</code>\n"
                f"📦 <b>Pack:</b> {html.escape(str(order['title']))}\n"
                f"💰 <b>Amount:</b> <b>₹{order['price']}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━"
            )
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=admin_msg,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"Admin payment alert failed: {e}")

        await query.message.reply_text(
            f"✅ <b>Payment Check Message Sent to Admin!</b>\n\n"
            f"Order ID: <code>{html.escape(order_id)}</code>\n"
            f"Amount: <b>₹{order['price']}</b>\n\n"
            f"Admin ko aapki payment request bhej di gayi hai.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        make_styled_button("🔙 Back", "go_back", "primary"),
                    ]
                ]
            ),
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception:", exc_info=context.error)


async def post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Start menu (3x photos + 5 buttons)"),
            BotCommand("admin", "Admin panel (QR, button name, text)"),
        ]
    )


def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN missing!")

    start_24x7_server(PORT)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_admin_photo_input))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(on_button_click))
    app.add_error_handler(error_handler)

    logger.info("24/7 Bot started cleanly...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()