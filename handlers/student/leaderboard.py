# handlers/student/leaderboard.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import database.queries as db
from keyboards.all_keyboards import (
    get_student_main_menu, get_back_keyboard
)

router = Router()

async def get_student_context(state: FSMContext) -> dict:
    data = await state.get_data()
    telegram_id = data.get('telegram_id', 0)
    student = await db.get_user_by_telegram_id(telegram_id) if telegram_id else None
    if not student:
        return {'student': None, 'student_id': None}

    # Get center_id from student's class
    classes = await db.get_classes_for_student(student['id'])
    center_id = None
    if classes:
        center_id = classes[0].get('center_id')

    return {
        'student': student,
        'student_id': student['id'],
        'center_id': center_id,
        'classes': classes
    }

@router.message(F.text == "🏆 Leaderboard")
async def leaderboard_menu(message: Message, state: FSMContext):
    """Show leaderboard"""
    ctx = await get_student_context(state)
    center_id = ctx.get('center_id')
    student_id = ctx.get('student_id')

    if not center_id:
        await message.answer("❌ No leaderboard available.")
        return

    # Get student's rank
    ranks = await db.get_student_rank(student_id, center_id)

    text = "🏆 **Leaderboard**\n\n"
    text += "📊 **Your Rankings:**\n"
    text += f"🌍 Global: **#{ranks.get('global_rank', 'N/A')}**\n"
    text += f"🏫 Class: **#{ranks.get('class_rank', 'N/A')}**\n"
    text += f"📈 Level: **#{ranks.get('level_rank', 'N/A')}**\n\n"
    text += "Select leaderboard to view:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Global Leaderboard", callback_data="s_lb_global")],
        [InlineKeyboardButton(text="🏫 Class Leaderboard", callback_data="s_lb_class")],
        [InlineKeyboardButton(text="📈 Level Leaderboard", callback_data="s_lb_level")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="s_back")]
    ])

    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "s_lb_global")
async def show_global_leaderboard(callback: CallbackQuery, state: FSMContext):
    """Show global leaderboard"""
    ctx = await get_student_context(state)
    center_id = ctx.get('center_id')
    student_id = ctx.get('student_id')

    leaderboard = await db.get_leaderboard(center_id, 'global', limit=20)

    text = "🌍 **Global Leaderboard**\n\n"
    await format_leaderboard(text, leaderboard, student_id, callback.message)
    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("s_lb_menu")
    )

@router.callback_query(F.data == "s_lb_class")
async def show_class_leaderboard(callback: CallbackQuery, state: FSMContext):
    """Show class leaderboard"""
    ctx = await get_student_context(state)
    center_id = ctx.get('center_id')
    student_id = ctx.get('student_id')
    classes = ctx.get('classes', [])

    if not classes:
        await callback.answer("No class found", show_alert=True)
        return

    class_id = classes[0]['id']
    leaderboard = await db.get_leaderboard(center_id, 'class', class_id=class_id, limit=20)

    text = "🏫 **Class Leaderboard**\n\n"
    await format_leaderboard(text, leaderboard, student_id, callback.message)
    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("s_lb_menu")
    )

async def format_leaderboard(text: str, leaderboard: list, student_id: int, message):
    """Format leaderboard entries"""
    if not leaderboard:
        text += "No entries yet.\n"
        return

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}

    for entry in leaderboard:
        rank = entry.get('rank', '?')
        medal = medals.get(rank, f"#{rank}")

        is_me = entry['student_id'] == student_id
        highlight = "➡️ " if is_me else ""

        text += f"{highlight}{medal} **{entry['full_name']}**\n"
        text += f"      ⭐ {entry.get('total_points', 0)} pts | 🔥 {entry.get('current_streak', 0)} day streak\n"
        text += "\n"

@router.callback_query(F.data == "s_lb_menu")
async def back_to_leaderboard_menu(callback: CallbackQuery, state: FSMContext):
    """Back to leaderboard menu"""
    await leaderboard_menu(callback.message, state)
