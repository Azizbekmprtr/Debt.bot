# handlers/student/communication.py
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

class CommunicationStates(StatesGroup):
    asking_teacher = State()
    rating_quiz = State()
    sending_feedback = State()

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

@router.message(F.text == "💬 Messages")
async def messages_menu(message: Message, state: FSMContext):
    """Show communication menu"""
    ctx = await get_student_context(state)
    student = ctx.get('student')

    if not student:
        await message.answer("❌ Student not found.")
        return

    # Get unread message count
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT COUNT(*) FROM messages
            WHERE receiver_id = ? AND is_read = 0
        """, (student['id'],))
        unread = (await cursor.fetchone())[0]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍🏫 Ask Teacher", callback_data="s_ask_teacher")],
        [InlineKeyboardButton(text=f"📨 Messages ({unread} unread)", callback_data="s_view_messages")],
        [InlineKeyboardButton(text="⭐ Rate Quiz", callback_data="s_rate_quiz")],
        [InlineKeyboardButton(text="📝 Send Feedback", callback_data="s_send_feedback")],
        [InlineKeyboardButton(text="📢 Announcements", callback_data="s_announcements")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="s_back")]
    ])

    text = "💬 **Communication**\n\n"
    text += f"📨 Unread: **{unread}**\n\n"
    text += "Select action:"

    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "s_ask_teacher")
async def ask_teacher_start(callback: CallbackQuery, state: FSMContext):
    """Start asking teacher a question"""
    ctx = await get_student_context(state)
    classes = ctx.get('classes', [])

    if not classes:
        await callback.answer("Not enrolled in any class", show_alert=True)
        return

    # Get teachers for student's classes
    teachers = []
    for cls in classes:
        class_teachers = await db.get_teachers_for_class(cls['id'])
        for t in class_teachers:
            if t['id'] not in [x['id'] for x in teachers]:
                teachers.append(t)

    if not teachers:
        await callback.message.edit_text(
            "No teachers assigned to your classes.",
            reply_markup=get_back_keyboard("s_back")
        )
        return

    buttons = []
    for teacher in teachers:
        buttons.append([InlineKeyboardButton(
            text=f"👨‍🏫 {teacher['full_name']}",
            callback_data=f"s_msg_teacher_{teacher['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="s_back")])

    await callback.message.edit_text(
        "👨‍🏫 **Ask Teacher**\n\nSelect teacher to message:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("s_msg_teacher_"))
async def message_teacher(callback: CallbackQuery, state: FSMContext):
    """Compose message to teacher"""
    teacher_id = int(callback.data.replace("s_msg_teacher_", ""))
    await state.update_data(msg_receiver_id=teacher_id)

    await callback.message.edit_text(
        "💬 **Compose Message**\n\n"
        "Type your question below:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CommunicationStates.asking_teacher)

@router.message(CommunicationStates.asking_teacher, F.text)
async def send_teacher_message(message: Message, state: FSMContext):
    """Send message to teacher"""
    ctx = await get_student_context(state)
    student_id = ctx['student_id']
    data = await state.get_data()
    teacher_id = data['msg_receiver_id']

    msg_id = await db.send_message(
        sender_id=student_id,
        receiver_id=teacher_id,
        content=message.text.strip()
    )

    if msg_id:
        await message.answer(
            "✅ **Message Sent!**\n\n"
            "Your teacher will respond soon.",
            reply_markup=get_student_main_menu()
        )
    else:
        await message.answer(
            "❌ Failed to send message.",
            reply_markup=get_student_main_menu()
        )

    await state.clear()

@router.callback_query(F.data == "s_view_messages")
async def view_messages(callback: CallbackQuery, state: FSMContext):
    """View recent messages"""
    ctx = await get_student_context(state)
    student_id = ctx['student_id']

    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT m.*, u.full_name as sender_name, u2.full_name as receiver_name
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            JOIN users u2 ON m.receiver_id = u2.id
            WHERE m.sender_id = ? OR m.receiver_id = ?
            ORDER BY m.created_at DESC
            LIMIT 30
        """, (student_id, student_id))
        messages = [dict(row) for row in await cursor.fetchall()]

    if not messages:
        await callback.message.edit_text(
            "📨 No messages yet.",
            reply_markup=get_back_keyboard("s_back")
        )
        return

    text = "📨 **Messages**\n\n"

    for msg in messages:
        is_sent = msg['sender_id'] == student_id
        direction = "📤 To:" if is_sent else "📥 From:"
        other_person = msg['receiver_name'] if is_sent else msg['sender_name']
        read_status = "" if is_sent else (" ✅" if msg['is_read'] else " 🔵")

        text += f"{direction} **{other_person}**{read_status}\n"
        text += f"  {msg['content'][:100]}\n"
        text += f"  {msg['created_at'][:19] if msg.get('created_at') else 'N/A'}\n\n"

    # Mark messages as read
    await db.mark_messages_read(student_id)

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("s_back")
    )

