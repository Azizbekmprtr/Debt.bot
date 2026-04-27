# handlers/student/profile.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database.queries as db
from keyboards.all_keyboards import (
    get_student_main_menu, get_cancel_keyboard,
    get_back_keyboard
)

router = Router()

class EditProfileStates(StatesGroup):
    entering_value = State()

async def get_student_context(state: FSMContext) -> dict:
    data = await state.get_data()
    telegram_id = data.get('telegram_id', 0)
    student = await db.get_user_by_telegram_id(telegram_id) if telegram_id else None
    if not student:
        return {'student': None, 'student_id': None}
    classes = await db.get_classes_for_student(student['id'])
    return {
        'student': student,
        'student_id': student['id'],
        'classes': classes
    }

@router.message(F.text == "👤 Profile")
async def student_profile(message: Message, state: FSMContext):
    """Show student profile"""
    ctx = await get_student_context(state)
    student = ctx.get('student')

    if not student:
        await message.answer("❌ Student not found.")
        return

    classes = ctx.get('classes', [])
    points = await db.get_student_points_and_streak(student['id'])
    badges = await db.get_student_badges(student['id'])
    attendance_stats = await db.get_student_attendance_stats(student['id'])

    text = f"👤 **My Profile**\n\n"
    text += f"📛 **Name:** {student['full_name']}\n"
    text += f"📱 **Phone:** {student.get('phone', 'N/A')}\n"
    text += f"📧 **Email:** {student.get('email', 'N/A')}\n\n"

    text += "📊 **Statistics:**\n"
    text += f"⭐ **Points:** {points['total_points']}\n"
    text += f"🔥 **Streak:** {points['current_streak']} days (Best: {points['longest_streak']})\n"
    text += f"🏅 **Badges:** {len(badges)}\n"

    if attendance_stats:
        total = attendance_stats.get('total_sessions', 0)
        present = attendance_stats.get('present_count', 0)
        rate = (present / total * 100) if total > 0 else 0
        text += f"📅 **Attendance:** {rate:.1f}%\n"

    text += "\n"

    if classes:
        text += "🏫 **My Classes:**\n"
        for cls in classes:
            text += f"  • {cls['name']} ({cls['level']})\n"
    else:
        text += "🏫 **Not enrolled in any class**\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit Name", callback_data="sp_edit_name")],
        [InlineKeyboardButton(text="📞 Edit Phone", callback_data="sp_edit_phone")],
        [InlineKeyboardButton(text="📅 My Schedule", callback_data="sp_schedule")],
        [InlineKeyboardButton(text="📊 My Progress", callback_data="sp_progress")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="s_back")]
    ])

    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "sp_edit_name")
async def edit_name_start(callback: CallbackQuery, state: FSMContext):
    """Start editing name"""
    await callback.message.edit_text(
        "✏️ Enter your new full name:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(EditProfileStates.entering_value)
    await state.update_data(edit_field='full_name')

@router.callback_query(F.data == "sp_edit_phone")
async def edit_phone_start(callback: CallbackQuery, state: FSMContext):
    """Start editing phone"""
    await callback.message.edit_text(
        "📞 Enter your new phone number:\n"
        "Example: +998901234567",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(EditProfileStates.entering_value)
    await state.update_data(edit_field='phone')

@router.message(EditProfileStates.entering_value, F.text)
async def process_edit_value(message: Message, state: FSMContext):
    """Process edited value"""
    ctx = await get_student_context(state)
    student_id = ctx['student_id']
    data = await state.get_data()
    field = data.get('edit_field')
    new_value = message.text.strip()

    if field == 'full_name' and len(new_value) < 2:
        await message.answer("❌ Name must be at least 2 characters.")
        return

    if field == 'phone':
        from utils.helpers import validate_phone
        is_valid, phone = validate_phone(new_value)
        if not is_valid:
            await message.answer("❌ Invalid phone format. Use +998XXXXXXXXX")
            return
        new_value = phone

    await db.update_user_field(student_id, field, new_value)

    await message.answer(
        "✅ Profile updated!",
        reply_markup=get_student_main_menu()
    )
    await state.clear()

@router.callback_query(F.data == "sp_schedule")
async def view_schedule(callback: CallbackQuery, state: FSMContext):
    """View class schedule"""
    ctx = await get_student_context(state)
    classes = ctx.get('classes', [])

    if not classes:
        await callback.answer("Not enrolled in any class", show_alert=True)
        return

    text = "📅 **My Schedule**\n\n"
    day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    for cls in classes:
        text += f"🏫 **{cls['name']}** ({cls['level']})\n"

        schedules = await db.get_schedules_for_class(cls['id'])
        if schedules:
            for sched in schedules:
                day = day_names[sched['day_of_week']]
                text += f"  📅 {day}: {sched['start_time']}-{sched['end_time']}"
                if sched.get('room'):
                    text += f" | Room: {sched['room']}"
                text += "\n"
        else:
            text += "  No schedule set\n"
        text += "\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("sp_profile")
    )

@router.callback_query(F.data == "sp_progress")
async def view_progress(callback: CallbackQuery, state: FSMContext):
    """View learning progress"""
    ctx = await get_student_context(state)
    student_id = ctx['student_id']

    units = await db.get_units_for_student(student_id)
    quiz_results = await db.get_student_quiz_results(student_id, 50)
    points_history = await db.get_student_points_history(student_id, 30)

    text = "📊 **My Progress**\n\n"

    if units:
        text += "📚 **Unit Completion:**\n"
        for unit in units[:15]:
            progress = unit.get('completion_percent', 0)
            bar = "▓" * int(progress / 10) + "░" * (10 - int(progress / 10))
            text += f"  Unit {unit['unit_number']}: [{bar}] {progress}%\n"
        text += "\n"

    if quiz_results:
        total_quizzes = len(quiz_results)
        passed = sum(1 for q in quiz_results if q.get('passed'))
        pass_rate = (passed / total_quizzes * 100) if total_quizzes > 0 else 0

        text += f"📝 **Quiz Performance:**\n"
        text += f"  Total: {total_quizzes} | Passed: {passed}\n"
        text += f"  Pass Rate: {pass_rate:.1f}%\n\n"

    if points_history:
        text += "⭐ **Recent Points:**\n"
        for entry in points_history[:10]:
            text += f"  {entry['created_at'][:10] if entry.get('created_at') else 'N/A'}: +{entry.get('points', 0)}\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("sp_profile")
    )

@router.callback_query(F.data == "sp_profile")
async def back_to_profile(callback: CallbackQuery, state: FSMContext):
    """Back to profile"""
    await student_profile(callback.message, state)
