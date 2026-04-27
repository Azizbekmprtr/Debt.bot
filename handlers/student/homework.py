# handlers/student/homework.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import database.queries as db
from keyboards.all_keyboards import (
    get_student_main_menu, get_cancel_keyboard,
    get_back_keyboard
)

router = Router()

class SubmitHomeworkStates(StatesGroup):
    selecting_homework = State()
    uploading_file = State()
    entering_text = State()
    confirm = State()

async def get_student_context(state: FSMContext) -> dict:
    data = await state.get_data()
    telegram_id = data.get('telegram_id', 0)
    student = await db.get_user_by_telegram_id(telegram_id) if telegram_id else None
    return {'student': student, 'student_id': student['id'] if student else None}

@router.message(F.text == "📋 Homework")
async def student_homework(message: Message, state: FSMContext):
    """Show student's homework"""
    ctx = await get_student_context(state)
    student_id = ctx.get('student_id')

    if not student_id:
        await message.answer("❌ Student not found.")
        return

    homework_list = await db.get_homework_for_student(student_id)

    if not homework_list:
        await message.answer(
            "📋 No homework assigned yet.",
            reply_markup=get_student_main_menu()
        )
        return

    # Separate pending and submitted
    pending = [h for h in homework_list if not h.get('submission_id')]
    submitted = [h for h in homework_list if h.get('submission_id')]

    text = "📋 **My Homework**\n\n"

    if pending:
        text += "⏳ **Pending:**\n"
        for hw in pending:
            deadline = hw['deadline'][:10] if isinstance(hw['deadline'], str) else str(hw['deadline'])[:10]
            days_left = (datetime.fromisoformat(deadline) - datetime.now()).days
            urgency = "🔴" if days_left < 0 else "🟡" if days_left <= 2 else "🟢"
            text += f"{urgency} **{hw['title']}** ({hw['class_name']})\n"
            text += f"  📅 Due: {deadline} ({days_left} days)\n"
            text += f"  ⭐ Max: {hw['max_score']} pts\n\n"

    if submitted:
        text += "✅ **Submitted:**\n"
        for hw in submitted:
            text += f"✅ **{hw['title']}** ({hw['class_name']})\n"
            if hw.get('is_graded'):
                text += f"  📊 Grade: **{hw['score']}/{hw['max_score']}**\n"
                if hw.get('feedback'):
                    text += f"  💬 {hw['feedback']}\n"
            else:
                text += f"  ⏳ Awaiting grade\n"
            text += "\n"

    buttons = []
    for hw in pending:
        buttons.append([InlineKeyboardButton(
            text=f"📤 Submit: {hw['title'][:35]}",
            callback_data=f"s_submit_hw_{hw['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="s_back")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("s_submit_hw_"))
async def submit_homework_start(callback: CallbackQuery, state: FSMContext):
    """Start submitting homework"""
    homework_id = int(callback.data.replace("s_submit_hw_", ""))
    homework = await db.get_homework_by_id(homework_id)

    if not homework:
        await callback.answer("Homework not found", show_alert=True)
        return

    await state.update_data(submit_hw_id=homework_id, submit_hw=homework)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📎 Upload File", callback_data="hw_upload_file")],
        [InlineKeyboardButton(text="📝 Type Answer", callback_data="hw_type_text")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="s_back")]
    ])

    await callback.message.edit_text(
        f"📤 **Submit Homework**\n\n"
        f"📌 {homework['title']}\n"
        f"📅 Due: {homework['deadline'][:10]}\n"
        f"⭐ Max: {homework['max_score']} pts\n\n"
        "How would you like to submit?",
        reply_markup=keyboard
    )
    await state.set_state(SubmitHomeworkStates.selecting_homework)

@router.callback_query(SubmitHomeworkStates.selecting_homework, F.data == "hw_upload_file")
async def upload_file_start(callback: CallbackQuery, state: FSMContext):
    """Start file upload"""
    await callback.message.edit_text(
        "📎 **Upload Your Homework**\n\n"
        "Send your file (PDF, image, document, etc.):\n"
        "Max size: 20MB",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(SubmitHomeworkStates.uploading_file)

@router.message(SubmitHomeworkStates.uploading_file, F.document | F.photo)
async def receive_file_submission(message: Message, state: FSMContext):
    """Receive and process file submission"""
    ctx = await get_student_context(state)
    student_id = ctx['student_id']
    data = await state.get_data()
    homework_id = data['submit_hw_id']

    file_id = None
    file_name = None
    file_type = None

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        file_type = 'document'
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_name = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        file_type = 'photo'

    submission_id = await db.submit_homework(
        homework_id=homework_id,
        student_id=student_id,
        file_id=file_id,
        file_name=file_name,
        file_type=file_type
    )

    if submission_id:
        # Award points for early submission
        await db.award_points(student_id, 5, "Submitted homework")

        await message.answer(
            "✅ **Homework Submitted!**\n\n"
            "Your teacher will grade it soon.\n"
            "You'll be notified when it's graded.",
            reply_markup=get_student_main_menu()
        )
    else:
        await message.answer(
            "❌ Failed to submit. You may have already submitted this homework.",
            reply_markup=get_student_main_menu()
        )

    await state.clear()

@router.callback_query(SubmitHomeworkStates.selecting_homework, F.data == "hw_type_text")
async def type_answer_start(callback: CallbackQuery, state: FSMContext):
    """Start typing answer"""
    await callback.message.edit_text(
        "📝 **Type Your Answer**\n\n"
        "Write your answer below:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(SubmitHomeworkStates.entering_text)

@router.message(SubmitHomeworkStates.entering_text, F.text)
async def receive_text_submission(message: Message, state: FSMContext):
    """Receive text submission"""
    ctx = await get_student_context(state)
    student_id = ctx['student_id']
    data = await state.get_data()
    homework_id = data['submit_hw_id']

    submission_id = await db.submit_homework(
        homework_id=homework_id,
        student_id=student_id,
        text_content=message.text.strip()
    )

    if submission_id:
        await db.award_points(student_id, 3, "Submitted homework")

        await message.answer(
            "✅ **Homework Submitted!**",
            reply_markup=get_student_main_menu()
        )
    else:
        await message.answer(
            "❌ Failed to submit.",
            reply_markup=get_student_main_menu()
        )

    await state.clear()
