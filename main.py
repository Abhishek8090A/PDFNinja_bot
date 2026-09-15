import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyilovepdf import ILovePdf
from flask import Flask
from threading import Thread
import os

# --- Your API Keys and Token ---
TELEGRAM_TOKEN = '7912628972:AAFq72d_STTAJJBHzSLSlRHkAUxpQcft09M'
PUBLIC_KEY = 'project_public_9de017d12938f5eb5fe837197f34d925_Y2rbd6f01dd9c5063f8c898ec4a207f5739df'
SECRET_KEY = 'secret_key_d0b29d002254eddec1383aba2b6af74d_QGRTqdc4f93d5becf0e806598aeeb1448e18c'
ADMIN_ID = 6262854630

bot = telebot.TeleBot(TELEGRAM_TOKEN)
user_states = {}
user_files = {}

# --- Flask Server (24/7 Alive) ---
app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is running with Admin Panel!"
def run():
    app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()
# ----------------------------------------

# Function to save user data
def save_user(chat_id):
    users = set()
    if os.path.exists('users.txt'):
        with open('users.txt', 'r') as f:
            for line in f:
                users.add(line.strip())
    if str(chat_id) not in users:
        with open('users.txt', 'a') as f:
            f.write(f"{chat_id}\n")

# Function to get the list of users
def get_users():
    if not os.path.exists('users.txt'):
        return []
    with open('users.txt', 'r') as f:
        return [line.strip() for line in f]

# --- Mapping 30+ Tools to iLovePDF API ---
TASK_MAP = {
    "tool_compress": "compress", "tool_split": "split", "tool_rotate": "rotate", "tool_merge": "merge",
    "to_word": "officepdf", "to_excel": "officepdf", "to_ppt": "officepdf",
    "to_jpg": "imagepdf", "to_png": "imagepdf", "to_bmp": "imagepdf", "to_tiff": "imagepdf",
    "from_jpg": "pdfjpg", "from_txt": "extract"
}

# --- Main Menu ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    chat_id = message.chat.id
    save_user(chat_id) # Save user to database
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🛠 Edit PDF", callback_data="menu_edit"),
        InlineKeyboardButton("➡️ Convert TO PDF", callback_data="menu_to_pdf"),
        InlineKeyboardButton("⬅️ Convert FROM PDF", callback_data="menu_from_pdf")
    )
    
    # Show an extra button if the sender is the Admin
    if chat_id == ADMIN_ID:
        markup.add(InlineKeyboardButton("📢 Admin Panel (Broadcast)", callback_data="admin_panel"))

    bot.send_message(chat_id, "Hello! I am your All-in-One 30+ Tools PDF Bot.\nPlease select a tool:", reply_markup=markup)

