# handlers/super_admin/system.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import database.queries as db
from keyboards.all_keyboards import (
    get_super_admin_main_menu, get_cancel_keyboard,
    get_confirm_keyboard, get_back_keyboard
)
import os
import sys
import json
from config import DB_PATH, BACKUP_DIR, BOT_TOKEN

router = Router()

# ========================
# SYSTEM MAIN MENU
# ========================

@router.message(F.text == "⚙️ System")
async def system_main_menu(message: Message, state: FSMContext):
    """Show system management main menu"""
    # Get system stats
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    db_size_mb = db_size / (1024 * 1024)

    async with db.get_db() as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM centers")
        total_centers = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM system_logs WHERE level = 'ERROR'")
        error_count = (await cursor.fetchone())[0]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 System Stats", callback_data="sa_system_stats")],
        [InlineKeyboardButton(text="📝 View Logs", callback_data="sa_view_logs")],
        [InlineKeyboardButton(text="🔄 Restart Bot", callback_data="sa_restart_bot")],
        [InlineKeyboardButton(text="🚧 Maintenance Mode", callback_data="sa_maintenance")],
        [InlineKeyboardButton(text="📢 Broadcast Message", callback_data="sa_broadcast")],
        [InlineKeyboardButton(text="⚙️ Settings", callback_data="sa_settings")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    text = "⚙️ **System Management**\n\n"
    text += f"📊 **System Overview:**\n"
    text += f"• Database Size: **{db_size_mb:.2f} MB**\n"
    text += f"• Total Users: **{total_users}**\n"
    text += f"• Total Centers: **{total_centers}**\n"
    text += f"• Errors: **{error_count}**\n"
    text += f"• Bot Token: {'✅ Set' if BOT_TOKEN else '❌ Missing'}\n\n"
    text += "Select action:"

    await message.answer(text, reply_markup=keyboard)

# ========================
# SYSTEM STATISTICS
# ========================

@router.callback_query(F.data == "sa_system_stats")
async def show_system_stats(callback: CallbackQuery, state: FSMContext):
    """Show detailed system statistics"""
    async with db.get_db() as conn:
        stats = {}

        # User stats
        cursor = await conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN is_blocked = 1 THEN 1 END) as blocked,
                COUNT(CASE WHEN is_active = 1 THEN 1 END) as active,
                AVG(total_points) as avg_points,
                MAX(current_streak) as max_streak
            FROM users
        """)
        stats['users'] = dict(await cursor.fetchone())

        # Center stats
        cursor = await conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN is_suspended = 1 THEN 1 END) as suspended,
                COUNT(CASE WHEN is_active = 1 THEN 1 END) as active
            FROM centers
        """)
        stats['centers'] = dict(await cursor.fetchone())

        # Content stats
        cursor = await conn.execute("SELECT COUNT(*) as total FROM classes WHERE is_archived = 0")
        stats['classes'] = (await cursor.fetchone())['total']

        cursor = await conn.execute("SELECT COUNT(*) as total FROM quizzes WHERE is_active = 1")
        stats['quizzes'] = (await cursor.fetchone())['total']

        cursor = await conn.execute("SELECT COUNT(*) as total FROM quiz_attempts WHERE completed_at IS NOT NULL")
        stats['quiz_attempts'] = (await cursor.fetchone())['total']

        cursor = await conn.execute("SELECT COUNT(*) as total FROM homework_submissions")
        stats['homework_submissions'] = (await cursor.fetchone())['total']

        # Payment stats
        cursor = await conn.execute("""
            SELECT
                COUNT(*) as total_transactions,
                COALESCE(SUM(amount), 0) as total_revenue
            FROM payments
        """)
        stats['payments'] = dict(await cursor.fetchone())

        # Database info
        db_size = os.path.getsize(DB_PATH)
        stats['database'] = {
            'size_mb': db_size / (1024 * 1024),
            'path': str(DB_PATH)
        }

    text = "📊 **Detailed System Statistics**\n\n"

    text += "👥 **Users:**\n"
    text += f"• Total: {stats['users']['total']}\n"
    text += f"• Active: {stats['users']['active']}\n"
    text += f"• Blocked: {stats['users']['blocked']}\n"
    text += f"• Avg Points: {stats['users']['avg_points']:.1f}\n"
    text += f"• Max Streak: {stats['users']['max_streak']} days\n\n"

    text += "🏢 **Centers:**\n"
    text += f"• Total: {stats['centers']['total']}\n"
    text += f"• Active: {stats['centers']['active']}\n"
    text += f"• Suspended: {stats['centers']['suspended']}\n\n"

    text += "📚 **Content:**\n"
    text += f"• Active Classes: {stats['classes']}\n"
    text += f"• Active Quizzes: {stats['quizzes']}\n"
    text += f"• Quiz Attempts: {stats['quiz_attempts']}\n"
    text += f"• Homework Submissions: {stats['homework_submissions']}\n\n"

    text += "💰 **Finance:**\n"
    text += f"• Total Transactions: {stats['payments']['total_transactions']}\n"
    text += f"• Total Revenue: {stats['payments']['total_revenue']:,.0f} UZS\n\n"

    text += "💾 **Database:**\n"
    text += f"• Size: {stats['database']['size_mb']:.2f} MB\n"
    text += f"• Path: {stats['database']['path']}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Export Full Report", callback_data="sa_export_system_report")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

