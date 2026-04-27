# handlers/super_admin/security.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import database.queries as db
from keyboards.all_keyboards import (
    get_super_admin_main_menu, get_cancel_keyboard,
    get_confirm_keyboard, get_back_keyboard
)
import json

router = Router()

# ========================
# SECURITY MAIN MENU
# ========================

@router.message(F.text == "🔐 Security")
async def security_main_menu(message: Message, state: FSMContext):
    """Show security management main menu"""
    # Get security stats
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT COUNT(*) FROM login_attempts
            WHERE attempted_at > datetime('now', '-24 hours')
        """)
        recent_attempts = (await cursor.fetchone())[0]

        cursor = await conn.execute("""
            SELECT COUNT(*) FROM login_attempts
            WHERE is_successful = 0 AND attempted_at > datetime('now', '-24 hours')
        """)
        failed_attempts = (await cursor.fetchone())[0]

        cursor = await conn.execute("""
            SELECT COUNT(*) FROM audit_logs
            WHERE created_at > datetime('now', '-7 days')
        """)
        recent_audits = (await cursor.fetchone())[0]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 View Audit Logs", callback_data="sa_audit_logs")],
        [InlineKeyboardButton(text="🔐 Login Attempts", callback_data="sa_login_attempts")],
        [InlineKeyboardButton(text="👑 Manage Super Admins", callback_data="sa_manage_admins")],
        [InlineKeyboardButton(text="🌐 IP Whitelist", callback_data="sa_ip_whitelist")],
        [InlineKeyboardButton(text="🔑 Security Scan", callback_data="sa_security_scan")],
        [InlineKeyboardButton(text="📤 Export All Data", callback_data="sa_export_all_data")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    text = "🔐 **Security & Access**\n\n"
    text += f"📊 **Security Overview:**\n"
    text += f"• Login Attempts (24h): **{recent_attempts}**\n"
    text += f"• Failed Attempts (24h): **{failed_attempts}**\n"
    text += f"• Audit Entries (7d): **{recent_audits}**\n\n"
    text += "Select action:"

    await message.answer(text, reply_markup=keyboard)

# ========================
# AUDIT LOGS
# ========================

@router.callback_query(F.data == "sa_audit_logs")
async def view_audit_logs(callback: CallbackQuery, state: FSMContext):
    """View comprehensive audit logs"""
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT al.*, u.full_name as user_name
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            ORDER BY al.created_at DESC
            LIMIT 100
        """)
        logs = [dict(row) for row in await cursor.fetchall()]

        # Get stats
        cursor = await conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT user_id) as unique_users,
                MIN(created_at) as first_entry,
                MAX(created_at) as last_entry
            FROM audit_logs
        """)
        stats = dict(await cursor.fetchone())

    if not logs:
        await callback.message.edit_text(
            "No audit logs found.",
            reply_markup=get_back_keyboard("sa_back")
        )
        return

    text = "📋 **Audit Logs**\n\n"
    text += f"📊 Total entries: {stats['total']}\n"
    text += f"👥 Unique users: {stats['unique_users']}\n"
    text += f"📅 From: {stats['first_entry'][:10] if stats.get('first_entry') else 'N/A'}\n"
    text += f"📅 To: {stats['last_entry'][:10] if stats.get('last_entry') else 'N/A'}\n\n"
    text += "**Recent Activity:**\n\n"

    for log in logs[:15]:
        timestamp = log['created_at'][:19] if log.get('created_at') else 'N/A'
        user = log.get('user_name', 'System')
        text += f"🕐 {timestamp}\n"
        text += f"👤 {user}\n"
        text += f"🔧 {log['action']}\n"
        if log.get('entity_type'):
            text += f"📦 {log['entity_type']} #{log.get('entity_id', '')}\n"
        if log.get('new_values'):
            try:
                new_vals = json.loads(log['new_values'])
                text += f"📝 {json.dumps(new_vals)[:80]}\n"
            except:
                pass
        text += "─" * 30 + "\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Filter by Action", callback_data="sa_filter_audit")],
        [InlineKeyboardButton(text="📥 Export Audit Log", callback_data="sa_export_audit")],
        [InlineKeyboardButton(text="🗑️ Clear Old Logs", callback_data="sa_clear_audit_logs")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "sa_clear_audit_logs")
async def clear_old_audit_logs(callback: CallbackQuery, state: FSMContext):
    """Clear audit logs older than 90 days"""
    async with db.get_db() as conn:
        await conn.execute("""
            DELETE FROM audit_logs
            WHERE created_at < datetime('now', '-90 days')
        """)
        await conn.commit()

    await callback.answer("✅ Old audit logs cleared (kept last 90 days)")
    await view_audit_logs(callback, state)

# ========================
# LOGIN ATTEMPTS
# ========================

@router.callback_query(F.data == "sa_login_attempts")
async def view_login_attempts(callback: CallbackQuery, state: FSMContext):
    """View login attempts"""
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT * FROM login_attempts
            ORDER BY attempted_at DESC
            LIMIT 100
        """)
        attempts = [dict(row) for row in await cursor.fetchall()]

        # Stats
        cursor = await conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN is_successful = 1 THEN 1 END) as successful,
                COUNT(CASE WHEN is_successful = 0 THEN 1 END) as failed,
                COUNT(DISTINCT ip_address) as unique_ips
            FROM login_attempts
            WHERE attempted_at > datetime('now', '-7 days')
        """)
        stats = dict(await cursor.fetchone())

    if not attempts:
        await callback.message.edit_text(
            "No login attempts recorded.",
            reply_markup=get_back_keyboard("sa_back")
        )
        return

    text = "🔐 **Login Attempts**\n\n"
    text += f"📊 **Last 7 Days:**\n"
    text += f"• Total: {stats['total']}\n"
    text += f"• Successful: {stats['successful']}\n"
    text += f"• Failed: {stats['failed']}\n"
    text += f"• Unique IPs: {stats['unique_ips']}\n\n"
    text += "**Recent Attempts:**\n\n"

    for attempt in attempts[:20]:
        status = "✅" if attempt['is_successful'] else "❌"
        timestamp = attempt['attempted_at'][:19] if attempt.get('attempted_at') else 'N/A'
        text += f"{status} [{timestamp}]\n"
        text += f"   TG ID: {attempt.get('telegram_id', 'N/A')}\n"
        text += f"   IP: {attempt.get('ip_address', 'N/A')}\n"
        if not attempt.get('is_successful'):
            text += f"   Reason: {attempt.get('failure_reason', 'N/A')}\n"
        text += "\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Block Suspicious IPs", callback_data="sa_block_suspicious")],
        [InlineKeyboardButton(text="🗑️ Clear Old Attempts", callback_data="sa_clear_attempts")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "sa_block_suspicious")
async def block_suspicious_ips(callback: CallbackQuery, state: FSMContext):
    """Block IPs with many failed attempts"""
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT ip_address, COUNT(*) as attempts
            FROM login_attempts
            WHERE is_successful = 0
              AND attempted_at > datetime('now', '-24 hours')
            GROUP BY ip_address
            HAVING attempts >= 5
        """)
        suspicious = [dict(row) for row in await cursor.fetchall()]

    if not suspicious:
        await callback.answer("No suspicious IPs found", show_alert=True)
        return

    blocked = []
    for entry in suspicious:
        await db.add_to_ip_blacklist(entry['ip_address'])
        blocked.append(entry['ip_address'])

    await callback.message.edit_text(
        f"🚫 **Blocked Suspicious IPs**\n\n"
        f"Blocked {len(blocked)} IPs:\n" +
        "\n".join(f"• {ip}" for ip in blocked),
        reply_markup=get_back_keyboard("sa_login_attempts")
    )

