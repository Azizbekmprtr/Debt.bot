# handlers/center_admin/classes.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, time
import database.queries as db
from keyboards.all_keyboards import (
    get_center_admin_main_menu, get_center_admin_classes_menu,
    get_cancel_keyboard, get_confirm_keyboard, get_back_keyboard,
    get_pagination_keyboard
)
from utils.helpers import format_price
import re

router = Router()

# ========================
# CLASS MANAGEMENT STATES
# ========================

class CreateClassStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_level = State()
    waiting_for_price = State()
    waiting_for_description = State()
    waiting_for_max_students = State()
    confirm = State()

class EditClassStates(StatesGroup):
    selecting_field = State()
    entering_value = State()

class ScheduleStates(StatesGroup):
    selecting_day = State()
    entering_time = State()
    entering_room = State()
    entering_subject = State()
    confirm = State()

class AssignTeacherStates(StatesGroup):
    selecting_teacher = State()
    confirm = State()

# ========================
# HELPER: GET CENTER CONTEXT
# ========================

async def get_center_context(state: FSMContext) -> dict:
    """Get current center context from state"""
    data = await state.get_data()
    center_id = data.get('current_center_id')

    if not center_id:
        user_data = data
        if not center_id:
            return {'center_id': None, 'center': None}

    center = await db.get_center_by_id(center_id) if center_id else None
    return {'center_id': center_id, 'center': center}

# ========================
# CLASSES MAIN MENU
# ========================

