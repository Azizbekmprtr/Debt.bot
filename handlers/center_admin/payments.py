# handlers/center_admin/payments.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import database.queries as db
from keyboards.all_keyboards import (
    get_center_admin_main_menu, get_cancel_keyboard,
    get_confirm_keyboard, get_back_keyboard
)
from utils.helpers import format_price
import csv
import os
from config import EXPORTS_DIR

router = Router()

class RecordPaymentStates(StatesGroup):
    selecting_student = State()
    entering_amount = State()
    entering_notes = State()
    confirm = State()

async def get_center_context(state: FSMContext) -> dict:
    data = await state.get_data()
    center_id = data.get('current_center_id')
    center = await db.get_center_by_id(center_id) if center_id else None
    return {'center_id': center_id, 'center': center}

@router.message(F.text == "💰 Payments")
async def payments_menu(message: Message, state: FSMContext):
    """Show payments management menu"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    if not center_id:
        await message.answer("❌ No center context found.")
        return

    # Get revenue stats
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_revenue,
                   COUNT(*) as total_transactions,
                   COALESCE(SUM(CASE WHEN payment_date >= date('now', 'start of month') THEN amount ELSE 0 END), 0) as month_revenue
            FROM payments
            WHERE center_id = ?
        """, (center_id,))
        stats = dict(await cursor.fetchone())

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Record Payment", callback_data="ca_record_payment")],
        [InlineKeyboardButton(text="📋 View Payment History", callback_data="ca_payment_history")],
        [InlineKeyboardButton(text="📊 Revenue Report", callback_data="ca_revenue_report")],
        [InlineKeyboardButton(text="📥 Export Payments", callback_data="ca_export_payments")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")]
    ])

    text = "💰 **Payment Management**\n\n"
    text += f"💰 Total Revenue: **{format_price(stats['total_revenue'])} UZS**\n"
    text += f"📊 Transactions: **{stats['total_transactions']}**\n"
    text += f"📅 This Month: **{format_price(stats['month_revenue'])} UZS**\n\n"
    text += "Select action:"

    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "ca_record_payment")
