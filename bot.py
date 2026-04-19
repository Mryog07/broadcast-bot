import os
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient

# रेंडरवरील वेरिएबल्स
BOT_TOKEN = os.environ.get("API_TOKEN")
MONGO_URL = os.environ.get("MONGO_URI")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

# टेलिग्राम अधिकृत API Keys
API_ID = 22247348 
API_HASH = "8706856012351235b2e564751235" 

app = Client("broadcast_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client.broadcast_db
channels_col = db.channels # चॅनेल आयडी सेव्ह करण्यासाठी
msg_col = db.messages # डिलीट फीचरसाठी

# --- १. स्टार्ट आणि हेल्प ---
@app.on_message(filters.private & filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "👋 **MTC ब्रॉडकास्ट बॉटमध्ये स्वागत आहे!**\n\n"
        "🔹 **चॅनेल ॲड करण्यासाठी:** चॅनेलची एखादी पोस्ट मला फॉरवर्ड करा.\n"
        "🔹 **ब्रॉडकास्टसाठी:** कोणताही मेसेज पाठवा, तो सर्व ॲड केलेल्या चॅनेल्सवर जाईल.\n"
        "🔹 **कमांड्स:** /stats, /delete, /clean"
    )

# --- २. चॅनेल ॲड करण्याचे लॉजिक (फॉरवर्ड करून) ---
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.forwarded)
async def add_channel(client, message):
    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        chat_title = message.forward_from_chat.title
        
        await channels_col.update_one(
            {"chat_id": chat_id}, 
            {"$set": {"title": chat_title}}, 
            upsert=True
        )
        await message.reply_text(f"✅ **चॅनेल यशस्वीरित्या ॲड झाले!**\n\n📢 नाव: {chat_title}\n🆔 ID: `{chat_id}`")
    else:
        await message.reply_text("❌ कृपया चॅनेलचा मेसेज फॉरवर्ड करा (युजरचा नाही).")

# --- ३. स्टेट्स आणि क्लिन ---
@app.on_message(filters.private & filters.command("stats"))
async def stats(client, message):
    count = await channels_col.count_documents({})
    await message.reply_text(f"📊 **स्टेटस:**\n✅ सध्या {count} चॅनेल्स ब्रॉडकास्टसाठी जोडले आहेत.")

@app.on_message(filters.private & filters.command("clean"))
async def clean_database(client, message):
    await channels_col.delete_many({})
    await message.reply_text("🗑️ सर्व जुने चॅनेल आयडी डेटाबेसमधून हटवले आहेत. आता नवीन ॲड करा.")

# --- ४. ब्रॉडकास्ट आणि डिलीट ---
@app.on_message(filters.private & filters.user(ADMIN_ID) & ~filters.command(["start", "stats", "delete", "clean"]))
async def start_broadcast(client, message):
    channels = await channels_col.find().to_list(length=100)
    if not channels:
        return await message.reply_text("❌ आधी चॅनेल ॲड करा! (चॅनेलची एखादी पोस्ट फॉरवर्ड करा)")

    sent_ids = []
    for ch in channels:
        try:
            sent = await message.copy(ch['chat_id'])
            sent_ids.append([ch['chat_id'], sent.id])
        except: pass
    
    await msg_col.update_one({"admin_id": ADMIN_ID}, {"$set": {"sent_ids": sent_ids}}, upsert=True)
    await message.reply_text(f"✅ {len(sent_ids)} चॅनेल्सवर मेसेज पाठवला!\nडिलीट करण्यासाठी /delete दाबा.")

@app.on_message(filters.private & filters.command("delete"))
async def delete_broadcast(client, message):
    data = await msg_col.find_one({"admin_id": ADMIN_ID})
    if data:
        for chat_id, msg_id in data["sent_ids"]:
            try: await client.delete_messages(chat_id, msg_id)
            except: pass
        await msg_col.delete_one({"admin_id": ADMIN_ID})
        await message.reply_text("🗑️ सर्व चॅनेल्सवरून पोस्ट डिलीट केली!")
    else:
        await message.reply_text("❌ डिलीट करण्यासाठी कोणतीही पोस्ट सापडली नाही.")

app.run()
