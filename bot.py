import os
import logging
import json
import time
from collections import defaultdict
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler, CallbackQueryHandler

# ============================================
# ЗАГРУЗКА ПЕРЕМЕННЫХ ИЗ .env
# ============================================
load_dotenv()

TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = os.getenv('ADMIN_ID')

if not TOKEN:
    raise ValueError("❌ ОШИБКА: Токен не найден! Создай файл .env с BOT_TOKEN=...")

if not ADMIN_ID:
    raise ValueError("❌ ОШИБКА: ADMIN_ID не найден! Создай файл .env с ADMIN_ID=...")

try:
    ADMIN_ID = int(ADMIN_ID)
except:
    raise ValueError("❌ ОШИБКА: ADMIN_ID должен быть числом!")

# ============================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ============================================
# ФАЙЛЫ ДЛЯ ХРАНЕНИЯ
# ============================================
SETTINGS_FILE = 'bot_settings.json'
sticker_tracker = defaultdict(list)

# ============================================
# НАСТРОЙКИ ПО УМОЛЧАНИЮ
# ============================================
DEFAULT_SETTINGS = {
    'filter_links': True,
    'filter_stickers': True,
    'filter_caps': True,
    'filter_flood': True,
    'filter_swear': True,
    'caps_limit': 50,
    'flood_limit': 5,
    'chat_creator': 0,
    'custom_admins': [],
    'chat_title': '',
    'added_date': ''
}

# Загружаем настройки
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_settings():
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(chat_settings, f, ensure_ascii=False, indent=2)
    except:
        pass

chat_settings = load_settings()

# ============================================
# ФУНКЦИИ ПРОВЕРКИ
# ============================================
def has_tg_link(text):
    if not text:
        return False
    return 't.me/' in text.lower()

def is_18_sticker(sticker):
    if not sticker or not sticker.set_name:
        return False
    name = sticker.set_name.lower()
    bad = ['nsfw', '18+', 'sex', 'porn', 'adult', 'hentai', 'xxx']
    return any(word in name for word in bad)

def is_caps(text, limit=50):
    if not text or len(text) < 5:
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    caps = sum(1 for c in letters if c.isupper())
    return (caps / len(letters)) * 100 > limit

def has_swear(text):
    if not text:
        return False
    text = text.lower()
    bad_words = ['хуй', 'пизд', 'ебл', 'бля', 'сука', 'fuck', 'shit']
    return any(word in text for word in bad_words)

def is_flood(user_id, chat_id, limit=5):
    key = f"{user_id}:{chat_id}"
    now = time.time()
    sticker_tracker[key] = [t for t in sticker_tracker.get(key, []) if now - t < 60]
    if key not in sticker_tracker:
        sticker_tracker[key] = []
    sticker_tracker[key].append(now)
    return len(sticker_tracker[key]) > limit

# ============================================
# ПРОВЕРКА АДМИНА
# ============================================
def is_admin(chat_id, user_id):
    chat = chat_settings.get(str(chat_id), {})
    if user_id == ADMIN_ID:
        return True
    if chat.get('chat_creator') == user_id:
        return True
    if user_id in chat.get('custom_admins', []):
        return True
    return False

# ============================================
# КОМАНДА START
# ============================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"╔════════════════════════╗\n"
        f"║   🎯 ДОБРО ПОЖАЛОВАТЬ  ║\n"
        f"║      👤 {user.first_name}      ║\n"
        f"╚════════════════════════╝\n\n"
        f"🤖 *АНТИСПАМ БОТ*\n"
        f"Защищаю группы от:\n"
        f"• 🔗 Ссылки на Telegram\n"
        f"• 🔞 18+ стикеры\n"
        f"• 📢 КАПС (более 50%)\n"
        f"• 🎭 Флуд стикерами\n"
        f"• 🤬 Маты\n\n"
        f"📋 *ДОСТУПНЫЕ КОМАНДЫ:*\n"
        f"╔══════════════════╗\n"
        f"║  ❓ /help        ║\n"
        f"║  📊 /status     ║\n"
        f"║  ⚙️ /settings   ║\n"
        f"║  👑 /admin      ║\n"
        f"║  🗑️ /delchat    ║\n"
        f"╚══════════════════╝"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ============================================
