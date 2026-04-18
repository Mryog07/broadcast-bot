import os
import telebot
from flask import Flask
from threading import Thread

# १. रेंडरसाठी वेब सर्व्हर (Ping Logic)
app = Flask('')

@app.route('/')
def home():
    return "Bot is Running!"

def run():
    # रेंडर पोर्ट आपोआप डिटेक्ट करेल
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

def keep_alive():
    t = Thread(target=run)
    t.start()

# २. बॉट सेटअप (Environment Variables मधून डेटा घेईल)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
# चॅनेल्सची लिस्ट स्वल्पविरामाने (comma) वेगळी केली आहे
CHANNELS = [int(i.strip()) for i in os.getenv("CHANNELS").split(",")]

bot = telebot.TeleBot(BOT_TOKEN)

# ३. ब्रॉडकास्ट फंक्शन (फक्त ॲडमिनसाठी)
@bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID, 
                     content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'animation'])
def broadcast(message):
    status_msg = bot.reply_to(message, "⏳ Broadcasting सुरू आहे...")
    success = 0
    failed = 0
    
    for chat_id in CHANNELS:
        try:
            # copy_message फंक्शन मेसेजला 'same to same' पाठवतं
            bot.copy_message(chat_id, message.chat.id, message.message_id)
            success += 1
        except Exception as e:
            print(f"Error on {chat_id}: {e}")
            failed += 1
    
    bot.edit_message_text(f"✅ पोस्ट पाठवून झाली आहे!\n\nयशस्वी: {success}\nअपयशी: {failed}", 
                          status_msg.chat.id, status_msg.message_id)

if __name__ == "__main__":
    print("बॉट सुरू होत आहे...")
    keep_alive() # वेब सर्व्हर सुरू करतोय
    bot.infinity_polling()