# ========================
# VIEW SYSTEM LOGS
# ========================

@router.callback_query(F.data == "sa_view_logs")
async def view_system_logs(callback: CallbackQuery, state: FSMContext):
    """View system logs"""
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT * FROM system_logs
            ORDER BY created_at DESC
            LIMIT 50
        """)
        logs = [dict(row) for row in await cursor.fetchall()]

    if not logs:
        await callback.message.edit_text(
            "No system logs found.",
            reply_markup=get_back_keyboard("sa_back")
        )
        return

    text = "📝 **System Logs (Last 50)**\n\n"

    for log in logs[:20]:
        level_emoji = {'ERROR': '🔴', 'WARNING': '🟡', 'INFO': '🔵', 'DEBUG': '⚪'}
        emoji = level_emoji.get(log.get('level', 'INFO'), '⚪')

        timestamp = log['created_at'][:19] if log.get('created_at') else 'N/A'
        text += f"{emoji} [{timestamp}] {log.get('level', 'INFO')}\n"
        text += f"   {log.get('message', '')[:100]}\n"
        if log.get('component'):
            text += f"   Component: {log['component']}\n"
        text += "─" * 30 + "\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔴 Errors Only", callback_data="sa_logs_error"),
            InlineKeyboardButton(text="🟡 Warnings", callback_data="sa_logs_warning")
        ],
        [InlineKeyboardButton(text="🗑️ Clear Logs", callback_data="sa_clear_logs")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("sa_logs_"))
async def filter_system_logs(callback: CallbackQuery, state: FSMContext):
    """Filter system logs by level"""
    level = callback.data.replace("sa_logs_", "").upper()

    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT * FROM system_logs
            WHERE level = ?
            ORDER BY created_at DESC
            LIMIT 50
        """, (level,))
        logs = [dict(row) for row in await cursor.fetchall()]

    if not logs:
        await callback.message.edit_text(
            f"No {level} logs found.",
            reply_markup=get_back_keyboard("sa_view_logs")
        )
        return

    text = f"📝 **{level} Logs**\n\n"

    for log in logs[:20]:
        timestamp = log['created_at'][:19] if log.get('created_at') else 'N/A'
        text += f"[{timestamp}] {log.get('message', '')[:100]}\n"
        text += "─" * 30 + "\n"

    await callback.message.edit_text(text, reply_markup=get_back_keyboard("sa_view_logs"))

@router.callback_query(F.data == "sa_clear_logs")
async def clear_system_logs(callback: CallbackQuery, state: FSMContext):
    """Clear old system logs"""
    async with db.get_db() as conn:
        # Keep last 7 days
        await conn.execute("""
            DELETE FROM system_logs
            WHERE created_at < datetime('now', '-7 days')
        """)
        await conn.commit()

    await callback.answer("✅ Old logs cleared (kept last 7 days)")
    await view_system_logs(callback, state)

# ========================
# RESTART BOT
# ========================

@router.callback_query(F.data == "sa_restart_bot")
async def restart_bot_confirm(callback: CallbackQuery, state: FSMContext):
    """Confirm bot restart"""
    await callback.message.edit_text(
        "⚠️ **Restart Bot**\n\n"
        "Are you sure you want to restart the bot?\n"
        "This will disconnect all users temporarily.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Restart Now", callback_data="confirm_restart"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="sa_back")
            ]
        ])
    )

@router.callback_query(F.data == "confirm_restart")
async def restart_bot_execute(callback: CallbackQuery, state: FSMContext):
    """Execute bot restart"""
    # Log the restart
    await db.log_audit(
        user_id=callback.from_user.id,
        action='restart_bot',
        entity_type='system',
        new_values={'restarted_at': datetime.now().isoformat()}
    )

    await callback.message.edit_text("🔄 **Restarting bot...**")

    # Schedule restart
    import asyncio
    await asyncio.sleep(2)

    # Restart the bot process
    os.execv(sys.executable, ['python'] + sys.argv)

