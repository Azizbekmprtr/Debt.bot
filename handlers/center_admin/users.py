# handlers/center_admin/users.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
from typing import List, Dict
import database.queries as db
from keyboards.all_keyboards import (
    get_center_admin_main_menu, get_center_admin_users_menu,
    get_cancel_keyboard, get_confirm_keyboard, get_back_keyboard,
    get_pagination_keyboard
)
import re
import csv
import io

router = Router()

# ========================
# USER MANAGEMENT STATES
# ========================

class AddTeacherStates(StatesGroup):
    waiting_for_info = State()
    confirm = State()

class AddStudentStates(StatesGroup):
    waiting_for_info = State()
    waiting_for_level = State()
    confirm = State()

class AddParentStates(StatesGroup):
    waiting_for_info = State()
    waiting_for_child_link = State()
    confirm = State()

class EditUserStates(StatesGroup):
    selecting_user = State()
    selecting_field = State()
    entering_value = State()

class ImportUsersStates(StatesGroup):
    waiting_for_csv = State()
    preview = State()
    confirm_import = State()

# ========================
# HELPER: GET CENTER CONTEXT
# ========================

async def get_center_context(state: FSMContext) -> dict:
    """Get current center context from state"""
    data = await state.get_data()
    center_id = data.get('current_center_id')

    if not center_id:
        # Get from user roles
        user = await db.get_user_by_telegram_id(data.get('telegram_id', 0))
        if user:
            roles = await db.get_user_roles(user['id'])
            for role_data in roles:
                if role_data.get('center_id'):
                    center_id = role_data['center_id']
                    await state.update_data(current_center_id=center_id)
                    break

    center = await db.get_center_by_id(center_id) if center_id else None
    return {'center_id': center_id, 'center': center}

# ========================
# USERS MAIN MENU
# ========================

@router.message(F.text == "👥 Users")
async def users_main_menu(message: Message, state: FSMContext):
    """Show users management main menu"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    if not center_id:
        await message.answer("❌ No center context found. Please contact support.")
        return

    # Get user stats for this center
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT COUNT(DISTINCT ur.user_id) as total
            FROM user_roles ur
            WHERE ur.center_id = ? AND ur.role = 'teacher'
        """, (center_id,))
        teacher_count = (await cursor.fetchone())[0]

        cursor = await conn.execute("""
            SELECT COUNT(DISTINCT ur.user_id) as total
            FROM user_roles ur
            WHERE ur.center_id = ? AND ur.role = 'student'
        """, (center_id,))
        student_count = (await cursor.fetchone())[0]

        cursor = await conn.execute("""
            SELECT COUNT(DISTINCT ur.user_id) as total
            FROM user_roles ur
            WHERE ur.center_id = ? AND ur.role = 'parent'
        """, (center_id,))
        parent_count = (await cursor.fetchone())[0]

    text = "👥 **User Management**\n\n"
    text += f"📊 **Center Statistics:**\n"
    text += f"👨‍🏫 Teachers: **{teacher_count}**\n"
    text += f"🎓 Students: **{student_count}**\n"
    text += f"👪 Parents: **{parent_count}**\n\n"
    text += "Select action:"

    await message.answer(text, reply_markup=get_center_admin_users_menu())

# ========================
# ADD TEACHER
# ========================