# КОМАНДА HELP
# ============================================
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"╔════════════════╗\n"
        f"║   ❓ ПОМОЩЬ    ║\n"
        f"╚════════════════╝\n\n"
        f"*КАК ИСПОЛЬЗОВАТЬ:*\n"
        f"1️⃣ Добавь бота в группу\n"
        f"2️⃣ Сделай его администратором\n"
        f"3️⃣ Настрой фильтры через /settings\n\n"
        f"*👑 АДМИНЫ:*\n"
        f"• /admin - управление админами\n"
        f"• Тот, кто добавил бота - главный админ\n"
        f"• Можно добавлять других админов\n\n"
        f"*⚙️ НАСТРОЙКИ:*\n"
        f"• /settings - включить/выключить фильтры\n"
        f"• /status - статус всех чатов\n"
        f"• /delchat - удалить чат"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ============================================
# КОМАНДА STATUS
# ============================================
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"╔════════════════╗\n║   📊 СТАТУС   ║\n╚════════════════╝\n\n"
    
    found = False
    for chat_id, settings in chat_settings.items():
        if not settings.get('chat_title'):
            continue
        try:
            chat = await context.bot.get_chat(int(chat_id))
            title = chat.title or "Группа"
            text += f"*📌 {title}*\n"
            text += f"• 🔗 Ссылки: {'✅' if settings.get('filter_links', True) else '❌'}\n"
            text += f"• 🔞 18+: {'✅' if settings.get('filter_stickers', True) else '❌'}\n"
            text += f"• 📢 КАПС: {'✅' if settings.get('filter_caps', True) else '❌'}\n"
            text += f"• 🎭 Флуд: {'✅' if settings.get('filter_flood', True) else '❌'}\n"
            text += f"• 🤬 Маты: {'✅' if settings.get('filter_swear', True) else '❌'}\n\n"
            found = True
        except:
            pass
    
    if not found:
        text += "❌ Бот не добавлен ни в одну группу"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ============================================
