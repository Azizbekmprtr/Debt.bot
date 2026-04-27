# handlers/parent/attendance.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from datetime import datetime
import database.queries as db
from keyboards.all_keyboards import (
    get_parent_main_menu, get_parent_children_keyboard,
    get_back_keyboard
)
import os
from config import EXPORTS_DIR
import csv

router = Router()

async def get_parent_context(state: FSMContext) -> dict:
    data = await state.get_data()
    telegram_id = data.get('telegram_id', 0)
    parent = await db.get_user_by_telegram_id(telegram_id) if telegram_id else None
    if not parent:
        return {'parent': None, 'parent_id': None, 'children': []}
    children = await db.get_children_for_parent(parent['id'])
    return {'parent': parent, 'parent_id': parent['id'], 'children': children}

@router.message(F.text == "📅 Attendance")
async def attendance_menu(message: Message, state: FSMContext):
    """Show attendance tracking menu"""
    ctx = await get_parent_context(state)
    children = ctx.get('children', [])

    if not children:
        await message.answer(
            "👶 No children linked to your account.",
            reply_markup=get_parent_main_menu()
        )
        return

    # Quick summary for all children
    text = "📅 **Attendance Tracking**\n\n"

    for child in children:
        stats = await db.get_student_attendance_stats(child['id'])
        total = stats.get('total_sessions', 0)
        present = stats.get('present_count', 0)
        rate = (present / total * 100) if total > 0 else 0

        text += f"👶 **{child['full_name']}**\n"
        text += f"  📊 Rate: {rate:.1f}% ({present}/{total})\n\n"

    text += "Select child for detailed view:"

    await message.answer(text, reply_markup=get_parent_children_keyboard(children))

@router.callback_query(F.data.startswith("parent_child_"))
async def view_child_attendance_detail(callback: CallbackQuery, state: FSMContext):
    """View detailed attendance for a child"""
    child_id = int(callback.data.replace("parent_child_", ""))
    child = await db.get_user_by_id(child_id)

    if not child:
        await callback.answer("Child not found", show_alert=True)
        return

    stats = await db.get_student_attendance_stats(child_id)
    history = await db.get_student_attendance_history(child_id, 50)

    total = stats.get('total_sessions', 0)
    present = stats.get('present_count', 0)
    late = stats.get('late_count', 0)
    absent = stats.get('absent_count', 0)
    excused = stats.get('excused_count', 0)
    rate = (present / total * 100) if total > 0 else 0

    text = f"📅 **Attendance: {child['full_name']}**\n\n"
    text += "══════════════════════════════\n\n"

    text += "📊 **Overall Statistics:**\n"
    text += f"  • Total Sessions: **{total}**\n"
    text += f"  • Attendance Rate: **{rate:.1f}%**\n\n"

    # Visual bar
    bar_filled = int(rate / 10)
    bar = "▓" * bar_filled + "░" * (10 - bar_filled)
    text += f"  [{bar}] {rate:.1f}%\n\n"

    text += "📋 **Breakdown:**\n"
    text += f"  ✅ Present: **{present}** ({present/total*100:.1f}%)\n" if total > 0 else f"  ✅ Present: **0**\n"
    text += f"  ⏰ Late: **{late}**\n"
    text += f"  ❌ Absent: **{absent}**\n"
    text += f"  📝 Excused: **{excused}**\n\n"

    if history:
        text += "📅 **Recent Attendance:**\n"
        status_emoji = {'present': '✅', 'late': '⏰', 'absent': '❌', 'excused': '📝'}

        for record in history[:15]:
            emoji = status_emoji.get(record.get('status', ''), '❓')
            date = record.get('session_date', '')
            text += f"  {emoji} {date}: {record.get('status', '').title()}"
            if record.get('class_name'):
                text += f" - {record['class_name']}"
            text += "\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Export Attendance", callback_data=f"pa_export_attendance_{child_id}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="pa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("pa_export_attendance_"))
async def export_child_attendance(callback: CallbackQuery, state: FSMContext):
    """Export child's attendance to CSV"""
    child_id = int(callback.data.replace("pa_export_attendance_", ""))
    child = await db.get_user_by_id(child_id)

    if not child:
        await callback.answer("Child not found", show_alert=True)
        return

    history = await db.get_student_attendance_history(child_id, 365)

    filename = f"attendance_{child['full_name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(EXPORTS_DIR, filename)
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Status', 'Class'])
        for record in history:
            writer.writerow([
                record.get('session_date', ''),
                record.get('status', ''),
                record.get('class_name', '')
            ])

    document = FSInputFile(filepath)
    await callback.message.answer_document(
        document=document,
        caption=f"📅 Attendance Report: {child['full_name']}"
    )

    await callback.answer("✅ Attendance exported!")

@router.callback_query(F.data == "pa_back")
async def back_to_attendance_menu(callback: CallbackQuery, state: FSMContext):
    """Back to attendance menu"""
    await attendance_menu(callback.message, state)