@router.callback_query(F.data == "ca_add_teacher")
async def add_teacher_start(callback: CallbackQuery, state: FSMContext):
    """Start adding a teacher"""
    await callback.message.edit_text(
        "👨‍🏫 **Add New Teacher**\n\n"
        "Enter teacher information in one line:\n\n"
        "`Full Name [@username] [+998XXXXXXXXX] [TelegramID]`\n\n"
        "Examples:\n"
        "• `John Smith @john_teacher +998901234567`\n"
        "• `Jane Doe 123456789` (Telegram ID)\n"
        "• `Bob Wilson @bob_wilson` (Username only)\n\n"
        "Enter teacher info:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AddTeacherStates.waiting_for_info)

@router.message(AddTeacherStates.waiting_for_info, F.text)
async def add_teacher_process(message: Message, state: FSMContext):
    """Process teacher information"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    info = await parse_user_info(message.text.strip())

    if not info['full_name']:
        await message.answer("❌ Please provide at least a full name.")
        return

    # Check if user exists
    user = None
    if info.get('telegram_id'):
        user = await db.get_user_by_telegram_id(info['telegram_id'])
    elif info.get('username'):
        user = await db.get_user_by_username(info['username'])

    if not user:
        # Create new user
        user_id = await db.create_user(
            telegram_id=info.get('telegram_id'),
            full_name=info['full_name'],
            phone=info.get('phone'),
            username=info.get('username')
        )
        if not user_id:
            await message.answer("❌ Failed to create user. The Telegram ID might already be registered.")
            return
        user = await db.get_user_by_id(user_id)

    # Assign teacher role for this center
    await db.assign_role(user['id'], 'teacher', center_id, message.from_user.id)

    # Log audit
    await db.log_audit(
        user_id=message.from_user.id,
        action='add_teacher',
        entity_type='user',
        entity_id=user['id'],
        center_id=center_id,
        new_values={'name': info['full_name']}
    )

    await message.answer(
        f"✅ **Teacher Added Successfully!**\n\n"
        f"👨‍🏫 Name: **{user['full_name']}**\n"
        f"🆔 ID: {user['id']}\n"
        f"📱 Phone: {user.get('phone', 'N/A')}\n"
        f"💬 The teacher can now use /start to access their account.",
        reply_markup=get_center_admin_main_menu()
    )
    await state.clear()

async def parse_user_info(text: str) -> dict:
    """Parse user information from text input"""
    info = {
        'full_name': '',
        'username': None,
        'phone': None,
        'telegram_id': None
    }

    parts = text.split()

    # Extract Telegram ID (last part if numeric)
    if parts and parts[-1].isdigit() and len(parts[-1]) >= 5:
        info['telegram_id'] = int(parts[-1])
        parts = parts[:-1]

    # Extract phone number
    for i, part in enumerate(parts):
        if part.startswith('+') or (part.isdigit() and len(part) >= 10):
            info['phone'] = part.strip('+')
            parts.pop(i)
            break

    # Extract username
    for i, part in enumerate(parts):
        if part.startswith('@'):
            info['username'] = part.lstrip('@')
            parts.pop(i)
            break

    # Remaining parts are the name
    info['full_name'] = ' '.join(parts).strip().upper()

    return info

# ========================
# ADD STUDENT
# ========================

@router.callback_query(F.data == "ca_add_student")
async def add_student_start(callback: CallbackQuery, state: FSMContext):
    """Start adding a student"""
    await callback.message.edit_text(
        "🎓 **Add New Student**\n\n"
        "Enter student information:\n\n"
        "`Full Name [@username] [+998XXXXXXXXX] [TelegramID]`\n\n"
        "Examples:\n"
        "• `Alice Johnson @alice_student +998901234567`\n"
        "• `Bob Brown 987654321`\n\n"
        "Enter student info:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AddStudentStates.waiting_for_info)

@router.message(AddStudentStates.waiting_for_info, F.text)
async def add_student_process(message: Message, state: FSMContext):
    """Process student information"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    info = await parse_user_info(message.text.strip())

    if not info['full_name']:
        await message.answer("❌ Please provide at least a full name.")
        return

    # Check if user exists
    user = None
    if info.get('telegram_id'):
        user = await db.get_user_by_telegram_id(info['telegram_id'])
    elif info.get('username'):
        user = await db.get_user_by_username(info['username'])

    if not user:
        user_id = await db.create_user(
            telegram_id=info.get('telegram_id'),
            full_name=info['full_name'],
            phone=info.get('phone'),
            username=info.get('username')
        )
        if not user_id:
            await message.answer("❌ Failed to create user.")
            return
        user = await db.get_user_by_id(user_id)

    # Assign student role
    await db.assign_role(user['id'], 'student', center_id, message.from_user.id)

    await state.update_data(new_student=user, new_student_info=info)

    # Ask for level/schedule preference
    classes = await db.get_classes_for_center(center_id)

    if classes:
        buttons = []
        for cls in classes[:20]:
            buttons.append([InlineKeyboardButton(
                text=f"{cls['name']} ({cls['level']}) - {cls.get('student_count', 0)} students",
                callback_data=f"enroll_student_{user['id']}_{cls['id']}"
            )])
        buttons.append([InlineKeyboardButton(text="⏭️ Skip (Add to waitlist)", callback_data="skip_enrollment")])

        await message.answer(
            f"✅ Student: **{user['full_name']}**\n\n"
            "Select a class to enroll the student:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        await state.set_state(AddStudentStates.waiting_for_level)
    else:
        # No classes - just confirm
        await confirm_student_addition(message, state, user)

@router.callback_query(AddStudentStates.waiting_for_level, F.data.startswith("enroll_student_"))
async def enroll_student_to_class(callback: CallbackQuery, state: FSMContext):
    """Enroll student in selected class"""
    parts = callback.data.replace("enroll_student_", "").split("_")
    student_id = int(parts[0])
    class_id = int(parts[1])

    await db.enroll_student(student_id, class_id, callback.from_user.id)
    await callback.answer("✅ Student enrolled!")

    await callback.message.edit_text(
        "✅ Student enrolled in class!",
        reply_markup=get_back_keyboard("ca_list_users")
    )
    await state.clear()

@router.callback_query(AddStudentStates.waiting_for_level, F.data == "skip_enrollment")
async def skip_enrollment(callback: CallbackQuery, state: FSMContext):
    """Skip class enrollment"""
    await callback.message.edit_text(
        "✅ Student added to waitlist. They can be enrolled later.",
        reply_markup=get_back_keyboard("ca_list_users")
    )
    await state.clear()

async def confirm_student_addition(message, state, user):
    """Confirm student addition without class enrollment"""
    await message.answer(
        f"✅ **Student Added!**\n\n"
        f"🎓 Name: **{user['full_name']}**\n"
        f"🆔 ID: {user['id']}\n"
        f"⚠️ Student is not enrolled in any class yet.",
        reply_markup=get_center_admin_main_menu()
    )
    await state.clear()

# ========================
# ADD PARENT & LINK CHILD
# ========================

@router.callback_query(F.data == "ca_add_parent")
async def add_parent_start(callback: CallbackQuery, state: FSMContext):
    """Start adding a parent"""
    await callback.message.edit_text(
        "👪 **Add New Parent**\n\n"
        "Enter parent information:\n\n"
        "`Full Name [@username] [+998XXXXXXXXX] [TelegramID]`\n\n"
        "Enter parent info:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AddParentStates.waiting_for_info)

@router.message(AddParentStates.waiting_for_info, F.text)
async def add_parent_process(message: Message, state: FSMContext):
    """Process parent information"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    info = await parse_user_info(message.text.strip())

    if not info['full_name']:
        await message.answer("❌ Please provide at least a full name.")
        return

    user = None
    if info.get('telegram_id'):
        user = await db.get_user_by_telegram_id(info['telegram_id'])
    elif info.get('username'):
        user = await db.get_user_by_username(info['username'])

    if not user:
        user_id = await db.create_user(
            telegram_id=info.get('telegram_id'),
            full_name=info['full_name'],
            phone=info.get('phone'),
            username=info.get('username')
        )
        user = await db.get_user_by_id(user_id)

    # Assign parent role
    await db.assign_role(user['id'], 'parent', center_id, message.from_user.id)

    await state.update_data(new_parent=user, new_parent_id=user['id'])

    # Get students for linking
    students = await db.get_students_for_center(center_id)

    if students:
        buttons = []
        for student in students[:30]:
            buttons.append([InlineKeyboardButton(
                text=f"👶 {student['full_name']}",
                callback_data=f"link_child_{user['id']}_{student['id']}"
            )])
        buttons.append([InlineKeyboardButton(text="⏭️ Skip (Link later)", callback_data="skip_linking")])

        await message.answer(
            f"✅ Parent: **{user['full_name']}**\n\n"
            "Select child(ren) to link:\n"
            "(You can link multiple children)",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
        await state.set_state(AddParentStates.waiting_for_child_link)
    else:
        await message.answer(
            f"✅ **Parent Added!**\n\n"
            f"👪 Name: **{user['full_name']}**\n"
            f"🆔 ID: {user['id']}\n"
            f"⚠️ No students available to link yet.",
            reply_markup=get_center_admin_main_menu()
        )
        await state.clear()

@router.callback_query(AddParentStates.waiting_for_child_link, F.data.startswith("link_child_"))
async def link_child_to_parent(callback: CallbackQuery, state: FSMContext):
    """Link a child to parent"""
    parts = callback.data.replace("link_child_", "").split("_")
    parent_id = int(parts[0])
    child_id = int(parts[1])

    await db.link_parent_to_child(parent_id, child_id)

    parent = await db.get_user_by_id(parent_id)
    child = await db.get_user_by_id(child_id)

    await callback.answer(f"✅ {parent['full_name']} linked to {child['full_name']}")

    # Continue linking more
    ctx = await get_center_context(state)
    students = await db.get_students_for_center(ctx['center_id'])

    # Get already linked children
    linked = await db.get_children_for_parent(parent_id)
    linked_ids = [c['id'] for c in linked]

    unlinked = [s for s in students if s['id'] not in linked_ids]

    if unlinked:
        buttons = []
        for student in unlinked[:20]:
            buttons.append([InlineKeyboardButton(
                text=f"👶 {student['full_name']}",
                callback_data=f"link_child_{parent_id}_{student['id']}"
            )])
        buttons.append([InlineKeyboardButton(text="✅ Done", callback_data="finish_linking")])

        await callback.message.edit_text(
            f"✅ Linked: {child['full_name']}\n\n"
            "Select another child to link or 'Done':",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    else:
        await callback.message.edit_text(
            f"✅ All students linked to {parent['full_name']}!",
            reply_markup=get_back_keyboard("ca_list_users")
        )
        await state.clear()

@router.callback_query(AddParentStates.waiting_for_child_link, F.data == "skip_linking")
@router.callback_query(F.data == "finish_linking")
async def finish_parent_linking(callback: CallbackQuery, state: FSMContext):
    """Finish parent creation"""
    await callback.message.edit_text(
        "✅ Parent setup complete!",
        reply_markup=get_back_keyboard("ca_list_users")
    )
    await state.clear()

# ========================
# VIEW ALL USERS
# ========================

@router.callback_query(F.data == "ca_list_users")
async def list_all_users(callback: CallbackQuery, state: FSMContext):
    """List all users in the center"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    users = await get_center_users(center_id)

    await state.update_data(center_users=users, center_users_page=0)
    await display_center_users_page(callback.message, state, 0)

async def get_center_users(center_id: int, role: str = None) -> List[Dict]:
    """Get all users for a center"""
    async with db.get_db() as conn:
        query = """
            SELECT DISTINCT u.*, GROUP_CONCAT(DISTINCT ur.role) as roles
            FROM users u
            JOIN user_roles ur ON u.id = ur.user_id
            WHERE ur.center_id = ?
        """
        params = [center_id]

        if role:
            query += " AND ur.role = ?"
            params.append(role)

        query += " GROUP BY u.id ORDER BY u.full_name"

        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def display_center_users_page(message, state: FSMContext, page: int):
    """Display a page of center users"""
    data = await state.get_data()
    users = data.get('center_users', [])
    per_page = 10
    total_pages = max(1, (len(users) + per_page - 1) // per_page)
    start = page * per_page
    end = start + per_page
    page_users = users[start:end]

    text = "👥 **Center Users**\n\n"

    for user in page_users:
        roles = user.get('roles', 'student') or 'student'
        role_emoji = {
            'teacher': '👨‍🏫', 'student': '🎓', 'parent': '👪',
            'center_admin': '🏢'
        }

        # Get primary role emoji
        first_role = roles.split(',')[0] if roles else 'student'
        emoji = role_emoji.get(first_role, '👤')

        text += f"{emoji} **{user['full_name']}**\n"
        text += f"   ID: {user['id']} | TG: {user.get('telegram_id', 'N/A')}\n"
        text += f"   Roles: {roles}\n"
        text += f"   📞 {user.get('phone', 'N/A')}\n"
        text += "─" * 30 + "\n"

    # Build keyboard
    buttons = []
    for user in page_users:
        buttons.append([InlineKeyboardButton(
            text=f"👤 {user['full_name'][:40]}",
            callback_data=f"ca_user_detail_{user['id']}"
        )])

    # Pagination
    pagination = []
    if page > 0:
        pagination.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"causers_page_{page-1}"))
    pagination.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        pagination.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"causers_page_{page+1}"))
    buttons.append(pagination)

    # Filter buttons
    buttons.append([
        InlineKeyboardButton(text="👨‍🏫 Teachers", callback_data="ca_filter_teacher"),
        InlineKeyboardButton(text="🎓 Students", callback_data="ca_filter_student"),
        InlineKeyboardButton(text="👪 Parents", callback_data="ca_filter_parent")
    ])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.edit_text(text, reply_markup=keyboard)
    await state.update_data(center_users_page=page)

