import os
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient

# रेंडरवरील वेरिएबल्स
BOT_TOKEN = os.environ.get("API_TOKEN")
MONGO_URL = os.environ.get("MONGO_URI")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

API_ID = 22247348 
API_HASH = "8706856012351235b2e564751235" 

app = Client("broadcast_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client.broadcast_db
channels_col = db.channels
msg_col = db.messages

@app.on_message(filters.private & filters.command("start"))
async def start(client, message):
    await message.reply_text("भावा, आता तू ID टाकून पण चॅनेल ॲड करू शकतोस!\n\n"
                             "🔹 **/add -100xxxx** : चॅनेल ॲड करण्यासाठी\n"
                             "🔹 **/remove -100xxxx** : चॅनेल काढण्यासाठी\n"
                             "🔹 **/stats** : लिस्ट बघण्यासाठी")

# --- १. ID टाकून चॅनेल ॲड करणे ---
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command("add"))
async def add_channel_by_id(client, message):
    if len(message.command) < 2:
        return await message.reply_text("❌ आयडी पण टाक भावा! उदा: `/add -100123456789`")
    
    chat_id = int(message.command[1])
    await channels_col.update_one({"chat_id": chat_id}, {"$set": {"chat_id": chat_id}}, upsert=True)
    await message.reply_text(f"✅ चॅनेल ID `{chat_id}` यशस्वीरित्या ॲड झाला!")

# --- २. ID टाकून चॅनेल रिमूव्ह करणे ---
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command("remove"))
async def remove_channel_by_id(client, message):
    if len(message.command) < 2:
        return await message.reply_text("❌ कोणता आयडी काढायचा? उदा: `/remove -100123456789`")
    
    chat_id = int(message.command[1])
    await channels_col.delete_one({"chat_id": chat_id})
    await message.reply_text(f"🗑️ चॅनेल ID `{chat_id}` काढला आहे.")

# बाकीचे ब्रॉडकास्ट आणि स्टेट्स लॉजिक तसेच आहे...
@app.on_message(filters.private & filters.command("stats"))
async def stats(client, message):
    count = await channels_col.count_documents({})
    await message.reply_text(f"📊 सध्या {count} चॅनेल्स जोडले आहेत.")

@app.on_message(filters.private & filters.user(ADMIN_ID) & ~filters.command(["start", "stats", "delete", "add", "remove"]))
async def start_broadcast(client, message):
    channels = await channels_col.find().to_list(length=100)
    if not channels: return await message.reply_text("❌ आधी चॅनेल ॲड करा!")
    sent_ids = []
    for ch in channels:
        try:
            sent = await message.copy(ch['chat_id'])
            sent_ids.append([ch['chat_id'], sent.id])
        except: pass
    await msg_col.update_one({"admin_id": ADMIN_ID}, {"$set": {"sent_ids": sent_ids}}, upsert=True)
    await message.reply_text(f"✅ {len(sent_ids)} चॅनेल्सवर पाठवला!")

@app.on_message(filters.private & filters.command("delete"))
async def delete_broadcast(client, message):
    data = await msg_col.find_one({"admin_id": ADMIN_ID})
    if data:
        for chat_id, msg_id in data["sent_ids"]:
            try: await client.delete_messages(chat_id, msg_id)
            except: pass
        await msg_col.delete_one({"admin_id": ADMIN_ID})
        await message.reply_text("🗑️ पोस्ट डिलीट केली!")

app.run()