async def record_payment_start(callback: CallbackQuery, state: FSMContext):
    """Start recording a payment"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    students = await db.get_students_for_center(center_id)

    if not students:
        await callback.answer("No students found", show_alert=True)
        return

    buttons = []
    for student in students[:30]:
        balance = await db.get_student_balance(student['id'])
        buttons.append([InlineKeyboardButton(
            text=f"{student['full_name']} (Balance: {format_price(balance)} UZS)",
            callback_data=f"pay_student_{student['id']}"
        )])

    # Pagination if needed
    if len(students) > 30:
        buttons.append([InlineKeyboardButton(text="🔍 Search Student", callback_data="ca_search_student_payment")])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")])

    await callback.message.edit_text(
        "💳 **Record Payment**\n\nSelect student:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(RecordPaymentStates.selecting_student)

@router.callback_query(RecordPaymentStates.selecting_student, F.data.startswith("pay_student_"))
async def process_payment_student(callback: CallbackQuery, state: FSMContext):
    """Process student selection"""
    student_id = int(callback.data.replace("pay_student_", ""))
    student = await db.get_user_by_id(student_id)
    balance = await db.get_student_balance(student_id)

    await state.update_data(pay_student_id=student_id, pay_student=student, pay_balance=balance)

    await callback.message.edit_text(
        f"💳 **Record Payment**\n\n"
        f"👤 Student: **{student['full_name']}**\n"
        f"💰 Current Balance: **{format_price(balance)} UZS**\n\n"
        "Enter payment amount (UZS):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(RecordPaymentStates.entering_amount)

@router.message(RecordPaymentStates.entering_amount, F.text)
async def process_payment_amount(message: Message, state: FSMContext):
    """Process payment amount"""
    try:
        amount_text = message.text.strip().replace(" ", "").replace(",", "")
        amount = float(amount_text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Please enter a valid positive amount:")
        return

    await state.update_data(pay_amount=amount)

    await message.answer(
        f"✅ Amount: **{format_price(int(amount))} UZS**\n\n"
        "Enter notes (optional, type 'skip'):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(RecordPaymentStates.entering_notes)

@router.message(RecordPaymentStates.entering_notes, F.text)
async def process_payment_notes(message: Message, state: FSMContext):
    """Process payment notes and confirm"""
    notes = message.text.strip()
    if notes.lower() == 'skip':
        notes = None

    data = await state.get_data()

    text = "💳 **Confirm Payment**\n\n"
    text += f"👤 Student: **{data['pay_student']['full_name']}**\n"
    text += f"💰 Amount: **{format_price(int(data['pay_amount']))} UZS**\n"
    if notes:
        text += f"📝 Notes: {notes}\n"
    text += f"\n💰 New Balance: **{format_price(int(data['pay_balance'] + data['pay_amount']))} UZS**\n\n"
    text += "Record this payment?"

    await state.update_data(pay_notes=notes)

    await message.answer(text, reply_markup=get_confirm_keyboard("confirm_payment", "cancel"))
    await state.set_state(RecordPaymentStates.confirm)

@router.callback_query(RecordPaymentStates.confirm, F.data == "confirm_payment")
async def confirm_payment(callback: CallbackQuery, state: FSMContext):
    """Finalize payment recording"""
    data = await state.get_data()
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    payment_id = await db.record_payment(
        student_id=data['pay_student_id'],
        amount=data['pay_amount'],
        payment_method='cash',
        recorded_by=callback.from_user.id,
        center_id=center_id,
        notes=data.get('pay_notes')
    )

    if payment_id:
        # Send notification to student
        student = await db.get_user_by_id(data['pay_student_id'])
        if student and student.get('telegram_id'):
            from services.notifications import send_payment_notification
            await send_payment_notification(
                student['telegram_id'],
                data['pay_amount'],
                datetime.now().strftime('%d.%m.%Y'),
                data.get('pay_notes')
            )

        await callback.message.edit_text(
            f"✅ **Payment Recorded!**\n\n"
            f"💰 Amount: {format_price(int(data['pay_amount']))} UZS\n"
            f"🆔 Transaction ID: {payment_id}",
            reply_markup=get_back_keyboard("ca_back")
        )
    else:
        await callback.message.edit_text(
            "❌ Failed to record payment.",
            reply_markup=get_back_keyboard("ca_back")
        )

    await state.clear()

@router.callback_query(F.data == "ca_payment_history")
async def view_payment_history(callback: CallbackQuery, state: FSMContext):
    """View payment history"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT p.*, u.full_name as student_name, u2.full_name as recorded_by_name
            FROM payments p
            JOIN users u ON p.student_id = u.id
            JOIN users u2 ON p.recorded_by = u2.id
            WHERE p.center_id = ?
            ORDER BY p.payment_date DESC
            LIMIT 50
        """, (center_id,))
        payments = [dict(row) for row in await cursor.fetchall()]

    if not payments:
        await callback.message.edit_text(
            "📋 No payment records found.",
            reply_markup=get_back_keyboard("ca_back")
        )
        return

    text = "📋 **Payment History**\n\n"

    for payment in payments:
        text += f"📅 {payment['payment_date'][:19] if payment.get('payment_date') else 'N/A'}\n"
        text += f"  👤 {payment.get('student_name', 'N/A')}\n"
        text += f"  💰 {format_price(int(payment['amount']))} UZS\n"
        if payment.get('notes'):
            text += f"  📝 {payment['notes']}\n"
        text += f"  👤 By: {payment.get('recorded_by_name', 'N/A')}\n"
        text += "\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("ca_back")
    )

@router.callback_query(F.data == "ca_revenue_report")
async def revenue_report(callback: CallbackQuery, state: FSMContext):
    """Show revenue report"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    async with db.get_db() as conn:
        # Monthly breakdown
        cursor = await conn.execute("""
            SELECT strftime('%Y-%m', payment_date) as month,
                   COALESCE(SUM(amount), 0) as total,
                   COUNT(*) as count
            FROM payments
            WHERE center_id = ? AND payment_date >= date('now', '-12 months')
            GROUP BY strftime('%Y-%m', payment_date)
            ORDER BY month DESC
        """, (center_id,))
        monthly = [dict(row) for row in await cursor.fetchall()]

        # Top paying students
        cursor = await conn.execute("""
            SELECT u.full_name, COALESCE(SUM(p.amount), 0) as total_paid, COUNT(*) as payments
            FROM payments p
            JOIN users u ON p.student_id = u.id
            WHERE p.center_id = ?
            GROUP BY p.student_id
            ORDER BY total_paid DESC
            LIMIT 10
        """, (center_id,))
        top_payers = [dict(row) for row in await cursor.fetchall()]

    text = "💰 **Revenue Report**\n\n"

    text += "📅 **Monthly Breakdown:**\n"
    for month in monthly:
        text += f"  {month['month']}: {format_price(int(month['total']))} UZS ({month['count']} payments)\n"

    text += f"\n🏆 **Top Paying Students:**\n"
    for i, payer in enumerate(top_payers, 1):
        text += f"  {i}. {payer['full_name']}: {format_price(int(payer['total_paid']))} UZS\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Export Report", callback_data="ca_export_payments")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "ca_export_payments")
async def export_payments(callback: CallbackQuery, state: FSMContext):
    """Export payment data to CSV"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    filename = f"payments_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(EXPORTS_DIR, filename)
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT p.payment_date, u.full_name as student_name, p.amount, p.payment_method, p.notes
            FROM payments p
            JOIN users u ON p.student_id = u.id
            WHERE p.center_id = ?
            ORDER BY p.payment_date DESC
        """, (center_id,))

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Student', 'Amount (UZS)', 'Method', 'Notes'])

            for row in await cursor.fetchall():
                writer.writerow([row[0], row[1], row[2], row[3], row[4]])

    document = FSInputFile(filepath)
    await callback.message.answer_document(
        document=document,
        caption="📥 Payment Export"
    )

    await callback.answer("✅ Export complete!")
