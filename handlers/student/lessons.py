# handlers/student/lessons.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import database.queries as db
from keyboards.all_keyboards import (
    get_student_main_menu, get_student_lessons_menu,
    get_back_keyboard
)

router = Router()

async def get_student_context(state: FSMContext) -> dict:
    """Get student context"""
    data = await state.get_data()
    telegram_id = data.get('telegram_id', 0)
    student = await db.get_user_by_telegram_id(telegram_id) if telegram_id else None
    if not student:
        return {'student': None, 'classes': []}
    classes = await db.get_classes_for_student(student['id'])
    return {'student': student, 'student_id': student['id'], 'classes': classes}

@router.message(F.text == "📚 My Lessons")
async def my_lessons_menu(message: Message, state: FSMContext):
    """Show student's lessons"""
    ctx = await get_student_context(state)
    student = ctx.get('student')

    if not student:
        await message.answer("❌ Student not found.")
        return

    classes = ctx.get('classes', [])

    if not classes:
        await message.answer(
            "📚 You are not enrolled in any classes yet.",
            reply_markup=get_student_main_menu()
        )
        return

    text = "📚 **My Lessons**\n\n"
    buttons = []

    for cls in classes:
        text += f"🏫 **{cls['name']}** ({cls['level']})\n"

        # Get current unit
        current_unit = await db.get_current_unit_for_class(cls['id'])
        if current_unit:
            text += f"  📌 Current: {current_unit['title']}\n"

        # Get unit count
        units = await db.get_units_for_class(cls['id'])
        text += f"  📊 Units: {len(units)}\n\n"

        buttons.append([InlineKeyboardButton(
            text=f"📖 {cls['name']} - View Units",
            callback_data=f"s_class_units_{cls['id']}"
        )])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("s_class_units_"))
async def view_class_units(callback: CallbackQuery, state: FSMContext):
    """View units for a class"""
    class_id = int(callback.data.replace("s_class_units_", ""))
    units = await db.get_units_for_class(class_id)

    if not units:
        await callback.message.edit_text(
            "📚 No units available yet.",
            reply_markup=get_back_keyboard("s_back")
        )
        return

    text = "📚 **Units**\n\n"
    buttons = []

    for unit in units:
        current = " 📌 CURRENT" if unit.get('is_current') else ""
        text += f"**Unit {unit['unit_number']}: {unit['title']}**{current}\n"

        if unit.get('description'):
            text += f"  {unit['description'][:100]}\n"

        # Materials indicators
        materials = []
        if unit.get('video_url'):
            materials.append("🎥 Video")
        if unit.get('audio_url'):
            materials.append("🎧 Audio")
        if unit.get('pdf_url'):
            materials.append("📎 PDF")

        if materials:
            text += f"  {' | '.join(materials)}\n"

        text += "\n"

        buttons.append([InlineKeyboardButton(
            text=f"📖 Unit {unit['unit_number']}: {unit['title'][:30]}",
            callback_data=f"s_unit_detail_{unit['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="s_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("s_unit_detail_"))
async def view_unit_detail(callback: CallbackQuery, state: FSMContext):
    """View unit details with materials"""
    unit_id = int(callback.data.replace("s_unit_detail_", ""))
    unit = await db.get_unit_by_id(unit_id)

    if not unit:
        await callback.answer("Unit not found", show_alert=True)
        return

    text = f"📖 **{unit['title']}**\n\n"

    if unit.get('description'):
        text += f"📄 {unit['description']}\n\n"

    if unit.get('video_url'):
        text += f"🎥 **Video Lesson:**\n{unit['video_url']}\n\n"

    if unit.get('audio_url'):
        text += f"🎧 **Audio Lesson:**\n{unit['audio_url']}\n\n"

    if unit.get('pdf_url'):
        text += f"📎 **Download PDF:**\n{unit['pdf_url']}\n\n"

    # Get quizzes for this unit
    quizzzes = await db.get_quizzes_for_unit(unit_id)

    if quizzes:
        text += "📝 **Available Quizzes:**\n"
        for quiz in quizzes:
            text += f"• {quiz['title']}\n"

    buttons = []
    for quiz in quizzes:
        buttons.append([InlineKeyboardButton(
            text=f"▶️ Take: {quiz['title']}",
            callback_data=f"s_start_quiz_{quiz['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="s_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data == "s_back")
async def back_to_student_main(callback: CallbackQuery, state: FSMContext):
    """Return to student main menu"""
    await callback.message.delete()
    await callback.message.answer(
        "🎓 Student Panel",
        reply_markup=get_student_main_menu()
    )
