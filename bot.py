import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

# --- रेंडरला जिवंत ठेवण्यासाठी Dummy Web Server ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"MTC Unified Bot is Running!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

threading.Thread(target=run_dummy_server, daemon=True).start()
# ----------------------------------------------

# रेंडरवरील Variables
BOT_TOKEN = os.environ.get("API_TOKEN")
MONGO_URL = os.environ.get("MONGO_URI")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

API_ID = 30767171  
API_HASH = "af363a055e5c68096847d64871c758c5"  

app = Client("mtc_unified_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client.mtc_unified_db

marathi_col = db.marathi_channels
hindi_col = db.hindi_channels
msg_col = db.messages

# शेड्युलर सेटअप
scheduler = AsyncIOScheduler()

async def scheduled_broadcast(chat_ids, reply_to_message, mode):
    sent_ids = []
    for c_id in chat_ids:
        try:
            sent = await reply_to_message.copy(c_id)
            sent_ids.append([c_id, sent.id])
        except: pass
    await msg_col.update_one({"type": mode}, {"$set": {"sent_ids": sent_ids}}, upsert=True)

@app.on_message(filters.private & filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "🚀 **MTC Unified Control Panel**\n\n"
        "🚩 **मराठी विभाग:**\n"
        "➕ `/add_marathi` | ➖ `/remove_marathi` | 📊 `/stats_marathi`\n"
        "📢 ब्रॉडकास्ट: `/broadcast_marathi` (रिप्लाय द्या)\n"
        "⏰ शेड्युल: `/schedule_marathi 10:00 AM` (रिप्लाय द्या)\n\n"
        "🔥 **हिंदी विभाग:**\n"
        "➕ `/add_hindi` | ➖ `/remove_hindi` | 📊 `/stats_hindi`\n"
        "📢 ब्रॉडकास्ट: `/broadcast_hindi` (रिप्लाय द्या)\n"
        "⏰ शेड्युल: `/schedule_hindi 10:00 AM` (रिप्लाय द्या)\n\n"
        "🗑️ **डिलीट:** `/delete_marathi` किंवा `/delete_hindi`"
    )

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["add_marathi", "add_hindi"]))
async def add_ch(client, message):
    col = marathi_col if "marathi" in message.text else hindi_col
    if len(message.command) < 2: return await message.reply_text("❌ ID द्या! उदा: /add_marathi -100xxx")
    try:
        c_id = int(message.command[1].strip())
        await col.update_one({"chat_id": c_id}, {"$set": {"chat_id": c_id}}, upsert=True)
        await message.reply_text(f"✅ चॅनेल {c_id} सेव्ह झाला!")
    except: await message.reply_text("❌ आयडी फक्त आकड्यांत द्या!")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["remove_marathi", "remove_hindi"]))
async def rem_ch(client, message):
    col = marathi_col if "marathi" in message.text else hindi_col
    if len(message.command) < 2: return await message.reply_text("❌ ID द्या! उदा: /remove_marathi -100xxx")
    try:
        c_id = int(message.command[1].strip())
        await col.delete_one({"chat_id": c_id})
        await message.reply_text(f"🗑️ चॅनेल {c_id} काढला!")
    except: pass

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["stats_marathi", "stats_hindi"]))
async def show_stats(client, message):
    col = marathi_col if "marathi" in message.text else hindi_col
    lang = "मराठी" if "marathi" in message.text else "हिंदी"
    count = await col.count_documents({})
    await message.reply_text(f"📊 सध्या {count} {lang} चॅनेल्स जोडलेले आहेत.")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["broadcast_marathi", "broadcast_hindi"]))
async def b_cast(client, message):
    if not message.reply_to_message:
        return await message.reply_text("❌ पोस्टला रिप्लाय देऊन कमांड टाका!")
    col = marathi_col if "marathi" in message.text else hindi_col
    reply_msg = message.reply_to_message
    channels = await col.find().to_list(length=300)
    if not channels: return await message.reply_text("❌ चॅनेल लिस्ट रिकामी आहे!")
    sent_ids = []
    for ch in channels:
        try:
            sent = await reply_msg.copy(ch['chat_id'])
            sent_ids.append([ch['chat_id'], sent.id])
        except: pass
    mode = "marathi" if "marathi" in message.text else "hindi"
    await msg_col.update_one({"type": mode}, {"$set": {"sent_ids": sent_ids}}, upsert=True)
    await message.reply_text(f"✅ {len(sent_ids)} चॅनेल्सवर ब्रॉडकास्ट पूर्ण!")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["schedule_marathi", "schedule_hindi"]))
async def schedule_cmd(client, message):
    if not message.reply_to_message or len(message.command) < 3:
        return await message.reply_text("❌ पद्धत: /schedule_marathi 10:05 AM")
    time_str = f"{message.command[1]} {message.command[2]}"
    mode = "marathi" if "marathi" in message.text else "hindi"
    col = marathi_col if mode == "marathi" else hindi_col
    try:
        # UTC ते IST कन्व्हर्जन फिक्स
        target_time = datetime.strptime(f"{datetime.now().date()} {time_str}", "%Y-%m-%d %I:%M %p")
        run_date = target_time - timedelta(hours=5, minutes=30)
        
        channels = await col.find().to_list(length=300)
        chat_ids = [ch['chat_id'] for ch in channels]
        scheduler.add_job(scheduled_broadcast, 'date', run_date=run_date, args=[chat_ids, message.reply_to_message, mode])
        await message.reply_text(f"✅ पोस्ट {time_str} ला शेड्युल झाली आहे!")
    except Exception as e:
        await message.reply_text(f"❌ वेळ नीट द्या (उदा: 10:05 AM). Error: {e}")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["delete_marathi", "delete_hindi"]))
async def del_cast(client, message):
    mode = "marathi" if "marathi" in message.text else "hindi"
    data = await msg_col.find_one({"type": mode})
    if data:
        for c_id, m_id in data["sent_ids"]:
            try: await client.delete_messages(c_id, m_id)
            except: pass
        await msg_col.delete_one({"type": mode})
        await message.reply_text(f"🗑️ {mode} चॅनेल्सवरून पोस्ट डिलीट केली!")
    else: await message.reply_text("❌ डिलीट करण्यासाठी डेटा नाही.")

async def main():
    scheduler.start()
    await app.start()
    print("MTC Unified Bot Started! 🚀")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
