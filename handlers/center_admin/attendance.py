# handlers/center_admin/attendance.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import database.queries as db
from keyboards.all_keyboards import (
    get_center_admin_main_menu, get_cancel_keyboard,
    get_confirm_keyboard, get_back_keyboard
)
import csv
import os
from config import EXPORTS_DIR

router = Router()

async def get_center_context(state: FSMContext) -> dict:
    data = await state.get_data()
    center_id = data.get('current_center_id')
    center = await db.get_center_by_id(center_id) if center_id else None
    return {'center_id': center_id, 'center': center}

@router.message(F.text == "📅 Attendance")
async def attendance_menu(message: Message, state: FSMContext):
    """Show attendance management menu"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    if not center_id:
        await message.answer("❌ No center context found.")
        return

    # Get attendance stats
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT COUNT(DISTINCT a.id) as total_sessions,
                   COUNT(DISTINCT CASE WHEN a.session_date = date('now') THEN a.id END) as today_sessions
            FROM attendance_sessions a
            JOIN classes c ON a.class_id = c.id
            WHERE c.center_id = ?
        """, (center_id,))
        stats = dict(await cursor.fetchone())

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 View Attendance Records", callback_data="ca_view_attendance")],
        [InlineKeyboardButton(text="📊 Attendance Statistics", callback_data="ca_attendance_stats")],
        [InlineKeyboardButton(text="📥 Export Attendance", callback_data="ca_export_attendance")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")]
    ])

    text = "📅 **Attendance Management**\n\n"
    text += f"📊 Total Sessions: **{stats.get('total_sessions', 0)}**\n"
    text += f"📅 Today's Sessions: **{stats.get('today_sessions', 0)}**\n\n"
    text += "Select action:"

    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "ca_view_attendance")
async def view_attendance_start(callback: CallbackQuery, state: FSMContext):
    """Start viewing attendance records"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    classes = await db.get_classes_for_center(center_id)

    if not classes:
        await callback.answer("No classes found", show_alert=True)
        return

    buttons = []
    for cls in classes:
        buttons.append([InlineKeyboardButton(
            text=f"{cls['name']} ({cls['level']})",
            callback_data=f"ca_att_class_{cls['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")])

    await callback.message.edit_text(
        "Select class to view attendance:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("ca_att_class_"))
async def view_class_attendance(callback: CallbackQuery, state: FSMContext):
    """View attendance for a specific class"""
    class_id = int(callback.data.replace("ca_att_class_", ""))

    # Get recent attendance sessions
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT * FROM attendance_sessions
            WHERE class_id = ?
            ORDER BY session_date DESC
            LIMIT 20
        """, (class_id,))
        sessions = [dict(row) for row in await cursor.fetchall()]

    if not sessions:
        await callback.message.edit_text(
            "📋 No attendance records yet.",
            reply_markup=get_back_keyboard("ca_view_attendance")
        )
        return

    text = "📋 **Attendance Records**\n\n"
    buttons = []

    for session in sessions:
        # Get summary for this session
        summary = await db.get_attendance_summary(session['id'])
        summary_data = summary.get('summary', {})

        text += f"📅 **{session['session_date']}**\n"
        text += f"  ✅ Present: {summary_data.get('present', 0)}\n"
        text += f"  ❌ Absent: {summary_data.get('absent', 0)}\n"
        text += f"  ⏰ Late: {summary_data.get('late', 0)}\n\n"

        buttons.append([InlineKeyboardButton(
            text=f"📋 {session['session_date']} - Details",
            callback_data=f"ca_att_session_{session['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_view_attendance")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("ca_att_session_"))
async def view_session_detail(callback: CallbackQuery, state: FSMContext):
    """View detailed attendance session"""
    session_id = int(callback.data.replace("ca_att_session_", ""))
    summary = await db.get_attendance_summary(session_id)

    text = "📋 **Attendance Details**\n\n"
    text += f"📅 Date: {summary['session']['session_date']}\n\n"

    records = summary.get('records', [])
    for record in records:
        status_emoji = {'present': '✅', 'late': '⏰', 'absent': '❌', 'excused': '📝'}
        emoji = status_emoji.get(record['status'], '❓')
        text += f"{emoji} **{record['name']}** - {record['status'].title()}\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("ca_view_attendance")
    )