@router.message(F.text == "🏫 Classes")
async def classes_main_menu(message: Message, state: FSMContext):
    """Show classes management main menu"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    if not center_id:
        await message.answer("❌ No center context found.")
        return

    classes = await db.get_classes_for_center(center_id)
    active_count = len([c for c in classes if not c.get('is_archived')])
    archived_count = len([c for c in classes if c.get('is_archived')])

    text = "🏫 **Class Management**\n\n"
    text += f"📊 **Summary:**\n"
    text += f"• Active Classes: **{active_count}**\n"
    text += f"• Archived Classes: **{archived_count}**\n\n"
    text += "Select action:"

    await message.answer(text, reply_markup=get_center_admin_classes_menu())

# ========================
# CREATE CLASS
# ========================

@router.callback_query(F.data == "ca_create_class")
async def create_class_start(callback: CallbackQuery, state: FSMContext):
    """Start creating a new class"""
    await callback.message.edit_text(
        "🏫 **Create New Class**\n\n"
        "Enter class name (e.g., 'Morning Group A', 'B2 Intensive'):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateClassStates.waiting_for_name)

@router.message(CreateClassStates.waiting_for_name, F.text)
async def process_class_name(message: Message, state: FSMContext):
    """Process class name"""
    name = message.text.strip()

    if len(name) < 2 or len(name) > 100:
        await message.answer("❌ Class name must be between 2 and 100 characters.")
        return

    await state.update_data(class_name=name)

    # Level selection
    levels = ["A1 - Beginner", "A2 - Elementary", "B1 - Intermediate", "B2 - Upper Intermediate", "C1 - Advanced"]

    buttons = []
    for level in levels:
        buttons.append([InlineKeyboardButton(text=level, callback_data=f"class_level_{level[:2]}")])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="cancel")])

    await message.answer(
        f"✅ Name: **{name}**\n\n"
        "Select level:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(CreateClassStates.waiting_for_level)

@router.callback_query(CreateClassStates.waiting_for_level, F.data.startswith("class_level_"))
async def process_class_level(callback: CallbackQuery, state: FSMContext):
    """Process class level"""
    level = callback.data.replace("class_level_", "")
    await state.update_data(class_level=level)

    await callback.message.edit_text(
        f"✅ Level: **{level}**\n\n"
        "Enter monthly price (in UZS, 0 for free):\n"
        "Example: 350000 or 350 000",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateClassStates.waiting_for_price)

@router.message(CreateClassStates.waiting_for_price, F.text)
async def process_class_price(message: Message, state: FSMContext):
    """Process class price"""
    try:
        price_text = message.text.strip().replace(" ", "")
        price = int(price_text)
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Please enter a valid price (0 or positive number):")
        return

    await state.update_data(class_price=price)

    await message.answer(
        f"✅ Price: **{format_price(price)} UZS**\n\n"
        "Enter class description (optional, type 'skip' to skip):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateClassStates.waiting_for_description)

@router.message(CreateClassStates.waiting_for_description, F.text)
async def process_class_description(message: Message, state: FSMContext):
    """Process class description"""
    description = message.text.strip()
    if description.lower() == 'skip':
        description = None

    await state.update_data(class_description=description)

    await message.answer(
        "Enter maximum number of students (default: 30):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateClassStates.waiting_for_max_students)

@router.message(CreateClassStates.waiting_for_max_students, F.text)
async def process_class_max_students(message: Message, state: FSMContext):
    """Process max students"""
    try:
        max_students = int(message.text.strip())
        if max_students < 1 or max_students > 200:
            raise ValueError
    except ValueError:
        await message.answer("❌ Please enter a number between 1 and 200:")
        return

    data = await state.get_data()

    # Show confirmation
    text = "🏫 **Confirm Class Creation**\n\n"
    text += f"📛 **Name:** {data['class_name']}\n"
    text += f"📊 **Level:** {data['class_level']}\n"
    text += f"💰 **Price:** {format_price(data['class_price'])} UZS/month\n"
    text += f"👥 **Max Students:** {max_students}\n"
    if data.get('class_description'):
        text += f"📄 **Description:** {data['class_description']}\n"
    text += "\nCreate this class?"

    await state.update_data(class_max_students=max_students)

    await message.answer(text, reply_markup=get_confirm_keyboard("confirm_create_class", "cancel"))
    await state.set_state(CreateClassStates.confirm)

@router.callback_query(CreateClassStates.confirm, F.data == "confirm_create_class")
async def confirm_create_class(callback: CallbackQuery, state: FSMContext):
    """Finalize class creation"""
    data = await state.get_data()
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    class_id = await db.create_class(
        center_id=center_id,
        name=data['class_name'],
        level=data['class_level'],
        price=data['class_price'],
        description=data.get('class_description'),
        max_students=data['class_max_students'],
        created_by=callback.from_user.id
    )

    if class_id:
        # Log audit
        await db.log_audit(
            user_id=callback.from_user.id,
            action='create_class',
            entity_type='class',
            entity_id=class_id,
            center_id=center_id,
            new_values={'name': data['class_name'], 'level': data['class_level']}
        )

        await callback.message.edit_text(
            f"✅ **Class Created!**\n\n"
            f"🏫 **{data['class_name']}**\n"
            f"📊 Level: {data['class_level']}\n"
            f"💰 Price: {format_price(data['class_price'])} UZS\n"
            f"🆔 ID: {class_id}\n\n"
            "You can now:\n"
            "• Set the class schedule\n"
            "• Assign teachers\n"
            "• Enroll students",
            reply_markup=get_back_keyboard("ca_list_classes")
        )
    else:
        await callback.message.edit_text(
            "❌ Failed to create class.",
            reply_markup=get_back_keyboard("ca_back")
        )

    await state.clear()

# ========================
# VIEW ALL CLASSES
# ========================

@router.callback_query(F.data == "ca_list_classes")
async def list_all_classes(callback: CallbackQuery, state: FSMContext):
    """List all classes in the center"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    classes = await db.get_classes_for_center(center_id, include_archived=True)

    if not classes:
        await callback.message.edit_text(
            "📋 No classes found. Create your first class!",
            reply_markup=get_back_keyboard("ca_back")
        )
        return

    await state.update_data(center_classes=classes, classes_page=0)
    await display_classes_page(callback.message, state, 0)

