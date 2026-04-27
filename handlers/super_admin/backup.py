# handlers/super_admin/backup.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import database.queries as db
from keyboards.all_keyboards import (
    get_super_admin_main_menu, get_cancel_keyboard,
    get_confirm_keyboard, get_back_keyboard
)
import os
import json
import shutil
from config import DB_PATH, BACKUP_DIR

router = Router()

# ========================
# BACKUP MAIN MENU
# ========================

@router.message(F.text == "💾 Backup")
async def backup_main_menu(message: Message, state: FSMContext):
    """Show backup management main menu"""
    # Get backup stats
    backups = list_backups()

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Create Platform Backup", callback_data="sa_create_backup")],
        [InlineKeyboardButton(text="📋 List All Backups", callback_data="sa_list_backups")],
        [InlineKeyboardButton(text="🔄 Schedule Auto Backup", callback_data="sa_schedule_backup")],
        [InlineKeyboardButton(text="📥 Download Latest Backup", callback_data="sa_download_backup")],
        [InlineKeyboardButton(text="🗑️ Clean Old Backups", callback_data="sa_clean_backups")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    text = "💾 **Backup & Restore**\n\n"
    text += f"📊 **Backup Stats:**\n"
    text += f"• Total Backups: **{len(backups)}**\n"
    text += f"• Backup Directory: {BACKUP_DIR}\n\n"
    text += "Select action:"

    await message.answer(text, reply_markup=keyboard)

def list_backups() -> list:
    """List all backup files"""
    if not os.path.exists(BACKUP_DIR):
        return []

    backups = []
    for file in os.listdir(BACKUP_DIR):
        if file.endswith('.db') or file.endswith('.zip'):
            filepath = os.path.join(BACKUP_DIR, file)
            stats = os.stat(filepath)
            backups.append({
                'filename': file,
                'size_mb': stats.st_size / (1024 * 1024),
                'created': datetime.fromtimestamp(stats.st_ctime).isoformat()
            })

    return sorted(backups, key=lambda x: x['created'], reverse=True)

# ========================
# CREATE BACKUP
# ========================

@router.callback_query(F.data == "sa_create_backup")
async def create_backup_menu(callback: CallbackQuery, state: FSMContext):
    """Show backup creation options"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Full Platform Backup", callback_data="create_full_backup")],
        [InlineKeyboardButton(text="🏢 Specific Center Backup", callback_data="create_center_backup")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(
        "📦 **Create Backup**\n\n"
        "Select backup type:",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "create_full_backup")
async def create_full_backup(callback: CallbackQuery, state: FSMContext):
    """Create a full platform backup"""
    await callback.message.edit_text("📦 **Creating full backup...**")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"full_backup_{timestamp}.db"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    try:
        # Copy database file
        shutil.copy2(DB_PATH, backup_path)

        # Also create a JSON export of all data
        json_backup = await create_json_export()
        json_filename = f"full_backup_{timestamp}.json"
        json_path = os.path.join(BACKUP_DIR, json_filename)

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_backup, f, ensure_ascii=False, indent=2, default=str)

        # Create a zip archive
        zip_filename = f"full_backup_{timestamp}.zip"
        zip_path = os.path.join(BACKUP_DIR, zip_filename)

        import zipfile
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.write(backup_path, backup_filename)
            zf.write(json_path, json_filename)

        # Clean up temp files
        os.remove(backup_path)
        os.remove(json_path)

        # Log
        await db.log_audit(
            user_id=callback.from_user.id,
            action='create_backup',
            entity_type='backup',
            new_values={'filename': zip_filename, 'type': 'full'}
        )

        file_size = os.path.getsize(zip_path) / (1024 * 1024)

        await callback.message.edit_text(
            f"✅ **Full Backup Created!**\n\n"
            f"📁 File: {zip_filename}\n"
            f"📊 Size: {file_size:.2f} MB\n"
            f"📅 Date: {timestamp}",
            reply_markup=get_back_keyboard("sa_back")
        )

    except Exception as e:
        await callback.message.edit_text(
            f"❌ Backup failed: {str(e)}",
            reply_markup=get_back_keyboard("sa_back")
        )

async def create_json_export() -> dict:
    """Create a JSON export of all database data"""
    export = {
        'export_date': datetime.now().isoformat(),
        'centers': [],
        'users': [],
        'classes': [],
        'quizzes': [],
        'payments': []
    }

    async with db.get_db() as conn:
        # Export centers
        cursor = await conn.execute("SELECT * FROM centers")
        export['centers'] = [dict(row) for row in await cursor.fetchall()]

        # Export users (without passwords)
        cursor = await conn.execute("""
            SELECT id, telegram_id, username, full_name, phone, email,
                   language, timezone, total_points, current_streak,
                   is_blocked, created_at, last_active
            FROM users
        """)
        export['users'] = [dict(row) for row in await cursor.fetchall()]

        # Export classes
        cursor = await conn.execute("SELECT * FROM classes")
        export['classes'] = [dict(row) for row in await cursor.fetchall()]

        # Export quizzes
        cursor = await conn.execute("SELECT * FROM quizzes WHERE is_active = 1")
        export['quizzes'] = [dict(row) for row in await cursor.fetchall()]

        # Export payments
        cursor = await conn.execute("SELECT * FROM payments")
        export['payments'] = [dict(row) for row in await cursor.fetchall()]

    return export

@router.callback_query(F.data == "create_center_backup")
async def create_center_backup_start(callback: CallbackQuery, state: FSMContext):
    """Start center-specific backup"""
    centers = await db.get_all_centers()

    buttons = []
    for center in centers:
        buttons.append([InlineKeyboardButton(
            text=center['name'],
            callback_data=f"backup_center_{center['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")])

    await callback.message.edit_text(
        "Select center to backup:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("backup_center_"))
async def create_center_backup(callback: CallbackQuery, state: FSMContext):
    """Create backup for a specific center"""
    center_id = int(callback.data.replace("backup_center_", ""))
    center = await db.get_center_by_id(center_id)

    if not center:
        await callback.answer("Center not found", show_alert=True)
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"center_{center['slug']}_{timestamp}.json"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    # Export center-specific data
    export = await export_center_data(center_id)

    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump(export, f, ensure_ascii=False, indent=2, default=str)

    file_size = os.path.getsize(backup_path) / (1024 * 1024)

    # Log
    await db.log_audit(
        user_id=callback.from_user.id,
        action='create_center_backup',
        entity_type='backup',
        entity_id=center_id,
        new_values={'filename': backup_filename}
    )

    await callback.message.edit_text(
        f"✅ **Center Backup Created!**\n\n"
        f"🏢 Center: {center['name']}\n"
        f"📁 File: {backup_filename}\n"
        f"📊 Size: {file_size:.2f} MB",
        reply_markup=get_back_keyboard("sa_back")
    )

async def export_center_data(center_id: int) -> dict:
    """Export all data for a specific center"""
    export = {
        'center_id': center_id,
        'export_date': datetime.now().isoformat(),
        'data': {}
    }

    async with db.get_db() as conn:
        # Center info
        cursor = await conn.execute("SELECT * FROM centers WHERE id = ?", (center_id,))
        export['data']['center'] = dict(await cursor.fetchone())

        # Center users
        cursor = await conn.execute("""
            SELECT u.* FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            WHERE ur.center_id = ?
        """, (center_id,))
        export['data']['users'] = [dict(row) for row in await cursor.fetchall()]

        # Classes
        cursor = await conn.execute("SELECT * FROM classes WHERE center_id = ?", (center_id,))
        export['data']['classes'] = [dict(row) for row in await cursor.fetchall()]

        # Payments
        cursor = await conn.execute("SELECT * FROM payments WHERE center_id = ?", (center_id,))
        export['data']['payments'] = [dict(row) for row in await cursor.fetchall()]

    return export

# ========================
# LIST & DOWNLOAD BACKUPS
# ========================

@router.callback_query(F.data == "sa_list_backups")
async def list_all_backups(callback: CallbackQuery, state: FSMContext):
    """List all available backups"""
    backups = list_backups()

    if not backups:
        await callback.message.edit_text(
            "📋 No backups found.",
            reply_markup=get_back_keyboard("sa_back")
        )
        return

    text = "📋 **Available Backups**\n\n"
    buttons = []

    for i, backup in enumerate(backups[:15], 1):
        created = backup['created'][:16] if backup.get('created') else 'N/A'
        text += f"{i}. 📁 {backup['filename']}\n"
        text += f"   📊 {backup['size_mb']:.2f} MB | 📅 {created}\n\n"

        buttons.append([InlineKeyboardButton(
            text=f"📥 Download - {backup['filename'][:30]}",
            callback_data=f"download_backup_{i-1}"
        )])

    buttons.append([InlineKeyboardButton(text="🗑️ Delete All Backups", callback_data="sa_delete_all_backups")])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")])

    await state.update_data(backup_list=backups)

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("download_backup_"))
async def download_backup(callback: CallbackQuery, state: FSMContext):
    """Send a backup file to the user"""
    data = await state.get_data()
    backups = data.get('backup_list', [])
    index = int(callback.data.replace("download_backup_", ""))

    if index >= len(backups):
        await callback.answer("Backup not found", show_alert=True)
        return

    backup = backups[index]
    filepath = os.path.join(BACKUP_DIR, backup['filename'])

    if not os.path.exists(filepath):
        await callback.answer("Backup file not found on disk", show_alert=True)
        return

    await callback.message.answer("📤 Sending backup file...")

    document = FSInputFile(filepath)
    await callback.message.answer_document(
        document=document,
        caption=f"📦 Backup: {backup['filename']}\n📅 Created: {backup['created'][:19]}"
    )

@router.callback_query(F.data == "sa_download_backup")
async def download_latest_backup(callback: CallbackQuery, state: FSMContext):
    """Download the most recent backup"""
    backups = list_backups()

    if not backups:
        await callback.answer("No backups available", show_alert=True)
        return

    latest = backups[0]
    filepath = os.path.join(BACKUP_DIR, latest['filename'])

    if not os.path.exists(filepath):
        await callback.answer("Backup file not found", show_alert=True)
        return

    await callback.message.answer("📤 Sending latest backup...")

    document = FSInputFile(filepath)
    await callback.message.answer_document(
        document=document,
        caption=f"📦 Latest Backup: {latest['filename']}\n📅 Created: {latest['created'][:19]}"
    )

# ========================
# SCHEDULE AUTO BACKUP
# ========================

@router.callback_query(F.data == "sa_schedule_backup")
async def schedule_backup_menu(callback: CallbackQuery, state: FSMContext):
    """Show backup scheduling options"""
    current_schedule = await db.get_setting(None, 'auto_backup_schedule', 'daily')

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{'✅ ' if current_schedule == 'daily' else ''}Daily",
            callback_data="schedule_backup_daily"
        )],
        [InlineKeyboardButton(
            text=f"{'✅ ' if current_schedule == 'weekly' else ''}Weekly",
            callback_data="schedule_backup_weekly"
        )],
        [InlineKeyboardButton(
            text=f"{'✅ ' if current_schedule == 'monthly' else ''}Monthly",
            callback_data="schedule_backup_monthly"
        )],
        [InlineKeyboardButton(text="❌ Disable Auto Backup", callback_data="schedule_backup_off")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(
        "🔄 **Auto Backup Schedule**\n\n"
        f"Current: **{current_schedule.title()}**\n\n"
        "Select backup frequency:",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("schedule_backup_"))
async def set_backup_schedule(callback: CallbackQuery, state: FSMContext):
    """Set auto backup schedule"""
    schedule = callback.data.replace("schedule_backup_", "")

    await db.set_setting(None, 'auto_backup_schedule', schedule)

    # Log
    await db.log_audit(
        user_id=callback.from_user.id,
        action='set_backup_schedule',
        entity_type='system',
        new_values={'schedule': schedule}
    )

    await callback.answer(f"✅ Auto backup set to {schedule}")
    await schedule_backup_menu(callback, state)

# ========================
# CLEAN OLD BACKUPS
# ========================

@router.callback_query(F.data == "sa_clean_backups")
async def clean_old_backups_confirm(callback: CallbackQuery, state: FSMContext):
    """Confirm cleaning old backups"""
    backups = list_backups()

    if len(backups) < 3:
        await callback.answer("Not enough backups to clean", show_alert=True)
        return

    await callback.message.edit_text(
        f"🗑️ **Clean Old Backups**\n\n"
        f"Total backups: {len(backups)}\n"
        f"Will keep the 5 most recent backups.\n\n"
        f"Delete the rest?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑️ Clean", callback_data="confirm_clean_backups"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="sa_back")
            ]
        ])
    )

@router.callback_query(F.data == "confirm_clean_backups")
async def execute_clean_backups(callback: CallbackQuery, state: FSMContext):
    """Execute backup cleanup"""
    backups = list_backups()

    # Keep 5 most recent
    to_delete = backups[5:]
    deleted_count = 0

    for backup in to_delete:
        filepath = os.path.join(BACKUP_DIR, backup['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
            deleted_count += 1

    # Log
    await db.log_audit(
        user_id=callback.from_user.id,
        action='clean_backups',
        entity_type='system',
        new_values={'deleted_count': deleted_count}
    )

    await callback.message.edit_text(
        f"✅ **Backups Cleaned**\n\n"
        f"🗑️ Deleted: {deleted_count} old backups\n"
        f"📦 Kept: {min(5, len(backups))} recent backups",
        reply_markup=get_back_keyboard("sa_back")
    )

@router.callback_query(F.data == "sa_delete_all_backups")
async def delete_all_backups_confirm(callback: CallbackQuery, state: FSMContext):
    """Confirm deleting all backups"""
    backups = list_backups()

    await callback.message.edit_text(
        f"⚠️ **Delete ALL Backups?**\n\n"
        f"This will delete {len(backups)} backup files.\n"
        f"This action CANNOT be undone!\n\n"
        f"Type 'DELETE ALL' to confirm:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state("confirm_delete_all_backups")

@router.message(F.text, state="confirm_delete_all_backups")
async def execute_delete_all_backups(message: Message, state: FSMContext):
    """Execute deleting all backups"""
    if message.text.strip().upper() != 'DELETE ALL':
        await message.answer("❌ Deletion cancelled.")
        await state.clear()
        return

    backups = list_backups()
    deleted_count = 0

    for backup in backups:
        filepath = os.path.join(BACKUP_DIR, backup['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
            deleted_count += 1

    await message.answer(
        f"✅ All {deleted_count} backups deleted.",
        reply_markup=get_super_admin_main_menu()
    )
    await state.clear()
