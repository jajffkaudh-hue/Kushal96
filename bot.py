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
    BotCommandScopeChat,
    BotCommandScopeDefault,
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
UPI_NAME = (os.getenv("UPI_NAME") or "Official Store").strip()
DEFAULT_QR_URL = (os.getenv("QR_CODE_URL") or "").strip()

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

DEFAULT_ITEMS = [
    {
        "title": "⚡ Obsidian Edition",
        "style": "primary",
        "text": "Curated collection with instant access details and fast checkout.",
        "price": 150,
        "qr": "",
        "qr_text": "Scan the QR code to complete your payment, then tap Check Payment.",
        "photo": "",
    },
    {
        "title": "💎 Sapphire Vault",
        "style": "primary",
        "text": "Selected showcase with clean layout and verified order support.",
        "price": 180,
        "qr": "",
        "qr_text": "Complete payment via QR scan and press Check Payment below.",
        "photo": "",
    },
    {
        "title": "🔥 Ember Select",
        "style": "danger",
        "text": "Featured edition ready to view with simple step-by-step confirmation.",
        "price": 199,
        "qr": "",
        "qr_text": "Pay using the QR code shown above, then tap Check Payment.",
        "photo": "",
    },
    {
        "title": "🌿 Emerald Pass",
        "style": "success",
        "text": "Smooth member selection with quick QR checkout and admin review.",
        "price": 249,
        "qr": "",
        "qr_text": "Scan QR to pay the exact amount, then click Check Payment.",
        "photo": "",
    },
    {
        "title": "👑 Royal Crown",
        "style": "danger",
        "text": "Signature collection with priority check after payment confirmation.",
        "price": 299,
        "qr": "",
        "qr_text": "Finish QR payment and tap Check Payment to notify the store admin.",
        "photo": "",
    },
]

