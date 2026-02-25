from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

# ================= CONFIG =================
BOT_TOKEN = "8595786501:AAEufg71y0PZ_zf8_NQfzHEBSxfUaJIECfk"

ADMIN_IDS = [ 6587658540, 7691071175]

GROUPS = {
    "market": {"name": "📢 Market Forums", "id": -1003692774580},
    "chat": {"name": "💬 Chat GC", "id": -1003382668169}
}

SELECT_GROUP, WRITE_REASON = range(2)

user_group_map = {}
pending_appeals = {}
# Structure: pending_appeals[user_id] = {"group": group_key, "type": "ban"/"mute"}

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id in pending_appeals:
        await update.message.reply_text(
            "⏳ *Your appeal is already under review.*\n❗ Please wait for admin decision.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("📢 Market Forums", callback_data="market")],
        [InlineKeyboardButton("💬 Chat GC", callback_data="chat")]
    ]

    await update.message.reply_text(
        "👋 *Welcome to Appeal Bot*\n📌 Please select the group you want to appeal from:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return SELECT_GROUP

# ================= GROUP SELECT =================
async def group_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    group_key = query.data
    group = GROUPS[group_key]

    if user_id in pending_appeals:
        await query.edit_message_text("⏳ *Your appeal is already pending review.*", parse_mode="Markdown")
        return ConversationHandler.END

    status_type = None
    try:
        member = await context.bot.get_chat_member(group["id"], user_id)
        if member.status == "kicked":
            status_type = "ban"
        elif member.can_send_messages is False:
            status_type = "mute"
    except:
        # Probably banned or muted, proceed
        pass

    if not status_type:
        await query.edit_message_text("✅ *You are neither banned nor muted in this group.*", parse_mode="Markdown")
        return ConversationHandler.END

    user_group_map[user_id] = {"group": group_key, "type": status_type}

    await query.edit_message_text(
        f"🚫 *{status_type.upper()} Detected*\n📢 Group: *{group['name']}*\n📝 Please write your appeal reason:",
        parse_mode="Markdown"
    )
    return WRITE_REASON

# ================= APPEAL TEXT =================
async def appeal_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    reason = update.message.text
    user_id = user.id

    info = user_group_map.get(user_id)
    group_key = info["group"]
    status_type = info["type"]
    group = GROUPS[group_key]

    username = user.username or "NoUsername"
    pending_appeals[user_id] = {"group": group_key, "type": status_type}

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}_{group_key}_{status_type}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")
        ]
    ])

    text = (
        "📩 NEW APPEAL RECEIVED\n\n"
        f"👤 User: @{username}\n"
        f"🆔 ID: {user_id}\n"
        f"📢 Group: {group['name']}\n"
        f"⚠️ Type: {status_type.upper()}\n\n"
        "📝 Reason:\n"
        f"{reason}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text, reply_markup=buttons)
        except:
            pass

    await update.message.reply_text(
        "✅ *Appeal Submitted Successfully!*\n⏳ Your appeal is under admin review.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ================= ADMIN DECISION =================
async def decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data.split("_")
    action = data[0]
    user_id = int(data[1])

    info = pending_appeals.pop(user_id, None)
    if not info:
        await query.edit_message_text("⚠️ This appeal is no longer valid.")
        return

    group_key = info["group"]
    status_type = info["type"]
    group = GROUPS[group_key]
    username = None

    if action == "approve":
        try:
            if status_type == "ban":
                await context.bot.unban_chat_member(group["id"], user_id)
            elif status_type == "mute":
                await context.bot.restrict_chat_member(
                    group["id"], user_id, permissions=None
                )
            # Notify user
            await context.bot.send_message(
                user_id,
                f"🎉 *Appeal Approved!*\n"
                f"✅ You have been {('unbanned' if status_type=='ban' else 'unmuted')} from *{group['name']}*.",
                parse_mode="Markdown"
            )
        except:
            pass

        # Send message to group
        try:
            member = await context.bot.get_chat_member(group["id"], user_id)
            username = member.user.username or "NoUsername"
        except:
            username = "NoUsername"

        await context.bot.send_message(
            group["id"],
            f"👤 @{username} | ID: {user_id} has been "
            f"{'unbanned' if status_type=='ban' else 'unmuted'}."
        )

        await query.edit_message_text(f"✅ Appeal Approved & User {status_type} lifted")

    else:
        try:
            await context.bot.send_message(
                user_id,
                "❌ *Appeal Rejected*\nAdmin has rejected your appeal.",
                parse_mode="Markdown"
            )
        except:
            pass

        await query.edit_message_text("❌ Appeal Rejected")

# ================= APP =================
app = Application.builder().token(BOT_TOKEN).build()

conv = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        SELECT_GROUP: [CallbackQueryHandler(group_select)],
        WRITE_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, appeal_reason)]
    },
    fallbacks=[]
)

app.add_handler(conv)
app.add_handler(CallbackQueryHandler(decision))

app.run_polling()
