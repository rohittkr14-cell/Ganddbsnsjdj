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
from telegram.constants import ParseMode
import logging
import html
import json
import os

# ================= LOGGING =================
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("telegram").setLevel(logging.ERROR)

# ================= CONFIG =================
BOT_TOKEN = "8360710143:AAEeJFu2KJ1iF27-5FKrQBQz0TKvx4RA8TA"

ADMIN_IDS = [6587658540, 7691071175]

GROUPS = {
    "chatting": {
        "button": "💬 Chatting",
        "name": "💬 Chatting",
        "id": -1003730637965,
        "link": "https://t.me/frmchating"
    },
    "foruming": {
        "button": "🌾 Foruming",
        "name": "🌾 Foruming",
        "id": -1003726011915,  # <-- YAHAN FORUMING GROUP ID DALO
        "link": "https://t.me/frmhub"  # <-- YAHAN FORUMING GROUP LINK DALO
    }
}

WRITE_REASON = 0
DATA_FILE = "pending_appeals.json"

# KEY = "user_id:group_key"
pending_appeals = {}

# ================= KEYBOARD =================
main_keyboard = ReplyKeyboardMarkup(
    [
        ["💬 Chatting", "🌾 Foruming"]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# ================= HELPERS =================
def safe(text):
    return html.escape(str(text)) if text else "N/A"

def get_group_by_button(button_text):
    for key, group in GROUPS.items():
        if group["button"] == button_text:
            return key, group
    return None, None

def appeal_key(user_id: int, group_key: str):
    return f"{user_id}:{group_key}"

def save_pending():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(pending_appeals, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[SAVE ERROR] {e}")

def load_pending():
    global pending_appeals
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                pending_appeals = json.load(f)
        except Exception as e:
            print(f"[LOAD ERROR] {e}")
            pending_appeals = {}
    else:
        pending_appeals = {}

def has_pending_in_group(user_id: int, group_key: str):
    return appeal_key(user_id, group_key) in pending_appeals

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 <b>WELCOME TO THE APPEAL BOT</b>\n\n"
        "<b>SELECT THE GROUP BELOW TO SUBMIT YOUR APPEAL.</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard
    )
    return ConversationHandler.END

# ================= CHECK STATUS =================
async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE, selected_group_key: str):
    user_id = update.effective_user.id
    group = GROUPS[selected_group_key]

    # SAME GROUP pending check only
    if has_pending_in_group(user_id, selected_group_key):
        await update.message.reply_text(
            f"⏳ <b>YOUR APPEAL FOR {safe(group['name'])} IS ALREADY UNDER REVIEW.</b>\n"
            f"<b>WAIT FOR ADMIN RESPONSE BEFORE SENDING ANOTHER APPEAL FOR THIS GROUP.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard
        )
        return ConversationHandler.END

    status_type = None

    try:
        member = await context.bot.get_chat_member(group["id"], user_id)

        if member.status == "kicked":
            status_type = "ban"

        elif member.status == "restricted":
            status_type = "mute"

        elif getattr(member, "can_send_messages", True) is False:
            status_type = "mute"

    except Exception:
        # Agar member fetch fail hua, usually banned/inaccessible ho sakta hai
        status_type = "ban"

    if not status_type:
        await update.message.reply_text(
            f"✅ <b>YOU ARE NOT BANNED OR MUTED/RESTRICTED IN {safe(group['name'])}.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard
        )
        return ConversationHandler.END

    context.user_data["status_type"] = status_type
    context.user_data["group_key"] = selected_group_key

    await update.message.reply_text(
        f"🚫 <b>{safe(status_type.upper())} DETECTED</b>\n"
        f"📢 <b>GROUP:</b> {safe(group['name'])}\n\n"
        f"📝 <b>PLEASE SEND YOUR APPEAL REASON.</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard
    )
    return WRITE_REASON

# ================= BUTTON HANDLER =================
async def group_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    group_key, _ = get_group_by_button(text)

    if not group_key:
        await update.message.reply_text(
            "❌ <b>INVALID OPTION.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard
        )
        return ConversationHandler.END

    return await check_status(update, context, group_key)

# ================= APPEAL TEXT =================
async def appeal_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reason = update.message.text.strip()
    user_id = user.id

    # If user presses button again while in reason mode
    if reason in [GROUPS["chatting"]["button"], GROUPS["foruming"]["button"]]:
        group_key, _ = get_group_by_button(reason)
        return await check_status(update, context, group_key)

    status_type = context.user_data.get("status_type")
    group_key = context.user_data.get("group_key")

    if not status_type or not group_key:
        await update.message.reply_text(
            "❌ <b>SESSION EXPIRED.</b>\n"
            "<b>PLEASE PRESS A BUTTON OR USE /start AGAIN.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard
        )
        return ConversationHandler.END

    group = GROUPS[group_key]
    key = appeal_key(user_id, group_key)

    # Double safety same-group check
    if key in pending_appeals:
        await update.message.reply_text(
            f"⏳ <b>YOUR APPEAL FOR {safe(group['name'])} IS ALREADY UNDER REVIEW.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard
        )
        return ConversationHandler.END

    username = user.username or "NoUsername"
    full_name = user.full_name or "Unknown"

    pending_appeals[key] = {
        "user_id": user_id,
        "type": status_type,
        "group_key": group_key,
        "reason": reason,
        "username": username,
        "full_name": full_name
    }
    save_pending()

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve|{user_id}|{group_key}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject|{user_id}|{group_key}")
        ]
    ])

    text = (
        f"📩 <b>NEW APPEAL RECEIVED</b>\n\n"
        f"👤 <b>USER:</b> {safe(full_name)}\n"
        f"🔗 <b>USERNAME:</b> @{safe(username)}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"📢 <b>GROUP:</b> {safe(group['name'])}\n"
        f"⚠️ <b>TYPE:</b> {safe(status_type.upper())}\n\n"
        f"📝 <b>REASON:</b>\n{safe(reason)}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=buttons
            )
        except Exception:
            pass

    await update.message.reply_text(
        f"✅ <b>APPEAL FOR {safe(group['name'])} SUBMITTED SUCCESSFULLY.</b>\n"
        f"⏳ <b>PLEASE WAIT WHILE ADMINS REVIEW IT.</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard
    )

    context.user_data.pop("status_type", None)
    context.user_data.pop("group_key", None)
    return ConversationHandler.END

