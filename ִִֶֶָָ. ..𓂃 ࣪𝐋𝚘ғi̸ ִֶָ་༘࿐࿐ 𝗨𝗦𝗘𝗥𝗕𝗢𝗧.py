from telethon import TelegramClient, events
from telethon.tl.functions.channels import InviteToChannelRequest, EditAdminRequest, EditPhotoRequest
from telethon.tl.functions.messages import AddChatUserRequest, EditChatAdminRequest
from telethon.tl.types import ChatAdminRights, Channel, Chat
from telethon.errors import FloodWaitError
import asyncio, random, time

# ---------- CONFIG ----------
api_id = 39472210
api_hash = "7f5b22842cd94f8e737455d427d5a816"
OWNER_ID = 7510461579

TEXT_DELAY = 1.2
# ----------------------------

client = TelegramClient("user_session", api_id, api_hash)

slide_targets = {}  # chat_id -> target_user_id
silenced_users = {}  # chat_id -> set(user_ids)
reply_targets = {}  # chat_id -> { "user_id": int, "text": str }
last_reply_time = {}  # chat_id -> timestamp
spam_tasks = {}  # chat_id -> asyncio Task
set_tasks = {}  # chat_id -> asyncio Task

# 👉 RAID TEXT (tum yahan edit kar sakte ho)
SWIPE_TEXTS = [
   "MADRCHOD KE BACHE 𓆩🦩𓆪",
    "𝐓ᴇʀ𝐈 𝐌ᴀ𝐀 𝐊ɪ 𝐗ᴜᴛ ~🪻🦂//>",
    " ᴛᴍᴋᴄ ᴍᴇʜ 🇱 🇦 🇳 🇩 🅳︎🅰︎🅻︎🅺︎🅴︎ 𝙛𝙖𝙖𝙙 ᴅᴜɴɢᴀ"
]






# ========== SPAM LOOP FUNCTION ==========

async def spam_loop(chat_id, text):
    while True:
        try:
            msg = await client.send_message(chat_id, text)
            print(f"[SPAM] Sent message: {text[:30]}...")
            # Pin message
            try:
                await client.pin_message(chat_id, msg.id, notify=False)
                print(f"[SPAM] Pinned message ID: {msg.id}")
            except Exception as e:
                print(f"[SPAM] Pin failed: {str(e)[:50]}")
            await asyncio.sleep(3)
        except FloodWaitError as fw:
            print(f"[SPAM] FloodWait: {fw.seconds}s")
            await asyncio.sleep(fw.seconds + 1)
        except Exception as e:
            print(f"[SPAM] Error: {str(e)}")
            await asyncio.sleep(3)

# ========== SET (GROUP DP) LOOP FUNCTION ==========

async def set_loop(chat_id, file_path):
    while True:
        try:
            file = await client.upload_file(file_path)
            await client(EditPhotoRequest(
                channel=chat_id,
                photo=file
            ))
            await asyncio.sleep(3)
        except FloodWaitError as fw:
            print(f"[SET] FloodWait: {fw.seconds}s")
            await asyncio.sleep(fw.seconds + 1)
        except Exception as e:
            print(f"[SET] Error: {str(e)}")
            await asyncio.sleep(3)

# ========== DOT COMMANDS ==========

# ---------- .chup / .stopchup (Auto-delete messages from silenced users) ----------
@client.on(events.NewMessage(outgoing=True, pattern=r'^~chup\s*$'))
async def cmd_chup(event):
    if not event.is_reply:
        await event.reply("Usage: Reply to a message and use ~chup")
        return

    chat_id = event.chat_id
    reply_msg = await event.get_reply_message()
    user_to_silence = reply_msg.sender_id

    if chat_id not in silenced_users:
        silenced_users[chat_id] = set()

    silenced_users[chat_id].add(user_to_silence)
    print(f"[CHUP] Silenced user {user_to_silence} in chat {chat_id}")
    await event.reply(f"✓ User silenced in this chat.")

@client.on(events.NewMessage(outgoing=True, pattern=r'^~stopchup\s*$'))
async def cmd_stopchup(event):
    if not event.is_reply:
        await event.reply("Usage: Reply to a message and use ~stopchup")
        return

    chat_id = event.chat_id
    reply_msg = await event.get_reply_message()
    user_to_unsilence = reply_msg.sender_id

    if chat_id in silenced_users:
        silenced_users[chat_id].discard(user_to_unsilence)
        print(f"[CHUP] Unsilenced user {user_to_unsilence} in chat {chat_id}")
        await event.reply(f"✓ User unsilenced in this chat.")
    else:
        await event.reply("No silenced users in this chat.")