# --- Sub-menus and Buttons ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("menu_") or call.data in ["main_menu", "admin_panel"])
def menu_navigation(call):
    chat_id = call.message.chat.id
    
    # --- Admin Panel Logic ---
    if call.data == "admin_panel" and chat_id == ADMIN_ID:
        user_states[chat_id] = "waiting_for_broadcast"
        users_count = len(get_users())
        bot.send_message(chat_id, f"📢 **Broadcast Mode ON**\nTotal Users: {users_count}\n\nPlease send the message, photo, or file you want to broadcast to everyone:")
        return

    # --- Menu for other tools ---
    elif call.data == "menu_edit":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("Merge", callback_data="tool_merge"),
            InlineKeyboardButton("Split", callback_data="tool_split"),
            InlineKeyboardButton("Compress", callback_data="tool_compress"),
            InlineKeyboardButton("Rotate", callback_data="tool_rotate"),
            InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")
        )
        bot.edit_message_text("🛠 **PDF Editing Tools:**", chat_id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

    elif call.data == "menu_to_pdf":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("Word to PDF", callback_data="to_word"),
            InlineKeyboardButton("Excel to PDF", callback_data="to_excel"),
            InlineKeyboardButton("PowerPoint to PDF", callback_data="to_ppt"),
            InlineKeyboardButton("JPG to PDF", callback_data="to_jpg"),
            InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")
        )
        bot.edit_message_text("➡️ **Convert to PDF from various formats:**", chat_id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

    elif call.data == "menu_from_pdf":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("PDF to JPG", callback_data="from_jpg"),
            InlineKeyboardButton("PDF to Text", callback_data="from_txt"),
            InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")
        )
        bot.edit_message_text("⬅️ **Convert FROM PDF to other formats:**", chat_id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

    elif call.data == "main_menu":
        send_welcome(call.message)

@bot.callback_query_handler(func=lambda call: not call.data.startswith("menu_") and call.data not in ["main_menu", "admin_panel"])
def select_tool(call):
    chat_id = call.message.chat.id
    tool = call.data
    if tool == "tool_merge":
        user_states[chat_id] = "merge"
        user_files[chat_id] = []
        bot.send_message(chat_id, "📚 Please send all the PDF files you want to merge. Type /done when you have sent all of them.")
    else:
        api_task = TASK_MAP.get(tool, "officepdf")
        user_states[chat_id] = api_task
        bot.send_message(chat_id, f"✅ Tool selected! Please send your file (.pdf, .docx, .jpg, etc.) here.")

# --- On receiving any message (Text, Document, Photo, Video) ---
@bot.message_handler(content_types=['text', 'document', 'photo', 'video'])
def handle_all_messages(message):
    chat_id = message.chat.id
    
    # 1. If admin is broadcasting
    if user_states.get(chat_id) == "waiting_for_broadcast" and chat_id == ADMIN_ID:
        users = get_users()
        success = 0
        fail = 0
        bot.send_message(chat_id, "⏳ Sending broadcast...")
        
        for u in users:
            try:
                bot.copy_message(chat_id=u, from_chat_id=chat_id, message_id=message.message_id)
                success += 1
            except:
                fail += 1
                
        bot.send_message(chat_id, f"✅ Broadcast complete!\nSuccessfully sent: {success}\nFailed: {fail}")
        user_states[chat_id] = None # Turn off broadcast mode
        return

    # 2. If user is sending a file to convert (only photo or document)
    if message.content_type in ['document', 'photo']:
        task_name = user_states.get(chat_id)
        
        if not task_name:
            bot.send_message(chat_id, "❌ Please select a tool from the menu (/start) first.")
            return

        bot.send_message(chat_id, "⏳ File is being processed on the server, please wait...")

        try:
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

            if task_name == "merge":
                user_files.setdefault(chat_id, []).append(input_filename)
                bot.send_message(chat_id, f"✅ File received! Total {len(user_files[chat_id])} files. Send more or type /done.")
                return

            ilovepdf = ILovePdf(PUBLIC_KEY, SECRET_KEY)
            task = ilovepdf.new_task(task_name)
            task.add_file(input_filename)
            task.set_output_folder('output_files')
            task.execute()
            task.download()
            
            output_filename = task.downloaded_filename
            output_path = f"output_files/{output_filename}"
            
            with open(output_path, 'rb') as doc:
                bot.send_document(chat_id, doc, caption="✅ Here is your processed file!")
            
            os.remove(input_filename)
            os.remove(output_path)
            user_states[chat_id] = None

        except Exception as e:
            bot.send_message(chat_id, f"❌ Something went wrong! Please check if your file is in the correct format.")
    else:
        # If user sends text without selecting a tool
        if chat_id != ADMIN_ID or user_states.get(chat_id) != "waiting_for_broadcast":
             bot.send_message(chat_id, "Please type /start to use the tools.")

@bot.message_handler(commands=['done'])
def merge_done(message):
    chat_id = message.message.chat.id if hasattr(message, 'message') else message.chat.id
    if user_states.get(chat_id) == "merge" and len(user_files.get(chat_id, [])) > 1:
        bot.send_message(chat_id, "⏳ Merging PDF files...")
        try:
            ilovepdf = ILovePdf(PUBLIC_KEY, SECRET_KEY)
            task = ilovepdf.new_task('merge')
            for file in user_files[chat_id]:
                task.add_file(file)
            task.set_output_folder('output_files')
            task.execute()
            task.download()
            
            output_path = f"output_files/{task.downloaded_filename}"
            with open(output_path, 'rb') as doc:
                bot.send_document(chat_id, doc, caption="✅ All your PDFs have been merged successfully!")
                
            for file in user_files[chat_id]:
                os.remove(file)
            os.remove(output_path)
            user_states[chat_id] = None
            user_files[chat_id] = []
        except:
            bot.send_message(chat_id, "❌ Error occurred while merging.")
    elif user_states.get(chat_id) == "merge":
        bot.send_message(chat_id, "Please send at least 2 files to merge!")

if __name__ == "__main__":
    if not os.path.exists('output_files'):
        os.makedirs('output_files')
    keep_alive()
    bot.polling(none_stop=True)
