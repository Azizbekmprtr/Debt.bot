# handlers/student/achievements.py
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
    return {'student': student, 'student_id': student['id'] if student else None}

@router.message(F.text == "🎖 Achievements")
async def achievements_menu(message: Message, state: FSMContext):
    """Show student's achievements"""
    ctx = await get_student_context(state)
    student_id = ctx.get('student_id')
    student = ctx.get('student')

    if not student_id:
        await message.answer("❌ Student not found.")
        return

    badges = await db.get_student_badges(student_id)
    certificates = await db.get_student_certificates(student_id)
    points_streak = await db.get_student_points_and_streak(student_id)

    text = "🎖 **My Achievements**\n\n"
    text += f"⭐ **Total Points:** {points_streak['total_points']}\n"
    text += f"🔥 **Current Streak:** {points_streak['current_streak']} days\n"
    text += f"⚡ **Longest Streak:** {points_streak['longest_streak']} days\n\n"

    if badges:
        text += f"🏅 **Badges ({len(badges)}):**\n"
        for badge in badges[:10]:
            text += f"  {badge.get('icon', '🏅')} **{badge['name']}**"
            if badge.get('earned_at'):
                text += f" - {badge['earned_at'][:10]}"
            text += "\n"
            if badge.get('description'):
                text += f"     {badge['description']}\n"
        text += "\n"

    if certificates:
        text += f"📜 **Certificates ({len(certificates)}):**\n"
        for cert in certificates[:5]:
            text += f"  📜 **{cert['title']}**"
            if cert.get('level'):
                text += f" ({cert['level']})"
            text += f" - {cert['issued_at'][:10] if cert.get('issued_at') else 'N/A'}\n"
        text += "\n"

    if not badges and not certificates:
        text += "Complete quizzes and maintain streaks to earn badges and certificates!\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏅 View All Badges", callback_data="s_all_badges")],
        [InlineKeyboardButton(text="📜 View All Certificates", callback_data="s_all_certs")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="s_back")]
    ])

    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "s_all_badges")
async def view_all_badges(callback: CallbackQuery, state: FSMContext):
    """View all badges (earned and available)"""
    ctx = await get_student_context(state)
    student_id = ctx.get('student_id')

    earned_badges = await db.get_student_badges(student_id)
    all_badges = await db.get_all_badges()

    earned_ids = [b['badge_id'] for b in earned_badges]

    text = "🏅 **All Badges**\n\n"

    for badge in all_badges:
        earned = badge['id'] in earned_ids
        status = "✅" if earned else "🔒"
        text += f"{status} {badge.get('icon', '🏅')} **{badge['name']}**"
        if earned:
            for eb in earned_badges:
                if eb['badge_id'] == badge['id']:
                    text += f" - Earned: {eb['earned_at'][:10]}"
                    break
        text += "\n"
        if badge.get('description'):
            text += f"   {badge['description']}\n"
        text += f"   Reward: +{badge.get('points_awarded', 0)} pts\n\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("s_achievements")
    )

@router.callback_query(F.data == "s_achievements")
async def back_to_achievements(callback: CallbackQuery, state: FSMContext):
    """Back to achievements menu"""
    await achievements_menu(callback.message, state)