@router.callback_query(F.data.startswith("causers_page_"))
async def handle_users_pagination(callback: CallbackQuery, state: FSMContext):
    """Handle users pagination"""
    page = int(callback.data.replace("causers_page_", ""))
    await display_center_users_page(callback.message, state, page)

@router.callback_query(F.data.startswith("ca_filter_"))
async def filter_users_by_role(callback: CallbackQuery, state: FSMContext):
    """Filter users by role"""
    role = callback.data.replace("ca_filter_", "")
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    users = await get_center_users(center_id, role)

    await state.update_data(center_users=users, center_users_page=0)
    await display_center_users_page(callback.message, state, 0)

# ========================
# USER DETAILS & EDIT
# ========================

@router.callback_query(F.data.startswith("ca_user_detail_"))
async def view_user_detail(callback: CallbackQuery, state: FSMContext):
    """View user details"""
    user_id = int(callback.data.replace("ca_user_detail_", ""))
    user = await db.get_user_by_id(user_id)

    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    # Get classes for this user
    classes = await db.get_classes_for_student(user_id) if user_id else []
    children = await db.get_children_for_parent(user_id) if user_id else []
    parents = await db.get_parents_for_student(user_id) if user_id else []

    text = f"👤 **{user['full_name']}**\n\n"
    text += f"🆔 ID: {user['id']}\n"
    text += f"📱 TG: {user.get('telegram_id', 'N/A')}\n"
    text += f"📞 Phone: {user.get('phone', 'N/A')}\n"
    text += f"📅 Joined: {user['created_at'][:10] if user.get('created_at') else 'N/A'}\n"

    if classes:
        text += f"\n🏫 **Classes:**\n"
        for cls in classes:
            text += f"• {cls['name']} ({cls['level']})\n"

    if children:
        text += f"\n👶 **Children:**\n"
        for child in children:
            text += f"• {child['full_name']}\n"

    if parents:
        text += f"\n👪 **Parents:**\n"
        for parent in parents:
            text += f"• {parent['full_name']}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit", callback_data=f"ca_edit_user_{user_id}")],
        [InlineKeyboardButton(text="🏫 Enroll in Class", callback_data=f"ca_enroll_user_{user_id}")],
        [InlineKeyboardButton(text="🗑️ Remove from Center", callback_data=f"ca_remove_user_{user_id}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="ca_list_users")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("ca_edit_user_"))
async def edit_user_start(callback: CallbackQuery, state: FSMContext):
    """Start editing a user"""
    user_id = int(callback.data.replace("ca_edit_user_", ""))
    user = await db.get_user_by_id(user_id)

    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    await state.update_data(edit_user_id=user_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📛 Edit Name", callback_data="ca_edit_field_name")],
        [InlineKeyboardButton(text="📞 Edit Phone", callback_data="ca_edit_field_phone")],
        [InlineKeyboardButton(text="🏫 Change Class", callback_data=f"ca_enroll_user_{user_id}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data=f"ca_user_detail_{user_id}")]
    ])

    await callback.message.edit_text(
        f"✏️ **Edit: {user['full_name']}**\n\n"
        "Select field to edit:",
        reply_markup=keyboard
    )
    await state.set_state(EditUserStates.selecting_field)

@router.callback_query(EditUserStates.selecting_field, F.data == "ca_edit_field_name")
async def edit_user_name(callback: CallbackQuery, state: FSMContext):
    """Edit user name"""
    await callback.message.edit_text(
        "Enter new full name:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(EditUserStates.entering_value)

@router.callback_query(EditUserStates.selecting_field, F.data == "ca_edit_field_phone")
async def edit_user_phone(callback: CallbackQuery, state: FSMContext):
    """Edit user phone"""
    await callback.message.edit_text(
        "Enter new phone number:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(EditUserStates.entering_value)

@router.message(EditUserStates.entering_value, F.text)
async def process_edit_value(message: Message, state: FSMContext):
    """Process edited value"""
    data = await state.get_data()
    user_id = data['edit_user_id']
    new_value = message.text.strip()

    await db.update_user_field(user_id, 'full_name' if 'name' in data.get('edit_field', '') else 'phone', new_value)

    # Log
    await db.log_audit(
        user_id=message.from_user.id,
        action='edit_user',
        entity_type='user',
        entity_id=user_id
    )

    await message.answer(
        "✅ User updated!",
        reply_markup=get_back_keyboard(f"ca_user_detail_{user_id}")
    )
    await state.clear()

# ========================
# ENROLL USER IN CLASS
# ========================

@router.callback_query(F.data.startswith("ca_enroll_user_"))
async def enroll_user_start(callback: CallbackQuery, state: FSMContext):
    """Start enrolling a user in a class"""
    user_id = int(callback.data.replace("ca_enroll_user_", ""))
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    classes = await db.get_classes_for_center(center_id)

    if not classes:
        await callback.answer("No classes available", show_alert=True)
        return

    await state.update_data(enroll_user_id=user_id)

    buttons = []
    for cls in classes:
        buttons.append([InlineKeyboardButton(
            text=f"{cls['name']} ({cls['level']})",
            callback_data=f"enroll_in_class_{user_id}_{cls['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data=f"ca_user_detail_{user_id}")])

    await callback.message.edit_text(
        "Select class to enroll user:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("enroll_in_class_"))
async def enroll_user_execute(callback: CallbackQuery, state: FSMContext):
    """Execute enrollment"""
    parts = callback.data.replace("enroll_in_class_", "").split("_")
    user_id = int(parts[0])
    class_id = int(parts[1])

    success = await db.enroll_student(user_id, class_id, callback.from_user.id)

    if success:
        await callback.answer("✅ User enrolled!")
    else:
        await callback.answer("❌ Failed to enroll. User might already be in this class.", show_alert=True)

    await view_user_detail(callback, state)

# ========================
# REMOVE USER FROM CENTER
# ========================

@router.callback_query(F.data.startswith("ca_remove_user_"))
async def remove_user_start(callback: CallbackQuery, state: FSMContext):
    """Start removing a user from center"""
    user_id = int(callback.data.replace("ca_remove_user_", ""))
    user = await db.get_user_by_id(user_id)

    if not user:
        await callback.answer("User not found", show_alert=True)
        return

    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    await state.update_data(remove_user_id=user_id)

    await callback.message.edit_text(
        f"⚠️ **Remove User from Center?**\n\n"
        f"👤 {user['full_name']}\n\n"
        f"This will remove all center-specific roles and data.\n"
        f"The user's account will NOT be deleted.\n\n"
        f"Confirm removal?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Yes, Remove", callback_data=f"confirm_remove_user_{user_id}"),
                InlineKeyboardButton(text="❌ Cancel", callback_data=f"ca_user_detail_{user_id}")
            ]
        ])
    )

@router.callback_query(F.data.startswith("confirm_remove_user_"))
async def remove_user_execute(callback: CallbackQuery, state: FSMContext):
    """Execute user removal"""
    user_id = int(callback.data.replace("confirm_remove_user_", ""))
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    # Remove center-specific roles
    async with db.get_db() as conn:
        await conn.execute("""
            DELETE FROM user_roles WHERE user_id = ? AND center_id = ?
        """, (user_id, center_id))

        # Unenroll from classes
        await conn.execute("""
            UPDATE class_enrollments SET is_active = 0, unenrolled_at = CURRENT_TIMESTAMP
            WHERE student_id = ? AND class_id IN (
                SELECT id FROM classes WHERE center_id = ?
            )
        """, (user_id, center_id))

        await conn.commit()

    # Log
    await db.log_audit(
        user_id=callback.from_user.id,
        action='remove_user_from_center',
        entity_type='user',
        entity_id=user_id,
        center_id=center_id
    )

    await callback.message.edit_text(
        "✅ User removed from center.",
        reply_markup=get_back_keyboard("ca_list_users")
    )

# ========================
# SEARCH USERS
# ========================

@router.callback_query(F.data == "ca_search_users")
async def search_users_start(callback: CallbackQuery, state: FSMContext):
    """Start searching users"""
    await callback.message.edit_text(
        "🔍 **Search Users**\n\n"
        "Enter search term (name, phone, or Telegram ID):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state("ca_search_users")

@router.message(F.text, state="ca_search_users")
async def search_users_process(message: Message, state: FSMContext):
    """Process user search"""
    search_term = message.text.strip()
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    if len(search_term) < 2:
        await message.answer("❌ Search term too short.")
        return

    # Search within center
    async with db.get_db() as conn:
        try:
            telegram_id = int(search_term)
            cursor = await conn.execute("""
                SELECT DISTINCT u.* FROM users u
                JOIN user_roles ur ON u.id = ur.user_id
                WHERE ur.center_id = ? AND u.telegram_id = ?
            """, (center_id, telegram_id))
        except ValueError:
            cursor = await conn.execute("""
                SELECT DISTINCT u.* FROM users u
                JOIN user_roles ur ON u.id = ur.user_id
                WHERE ur.center_id = ? AND (u.full_name LIKE ? OR u.phone LIKE ?)
                LIMIT 20
            """, (center_id, f'%{search_term}%', f'%{search_term}%'))

        users = [dict(row) for row in await cursor.fetchall()]

    if not users:
        await message.answer(
            "❌ No users found.",
            reply_markup=get_back_keyboard("ca_list_users")
        )
        await state.clear()
        return

    text = f"🔍 **Search Results for '{search_term}'**\n\n"
    buttons = []

    for user in users:
        text += f"• {user['full_name']} (ID: {user['id']})\n"
        buttons.append([InlineKeyboardButton(
            text=f"👤 {user['full_name']}",
            callback_data=f"ca_user_detail_{user['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_list_users")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.clear()

# ========================
# IMPORT USERS (CSV)
# ========================

@router.callback_query(F.data == "ca_import_users")
async def import_users_start(callback: CallbackQuery, state: FSMContext):
    """Start importing users from CSV"""
    await callback.message.edit_text(
        "📥 **Import Users**\n\n"
        "Please send a CSV file with the following columns:\n"
        "`full_name,role,phone,telegram_id,username`\n\n"
        "Example CSV content:\n"
        "```\n"
        "full_name,role,phone,telegram_id,username\n"
        "John Smith,teacher,+998901234567,,@john_teacher\n"
        "Alice Johnson,student,,123456789,\n"
        "Bob Wilson,parent,+998909876543,,\n"
        "```\n\n"
        "Send the CSV file now:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ImportUsersStates.waiting_for_csv)

@router.message(ImportUsersStates.waiting_for_csv, F.document)
async def process_csv_import(message: Message, state: FSMContext):
    """Process CSV file import"""
    document = message.document

    # Download file
    file = await message.bot.get_file(document.file_id)
    file_content = await message.bot.download_file(file.file_path)

    # Parse CSV
    try:
        csv_text = file_content.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_text))
        users_data = list(reader)
    except Exception as e:
        await message.answer(f"❌ Failed to parse CSV: {str(e)}")
        return

    if not users_data:
        await message.answer("❌ No valid data found in CSV.")
        return

    await state.update_data(import_users=users_data)

    # Preview
    text = f"📥 **CSV Import Preview**\n\n"
    text += f"Total rows: **{len(users_data)}**\n\n"
    text += "First 5 entries:\n"

    for i, user in enumerate(users_data[:5]):
        text += f"{i+1}. {user.get('full_name', 'N/A')} - {user.get('role', 'student')}\n"

    text += "\nImport these users?"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Import All", callback_data="confirm_csv_import"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")
        ]
    ])

    await message.answer(text, reply_markup=keyboard)
    await state.set_state(ImportUsersStates.confirm_import)

@router.callback_query(ImportUsersStates.confirm_import, F.data == "confirm_csv_import")
async def execute_csv_import(callback: CallbackQuery, state: FSMContext):
    """Execute CSV import"""
    data = await state.get_data()
    users_data = data.get('import_users', [])
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    imported = {'success': 0, 'failed': 0, 'skipped': 0}

    for user_data in users_data:
        try:
            full_name = user_data.get('full_name', '').strip().upper()
            role = user_data.get('role', 'student').strip().lower()
            phone = user_data.get('phone', '').strip() or None
            username = user_data.get('username', '').strip().lstrip('@') or None

            telegram_id_str = user_data.get('telegram_id', '').strip()
            telegram_id = int(telegram_id_str) if telegram_id_str.isdigit() else None

            if not full_name:
                imported['failed'] += 1
                continue

            # Create or get user
            user = None
            if telegram_id:
                user = await db.get_user_by_telegram_id(telegram_id)
            elif username:
                user = await db.get_user_by_username(username)

            if not user:
                user_id = await db.create_user(
                    telegram_id=telegram_id,
                    full_name=full_name,
                    phone=phone,
                    username=username
                )
                if user_id:
                    user = await db.get_user_by_id(user_id)
                    imported['success'] += 1
                else:
                    imported['failed'] += 1
                    continue
            else:
                imported['skipped'] += 1

            # Assign role for center
            if role in ['teacher', 'student', 'parent', 'center_admin']:
                await db.assign_role(user['id'], role, center_id, callback.from_user.id)

        except Exception as e:
            imported['failed'] += 1

    # Log
    await db.log_audit(
        user_id=callback.from_user.id,
        action='import_users',
        entity_type='users',
        center_id=center_id,
        new_values=imported
    )

    await callback.message.edit_text(
        f"✅ **Import Complete!**\n\n"
        f"✅ Imported: {imported['success']}\n"
        f"⏭️ Skipped (existing): {imported['skipped']}\n"
        f"❌ Failed: {imported['failed']}\n"
        f"📊 Total processed: {len(users_data)}",
        reply_markup=get_back_keyboard("ca_list_users")
    )
    await state.clear()

# ========================
# NAVIGATION
# ========================

@router.callback_query(F.data == "ca_back")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    """Return to center admin main menu"""
    await callback.message.delete()
    await callback.message.answer(
        "🏢 Center Admin Panel",
        reply_markup=get_center_admin_main_menu()
    )
