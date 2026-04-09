from telethon import TelegramClient, events
from telethon.tl.functions.channels import InviteToChannelRequest, EditAdminRequest
from telethon.tl.functions.messages import AddChatUserRequest, EditChatAdminRequest
from telethon.tl.types import ChatAdminRights, Channel, Chat
from telethon.errors import FloodWaitError
import asyncio, random

# ---------- CONFIG ----------
api_id = 39472210
api_hash = "7f5b22842cd94f8e737455d427d5a816"
OWNER_ID = 7510461579

TEXT_DELAY = 1.2
# ----------------------------

client = TelegramClient("user_session", api_id, api_hash)

slide_targets = {}  # chat_id -> target_user_id
silenced_users = {}  # chat_id -> set(user_ids)

# 👉 RAID TEXT (tum yahan edit kar sakte ho)
SWIPE_TEXTS = [
   "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15"
]






# ========== DOT COMMANDS ==========

# ---------- .chup / .stopchup (Auto-delete messages from silenced users) ----------
@client.on(events.NewMessage(pattern=r'^\.chup$'))
async def cmd_chup(event):
    if event.sender_id != OWNER_ID:
        return

    if not event.is_reply:
        await event.reply("Usage: Reply to a message and use .chup")
        return

    chat_id = event.chat_id
    reply_msg = await event.get_reply_message()
    user_to_silence = reply_msg.sender_id

    if chat_id not in silenced_users:
        silenced_users[chat_id] = set()

    silenced_users[chat_id].add(user_to_silence)
    await event.reply(f"✓ User silenced in this chat.")

@client.on(events.NewMessage(pattern=r'^\.stopchup$'))
async def cmd_stopchup(event):
    if event.sender_id != OWNER_ID:
        return

    if not event.is_reply:
        await event.reply("Usage: Reply to a message and use .stopchup")
        return

    chat_id = event.chat_id
    reply_msg = await event.get_reply_message()
    user_to_unsilence = reply_msg.sender_id

    if chat_id in silenced_users:
        silenced_users[chat_id].discard(user_to_unsilence)
        await event.reply(f"✓ User unsilenced in this chat.")
    else:
        await event.reply("No silenced users in this chat.")

# ---------- Auto-delete messages from silenced users ----------
@client.on(events.NewMessage(incoming=True))
async def check_silenced_user(event):
    chat_id = event.chat_id
    sender_id = event.sender_id

    # Don't delete OWNER messages or dot commands
    raw_text = event.raw_text or ""
    if sender_id == OWNER_ID or raw_text.startswith('.'):
        return

    if chat_id in silenced_users and sender_id in silenced_users[chat_id]:
        try:
            await event.delete()
        except:
            pass