# ---------- Auto-delete messages from silenced users ----------
@client.on(events.NewMessage(incoming=True))
async def check_silenced_user(event):
    chat_id = event.chat_id
    sender_id = event.sender_id

    # Don't delete OWNER messages or tilde commands
    raw_text = event.raw_text or ""
    if sender_id == OWNER_ID:
        return
    
    # Skip tilde commands
    if raw_text.startswith('~'):
        return

    if chat_id in silenced_users and sender_id in silenced_users[chat_id]:
        try:
            await event.delete()
            print(f"[CHUP] Deleted message from silenced user {sender_id}: {raw_text[:30]}")
        except Exception as e:
            print(f"[CHUP] Delete failed: {str(e)}")


# ---------- ~add @bot1,@bot2,... (Add and promote bots) ----------
@client.on(events.NewMessage(outgoing=True, pattern=r'^~add\s+(.+?)\s*$'))
async def cmd_add(event):
    bots_str = event.pattern_match.group(1).strip()
    bot_usernames = [b.strip().lstrip('@') for b in bots_str.split(',') if b.strip()]

    if not bot_usernames:
        await event.reply("Usage: ~add @bot1,@bot2,@bot3")
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
@client.on(events.NewMessage(outgoing=True, pattern=r'^~slide\s*$'))
async def cmd_slide(event):
    if not event.is_reply:
        await event.reply("Usage: Reply to a message and use ~slide")
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
@client.on(events.NewMessage(outgoing=True, pattern=r'^~stopslide\s*$'))
async def cmd_stopslide(event):
    chat_id = event.chat_id
    if chat_id in slide_targets:
        del slide_targets[chat_id]
        await event.reply("✗ Slide deactivated.")
    else:
        await event.reply("Slide not active.")

# ---------- .reply <text> ----------
@client.on(events.NewMessage(outgoing=True, pattern=r'^~reply\s+(.+?)\s*$'))
async def cmd_reply(event):
    if not event.is_reply:
        await event.reply("Usage: Reply to a message and use ~reply <text>")
        return

    chat_id = event.chat_id
    reply_msg = await event.get_reply_message()
    target_user_id = reply_msg.sender_id
    custom_text = event.pattern_match.group(1).strip()

    reply_targets[chat_id] = {
        "user_id": target_user_id,
        "text": custom_text
    }
    await event.reply(f"✓ Reply mode activated with text: {custom_text}")

# ---------- .stopreply ----------
@client.on(events.NewMessage(outgoing=True, pattern=r'^~stopreply\s*$'))
async def cmd_stopreply(event):
    chat_id = event.chat_id
    if chat_id in reply_targets:
        del reply_targets[chat_id]
        await event.reply("✗ Reply mode deactivated")
    else:
        await event.reply("Reply mode not active.")

# ---------- .spam <text> ----------
@client.on(events.NewMessage(outgoing=True, pattern=r'^~spam\s+(.+?)\s*$'))
async def cmd_spam(event):
    chat_id = event.chat_id
    text = event.pattern_match.group(1).strip()

    if not text:
        await event.reply("Usage: ~spam <text>")
        return

    print(f"[SPAM] Starting spam in chat {chat_id} with text: {text}")
    
    # Stop existing spam if running
    if chat_id in spam_tasks:
        spam_tasks[chat_id].cancel()
        del spam_tasks[chat_id]
        print(f"[SPAM] Stopped existing spam in chat {chat_id}")

    # Start new spam
    task = asyncio.create_task(spam_loop(chat_id, text))
    spam_tasks[chat_id] = task
    print(f"[SPAM] Task created for chat {chat_id}")
    await event.reply("✓ Spam started")

# ---------- .stopspam ----------
@client.on(events.NewMessage(outgoing=True, pattern=r'^~stopspam\s*$'))
async def cmd_stopspam(event):
    chat_id = event.chat_id
    if chat_id in spam_tasks:
        spam_tasks[chat_id].cancel()
        del spam_tasks[chat_id]
        await event.reply("✗ Spam stopped")
    else:
        await event.reply("No spam running.")

