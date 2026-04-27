# handlers/parent/dashboard.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import database.queries as db
from keyboards.all_keyboards import (
    get_parent_main_menu, get_parent_children_keyboard,
    get_parent_child_menu, get_back_keyboard
)

router = Router()

async def get_parent_context(state: FSMContext) -> dict:
    """Get parent context"""
    data = await state.get_data()
    telegram_id = data.get('telegram_id', 0)
    parent = await db.get_user_by_telegram_id(telegram_id) if telegram_id else None
    if not parent:
        return {'parent': None, 'parent_id': None, 'children': []}

    children = await db.get_children_for_parent(parent['id'])
    return {
        'parent': parent,
        'parent_id': parent['id'],
        'children': children
    }

@router.message(F.text == "👶 My Children")
async def parent_dashboard(message: Message, state: FSMContext):
    """Show parent dashboard with children overview"""
    ctx = await get_parent_context(state)
    parent = ctx.get('parent')
    children = ctx.get('children', [])

    if not parent:
        await message.answer("❌ Parent account not found.")
        return

    if not children:
        await message.answer(
            "👶 No children linked to your account yet.\n"
            "Contact the center admin to link your child.",
            reply_markup=get_parent_main_menu()
        )
        return

    text = "👪 **Parent Dashboard**\n\n"
    text += f"👋 Welcome, **{parent['full_name']}**!\n\n"
    text += f"👶 **Your Children ({len(children)}):**\n\n"

    for child in children:
        # Get child's stats
        classes = await db.get_classes_for_student(child['id'])
        class_info = classes[0] if classes else None
        points = await db.get_student_points_and_streak(child['id'])
        badges = await db.get_student_badges(child['id'])
        attendance = await db.get_student_attendance_stats(child['id'])

        text += f"### **{child['full_name']}**\n"
        if class_info:
            text += f"🏫 Class: {class_info['name']} ({class_info['level']})\n"
        text += f"⭐ Points: {points['total_points']}\n"
        text += f"🔥 Streak: {points['current_streak']} days\n"
        text += f"🏅 Badges: {len(badges)}\n"

        if attendance:
            total_sessions = attendance.get('total_sessions', 0)
            present = attendance.get('present_count', 0)
            rate = (present / total_sessions * 100) if total_sessions > 0 else 0
            text += f"📅 Attendance: {rate:.1f}%\n"

        text += "\n"

    await message.answer(text, reply_markup=get_parent_children_keyboard(children))

@router.callback_query(F.data.startswith("parent_child_"))
async def view_child_detail(callback: CallbackQuery, state: FSMContext):
    """View detailed child information"""
    child_id = int(callback.data.replace("parent_child_", ""))
    child = await db.get_user_by_id(child_id)

    if not child:
        await callback.answer("Child not found", show_alert=True)
        return

    await state.update_data(viewing_child_id=child_id)

    # Get comprehensive child data
    classes = await db.get_classes_for_student(child_id)
    class_info = classes[0] if classes else None
    points = await db.get_student_points_and_streak(child_id)
    badges = await db.get_student_badges(child_id)
    attendance = await db.get_student_attendance_stats(child_id)
    quiz_results = await db.get_student_quiz_results(child_id, 5)
    homework = await db.get_homework_for_student(child_id)

    text = f"👶 **{child['full_name']}**\n\n"

    if class_info:
        text += f"🏫 **Class:** {class_info['name']} ({class_info['level']})\n"

    text += f"⭐ **Points:** {points['total_points']}\n"
    text += f"🔥 **Streak:** {points['current_streak']} days (Best: {points['longest_streak']})\n"
    text += f"🏅 **Badges:** {len(badges)}\n\n"

    if quiz_results:
        text += "📝 **Recent Quiz Results:**\n"
        for qr in quiz_results[:3]:
            text += f"  • {qr['quiz_title']}: {qr['score']}/{qr['max_score']} "
            text += f"({'✅' if qr.get('passed') else '❌'})\n"
        text += "\n"

    if attendance:
        total = attendance.get('total_sessions', 0)
        present = attendance.get('present_count', 0)
        rate = (present / total * 100) if total > 0 else 0
        text += f"📅 **Attendance:** {rate:.1f}% ({present}/{total})\n\n"

    if homework:
        pending = [h for h in homework if not h.get('submission_id')]
        text += f"📋 **Homework:** {len(pending)} pending\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_parent_child_menu(child_id)
    )

@router.callback_query(F.data == "p_back")
async def back_to_parent_main(callback: CallbackQuery, state: FSMContext):
    """Return to parent main menu"""
    await callback.message.delete()
    await callback.message.answer(
        "👪 Parent Panel",
        reply_markup=get_parent_main_menu()
    )

@router.callback_query(F.data.startswith("p_child_progress_"))
async def view_child_progress(callback: CallbackQuery, state: FSMContext):
    """View child's detailed progress"""
    child_id = int(callback.data.replace("p_child_progress_", ""))

    # Get units with progress
    units = await db.get_units_for_student(child_id)
    quiz_results = await db.get_student_quiz_results(child_id, 20)

    text = "📊 **Progress Report**\n\n"

    if units:
        text += "📚 **Units:**\n"
        for unit in units[:10]:
            progress = unit.get('completion_percent', 0)
            bar = "▓" * int(progress / 10) + "░" * (10 - int(progress / 10))
            text += f"  Unit {unit['unit_number']}: [{bar}] {progress}%\n"
        text += "\n"

    if quiz_results:
        text += "📝 **Quiz History:**\n"
        for qr in quiz_results[:10]:
            passed = "✅" if qr.get('passed') else "❌"
            text += f"  {passed} {qr['quiz_title']}: {qr['score']}/{qr['max_score']}\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(f"parent_child_{child_id}")
    )