# КОМАНДА SETTINGS
# ============================================
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    user = update.effective_user
    chat_id = str(update.effective_chat.id)
    
    if not is_admin(chat_id, user.id):
        await update.message.reply_text("❌ Только админы могут настраивать фильтры!")
        return
    
    settings = chat_settings.get(chat_id, DEFAULT_SETTINGS.copy())
    
    keyboard = [
        [InlineKeyboardButton(f"{'✅' if settings.get('filter_links', True) else '❌'} 🔗 Ссылки", callback_data="toggle_links")],
        [InlineKeyboardButton(f"{'✅' if settings.get('filter_stickers', True) else '❌'} 🔞 18+ стикеры", callback_data="toggle_stickers")],
        [InlineKeyboardButton(f"{'✅' if settings.get('filter_caps', True) else '❌'} 📢 КАПС", callback_data="toggle_caps")],
        [InlineKeyboardButton(f"{'✅' if settings.get('filter_flood', True) else '❌'} 🎭 Флуд", callback_data="toggle_flood")],
        [InlineKeyboardButton(f"{'✅' if settings.get('filter_swear', True) else '❌'} 🤬 Маты", callback_data="toggle_swear")]
    ]
    
    await update.message.reply_text(
        "⚙️ *НАСТРОЙКИ ФИЛЬТРОВ*\n\nНажми чтобы включить/выключить:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ============================================
# КОМАНДА ADMIN
# ============================================
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        await update.message.reply_text("❌ Эта команда работает только в группах!")
        return
    
    user = update.effective_user
    chat_id = str(update.effective_chat.id)
    
    if not is_admin(chat_id, user.id):
        await update.message.reply_text("❌ Только админы могут управлять админами!")
        return
    
    settings = chat_settings.get(chat_id, DEFAULT_SETTINGS.copy())
    admins = settings.get('custom_admins', [])
    
    text = f"👑 *АДМИНИСТРАТОРЫ*\n\n"
    text += f"👤 Главный админ: `{settings.get('chat_creator', 'неизвестен')}`\n"
    if admins:
        text += f"\n👥 Дополнительные:\n"
        for a in admins:
            text += f"• `{a}`\n"
    else:
        text += f"\n❌ Нет дополнительных админов"
    
    keyboard = [
        [InlineKeyboardButton("➕ ДОБАВИТЬ АДМИНА", callback_data="add_admin")],
        [InlineKeyboardButton("➖ УДАЛИТЬ АДМИНА", callback_data="remove_admin")]
    ]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ============================================
# КОМАНДА DELCHAT
# ============================================
async def delchat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ Только главный админ может удалять чаты!")
        return
    
    if not chat_settings:
        await update.message.reply_text("📭 Нет сохраненных чатов")
        return
    
    keyboard = []
    for chat_id, settings in chat_settings.items():
        title = settings.get('chat_title', 'Неизвестный чат')
        keyboard.append([InlineKeyboardButton(f"❌ {title}", callback_data=f"del_{chat_id}")])
    
    await update.message.reply_text(
        "🗑 *ВЫБЕРИ ЧАТ ДЛЯ УДАЛЕНИЯ:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ============================================
# ОБРАБОТКА КНОПОК
# ============================================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user = query.from_user
    chat_id = str(update.effective_chat.id)
    
    # НАСТРОЙКИ
    if data.startswith("toggle_"):
        if not is_admin(chat_id, user.id):
            await query.edit_message_text("❌ Нет прав!")
            return
        
        settings = chat_settings.get(chat_id, DEFAULT_SETTINGS.copy())
        
        if data == "toggle_links":
            settings['filter_links'] = not settings.get('filter_links', True)
        elif data == "toggle_stickers":
            settings['filter_stickers'] = not settings.get('filter_stickers', True)
        elif data == "toggle_caps":
            settings['filter_caps'] = not settings.get('filter_caps', True)
        elif data == "toggle_flood":
            settings['filter_flood'] = not settings.get('filter_flood', True)
        elif data == "toggle_swear":
            settings['filter_swear'] = not settings.get('filter_swear', True)
        
        chat_settings[chat_id] = settings
        save_settings()
        
        keyboard = [
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_links', True) else '❌'} 🔗 Ссылки", callback_data="toggle_links")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_stickers', True) else '❌'} 🔞 18+ стикеры", callback_data="toggle_stickers")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_caps', True) else '❌'} 📢 КАПС", callback_data="toggle_caps")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_flood', True) else '❌'} 🎭 Флуд", callback_data="toggle_flood")],
            [InlineKeyboardButton(f"{'✅' if settings.get('filter_swear', True) else '❌'} 🤬 Маты", callback_data="toggle_swear")]
        ]
        
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))
    
    # АДМИНЫ
    elif data == "add_admin":
        context.user_data['action'] = ('add_admin', chat_id)
        await query.edit_message_text(
            "📝 *ДОБАВЛЕНИЕ АДМИНА*\n\n"
            "Отправь ID пользователя:",
            parse_mode="Markdown"
        )
    
    elif data == "remove_admin":
        settings = chat_settings.get(chat_id, {})
        admins = settings.get('custom_admins', [])
        
        if not admins:
            await query.edit_message_text("❌ Нет админов для удаления")
            return
        
        keyboard = []
        for a in admins:
            keyboard.append([InlineKeyboardButton(f"❌ {a}", callback_data=f"del_admin_{a}")])
        
        await query.edit_message_text(
            "👥 *ВЫБЕРИ АДМИНА:*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    elif data.startswith("del_admin_"):
        admin_id = int(data.replace("del_admin_", ""))
        settings = chat_settings.get(chat_id, {})
        if 'custom_admins' in settings and admin_id in settings['custom_admins']:
            settings['custom_admins'].remove(admin_id)
            chat_settings[chat_id] = settings
            save_settings()
            await query.edit_message_text(f"✅ Админ {admin_id} удален!")
    
    # УДАЛЕНИЕ ЧАТА
    elif data.startswith("del_"):
        del_chat_id = data.replace("del_", "")
        if del_chat_id in chat_settings:
            title = chat_settings[del_chat_id].get('chat_title', 'Неизвестный чат')
            del chat_settings[del_chat_id]
            save_settings()
            await query.edit_message_text(f"✅ Чат {title} удален!")

# ============================================
# ОБРАБОТКА ТЕКСТА (ДЛЯ ДОБАВЛЕНИЯ АДМИНОВ)
# ============================================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    
    if 'action' not in context.user_data:
        return
    
    action, chat_id = context.user_data['action']
    user_id = update.effective_user.id
    
    if action == 'add_admin' and user_id == ADMIN_ID:
        try:
            new_admin = int(update.message.text.strip())
            settings = chat_settings.get(chat_id, DEFAULT_SETTINGS.copy())
            
            if 'custom_admins' not in settings:
                settings['custom_admins'] = []
            
            if new_admin in settings['custom_admins']:
                await update.message.reply_text("❌ Уже админ!")
            else:
                settings['custom_admins'].append(new_admin)
                chat_settings[chat_id] = settings
                save_settings()
                await update.message.reply_text(f"✅ Админ {new_admin} добавлен!")
        except:
            await update.message.reply_text("❌ Отправь ID числом!")
        
        del context.user_data['action']

# ============================================
# ПРОВЕРКА СООБЩЕНИЙ В ГРУППАХ
# ============================================
async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == "private":
        return
    
    msg = update.message
    if not msg:
        return
    
    user = msg.from_user
    chat = msg.chat
    chat_id = str(chat.id)
    
    if user.is_bot:
        return
    
    # Сохраняем название чата
    if chat_id not in chat_settings:
        chat_settings[chat_id] = DEFAULT_SETTINGS.copy()
        chat_settings[chat_id]['chat_title'] = chat.title
        chat_settings[chat_id]['added_date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_settings()
    
    # Проверка админов
    if is_admin(chat_id, user.id):
        return
    
    try:
        member = await context.bot.get_chat_member(chat.id, user.id)
        if member.status in ['administrator', 'creator']:
            return
    except:
        pass
    
    settings = chat_settings.get(chat_id, DEFAULT_SETTINGS.copy())
    
    # Проверка стикеров
    if msg.sticker:
        if settings.get('filter_flood', True) and is_flood(user.id, chat.id, settings.get('flood_limit', 5)):
            try:
                await msg.delete()
                await msg.reply_text(f"@{user.username} ❌ НЕ ФЛУДИ СТИКЕРАМИ!")
            except:
                pass
            return
        
        if settings.get('filter_stickers', True) and is_18_sticker(msg.sticker):
            try:
                await msg.delete()
                await msg.reply_text(f"@{user.username} ❌ 18+ СТИКЕРЫ ЗАПРЕЩЕНЫ!")
            except:
                pass
            return
    
    # Проверка текста
    text = msg.text or msg.caption
    if text:
        if settings.get('filter_links', True) and has_tg_link(text):
            try:
                await msg.delete()
                await msg.reply_text(f"@{user.username} ❌ ССЫЛКИ НА TELEGRAM ЗАПРЕЩЕНЫ!")
            except:
                pass
            return
        
        if settings.get('filter_swear', True) and has_swear(text):
            try:
                await msg.delete()
                await msg.reply_text(f"@{user.username} ❌ МАТЫ ЗАПРЕЩЕНЫ!")
            except:
                pass
            return
        
        if settings.get('filter_caps', True) and is_caps(text, settings.get('caps_limit', 50)):
            try:
                await msg.delete()
                await msg.reply_text(f"@{user.username} ❌ НЕ КРИЧИ! КАПС ЗАПРЕЩЕН!")
            except:
                pass
            return

# ============================================
# НОВЫЙ ЧАТ
# ============================================
async def new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.new_chat_members:
        return
    
    if msg.chat.type == "private":
        return
    
    for member in msg.new_chat_members:
        if member.id == context.bot.id:
            chat_id = str(msg.chat.id)
            adder_id = msg.from_user.id
            
            chat_settings[chat_id] = DEFAULT_SETTINGS.copy()
            chat_settings[chat_id]['chat_creator'] = adder_id
            chat_settings[chat_id]['chat_title'] = msg.chat.title
            chat_settings[chat_id]['added_date'] = datetime.now().strftime("%Y-%m-%d %H:%M")
            save_settings()
            
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"✅ БОТ ДОБАВЛЕН В ГРУППУ!\n\n"
                    f"📌 Название: {msg.chat.title}\n"
                    f"🆔 ID: {chat_id}\n"
                    f"👤 Добавил: {adder_id}"
                )
            except:
                pass

# ============================================
# ЗАПУСК
# ============================================
def main():
    print("=" * 60)
    print("╔══════════════════════════╗")
    print("║   🤖 ANTISPAM БОТ       ║")
    print("║   ⚡ ВСЕ ФИЛЬТРЫ         ║")
    print("║   ✨ С ЭМОДЗИ            ║")
    print("╚══════════════════════════╝")
    print("=" * 60)
    print(f"👑 ТВОЙ ID: {ADMIN_ID}")
    print(f"📊 ЧАТОВ: {len(chat_settings)}")
    print("=" * 60)
    print("📋 КОМАНДЫ:")
    print("   ❓ /help     - помощь")
    print("   📊 /status   - статус")
    print("   ⚙️ /settings - настройки")
    print("   👑 /admin    - админы")
    print("   🗑️ /delchat  - удалить чат")
    print("=" * 60)
    
    app = Application.builder().token(TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("settings", settings))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("delchat", delchat))
    
    # Кнопки
    app.add_handler(CallbackQueryHandler(button))
    
    # Текст (для добавления админов)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, text_handler))
    
    # Проверка сообщений в группах
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Sticker.ALL,
        check
    ))
    
    # Новые чаты
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_chat))
    
    print("✅ БОТ ЗАПУЩЕН! 🚀")
    print("=" * 60)
    
    app.run_polling()

if __name__ == '__main__':
    main()