# ---------- .add @bot1,@bot2,... (Add and promote bots) ----------
@client.on(events.NewMessage(pattern=r'^\.add\s+(.+)$'))
async def cmd_add(event):
    if event.sender_id != OWNER_ID:
        return

    bots_str = event.pattern_match.group(1).strip()
    bot_usernames = [b.strip().lstrip('@') for b in bots_str.split(',') if b.strip()]

    if not bot_usernames:
        await event.reply("Usage: .add @bot1,@bot2,@bot3")
        return

    results = []
    
    # Get the actual chat object to determine type
    try:
        chat = await event.get_chat()
    except Exception as e:
        await event.reply(f"Error getting chat info: {str(e)[:50]}")
        return

    is_channel = isinstance(chat, Channel)
    chat_id = chat.id

    for bot_username in bot_usernames:
        try:
            # Resolve bot username to user with @ prefix
            bot_user = await client.get_entity("@" + bot_username)
            bot_id = bot_user.id

            if is_channel:
                # CHANNEL/SUPERGROUP: Use InviteToChannelRequest + EditAdminRequest
                try:
                    await client(InviteToChannelRequest(
                        channel=chat_id,
                        users=[bot_user]
                    ))
                except Exception:
                    # Bot might already be in the group
                    pass

                # Promote to admin with valid fields
                admin_rights = ChatAdminRights(
                    change_info=True,
                    post_messages=True,
                    edit_messages=True,
                    delete_messages=True,
                    ban_users=True,
                    invite_users=True,
                    pin_messages=True,
                    add_admins=False
                )

                await client(EditAdminRequest(
                    channel=chat_id,
                    user_id=bot_id,
                    admin_rights=admin_rights,
                    rank="Admin"
                ))
            else:
                # NORMAL GROUP: Use AddChatUserRequest + EditChatAdminRequest
                try:
                    await client(AddChatUserRequest(
                        chat_id=chat_id,
                        user_id=bot_id,
                        fwd_limit=0
                    ))
                except Exception:
                    # Bot might already be in the group
                    pass

                # Promote to admin
                await client(EditChatAdminRequest(
                    chat_id=chat_id,
                    user_id=bot_id,
                    is_admin=True
                ))

            results.append(f"✓ @{bot_username}")

        except Exception as e:
            # Truncate long error messages
            error_msg = str(e)[:50]
            results.append(f"✗ @{bot_username}: {error_msg}")

    # Send results in chunks to avoid MessageTooLongError
    reply_text = "Add bot results:\n"
    for result in results:
        if len(reply_text) + len(result) + 1 > 4000:
            # Send current chunk and start a new one
            await event.reply(reply_text)
            reply_text = "Add bot results (cont):\n"
        reply_text += result + "\n"
    
    # Send final chunk
    if reply_text.strip() != "Add bot results:\n" and reply_text.strip() != "Add bot results (cont):\n":
        await event.reply(reply_text)

# ---------- .slide (reply raid trigger) ----------
@client.on(events.NewMessage(pattern=r'^\.slide$'))
async def cmd_slide(event):
    if event.sender_id != OWNER_ID:
        return

    if not event.is_reply:
        await event.reply("Usage: Reply to a message and use .slide")
        return

    chat_id = event.chat_id
    if chat_id in slide_targets:
        await event.reply("Slide already active in this chat.")
        return

    reply_msg = await event.get_reply_message()
    target_user_id = reply_msg.sender_id

    slide_targets[chat_id] = target_user_id
    await event.reply("✓ Slide activated. Will reply to target user's messages.")

# ---------- .stopslide ----------
@client.on(events.NewMessage(pattern=r'^\.stopslide$'))
async def cmd_stopslide(event):
    if event.sender_id != OWNER_ID:
        return

    chat_id = event.chat_id
    if chat_id in slide_targets:
        del slide_targets[chat_id]
        await event.reply("✗ Slide deactivated.")
    else:
        await event.reply("Slide not active.")

# ---------- Slide raid trigger handler (global incoming messages) ----------
@client.on(events.NewMessage(incoming=True))
async def handle_slide_trigger(event):
    chat_id = event.chat_id
    sender_id = event.sender_id

    # Only trigger if this chat has an active slide target
    if chat_id not in slide_targets:
        return

    target_user_id = slide_targets[chat_id]

    # Don't trigger on OWNER or target user not matching
    if sender_id == OWNER_ID or sender_id != target_user_id:
        return

    # Don't trigger on dot commands
    raw_text = event.raw_text or ""
    if raw_text.startswith('.'):
        return

    # Get target user info for mention
    try:
        target_user = await client.get_entity(sender_id)
    except Exception:
        return

    # Create mention
    if target_user.username:
        target_mention = f"@{target_user.username}"
        use_html = False
    else:
        user_name = target_user.first_name or f"User {target_user.id}"
        target_mention = f'<a href="tg://user?id={target_user.id}">{user_name}</a>'
        use_html = True

    # Send 50 burst replies to this message
    reply_count = 0
    for i in range(50):
        try:
            raid_text = random.choice(SWIPE_TEXTS)
            msg = f"{target_mention} {raid_text}"
            await event.reply(msg, parse_mode="html" if use_html else None)
            reply_count += 1
            await asyncio.sleep(0.2)  # Delay between replies
        except FloodWaitError as fw:
            # Handle flood wait - sleep then continue
            await asyncio.sleep(fw.seconds + 1)
        except Exception:
            # Skip on other errors but continue
            continue

# ---------- START ----------
client.start()
print("Userbot running (final build)...")
client.run_until_disconnected()
