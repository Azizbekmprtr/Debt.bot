# handlers/student/speaking.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import database.queries as db
from keyboards.all_keyboards import (
    get_student_main_menu, get_cancel_keyboard,
    get_confirm_keyboard, get_back_keyboard
)

router = Router()

class SpeakingStates(StatesGroup):
    finding_partner = State()
    in_session = State()
    submitting_topic = State()

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
        'classes': classes,
        'center_id': classes[0].get('center_id') if classes else None
    }

@router.message(F.text == "🗣 Speaking Partner")
async def speaking_menu(message: Message, state: FSMContext):
    """Show speaking partner menu"""
    ctx = await get_student_context(state)
    student = ctx.get('student')

    if not student:
        await message.answer("❌ Student not found.")
        return

    # Get speaking stats
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT COUNT(*) as session_count,
                   COALESCE(SUM(duration_minutes), 0) as total_minutes
            FROM speaking_sessions
            WHERE (student1_id = ? OR student2_id = ?) AND ended_at IS NOT NULL
        """, (student['id'], student['id']))
        stats = dict(await cursor.fetchone())

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Find Partner", callback_data="s_find_partner")],
        [InlineKeyboardButton(text="📋 View Topics", callback_data="s_view_topics")],
        [InlineKeyboardButton(text="➕ Add Topic", callback_data="s_add_topic")],
        [InlineKeyboardButton(text="📊 My History", callback_data="s_speaking_history")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="s_back")]
    ])

    text = "🗣 **Speaking Partner**\n\n"
    text += f"📊 **Your Stats:**\n"
    text += f"• Sessions: **{stats['session_count']}**\n"
    text += f"• Total Time: **{stats['total_minutes']}** minutes\n\n"
    text += "Practice speaking with other students!\n"
    text += "Select action:"

    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "s_find_partner")
async def find_speaking_partner(callback: CallbackQuery, state: FSMContext):
    """Find a random speaking partner"""
    ctx = await get_student_context(state)
    student_id = ctx['student_id']
    classes = ctx.get('classes', [])

    if not classes:
        await callback.answer("You need to be enrolled in a class first", show_alert=True)
        return

    level = classes[0].get('level', 'A1')

    await callback.message.edit_text(
        "🔍 **Finding Partner...**\n\n"
        f"Looking for a {level} level partner...",
    )

    # Find partner at same level
    partner = await db.find_speaking_partner(student_id, level)

    if not partner:
        # Try any level
        partner = await db.find_speaking_partner(student_id, None)

    if not partner:
        await callback.message.edit_text(
            "😔 **No Partner Available**\n\n"
            "No other students are available right now.\n"
            "Try again later!",
            reply_markup=get_back_keyboard("s_speaking_menu")
        )
        return

    # Get a random topic
    topic = await db.get_random_speaking_topic(ctx.get('center_id'), level)

    # Start session
    session_id = await db.start_speaking_session(
        student_id, partner['id'],
        topic['id'] if topic else None
    )

    await state.update_data(
        speaking_session_id=session_id,
        speaking_partner=partner,
        speaking_topic=topic
    )

    text = "🎉 **Partner Found!**\n\n"
    text += f"👤 **Partner:** {partner['full_name']}\n"
    text += f"📊 **Level:** {partner.get('class_level', level)}\n\n"

    if topic:
        text += f"📋 **Topic:**\n{topic['topic_text']}\n\n"

    text += "💡 **Tips:**\n"
    text += "• Take turns speaking\n"
    text += "• Ask follow-up questions\n"
    text += "• Be respectful and patient\n\n"
    text += "Session started! Send voice messages or text to practice."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 New Topic", callback_data="s_new_topic")],
        [InlineKeyboardButton(text="🏁 End Session", callback_data="s_end_session")],
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(SpeakingStates.in_session)

@router.callback_query(F.data == "s_new_topic")
async def get_new_topic(callback: CallbackQuery, state: FSMContext):
    """Get a new speaking topic"""
    ctx = await get_student_context(state)
    classes = ctx.get('classes', [])
    level = classes[0].get('level', 'A1') if classes else None

    topic = await db.get_random_speaking_topic(ctx.get('center_id'), level)

    if topic:
        await state.update_data(speaking_topic=topic)
        await callback.answer(f"📋 New topic: {topic['topic_text'][:50]}...", show_alert=True)
    else:
        await callback.answer("No more topics available", show_alert=True)

@router.callback_query(F.data == "s_end_session")
async def end_speaking_session(callback: CallbackQuery, state: FSMContext):
    """End the speaking session"""
    data = await state.get_data()
    session_id = data.get('speaking_session_id')

    if session_id:
        await db.end_speaking_session(session_id)

    # Award points
    ctx = await get_student_context(state)
    await db.award_points(ctx['student_id'], 10, "Completed speaking session")

    await callback.message.edit_text(
        "✅ **Session Ended**\n\n"
        "Great job practicing! 🎉\n"
        "+10 points for completing a session.\n\n"
        "Come back soon for more practice!",
        reply_markup=get_back_keyboard("s_speaking_menu")
    )
    await state.clear()

@router.callback_query(F.data == "s_view_topics")
async def view_speaking_topics(callback: CallbackQuery, state: FSMContext):
    """View available speaking topics"""
    ctx = await get_student_context(state)
    center_id = ctx.get('center_id')

    if not center_id:
        await callback.answer("No center context", show_alert=True)
        return

    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT * FROM speaking_topics
            WHERE center_id = ? AND is_active = 1
            ORDER BY level, category
            LIMIT 30
        """, (center_id,))
        topics = [dict(row) for row in await cursor.fetchall()]

    if not topics:
        await callback.message.edit_text(
            "📋 No topics available yet.\n"
            "You can add new topics!",
            reply_markup=get_back_keyboard("s_speaking_menu")
        )
        return

    text = "📋 **Speaking Topics**\n\n"

    current_level = None
    for topic in topics:
        if topic.get('level') != current_level:
            current_level = topic.get('level')
            text += f"\n**{current_level or 'General'} Level:**\n"

        text += f"• {topic['topic_text'][:80]}\n"
        if topic.get('category'):
            text += f"  [{topic['category']}]\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("s_speaking_menu")
    )

