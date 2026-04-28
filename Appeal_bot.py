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
import re

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

AVOID_HARM_CHANNEL = {
    "button": "🚫 Avoid Harm",
    "name": "🚫 Avoid Harm",
    "id": -1003344628533,  # <-- YAHAN CHANNEL ID DALO
    "link": "https://t.me/avoidharm"  # <-- YAHAN CHANNEL LINK DALO
}

GROUPS = {
    "chatting": {
        "button": "💬 Chatting",
        "name": "💬 Chatting",
        "id": -1003730637965,
        "link": "https://t.me/frmchating"
    }
}

WRITE_REASON = 0
ASK_POST_LINK = 1
ASK_EXPLANATION = 2

DATA_FILE = "pending_appeals.json"
post_link_pattern = re.compile(r'https?://t\.me/(?:c/)?[\w_]+/\d+')

pending_appeals = {}

main_keyboard = ReplyKeyboardMarkup(
    [
        ["💬 Chatting", "🚫 Avoid Harm"]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

def safe(text):
    return html.escape(str(text)) if text else "N/A"

def get_group_by_button(button_text):
    if button_text == GROUPS["chatting"]["button"]:
        return "chatting", GROUPS["chatting"]
    if button_text == AVOID_HARM_CHANNEL["button"]:
        return "avoid_harm", AVOID_HARM_CHANNEL
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

# ================= CHECK STATUS (for Chatting - SAME AS ORIGINAL) =================
async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE, selected_group_key: str):
    user_id = update.effective_user.id
    group = GROUPS[selected_group_key]

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
    group_key, group_info = get_group_by_button(text)

    if not group_key:
        await update.message.reply_text(
            "❌ <b>INVALID OPTION.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard
        )
        return ConversationHandler.END

    if group_key == "avoid_harm":
        await update.message.reply_text(
            "🔗 <b>PLEASE SEND THE POST LINK</b>\n\n"
            "<b>FOR EXAMPLE:</b>\n"
            "<code>https://t.me/username/1234</code>\n"
            "<code>https://t.me/c/123456789/1234</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard
        )
        return ASK_POST_LINK

    return await check_status(update, context, group_key)

# ================= AVOID HARM - POST LINK =================
async def handle_post_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    user_id = user.id

    group_key, _ = get_group_by_button(text)
    if group_key:
        return await group_button(update, context)

    if not post_link_pattern.match(text):
        await update.message.reply_text(
            "❌ <b>INVALID POST LINK.</b>\n\n"
            "<b>PLEASE SEND A VALID TELEGRAM POST LINK:</b>\n"
            "<code>https://t.me/username/1234</code>\n"
            "<code>https://t.me/c/123456789/1234</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard
        )
        return ASK_POST_LINK

    key = appeal_key(user_id, "avoid_harm")
    if key in pending_appeals:
        await update.message.reply_text(
            "⏳ <b>YOUR AVOID HARM REPORT IS ALREADY UNDER REVIEW.</b>\n"
            "<b>WAIT FOR ADMIN RESPONSE BEFORE SENDING ANOTHER REPORT.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard
        )
        return ConversationHandler.END

    context.user_data["post_link"] = text
    context.user_data["group_key"] = "avoid_harm"

    await update.message.reply_text(
        "📝 <b>PLEASE EXPLAIN WHY THIS POST IS HARMFUL/FAKE/SPAM.</b>\n\n"
        "<b>PROVIDE A CLEAR EXPLANATION.</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard
    )
    return ASK_EXPLANATION

# ================= AVOID HARM - EXPLANATION =================
async def handle_explanation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user = update.effective_user
    user_id = user.id

    group_key, _ = get_group_by_button(text)
    if group_key:
        return await group_button(update, context)

    post_link = context.user_data.get("post_link")
    if not post_link:
        await update.message.reply_text(
            "❌ <b>SESSION EXPIRED.</b>\n"
            "<b>PLEASE USE /start AGAIN.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard
        )
        return ConversationHandler.END

    key = appeal_key(user_id, "avoid_harm")
    if key in pending_appeals:
        await update.message.reply_text(
            "⏳ <b>YOUR AVOID HARM REPORT IS ALREADY UNDER REVIEW.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard
        )
        return ConversationHandler.END

    username = user.username or "NoUsername"
    full_name = user.full_name or "Unknown"

    pending_appeals[key] = {
        "user_id": user_id,
        "type": "avoid_harm",
        "group_key": "avoid_harm",
        "post_link": post_link,
        "reason": text,
        "username": username,
        "full_name": full_name
    }
    save_pending()

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve|{user_id}|avoid_harm"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject|{user_id}|avoid_harm")
        ]
    ])

    report_text = (
        f"🚫 <b>NEW AVOID HARM REPORT</b>\n\n"
        f"👤 <b>REPORTED BY:</b> {safe(full_name)}\n"
        f"🔗 <b>USERNAME:</b> @{safe(username)}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"🔗 <b>POST LINK:</b> {safe(post_link)}\n\n"
        f"📝 <b>EXPLANATION:</b>\n{safe(text)}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=report_text,
                parse_mode=ParseMode.HTML,
                reply_markup=buttons
            )
        except Exception:
            pass

    await update.message.reply_text(
        "✅ <b>YOUR REPORT HAS BEEN SUBMITTED SUCCESSFULLY.</b>\n"
        "⏳ <b>PLEASE WAIT WHILE ADMINS REVIEW IT.</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard
    )

    context.user_data.pop("post_link", None)
    context.user_data.pop("group_key", None)
    return ConversationHandler.END
    # ================= APPEAL REASON (Chatting - SAME AS ORIGINAL) =================
