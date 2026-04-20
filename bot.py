import os
import asyncio
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient

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

# रेंडरवरील Variables (काहीही बदलू नकोस, रेंडरवरून आपोआप उचलले जातील)
BOT_TOKEN = os.environ.get("API_TOKEN")
MONGO_URL = os.environ.get("MONGO_URI")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

# तुझे ओरिजनल आकडे
API_ID = 30767171  
API_HASH = "af363a055e5c68096847d64871c758c5"  

app = Client("mtc_unified_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client.mtc_unified_db

# दोन वेगळे कप्पे (Collections)
marathi_col = db.marathi_channels
hindi_col = db.hindi_channels
msg_col = db.messages

@app.on_message(filters.private & filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "🚀 **MTC Unified Control Panel**\n\n"
        "🚩 **मराठी विभाग:**\n"
        "➕ `/add_m` | ➖ `/rm_m` | 📊 `/stats_m` \n"
        "📢 ब्रॉडकास्ट: पोस्टला `/bm` ने रिप्लाय द्या.\n\n"
        "🔥 **हिंदी विभाग:**\n"
        "➕ `/add_h` | ➖ `/rm_h` | 📊 `/stats_h` \n"
        "📢 ब्रॉडकास्ट: पोस्टला `/bh` ने रिप्लाय द्या.\n\n"
        "🗑️ **डिलीट:** `/del_m` किंवा `/del_h` (शेवटची पोस्ट उडवण्यासाठी)"
    )

# --- चॅनेल मॅनेजमेंट ---
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["add_m", "add_h"]))
async def add_ch(client, message):
    col = marathi_col if "_m" in message.text else hindi_col
    if len(message.command) < 2: return await message.reply_text("❌ ID द्या!")
    try:
        c_id = int(message.command[1].strip())
        await col.update_one({"chat_id": c_id}, {"$set": {"chat_id": c_id}}, upsert=True)
        await message.reply_text(f"✅ चॅनेल {c_id} सेव्ह झाला!")
    except: await message.reply_text("❌ आयडी फक्त आकड्यांत द्या!")

@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["rm_m", "rm_h"]))
async def rem_ch(client, message):
    col = marathi_col if "_m" in message.text else hindi_col
    try:
        c_id = int(message.command[1].strip())
        await col.delete_one({"chat_id": c_id})
        await message.reply_text(f"🗑️ चॅनेल {c_id} काढला!")
    except: pass

# --- ब्रॉडकास्ट सिस्टीम ---
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["bm", "bh"]))
async def b_cast(client, message):
    if not message.reply_to_message:
        return await message.reply_text("❌ ज्या मेसेजचा ब्रॉडकास्ट करायचा आहे, त्याला रिप्लाय देऊन ही कमांड टाका!")
    
    col = marathi_col if message.text == "/bm" else hindi_col
    reply_msg = message.reply_to_message
    channels = await col.find().to_list(length=300)
    
    if not channels: return await message.reply_text("❌ चॅनेल लिस्ट रिकामी आहे!")
    
    sent_ids = []
    for ch in channels:
        try:
            sent = await reply_msg.copy(ch['chat_id'])
            sent_ids.append([ch['chat_id'], sent.id])
        except: pass
    
    mode = "marathi" if message.text == "/bm" else "hindi"
    await msg_col.update_one({"type": mode}, {"$set": {"sent_ids": sent_ids}}, upsert=True)
    await message.reply_text(f"✅ {len(sent_ids)} चॅनेल्सवर ब्रॉडकास्ट पूर्ण!")

# --- डिलीट सिस्टीम ---
@app.on_message(filters.private & filters.user(ADMIN_ID) & filters.command(["del_m", "del_h"]))
async def del_cast(client, message):
    mode = "marathi" if "_m" in message.text else "hindi"
    data = await msg_col.find_one({"type": mode})
    if data:
        for c_id, m_id in data["sent_ids"]:
            try: await client.delete_messages(c_id, m_id)
            except: pass
        await msg_col.delete_one({"type": mode})
        await message.reply_text(f"🗑️ {mode} चॅनेल्सवरून शेवटची पोस्ट डिलीट केली!")
    else: await message.reply_text("❌ डिलीट करण्यासाठी डेटा नाही.")

async def main():
    await app.start()
    print("MTC Unified Bot Started! 🚀")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