@router.callback_query(F.data == "s_add_topic")
async def add_topic_start(callback: CallbackQuery, state: FSMContext):
    """Start adding a new speaking topic"""
    await callback.message.edit_text(
        "➕ **Add Speaking Topic**\n\n"
        "Enter a conversation topic/prompt:\n"
        "Example: 'Describe your favorite holiday and why you like it'",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(SpeakingStates.submitting_topic)

@router.message(SpeakingStates.submitting_topic, F.text)
async def submit_topic(message: Message, state: FSMContext):
    """Submit a new speaking topic"""
    topic_text = message.text.strip()

    if len(topic_text) < 10:
        await message.answer("❌ Topic must be at least 10 characters.")
        return

    ctx = await get_student_context(state)
    center_id = ctx.get('center_id')

    if not center_id:
        await message.answer("❌ Unable to add topic.")
        await state.clear()
        return

    classes = ctx.get('classes', [])
    level = classes[0].get('level') if classes else None

    topic_id = await db.add_speaking_topic(
        center_id=center_id,
        topic_text=topic_text,
        level=level,
        created_by=ctx['student_id']
    )

    if topic_id:
        await db.award_points(ctx['student_id'], 2, "Added speaking topic")

        await message.answer(
            "✅ **Topic Added!**\n\n"
            "Thank you for contributing!\n"
            "+2 points for adding a topic.",
            reply_markup=get_student_main_menu()
        )
    else:
        await message.answer(
            "❌ Failed to add topic.",
            reply_markup=get_student_main_menu()
        )

    await state.clear()

@router.callback_query(F.data == "s_speaking_history")
async def speaking_history(callback: CallbackQuery, state: FSMContext):
    """View speaking session history"""
    ctx = await get_student_context(state)
    student_id = ctx['student_id']

    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT ss.*,
                   u1.full_name as partner_name,
                   st.topic_text
            FROM speaking_sessions ss
            JOIN users u1 ON (
                CASE WHEN ss.student1_id = ? THEN ss.student2_id ELSE ss.student1_id END = u1.id
            )
            LEFT JOIN speaking_topics st ON ss.topic_id = st.id
            WHERE (ss.student1_id = ? OR ss.student2_id = ?) AND ss.ended_at IS NOT NULL
            ORDER BY ss.ended_at DESC
            LIMIT 20
        """, (student_id, student_id, student_id))
        sessions = [dict(row) for row in await cursor.fetchall()]

    if not sessions:
        await callback.message.edit_text(
            "📊 No speaking sessions yet.\n"
            "Find a partner and start practicing!",
            reply_markup=get_back_keyboard("s_speaking_menu")
        )
        return

    text = "📊 **Speaking History**\n\n"

    for session in sessions:
        text += f"📅 {session['started_at'][:19] if session.get('started_at') else 'N/A'}\n"
        text += f"👤 Partner: {session.get('partner_name', 'Unknown')}\n"
        if session.get('duration_minutes'):
            text += f"⏱️ Duration: {session['duration_minutes']} min\n"
        if session.get('topic_text'):
            text += f"📋 Topic: {session['topic_text'][:60]}\n"
        text += "\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("s_speaking_menu")
    )

@router.callback_query(F.data == "s_speaking_menu")
async def back_to_speaking_menu(callback: CallbackQuery, state: FSMContext):
    """Back to speaking menu"""
    await speaking_menu(callback.message, state)
