import logging
import re
import json
import os
import time
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

# ============================================
# ТВОИ ДАННЫЕ
# ============================================
import logging
import re
import json
import os
import time
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler
from dotenv import load_dotenv  # Эту строку ДОБАВИТЬ

# Загружаем переменные из .env файла
load_dotenv()

# ============================================
# ТВОИ ДАННЫЕ (теперь из файла .env)
# ============================================
TOKEN = os.getenv('BOT_TOKEN')
MY_ID = int(os.getenv('ADMIN_ID', '0'))

if not TOKEN:
    raise ValueError("❌ ОШИБКА: Токен не найден! Создай файл .env с BOT_TOKEN=...")

# ============================================
# НАСТРОЙКИ ФИЛЬТРОВ (ПО УМОЛЧАНИЮ)
# ============================================
DEFAULT_SETTINGS = {
    'filter_links': True,
    'filter_stickers': True,
    'filter_caps': True,
    'filter_sticker_flood': True,
    'filter_swear': True,
    'caps_limit': 50,
    'min_length': 5,
    'sticker_flood_limit': 5,
    'sticker_flood_time': 60
}

SETTINGS_FILE = 'bot_settings.json'
sticker_tracker = defaultdict(list)

# ============================================
# СПИСОК МАТОВ
# ============================================
SWEAR_WORDS = [
    'хуй', 'пизд', 'ебл', 'еба', 'ёб', 'бля', 'блять', 'сука', 'пиздец',
    'нахер', 'нафиг', 'похер', 'хер', 'мудак', 'гандон', 'пидор', 'педик',
    'шлюх', 'простит', 'далбаеб', 'долбоеб', 'ебан', 'ебну', 'раком',
    'залуп', 'манда', 'сперм', 'мошонк', 'яичк', 'член', 'пенис', 'вагин',
    'трах', 'секс', 'fuck', 'shit', 'asshole', 'bitch', 'whore', 'slut',
]

# ============================================
# ЗАГРУЗКА НАСТРОЕК
# ============================================
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

chat_settings = load_settings()

# ============================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def get_chat_settings(chat_id):
    chat_id_str = str(chat_id)
    if chat_id_str not in chat_settings:
        chat_settings[chat_id_str] = DEFAULT_SETTINGS.copy()
        save_settings(chat_settings)
    return chat_settings[chat_id_str]

# ============================================
# ФУНКЦИИ ПРОВЕРКИ
# ============================================
def is_tg_link(text):
    if not text:
        return False
    return 't.me/' in text.lower()

def is_bad_sticker(sticker):
    if not sticker or not sticker.set_name:
        return False
    
    name = sticker.set_name.lower()
    bad_words = ['nsfw', '18+', 'sex', 'porn', 'adult', 'hentai', 'xxx']
    
    for word in bad_words:
        if word in name:
            print(f"🚫 Найден 18+ стикер: {word}")
            return True
    return False

def is_too_many_caps(text, limit=50, min_length=5):
    if not text or len(text) < min_length:
        return False
    
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    
    caps = sum(1 for c in letters if c.isupper())
    percent = (caps / len(letters)) * 100
    
    print(f"📊 Проверка капса: {percent:.1f}% (лимит {limit}%)")
    return percent > limit

def contains_swear(text):
    if not text:
        return False
    
    text_lower = text.lower()
    for word in SWEAR_WORDS:
        if word in text_lower:
            print(f"🤬 Найден мат: {word}")
            return True
    return False

def check_sticker_flood(user_id, chat_id, limit=5, time_window=60):
    key = f"{user_id}:{chat_id}"
    current_time = time.time()
    
    sticker_tracker[key] = [t for t in sticker_tracker[key] if current_time - t < time_window]
    sticker_tracker[key].append(current_time)
    
    return len(sticker_tracker[key]) > limit