async def appeal_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reason = update.message.text.strip()
    user_id = user.id

    group_key, _ = get_group_by_button(reason)
    if group_key:
        context.user_data.pop("status_type", None)
        context.user_data.pop("group_key", None)
        return await group_button(update, context)

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

# ================= PARSE TELEGRAM POST LINK =================
def parse_telegram_post(post_link: str):
    try:
        match = re.search(r't\.me/c/(\d+)/(\d+)', post_link)
        if match:
            return int(match.group(1)), int(match.group(2))
        match = re.search(r't\.me/([^/]+)/(\d+)', post_link)
        if match:
            return match.group(1), int(match.group(2))
    except Exception:
        pass
    return None, None

# ================= ADMIN DECISION =================
async def decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    admin_id = query.from_user.id
    if admin_id not in ADMIN_IDS:
        await query.answer("🚫 UNAUTHORIZED ACCESS.", show_alert=True)
        return

    try:
        action, user_id_str, group_key = query.data.split("|")
        target_user_id = int(user_id_str)
    except Exception:
        await query.answer("❌ INVALID ACTION DATA.", show_alert=True)
        return

    key = appeal_key(target_user_id, group_key)
    info = pending_appeals.pop(key, None)

    if not info:
        await query.answer("⚠️ REPORT ALREADY HANDLED.", show_alert=True)
        try:
            await query.edit_message_text(
                "⚠️ <b>REPORT ALREADY HANDLED OR EXPIRED.</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        return

    save_pending()

    # ========== AVOID HARM ==========
    if group_key == "avoid_harm":
        if action == "approve":
            try:
                post_link = info.get("post_link", "")
                identifier, message_id = parse_telegram_post(post_link)
                deleted = False

                if message_id:
                    try:
                        await context.bot.delete_message(
                            chat_id=AVOID_HARM_CHANNEL["id"],
                            message_id=message_id
                        )
                        deleted = True
                    except Exception:
                        if isinstance(identifier, str):
                            try:
                                await context.bot.delete_message(
                                    chat_id=f"@{identifier}",
                                    message_id=message_id
                                )
                                deleted = True
                            except Exception:
                                pass

                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=(
                            f"✅ <b>YOUR AVOID HARM REPORT HAS BEEN APPROVED.</b>\n\n"
                            f"🔗 <b>POST:</b> {safe(post_link)}\n"
                            f"📋 <b>STATUS:</b> POST HAS BEEN REMOVED ✅"
                        ),
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                except Exception:
                    pass

                status_text = "POST DELETED ✅" if deleted else "POST COULD NOT BE DELETED (CHECK BOT PERMISSIONS) ⚠️"

                await query.edit_message_text(
                    f"✅ <b>REPORT APPROVED.</b>\n"
                    f"👤 <b>USER ID:</b> <code>{target_user_id}</code>\n"
                    f"🔗 <b>POST:</b> {safe(post_link)}\n"
                    f"📋 <b>STATUS:</b> {status_text}",
                    parse_mode=ParseMode.HTML
                )

            except Exception as e:
                pending_appeals[key] = info
                save_pending()
                await query.edit_message_text(
                    f"❌ <b>FAILED TO APPROVE.</b>\n"
                    f"<b>ERROR:</b> <code>{safe(e)}</code>",
                    parse_mode=ParseMode.HTML
                )

        elif action == "reject":
            # Store reject info in pending_appeals temporarily with a flag
            key_reject = f"reject_waiting:{target_user_id}"
            pending_appeals[key_reject] = {
                "user_id": target_user_id,
                "post_link": info.get("post_link", ""),
                "info": info
            }
            save_pending()

            # Mark this in user_data for the next text message from this admin
            context.user_data["waiting_reject_reason_for"] = str(target_user_id)

            await query.edit_message_text(
                f"❌ <b>REJECTING REPORT...</b>\n\n"
                f"👤 <b>USER ID:</b> <code>{target_user_id}</code>\n"
                f"🔗 <b>POST:</b> {safe(info.get('post_link', ''))}\n\n"
                f"📝 <b>PLEASE TYPE THE REASON FOR REJECTION.</b>\n"
                f"<b>THE USER WILL RECEIVE THIS REASON.</b>",
                parse_mode=ParseMode.HTML
            )

        return

    # ========== CHATTING GROUP (SAME AS ORIGINAL) ==========
    status_type = info["type"]
    username = info.get("username", "user")
    group = GROUPS[group_key]

    if action == "approve":
        try:
            if status_type == "ban":
                await context.bot.unban_chat_member(
                    chat_id=group["id"],
                    user_id=target_user_id,
                    only_if_banned=True
                )
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

# ================= HANDLE ADMIN REJECT REASON =================
async def handle_admin_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    target_user_id_str = context.user_data.get("waiting_reject_reason_for")
    if not target_user_id_str:
        return

    reason = update.message.text.strip()
    target_user_id = int(target_user_id_str)

    # Retrieve stored info
    key_reject = f"reject_waiting:{target_user_id}"
    reject_data = pending_appeals.pop(key_reject, None)
    save_pending()

    if not reject_data:
        await update.message.reply_text(
            "❌ <b>REJECT SESSION EXPIRED.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=main_keyboard
        )
        context.user_data.pop("waiting_reject_reason_for", None)
        return

    # Send rejection reason to user
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                f"❌ <b>YOUR AVOID HARM REPORT HAS BEEN REJECTED.</b>\n\n"
                f"📋 <b>REASON:</b>\n{safe(reason)}"
            ),
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass

    await update.message.reply_text(
        f"✅ <b>REJECTION SENT TO USER.</b>\n"
        f"👤 <b>USER ID:</b> <code>{target_user_id}</code>\n"
        f"📋 <b>REASON:</b> {safe(reason)}",
        parse_mode=ParseMode.HTML,
        reply_markup=main_keyboard
    )

    context.user_data.pop("waiting_reject_reason_for", None)

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

    lines = ["📋 <b>PENDING APPEALS/REPORTS:</b>\n"]

    count = 0
    for key, info in pending_appeals.items():
        if key.startswith("reject_waiting:"):
            continue
            
        uid = info.get("user_id", "Unknown")

        if info.get("group_key") == "avoid_harm":
            group_name = "🚫 Avoid Harm"
            extra = f"🔗 <b>POST:</b> {safe(info.get('post_link', 'N/A'))}"
        else:
            group_name = GROUPS.get(info.get("group_key", ""), {}).get("name", "Unknown")
            extra = f"⚠️ <b>TYPE:</b> {safe(info.get('type', 'unknown').upper())}"

        lines.append(
            f"👤 <b>ID:</b> <code>{uid}</code>\n"
            f"📢 <b>GROUP:</b> {safe(group_name)}\n"
            f"{extra}\n"
            f"🔗 <b>USERNAME:</b> @{safe(info.get('username', 'NoUsername'))}\n"
        )

        count += 1
        if count >= 15:
            break

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML
    )

# ================= MAIN =================
def main():
    load_pending()

    application = Application.builder().token(BOT_TOKEN).concurrent_updates(True).build()

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^(💬 Chatting|🚫 Avoid Harm)$"), group_button)
        ],
        states={
            WRITE_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, appeal_reason)
            ],
            ASK_POST_LINK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_post_link)
            ],
            ASK_EXPLANATION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_explanation)
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
    
    # Admin reject reason handler - outside conversation to avoid session expired
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.User(user_id=ADMIN_IDS),
            handle_admin_reject_reason
        )
    )

    print("🚀 BOT STARTED - CHATTING + AVOID HARM MODE")
    print(f"   ADMIN IDS: {ADMIN_IDS}")
    print(f"   AVOID HARM CHANNEL ID: {AVOID_HARM_CHANNEL['id']}")
    print(f"   (MAKE SURE BOT IS ADMIN IN THE CHANNEL WITH DELETE PERMISSION)")

    application.run_polling(
        drop_pending_updates=True,
        poll_interval=0.1,
        timeout=10,
        bootstrap_retries=-1,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == "__main__":
    main()