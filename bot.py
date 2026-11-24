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
