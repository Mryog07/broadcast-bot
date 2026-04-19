import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient

# --- रेंडरला फसवण्यासाठी Dummy Web Server ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running!")

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

# तुझे खरे आकडे
API_ID = 30767171  
API_HASH = "af363a055e5c68096847d64871c758c5"  

app = Client("broadcast_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client.broadcast_db
channels_col = db.channels
msg_col = db.messages

@app.on_message(filters.private & filters.command("start"))
async def start(client, message):
    await message.reply_text("🔥 MTC ब्रॉडकास्ट बॉट तयार आहे!\n\n"
                             "🔹 /add -100xxx : चॅनेल जोडा\n"
                             "🔹 /remove -100xxx : चॅनेल काढा\n"
                             "🔹 /stats : चॅनेल्सची संख्या बघा\n"
                             "🔹 /delete : शेवटची पोस्ट उडवा")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command("add"))
async def add_ch(client, message):
    if len(message.command) < 2: 
        return await message.reply_text("❌ ID टाका! उदा: /add -100123456789")
    try:
        c_id = int(message.command[1].strip())
        await channels_col.update_one({"chat_id": c_id}, {"$set": {"chat_id": c_id}}, upsert=True)
        await message.reply_text(f"✅ ID {c_id} डेटाबेसमध्ये सेव्ह झाला!")
    except: 
        await message.reply_text("❌ चुकीचा ID! फक्त आकडे टाका.")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command("remove"))
async def rem_ch(client, message):
    if len(message.command) < 2: return await message.reply_text("❌ ID टाका!")
    try:
        c_id = int(message.command[1].strip())
        await channels_col.delete_one({"chat_id": c_id})
        await message.reply_text(f"🗑️ ID {c_id} काढला आहे.")
    except: pass

@app.on_message(filters.private & filters.command("stats"))
async def show_stats(client, message):
    count = await channels_col.count_documents({})
    await message.reply_text(f"📊 सध्या {count} चॅनेल्स ब्रॉडकास्टसाठी जोडलेले आहेत.")

@app.on_message(filters.private & filters.user(ADMIN_ID) & ~filters.command(["start", "stats", "delete", "add", "remove"]))
async def b_cast(client, message):
    channels = await channels_col.find().to_list(length=100)
    if not channels: 
        return await message.reply_text("❌ आधी /add करून चॅनेल जोडा!")
    
    sent_ids = []
    for ch in channels:
        try:
            sent = await message.copy(ch['chat_id'])
            sent_ids.append([ch['chat_id'], sent.id])
        except: pass
    
    await msg_col.update_one({"admin_id": ADMIN_ID}, {"$set": {"sent_ids": sent_ids}}, upsert=True)
    await message.reply_text(f"✅ {len(sent_ids)} ठिकाणी ब्रॉडकास्ट झाला!")

@app.on_message(filters.private & filters.command("delete"))
async def del_cast(client, message):
    data = await msg_col.find_one({"admin_id": ADMIN_ID})
    if data:
        for c_id, m_id in data["sent_ids"]:
            try: await client.delete_messages(c_id, m_id)
            except: pass
        await msg_col.delete_one({"admin_id": ADMIN_ID})
        await message.reply_text("🗑️ सर्व चॅनेल्सवरून पोस्ट डिलीट केली!")
    else:
        await message.reply_text("❌ डिलीट करण्यासाठी मेसेज सापडला नाही.")

async def main():
    await app.start()
    print("बॉट सुरू झाला आहे... 🚀")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
