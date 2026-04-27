# handlers/super_admin/users.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from typing import List, Dict
import database.queries as db
from keyboards.all_keyboards import (
    get_super_admin_main_menu, get_cancel_keyboard,
    get_confirm_keyboard, get_back_keyboard, get_pagination_keyboard
)
import json

router = Router()

# ========================
# USER MANAGEMENT STATES
# ========================

class SearchUsersStates(StatesGroup):
    waiting_for_search = State()
    viewing_results = State()

class EditUserStates(StatesGroup):
    selecting_user = State()
    selecting_field = State()
    entering_value = State()

class ChangeRoleStates(StatesGroup):
    selecting_user = State()
    selecting_role = State()
    selecting_center = State()
    confirm_change = State()

class BlockUserStates(StatesGroup):
    selecting_user = State()
    entering_reason = State()
    confirm_block = State()

class TransferUserStates(StatesGroup):
    selecting_user = State()
    selecting_target_center = State()
    confirm_transfer = State()

class MergeUsersStates(StatesGroup):
    selecting_primary = State()
    selecting_secondary = State()
    confirm_merge = State()

# ========================
# MAIN USERS MENU
# ========================

@router.message(F.text == "👥 Users")
async def users_main_menu(message: Message, state: FSMContext):
    """Show users management main menu"""
    # Get quick stats
    async with db.get_db() as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM users")
        total_users = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1")
        blocked_users = (await cursor.fetchone())[0]

        cursor = await conn.execute("""
            SELECT COUNT(DISTINCT user_id) FROM user_roles WHERE role = 'teacher'
        """)
        total_teachers = (await cursor.fetchone())[0]

        cursor = await conn.execute("""
            SELECT COUNT(DISTINCT user_id) FROM user_roles WHERE role = 'student'
        """)
        total_students = (await cursor.fetchone())[0]

        cursor = await conn.execute("""
            SELECT COUNT(DISTINCT user_id) FROM user_roles WHERE role = 'center_admin'
        """)
        total_admins = (await cursor.fetchone())[0]

        cursor = await conn.execute("""
            SELECT COUNT(DISTINCT user_id) FROM user_roles WHERE role = 'parent'
        """)
        total_parents = (await cursor.fetchone())[0]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 View All Users", callback_data="sa_view_all_users")],
        [InlineKeyboardButton(text="🔍 Search Users", callback_data="sa_search_users")],
        [InlineKeyboardButton(text="✏️ Edit User", callback_data="sa_edit_user")],
        [InlineKeyboardButton(text="🔄 Change Role", callback_data="sa_change_user_role")],
        [
            InlineKeyboardButton(text="🚫 Block User", callback_data="sa_block_user"),
            InlineKeyboardButton(text="✅ Unblock User", callback_data="sa_unblock_user")
        ],
        [InlineKeyboardButton(text="🗑️ Delete User", callback_data="sa_delete_user")],
        [InlineKeyboardButton(text="📦 Transfer User", callback_data="sa_transfer_user")],
        [InlineKeyboardButton(text="🔗 Merge Users", callback_data="sa_merge_users")],
        [InlineKeyboardButton(text="📊 User Activity", callback_data="sa_user_activity")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    text = "👥 **Users Management**\n\n"
    text += f"📊 **Platform Statistics:**\n"
    text += f"• Total Users: **{total_users}**\n"
    text += f"• Admins: **{total_admins}**\n"
    text += f"• Teachers: **{total_teachers}**\n"
    text += f"• Students: **{total_students}**\n"
    text += f"• Parents: **{total_parents}**\n"
    text += f"• Blocked: **{blocked_users}**\n\n"
    text += "Select an action:"

    await message.answer(text, reply_markup=keyboard)

# ========================
# VIEW ALL USERS
# ========================

@router.callback_query(F.data == "sa_view_all_users")
async def view_all_users_start(callback: CallbackQuery, state: FSMContext):
    """Start viewing all users with role filter"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 All Users", callback_data="list_users_all")],
        [InlineKeyboardButton(text="🏢 Center Admins", callback_data="list_users_center_admin")],
        [InlineKeyboardButton(text="👨‍🏫 Teachers", callback_data="list_users_teacher")],
        [InlineKeyboardButton(text="🎓 Students", callback_data="list_users_student")],
        [InlineKeyboardButton(text="👪 Parents", callback_data="list_users_parent")],
        [InlineKeyboardButton(text="🚫 Blocked Users", callback_data="list_users_blocked")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(
        "📋 **View Users**\n\nFilter by role:",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("list_users_"))
async def list_users_by_role(callback: CallbackQuery, state: FSMContext):
    """List users filtered by role"""
    role_filter = callback.data.replace("list_users_", "")

    users = await db.get_users_by_filter(role_filter)

    await state.update_data(
        user_list=users,
        user_list_filter=role_filter,
        user_list_page=0
    )

    await display_users_page(callback.message, state, 0)

async def get_users_by_filter(filter_type: str) -> List[Dict]:
    """Get users based on filter type"""
    async with db.get_db() as conn:
        if filter_type == "all":
            cursor = await conn.execute("""
                SELECT u.*, GROUP_CONCAT(DISTINCT ur.role) as roles
                FROM users u
                LEFT JOIN user_roles ur ON u.id = ur.user_id
                GROUP BY u.id
                ORDER BY u.created_at DESC
                LIMIT 100
            """)
        elif filter_type == "blocked":
            cursor = await conn.execute("""
                SELECT u.*, GROUP_CONCAT(DISTINCT ur.role) as roles
                FROM users u
                LEFT JOIN user_roles ur ON u.id = ur.user_id
                WHERE u.is_blocked = 1
                GROUP BY u.id
                ORDER BY u.created_at DESC
            """)
        else:
            cursor = await conn.execute("""
                SELECT u.*, GROUP_CONCAT(DISTINCT ur.role) as roles
                FROM users u
                JOIN user_roles ur ON u.id = ur.user_id
                WHERE ur.role = ?
                GROUP BY u.id
                ORDER BY u.created_at DESC
                LIMIT 100
            """, (filter_type,))

        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def display_users_page(message, state: FSMContext, page: int):
    """Display a paginated page of users"""
    data = await state.get_data()
    users = data.get('user_list', [])
    per_page = 10
    total_pages = max(1, (len(users) + per_page - 1) // per_page)
    start = page * per_page
    end = start + per_page
    page_users = users[start:end]

    text = f"👥 **Users List** (Page {page+1}/{total_pages})\n\n"

    for user in page_users:
        status = "🚫" if user.get('is_blocked') else "🟢"
        roles = user.get('roles', 'student') or 'student'
        text += f"{status} **{user['full_name']}**\n"
        text += f"   ID: {user['id']} | TG: {user.get('telegram_id', 'N/A')}\n"
        text += f"   Roles: {roles}\n"
        text += f"   Joined: {user['created_at'][:10] if user.get('created_at') else 'N/A'}\n"
        text += "─" * 30 + "\n"

    # Build keyboard with user actions
    buttons = []

    for user in page_users:
        buttons.append([InlineKeyboardButton(
            text=f"👤 {user['full_name'][:30]}",
            callback_data=f"sa_user_detail_{user['id']}"
        )])

    # Pagination row
    pagination = []
    if page > 0:
        pagination.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"userlist_page_{page-1}"))
    pagination.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        pagination.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"userlist_page_{page+1}"))
    buttons.append(pagination)

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_view_all_users")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.edit_text(text, reply_markup=keyboard)
    await state.update_data(user_list_page=page)

@router.callback_query(F.data.startswith("userlist_page_"))
async def handle_users_pagination(callback: CallbackQuery, state: FSMContext):
    """Handle users list pagination"""
    page = int(callback.data.replace("userlist_page_", ""))
    await display_users_page(callback.message, state, page)

# ========================
# USER DETAILS
# ========================

@router.callback_query(F.data.startswith("sa_user_detail_"))
async def view_user_details(callback: CallbackQuery, state: FSMContext):
    """View comprehensive user details"""
    user_id = int(callback.data.replace("sa_user_detail_", ""))
    user = await db.get_user_by_id(user_id)

    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    # Get all roles with centers
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT ur.role, ur.center_id, c.name as center_name
            FROM user_roles ur
            LEFT JOIN centers c ON ur.center_id = c.id
            WHERE ur.user_id = ?
        """, (user_id,))
        roles = [dict(row) for row in await cursor.fetchall()]

        # Get activity stats
        cursor = await conn.execute("""
            SELECT COUNT(*) as quiz_count FROM quiz_attempts WHERE student_id = ?
        """, (user_id,))
        quiz_stats = await cursor.fetchone()

        cursor = await conn.execute("""
            SELECT COUNT(*) as submission_count FROM homework_submissions WHERE student_id = ?
        """, (user_id,))
        hw_stats = await cursor.fetchone()

        # Get children if parent
        children = await db.get_children_for_parent(user_id)

        # Get parents if student
        parents = await db.get_parents_for_student(user_id)

    status = "🚫 Blocked" if user.get('is_blocked') else "🟢 Active"

    text = f"👤 **User Details**\n\n"
    text += f"🆔 **ID:** {user['id']}\n"
    text += f"📛 **Name:** {user['full_name']}\n"
    text += f"📱 **Telegram ID:** {user.get('telegram_id', 'N/A')}\n"
    text += f"👤 **Username:** @{user.get('username', 'N/A')}\n"
    text += f"📞 **Phone:** {user.get('phone', 'N/A')}\n"
    text += f"📧 **Email:** {user.get('email', 'N/A')}\n"
    text += f"📊 **Status:** {status}\n"
    text += f"🌐 **Language:** {user.get('language', 'uz')}\n"
    text += f"⭐ **Points:** {user.get('total_points', 0)}\n"
    text += f"🔥 **Streak:** {user.get('current_streak', 0)} days\n"
    text += f"📅 **Joined:** {user['created_at'][:10] if user.get('created_at') else 'N/A'}\n"
    text += f"🕐 **Last Active:** {user.get('last_active', 'N/A')}\n\n"

    text += "**Roles:**\n"
    for role in roles:
        center_name = role.get('center_name', 'Platform-wide')
        text += f"• {role['role'].replace('_', ' ').title()} - {center_name}\n"

    if children:
        text += f"\n👶 **Children ({len(children)}):**\n"
        for child in children:
            text += f"• {child['full_name']} (ID: {child['id']})\n"

    if parents:
        text += f"\n👪 **Parents ({len(parents)}):**\n"
        for parent in parents:
            text += f"• {parent['full_name']} (ID: {parent['id']})\n"

    text += f"\n📊 **Activity:**\n"
    text += f"• Quizzes taken: {quiz_stats['quiz_count'] if quiz_stats else 0}\n"
    text += f"• Homework submitted: {hw_stats['submission_count'] if hw_stats else 0}\n"

    # Action buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit Profile", callback_data=f"sa_edit_user_{user_id}")],
        [InlineKeyboardButton(text="🔄 Change Role", callback_data=f"sa_change_role_{user_id}")],
        [
            InlineKeyboardButton(
                text="✅ Unblock" if user.get('is_blocked') else "🚫 Block",
                callback_data=f"sa_toggle_block_{user_id}"
            ),
            InlineKeyboardButton(text="🗑️ Delete", callback_data=f"sa_delete_user_{user_id}")
        ],
        [InlineKeyboardButton(text="📦 Transfer", callback_data=f"sa_transfer_user_{user_id}")],
        [InlineKeyboardButton(text="📊 Full Activity Log", callback_data=f"sa_user_activity_{user_id}")],
        [InlineKeyboardButton(text="🔙 Back to List", callback_data="sa_view_all_users")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

# ========================
# SEARCH USERS
# ========================

@router.callback_query(F.data == "sa_search_users")
async def search_users_start(callback: CallbackQuery, state: FSMContext):
    """Start user search"""
    await callback.message.edit_text(
        "🔍 **Search Users**\n\n"
        "Enter search term:\n"
        "• Name\n"
        "• Telegram ID\n"
        "• Username\n"
        "• Phone number\n"
        "• Email\n\n"
        "Type your search query:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(SearchUsersStates.waiting_for_search)

@router.message(SearchUsersStates.waiting_for_search, F.text)
async def process_user_search(message: Message, state: FSMContext):
    """Process user search"""
    search_term = message.text.strip()

    if len(search_term) < 2:
        await message.answer("❌ Search term must be at least 2 characters.")
        return

    # Search across multiple fields
    users = await search_users_comprehensive(search_term)

    if not users:
        await message.answer(
            f"❌ No users found matching '{search_term}'",
            reply_markup=get_back_keyboard("sa_back")
        )
        await state.clear()
        return

    await state.update_data(search_results=users)

    text = f"🔍 **Search Results for '{search_term}'**\n\n"
    text += f"Found {len(users)} user(s):\n\n"

    buttons = []
    for user in users[:20]:
        roles = user.get('roles', 'student') or 'student'
        text += f"• **{user['full_name']}** (ID: {user['id']})\n"
        text += f"  TG: {user.get('telegram_id', 'N/A')} | Roles: {roles}\n\n"

        buttons.append([InlineKeyboardButton(
            text=f"👤 {user['full_name']}",
            callback_data=f"sa_user_detail_{user['id']}"
        )])

    if len(users) > 20:
        text += f"... and {len(users) - 20} more users"

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.clear()

async def search_users_comprehensive(search_term: str) -> List[Dict]:
    """Comprehensive user search across multiple fields"""
    async with db.get_db() as conn:
        # Try exact match on telegram_id first
        try:
            telegram_id = int(search_term)
            cursor = await conn.execute("""
                SELECT u.*, GROUP_CONCAT(DISTINCT ur.role) as roles
                FROM users u
                LEFT JOIN user_roles ur ON u.id = ur.user_id
                WHERE u.telegram_id = ?
                GROUP BY u.id
            """, (telegram_id,))
        except ValueError:
            cursor = await conn.execute("""
                SELECT u.*, GROUP_CONCAT(DISTINCT ur.role) as roles
                FROM users u
                LEFT JOIN user_roles ur ON u.id = ur.user_id
                WHERE u.full_name LIKE ? OR u.username LIKE ? OR u.phone LIKE ? OR u.email LIKE ?
                GROUP BY u.id
                LIMIT 50
            """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))

        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ========================
# EDIT USER
# ========================

@router.callback_query(F.data == "sa_edit_user")
async def edit_user_start(callback: CallbackQuery, state: FSMContext):
    """Start editing a user - ask for user ID"""
    await callback.message.edit_text(
        "✏️ **Edit User**\n\n"
        "Enter the user's Telegram ID or internal ID:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(EditUserStates.selecting_user)

@router.message(EditUserStates.selecting_user, F.text)
async def edit_user_select(message: Message, state: FSMContext):
    """Select user to edit"""
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Please enter a valid user ID (numbers only):")
        return

    user = await db.get_user_by_id(user_id)
    if not user:
        # Try by telegram_id
        user = await db.get_user_by_telegram_id(user_id)

    if not user:
        await message.answer("❌ User not found. Please try again:")
        return

    await state.update_data(edit_user_id=user['id'], edit_user=user)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📛 Change Name", callback_data="edit_field_name")],
        [InlineKeyboardButton(text="📞 Change Phone", callback_data="edit_field_phone")],
        [InlineKeyboardButton(text="📧 Change Email", callback_data="edit_field_email")],
        [InlineKeyboardButton(text="🌐 Change Language", callback_data="edit_field_language")],
        [InlineKeyboardButton(text="🔙 Cancel", callback_data="cancel")]])

    await message.answer(
        f"✏️ **Editing: {user['full_name']}**\n\n"
        "Select field to edit:",
        reply_markup=keyboard
    )
    await state.set_state(EditUserStates.selecting_field)