# ============================================
# НОВАЯ КОМАНДА ДЛЯ УДАЛЕНИЯ ЧАТА
# ============================================
async def delchat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список чатов для удаления"""
    user = update.effective_user
    
    # Проверяем, что команду использует админ
    if user.id != MY_ID:
        await update.message.reply_text("❌ Эта команда только для админа!")
        return
    
    if not chat_settings:
        await update.message.reply_text("📭 Нет сохраненных чатов.")
        return
    
    text = "🗑 *Выбери чат для удаления:*\n\n"
    keyboard = []
    
    i = 1
    for chat_id_str in list(chat_settings.keys()):
        try:
            chat = await context.bot.get_chat(int(chat_id_str))
            chat_name = chat.title or "Личный чат"
            text += f"{i}. {chat_name}\n"
            keyboard.append([InlineKeyboardButton(f"❌ {chat_name}", callback_data=f"delchat_{chat_id_str}")])
        except:
            # Если чат недоступен, показываем просто ID
            text += f"{i}. ID: {chat_id_str} (недоступен)\n"
            keyboard.append([InlineKeyboardButton(f"❌ ID: {chat_id_str[:10]}...", callback_data=f"delchat_{chat_id_str}")])
        i += 1
    
    keyboard.append([InlineKeyboardButton("🔙 ОТМЕНА", callback_data="delchat_cancel")])
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ============================================
# КОМАНДЫ
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"╔════════════════════════╗\n"
        f"║   *ДОБРО ПОЖАЛОВАТЬ*   ║\n"
        f"║      👋 {user.first_name}      ║\n"
        f"╚════════════════════════╝\n\n"
        f"*🤖 ANTISPAM БОТ*\n"
        f"Я защищаю группы от спама\n\n"
        f"*🔍 ЧТО ПРОВЕРЯЮ:*\n"
        f"• 🔗 Ссылки на Telegram\n"
        f"• 🔞 18+ стикеры\n"
        f"• 🔠 Сообщения КАПСОМ\n"
        f"• 🎭 Флуд стикерами\n"
        f"• 🤬 Нецензурная лексика\n\n"
        f"*📋 КОМАНДЫ:*\n"
        f"╔══════════════════╗\n"
        f"║  📚 /help        ║\n"
        f"║  📊 /status      ║\n"
        f"║  ⚙️ /settings    ║\n"
        f"║  🗑️ /delchat     ║\n"
        f"╚══════════════════╝"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"╔════════════════╗\n"
        f"║   *📚 ПОМОЩЬ*   ║\n"
        f"╚════════════════╝\n\n"
        f"*КАК ИСПОЛЬЗОВАТЬ:*\n"
        f"1️⃣ Добавь бота в группу\n"
        f"2️⃣ Сделай его администратором\n"
        f"3️⃣ Настрой фильтры через /settings\n\n"
        f"*👑 АДМИНЫ:*\n"
        f"Админы группы могут писать всё\n\n"
        f"*🗑️ УДАЛЕНИЕ ЧАТОВ:*\n"
        f"Используй /delchat чтобы удалить чат из настроек"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"╔════════════════╗\n║   *📊 СТАТУС*   ║\n╚════════════════╝\n\n"
    
    found_chats = False
    for chat_id_str, settings in chat_settings.items():
        try:
            chat = await context.bot.get_chat(int(chat_id_str))
            text += f"*Чат:* {chat.title}\n"
            text += f"• 🔗 Ссылки: {'✅' if settings.get('filter_links', True) else '❌'}\n"
            text += f"• 🔞 18+ стикеры: {'✅' if settings.get('filter_stickers', True) else '❌'}\n"
            text += f"• 🔠 Капс: {'✅' if settings.get('filter_caps', True) else '❌'} ({settings.get('caps_limit', 50)}%)\n"
            text += f"• 🎭 Флуд: {'✅' if settings.get('filter_sticker_flood', True) else '❌'} (макс. {settings.get('sticker_flood_limit', 5)})\n"
            text += f"• 🤬 Маты: {'✅' if settings.get('filter_swear', True) else '❌'}\n\n"
            found_chats = True
        except:
            pass
    
    if not found_chats:
        text += "Бот еще не добавлен в группы."
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📋 ВЫБЕРИ ЧАТ", callback_data="no_action")], []]
    
    for chat_id_str in chat_settings.keys():
        try:
            chat = await context.bot.get_chat(int(chat_id_str))
            keyboard.append([InlineKeyboardButton(f"⚙️ {chat.title}", callback_data=f"chat_{chat_id_str}")])
        except:
            pass
    
    if len(keyboard) == 2:
        await update.message.reply_text("❌ Бот еще не добавлен ни в один чат!", parse_mode="Markdown")
        return
    
    await update.message.reply_text("⚙️ *НАСТРОЙКИ*\n\nВыбери чат:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_chat_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: str):
    query = update.callback_query
    settings = get_chat_settings(chat_id)
    
    try:
        chat = await context.bot.get_chat(int(chat_id))
        chat_title = chat.title
    except:
        chat_title = "Неизвестный чат"
    
    keyboard = [
        [InlineKeyboardButton(f"{'✅' if settings.get('filter_links', True) else '❌'} 🔗 Ссылки", callback_data=f"toggle_links_{chat_id}")],
        [InlineKeyboardButton(f"{'✅' if settings.get('filter_stickers', True) else '❌'} 🔞 18+ стикеры", callback_data=f"toggle_stickers_{chat_id}")],
        [InlineKeyboardButton(f"{'✅' if settings.get('filter_caps', True) else '❌'} 🔠 Капс ({settings.get('caps_limit', 50)}%)", callback_data=f"toggle_caps_{chat_id}")],
        [InlineKeyboardButton(f"{'✅' if settings.get('filter_sticker_flood', True) else '❌'} 🎭 Флуд (макс. {settings.get('sticker_flood_limit', 5)})", callback_data=f"toggle_flood_{chat_id}")],
        [InlineKeyboardButton(f"{'✅' if settings.get('filter_swear', True) else '❌'} 🤬 Маты", callback_data=f"toggle_swear_{chat_id}")],
        [InlineKeyboardButton("📊 ЛИМИТ КАПСА", callback_data=f"caps_limit_{chat_id}")],
        [InlineKeyboardButton("🎭 ЛИМИТ ФЛУДА", callback_data=f"flood_limit_{chat_id}")],
        [InlineKeyboardButton("🔙 НАЗАД", callback_data="back_to_chats")]
    ]
    
    await query.edit_message_text(f"⚙️ *{chat_title}*\n\nНажми для включения/выключения:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ============================================
# ОБРАБОТКА КНОПОК
# ============================================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    print(f"🔘 Нажата кнопка: {data}")
    
    if data == "back_to_chats":
        keyboard = [[InlineKeyboardButton("📋 ВЫБЕРИ ЧАТ", callback_data="no_action")], []]
        for chat_id_str in chat_settings.keys():
            try:
                chat = await context.bot.get_chat(int(chat_id_str))
                keyboard.append([InlineKeyboardButton(f"⚙️ {chat.title}", callback_data=f"chat_{chat_id_str}")])
            except:
                pass
        await query.edit_message_text("⚙️ *НАСТРОЙКИ*\n\nВыбери чат:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
    elif data == "delchat_cancel":
        await query.edit_message_text("❌ Удаление отменено.")
    
    elif data.startswith("delchat_"):
        chat_id = data.replace("delchat_", "")
        if chat_id in chat_settings:
            del chat_settings[chat_id]
            save_settings(chat_settings)
            await query.edit_message_text(f"✅ Чат удален из настроек!")
            print(f"🗑️ Удален чат {chat_id}")
        else:
            await query.edit_message_text("❌ Чат не найден.")
    
    elif data.startswith("chat_"):
        chat_id = data.replace("chat_", "")
        await show_chat_settings(update, context, chat_id)
    
    elif data.startswith("toggle_"):
        parts = data.split("_")
        action = parts[1]
        chat_id = parts[2]
        settings = get_chat_settings(chat_id)
        
        if action == "links":
            settings['filter_links'] = not settings.get('filter_links', True)
        elif action == "stickers":
            settings['filter_stickers'] = not settings.get('filter_stickers', True)
        elif action == "caps":
            settings['filter_caps'] = not settings.get('filter_caps', True)
        elif action == "flood":
            settings['filter_sticker_flood'] = not settings.get('filter_sticker_flood', True)
        elif action == "swear":
            settings['filter_swear'] = not settings.get('filter_swear', True)
        
        save_settings(chat_settings)
        await show_chat_settings(update, context, chat_id)
    
    elif data.startswith("caps_limit_"):
        chat_id = data.replace("caps_limit_", "")
        keyboard = [
            [InlineKeyboardButton("30%", callback_data=f"set_caps_{chat_id}_30")],
            [InlineKeyboardButton("50%", callback_data=f"set_caps_{chat_id}_50")],
            [InlineKeyboardButton("70%", callback_data=f"set_caps_{chat_id}_70")],
            [InlineKeyboardButton("80%", callback_data=f"set_caps_{chat_id}_80")],
            [InlineKeyboardButton("🔙 НАЗАД", callback_data=f"chat_{chat_id}")]
        ]
        await query.edit_message_text("📊 *ЛИМИТ КАПСА*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
    elif data.startswith("flood_limit_"):
        chat_id = data.replace("flood_limit_", "")
        keyboard = [
            [InlineKeyboardButton("3 стикера", callback_data=f"set_flood_{chat_id}_3")],
            [InlineKeyboardButton("5 стикеров", callback_data=f"set_flood_{chat_id}_5")],
            [InlineKeyboardButton("7 стикеров", callback_data=f"set_flood_{chat_id}_7")],
            [InlineKeyboardButton("10 стикеров", callback_data=f"set_flood_{chat_id}_10")],
            [InlineKeyboardButton("🔙 НАЗАД", callback_data=f"chat_{chat_id}")]
        ]
        await query.edit_message_text("🎭 *ЛИМИТ ФЛУДА*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
    elif data.startswith("set_caps_"):
        parts = data.split("_")
        chat_id = parts[2]
        limit = int(parts[3])
        settings = get_chat_settings(chat_id)
        settings['caps_limit'] = limit
        save_settings(chat_settings)
        await show_chat_settings(update, context, chat_id)
    
    elif data.startswith("set_flood_"):
        parts = data.split("_")
        chat_id = parts[2]
        limit = int(parts[3])
        settings = get_chat_settings(chat_id)
        settings['sticker_flood_limit'] = limit
        save_settings(chat_settings)
        await show_chat_settings(update, context, chat_id)

# ============================================
# ПРОВЕРКА СООБЩЕНИЙ
# ============================================
async def check_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message:
        return
    
    user = message.from_user
    chat = message.chat
    
    if user.is_bot or user.id == MY_ID:
        return
    
    try:
        chat_member = await context.bot.get_chat_member(chat.id, user.id)
        if chat_member.status in ['administrator', 'creator']:
            return
    except:
        pass
    
    settings = get_chat_settings(chat.id)
    
    # Проверка стикеров
    if message.sticker:
        if settings.get('filter_sticker_flood', True):
            if check_sticker_flood(user.id, chat.id, settings.get('sticker_flood_limit', 5)):
                await message.delete()
                await message.reply_text(f"@{user.username} ❗ *НЕ ФЛУДИ СТИКЕРАМИ!*", parse_mode="Markdown")
                return
        
        if settings.get('filter_stickers', True) and is_bad_sticker(message.sticker):
            await message.delete()
            await message.reply_text(f"@{user.username} ❗ *18+ СТИКЕРЫ ЗАПРЕЩЕНЫ*", parse_mode="Markdown")
            return
    
    # Проверка текста
    if message.text:
        if settings.get('filter_links', True) and is_tg_link(message.text):
            await message.delete()
            await message.reply_text(f"@{user.username} ❗ *ССЫЛКИ ЗАПРЕЩЕНЫ*", parse_mode="Markdown")
            return
        
        if settings.get('filter_swear', True) and contains_swear(message.text):
            await message.delete()
            await message.reply_text(f"@{user.username} ❗ *МАТЫ ЗАПРЕЩЕНЫ*", parse_mode="Markdown")
            return
        
        if settings.get('filter_caps', True) and is_too_many_caps(message.text, settings.get('caps_limit', 50)):
            await message.delete()
            await message.reply_text(f"@{user.username} ❗ *НЕ КРИЧИ!*", parse_mode="Markdown")
            return
    
    # Проверка подписей
    if message.caption:
        if settings.get('filter_links', True) and is_tg_link(message.caption):
            await message.delete()
            await message.reply_text(f"@{user.username} ❗ *ССЫЛКИ ЗАПРЕЩЕНЫ*", parse_mode="Markdown")
            return
        
        if settings.get('filter_swear', True) and contains_swear(message.caption):
            await message.delete()
            await message.reply_text(f"@{user.username} ❗ *МАТЫ ЗАПРЕЩЕНЫ*", parse_mode="Markdown")
            return
        
        if settings.get('filter_caps', True) and is_too_many_caps(message.caption, settings.get('caps_limit', 50)):
            await message.delete()
            await message.reply_text(f"@{user.username} ❗ *НЕ КРИЧИ!*", parse_mode="Markdown")
            return

# ============================================
# НОВЫЙ ЧАТ
# ============================================
async def new_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.new_chat_members:
        return
    
    for member in message.new_chat_members:
        if member.id == context.bot.id:
            chat_id = str(message.chat.id)
            if chat_id not in chat_settings:
                chat_settings[chat_id] = DEFAULT_SETTINGS.copy()
                save_settings(chat_settings)
            
            try:
                await context.bot.send_message(MY_ID, f"✅ Бот добавлен в чат: {message.chat.title}")
            except:
                pass

# ============================================
# ЗАПУСК
# ============================================
def main():
    print("=" * 60)
    print("╔══════════════════════════╗")
    print("║  ANTISPAM БОТ ЗАПУЩЕН   ║")
    print("╚══════════════════════════╝")
    print("=" * 60)
    print(f"📌 Токен: {TOKEN[:15]}...")
    print(f"📌 Твой ID: {MY_ID}")
    print(f"📌 Чатов в настройках: {len(chat_settings)}")
    print("=" * 60)
    print("📋 Новые команды:")
    print("   /delchat - удалить чат из настроек")
    print("=" * 60)
    print("✅ Бот работает! Нажми Ctrl+C для остановки")
    print("=" * 60)
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("settings", settings_command))
    app.add_handler(CommandHandler("delchat", delchat_command))  # Новая команда
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO, check_group))
    app.add_handler(MessageHandler(filters.Sticker.ALL, check_group))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_chat_member))
    
    app.run_polling()

if __name__ == '__main__':
    main()