# handlers/teacher/dashboard.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import database.queries as db
from keyboards.all_keyboards import (
    get_teacher_main_menu, get_back_keyboard
)
from datetime import datetime

router = Router()

async def get_teacher_context(state: FSMContext) -> dict:
    """Get teacher context from state"""
    data = await state.get_data()
    telegram_id = data.get('telegram_id', 0)

    if not telegram_id:
        return {'teacher': None, 'center_id': None, 'classes': []}

    teacher = await db.get_user_by_telegram_id(telegram_id)
    if not teacher:
        return {'teacher': None, 'center_id': None, 'classes': []}

    center_id = data.get('current_center_id')
    classes = await db.get_classes_for_teacher(teacher['id'])

    return {
        'teacher': teacher,
        'teacher_id': teacher['id'],
        'center_id': center_id,
        'classes': classes
    }

@router.message(F.text == "👤 Profile")
async def teacher_profile(message: Message, state: FSMContext):
    """Show teacher profile"""
    ctx = await get_teacher_context(state)
    teacher = ctx['teacher']

    if not teacher:
        await message.answer("❌ Teacher not found.")
        return

    classes = ctx.get('classes', [])

    text = "👨‍🏫 **Teacher Profile**\n\n"
    text += f"📛 **Name:** {teacher['full_name']}\n"
    text += f"📱 **Phone:** {teacher.get('phone', 'N/A')}\n"
    text += f"📧 **Email:** {teacher.get('email', 'N/A')}\n"
    text += f"📅 **Joined:** {teacher['created_at'][:10] if teacher.get('created_at') else 'N/A'}\n\n"

    text += f"🏫 **My Classes ({len(classes)}):**\n"
    for cls in classes[:10]:
        text += f"• {cls['name']} ({cls['level']}) - {cls.get('student_count', 0)} students\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Edit Name", callback_data="t_edit_name")],
        [InlineKeyboardButton(text="📞 Edit Phone", callback_data="t_edit_phone")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="t_back")]
    ])

    await message.answer(text, reply_markup=keyboard)

@router.message(F.text == "🏫 My Classes")
async def teacher_my_classes(message: Message, state: FSMContext):
    """Show teacher's classes"""
    ctx = await get_teacher_context(state)
    classes = ctx.get('classes', [])

    if not classes:
        await message.answer(
            "📋 You are not assigned to any classes yet.\n"
            "Contact your center admin."
        )
        return

    text = "🏫 **My Classes**\n\n"
    buttons = []

    for cls in classes:
        text += f"**{cls['name']}** ({cls['level']})\n"
        text += f"  👥 Students: {cls.get('student_count', 0)}\n"
        text += f"  {'⭐ Primary Teacher' if cls.get('is_primary') else '👨‍🏫 Co-Teacher'}\n\n"

        buttons.append([InlineKeyboardButton(
            text=f"📊 {cls['name']}",
            callback_data=f"t_class_detail_{cls['id']}"
        )])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data == "t_back")
async def back_to_teacher_main(callback: CallbackQuery, state: FSMContext):
    """Return to teacher main menu"""
    await callback.message.delete()
    await callback.message.answer(
        "👨‍🏫 Teacher Panel",
        reply_markup=get_teacher_main_menu()
    )