# ---------- .set (auto group DP changer) ----------
@client.on(events.NewMessage(outgoing=True, pattern=r'^~set\s*$'))
async def cmd_set(event):
    if not event.is_reply:
        await event.reply("Usage: Reply to an image and use ~set")
        return

    chat_id = event.chat_id
    reply_msg = await event.get_reply_message()

    # Check if reply has media
    if not reply_msg.media:
        await event.reply("Reply message must contain an image")
        return

    # Download the image
    try:
        file_path = await client.download_media(reply_msg.media)
        print(f"[SET] Downloaded image to: {file_path}")
    except Exception as e:
        await event.reply(f"Error downloading image: {str(e)[:50]}")
        print(f"[SET] Download error: {str(e)}")
        return

    # Stop existing set if running
    if chat_id in set_tasks:
        set_tasks[chat_id].cancel()
        del set_tasks[chat_id]
        print(f"[SET] Stopped existing task in chat {chat_id}")

    # Start new set loop
    task = asyncio.create_task(set_loop(chat_id, file_path))
    set_tasks[chat_id] = task
    print(f"[SET] Started new DP changer in chat {chat_id}")
    await event.reply("✓ Auto group DP changer started")

# ---------- .stopset ----------
@client.on(events.NewMessage(outgoing=True, pattern=r'^~stopset\s*$'))
async def cmd_stopset(event):
    chat_id = event.chat_id
    if chat_id in set_tasks:
        set_tasks[chat_id].cancel()
        del set_tasks[chat_id]
        await event.reply("✗ Auto group DP changer stopped")
    else:
        await event.reply("No auto DP changer running.")

# ---------- .menu (display all commands) ----------
@client.on(events.NewMessage(outgoing=True, pattern=r'^~menu\s*$'))
async def cmd_menu(event):
    menu_text = """🔥 𝗨𝗦𝗘𝗥𝗕𝗢𝗧 𝗠𝗘𝗡𝗨 🔥

━━━━━━━━━━━━━━━━━━━━━━━

🔇 ~chup
➤ Silence a user (auto delete messages)

🔊 ~stopchup
➤ Unsilence user

➕ ~add @bots
➤ Add & promote bots to group

💀 ~slide
➤ Spam reply mode (50 burst replies)

🛑 ~stopslide
➤ Stop slide mode

🎯 ~reply <text>
➤ Auto reply with fixed text

❌ ~stopreply
➤ Stop reply mode

🚀 ~spam <text>
➤ Auto spam + pin every 3 sec

⏹️ ~stopspam
➤ Stop spam

🖼️ ~set
➤ Auto change group DP every 3 sec

❌ ~stopset
➤ Stop DP changer

📋 ~menu
➤ Show this menu

━━━━━━━━━━━━━━━━━━━━━━━
⚡ Powered by ִֶָ. ..𓂃 ࣪ ִִֶֶָָ. ..𓂃 ࣪𝐋𝚘ғi̸ ִֶָ་༘࿐࿐
"""
    await event.reply(menu_text)

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
    if raw_text.startswith('~'):
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
            # Skip on other errors but continue
            continue

# ---------- Reply trigger handler (global incoming messages) ----------
@client.on(events.NewMessage(incoming=True))
async def handle_reply_trigger(event):
    chat_id = event.chat_id
    sender_id = event.sender_id

    # Only trigger if this chat has an active reply target
    if chat_id not in reply_targets:
        return

    target = reply_targets[chat_id]

    # Don't trigger on OWNER or target user not matching
    if sender_id == OWNER_ID or sender_id != target["user_id"]:
        return

    # Don't trigger on dot commands
    raw_text = event.raw_text or ""
    if raw_text.startswith('~'):
        return

    # Anti-spam: check last reply time
    current_time = time.time()
    if chat_id in last_reply_time:
        if current_time - last_reply_time[chat_id] < 0.5:
            return
    last_reply_time[chat_id] = current_time

    # Delay
    await asyncio.sleep(random.uniform(0.3, 0.7))

    try:
        await event.reply(target["text"])
    except FloodWaitError as fw:
        await asyncio.sleep(fw.seconds + 1)
        await event.reply(target["text"])
    except Exception:
        pass

# ---------- START ----------
client.start()
print("Userbot running (final build)...")
client.run_until_disconnected()
