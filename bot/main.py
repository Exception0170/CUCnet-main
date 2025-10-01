# main.py
import os
import logging
import time
from datetime import datetime
from typing import Dict, Any
from logging.handlers import RotatingFileHandler

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from config import *
from shared.database import DatabaseManager

# Command cooldowns
cooldowns: Dict[str, float] = {}


# Utils
def check_cooldown(user_id: int, command: str, cooldown_seconds: int) -> bool:
    """Check command cooldown"""
    key = f"{user_id}_{command}"
    current_time = time.time()

    if key in cooldowns:
        if current_time - cooldowns[key] < cooldown_seconds:
            return False

    cooldowns[key] = current_time
    return True


def log_user_action(user_id: int, action: str, result: str, details: str = None):
    """Log user action"""
    details_str = f", details={details}" if details else ""
    logger.info(f"user_id={user_id}, action={action}, result={result}{details_str}")


def is_admin_chat(chat_id: int) -> bool:
    """Check if command is executed in admin chat"""
    return chat_id == ADMIN_CHAT_ID


def validate_profile_name(name: str) -> bool:
    """Validate profile name"""
    if not name or len(name) > 50:
        return False
    # Allow letters, numbers, spaces, and basic punctuation
    return all(c.isalnum() or c in ' -_.' for c in name)


# Keyboards
def get_tos_keyboard():
    """Get TOS agreement keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Принимаю", callback_data="tos_accept"),
            InlineKeyboardButton("❌ Отказываюсь", callback_data="tos_reject")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_profile_type_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("Personal", callback_data="profile_type:Personal"),
            InlineKeyboardButton("Webserver", callback_data="profile_type:Webserver")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_profiles_keyboard(profiles, action_type):
    keyboard = []
    for profile in profiles:
        button_text = f"{profile['profile_name']} ({profile['profile_type']}) - {profile['assigned_ip']}"
        callback_data = f"{action_type}_profile:{profile['id']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    return InlineKeyboardMarkup(keyboard)


def get_profile_config_keyboard(profiles):
    """Keyboard for selecting profile to get config"""
    keyboard = []
    for profile in profiles:
        button_text = f"{profile['profile_name']} ({profile['profile_type']})"
        callback_data = f"get_config:{profile['id']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    return InlineKeyboardMarkup(keyboard)


def get_admin_approval_keyboard(user_id):
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_user:{user_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_user:{user_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_ignored_users_keyboard(ignored_users):
    keyboard = []
    for user in ignored_users:
        username = user['username'] or 'не указан'
        keyboard.append([
            InlineKeyboardButton(
                f"Одобрить {user['user_id']}",
                callback_data=f"approve_user:{user['user_id']}"
            ),
            InlineKeyboardButton(
                f"Разблокировать {user['user_id']}",
                callback_data=f"unban_user:{user['user_id']}"
            )
        ])
    return InlineKeyboardMarkup(keyboard)


# Commands
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    username = update.effective_user.username

    # Check if user already exists
    existing_user = db.get_user(user_id)
    if existing_user:
        if existing_user['ignored']:
            await update.message.reply_text("❌ Ваш аккаунт был отклонен. Обратитесь к администратору.")
            return
        elif existing_user['is_verified']:
            await update.message.reply_text("✅ Ваш аккаунт уже активирован. Используйте /help для списка команд.")
            return
        else:
            await update.message.reply_text("⏳ Ваш запрос еще находится на рассмотрении администраторами.")
            return

    # Send TOS agreement
    tos_message = """
📋 **Правила использования сервиса**

Перед использованием сервиса, пожалуйста, ознакомьтесь с правилами:

1. **Запрещено** использование сервиса для незаконной деятельности
2. **Запрещено** нарушение работы сети или других пользователей
3. **Разрешено** создание до 3 профилей WireGuard
4. **Типы профилей**:
   - Personal: для личного использования (IP: 10.8.100.0/24 - 10.8.255.0/24)
   - Webserver: для веб-серверов (IP: 10.8.10.0/24 - 10.8.25.0/24)