@router.callback_query(F.data.startswith("p_child_quizzes_"))
async def view_child_quizzes(callback: CallbackQuery, state: FSMContext):
    """View child's quiz results"""
    child_id = int(callback.data.replace("p_child_quizzes_", ""))
    quiz_results = await db.get_student_quiz_results(child_id, 30)

    text = f"📝 **Quiz Results**\n\n"

    if not quiz_results:
        text += "No quizzes taken yet.\n"
    else:
        for qr in quiz_results:
            passed = "✅" if qr.get('passed') else "❌"
            percent = (qr['score'] / qr['max_score'] * 100) if qr['max_score'] > 0 else 0
            text += f"{passed} **{qr['quiz_title']}**\n"
            text += f"  Score: {qr['score']}/{qr['max_score']} ({percent:.1f}%)\n"
            text += f"  Date: {qr.get('completed_at', 'N/A')[:10]}\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(f"parent_child_{child_id}")
    )

@router.callback_query(F.data.startswith("p_child_attendance_"))
async def view_child_attendance(callback: CallbackQuery, state: FSMContext):
    """View child's attendance"""
    child_id = int(callback.data.replace("p_child_attendance_", ""))
    attendance = await db.get_student_attendance_stats(child_id)
    history = await db.get_student_attendance_history(child_id, 30)

    text = "📅 **Attendance Report**\n\n"

    if attendance:
        total = attendance.get('total_sessions', 0)
        present = attendance.get('present_count', 0)
        late = attendance.get('late_count', 0)
        absent = attendance.get('absent_count', 0)
        excused = attendance.get('excused_count', 0)
        rate = (present / total * 100) if total > 0 else 0

        text += f"📊 **Overall:** {rate:.1f}%\n"
        text += f"✅ Present: {present}\n"
        text += f"⏰ Late: {late}\n"
        text += f"❌ Absent: {absent}\n"
        text += f"📝 Excused: {excused}\n\n"

    if history:
        text += "**Recent Attendance:**\n"
        for record in history[:10]:
            status_emoji = {'present': '✅', 'late': '⏰', 'absent': '❌', 'excused': '📝'}
            emoji = status_emoji.get(record.get('status', ''), '❓')
            text += f"  {emoji} {record.get('session_date', 'N/A')}: {record['status'].title()}\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(f"parent_child_{child_id}")
    )

@router.callback_query(F.data.startswith("p_child_payments_"))
async def view_child_payments(callback: CallbackQuery, state: FSMContext):
    """View child's payment history"""
    child_id = int(callback.data.replace("p_child_payments_", ""))
    payments = await db.get_student_payment_history(child_id, 20)
    balance = await db.get_student_balance(child_id)

    text = f"💰 **Payment History**\n\n"
    text += f"💳 **Current Balance:** {balance:,.0f} UZS\n\n"

    if payments:
        for payment in payments:
            text += f"📅 {payment['payment_date'][:10] if payment.get('payment_date') else 'N/A'}\n"
            text += f"  💰 Amount: {payment['amount']:,.0f} UZS\n"
            if payment.get('notes'):
                text += f"  📝 {payment['notes']}\n"
            if payment.get('recorded_by_name'):
                text += f"  👤 Recorded by: {payment['recorded_by_name']}\n"
            text += "\n"
    else:
        text += "No payment records found.\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(f"parent_child_{child_id}")
    )

@router.callback_query(F.data.startswith("p_contact_teacher_"))
async def contact_teacher(callback: CallbackQuery, state: FSMContext):
    """Contact child's teacher"""
    child_id = int(callback.data.replace("p_contact_teacher_", ""))
    child = await db.get_user_by_id(child_id)

    if not child:
        await callback.answer("Child not found", show_alert=True)
        return

    # Get child's class and teachers
    classes = await db.get_classes_for_student(child_id)

    if not classes:
        await callback.answer("Child not enrolled in any class", show_alert=True)
        return

    text = f"💬 **Contact Teacher for {child['full_name']}**\n\n"
    text += "Select teacher to message:\n"

    buttons = []
    for cls in classes:
        teachers = await db.get_teachers_for_class(cls['id'])
        for teacher in teachers:
            buttons.append([InlineKeyboardButton(
                text=f"👨‍🏫 {teacher['full_name']} ({cls['name']})",
                callback_data=f"p_msg_teacher_{teacher['id']}_{child_id}"
            )])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data=f"parent_child_{child_id}")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data == "p_child_homework_")
async def view_child_homework(callback: CallbackQuery, state: FSMContext):
    """View child's homework status"""
    child_id = int(callback.data.replace("p_child_homework_", ""))
    homework = await db.get_homework_for_student(child_id)

    text = "📋 **Homework Status**\n\n"

    if not homework:
        text += "No homework assigned.\n"
    else:
        pending = [h for h in homework if not h.get('submission_id')]
        submitted = [h for h in homework if h.get('submission_id')]

        if pending:
            text += f"⏳ **Pending ({len(pending)}):**\n"
            for hw in pending:
                deadline = hw['deadline'][:10] if isinstance(hw['deadline'], str) else str(hw['deadline'])[:10]
                text += f"  • {hw['title']} - Due: {deadline}\n"
            text += "\n"

        if submitted:
            text += f"✅ **Submitted ({len(submitted)}):**\n"
            for hw in submitted:
                if hw.get('is_graded'):
                    text += f"  • {hw['title']} - Score: {hw['score']}/{hw['max_score']}\n"
                    if hw.get('feedback'):
                        text += f"    💬 {hw['feedback']}\n"
                else:
                    text += f"  • {hw['title']} - Awaiting grade\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard(f"parent_child_{child_id}")
    )