@router.callback_query(F.data == "s_rate_quiz")
async def rate_quiz_start(callback: CallbackQuery, state: FSMContext):
    """Start rating a quiz"""
    ctx = await get_student_context(state)
    student_id = ctx['student_id']

    # Get recently completed quizzes
    results = await db.get_student_quiz_results(student_id, 5)

    if not results:
        await callback.message.edit_text(
            "⭐ No quizzes to rate yet.\nComplete a quiz first!",
            reply_markup=get_back_keyboard("s_back")
        )
        return

    buttons = []
    for result in results:
        buttons.append([InlineKeyboardButton(
            text=f"⭐ {result['quiz_title'][:40]}",
            callback_data=f"s_rate_quiz_{result['quiz_id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="s_back")])

    await callback.message.edit_text(
        "⭐ **Rate a Quiz**\n\nSelect quiz to rate:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("s_rate_quiz_"))
async def rate_quiz(callback: CallbackQuery, state: FSMContext):
    """Show rating options"""
    quiz_id = int(callback.data.replace("s_rate_quiz_", ""))
    await state.update_data(rate_quiz_id=quiz_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ 1", callback_data="quiz_rating_1"),
         InlineKeyboardButton(text="⭐ 2", callback_data="quiz_rating_2"),
         InlineKeyboardButton(text="⭐ 3", callback_data="quiz_rating_3"),
         InlineKeyboardButton(text="⭐ 4", callback_data="quiz_rating_4"),
         InlineKeyboardButton(text="⭐ 5", callback_data="quiz_rating_5")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="s_rate_quiz")]
    ])

    await callback.message.edit_text(
        "⭐ **Rate the Quiz**\n\nHow would you rate this quiz?",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("quiz_rating_"))
async def submit_quiz_rating(callback: CallbackQuery, state: FSMContext):
    """Submit quiz rating"""
    rating = int(callback.data.replace("quiz_rating_", ""))
    data = await state.get_data()
    quiz_id = data.get('rate_quiz_id')
    ctx = await get_student_context(state)

    await db.submit_feedback(
        student_id=ctx['student_id'],
        quiz_id=quiz_id,
        rating=rating
    )

    await callback.message.edit_text(
        f"✅ **Rating Submitted!**\n\n"
        f"⭐ {rating}/5 stars\n\n"
        "Thank you for your feedback!",
        reply_markup=get_back_keyboard("s_back")
    )

@router.callback_query(F.data == "s_send_feedback")
async def send_feedback_start(callback: CallbackQuery, state: FSMContext):
    """Start sending feedback"""
    await callback.message.edit_text(
        "📝 **Send Feedback**\n\n"
        "Share your thoughts, suggestions, or report issues:\n"
        "Type your feedback below:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CommunicationStates.sending_feedback)

@router.message(CommunicationStates.sending_feedback, F.text)
async def submit_feedback(message: Message, state: FSMContext):
    """Submit feedback"""
    ctx = await get_student_context(state)
    student_id = ctx['student_id']

    await db.submit_feedback(
        student_id=student_id,
        comment=message.text.strip()
    )

    await message.answer(
        "✅ **Feedback Submitted!**\n\n"
        "Thank you for helping us improve!",
        reply_markup=get_student_main_menu()
    )
    await state.clear()

@router.callback_query(F.data == "s_announcements")
async def view_announcements(callback: CallbackQuery, state: FSMContext):
    """View announcements for student"""
    ctx = await get_student_context(state)
    classes = ctx.get('classes', [])

    if not classes:
        await callback.answer("Not enrolled in any class", show_alert=True)
        return

    # Get announcements for student's center and classes
    announcements = []
    for cls in classes:
        class_announcements = await db.get_announcements_for_class(cls['id'])
        announcements.extend(class_announcements)

    if not announcements:
        await callback.message.edit_text(
            "📢 No announcements yet.",
            reply_markup=get_back_keyboard("s_back")
        )
        return

    text = "📢 **Announcements**\n\n"

    for ann in announcements[:10]:
        text += f"📌 **{ann['title']}**\n"
        text += f"  {ann['content'][:200]}\n"
        text += f"  📅 {ann['created_at'][:10] if ann.get('created_at') else 'N/A'}\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("s_back")
    )
