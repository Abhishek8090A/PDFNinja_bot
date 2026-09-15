import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread
import os
import requests

# --- Your API Keys and Token ---
TELEGRAM_TOKEN = '7912628972:AAFq72d_STTAJJBHzSLSlRHkAUxpQcft09M'
PUBLIC_KEY = 'project_public_9de017d12938f5eb5fe837197f34d925_Y2rbd6f01dd9c5063f8c898ec4a207f5739df'
SECRET_KEY = 'secret_key_d0b29d002254eddec1383aba2b6af74d_QGRTqdc4f93d5becf0e806598aeeb1448e18c'
ADMIN_ID = 6262854630

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_states = {}

# --- Flask Server (24/7 Alive) ---
app = Flask(__name__)
@app.route('/')
def home():
    return "PDF Ninja Bot is running 24/7!"
def run():
    app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()
# ----------------------------------------

def save_user(chat_id):
    users = set()
    if os.path.exists('users.txt'):
        with open('users.txt', 'r') as f:
            for line in f:
                users.add(line.strip())
    if str(chat_id) not in users:
        with open('users.txt', 'a') as f:
            f.write(f"{chat_id}\n")

def get_users():
    if not os.path.exists('users.txt'):
        return []
    with open('users.txt', 'r') as f:
        return [line.strip() for line in f]

# --- Main Menu ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    chat_id = message.chat.id
    save_user(chat_id)
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🗜 Compress PDF", callback_data="compress"),
        InlineKeyboardButton("🖼 PDF to JPG", callback_data="pdfjpg"),
        InlineKeyboardButton("📄 Word to PDF", callback_data="officepdf")
    )
    
    if chat_id == ADMIN_ID:
        markup.add(InlineKeyboardButton("📢 Admin Panel (Broadcast)", callback_data="admin_panel"))

    bot.send_message(chat_id, "🥷 **Welcome to PDF Ninja!**\nPlease select a tool below:", parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["compress", "pdfjpg", "officepdf", "admin_panel", "main_menu"])
def menu_navigation(call):
    chat_id = call.message.chat.id
    
    if call.data == "admin_panel" and chat_id == ADMIN_ID:
        user_states[chat_id] = "waiting_for_broadcast"
        users_count = len(get_users())
        bot.send_message(chat_id, f"📢 **Broadcast Mode ON**\nTotal Users: {users_count}\n\nSend the message or photo to broadcast:")
        return

    if call.data == "main_menu":
        send_welcome(call.message)
        return

    user_states[chat_id] = call.data
    tool_names = {
        "compress": "Compress PDF",
        "pdfjpg": "PDF to JPG",
        "officepdf": "Word/Excel to PDF"
    }
    bot.send_message(chat_id, f"✅ **{tool_names.get(chat_id, 'Tool')}** selected!\nPlease send your file now.", parse_mode='Markdown')

@bot.message_handler(content_types=['text', 'document', 'photo', 'video'])
def handle_all_messages(message):
    chat_id = message.chat.id
    
    if user_states.get(chat_id) == "waiting_for_broadcast" and chat_id == ADMIN_ID:
        users = get_users()
        success = 0
        for u in users:
            try:
                bot.copy_message(chat_id=u, from_chat_id=chat_id, message_id=message.message_id)
                success += 1
            except:
                pass
        bot.send_message(chat_id, f"✅ Broadcast sent to {success} users successfully!")
        user_states[chat_id] = None
        return

    if message.content_type in ['document', 'photo']:
        task_type = user_states.get(chat_id)
        if not task_type:
            bot.send_message(chat_id, "❌ Please select a tool from /start first.")
            return

        bot.send_message(chat_id, "⏳ Processing your file via iLovePDF server...")

        try:
            # 1. Download file from Telegram
            if message.content_type == 'photo':
                file_info = bot.get_file(message.photo[-1].file_id)
                ext = ".jpg"
            else:
                file_info = bot.get_file(message.document.file_id)
                ext = os.path.splitext(message.document.file_name)[1]
                
            downloaded_file = bot.download_file(file_info.file_path)
            input_filename = f"input_{chat_id}{ext}"
            
            with open(input_filename, 'wb') as new_file:
                new_file.write(downloaded_file)

            # 2. iLovePDF API Authentication (Get Token)
            auth_res = requests.post("https://api.ilovepdf.com/v1/auth", json={
                "public_key": PUBLIC_KEY,
                "secret_key": SECRET_KEY
            })
            token = auth_res.json().get('token')

            if not token:
                bot.send_message(chat_id, "❌ API Authentication failed.")
                return

            headers = {"Authorization": f"Bearer {token}"}

            # 3. Start Task
            start_res = requests.get(f"https://api.ilovepdf.com/v1/start/{task_type}", headers=headers)
            task_data = start_res.json()
            server = task_data.get('server')
            task_id = task_data.get('task')

            # 4. Upload File
            files = {'file': open(input_filename, 'rb')}
            data = {'task': task_id}
            requests.post(f"https://{server}/v1/upload", headers=headers, data=data, files=files)

            # 5. Process Task
            requests.post(f"https://{server}/v1/process", headers=headers, json={
                "task": task_id,
                "tool": task_type
            })

            # 6. Download Processed File
            download_res = requests.get(f"https://{server}/v1/download/{task_id}", headers=headers)
            output_filename = f"output_{chat_id}.pdf" if task_type != "pdfjpg" else f"output_{chat_id}.zip"
            
            with open(output_filename, 'wb') as f:
                f.write(download_res.content)

            # 7. Send back to user
            with open(output_filename, 'rb') as doc:
                bot.send_document(chat_id, doc, caption="✅ Here is your processed file from PDF Ninja!")

            # Cleanup
            os.remove(input_filename)
            os.remove(output_filename)
            user_states[chat_id] = None

        except Exception as e:
            bot.send_message(chat_id, f"❌ Processing error occurred. Please try again with a valid file.")
            print(e)
    else:
        if chat_id != ADMIN_ID:
            bot.send_message(chat_id, "Please type /start to use the bot.")

if __name__ == "__main__":
    if not os.path.exists('output_files'):
        os.makedirs('output_files')
    keep_alive()
    bot.polling(none_stop=True)