DEFAULT_STATE = {
    "welcome_text": (
        "✨ <b>WELCOME, {mention}!</b> ✨\n\n"
        "Explore our curated selections below and tap any option to continue."
    ),
    "global_qr": "",
    "global_qr_text": "Scan the QR code below to complete your payment, then tap Check Payment.",
    "items": DEFAULT_ITEMS,
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
            if isinstance(raw.get("global_qr_text"), str) and raw["global_qr_text"].strip():
                out["global_qr_text"] = raw["global_qr_text"]
            items = raw.get("items")
            if isinstance(items, list) and len(items) >= 1:
                cleaned = []
                for idx, entry in enumerate(items):
                    base = json.loads(
                        json.dumps(DEFAULT_ITEMS[idx % len(DEFAULT_ITEMS)])
                    )
                    if isinstance(entry, dict):
                        base.update(entry)
                    cleaned.append(base)
                out["items"] = cleaned
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
            body = b'{"status":"ok","bot":"protected-store-active"}'
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


def build_menu_buttons(state: dict) -> InlineKeyboardMarkup:
    items = state.get("items") or DEFAULT_ITEMS
    rows = []
    for idx, item in enumerate(items):
        btn_text = str(item.get("title") or f"✨ Option {idx + 1}").strip()
        rows.append(
            [
                make_styled_button(
                    text=btn_text,
                    callback_data=f"pick_item:{idx}",
                    style=item.get("style"),
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


def build_payment_button(
    idx: int, price: int, style: str | None = "success"
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                make_styled_button(
                    text=f"💳 Pay ₹{price}",
                    callback_data=f"pay_item:{idx}",
                    style=style,
                )
            ]
        ]
    )


def build_qr_buttons(order_id: str) -> InlineKeyboardMarkup:
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


def get_qr_media(state: dict, item: dict, amount: int, order_id: str) -> str:
    custom_qr = (
        item.get("qr") or state.get("global_qr") or DEFAULT_QR_URL or ""
    ).strip()
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


async def send_three_photos(
    target_message, primary_photo: str = ""
) -> None:
    pool = [f"{RAW_BASE}/{fname}" for fname in PHOTO_FILES]
    chosen: list[str] = []
    if primary_photo:
        chosen.append(primary_photo)
    candidates = [u for u in pool if u != primary_photo]
    need = max(0, 3 - len(chosen))
    if need > 0 and candidates:
        chosen.extend(random.sample(candidates, k=min(need, len(candidates))))

    media = [InputMediaPhoto(media=u) for u in chosen[:3]]
    try:
        await target_message.reply_media_group(
            media=media,
            protect_content=True,
        )
    except Exception as e:
        logger.warning(f"3x media group fallback: {e}")
        for u in chosen[:3]:
            try:
                await target_message.reply_photo(
                    photo=u,
                    protect_content=True,
                )
            except Exception:
                pass


async def send_start_screen(target_message, user, chat_id: int) -> None:
    state = load_state()
    safe_name = html.escape(user.first_name or "Member")
    mention = f'<a href="tg://user?id={user.id}">{safe_name}</a>'
    username = f"@{html.escape(user.username)}" if user.username else "Not set"

    await send_three_photos(target_message)

    tpl = state.get("welcome_text") or DEFAULT_STATE["welcome_text"]
    try:
        welcome_msg = tpl.format(
            mention=mention,
            username=username,
            chat_id=chat_id,
            name=safe_name,
        )
    except Exception:
        welcome_msg = f"✨ <b>WELCOME, {mention}!</b> ✨\n\nSelect an option below:"

    await target_message.reply_text(
        text=welcome_msg,
        parse_mode="HTML",
        reply_markup=build_menu_buttons(state),
        disable_web_page_preview=True,
        protect_content=True,
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user or not update.effective_chat:
        return
    await send_start_screen(update.message, update.effective_user, update.effective_chat.id)


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return
    if ADMIN_ID == 0 or update.effective_user.id != ADMIN_ID:
        return

    state = load_state()
    items = state.get("items") or DEFAULT_ITEMS
    summary_lines = ["🛠️ <b>ADMIN CONTROL PANEL</b>\n"]
    for idx, it in enumerate(items):
        summary_lines.append(
            f"• <b>{html.escape(str(it.get('title')))}</b> — ₹{it.get('price')}"
        )

    kb = InlineKeyboardMarkup(
        [
            [
                make_styled_button("🏷️ Change Button Name", "adm_pick:btn", "primary"),
                make_styled_button("✏️ Change Text", "adm_pick:txt", "success"),
            ],
            [
                make_styled_button("🖼️ Change QR", "adm_pick:qr", "primary"),
                make_styled_button("📝 Change QR Text", "adm_pick:qr_txt", "danger"),
            ],
            [
                make_styled_button("➕ Add New Product", "adm_add_prod", "success"),
                make_styled_button("🔄 Reset Defaults", "adm_reset", "danger"),
            ],
        ]
    )
    await update.message.reply_text(
        text="\n".join(summary_lines) + "\n\nChoose an action below:",
        parse_mode="HTML",
        reply_markup=kb,
        protect_content=True,
    )


def build_item_selector_keyboard(
    state: dict, prefix: str, include_special: str | None = None
) -> InlineKeyboardMarkup:
    items = state.get("items") or DEFAULT_ITEMS
    rows = []
    styles = ["primary", "success", "danger"]
    for idx, it in enumerate(items):
        lbl = str(it.get("title") or f"Option {idx + 1}")
        rows.append(
            [
                make_styled_button(
                    text=f"✦ {lbl}",
                    callback_data=f"{prefix}:{idx}",
                    style=styles[idx % len(styles)],
                )
            ]
        )
    if include_special == "welcome":
        rows.append(
            [make_styled_button("✨ Welcome Text", f"{prefix}:welcome", "primary")]
        )
    elif include_special == "qr_txt":
        rows.append(
            [make_styled_button("🌐 Default QR Text", f"{prefix}:global", "primary")]
        )
    elif include_special == "qr":
        rows.append(
            [make_styled_button("🌐 Default QR Code", f"{prefix}:global", "primary")]
        )
    rows.append([make_styled_button("🔙 Back", "go_back", "danger")])
    return InlineKeyboardMarkup(rows)


async def handle_admin_text(
    update: Update, context: ContextTypes.DEFAULT_TYPE, text: str
) -> bool:
    if not update.message or not update.effective_user:
        return False
    if ADMIN_ID == 0 or update.effective_user.id != ADMIN_ID:
        return False

    pending = context.user_data.get("adm_pending")
    if not isinstance(pending, dict):
        return False

    step = pending.get("step")
    state = load_state()

    if step == "btn_name":
        idx = int(pending["idx"])
        state["items"][idx]["title"] = text
        save_state(state)
        context.user_data["adm_pending"] = None
        await update.message.reply_text(
            f"✅ Button name updated to <b>{html.escape(text)}</b>.",
            parse_mode="HTML",
            protect_content=True,
        )
        return True

    if step == "item_text":
        target = pending["target"]
        if target == "welcome":
            state["welcome_text"] = text
        else:
            state["items"][int(target)]["text"] = text
        save_state(state)
        context.user_data["adm_pending"] = None
        await update.message.reply_text(
            "✅ Text updated successfully.",
            protect_content=True,
        )
        return True

    if step == "qr_media":
        target = pending["target"]
        if target == "global":
            state["global_qr"] = text
        else:
            state["items"][int(target)]["qr"] = text
        save_state(state)
        context.user_data["adm_pending"] = None
        await update.message.reply_text(
            "✅ QR code updated successfully.",
            protect_content=True,
        )
        return True

    if step == "qr_text":
        target = pending["target"]
        if target == "global":
            state["global_qr_text"] = text
        else:
            state["items"][int(target)]["qr_text"] = text
        save_state(state)
        context.user_data["adm_pending"] = None
        await update.message.reply_text(
            "✅ QR text updated successfully.",
            protect_content=True,
        )
        return True

    if step == "new_prod_title":
        pending["title"] = text
        pending["step"] = "new_prod_price"
        context.user_data["adm_pending"] = pending
        await update.message.reply_text(
            "💰 Enter product price (number only, e.g. <code>199</code>):",
            parse_mode="HTML",
            protect_content=True,
        )
        return True

    if step == "new_prod_price":
        digits = "".join(ch for ch in text if ch.isdigit())
        price_val = int(digits) if digits else 199
        pending["price"] = price_val
        pending["step"] = "new_prod_text"
        context.user_data["adm_pending"] = pending
        await update.message.reply_text(
            "📝 Enter product description text:",
            protect_content=True,
        )
        return True

    if step == "new_prod_text":
        pending["text"] = text
        pending["step"] = "new_prod_photo"
        context.user_data["adm_pending"] = pending
        await update.message.reply_text(
            "🖼️ Send product photo (or send a photo URL / type <code>skip</code> to use random photo):",
            parse_mode="HTML",
            protect_content=True,
        )
        return True

    if step == "new_prod_photo":
        photo_val = "" if text.lower() == "skip" else text
        styles = ["primary", "success", "danger"]
        new_entry = {
            "title": str(pending.get("title") or "✨ New Edition"),
            "style": styles[len(state["items"]) % len(styles)],
            "text": str(pending.get("text") or "Fresh product added."),
            "price": int(pending.get("price") or 199),
            "qr": "",
            "qr_text": state.get("global_qr_text")
            or DEFAULT_STATE["global_qr_text"],
            "photo": photo_val,
        }
        state["items"].append(new_entry)
        save_state(state)
        context.user_data["adm_pending"] = None
        await update.message.reply_text(
            f"✅ New product <b>{html.escape(new_entry['title'])}</b> (₹{new_entry['price']}) added!",
            parse_mode="HTML",
            protect_content=True,
        )
        return True

    return False


async def handle_admin_photo(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.message or not update.effective_user or not update.message.photo:
        return
    if ADMIN_ID == 0 or update.effective_user.id != ADMIN_ID:
        return

    pending = context.user_data.get("adm_pending")
    if not isinstance(pending, dict):
        return

    step = pending.get("step")
    file_id = update.message.photo[-1].file_id
    state = load_state()

    if step == "qr_media":
        target = pending["target"]
        if target == "global":
            state["global_qr"] = file_id
        else:
            state["items"][int(target)]["qr"] = file_id
        save_state(state)
        context.user_data["adm_pending"] = None
        await update.message.reply_text(
            "✅ QR photo saved successfully.",
            protect_content=True,
        )

    elif step == "new_prod_photo":
        styles = ["primary", "success", "danger"]
        new_entry = {
            "title": str(pending.get("title") or "✨ New Edition"),
            "style": styles[len(state["items"]) % len(styles)],
            "text": str(pending.get("text") or "Fresh product added."),
            "price": int(pending.get("price") or 199),
            "qr": "",
            "qr_text": state.get("global_qr_text")
            or DEFAULT_STATE["global_qr_text"],
            "photo": file_id,
        }
        state["items"].append(new_entry)
        save_state(state)
        context.user_data["adm_pending"] = None
        await update.message.reply_text(
            f"✅ New product <b>{html.escape(new_entry['title'])}</b> with photo added!",
            parse_mode="HTML",
            protect_content=True,
        )


async def handle_text_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if not text:
        return
    await handle_admin_text(update, context, text)


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
    items = state.get("items") or DEFAULT_ITEMS

    if data == "go_back":
        await send_start_screen(query.message, caller, chat_id)
        return

    # Admin Panel callbacks
    if data.startswith("adm_pick:"):
        if ADMIN_ID == 0 or caller.id != ADMIN_ID:
            return
        mode = data.split(":", 1)[1]
        if mode == "btn":
            kb = build_item_selector_keyboard(state, "edit_btn")
            await query.message.reply_text(
                "🏷️ Select which button name you want to change:",
                reply_markup=kb,
                protect_content=True,
            )
        elif mode == "txt":
            kb = build_item_selector_keyboard(state, "edit_txt", include_special="welcome")
            await query.message.reply_text(
                "✏️ Select which text you want to change:",
                reply_markup=kb,
                protect_content=True,
            )
        elif mode == "qr":
            kb = build_item_selector_keyboard(state, "edit_qr", include_special="qr")
            await query.message.reply_text(
                "🖼️ Select which QR code you want to change:",
                reply_markup=kb,
                protect_content=True,
            )
        elif mode == "qr_txt":
            kb = build_item_selector_keyboard(
                state, "edit_qr_txt", include_special="qr_txt"
            )
            await query.message.reply_text(
                "📝 Select which QR text you want to change:",
                reply_markup=kb,
                protect_content=True,
            )
        return

    if data.startswith("edit_btn:"):
        if ADMIN_ID == 0 or caller.id != ADMIN_ID:
            return
        idx = int(data.split(":", 1)[1])
        context.user_data["adm_pending"] = {"step": "btn_name", "idx": idx}
        await query.message.reply_text(
            "✍️ Send the new button name:",
            protect_content=True,
        )
        return

    if data.startswith("edit_txt:"):
        if ADMIN_ID == 0 or caller.id != ADMIN_ID:
            return
        target = data.split(":", 1)[1]
        context.user_data["adm_pending"] = {"step": "item_text", "target": target}
        await query.message.reply_text(
            "✍️ Send the new text:",
            protect_content=True,
        )
        return

    if data.startswith("edit_qr:"):
        if ADMIN_ID == 0 or caller.id != ADMIN_ID:
            return
        target = data.split(":", 1)[1]
        context.user_data["adm_pending"] = {"step": "qr_media", "target": target}
        await query.message.reply_text(
            "🖼️ Send a new QR photo or image URL:",
            protect_content=True,
        )
        return

    if data.startswith("edit_qr_txt:"):
        if ADMIN_ID == 0 or caller.id != ADMIN_ID:
            return
        target = data.split(":", 1)[1]
        context.user_data["adm_pending"] = {"step": "qr_text", "target": target}
        await query.message.reply_text(
            "📝 Send the new text to display under the QR code:",
            protect_content=True,
        )
        return

    if data == "adm_add_prod":
        if ADMIN_ID == 0 or caller.id != ADMIN_ID:
            return
        context.user_data["adm_pending"] = {"step": "new_prod_title"}
        await query.message.reply_text(
            "➕ <b>Add New Product</b>\n\nEnter the new product/button title:",
            parse_mode="HTML",
            protect_content=True,
        )
        return

    if data == "adm_reset":
        if ADMIN_ID == 0 or caller.id != ADMIN_ID:
            return
        save_state(json.loads(json.dumps(DEFAULT_STATE)))
        await query.message.reply_text(
            "✅ Default settings restored.",
            protect_content=True,
        )
        return

    # User selection -> 3 random photos + text + price + single payment button
    if data.startswith("pick_item:"):
        try:
            idx = int(data.split(":", 1)[1])
        except ValueError:
            idx = 0
        idx = max(0, min(len(items) - 1, idx))
        item = items[idx]

        title = str(item.get("title") or "✨ Selection")
        desc = str(item.get("text") or "Selected item ready.")
        price = int(item.get("price") or 199)
        custom_photo = str(item.get("photo") or "").strip()

        await send_three_photos(query.message, primary_photo=custom_photo)

        detail_text = (
            f"✨ <b>{html.escape(title)}</b>\n\n"
            f"📝 {html.escape(desc)}\n\n"
            f"💰 <b>Price:</b> <b>₹{price}</b>"
        )
        await query.message.reply_text(
            text=detail_text,
            parse_mode="HTML",
            reply_markup=build_payment_button(idx, price, item.get("style")),
            protect_content=True,
        )
        return

    # Payment button -> QR code + QR text + Back & Check Payment
    if data.startswith("pay_item:"):
        try:
            idx = int(data.split(":", 1)[1])
        except ValueError:
            idx = 0
        idx = max(0, min(len(items) - 1, idx))
        item = items[idx]

        title = str(item.get("title") or "Selected Item")
        price = int(item.get("price") or 199)
        qr_note = str(
            item.get("qr_text")
            or state.get("global_qr_text")
            or DEFAULT_STATE["global_qr_text"]
        )
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

        qr_media = get_qr_media(state, item, price, order_id)
        upi_line = (
            f"🏦 <b>UPI ID:</b> <code>{html.escape(UPI_ID)}</code>\n" if UPI_ID else ""
        )

        qr_caption = (
            f"📲 <b>PAYMENT QR</b>\n\n"
            f"🆔 <b>Order ID:</b> <code>{html.escape(order_id)}</code>\n"
            f"✨ <b>Item:</b> {html.escape(title)}\n"
            f"💰 <b>Amount:</b> <b>₹{price}</b>\n"
            f"{upi_line}\n"
            f"📝 {html.escape(qr_note)}"
        )
        qr_kb = build_qr_buttons(order_id)

        try:
            await query.message.reply_photo(
                photo=qr_media,
                caption=qr_caption,
                parse_mode="HTML",
                reply_markup=qr_kb,
                protect_content=True,
            )
        except Exception as e:
            logger.warning(f"QR photo fallback: {e}")
            await query.message.reply_text(
                text=qr_caption,
                parse_mode="HTML",
                reply_markup=qr_kb,
                protect_content=True,
            )
        return

    # Check payment -> notify admin
    if data.startswith("check_pay:"):
        order_id = data.split(":", 1)[1].strip()
        orders_store: dict = context.bot_data.get("orders") or {}
        order = orders_store.get(order_id) or {
            "order_id": order_id,
            "user_id": caller.id,
            "chat_id": chat_id,
            "full_name": caller.full_name,
            "username": caller.username or "Not set",
            "title": "Selected Item",
            "price": 199,
        }

        uname = (
            f"@{html.escape(str(order['username']))}"
            if order.get("username") and order.get("username") != "Not set"
            else "Not set"
        )
        safe_name = html.escape(str(order.get("full_name") or "Member"))

        if ADMIN_ID != 0:
            admin_notice = (
                f"🔔 <b>PAYMENT CHECK REQUEST</b>\n\n"
                f"👤 <b>Member:</b> {safe_name}\n"
                f"🌐 <b>Username:</b> {uname}\n"
                f"🆔 <b>User ID:</b> <code>{order['user_id']}</code>\n"
                f"💬 <b>Chat ID:</b> <code>{order['chat_id']}</code>\n"
                f"🧾 <b>Order ID:</b> <code>{html.escape(order_id)}</code>\n"
                f"✨ <b>Item:</b> {html.escape(str(order['title']))}\n"
                f"💰 <b>Amount:</b> <b>₹{order['price']}</b>"
            )
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=admin_notice,
                    parse_mode="HTML",
                    protect_content=True,
                )
            except Exception as e:
                logger.error(f"Failed notifying ADMIN_ID {ADMIN_ID}: {e}")

        await query.message.reply_text(
            f"✅ <b>Payment Check Sent</b>\n\n"
            f"Order ID: <code>{html.escape(order_id)}</code>\n"
            f"Amount: <b>₹{order['price']}</b>\n\n"
            f"Your payment check request has been sent to the admin.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                [[make_styled_button("🔙 Back", "go_back", "primary")]]
            ),
            protect_content=True,
        )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception:", exc_info=context.error)


async def post_init(application: Application) -> None:
    # Sabhi normal users ke liye sirf /start command
    await application.bot.set_my_commands(
        [BotCommand("start", "Start menu")],
        scope=BotCommandScopeDefault(),
    )

    # Admin command sirf ADMIN_ID ke chat mein
    if ADMIN_ID != 0:
        try:
            await application.bot.set_my_commands(
                [
                    BotCommand("start", "Start menu"),
                    BotCommand("admin", "Admin panel"),
                ],
                scope=BotCommandScopeChat(chat_id=ADMIN_ID),
            )
        except Exception as e:
            logger.debug(f"Admin command scope setup skipped: {e}")


def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN missing!")

    start_24x7_server(PORT)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_admin_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(CallbackQueryHandler(on_button_click))
    app.add_error_handler(error_handler)

    logger.info("Protected Store Bot running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