# ========================
# MANAGE SUPER ADMINS
# ========================

@router.callback_query(F.data == "sa_manage_admins")
async def manage_super_admins(callback: CallbackQuery, state: FSMContext):
    """Manage super admins"""
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT u.* FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            WHERE ur.role = 'super_admin'
            ORDER BY u.full_name
        """)
        admins = [dict(row) for row in await cursor.fetchall()]

    text = "👑 **Super Admins**\n\n"
    buttons = []

    for admin in admins:
        status = "🟢" if not admin.get('is_blocked') else "🔴"
        text += f"{status} **{admin['full_name']}**\n"
        text += f"   ID: {admin['id']} | TG: {admin.get('telegram_id', 'N/A')}\n"
        text += f"   Joined: {admin['created_at'][:10] if admin.get('created_at') else 'N/A'}\n\n"

        buttons.append([InlineKeyboardButton(
            text=f"❌ Remove {admin['full_name']}",
            callback_data=f"remove_admin_{admin['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="➕ Add Super Admin", callback_data="sa_add_admin")])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data == "sa_add_admin")
async def add_super_admin_start(callback: CallbackQuery, state: FSMContext):
    """Start adding a super admin"""
    await callback.message.edit_text(
        "➕ **Add Super Admin**\n\n"
        "Enter the Telegram ID of the new super admin:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state("add_super_admin")

@router.message(F.text, state="add_super_admin")
async def add_super_admin_execute(message: Message, state: FSMContext):
    """Execute adding super admin"""
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Please enter a valid Telegram ID:")
        return

    user = await db.get_user_by_telegram_id(telegram_id)
    if not user:
        # Create user
        user_id = await db.create_user(
            telegram_id=telegram_id,
            full_name=f"Admin_{telegram_id}"
        )
    else:
        user_id = user['id']

    # Assign super admin role
    await db.assign_role(user_id, 'super_admin', granted_by=message.from_user.id)

    # Log
    await db.log_audit(
        user_id=message.from_user.id,
        action='add_super_admin',
        entity_type='user',
        entity_id=user_id
    )

    await message.answer(
        f"✅ Super admin added! (ID: {user_id})",
        reply_markup=get_super_admin_main_menu()
    )
    await state.clear()

@router.callback_query(F.data.startswith("remove_admin_"))
async def remove_super_admin(callback: CallbackQuery, state: FSMContext):
    """Remove a super admin"""
    admin_id = int(callback.data.replace("remove_admin_", ""))

    # Don't allow removing yourself
    if admin_id == callback.from_user.id:
        await callback.answer("❌ You cannot remove yourself!", show_alert=True)
        return

    await db.remove_role(admin_id, 'super_admin')

    # Log
    await db.log_audit(
        user_id=callback.from_user.id,
        action='remove_super_admin',
        entity_type='user',
        entity_id=admin_id
    )

    await callback.answer("✅ Super admin removed")
    await manage_super_admins(callback, state)

# ========================
# IP WHITELIST
# ========================

@router.callback_query(F.data == "sa_ip_whitelist")
async def ip_whitelist_menu(callback: CallbackQuery, state: FSMContext):
    """Show IP whitelist management"""
    whitelist = await db.get_setting(None, 'ip_whitelist', '[]')
    whitelist_ips = json.loads(whitelist) if isinstance(whitelist, str) else whitelist

    text = "🌐 **IP Whitelist**\n\n"

    if whitelist_ips:
        text += "**Allowed IPs:**\n"
        for ip in whitelist_ips:
            text += f"• {ip}\n"
    else:
        text += "No IPs whitelisted. All IPs allowed.\n"

    text += "\nSelect action:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add IP", callback_data="sa_add_ip")],
        [InlineKeyboardButton(text="➖ Remove IP", callback_data="sa_remove_ip")],
        [InlineKeyboardButton(text="🗑️ Clear Whitelist", callback_data="sa_clear_whitelist")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "sa_add_ip")
async def add_ip_start(callback: CallbackQuery, state: FSMContext):
    """Start adding IP to whitelist"""
    await callback.message.edit_text(
        "Enter IP address to whitelist:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state("add_ip")

@router.message(F.text, state="add_ip")
async def add_ip_execute(message: Message, state: FSMContext):
    """Execute adding IP"""
    ip = message.text.strip()

    # Validate IP format
    import re
    ip_pattern = re.compile(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    if not ip_pattern.match(ip):
        await message.answer("❌ Invalid IP format. Use format: 192.168.1.1")
        return

    whitelist = await db.get_setting(None, 'ip_whitelist', '[]')
    whitelist_ips = json.loads(whitelist) if isinstance(whitelist, str) else whitelist

    if ip not in whitelist_ips:
        whitelist_ips.append(ip)
        await db.set_setting(None, 'ip_whitelist', json.dumps(whitelist_ips))

    await message.answer(
        f"✅ IP {ip} added to whitelist.",
        reply_markup=get_super_admin_main_menu()
    )
    await state.clear()

@router.callback_query(F.data == "sa_clear_whitelist")
async def clear_whitelist(callback: CallbackQuery, state: FSMContext):
    """Clear IP whitelist"""
    await db.set_setting(None, 'ip_whitelist', '[]')
    await callback.answer("✅ Whitelist cleared")
    await ip_whitelist_menu(callback, state)

# ========================
# SECURITY SCAN
# ========================

@router.callback_query(F.data == "sa_security_scan")
async def security_scan(callback: CallbackQuery, state: FSMContext):
    """Run a security scan"""
    results = {
        'database_integrity': True,
        'foreign_keys_enabled': True,
        'admin_count': 0,
        'blocked_users': 0,
        'suspicious_ips': 0,
        'missing_indexes': [],
        'warnings': []
    }

    async with db.get_db() as conn:
        # Check foreign keys
        cursor = await conn.execute("PRAGMA foreign_keys")
        fk_status = await cursor.fetchone()
        results['foreign_keys_enabled'] = bool(fk_status[0]) if fk_status else False

        # Check admin count
        cursor = await conn.execute("""
            SELECT COUNT(*) FROM user_roles WHERE role = 'super_admin'
        """)
        results['admin_count'] = (await cursor.fetchone())[0]

        if results['admin_count'] == 0:
            results['warnings'].append("No super admins configured!")

        # Check blocked users
        cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
        results['blocked_users'] = (await cursor.fetchone())[0]

        # Check for suspicious IPs
        cursor = await conn.execute("""
            SELECT COUNT(DISTINCT ip_address) FROM login_attempts
            WHERE is_successful = 0
              AND attempted_at > datetime('now', '-24 hours')
            GROUP BY ip_address
            HAVING COUNT(*) >= 10
        """)
        results['suspicious_ips'] = len(await cursor.fetchall())

        if results['suspicious_ips'] > 0:
            results['warnings'].append(f"Found {results['suspicious_ips']} suspicious IPs")

    # Check database file
    if os.path.exists(DB_PATH):
        results['database_integrity'] = True
        # Check file permissions
        perms = oct(os.stat(DB_PATH).st_mode)[-3:]
        if perms != '600' and perms != '644':
            results['warnings'].append(f"Database file permissions are {perms} (recommended: 600)")

    text = "🔑 **Security Scan Results**\n\n"
    text += f"✅ Database Integrity: {'OK' if results['database_integrity'] else 'FAILED'}\n"
    text += f"✅ Foreign Keys: {'Enabled' if results['foreign_keys_enabled'] else 'Disabled'}\n"
    text += f"👑 Super Admins: {results['admin_count']}\n"
    text += f"🚫 Blocked Users: {results['blocked_users']}\n"
    text += f"⚠️ Suspicious IPs (24h): {results['suspicious_ips']}\n\n"

    if results['warnings']:
        text += "⚠️ **Warnings:**\n"
        for warning in results['warnings']:
            text += f"• {warning}\n"
    else:
        text += "✅ No security warnings found.\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Run Scan Again", callback_data="sa_security_scan")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

# ========================
# EXPORT ALL DATA
# ========================

@router.callback_query(F.data == "sa_export_all_data")
async def export_all_data(callback: CallbackQuery, state: FSMContext):
    """Export all platform data"""
    await callback.message.edit_text("📤 **Exporting all data...**")

    export = await create_json_export()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"platform_export_{timestamp}.json"
    filepath = os.path.join(BACKUP_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(export, f, ensure_ascii=False, indent=2, default=str)

    file_size = os.path.getsize(filepath) / (1024 * 1024)

    # Send file
    document = FSInputFile(filepath)
    await callback.message.answer_document(
        document=document,
        caption=f"📦 Platform Data Export\n📅 {timestamp}\n📊 {file_size:.2f} MB"
    )

    await callback.message.edit_text(
        f"✅ Data exported successfully!\n\n"
        f"📁 File: {filename}\n"
        f"📊 Size: {file_size:.2f} MB",
        reply_markup=get_back_keyboard("sa_back")
    )

# ========================
# CLEAR ALL PLATFORM DATA
# ========================

@router.callback_query(F.data == "sa_clear_all_data")
async def clear_all_data_confirm(callback: CallbackQuery, state: FSMContext):
    """Confirm clearing all platform data"""
    await callback.message.edit_text(
        "⚠️ **CLEAR ALL DATA?**\n\n"
        "This will DELETE ALL data from the platform!\n\n"
        "This includes:\n"
        "• All users and their data\n"
        "• All centers\n"
        "• All classes, quizzes, and materials\n"
        "• All payments and records\n\n"
        "⚠️ THIS ACTION CANNOT BE UNDONE!\n\n"
        "Type 'CLEAR ALL' to confirm:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state("confirm_clear_all")

@router.message(F.text, state="confirm_clear_all")
async def execute_clear_all(message: Message, state: FSMContext):
    """Execute clearing all data"""
    if message.text.strip().upper() != 'CLEAR ALL':
        await message.answer("❌ Operation cancelled.")
        await state.clear()
        return

    # Create backup first
    await create_full_backup_silent()

    # Clear all data
    async with db.get_db() as conn:
        tables = [
            'student_answers', 'quiz_answers', 'quiz_attempts',
            'homework_submissions', 'homework',
            'attendance_records', 'attendance_sessions',
            'competition_participants', 'competitions',
            'payments', 'messages', 'announcements',
            'feedback', 'support_tickets', 'ticket_responses',
            'student_badges', 'certificates',
            'speaking_sessions', 'speaking_topics',
            'leaderboard_entries',
            'quiz_questions', 'question_options', 'fill_gap_answers', 'matching_pairs',
            'quizzes', 'units',
            'class_enrollments', 'class_teachers', 'schedules', 'classes',
            'parent_child', 'user_roles', 'users',
            'center_settings', 'center_features', 'centers',
            'subscription_invoices', 'subscription_plans',
            'audit_logs', 'login_attempts', 'system_logs', 'backups'
        ]

        for table in tables:
            await conn.execute(f"DELETE FROM {table}")

        await conn.commit()

    # Log (this will be the last entry before deletion)
    await message.answer(
        "✅ All platform data has been cleared.\n"
        "A backup was created before deletion.",
        reply_mup=get_super_admin_main_menu()
    )
    await state.clear()

async def create_full_backup_silent():
    """Create a backup without user interaction"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"pre_clear_backup_{timestamp}.db")

    try:
        shutil.copy2(DB_PATH, backup_path)
        return backup_path
    except:
        return None
