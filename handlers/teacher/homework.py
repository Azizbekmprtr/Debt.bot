# handlers/teacher/homework.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import database.queries as db
from keyboards.all_keyboards import (
    get_teacher_main_menu, get_cancel_keyboard,
    get_confirm_keyboard, get_back_keyboard
)

router = Router()

class AssignHomeworkStates(StatesGroup):
    selecting_class = State()
    entering_title = State()
    entering_description = State()
    selecting_deadline = State()
    entering_max_score = State()
    confirm = State()

class GradeHomeworkStates(StatesGroup):
    selecting_submission = State()
    entering_score = State()
    entering_feedback = State()
    confirm = State()

async def get_teacher_context(state: FSMContext) -> dict:
    data = await state.get_data()
    telegram_id = data.get('telegram_id', 0)
    teacher = await db.get_user_by_telegram_id(telegram_id) if telegram_id else None
    if not teacher:
        return {'teacher': None, 'classes': []}
    classes = await db.get_classes_for_teacher(teacher['id'])
    return {'teacher': teacher, 'teacher_id': teacher['id'], 'classes': classes}

# ========================
# HOMEWORK MAIN MENU
# ========================

@router.message(F.text == "📋 Homework")
async def homework_menu(message: Message, state: FSMContext):
    """Show homework management menu"""
    ctx = await get_teacher_context(state)
    classes = ctx.get('classes', [])

    if not classes:
        await message.answer("❌ No classes assigned.")
        return

    # Get pending submissions count
    pending_count = 0
    for cls in classes:
        submissions = await db.get_pending_submissions_for_class(cls['id'])
        pending_count += len(submissions)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Assign Homework", callback_data="t_assign_homework")],
        [InlineKeyboardButton(text="📋 View Assigned", callback_data="t_view_homework")],
        [InlineKeyboardButton(text=f"📝 Grade Submissions ({pending_count})", callback_data="t_grade_homework")],
        [InlineKeyboardButton(text="📊 View Graded", callback_data="t_view_graded")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="t_back")]
    ])

    text = "📋 **Homework Management**\n\n"
    text += f"📝 Pending to grade: **{pending_count}**\n\n"
    text += "Select action:"

    await message.answer(text, reply_markup=keyboard)

# ========================
# ASSIGN HOMEWORK
# ========================