5. Администрация оставляет за собой право блокировать аккаунты за нарушение правил

Для продолжения необходимо принять условия использования.
    """

    await update.message.reply_text(
        tos_message,
        reply_markup=get_tos_keyboard(),
        parse_mode='Markdown'
    )
    log_user_action(user_id, "/start", "tos_shown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    user_id = update.effective_user.id

    help_message = """
🤖 **CUCnet Profile Bot - Справка**

📋 **Основные команды:**
/start - Начать работу с ботом
/help - Показать эту справку

👤 **Управление профилями WireGuard:**
/newprofile - Создать новый профиль WireGuard (максимум 3)
/profiles - Просмотреть все профили и скачать конфигурационные файлы
/rename - Переименовать существующий профиль

🔐 **Доступ к системе:**
/site_login - Получить данные для входа на веб-сайт

⚙️ **Для администраторов** (только в админ-чате):
/pending - Просмотреть пользователей ожидающих одобрения
/rejected - Просмотреть отклоненных пользователей

💡 **Информация:**
- Создавайте до 3 профилей WireGuard
- Типы профилей: Personal (личное использование) и Webserver (для веб-серверов)
- Каждый профиль получает уникальный IP адрес
- Конфигурационные файлы отправляются автоматически при создании профиля

📞 **Поддержка:**
По всем вопросам обращайтесь к администраторам.
    """

    await update.message.reply_text(help_message, parse_mode='Markdown')
    log_user_action(user_id, "/help", "shown")


async def newprofile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /newprofile"""
    user_id = update.effective_user.id

    # Проверяем статус пользователя
    user = db.get_user(user_id)
    if not user or not user['is_verified'] or user['ignored']:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return

    # Проверяем лимит профилей
    profile_count = db.get_profile_count(user_id)
    if profile_count >= MAX_PROFILES_PER_USER:
        await update.message.reply_text(f"❌ У вас уже есть {MAX_PROFILES_PER_USER} профиля. Новый создать нельзя")
        log_user_action(user_id, "/newprofile", "failed", "limit reached")
        return

    # Отправляем клавиатуру выбора типа профиля
    keyboard = get_profile_type_keyboard()
    await update.message.reply_text(
        "Выберите тип профиля:",
        reply_markup=keyboard
    )


async def profiles_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /profiles"""
    user_id = update.effective_user.id

    # Проверяем статус пользователя
    user = db.get_user(user_id)
    if not user or not user['is_verified'] or user['ignored']:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return

    # Получаем профили пользователя
    profiles = db.get_user_profiles(user_id)

    if not profiles:
        await update.message.reply_text("📝 У вас пока нет профилей. Создайте первый с помощью /newprofile")
        return

    # Формируем сообщение со списком профилей
    message = "📋 Ваши профили:\n\n"
    for profile in profiles:
        message += f"• **{profile['profile_name']}** ({profile['profile_type']}) - `{profile['assigned_ip']}`\n"

    message += "\nНажмите на профиль ниже чтобы получить конфигурационный файл:"

    keyboard = get_profile_config_keyboard(profiles)
    await update.message.reply_text(
        message,
        reply_markup=keyboard,
        parse_mode='Markdown'
    )
    log_user_action(user_id, "/profiles", "success", f"count={len(profiles)}")


async def rename_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /rename"""
    user_id = update.effective_user.id

    # Проверяем статус пользователя
    user = db.get_user(user_id)
    if not user or not user['is_verified'] or user['ignored']:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return

    # Получаем профили пользователя
    profiles = db.get_user_profiles(user_id)

    if not profiles:
        await update.message.reply_text("📝 У вас пока нет профилей для переименования")
        return

    # Отправляем клавиатуру с профилями
    keyboard = get_profiles_keyboard(profiles, 'rename')
    await update.message.reply_text(
        "Выберите профиль для переименования:",
        reply_markup=keyboard
    )