async def display_classes_page(message, state: FSMContext, page: int):
    """Display a page of classes"""
    data = await state.get_data()
    classes = data.get('center_classes', [])
    per_page = 5
    total_pages = max(1, (len(classes) + per_page - 1) // per_page)
    start = page * per_page
    end = start + per_page
    page_classes = classes[start:end]

    text = "🏫 **All Classes**\n\n"

    for cls in page_classes:
        status = "📦 Archived" if cls.get('is_archived') else "🟢 Active"
        text += f"**{cls['name']}** ({cls['level']})\n"
        text += f"   Status: {status}\n"
        text += f"   Students: {cls.get('student_count', 0)}\n"
        text += f"   Price: {format_price(cls.get('price', 0))} UZS\n"
        text += f"   Teachers: {cls.get('teacher_names', 'None')}\n"
        text += "─" * 30 + "\n"

    buttons = []
    for cls in page_classes:
        buttons.append([InlineKeyboardButton(
            text=f"📊 {cls['name']} - Details",
            callback_data=f"ca_class_detail_{cls['id']}"
        )])

    # Pagination
    pagination = []
    if page > 0:
        pagination.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"classes_page_{page-1}"))
    pagination.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        pagination.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"classes_page_{page+1}"))
    buttons.append(pagination)

    buttons.append([InlineKeyboardButton(text="➕ Create Class", callback_data="ca_create_class")])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.edit_text(text, reply_markup=keyboard)
    await state.update_data(classes_page=page)

@router.callback_query(F.data.startswith("classes_page_"))
async def handle_classes_pagination(callback: CallbackQuery, state: FSMContext):
    """Handle classes pagination"""
    page = int(callback.data.replace("classes_page_", ""))
    await display_classes_page(callback.message, state, page)

# ========================
# CLASS DETAILS
# ========================