@router.callback_query(F.data == "t_assign_homework")
async def assign_homework_start(callback: CallbackQuery, state: FSMContext):
    """Start assigning homework"""
    ctx = await get_teacher_context(state)
    classes = ctx.get('classes', [])

    if not classes:
        await callback.answer("No classes assigned", show_alert=True)
        return

    buttons = []
    for cls in classes:
        buttons.append([InlineKeyboardButton(
            text=f"{cls['name']} ({cls['level']}) - {cls.get('student_count', 0)} students",
            callback_data=f"hw_class_{cls['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="t_back")])

    await callback.message.edit_text(
        "📋 **Assign Homework**\n\nSelect class:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(AssignHomeworkStates.selecting_class)

@router.callback_query(AssignHomeworkStates.selecting_class, F.data.startswith("hw_class_"))
async def process_hw_class(callback: CallbackQuery, state: FSMContext):
    """Process class selection"""
    class_id = int(callback.data.replace("hw_class_", ""))
    await state.update_data(hw_class_id=class_id)

    await callback.message.edit_text(
        "Enter homework title:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AssignHomeworkStates.entering_title)

@router.message(AssignHomeworkStates.entering_title, F.text)
async def process_hw_title(message: Message, state: FSMContext):
    """Process homework title"""
    title = message.text.strip()
    if len(title) < 3 or len(title) > 200:
        await message.answer("❌ Title must be between 3 and 200 characters.")
        return

    await state.update_data(hw_title=title)

    await message.answer(
        f"✅ Title: **{title}**\n\n"
        "Enter description/instructions (type 'skip' to skip):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AssignHomeworkStates.entering_description)

@router.message(AssignHomeworkStates.entering_description, F.text)
async def process_hw_description(message: Message, state: FSMContext):
    """Process homework description"""
    desc = message.text.strip()
    if desc.lower() == 'skip':
        desc = None

    await state.update_data(hw_description=desc)

    # Deadline suggestions
    today = datetime.now()
    suggestions = [
        today + timedelta(days=1),
        today + timedelta(days=3),
        today + timedelta(days=7),
        today + timedelta(days=14)
    ]

    buttons = []
    for s in suggestions:
        buttons.append([InlineKeyboardButton(
            text=f"📅 {s.strftime('%A, %d %B %Y')}",
            callback_data=f"hw_deadline_{s.strftime('%Y-%m-%d')}"
        )])
    buttons.append([InlineKeyboardButton(text="✏️ Custom Date", callback_data="hw_deadline_custom")])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="cancel")])

    await message.answer(
        "📅 **Select Deadline:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(AssignHomeworkStates.selecting_deadline)

@router.callback_query(AssignHomeworkStates.selecting_deadline, F.data.startswith("hw_deadline_"))
async def process_hw_deadline(callback: CallbackQuery, state: FSMContext):
    """Process deadline selection"""
    deadline_str = callback.data.replace("hw_deadline_", "")

    if deadline_str == "custom":
        await callback.message.edit_text(
            "Enter deadline in format YYYY-MM-DD:\n"
            "Example: 2024-12-31",
            reply_markup=get_cancel_keyboard()
        )
        return

    try:
        deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
    except ValueError:
        await callback.answer("Invalid date format", show_alert=True)
        return

    await state.update_data(hw_deadline=deadline_str)

    await callback.message.edit_text(
        f"✅ Deadline: **{deadline.strftime('%d %B %Y')}**\n\n"
        "Enter maximum score (default: 100):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AssignHomeworkStates.entering_max_score)

@router.message(AssignHomeworkStates.entering_max_score, F.text)
async def process_hw_max_score(message: Message, state: FSMContext):
    """Process max score and confirm"""
    try:
        max_score = int(message.text.strip())
        if max_score < 1 or max_score > 1000:
            raise ValueError
    except ValueError:
        await message.answer("❌ Enter a number between 1 and 1000:")
        return

    data = await state.get_data()

    text = "📋 **Confirm Homework Assignment**\n\n"
    text += f"📌 **Title:** {data['hw_title']}\n"
    if data.get('hw_description'):
        text += f"📄 **Description:** {data['hw_description'][:100]}...\n"
    text += f"📅 **Deadline:** {data['hw_deadline']}\n"
    text += f"⭐ **Max Score:** {max_score}\n"
    text += f"👥 **Class:** Will be assigned to all students\n\n"
    text += "Assign this homework?"

    await state.update_data(hw_max_score=max_score)

    await message.answer(text, reply_markup=get_confirm_keyboard("confirm_assign_hw", "cancel"))
    await state.set_state(AssignHomeworkStates.confirm)

@router.callback_query(AssignHomeworkStates.confirm, F.data == "confirm_assign_hw")
async def confirm_assign_homework(callback: CallbackQuery, state: FSMContext):
    """Finalize homework assignment"""
    data = await state.get_data()

    homework_id = await db.assign_homework(
        class_id=data['hw_class_id'],
        title=data['hw_title'],
        description=data.get('hw_description'),
        deadline=data['hw_deadline'],
        max_score=data['hw_max_score'],
        created_by=callback.from_user.id
    )

    if homework_id:
        await db.log_audit(
            user_id=callback.from_user.id,
            action='assign_homework',
            entity_type='homework',
            entity_id=homework_id,
            new_values={'title': data['hw_title'], 'class_id': data['hw_class_id']}
        )

        await callback.message.edit_text(
            f"✅ **Homework Assigned!**\n\n"
            f"📌 {data['hw_title']}\n"
            f"📅 Due: {data['hw_deadline']}\n"
            f"⭐ Max: {data['hw_max_score']} points\n\n"
            "Students will be notified.",
            reply_markup=get_back_keyboard("t_view_homework")
        )
    else:
        await callback.message.edit_text(
            "❌ Failed to assign homework.",
            reply_markup=get_back_keyboard("t_back")
        )

    await state.clear()

# ========================
# VIEW ASSIGNED HOMEWORK
# ========================

@router.callback_query(F.data == "t_view_homework")
async def view_assigned_homework(callback: CallbackQuery, state: FSMContext):
    """View all assigned homework"""
    ctx = await get_teacher_context(state)
    teacher = ctx.get('teacher')

    if not teacher:
        await callback.answer("Teacher not found", show_alert=True)
        return

    # Get all homework for teacher's classes
    all_homework = []
    for cls in ctx.get('classes', []):
        hw_list = await db.get_homework_for_class(cls['id'])
        for hw in hw_list:
            hw['class_name'] = cls['name']
            all_homework.append(hw)

    if not all_homework:
        await callback.message.edit_text(
            "📋 No homework assigned yet.",
            reply_markup=get_back_keyboard("t_back")
        )
        return

    text = "📋 **Assigned Homework**\n\n"
    buttons = []

    for hw in all_homework[:20]:
        deadline = hw['deadline'][:10] if isinstance(hw['deadline'], str) else str(hw['deadline'])[:10]
        status = "🟢 Active" if datetime.fromisoformat(deadline) > datetime.now() else "🔴 Overdue"

        text += f"**{hw['title']}** ({hw['class_name']})\n"
        text += f"  📅 Due: {deadline} | ⭐ {hw['max_score']} pts\n"
        text += f"  Status: {status}\n\n"

        buttons.append([InlineKeyboardButton(
            text=f"📊 View Submissions: {hw['title'][:30]}",
            callback_data=f"t_hw_submissions_{hw['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="t_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("t_hw_submissions_"))
async def view_homework_submissions(callback: CallbackQuery, state: FSMContext):
    """View submissions for a specific homework"""
    homework_id = int(callback.data.replace("t_hw_submissions_", ""))

    submissions = await db.get_submissions_by_homework(homework_id)
    homework = await db.get_homework_by_id(homework_id)

    if not homework:
        await callback.answer("Homework not found", show_alert=True)
        return

    text = f"📥 **Submissions: {homework['title']}**\n\n"
    text += f"📅 Due: {homework['deadline'][:10]}\n"
    text += f"📊 Total submissions: **{len(submissions)}**\n\n"

    buttons = []

    pending = [s for s in submissions if not s.get('is_graded')]
    graded = [s for s in submissions if s.get('is_graded')]

    if pending:
        text += f"⏳ **Pending ({len(pending)}):**\n"
        for sub in pending[:10]:
            text += f"  • {sub['student_name']} - Submitted: {sub['submitted_at'][:19] if sub.get('submitted_at') else 'N/A'}\n"
            buttons.append([InlineKeyboardButton(
                text=f"📝 Grade: {sub['student_name']}",
                callback_data=f"t_grade_sub_{sub['id']}"
            )])

    if graded:
        text += f"\n✅ **Graded ({len(graded)}):**\n"
        for sub in graded[:5]:
            text += f"  • {sub['student_name']} - Score: {sub.get('score', 0)}/{homework['max_score']}\n"

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="t_view_homework")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ========================
# GRADE HOMEWORK
# ========================

@router.callback_query(F.data == "t_grade_homework")
async def grade_homework_start(callback: CallbackQuery, state: FSMContext):
    """Start grading homework"""
    ctx = await get_teacher_context(state)

    # Get all pending submissions for teacher's classes
    pending_submissions = []
    for cls in ctx.get('classes', []):
        subs = await db.get_pending_submissions_for_class(cls['id'])
        for sub in subs:
            sub['class_name'] = cls['name']
            pending_submissions.append(sub)

    if not pending_submissions:
        await callback.message.edit_text(
            "✅ No pending submissions to grade!",
            reply_markup=get_back_keyboard("t_back")
        )
        return

    text = "📝 **Pending Submissions**\n\n"
    buttons = []

    for sub in pending_submissions[:20]:
        text += f"• **{sub['student_name']}** - {sub['homework_title']}\n"
        text += f"  Class: {sub['class_name']}\n"
        text += f"  Submitted: {sub['submitted_at'][:19] if sub.get('submitted_at') else 'N/A'}\n\n"

        buttons.append([InlineKeyboardButton(
            text=f"📝 Grade: {sub['student_name']} - {sub['homework_title'][:20]}",
            callback_data=f"t_grade_sub_{sub['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="t_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("t_grade_sub_"))
async def grade_submission_start(callback: CallbackQuery, state: FSMContext):
    """Start grading a submission"""
    submission_id = int(callback.data.replace("t_grade_sub_", ""))

    # Get submission details
    submission = await db.get_submission_by_id(submission_id)

    if not submission:
        await callback.answer("Submission not found", show_alert=True)
        return

    await state.update_data(grade_submission_id=submission_id, grade_submission=submission)

    text = f"📝 **Grade Submission**\n\n"
    text += f"👤 **Student:** {submission['student_name']}\n"
    text += f"📋 **Homework:** {submission.get('homework_title', 'N/A')}\n"
    text += f"📅 **Submitted:** {submission['submitted_at'][:19] if submission.get('submitted_at') else 'N/A'}\n"

    if submission.get('file_type'):
        text += f"📎 **File Type:** {submission['file_type']}\n"
    if submission.get('text_content'):
        text += f"📄 **Content:** {submission['text_content'][:200]}...\n"

    text += f"\n⭐ Max Score: {submission.get('max_score', 100)}\n"
    text += "Enter score:"

    await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
    await state.set_state(GradeHomeworkStates.entering_score)

@router.message(GradeHomeworkStates.entering_score, F.text)
async def process_grade_score(message: Message, state: FSMContext):
    """Process grade score"""
    try:
        score = int(message.text.strip())
        data = await state.get_data()
        max_score = data['grade_submission'].get('max_score', 100)
        if score < 0 or score > max_score:
            raise ValueError
    except ValueError:
        await message.answer(f"❌ Enter a number between 0 and the max score:")
        return

    await state.update_data(grade_score=score)

    await message.answer(
        f"✅ Score: **{score}**\n\n"
        "Enter feedback/comment (type 'skip' to skip):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(GradeHomeworkStates.entering_feedback)

@router.message(GradeHomeworkStates.entering_feedback, F.text)
async def process_grade_feedback(message: Message, state: FSMContext):
    """Process feedback and confirm"""
    feedback = message.text.strip()
    if feedback.lower() == 'skip':
        feedback = None

    data = await state.get_data()

    text = "📝 **Confirm Grade**\n\n"
    text += f"👤 Student: {data['grade_submission']['student_name']}\n"
    text += f"⭐ Score: **{data['grade_score']}**\n"
    if feedback:
        text += f"💬 Feedback: {feedback}\n"
    text += "\nSubmit grade?"

    await state.update_data(grade_feedback=feedback)

    await message.answer(text, reply_markup=get_confirm_keyboard("confirm_grade", "cancel"))
    await state.set_state(GradeHomeworkStates.confirm)

@router.callback_query(GradeHomeworkStates.confirm, F.data == "confirm_grade")
async def confirm_grade(callback: CallbackQuery, state: FSMContext):
    """Submit grade"""
    data = await state.get_data()

    success = await db.grade_homework(
        submission_id=data['grade_submission_id'],
        score=data['grade_score'],
        feedback=data.get('grade_feedback'),
        graded_by=callback.from_user.id
    )

    if success:
        # Award points to student
        student_id = data['grade_submission']['student_id']
        points = int(data['grade_score'] / 10)  # 10% of score as points
        if data['grade_score'] >= data['grade_submission'].get('max_score', 100) * 0.9:
            points += 10  # Bonus for excellent work

        await db.award_points(student_id, points, "Homework graded")

        await callback.message.edit_text(
            f"✅ **Grade Submitted!**\n\n"
            f"⭐ Score: {data['grade_score']}\n"
            f"💬 Feedback: {data.get('grade_feedback', 'None')}\n\n"
            "Student has been notified.",
            reply_markup=get_back_keyboard("t_grade_homework")
        )
    else:
        await callback.message.edit_text(
            "❌ Failed to submit grade.",
            reply_markup=get_back_keyboard("t_back")
        )

    await state.clear()
