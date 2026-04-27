# main.py
import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import BOT_TOKEN, SUPER_ADMIN_IDS, TEACHER_IDS
import database.queries as db
from database.models import init_db, create_default_data

# Import all routers
from handlers.start import router as start_router
from handlers.super_admin import router as super_admin_router
from handlers.center_admin import router as center_admin_router
from handlers.teacher import router as teacher_router
from handlers.student import router as student_router
from handlers.parent import router as parent_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

async def set_commands(bot: Bot):
    """Set bot commands for different user roles"""
    # Default commands (shown to all users)
    default_commands = [
        BotCommand(command="start", description="🚀 Start the bot / Register"),
        BotCommand(command="help", description="❓ Get help"),
        BotCommand(command="language", description="🌐 Change language"),
        BotCommand(command="profile", description="👤 View my profile"),
    ]
    await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())

    logger.info("✅ Bot commands configured")

async def initialize_system():
    """Initialize database and create default data"""
    logger.info("🔄 Initializing database...")
    await init_db()
    logger.info("✅ Database schema initialized")

    await create_default_data()
    logger.info("✅ Default data created")

    # Sync super admins from config
    for admin_id in SUPER_ADMIN_IDS:
        user = await db.get_user_by_telegram_id(admin_id)
        if not user:
            user_id = await db.create_user(
                telegram_id=admin_id,
                full_name=f"SuperAdmin_{admin_id}",
                role='super_admin'
            )
            if user_id:
                await db.assign_role(user_id, 'super_admin')
                logger.info(f"✅ Super admin {admin_id} created")
        else:
            # Ensure super admin role
            roles = await db.get_user_roles(user['id'])
            if 'super_admin' not in roles:
                await db.assign_role(user['id'], 'super_admin')
                logger.info(f"✅ Super admin role assigned to {admin_id}")

    # Sync teachers from config (if any)
    for teacher_id in TEACHER_IDS:
        user = await db.get_user_by_telegram_id(teacher_id)
        if not user:
            user_id = await db.create_user(
                telegram_id=teacher_id,
                full_name=f"Teacher_{teacher_id}",
                role='teacher'
            )
            logger.info(f"✅ Teacher {teacher_id} created")

    logger.info("✅ System initialization complete")

async def check_maintenance_mode() -> bool:
    """Check if platform is in maintenance mode"""
    maintenance = await db.get_setting(None, 'maintenance_mode', 'false')
    return maintenance == 'true'

async def main():
    """Main bot runner"""
    logger.info("🤖 Starting StudyCenter Bot...")

    # Initialize system
    await initialize_system()

    # Check if bot token is set
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found in .env file!")
        sys.exit(1)

    # Initialize bot
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Set commands
    await set_commands(bot)

    # Initialize storage and dispatcher
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register middleware for maintenance mode check
    @dp.message.middleware()
    async def maintenance_middleware(handler, event, data):
        """Check maintenance mode before processing messages"""
        is_maintenance = await check_maintenance_mode()

        if is_maintenance:
            user_id = event.from_user.id if hasattr(event, 'from_user') else None

            # Allow super admins through
            if user_id and user_id in SUPER_ADMIN_IDS:
                return await handler(event, data)

            # Block other users
            if hasattr(event, 'answer'):
                maintenance_msg = await db.get_setting(None, 'maintenance_message',
                    '🛠 The platform is currently under maintenance. Please try again later.')
                await event.answer(maintenance_msg)
            return

        return await handler(event, data)

    # Log all updates middleware
    @dp.message.middleware()
    async def logging_middleware(handler, event, data):
        """Log all incoming messages"""
        user_id = event.from_user.id if hasattr(event, 'from_user') else 'Unknown'
        username = event.from_user.username if hasattr(event, 'from_user') else 'Unknown'

        if hasattr(event, 'text'):
            logger.info(f"📩 Message from {user_id} (@{username}): {event.text[:100]}")
        elif hasattr(event, 'data'):
            logger.info(f"📩 Callback from {user_id} (@{username}): {event.data}")

        return await handler(event, data)

    # Include all routers
    dp.include_router(start_router)
    dp.include_router(super_admin_router)
    dp.include_router(center_admin_router)
    dp.include_router(teacher_router)
    dp.include_router(student_router)
    dp.include_router(parent_router)

    logger.info("✅ All routers registered")

    # Start polling
    try:
        logger.info("🚀 Bot is starting to poll...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Error starting bot: {e}")
        raise
    finally:
        await bot.session.close()
        logger.info("👋 Bot stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)
