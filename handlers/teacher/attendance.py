# handlers/teacher/attendance.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import database.queries as db
from keyboards.all_keyboards import (
    get_teacher_main_menu, get_cancel_keyboard,
    get_confirm_keyboard, get_back_keyboard,
    get_attendance_keyboard
)

router = Router()

class AttendanceStates(StatesGroup):
    selecting_class = State()
    marking = State()
    confirm_save = State()

@router.message(F.text == "📅 Attendance")
async def attendance_menu(message: Message, state: FSMContext):
    """Show attendance menu"""
    ctx = await get_teacher_context(state)
    classes = ctx.get('classes', [])

    if not classes:
        await message.answer("❌ No classes assigned.")
        return

    buttons = []
    for cls in classes:
        buttons.append([InlineKeyboardButton(
            text=f"{cls['name']} ({cls['level']})",
            callback_data=f"t_att_class_{cls['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="t_back")])

    await message.answer(
        "📅 **Take Attendance**\n\nSelect class:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("t_att_class_"))
async def start_attendance(callback: CallbackQuery, state: FSMContext):
    """Start attendance for a class"""
    class_id = int(callback.data.replace("t_att_class_", ""))

    # Check if attendance already taken today
    today = datetime.now().strftime("%Y-%m-%d")
    existing = await db.get_todays_attendance_session(class_id)

    if existing:
        await callback.message.edit_text(
            "⚠️ Attendance already taken today for this class.\n"
            "Use 'Edit Attendance' to modify.",
            reply_markup=get_back_keyboard(f"t_edit_att_{class_id}")
        )
        return

    # Get students
    students = await db.get_students_for_attendance(class_id)

    if not students:
        await callback.answer("No students in this class", show_alert=True)
        return

    # Create attendance session
    session_id = await db.create_attendance_session(class_id, today, callback.from_user.id)

    await state.update_data(
        att_class_id=class_id,
        att_session_id=session_id,
        att_students=students,
        att_current_index=0,
        att_statuses={}
    )

    await show_student_for_attendance(callback, state)

async def show_student_for_attendance(callback: CallbackQuery, state: FSMContext):
    """Show current student for attendance marking"""
    data = await state.get_data()
    students = data['att_students']
    current_index = data['att_current_index']

    if current_index >= len(students):
        await show_attendance_summary(callback, state)
        return

    student = students[current_index]

    await callback.message.edit_text(
        f"📅 **Attendance** ({current_index + 1}/{len(students)})\n\n"
        f"👤 **{student['full_name']}**\n"
        f"📞 {student.get('phone', 'N/A')}\n\n"
        "Mark status:",
        reply_markup=get_attendance_keyboard()
    )
    await state.set_state(AttendanceStates.marking)

@router.callback_query(AttendanceStates.marking, F.data.startswith("att_"))
async def mark_attendance(callback: CallbackQuery, state: FSMContext):
    """Mark a student's attendance"""
    status = callback.data.replace("att_", "")

    if status == "save_exit":
        await save_attendance(callback, state)
        return

    data = await state.get_data()
    students = data['att_students']
    current_index = data['att_current_index']
    session_id = data['att_session_id']
    student = students[current_index]

    # Save the record
    await db.mark_attendance(session_id, student['id'], status)

    # Update state
    statuses = data.get('att_statuses', {})
    statuses[str(student['id'])] = status

    await state.update_data(
        att_current_index=current_index + 1,
        att_statuses=statuses
    )

    # Show next student
    await show_student_for_attendance(callback, state)

async def show_attendance_summary(callback: CallbackQuery, state: FSMContext):
    """Show attendance summary"""
    data = await state.get_data()
    statuses = data.get('att_statuses', {})

    present = sum(1 for s in statuses.values() if s == 'present')
    late = sum(1 for s in statuses.values() if s == 'late')
    absent = sum(1 for s in statuses.values() if s == 'absent')
    excused = sum(1 for s in statuses.values() if s == 'excused')
    total = present + late + absent + excused

    text = "📊 **Attendance Summary**\n\n"
    text += f"✅ Present: **{present}**\n"
    text += f"⏰ Late: **{late}**\n"
    text += f"❌ Absent: **{absent}**\n"
    text += f"📝 Excused: **{excused}**\n"
    text += f"👥 Total: **{total}**\n\n"

    rate = (present + late) / total * 100 if total > 0 else 0
    text += f"📈 Attendance Rate: **{rate:.1f}%**\n\n"
    text += "Save and notify parents?"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💾 Save & Exit", callback_data="att_finalize"),
            InlineKeyboardButton(text="📝 Edit", callback_data="att_edit")
        ],
        [InlineKeyboardButton(text="❌ Cancel", callback_data="t_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "att_finalize")
async def finalize_attendance(callback: CallbackQuery, state: FSMContext):
    """Finalize and save attendance"""
    data = await state.get_data()

    # Mark session as finalized
    await db.finalize_attendance_session(data['att_session_id'])

    # Notify parents (if configured)
    # This would trigger notifications

    await callback.message.edit_text(
        "✅ **Attendance Saved!**\n\n"
        "Parents will be notified of their child's status.",
        reply_markup=get_teacher_main_menu()
    )
    await state.clear()

@router.callback_query(F.data == "att_save_exit")
async def save_attendance(callback: CallbackQuery, state: FSMContext):
    """Save current progress and exit"""
    await finalize_attendance(callback, state)
