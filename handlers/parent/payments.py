# handlers/parent/payments.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from datetime import datetime
import database.queries as db
from keyboards.all_keyboards import (
    get_parent_main_menu, get_parent_children_keyboard,
    get_back_keyboard
)
from utils.helpers import format_price
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

@router.message(F.text == "💰 Payments")
async def payments_menu(message: Message, state: FSMContext):
    """Show payments tracking menu"""
    ctx = await get_parent_context(state)
    children = ctx.get('children', [])

    if not children:
        await message.answer(
            "👶 No children linked to your account.",
            reply_markup=get_parent_main_menu()
        )
        return

    # Quick balance summary for all children
    text = "💰 **Payment Tracking**\n\n"

    for child in children:
        balance = await db.get_student_balance(child['id'])
        payments = await db.get_student_payment_history(child['id'], 5)
        last_payment = payments[0] if payments else None

        text += f"👶 **{child['full_name']}**\n"
        text += f"  💳 Balance: **{format_price(int(balance))} UZS**\n"
        if last_payment:
            text += f"  📅 Last Payment: {last_payment['payment_date'][:10] if last_payment.get('payment_date') else 'N/A'}\n"
            text += f"  💰 Amount: {format_price(int(last_payment['amount']))} UZS\n"
        text += "\n"

    text += "Select child for detailed view:"

    await message.answer(text, reply_markup=get_parent_children_keyboard(children))

@router.callback_query(F.data.startswith("parent_child_"))
async def view_child_payment_detail(callback: CallbackQuery, state: FSMContext):
    """View detailed payment history for a child"""
    child_id = int(callback.data.replace("parent_child_", ""))
    child = await db.get_user_by_id(child_id)

    if not child:
        await callback.answer("Child not found", show_alert=True)
        return

    balance = await db.get_student_balance(child_id)
    payments = await db.get_student_payment_history(child_id, 50)

    text = f"💰 **Payment History: {child['full_name']}**\n\n"
    text += "══════════════════════════════\n\n"

    text += f"💳 **Current Balance:** {format_price(int(balance))} UZS\n\n"

    if payments:
        # Summary
        total_paid = sum(p['amount'] for p in payments)
        text += f"📊 **Summary:**\n"
        text += f"  • Total Paid: **{format_price(int(total_paid))} UZS**\n"
        text += f"  • Transactions: **{len(payments)}**\n"
        text += f"  • Average: **{format_price(int(total_paid/len(payments)))} UZS**\n\n"

        text += "📋 **Transaction History:**\n"
        for payment in payments[:20]:
            date = payment.get('payment_date', '')
            if isinstance(date, str) and len(date) >= 10:
                date = date[:10]

            text += f"📅 **{date}**\n"
            text += f"  💰 Amount: **{format_price(int(payment['amount']))} UZS**\n"
            text += f"  💳 Method: {payment.get('payment_method', 'cash').title()}\n"
            if payment.get('notes'):
                text += f"  📝 {payment['notes']}\n"
            if payment.get('recorded_by_name'):
                text += f"  👤 Recorded by: {payment['recorded_by_name']}\n"
            if payment.get('payment_for_month'):
                text += f"  📅 For: {payment['payment_for_month']}\n"
            text += "\n"

        # Monthly breakdown
        monthly_totals = {}
        for payment in payments:
            if payment.get('payment_date'):
                month = payment['payment_date'][:7] if isinstance(payment['payment_date'], str) else str(payment['payment_date'])[:7]
                monthly_totals[month] = monthly_totals.get(month, 0) + payment['amount']

        if monthly_totals:
            text += "📅 **Monthly Breakdown:**\n"
            for month in sorted(monthly_totals.keys(), reverse=True)[:12]:
                text += f"  {month}: {format_price(int(monthly_totals[month]))} UZS\n"
    else:
        text += "No payment records found.\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Export Payments", callback_data=f"ppay_export_{child_id}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="ppay_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("ppay_export_"))
async def export_child_payments(callback: CallbackQuery, state: FSMContext):
    """Export child's payment history to CSV"""
    child_id = int(callback.data.replace("ppay_export_", ""))
    child = await db.get_user_by_id(child_id)

    if not child:
        await callback.answer("Child not found", show_alert=True)
        return

    payments = await db.get_student_payment_history(child_id, 365)

    filename = f"payments_{child['full_name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(EXPORTS_DIR, filename)
    os.makedirs(EXPORTS_DIR, exist_ok=True)

    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['Date', 'Amount (UZS)', 'Method', 'Notes', 'Month', 'Recorded By'])
        for payment in payments:
            writer.writerow([
                payment.get('payment_date', '')[:10] if payment.get('payment_date') else '',
                payment.get('amount', 0),
                payment.get('payment_method', 'cash'),
                payment.get('notes', ''),
                payment.get('payment_for_month', ''),
                payment.get('recorded_by_name', '')
            ])

    document = FSInputFile(filepath)
    await callback.message.answer_document(
        document=document,
        caption=f"💰 Payment History: {child['full_name']}"
    )

    await callback.answer("✅ Payments exported!")

@router.callback_query(F.data == "ppay_back")
async def back_to_payments_menu(callback: CallbackQuery, state: FSMContext):
    """Back to payments menu"""
    await payments_menu(callback.message, state)