@router.callback_query(F.data == "ca_attendance_stats")
async def attendance_statistics(callback: CallbackQuery, state: FSMContext):
    """Show attendance statistics"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    # Get overall statistics
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT
                COUNT(DISTINCT a.id) as total_sessions,
                COUNT(DISTINCT c.id) as total_classes,
                AVG(CAST(
                    (SELECT COUNT(*) FROM attendance_records ar WHERE ar.session_id = a.id AND ar.status = 'present')
                    AS FLOAT) /
                    NULLIF((SELECT COUNT(*) FROM attendance_records ar WHERE ar.session_id = a.id), 0)
                ) * 100 as avg_rate
            FROM attendance_sessions a
            JOIN classes c ON a.class_id = c.id
            WHERE c.center_id = ?
        """, (center_id,))
        stats = dict(await cursor.fetchone())

        # By class
        cursor = await conn.execute("""
            SELECT c.name, c.level,
                   COUNT(DISTINCT a.id) as sessions,
                   (SELECT COUNT(*) FROM attendance_records ar
                    JOIN attendance_sessions a2 ON ar.session_id = a2.id
                    WHERE a2.class_id = c.id AND ar.status = 'present') as total_present,
                   (SELECT COUNT(*) FROM attendance_records ar
                    JOIN attendance_sessions a2 ON ar.session_id = a2.id
                    WHERE a2.class_id = c.id) as total_records
            FROM classes c
            LEFT JOIN attendance_sessions a ON c.id = a.class_id
            WHERE c.center_id = ?
            GROUP BY c.id
        """, (center_id,))
        class_stats = [dict(row) for row in await cursor.fetchall()]

    text = "📊 **Attendance Statistics**\n\n"
    text += f"📅 Total Sessions: **{stats.get('total_sessions', 0)}**\n"
    text += f"🏫 Total Classes: **{stats.get('total_classes', 0)}**\n"
    text += f"📈 Average Rate: **{stats.get('avg_rate', 0):.1f}%**\n\n"

    text += "**By Class:**\n"
    for cs in class_stats:
        rate = (cs['total_present'] / cs['total_records'] * 100) if cs['total_records'] > 0 else 0
        text += f"• {cs['name']}: {rate:.1f}% ({cs['sessions']} sessions)\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("ca_back")
    )

@router.callback_query(F.data == "ca_export_attendance")
async def export_attendance_start(callback: CallbackQuery, state: FSMContext):
    """Export attendance data"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    classes = await db.get_classes_for_center(center_id)

    buttons = []
    for cls in classes:
        buttons.append([InlineKeyboardButton(
            text=f"{cls['name']} ({cls['level']})",
            callback_data=f"ca_export_att_class_{cls['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="📊 Export All", callback_data="ca_export_att_all")])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")])

    await callback.message.edit_text(
        "📥 **Export Attendance**\n\nSelect class or export all:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("ca_export_att_"))
async def export_attendance_execute(callback: CallbackQuery, state: FSMContext):
    """Execute attendance export"""
    target = callback.data.replace("ca_export_att_", "")

    if target == "all":
        ctx = await get_center_context(state)
        center_id = ctx['center_id']
        classes = await db.get_classes_for_center(center_id)
        class_ids = [c['id'] for c in classes]
    else:
        class_ids = [int(target.replace("class_", ""))]

    # Generate CSV
    filename = f"attendance_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(EXPORTS_DIR, filename)
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Class', 'Student', 'Status'])

        for class_id in class_ids:
            async with db.get_db() as conn:
                cursor = await conn.execute("""
                    SELECT a.session_date, c.name as class_name, u.full_name, ar.status
                    FROM attendance_records ar
                    JOIN attendance_sessions a ON ar.session_id = a.id
                    JOIN classes c ON a.class_id = c.id
                    JOIN users u ON ar.student_id = u.id
                    WHERE a.class_id = ?
                    ORDER BY a.session_date DESC, u.full_name
                """, (class_id,))

                for row in await cursor.fetchall():
                    writer.writerow([row[0], row[1], row[2], row[3]])

    document = FSInputFile(filepath)
    await callback.message.answer_document(
        document=document,
        caption="📥 Attendance Export"
    )

    await callback.message.edit_text(
        "✅ Attendance exported!",
        reply_markup=get_back_keyboard("ca_back")
    )