# ================= ADMIN DECISION =================
async def decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    admin_id = query.from_user.id
    if admin_id not in ADMIN_IDS:
        await query.answer("Unauthorized access.", show_alert=True)
        return

    try:
        action, user_id_str, group_key = query.data.split("|")
        target_user_id = int(user_id_str)
    except Exception:
        await query.answer("Invalid action data.", show_alert=True)
        return

    key = appeal_key(target_user_id, group_key)
    info = pending_appeals.pop(key, None)

    if not info:
        await query.answer("Appeal already handled or expired.", show_alert=True)
        try:
            await query.edit_message_text(
                "⚠️ <b>APPEAL ALREADY HANDLED OR EXPIRED.</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        return

    save_pending()

    status_type = info["type"]
    username = info.get("username", "user")
    group = GROUPS[group_key]

    if action == "approve":
        try:
            # ========== UNBAN ==========
            if status_type == "ban":
                await context.bot.unban_chat_member(
                    chat_id=group["id"],
                    user_id=target_user_id,
                    only_if_banned=True
                )

            # ========== UNMUTE ==========
            elif status_type == "mute":
                await context.bot.restrict_chat_member(
                    chat_id=group["id"],
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

            # ========== USER DM ==========
            try:
                user_button = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"🔗 Open {group['name']}", url=group["link"])]
                ])

                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=(
                        f"🎉 <b>APPEAL APPROVED!</b>\n\n"
                        f"<b>YOU HAVE BEEN "
                        f"{'UNBANNED' if status_type == 'ban' else 'UNMUTED'} "
                        f"FROM {safe(group['name'])}.</b>\n\n"
                        f"🔗 <b>GROUP LINK BELOW:</b>"
                    ),
                    parse_mode=ParseMode.HTML,
                    reply_markup=user_button,
                    disable_web_page_preview=True
                )
            except Exception:
                pass

            # ========== GROUP LOG ==========
            try:
                await context.bot.send_message(
                    group["id"],
                    f"👤 <b>@{safe(username)}</b> | <b>ID:</b> <code>{target_user_id}</code> "
                    f"<b>HAS BEEN "
                    f"{'UNBANNED' if status_type == 'ban' else 'UNMUTED'}.</b>",
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass

            await query.edit_message_text(
                f"✅ <b>APPEAL APPROVED.</b>\n"
                f"👤 <b>USER ID:</b> <code>{target_user_id}</code>\n"
                f"📢 <b>GROUP:</b> {safe(group['name'])}\n"
                f"⚠️ <b>ACTION:</b> {'UNBANNED' if status_type == 'ban' else 'UNMUTED'}",
                parse_mode=ParseMode.HTML
            )

        except Exception as e:
            # Restore if approve failed
            pending_appeals[key] = info
            save_pending()

            await query.edit_message_text(
                f"❌ <b>FAILED TO APPROVE.</b>\n"
                f"<b>ERROR:</b> <code>{safe(e)}</code>",
                parse_mode=ParseMode.HTML
            )

    elif action == "reject":
        try:
            await context.bot.send_message(
                chat_id=target_user_id,
                text=(
                    f"❌ <b>YOUR APPEAL FOR {safe(group['name'])} HAS BEEN REJECTED.</b>"
                ),
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass

        await query.edit_message_text(
            f"❌ <b>APPEAL REJECTED.</b>\n"
            f"👤 <b>USER ID:</b> <code>{target_user_id}</code>\n"
            f"📢 <b>GROUP:</b> {safe(group['name'])}",
            parse_mode=ParseMode.HTML
        )

# ================= ADMIN COMMANDS =================
async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        return

    if not pending_appeals:
        await update.message.reply_text(
            "✅ <b>NO PENDING APPEALS.</b>",
            parse_mode=ParseMode.HTML
        )
        return

    lines = ["📋 <b>PENDING APPEALS:</b>\n"]

    count = 0
    for _, info in pending_appeals.items():
        uid = info.get("user_id", "Unknown")
        group_name = GROUPS.get(info.get("group_key", ""), {}).get("name", "Unknown")

        lines.append(
            f"👤 <b>ID:</b> <code>{uid}</code>\n"
            f"📢 <b>GROUP:</b> {safe(group_name)}\n"
            f"⚠️ <b>TYPE:</b> {safe(info.get('type', 'unknown').upper())}\n"
            f"🔗 <b>USERNAME:</b> @{safe(info.get('username', 'NoUsername'))}\n"
        )

        count += 1
        if count >= 15:
            break

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML
    )

# ================= APP =================
def main():
    load_pending()

    application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^(💬 Chatting|🌾 Foruming)$"), group_button)
        ],
        states={
            WRITE_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, appeal_reason)
            ]
        },
        fallbacks=[],
        per_user=True,
        per_chat=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("pending", pending_command))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(decision, pattern=r"^(approve|reject)\|"))

    print("🚀 Appeal Bot Started - Dual Group Persistent Smooth Mode")
    application.run_polling(
        drop_pending_updates=True,
        poll_interval=0.1,
        timeout=10,
        bootstrap_retries=-1,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == "__main__":
    main()