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
import logging

# ================= LOGGING (Silent for speed) =================
logging.basicConfig(
    level=logging.ERROR,  # Only errors, no warnings/info
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("telegram").setLevel(logging.ERROR)

# ================= CONFIG =================
BOT_TOKEN = "8595786501:AAEufg71y0PZ_zf8_NQfzHEBSxfUaJIECfk"

ADMIN_IDS = [6587658540, 7691071175, 8552395485]

GROUPS = {
    "market": {"name": "📢 Market Forums", "id": -1003692774580},
    "chat": {"name": "💬 Chat GC", "id": -1003382668169}
}

SELECT_GROUP, WRITE_REASON = range(2)

user_group_map = {}
pending_appeals = {}

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
        await query.edit_message_text("⏳ *Your appeal is already pending in review.*")
        return ConversationHandler.END

    status_type = None
    try:
        member = await context.bot.get_chat_member(group["id"], user_id)
        if member.status == "kicked":
            status_type = "ban"
        elif member.can_send_messages is False:
            status_type = "mute"
    except:
        pass

    if not status_type:
        await query.edit_message_text("✅ *You are neither banned nor muted in this group.*")
        return ConversationHandler.END

    user_group_map[user_id] = {"group": group_key, "type": status_type}
    await query.edit_message_text(
        f"🚫 *{status_type.upper()} Detected*\n📢 Group: *{group['name']}*\n📝 Please write your appeal reason:"
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
        f"📩 NEW APPEAL RECEIVED\n\n"
        f"👤 User: @{username}\n"
        f"🆔 ID: {user_id}\n"
        f"📢 Group: {group['name']}\n"
        f"⚠️ Type: {status_type.upper()}\n\n"
        f"📝 Reason:\n{reason}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text, reply_markup=buttons)
        except:
            pass

    await update.message.reply_text(
        "✅ *Appeal Submitted Successfully!*\n⏳ Your appeal is under admin review."
    )
    return ConversationHandler.END

# ================= ADMIN DECISION =================
async def decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if user_id not in ADMIN_IDS:
        await query.answer("❌ Unauthorized", show_alert=True)
        return

    data = query.data.split("_")
    action = data[0]
    target_user_id = int(data[1])

    info = pending_appeals.pop(target_user_id, None)
    if not info:
        await query.edit_message_text("⚠️ Appeal expired")
        return

    group_key = info["group"]
    status_type = info["type"]
    group = GROUPS[group_key]

    if action == "approve":
        try:
            if status_type == "ban":
                await context.bot.unban_chat_member(group["id"], target_user_id)
            else:
                await context.bot.restrict_chat_member(group["id"], target_user_id, permissions=None)
                
            await context.bot.send_message(
                target_user_id,
                f"🎉 *Appeal Approved!*\n✅ You have been {('unbanned' if status_type=='ban' else 'unmuted')} from *{group['name']}*."
            )
            
            username = "user"
            try:
                member = await context.bot.get_chat_member(group["id"], target_user_id)
                username = member.user.username or "user"
                await context.bot.send_message(
                    group["id"],
                    f"👤 @{username} | ID: {target_user_id} has been {'unbanned' if status_type=='ban' else 'unmuted'}."
                )
            except:
                pass
                
        except:
            pass

        await query.edit_message_text(f"✅ Approved - {status_type} lifted")
    else:
        try:
            await context.bot.send_message(target_user_id, "❌ *Appeal Rejected*")
        except:
            pass
        await query.edit_message_text("❌ Rejected")

# ================= APP (Pydroid3 + AWS Compatible) =================
def main():
    application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_GROUP: [CallbackQueryHandler(group_select, pattern="^(market|chat)$")],
            WRITE_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, appeal_reason)]
        },
        fallbacks=[],
        per_user=True,
        per_chat=True  # Extra safety for AWS
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(decision, pattern="^(approve_|reject_)"))

    print("🚀 Appeal Bot Started - Pydroid3 & AWS Ready!")
    application.run_polling(
        drop_pending_updates=True,
        poll_interval=0.1,  # Ultra fast polling
        timeout=10,
        bootstrap_retries=-1  # Never stop
    )

if __name__ == "__main__":
    main()
