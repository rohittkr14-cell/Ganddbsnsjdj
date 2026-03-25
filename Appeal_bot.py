from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ChatPermissions
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

# ================= LOGGING =================
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("telegram").setLevel(logging.ERROR)

# ================= CONFIG =================
BOT_TOKEN = "8703011204:AAE6bhpuAAI-4FbSnxGiejLLOkPO0QAICVA"

ADMIN_IDS = [6587658540, 7691071175]

GROUP = {
    "name": "💬 E Chat",
    "id": -1003730637965,
    "link": "https://t.me/frmchating"
}

WRITE_REASON = 0
pending_appeals = {}

# ================= KEYBOARD =================
main_keyboard = ReplyKeyboardMarkup(
    [["💬 E Chat"]],
    resize_keyboard=True,
    one_time_keyboard=False
)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    await update.message.reply_text(
        "👋 *WELCOME TO THE APPEAL BOT*\n\n"
        "*USE THE BUTTON BELOW TO SUBMIT YOUR APPEAL FOR THE GROUP.*",
        parse_mode="Markdown",
        reply_markup=main_keyboard
    )

    if user_id in pending_appeals:
        await update.message.reply_text(
            "⏳ *YOUR APPEAL IS ALREADY UNDER REVIEW.*\n"
            "*PLEASE WAIT FOR AN ADMIN DECISION.*",
            parse_mode="Markdown",
            reply_markup=main_keyboard
        )
        return ConversationHandler.END