@router.callback_query(EditUserStates.selecting_field, F.data.startswith("edit_field_"))
async def edit_user_field(callback: CallbackQuery, state: FSMContext):
    """Select field to edit"""
    field = callback.data.replace("edit_field_", "")
    await state.update_data(edit_field=field)

    prompts = {
        'name': "Enter new full name:",
        'phone': "Enter new phone number:",
        'email': "Enter new email address:",
        'language': "Enter language code (uz/ru/en):"
    }

    await callback.message.edit_text(
        prompts.get(field, "Enter new value:"),
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(EditUserStates.entering_value)

@router.message(EditUserStates.entering_value, F.text)
async def edit_user_value(message: Message, state: FSMContext):
    """Process edited value"""
    data = await state.get_data()
    user_id = data['edit_user_id']
    field = data['edit_field']
    new_value = message.text.strip()

    # Validate based on field
    if field == 'name' and len(new_value) < 2:
        await message.answer("❌ Name must be at least 2 characters.")
        return
    elif field == 'language' and new_value not in ['uz', 'ru', 'en']:
        await message.answer("❌ Language must be uz, ru, or en.")
        return

    # Update in database
    await db.update_user_field(user_id, field, new_value)

    # Log audit
    await db.log_audit(
        user_id=message.from_user.id,
        action='edit_user',
        entity_type='user',
        entity_id=user_id,
        new_values={field: new_value}
    )

    await message.answer(
        f"✅ User {field} updated successfully!",
        reply_markup=get_back_keyboard(f"sa_user_detail_{user_id}")
    )
    await state.clear()

# ========================
# CHANGE USER ROLE
# ========================

@router.callback_query(F.data == "sa_change_user_role")
async def change_role_start(callback: CallbackQuery, state: FSMContext):
    """Start changing a user's role"""
    await callback.message.edit_text(
        "🔄 **Change User Role**\n\n"
        "Enter the user's ID:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ChangeRoleStates.selecting_user)

@router.message(ChangeRoleStates.selecting_user, F.text)
async def change_role_select_user(message: Message, state: FSMContext):
    """Select user for role change"""
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Please enter a valid user ID:")
        return

    user = await db.get_user_by_id(user_id)
    if not user:
        user = await db.get_user_by_telegram_id(user_id)

    if not user:
        await message.answer("❌ User not found.")
        return

    # Get current roles
    roles = await db.get_user_roles(user['id'])

    await state.update_data(change_role_user_id=user['id'], change_role_user=user, current_roles=roles)

    # Show role selection
    all_roles = ['super_admin', 'center_admin', 'teacher', 'student', 'parent']

    text = f"👤 **User:** {user['full_name']}\n"
    text += f"Current roles: {', '.join(roles) if roles else 'None'}\n\n"
    text += "Select new role to ADD or REMOVE:"

    buttons = []
    for role in all_roles:
        action = "remove" if role in roles else "add"
        emoji = "❌" if role in roles else "➕"
        buttons.append([InlineKeyboardButton(
            text=f"{emoji} {role.replace('_', ' ').title()} ({action})",
            callback_data=f"toggle_role_{role}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.set_state(ChangeRoleStates.selecting_role)

@router.callback_query(ChangeRoleStates.selecting_role, F.data.startswith("toggle_role_"))
async def toggle_user_role(callback: CallbackQuery, state: FSMContext):
    """Toggle a role for the user"""
    role = callback.data.replace("toggle_role_", "")
    data = await state.get_data()
    user_id = data['change_role_user_id']
    current_roles = data.get('current_roles', [])

    if role in current_roles:
        # Remove role
        await db.remove_role(user_id, role)
        await callback.answer(f"✅ Removed {role} role")
    else:
        # If adding center-specific role, ask for center
        if role in ['center_admin', 'teacher', 'student', 'parent']:
            centers = await db.get_all_centers()
            await state.update_data(adding_role=role)

            buttons = []
            for center in centers:
                buttons.append([InlineKeyboardButton(
                    text=center['name'],
                    callback_data=f"assign_role_center_{center['id']}"
                )])
            buttons.append([InlineKeyboardButton(text="🌐 Platform-wide (no center)", callback_data="assign_role_center_0")])
            buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")])

            await callback.message.edit_text(
                f"Select center for the **{role}** role:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
            await state.set_state(ChangeRoleStates.selecting_center)
            return
        else:
            # Super admin - no center needed
            await db.assign_role(user_id, role, granted_by=callback.from_user.id)
            await callback.answer(f"✅ Added {role} role")

    # Refresh roles
    updated_roles = await db.get_user_roles(user_id)
    await state.update_data(current_roles=updated_roles)

    # Show updated view
    text = "✅ Roles updated!\n\nCurrent roles:\n"
    for r in updated_roles:
        text += f"• {r.replace('_', ' ').title()}\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(f"sa_user_detail_{user_id}")
    )

@router.callback_query(ChangeRoleStates.selecting_center, F.data.startswith("assign_role_center_"))
async def assign_role_with_center(callback: CallbackQuery, state: FSMContext):
    """Assign role with center context"""
    center_id = int(callback.data.replace("assign_role_center_", ""))
    data = await state.get_data()
    user_id = data['change_role_user_id']
    role = data['adding_role']

    await db.assign_role(
        user_id=user_id,
        role=role,
        center_id=center_id if center_id > 0 else None,
        granted_by=callback.from_user.id
    )

    # Log audit
    await db.log_audit(
        user_id=callback.from_user.id,
        action='change_role',
        entity_type='user',
        entity_id=user_id,
        new_values={'role': role, 'center_id': center_id}
    )

    await callback.message.edit_text(
        f"✅ Role **{role}** assigned successfully!",
        reply_markup=get_back_keyboard(f"sa_user_detail_{user_id}")
    )
    await state.clear()

# ========================
# BLOCK/UNBLOCK USER
# ========================

@router.callback_query(F.data == "sa_block_user")
async def block_user_start(callback: CallbackQuery, state: FSMContext):
    """Start blocking a user"""
    await callback.message.edit_text(
        "🚫 **Block User**\n\n"
        "Enter the user's ID to block:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(BlockUserStates.selecting_user)

@router.message(BlockUserStates.selecting_user, F.text)
async def block_user_select(message: Message, state: FSMContext):
    """Select user and ask for reason"""
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Please enter a valid user ID:")
        return

    user = await db.get_user_by_id(user_id)
    if not user:
        user = await db.get_user_by_telegram_id(user_id)

    if not user:
        await message.answer("❌ User not found.")
        return

    if user.get('is_blocked'):
        await message.answer("This user is already blocked.")
        await state.clear()
        return

    await state.update_data(block_user_id=user['id'], block_user=user)

    await message.answer(
        f"🚫 **Blocking: {user['full_name']}**\n\n"
        "Enter the reason for blocking:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(BlockUserStates.entering_reason)

@router.message(BlockUserStates.entering_reason, F.text)
async def block_user_confirm(message: Message, state: FSMContext):
    """Confirm user blocking"""
    reason = message.text.strip()
    data = await state.get_data()
    user = data['block_user']

    await db.block_user(user['id'], reason)

    # Log audit
    await db.log_audit(
        user_id=message.from_user.id,
        action='block_user',
        entity_type='user',
        entity_id=user['id'],
        new_values={'reason': reason}
    )

    await message.answer(
        f"✅ User **{user['full_name']}** has been blocked.\n\n"
        f"Reason: {reason}",
        reply_markup=get_super_admin_main_menu()
    )
    await state.clear()

@router.callback_query(F.data == "sa_unblock_user")
async def unblock_user_start(callback: CallbackQuery, state: FSMContext):
    """Start unblocking a user"""
    # Get blocked users
    async with db.get_db() as conn:
        cursor = await conn.execute("SELECT * FROM users WHERE is_blocked = 1 ORDER BY created_at DESC")
        blocked_users = [dict(row) for row in await cursor.fetchall()]

    if not blocked_users:
        await callback.message.edit_text(
            "✅ No blocked users found.",
            reply_markup=get_back_keyboard("sa_back")
        )
        return

    text = "🚫 **Blocked Users**\n\nSelect user to unblock:\n\n"
    buttons = []

    for user in blocked_users:
        text += f"• {user['full_name']} (ID: {user['id']})\n"
        text += f"  Reason: {user.get('blocked_reason', 'N/A')}\n\n"
        buttons.append([InlineKeyboardButton(
            text=f"✅ Unblock {user['full_name']}",
            callback_data=f"unblock_user_{user['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("unblock_user_"))
async def unblock_user(callback: CallbackQuery, state: FSMContext):
    """Unblock a user"""
    user_id = int(callback.data.replace("unblock_user_", ""))

    await db.unblock_user(user_id)

    # Log audit
    await db.log_audit(
        user_id=callback.from_user.id,
        action='unblock_user',
        entity_type='user',
        entity_id=user_id
    )

    await callback.answer("✅ User unblocked!")
    await unblock_user_start(callback, state)

# ========================
# DELETE USER
# ========================

@router.callback_query(F.data == "sa_delete_user")
async def delete_user_start(callback: CallbackQuery, state: FSMContext):
    """Start deleting a user"""
    await callback.message.edit_text(
        "🗑️ **Delete User**\n\n"
        "⚠️ WARNING: This action is irreversible!\n"
        "Enter the user's ID to delete:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state("confirm_delete_user_id")

@router.message(F.text, state="confirm_delete_user_id")
async def delete_user_confirm(message: Message, state: FSMContext):
    """Confirm user deletion"""
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Please enter a valid user ID:")
        return

    user = await db.get_user_by_id(user_id)
    if not user:
        user = await db.get_user_by_telegram_id(user_id)

    if not user:
        await message.answer("❌ User not found.")
        await state.clear()
        return

    await state.update_data(delete_user_id=user['id'], delete_user=user)

    await message.answer(
        f"⚠️ **CONFIRM DELETION**\n\n"
        f"Are you sure you want to delete **{user['full_name']}** (ID: {user['id']})?\n\n"
        f"This will remove:\n"
        f"• All user data\n"
        f"• All quiz attempts\n"
        f"• All homework submissions\n"
        f"• All attendance records\n"
        f"• All payment records\n\n"
        f"Type 'DELETE' to confirm:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state("confirm_delete_user_final")

@router.message(F.text, state="confirm_delete_user_final")
async def delete_user_final(message: Message, state: FSMContext):
    """Finalize user deletion"""
    if message.text.strip().upper() != 'DELETE':
        await message.answer("❌ Deletion cancelled.")
        await state.clear()
        return

    data = await state.get_data()
    user = data['delete_user']
    user_id = data['delete_user_id']

    # Log audit before deletion
    await db.log_audit(
        user_id=message.from_user.id,
        action='delete_user',
        entity_type='user',
        entity_id=user_id,
        old_values={'name': user['full_name'], 'telegram_id': user.get('telegram_id')}
    )

    # Delete user
    await db.delete_user(user_id)

    await message.answer(
        f"✅ User **{user['full_name']}** has been permanently deleted.",
        reply_markup=get_super_admin_main_menu()
    )
    await state.clear()

# ========================
# TRANSFER USER BETWEEN CENTERS
# ========================

@router.callback_query(F.data == "sa_transfer_user")
async def transfer_user_start(callback: CallbackQuery, state: FSMContext):
    """Start transferring a user between centers"""
    await callback.message.edit_text(
        "📦 **Transfer User Between Centers**\n\n"
        "Enter the user's ID to transfer:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(TransferUserStates.selecting_user)

@router.message(TransferUserStates.selecting_user, F.text)
async def transfer_user_select(message: Message, state: FSMContext):
    """Select user and show available centers"""
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Please enter a valid user ID:")
        return

    user = await db.get_user_by_id(user_id)
    if not user:
        user = await db.get_user_by_telegram_id(user_id)

    if not user:
        await message.answer("❌ User not found.")
        return

    # Get user's current centers
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT DISTINCT c.id, c.name FROM centers c
            JOIN user_roles ur ON c.id = ur.center_id
            WHERE ur.user_id = ?
        """, (user['id'],))
        current_centers = [dict(row) for row in await cursor.fetchall()]

    await state.update_data(transfer_user=user, transfer_user_id=user['id'], current_centers=current_centers)

    # Get all centers
    all_centers = await db.get_all_centers()

    text = f"📦 **Transfer: {user['full_name']}**\n\n"
    text += "Current centers:\n"
    for cc in current_centers:
        text += f"• {cc['name']} (ID: {cc['id']})\n"
    text += "\nSelect **target center**:"

    buttons = []
    for center in all_centers:
        is_current = any(cc['id'] == center['id'] for cc in current_centers)
        prefix = "📍" if is_current else "➡️"
        buttons.append([InlineKeyboardButton(
            text=f"{prefix} {center['name']}",
            callback_data=f"transfer_to_center_{center['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.set_state(TransferUserStates.selecting_target_center)

@router.callback_query(TransferUserStates.selecting_target_center, F.data.startswith("transfer_to_center_"))
async def transfer_user_execute(callback: CallbackQuery, state: FSMContext):
    """Execute user transfer"""
    target_center_id = int(callback.data.replace("transfer_to_center_", ""))
    data = await state.get_data()
    user_id = data['transfer_user_id']
    user = data['transfer_user']

    # Get target center info
    target_center = await db.get_center_by_id(target_center_id)

    if not target_center:
        await callback.answer("Center not found", show_alert=True)
        return

    # Get user's current center roles
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT role, center_id FROM user_roles WHERE user_id = ? AND center_id IS NOT NULL
        """, (user_id,))
        current_roles = [dict(row) for row in await cursor.fetchall()]

    # Transfer: remove from old centers, add to new center
    for cr in current_roles:
        # Remove from old center
        await db.remove_role(user_id, cr['role'], cr['center_id'])
        # Add to new center with same role
        await db.assign_role(user_id, cr['role'], target_center_id, callback.from_user.id)

    # Also update class enrollments if student
    await transfer_student_classes(user_id, target_center_id)

    # Log audit
    await db.log_audit(
        user_id=callback.from_user.id,
        action='transfer_user',
        entity_type='user',
        entity_id=user_id,
        old_values={'centers': [cr['center_id'] for cr in current_roles]},
        new_values={'target_center': target_center_id}
    )

    await callback.message.edit_text(
        f"✅ **User Transferred!**\n\n"
        f"👤 {user['full_name']}\n"
        f"🏢 To: **{target_center['name']}**\n\n"
        "All roles and permissions have been updated.",
        reply_markup=get_back_keyboard(f"sa_user_detail_{user_id}")
    )
    await state.clear()

async def transfer_student_classes(user_id: int, target_center_id: int):
    """Transfer student's class enrollments to new center"""
    async with db.get_db() as conn:
        # Get student's current classes
        cursor = await conn.execute("""
            SELECT ce.class_id FROM class_enrollments ce
            WHERE ce.student_id = ? AND ce.is_active = 1
        """, (user_id,))
        current_classes = [row[0] for row in await cursor.fetchall()]

        # Remove from old classes
        await conn.execute("""
            UPDATE class_enrollments SET is_active = 0, unenrolled_at = CURRENT_TIMESTAMP
            WHERE student_id = ?
        """, (user_id,))

        # Note: New class assignments should be done by center admin
        await conn.commit()

# ========================
# MERGE USER ACCOUNTS
# ========================

@router.callback_query(F.data == "sa_merge_users")
async def merge_users_start(callback: CallbackQuery, state: FSMContext):
    """Start merging two user accounts"""
    await callback.message.edit_text(
        "🔗 **Merge User Accounts**\n\n"
        "This will combine two accounts into one.\n"
        "Enter the **PRIMARY** user ID (this one will be kept):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(MergeUsersStates.selecting_primary)

@router.message(MergeUsersStates.selecting_primary, F.text)
async def merge_users_select_primary(message: Message, state: FSMContext):
    """Select primary user"""
    try:
        primary_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Please enter a valid user ID:")
        return

    primary_user = await db.get_user_by_id(primary_id)
    if not primary_user:
        primary_user = await db.get_user_by_telegram_id(primary_id)

    if not primary_user:
        await message.answer("❌ Primary user not found.")
        return

    await state.update_data(merge_primary_id=primary_user['id'], merge_primary_user=primary_user)

    await message.answer(
        f"✅ Primary: **{primary_user['full_name']}** (ID: {primary_user['id']})\n\n"
        "Now enter the **SECONDARY** user ID (this one will be merged and deleted):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(MergeUsersStates.selecting_secondary)

@router.message(MergeUsersStates.selecting_secondary, F.text)
async def merge_users_select_secondary(message: Message, state: FSMContext):
    """Select secondary user and confirm merge"""
    try:
        secondary_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Please enter a valid user ID:")
        return

    secondary_user = await db.get_user_by_id(secondary_id)
    if not secondary_user:
        secondary_user = await db.get_user_by_telegram_id(secondary_id)

    if not secondary_user:
        await message.answer("❌ Secondary user not found.")
        return

    data = await state.get_data()
    primary_user = data['merge_primary_user']

    if primary_user['id'] == secondary_user['id']:
        await message.answer("❌ Cannot merge the same user!")
        return

    await state.update_data(merge_secondary_id=secondary_user['id'], merge_secondary_user=secondary_user)

    # Show merge preview
    text = "🔗 **Merge Accounts Preview**\n\n"
    text += f"**PRIMARY (Keep):**\n"
    text += f"• {primary_user['full_name']} (ID: {primary_user['id']})\n"
    text += f"• TG: {primary_user.get('telegram_id', 'N/A')}\n"
    text += f"• Points: {primary_user.get('total_points', 0)}\n\n"
    text += f"**SECONDARY (Merge & Delete):**\n"
    text += f"• {secondary_user['full_name']} (ID: {secondary_user['id']})\n"
    text += f"• TG: {secondary_user.get('telegram_id', 'N/A')}\n"
    text += f"• Points: {secondary_user.get('total_points', 0)}\n\n"
    text += "**After merge:**\n"
    text += f"• Total points: {primary_user.get('total_points', 0) + secondary_user.get('total_points', 0)}\n"
    text += "• All data from secondary will be transferred to primary\n"
    text += "• Secondary account will be deleted\n\n"
    text += "⚠️ This action is IRREVERSIBLE!\n"
    text += "Type 'MERGE' to confirm:"

    await message.answer(text, reply_markup=get_cancel_keyboard())
    await state.set_state(MergeUsersStates.confirm_merge)

@router.message(MergeUsersStates.confirm_merge, F.text)
async def merge_users_execute(message: Message, state: FSMContext):
    """Execute user merge"""
    if message.text.strip().upper() != 'MERGE':
        await message.answer("❌ Merge cancelled.")
        await state.clear()
        return

    data = await state.get_data()
    primary_id = data['merge_primary_id']
    secondary_id = data['merge_secondary_id']
    primary_user = data['merge_primary_user']
    secondary_user = data['merge_secondary_user']

    # Merge all data
    await merge_user_data(primary_id, secondary_id)

    # Log audit
    await db.log_audit(
        user_id=message.from_user.id,
        action='merge_users',
        entity_type='user',
        entity_id=primary_id,
        old_values={'secondary_id': secondary_id, 'secondary_name': secondary_user['full_name']},
        new_values={'merged_into': primary_id}
    )

    await message.answer(
        f"✅ **Accounts Merged Successfully!**\n\n"
        f"Primary: {primary_user['full_name']} (ID: {primary_id})\n"
        f"Merged: {secondary_user['full_name']} (ID: {secondary_id})\n\n"
        "All data has been consolidated.",
        reply_markup=get_super_admin_main_menu()
    )
    await state.clear()

async def merge_user_data(primary_id: int, secondary_id: int):
    """Merge all data from secondary user into primary user"""
    async with db.get_db() as conn:
        # Transfer quiz attempts
        await conn.execute("""
            UPDATE quiz_attempts SET student_id = ? WHERE student_id = ?
        """, (primary_id, secondary_id))

        # Transfer homework submissions
        await conn.execute("""
            UPDATE homework_submissions SET student_id = ? WHERE student_id = ?
        """, (primary_id, secondary_id))

        # Transfer attendance records
        await conn.execute("""
            UPDATE attendance_records SET student_id = ? WHERE student_id = ?
        """, (primary_id, secondary_id))

        # Transfer payments
        await conn.execute("""
            UPDATE payments SET student_id = ? WHERE student_id = ?
        """, (primary_id, secondary_id))

        # Transfer parent-child relationships
        await conn.execute("""
            UPDATE parent_child SET parent_id = ? WHERE parent_id = ?
        """, (primary_id, secondary_id))
        await conn.execute("""
            UPDATE parent_child SET student_id = ? WHERE student_id = ?
        """, (primary_id, secondary_id))

        # Transfer messages
        await conn.execute("""
            UPDATE messages SET sender_id = ? WHERE sender_id = ?
        """, (primary_id, secondary_id))
        await conn.execute("""
            UPDATE messages SET receiver_id = ? WHERE receiver_id = ?
        """, (primary_id, secondary_id))

        # Transfer badges and certificates
        await conn.execute("""
            INSERT OR IGNORE INTO student_badges (student_id, badge_id, earned_at)
            SELECT ?, badge_id, earned_at FROM student_badges WHERE student_id = ?
        """, (primary_id, secondary_id))

        await conn.execute("""
            UPDATE certificates SET student_id = ? WHERE student_id = ?
        """, (primary_id, secondary_id))

        # Transfer leaderboard entries
        await conn.execute("""
            INSERT OR REPLACE INTO leaderboard_entries (student_id, center_id, class_id, level, total_points, weekly_points, monthly_points)
            SELECT ?, le.center_id, le.class_id, le.level,
                   COALESCE(le.total_points, 0) + COALESCE((SELECT total_points FROM leaderboard_entries WHERE student_id = ? AND center_id = le.center_id), 0),
                   COALESCE(le.weekly_points, 0),
                   COALESCE(le.monthly_points, 0)
            FROM leaderboard_entries le WHERE le.student_id = ?
        """, (primary_id, primary_id, secondary_id))

        await conn.execute("""
            DELETE FROM leaderboard_entries WHERE student_id = ?
        """, (secondary_id,))

        # Combine points
        await conn.execute("""
            UPDATE users SET
                total_points = total_points + (SELECT COALESCE(total_points, 0) FROM users WHERE id = ?),
                current_streak = MAX(current_streak, (SELECT COALESCE(current_streak, 0) FROM users WHERE id = ?)),
                longest_streak = MAX(longest_streak, (SELECT COALESCE(longest_streak, 0) FROM users WHERE id = ?))
            WHERE id = ?
        """, (secondary_id, secondary_id, secondary_id, primary_id))

        # Delete secondary user
        await conn.execute("DELETE FROM users WHERE id = ?", (secondary_id,))

        await conn.commit()

# ========================
# USER ACTIVITY LOGS
# ========================

@router.callback_query(F.data == "sa_user_activity")
async def user_activity_overview(callback: CallbackQuery, state: FSMContext):
    """Show user activity overview"""
    # Get recent activity across platform
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT al.*, u.full_name
            FROM audit_logs al
            LEFT JOIN users u ON al.user_id = u.id
            ORDER BY al.created_at DESC
            LIMIT 50
        """)
        logs = [dict(row) for row in await cursor.fetchall()]

    if not logs:
        await callback.message.edit_text(
            "No activity logs found.",
            reply_markup=get_back_keyboard("sa_back")
        )
        return

    text = "📊 **Recent Platform Activity**\n\n"

    for log in logs[:20]:
        timestamp = log['created_at'][:19] if log.get('created_at') else 'N/A'
        text += f"🕐 {timestamp}\n"
        text += f"👤 {log.get('full_name', 'System')}\n"
        text += f"🔧 {log['action']} - {log.get('entity_type', '')} #{log.get('entity_id', '')}\n"
        text += "─" * 30 + "\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Filter by User", callback_data="sa_filter_activity")],
        [InlineKeyboardButton(text="📥 Export Logs", callback_data="sa_export_logs")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("sa_user_activity_"))
async def view_user_activity(callback: CallbackQuery, state: FSMContext):
    """View activity for a specific user"""
    user_id = int(callback.data.replace("sa_user_activity_", ""))
    user = await db.get_user_by_id(user_id)

    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    # Get activity logs for this user across all centers
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT al.*, c.name as center_name
            FROM audit_logs al
            LEFT JOIN centers c ON al.center_id = c.id
            WHERE al.user_id = ?
            ORDER BY al.created_at DESC
            LIMIT 100
        """, (user_id,))
        logs = [dict(row) for row in await cursor.fetchall()]

    text = f"📊 **Activity: {user['full_name']}**\n\n"

    if not logs:
        text += "No activity recorded yet.\n"
    else:
        for log in logs[:30]:
            timestamp = log['created_at'][:19] if log.get('created_at') else 'N/A'
            center = log.get('center_name', 'Platform')
            text += f"🕐 {timestamp} | 🏢 {center}\n"
            text += f"🔧 {log['action']}\n"
            if log.get('new_values'):
                new_vals = json.loads(log['new_values']) if isinstance(log['new_values'], str) else log['new_values']
                text += f"   📝 {json.dumps(new_vals, indent=2)[:100]}\n"
            text += "─" * 30 + "\n"

    # Get additional stats
    async with db.get_db() as conn:
        # Quiz attempts
        cursor = await conn.execute("""
            SELECT COUNT(*) as count, MAX(completed_at) as last_attempt
            FROM quiz_attempts WHERE student_id = ?
        """, (user_id,))
        quiz_info = await cursor.fetchone()
        quiz_info = dict(quiz_info) if quiz_info else {}

        # Homework
        cursor = await conn.execute("""
            SELECT COUNT(*) as count, MAX(submitted_at) as last_submission
            FROM homework_submissions WHERE student_id = ?
        """, (user_id,))
        hw_info = await cursor.fetchone()
        hw_info = dict(hw_info) if hw_info else {}

        # Attendance
        cursor = await conn.execute("""
            SELECT COUNT(*) as count FROM attendance_records WHERE student_id = ?
        """, (user_id,))
        att_info = await cursor.fetchone()
        att_info = dict(att_info) if att_info else {}

        # Payments
        cursor = await conn.execute("""
            SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as total
            FROM payments WHERE student_id = ?
        """, (user_id,))
        pay_info = await cursor.fetchone()
        pay_info = dict(pay_info) if pay_info else {}

    text += "\n📈 **Summary Stats:**\n"
    text += f"• Quizzes: {quiz_info.get('count', 0)} (Last: {quiz_info.get('last_attempt', 'Never')})\n"
    text += f"• Homework: {hw_info.get('count', 0)} (Last: {hw_info.get('last_submission', 'Never')})\n"
    text += f"• Attendance Records: {att_info.get('count', 0)}\n"
    text += f"• Payments: {pay_info.get('count', 0)} (Total: {pay_info.get('total', 0):,.0f} UZS)\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Export User Data", callback_data=f"sa_export_user_{user_id}")],
        [InlineKeyboardButton(text="🔙 Back to User", callback_data=f"sa_user_detail_{user_id}")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