async def site_login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /site_login"""
    user_id = update.effective_user.id

    # Проверяем статус пользователя
    user = db.get_user(user_id)
    if not user or not user['is_verified'] or user['ignored']:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return

    # Получаем или генерируем пароль
    site_password = user.get('site_password')
    if not site_password:
        site_password = db.generate_password()
        db.set_site_password(user_id, site_password)

    # Отправляем данные для входа
    message = f"""🔐 Данные для входа на сайт:
Логин: {user['username'] or f'user_{user_id}'}
Пароль: `{site_password}`"""

    await update.message.reply_text(message, parse_mode='Markdown')
    log_user_action(user_id, "/site_login", "success")


async def rejected_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /rejected (только для администраторов)"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Проверяем права администратора (admin chat only)
    if not is_admin_chat(chat_id):
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return

    # Получаем список отклоненных пользователей
    ignored_users = db.get_ignored_users()

    if not ignored_users:
        await update.message.reply_text("📝 Нет отклоненных пользователей")
        return

    # Формируем сообщение с кнопками
    message = "📋 Отклоненные пользователи:\n\n"
    for user in ignored_users:
        username = user['username'] or 'не указан'
        message += f"• ID: {user['user_id']}, @{username}\n"

    keyboard = get_ignored_users_keyboard(ignored_users)
    await update.message.reply_text(message, reply_markup=keyboard)
    log_user_action(user_id, "/rejected", "success", f"count={len(ignored_users)}")


async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /pending (только для администраторов)"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Проверяем права администратора (admin chat only)
    if not is_admin_chat(chat_id):
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return

    # Получаем список ожидающих пользователей
    pending_users = db.get_pending_users()

    if not pending_users:
        await update.message.reply_text("📝 Нет пользователей ожидающих одобрения")
        return

    # Формируем сообщение с кнопками
    message = "📋 Пользователи ожидающие одобрения:\n\n"
    keyboard_buttons = []

    for user in pending_users:
        username = user['username'] or 'не указан'
        message += f"• ID: {user['user_id']}, @{username}\n"

        keyboard_buttons.append([
            InlineKeyboardButton(
                f"✅ {user['user_id']}",
                callback_data=f"approve_user:{user['user_id']}"
            ),
            InlineKeyboardButton(
                f"❌ {user['user_id']}",
                callback_data=f"reject_user:{user['user_id']}"
            )
        ])

    keyboard = InlineKeyboardMarkup(keyboard_buttons)
    await update.message.reply_text(message, reply_markup=keyboard)
    log_user_action(user_id, "/pending", "success", f"count={len(pending_users)}")


# ============================================================================
# CALLBACK AND MESSAGE HANDLERS
# ============================================================================

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback-запросов от inline-кнопок"""
    query = update.callback_query
    await query.answer()

    data = query.data
    user_id = query.from_user.id
    chat_id = query.message.chat_id

    if data == 'tos_accept':
        # User accepted TOS
        username = query.from_user.username
        db.add_user(user_id, username)

        # Send approval request to admin group
        admin_keyboard = get_admin_approval_keyboard(user_id)
        admin_message = f"""
🆕 Новый пользователь запрашивает доступ:
ID: {user_id}
Username: @{username if username else 'не указан'}
Имя: {query.from_user.first_name}
        """

        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_message,
            reply_markup=admin_keyboard
        )

        await query.edit_message_text(
            "✅ Вы приняли условия использования.\n\n"
            "👋 Ваш запрос на доступ отправлен администраторам. "
            "Вы получите уведомление после рассмотрения заявки."
        )
        log_user_action(user_id, "tos", "accepted")

    elif data == 'tos_reject':
        # User rejected TOS
        await query.edit_message_text(
            "❌ Вы отказались от условий использования.\n\n"
            "Для использования сервиса необходимо принять условия."
        )
        log_user_action(user_id, "tos", "rejected")

    elif data.startswith('profile_type:'):
        # Обработка выбора типа профиля
        profile_type = data.split(':', 1)[1]
        context.user_data['selected_profile_type'] = profile_type
        await query.edit_message_text("Введите имя профиля:")

    elif data.startswith('rename_profile:'):
        # Обработка выбора профиля для переименования
        profile_id = int(data.split(':', 1)[1])
        context.user_data['selected_profile_id'] = profile_id
        await query.edit_message_text("Введите новое имя профиля:")

    elif data.startswith('get_config:'):
        # Get profile config file
        profile_id = int(data.split(':', 1)[1])
        user = db.get_user(user_id)

        if not user or not user['is_verified'] or user['ignored']:
            await query.edit_message_text("❌ У вас нет прав для этого действия")
            return

        config_content = db.get_profile_config(profile_id)
        if not config_content:
            await query.edit_message_text("❌ Ошибка получения конфигурации")
            return

        # Get profile info for filename
        profiles = db.get_user_profiles(user_id)
        profile_info = next((p for p in profiles if p['id'] == profile_id), None)

        if profile_info:
            filename = f"{profile_info['profile_name']}.conf"
            # Send as file
            await context.bot.send_document(
                chat_id=user_id,
                document=config_content.encode('utf-8'),
                filename=filename,
                caption=f"📁 Конфигурационный файл: {profile_info['profile_name']}\n"
                        f"📍 IP: {profile_info['assigned_ip']}\n"
                        f"🔧 Тип: {profile_info['profile_type']}"
            )
            await query.edit_message_text("✅ Конфигурационный файл отправлен в личные сообщения")
            log_user_action(user_id, "get_config", "success", f"profile_id={profile_id}")
        else:
            await query.edit_message_text("❌ Профиль не найден")

    elif data.startswith('approve_user:'):
        # Одобрение пользователя
        target_user_id = int(data.split(':', 1)[1])
        if is_admin_chat(chat_id):
            if db.approve_user(target_user_id):
                await query.edit_message_text(f"✅ Пользователь {target_user_id} одобрен")
                log_user_action(user_id, "approve_user", "success", f"target={target_user_id}")

                # Send welcome message to approved user
                welcome_message = """🎉 Добро пожаловать! Ваш аккаунт одобрен.

📋 Доступные команды:

👤 Управление профилями:
/newprofile - создать новый профиль WireGuard
/profiles - просмотреть все профили и скачать конфиги
/rename - переименовать профиль

🔐 Доступ к системе:
/site_login - получить данные для входа на сайт

💡 Справка:
- Используйте /help для полного списка команд
- Вы можете создать до 3 профилей WireGuard
- Типы профилей: Personal и Webserver
- Данные для входа генерируются автоматически

Начните с команды /newprofile для создания первого профиля!"""

                try:
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=welcome_message
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки приветственного сообщения пользователю {target_user_id}: {e}")
            else:
                await query.edit_message_text("❌ Ошибка при одобрении пользователя")
        else:
            await query.edit_message_text("❌ У вас нет прав для этого действия")

    elif data.startswith('reject_user:'):
        # Отклонение пользователя
        target_user_id = int(data.split(':', 1)[1])
        if is_admin_chat(chat_id):
            if db.reject_user(target_user_id):
                await query.edit_message_text(f"❌ Пользователь {target_user_id} отклонен")
                log_user_action(user_id, "reject_user", "success", f"target={target_user_id}")
            else:
                await query.edit_message_text("❌ Ошибка при отклонении пользователя")
        else:
            await query.edit_message_text("❌ У вас нет прав для этого действия")

    elif data.startswith('unban_user:'):
        # Разблокировка пользователя
        target_user_id = int(data.split(':', 1)[1])
        if is_admin_chat(chat_id):
            if db.unban_user(target_user_id):
                await query.edit_message_text(f"✅ Пользователь {target_user_id} разблокирован")
                log_user_action(user_id, "unban_user", "success", f"target={target_user_id}")
            else:
                await query.edit_message_text("❌ Ошибка при разблокировке пользователя")
        else:
            await query.edit_message_text("❌ У вас нет прав для этого действия")


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    user_id = update.effective_user.id
    text = update.message.text

    # Проверяем, ожидает ли бот ввода имени профиля
    if 'selected_profile_type' in context.user_data:
        profile_type = context.user_data['selected_profile_type']
        profile_name = text.strip()

        # Валидация имени профиля
        if not validate_profile_name(profile_name):
            await update.message.reply_text("❌ Неверное имя профиля. Используйте только буквы, цифры и пробелы")
            return

        # Проверяем лимит профилей
        profile_count = db.get_profile_count(user_id)
        if profile_count >= MAX_PROFILES_PER_USER:
            await update.message.reply_text(f"❌ У вас уже есть {MAX_PROFILES_PER_USER} профиля. Новый создать нельзя")
            return

        # Создаем профиль
        success, message = db.add_profile(user_id, profile_name, profile_type)
        if success:
            await update.message.reply_text(f"✅ Профиль {profile_name} создан")

            # Get the created profile to send config file
            profiles = db.get_user_profiles(user_id)
            new_profile = next((p for p in profiles if p['profile_name'] == profile_name), None)

            if new_profile:
                config_content = db.get_profile_config(new_profile['id'])
                if config_content:
                    filename = f"{profile_name}.conf"
                    await update.message.reply_document(
                        document=config_content.encode('utf-8'),
                        filename=filename,
                        caption=f"📁 Конфигурационный файл: {profile_name}\n"
                                f"📍 IP: {new_profile['assigned_ip']}\n"
                                f"🔧 Тип: {profile_type}"
                    )

            log_user_action(user_id, "create_profile", "success", f"name={profile_name}, type={profile_type}")
        else:
            await update.message.reply_text(f"❌ {message}")
            log_user_action(user_id, "create_profile", "failed", f"name={profile_name}, error={message}")

        # Очищаем временные данные
        context.user_data.clear()

    # Проверяем, ожидает ли бот ввода нового имени профиля
    elif 'selected_profile_id' in context.user_data:
        profile_id = context.user_data['selected_profile_id']
        new_name = text.strip()

        # Валидация имени профиля
        if not validate_profile_name(new_name):
            await update.message.reply_text("❌ Неверное имя профиля. Используйте только буквы, цифры и пробелы")
            return

        # Переименовываем профиль
        if db.rename_profile(profile_id, new_name):
            await update.message.reply_text("✅ Профиль переименован")
            log_user_action(user_id, "rename_profile", "success", f"profile_id={profile_id}, new_name={new_name}")
        else:
            await update.message.reply_text("❌ Профиль с таким именем уже существует")
            log_user_action(user_id, "rename_profile", "failed", "duplicate name")

        # Очищаем временные данные
        context.user_data.clear()


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging():
    """Setup logging configuration"""
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname("logs/bot.log")
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler()
        ]
    )

    # Set specific log levels for external libraries
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)


def main():
    setup_logging()
    global logger
    logger = logging.getLogger(__name__)

    # check token
    if not PROFILE_BOT_TOKEN or PROFILE_BOT_TOKEN == 'your_telegram_bot_token_here':
        logger.error("BOT_TOKEN не настроен")
        print("❌ Ошибка: BOT_TOKEN не настроен!")
        return

    logger.info("Starting bot...")

    # db init
    global db
    try:
        db = DatabaseManager()
        logger.info("База данных инициализирована")
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")
        return

    application = Application.builder().token(PROFILE_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("newprofile", newprofile_command))
    application.add_handler(CommandHandler("profiles", profiles_command))
    application.add_handler(CommandHandler("rename", rename_command))
    application.add_handler(CommandHandler("site_login", site_login_command))
    application.add_handler(CommandHandler("rejected", rejected_command))
    application.add_handler(CommandHandler("pending", pending_command))

    # Add callback query handler
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    # Add text message handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    print("CUCnet profile bot running!")
    print("Ctrl+C to stop")

    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        print("Bot stopped")


if __name__ == '__main__':
    main()