# ================= CHECK STATUS =================
async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id in pending_appeals:
        await update.message.reply_text(
            "⏳ *YOUR APPEAL IS ALREADY UNDER REVIEW.*\n"
            "*PLEASE WAIT FOR AN ADMIN DECISION.*",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    status_type = None

    try:
        member = await context.bot.get_chat_member(GROUP["id"], user_id)

        # Ban detect
        if member.status == "kicked":
            status_type = "ban"

        # Restricted / mute detect
        elif member.status == "restricted":
            status_type = "mute"

        elif getattr(member, "can_send_messages", True) is False:
            status_type = "mute"

    except:
        pass

    if not status_type:
        await update.message.reply_text(
            "✅ *YOU ARE NOT BANNED OR MUTED/RESTRICTED IN THIS GROUP.*",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    context.user_data["status_type"] = status_type

    await update.message.reply_text(
        f"🚫 *{status_type.upper()} DETECTED*\n"
        f"📢 *GROUP:* *{GROUP['name']}*\n\n"
        f"📝 *PLEASE SEND YOUR APPEAL REASON.*",
        parse_mode="Markdown"
    )
    return WRITE_REASON

# ================= KEYBOARD BUTTON =================
async def echat_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await check_status(update, context)

# ================= APPEAL TEXT =================
async def appeal_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    reason = update.message.text
    user_id = user.id

    if reason == "💬 E Chat":
        return await check_status(update, context)

    status_type = context.user_data.get("status_type")
    if not status_type:
        await update.message.reply_text(
            "❌ *SESSION EXPIRED.*\n"
            "*PLEASE PRESS 💬 E CHAT OR USE /start AGAIN.*",
            parse_mode="Markdown",
            reply_markup=main_keyboard
        )
        return ConversationHandler.END

    username = user.username or "NoUsername"
    full_name = user.full_name or "Unknown"

    pending_appeals[user_id] = {"type": status_type}

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user_id}_{status_type}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user_id}")
        ]
    ])

    text = (
        f"📩 *NEW APPEAL RECEIVED*\n\n"
        f"👤 *USER:* {full_name}\n"
        f"🔗 *USERNAME:* @{username}\n"
        f"🆔 *ID:* `{user_id}`\n"
        f"📢 *GROUP:* {GROUP['name']}\n"
        f"⚠️ *TYPE:* {status_type.upper()}\n\n"
        f"📝 *REASON:*\n{reason}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=buttons
            )
        except:
            pass

    await update.message.reply_text(
        "✅ *APPEAL SUBMITTED SUCCESSFULLY.*\n"
        "⏳ *PLEASE WAIT WHILE ADMINS REVIEW IT.*",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

# ================= ADMIN DECISION =================
async def decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    admin_id = query.from_user.id
    if admin_id not in ADMIN_IDS:
        await query.answer("Unauthorized access.", show_alert=True)
        return

    data = query.data.split("_")
    action = data[0]
    target_user_id = int(data[1])

    info = pending_appeals.pop(target_user_id, None)
    if not info:
        await query.answer("Appeal already handled or expired.", show_alert=True)
        try:
            await query.edit_message_text(
                "⚠️ *APPEAL ALREADY HANDLED OR EXPIRED.*",
                parse_mode="Markdown"
            )
        except:
            pass
        return

    status_type = info["type"]

    if action == "approve":
        try:
            # ================= UNBAN =================
            if status_type == "ban":
                await context.bot.unban_chat_member(
                    chat_id=GROUP["id"],
                    user_id=target_user_id,
                    only_if_banned=True
                )

            # ================= UNMUTE / REMOVE RESTRICTIONS =================
            elif status_type == "mute":
                await context.bot.restrict_chat_member(
                    chat_id=GROUP["id"],
                    user_id=target_user_id,
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_audios=True,
                        can_send_documents=True,
                        can_send_photos=True,
                        can_send_videos=True,
                        can_send_video_notes=True,
                        can_send_voice_notes=True,
                        can_send_polls=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True,
                        can_change_info=False,
                        can_invite_users=True,
                        can_pin_messages=False,
                        can_manage_topics=False
                    )
                )

            # ================= USER DM =================
            try:
                user_button = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Open E Chat", url=GROUP["link"])]
                ])

                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=(
                        f"🎉 *APPEAL APPROVED!*\n\n"
                        f"*YOU HAVE BEEN {'UNBANNED' if status_type == 'ban' else 'UNMUTED'} FROM {GROUP['name']}.*\n\n"
                        f"🔗 *GROUP LINK BELOW:*"
                    ),
                    parse_mode="Markdown",
                    reply_markup=user_button,
                    disable_web_page_preview=True
                )
            except:
                pass

            # ================= GROUP LOG =================
            try:
                member = await context.bot.get_chat_member(GROUP["id"], target_user_id)
                username = member.user.username or "user"
                await context.bot.send_message(
                    GROUP["id"],
                    f"👤 *@{username}* | *ID:* `{target_user_id}` *HAS BEEN "
                    f"{'UNBANNED' if status_type == 'ban' else 'UNMUTED'}.*",
                    parse_mode="Markdown"
                )
            except:
                pass

            await query.edit_message_text(
                f"✅ *APPEAL APPROVED.*\n"
                f"*USER HAS BEEN {'UNBANNED' if status_type == 'ban' else 'UNMUTED'}.*",
                parse_mode="Markdown"
            )

        except Exception as e:
            await query.edit_message_text(
                f"❌ *FAILED TO APPROVE.*\n*ERROR:* `{e}`",
                parse_mode="Markdown"
            )

    else:
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text="❌ *YOUR APPEAL HAS BEEN REJECTED.*",
                parse_mode="Markdown"
            )
        except:
            pass

        await query.edit_message_text(
            "❌ *APPEAL REJECTED.*",
            parse_mode="Markdown"
        )

# ================= APP =================
def main():
    application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💬 E Chat$"), echat_button)
        ],
        states={
            WRITE_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, appeal_reason)]
        },
        fallbacks=[],
        per_user=True,
        per_chat=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(decision, pattern="^(approve_|reject_)"))

    print("🚀 Appeal Bot Started - Final Smooth Mode")
    application.run_polling(
        drop_pending_updates=True,
        poll_interval=0.1,
        timeout=10,
        bootstrap_retries=-1,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == "__main__":
    main()