# ========================
# MAINTENANCE MODE
# ========================

@router.callback_query(F.data == "sa_maintenance")
async def maintenance_mode_menu(callback: CallbackQuery, state: FSMContext):
    """Show maintenance mode options"""
    # Check current maintenance status
    maintenance_status = await db.get_setting(None, 'maintenance_mode', 'false')

    status_text = "🟢 Enabled" if maintenance_status == 'true' else "🔴 Disabled"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔴 Disable Maintenance" if maintenance_status == 'true' else "🟢 Enable Maintenance",
            callback_data="sa_toggle_maintenance"
        )],
        [InlineKeyboardButton(text="✏️ Set Maintenance Message", callback_data="sa_maintenance_message")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(
        f"🚧 **Maintenance Mode**\n\n"
        f"Status: {status_text}\n\n"
        "When enabled, non-admin users will see a maintenance message.",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "sa_toggle_maintenance")
async def toggle_maintenance_mode(callback: CallbackQuery, state: FSMContext):
    """Toggle maintenance mode"""
    current = await db.get_setting(None, 'maintenance_mode', 'false')
    new_status = 'false' if current == 'true' else 'true'

    await db.set_setting(None, 'maintenance_mode', new_status)

    # Log
    await db.log_audit(
        user_id=callback.from_user.id,
        action='toggle_maintenance',
        entity_type='system',
        new_values={'maintenance_mode': new_status}
    )

    await callback.answer(f"✅ Maintenance mode {'enabled' if new_status == 'true' else 'disabled'}")
    await maintenance_mode_menu(callback, state)

@router.callback_query(F.data == "sa_maintenance_message")
async def set_maintenance_message(callback: CallbackQuery, state: FSMContext):
    """Set maintenance message"""
    await callback.message.edit_text(
        "Enter maintenance message (shown to users):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state("maintenance_message")

@router.message(F.text, state="maintenance_message")
async def save_maintenance_message(message: Message, state: FSMContext):
    """Save maintenance message"""
    msg = message.text.strip()
    await db.set_setting(None, 'maintenance_message', msg)

    await message.answer(
        "✅ Maintenance message saved!",
        reply_markup=get_super_admin_main_menu()
    )
    await state.clear()

# ========================
# BROADCAST MESSAGE
# ========================

@router.callback_query(F.data == "sa_broadcast")
async def broadcast_message_start(callback: CallbackQuery, state: FSMContext):
    """Start composing a broadcast message"""
    await callback.message.edit_text(
        "📢 **Broadcast Message**\n\n"
        "Enter the message to broadcast to all bot users:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state("broadcast_message")

@router.message(F.text, state="broadcast_message")
async def broadcast_message_confirm(message: Message, state: FSMContext):
    """Confirm broadcast message"""
    broadcast_text = message.text.strip()

    # Get user count
    async with db.get_db() as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE telegram_id IS NOT NULL AND is_blocked = 0")
        user_count = (await cursor.fetchone())[0]

    await state.update_data(broadcast_text=broadcast_text, broadcast_count=user_count)

    await message.answer(
        f"📢 **Ready to Broadcast**\n\n"
        f"📄 Message:\n{broadcast_text[:100]}...\n\n"
        f"👥 Recipients: **{user_count}** users\n\n"
        f"Send broadcast?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📤 Send", callback_data="confirm_broadcast"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")
            ]
        ])
    )

@router.callback_query(F.data == "confirm_broadcast")
async def send_broadcast(callback: CallbackQuery, state: FSMContext):
    """Send broadcast message to all users"""
    data = await state.get_data()
    broadcast_text = data['broadcast_text']

    # Get all users with telegram_id
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT telegram_id FROM users
            WHERE telegram_id IS NOT NULL AND is_blocked = 0
        """)
        users = [row[0] for row in await cursor.fetchall()]

    # Send to users (this would use the bot instance)
    sent_count = 0
    failed_count = 0

    # Log the broadcast
    await db.log_audit(
        user_id=callback.from_user.id,
        action='broadcast_message',
        entity_type='system',
        new_values={'recipients': len(users), 'sent': sent_count, 'failed': failed_count}
    )

    await callback.message.edit_text(
        f"📤 **Broadcast Complete**\n\n"
        f"✅ Sent: {sent_count}\n"
        f"❌ Failed: {failed_count}\n"
        f"📊 Total: {len(users)}",
        reply_markup=get_back_keyboard("sa_back")
    )
    await state.clear()