@router.callback_query(F.data.startswith("ca_class_detail_"))
async def view_class_detail(callback: CallbackQuery, state: FSMContext):
    """View detailed class information"""
    class_id = int(callback.data.replace("ca_class_detail_", ""))

    # Get class with details
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT c.*,
                   COUNT(DISTINCT ce.student_id) as enrolled_count,
                   GROUP_CONCAT(DISTINCT u.full_name) as teacher_names
            FROM classes c
            LEFT JOIN class_enrollments ce ON c.id = ce.class_id AND ce.is_active = 1
            LEFT JOIN class_teachers ct ON c.id = ct.class_id
            LEFT JOIN users u ON ct.teacher_id = u.id
            WHERE c.id = ?
            GROUP BY c.id
        """, (class_id,))
        class_data = await cursor.fetchone()

        if not class_data:
            await callback.answer("Class not found", show_alert=True)
            return

        class_data = dict(class_data)

        # Get schedule
        cursor = await conn.execute("""
            SELECT * FROM schedules WHERE class_id = ? AND is_active = 1
            ORDER BY day_of_week, start_time
        """, (class_id,))
        schedule = [dict(row) for row in await cursor.fetchall()]

        # Get enrolled students
        cursor = await conn.execute("""
            SELECT u.id, u.full_name, u.phone, ce.enrolled_at
            FROM class_enrollments ce
            JOIN users u ON ce.student_id = u.id
            WHERE ce.class_id = ? AND ce.is_active = 1
            ORDER BY u.full_name
        """, (class_id,))
        students = [dict(row) for row in await cursor.fetchall()]

    await state.update_data(current_class_id=class_id, current_class=class_data)

    text = f"🏫 **{class_data['name']}** ({class_data['level']})\n\n"
    text += f"📊 **Status:** {'📦 Archived' if class_data.get('is_archived') else '🟢 Active'}\n"
    text += f"💰 **Price:** {format_price(class_data.get('price', 0))} UZS/month\n"
    text += f"👥 **Students:** {class_data['enrolled_count']}/{class_data.get('max_students', 30)}\n"
    text += f"👨‍🏫 **Teachers:** {class_data.get('teacher_names', 'None assigned')}\n"

    if class_data.get('description'):
        text += f"📄 **Description:** {class_data['description']}\n"

    if schedule:
        text += f"\n📅 **Schedule:**\n"
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        for s in schedule:
            day = day_names[s['day_of_week']]
            text += f"• {day}: {s['start_time']}-{s['end_time']} | Room: {s.get('room', 'N/A')}\n"
            if s.get('subject'):
                text += f"  Subject: {s['subject']}\n"

    if students:
        text += f"\n👥 **Enrolled Students ({len(students)}):**\n"
        for student in students[:10]:
            text += f"• {student['full_name']}\n"
        if len(students) > 10:
            text += f"... and {len(students) - 10} more\n"

    # Action buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit Class", callback_data=f"ca_edit_class_{class_id}")],
        [InlineKeyboardButton(text="📅 Manage Schedule", callback_data=f"ca_manage_schedule_{class_id}")],
        [InlineKeyboardButton(text="👨‍🏫 Assign Teacher", callback_data=f"ca_assign_teacher_{class_id}")],
        [InlineKeyboardButton(text="👥 View Roster", callback_data=f"ca_view_roster_{class_id}")],
        [
            InlineKeyboardButton(
                text="📦 Archive" if not class_data.get('is_archived') else "🔄 Unarchive",
                callback_data=f"ca_toggle_archive_{class_id}"
            ),
            InlineKeyboardButton(text="🗑️ Delete", callback_data=f"ca_delete_class_{class_id}")
        ],
        [InlineKeyboardButton(text="🔙 Back", callback_data="ca_list_classes")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

# ========================
# SET CLASS SCHEDULE
# ========================

@router.callback_query(F.data.startswith("ca_manage_schedule_"))
async def manage_schedule_start(callback: CallbackQuery, state: FSMContext):
    """Start managing class schedule"""
    class_id = int(callback.data.replace("ca_manage_schedule_", ""))
    await state.update_data(schedule_class_id=class_id)

    # Get existing schedule
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT * FROM schedules WHERE class_id = ? AND is_active = 1
            ORDER BY day_of_week
        """, (class_id,))
        existing_schedule = [dict(row) for row in await cursor.fetchall()]

    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    buttons = []
    for i, day in enumerate(day_names):
        has_schedule = any(s['day_of_week'] == i for s in existing_schedule)
        prefix = "✅" if has_schedule else "➕"
        buttons.append([InlineKeyboardButton(
            text=f"{prefix} {day}",
            callback_data=f"schedule_day_{class_id}_{i}"
        )])

    buttons.append([InlineKeyboardButton(text="🗑️ Clear All Schedule", callback_data=f"clear_schedule_{class_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data=f"ca_class_detail_{class_id}")])

    text = "📅 **Manage Schedule**\n\n"
    text += "Select day to set/cancel class:\n"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("schedule_day_"))
async def set_schedule_for_day(callback: CallbackQuery, state: FSMContext):
    """Set schedule for a specific day"""
    parts = callback.data.replace("schedule_day_", "").split("_")
    class_id = int(parts[0])
    day = int(parts[1])
    day_name = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][day]

    await state.update_data(schedule_day=day, schedule_class_id=class_id)

    await callback.message.edit_text(
        f"📅 **Set Schedule: {day_name}**\n\n"
        "Enter time slot (HH:MM-HH:MM):\n"
        "Example: 09:00-10:30",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ScheduleStates.entering_time)

@router.message(ScheduleStates.entering_time, F.text)
async def process_schedule_time(message: Message, state: FSMContext):
    """Process schedule time"""
    time_text = message.text.strip()

    if not re.match(r'^\d{2}:\d{2}-\d{2}:\d{2}$', time_text):
        await message.answer("❌ Invalid format. Use HH:MM-HH:MM (e.g., 09:00-10:30):")
        return

    start_time, end_time = time_text.split("-")

    # Validate times
    try:
        start = datetime.strptime(start_time, "%H:%M").time()
        end = datetime.strptime(end_time, "%H:%M").time()
        if start >= end:
            await message.answer("❌ Start time must be before end time.")
            return
    except ValueError:
        await message.answer("❌ Invalid time. Use HH:MM format.")
        return

    await state.update_data(schedule_start=start_time, schedule_end=end_time)

    await message.answer(
        "Enter room/location:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ScheduleStates.entering_room)

@router.message(ScheduleStates.entering_room, F.text)
async def process_schedule_room(message: Message, state: FSMContext):
    """Process room"""
    room = message.text.strip()
    await state.update_data(schedule_room=room)

    await message.answer(
        "Enter subject/topic for this session (optional, type 'skip'):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(ScheduleStates.entering_subject)

@router.message(ScheduleStates.entering_subject, F.text)
async def process_schedule_subject(message: Message, state: FSMContext):
    """Process subject and confirm"""
    subject = message.text.strip()
    if subject.lower() == 'skip':
        subject = None

    data = await state.get_data()
    day_name = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'][data['schedule_day']]

    text = "📅 **Confirm Schedule**\n\n"
    text += f"📆 Day: **{day_name}**\n"
    text += f"⏰ Time: **{data['schedule_start']}-{data['schedule_end']}**\n"
    text += f"🚪 Room: **{data['schedule_room']}**\n"
    if subject:
        text += f"📚 Subject: **{subject}**\n"
    text += "\nSave this schedule?"

    await state.update_data(schedule_subject=subject)

    await message.answer(text, reply_markup=get_confirm_keyboard("confirm_schedule", "cancel"))
    await state.set_state(ScheduleStates.confirm)

@router.callback_query(ScheduleStates.confirm, F.data == "confirm_schedule")
async def confirm_schedule(callback: CallbackQuery, state: FSMContext):
    """Save schedule"""
    data = await state.get_data()
    class_id = data['schedule_class_id']
    day = data['schedule_day']

    # Remove existing schedule for this day
    async with db.get_db() as conn:
        await conn.execute("""
            DELETE FROM schedules WHERE class_id = ? AND day_of_week = ?
        """, (class_id, day))

        # Insert new schedule
        await conn.execute("""
            INSERT INTO schedules (class_id, day_of_week, start_time, end_time, room, subject, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (class_id, day, data['schedule_start'], data['schedule_end'],
              data['schedule_room'], data.get('schedule_subject')))

        await conn.commit()

    # Log
    await db.log_audit(
        user_id=callback.from_user.id,
        action='set_schedule',
        entity_type='schedule',
        entity_id=class_id,
        new_values={'day': day, 'time': f"{data['schedule_start']}-{data['schedule_end']}"}
    )

    await callback.message.edit_text(
        "✅ Schedule saved!",
        reply_markup=get_back_keyboard(f"ca_manage_schedule_{class_id}")
    )
    await state.clear()

@router.callback_query(F.data.startswith("clear_schedule_"))
async def clear_all_schedule(callback: CallbackQuery, state: FSMContext):
    """Clear all schedule for a class"""
    class_id = int(callback.data.replace("clear_schedule_", ""))

    async with db.get_db() as conn:
        await conn.execute("DELETE FROM schedules WHERE class_id = ?", (class_id,))
        await conn.commit()

    await callback.answer("✅ All schedule cleared")
    await manage_schedule_start(callback, state)

# ========================
# ASSIGN TEACHER
# ========================

@router.callback_query(F.data == "ca_assign_teacher")
async def assign_teacher_menu(callback: CallbackQuery, state: FSMContext):
    """Show assign teacher menu - first select class"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    classes = await db.get_classes_for_center(center_id)

    if not classes:
        await callback.answer("No classes available", show_alert=True)
        return

    buttons = []
    for cls in classes:
        buttons.append([InlineKeyboardButton(
            text=f"{cls['name']} ({cls['level']})",
            callback_data=f"ca_assign_teacher_{cls['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")])

    await callback.message.edit_text(
        "Select class to assign teacher:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("ca_assign_teacher_"))
async def assign_teacher_select(callback: CallbackQuery, state: FSMContext):
    """Select teacher for the class"""
    class_id = int(callback.data.replace("ca_assign_teacher_", ""))
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    # Get teachers in this center
    teachers = await db.get_center_users(center_id, 'teacher')

    if not teachers:
        await callback.answer("No teachers in this center. Add teachers first.", show_alert=True)
        return

    await state.update_data(assign_class_id=class_id)

    buttons = []
    for teacher in teachers:
        buttons.append([InlineKeyboardButton(
            text=teacher['full_name'],
            callback_data=f"assign_teacher_to_{class_id}_{teacher['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_assign_teacher")])

    await callback.message.edit_text(
        "Select teacher to assign:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("assign_teacher_to_"))
async def assign_teacher_execute(callback: CallbackQuery, state: FSMContext):
    """Execute teacher assignment"""
    parts = callback.data.replace("assign_teacher_to_", "").split("_")
    class_id = int(parts[0])
    teacher_id = int(parts[1])

    success = await db.assign_teacher_to_class(teacher_id, class_id, is_primary=False, assigned_by=callback.from_user.id)

    if success:
        # Log
        await db.log_audit(
            user_id=callback.from_user.id,
            action='assign_teacher',
            entity_type='class',
            entity_id=class_id,
            new_values={'teacher_id': teacher_id}
        )

        await callback.answer("✅ Teacher assigned!")
    else:
        await callback.answer("❌ Teacher might already be assigned.", show_alert=True)

    await view_class_detail(callback, state)

# ========================
# VIEW CLASS ROSTER
# ========================

@router.callback_query(F.data.startswith("ca_view_roster_"))
async def view_class_roster(callback: CallbackQuery, state: FSMContext):
    """View full class roster"""
    class_id = int(callback.data.replace("ca_view_roster_", ""))

    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT c.* FROM classes c WHERE c.id = ?
        """, (class_id,))
        class_data = await cursor.fetchone()

        cursor = await conn.execute("""
            SELECT u.*, ce.enrolled_at
            FROM class_enrollments ce
            JOIN users u ON ce.student_id = u.id
            WHERE ce.class_id = ? AND ce.is_active = 1
            ORDER BY u.full_name
        """, (class_id,))
        students = [dict(row) for row in await cursor.fetchall()]

    if not class_data:
        await callback.answer("Class not found", show_alert=True)
        return

    class_data = dict(class_data)

    text = f"👥 **Class Roster: {class_data['name']}**\n\n"
    text += f"📊 Total Students: **{len(students)}**\n\n"

    if students:
        for i, student in enumerate(students, 1):
            phone = student.get('phone', 'N/A')
            text += f"{i}. **{student['full_name']}**\n"
            text += f"   📞 {phone} | Enrolled: {student['enrolled_at'][:10] if student.get('enrolled_at') else 'N/A'}\n"
            text += "─" * 30 + "\n"
    else:
        text += "No students enrolled yet.\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Enroll Student", callback_data=f"ca_add_student")],
        [InlineKeyboardButton(text="📥 Export Roster", callback_data=f"ca_export_roster_{class_id}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data=f"ca_class_detail_{class_id}")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

# ========================
# DELETE/ARCHIVE CLASS
# ========================

@router.callback_query(F.data.startswith("ca_toggle_archive_"))
async def toggle_class_archive(callback: CallbackQuery, state: FSMContext):
    """Toggle class archive status"""
    class_id = int(callback.data.replace("ca_toggle_archive_", ""))

    async with db.get_db() as conn:
        cursor = await conn.execute("SELECT is_archived FROM classes WHERE id = ?", (class_id,))
        row = await cursor.fetchone()
        new_status = 0 if row and row['is_archived'] else 1

        await conn.execute("""
            UPDATE classes SET is_archived = ?, archived_at = CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP ELSE NULL END
            WHERE id = ?
        """, (new_status, new_status, class_id))
        await conn.commit()

    action = "archived" if new_status else "unarchived"

    # Log
    await db.log_audit(
        user_id=callback.from_user.id,
        action=f'{action}_class',
        entity_type='class',
        entity_id=class_id
    )

    await callback.answer(f"✅ Class {action}")
    await view_class_detail(callback, state)

@router.callback_query(F.data.startswith("ca_delete_class_"))
async def delete_class_confirm(callback: CallbackQuery, state: FSMContext):
    """Confirm class deletion"""
    class_id = int(callback.data.replace("ca_delete_class_", ""))

    await state.update_data(delete_class_id=class_id)

    await callback.message.edit_text(
        "⚠️ **Delete Class?**\n\n"
        "This will permanently delete:\n"
        "• All class data\n"
        "• Student enrollments\n"
        "• Schedules\n"
        "• Associated units and quizzes\n\n"
        "Type 'DELETE' to confirm:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state("confirm_delete_class")

@router.message(F.text, state="confirm_delete_class")
async def delete_class_execute(message: Message, state: FSMContext):
    """Execute class deletion"""
    if message.text.strip().upper() != 'DELETE':
        await message.answer("❌ Deletion cancelled.")
        await state.clear()
        return

    data = await state.get_data()
    class_id = data['delete_class_id']

    await db.delete_class(class_id)

    # Log
    await db.log_audit(
        user_id=message.from_user.id,
        action='delete_class',
        entity_type='class',
        entity_id=class_id
    )

    await message.answer(
        "✅ Class deleted.",
        reply_markup=get_center_admin_main_menu()
    )
    await state.clear()
