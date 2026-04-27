# handlers/center_admin/competitions.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import database.queries as db
from keyboards.all_keyboards import (
    get_center_admin_main_menu, get_cancel_keyboard,
    get_confirm_keyboard, get_back_keyboard
)

router = Router()

class CreateCompetitionStates(StatesGroup):
    entering_title = State()
    selecting_type = State()
    selecting_scope = State()
    selecting_duration = State()
    entering_description = State()
    confirm = State()

async def get_center_context(state: FSMContext) -> dict:
    data = await state.get_data()
    center_id = data.get('current_center_id')
    center = await db.get_center_by_id(center_id) if center_id else None
    return {'center_id': center_id, 'center': center}

@router.message(F.text == "🏆 Competitions")
async def competitions_menu(message: Message, state: FSMContext):
    """Show competitions management menu"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    if not center_id:
        await message.answer("❌ No center context found.")
        return

    # Get active competitions
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT COUNT(*) FROM competitions
            WHERE center_id = ? AND is_active = 1 AND end_date >= date('now')
        """, (center_id,))
        active_count = (await cursor.fetchone())[0]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create Competition", callback_data="ca_create_competition")],
        [InlineKeyboardButton(text="📋 View Active", callback_data="ca_active_competitions")],
        [InlineKeyboardButton(text="🏆 View Results", callback_data="ca_competition_results")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")]
    ])

    text = "🏆 **Competition Management**\n\n"
    text += f"📊 Active Competitions: **{active_count}**\n\n"
    text += "Create daily, weekly, or monthly competitions\n"
    text += "to motivate students!"

    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "ca_create_competition")
async def create_competition_start(callback: CallbackQuery, state: FSMContext):
    """Start creating a competition"""
    await callback.message.edit_text(
        "🏆 **Create Competition**\n\n"
        "Enter competition title:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateCompetitionStates.entering_title)

@router.message(CreateCompetitionStates.entering_title, F.text)
async def process_comp_title(message: Message, state: FSMContext):
    """Process competition title"""
    title = message.text.strip()
    if len(title) < 3 or len(title) > 100:
        await message.answer("❌ Title must be between 3 and 100 characters.")
        return

    await state.update_data(comp_title=title)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Daily", callback_data="comp_type_daily")],
        [InlineKeyboardButton(text="📅 Weekly", callback_data="comp_type_weekly")],
        [InlineKeyboardButton(text="📅 Monthly", callback_data="comp_type_monthly")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="cancel")]
    ])

    await message.answer(
        f"✅ Title: **{title}**\n\nSelect competition type:",
        reply_markup=keyboard
    )
    await state.set_state(CreateCompetitionStates.selecting_type)

@router.callback_query(CreateCompetitionStates.selecting_type, F.data.startswith("comp_type_"))
async def process_comp_type(callback: CallbackQuery, state: FSMContext):
    """Process competition type"""
    comp_type = callback.data.replace("comp_type_", "")
    await state.update_data(comp_type=comp_type)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏫 By Class", callback_data="comp_scope_class")],
        [InlineKeyboardButton(text="📊 By Level", callback_data="comp_scope_level")],
        [InlineKeyboardButton(text="🌍 Center-wide", callback_data="comp_scope_center")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="cancel")]
    ])

    await callback.message.edit_text(
        f"✅ Type: **{comp_type.title()}**\n\nSelect scope:",
        reply_markup=keyboard
    )
    await state.set_state(CreateCompetitionStates.selecting_scope)

@router.callback_query(CreateCompetitionStates.selecting_scope, F.data.startswith("comp_scope_"))
async def process_comp_scope(callback: CallbackQuery, state: FSMContext):
    """Process competition scope"""
    scope = callback.data.replace("comp_scope_", "")
    await state.update_data(comp_scope=scope)

    await callback.message.edit_text(
        f"✅ Scope: **{scope.title()}**\n\n"
        "Enter description (optional, type 'skip'):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateCompetitionStates.entering_description)

@router.message(CreateCompetitionStates.entering_description, F.text)
async def process_comp_description(message: Message, state: FSMContext):
    """Process description and confirm"""
    desc = message.text.strip()
    if desc.lower() == 'skip':
        desc = None

    await state.update_data(comp_description=desc)

    data = await state.get_data()

    # Calculate dates based on type
    now = datetime.now()
    if data['comp_type'] == 'daily':
        start_date = now.replace(hour=0, minute=0, second=0)
        end_date = start_date + timedelta(days=1)
    elif data['comp_type'] == 'weekly':
        start_date = now - timedelta(days=now.weekday())
        end_date = start_date + timedelta(days=7)
    else:  # monthly
        start_date = now.replace(day=1)
        if now.month == 12:
            end_date = start_date.replace(year=now.year+1, month=1)
        else:
            end_date = start_date.replace(month=now.month+1)

    text = "🏆 **Confirm Competition**\n\n"
    text += f"📌 **Title:** {data['comp_title']}\n"
    text += f"📅 **Type:** {data['comp_type'].title()}\n"
    text += f"🎯 **Scope:** {data['comp_scope'].title()}\n"
    if desc:
        text += f"📄 **Description:** {desc}\n"
    text += f"\n📅 Start: {start_date.strftime('%Y-%m-%d')}\n"
    text += f"📅 End: {end_date.strftime('%Y-%m-%d')}\n\n"
    text += "Create this competition?"

    await state.update_data(comp_start=str(start_date), comp_end=str(end_date))

    await message.answer(text, reply_markup=get_confirm_keyboard("confirm_create_comp", "cancel"))
    await state.set_state(CreateCompetitionStates.confirm)

@router.callback_query(CreateCompetitionStates.confirm, F.data == "confirm_create_comp")
async def confirm_create_competition(callback: CallbackQuery, state: FSMContext):
    """Finalize competition creation"""
    data = await state.get_data()
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    competition_id = await db.create_competition(
        center_id=center_id,
        title=data['comp_title'],
        competition_type=data['comp_type'],
        scope_type=data['comp_scope'],
        start_date=data['comp_start'],
        end_date=data['comp_end'],
        description=data.get('comp_description'),
        created_by=callback.from_user.id
    )

    if competition_id:
        await callback.message.edit_text(
            f"✅ **Competition Created!**\n\n"
            f"🏆 {data['comp_title']}\n"
            f"📅 {data['comp_type'].title()} competition\n"
            f"🎯 Scope: {data['comp_scope'].title()}\n\n"
            f"Students will be automatically enrolled.",
            reply_markup=get_back_keyboard("ca_back")
        )
    else:
        await callback.message.edit_text(
            "❌ Failed to create competition.",
            reply_markup=get_back_keyboard("ca_back")
        )

    await state.clear()

@router.callback_query(F.data == "ca_active_competitions")
async def view_active_competitions(callback: CallbackQuery, state: FSMContext):
    """View active competitions"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT * FROM competitions
            WHERE center_id = ? AND is_active = 1 AND end_date >= date('now')
            ORDER BY end_date ASC
        """, (center_id,))
        competitions = [dict(row) for row in await cursor.fetchall()]

    if not competitions:
        await callback.message.edit_text(
            "🏆 No active competitions.",
            reply_markup=get_back_keyboard("ca_back")
        )
        return

    text = "🏆 **Active Competitions**\n\n"
    buttons = []

    for comp in competitions:
        days_left = (datetime.fromisoformat(comp['end_date']) - datetime.now()).days
        text += f"**{comp['title']}**\n"
        text += f"  📅 Type: {comp['competition_type'].title()}\n"
        text += f"  🎯 Scope: {comp['scope_type'].title()}\n"
        text += f"  ⏰ {days_left} days remaining\n\n"

        buttons.append([InlineKeyboardButton(
            text=f"📊 {comp['title'][:40]}",
            callback_data=f"ca_comp_leaderboard_{comp['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("ca_comp_leaderboard_"))
async def view_competition_leaderboard(callback: CallbackQuery, state: FSMContext):
    """View competition leaderboard"""
    competition_id = int(callback.data.replace("ca_comp_leaderboard_", ""))
    leaderboard = await db.get_competition_leaderboard(competition_id, 20)

    text = "🏆 **Competition Leaderboard**\n\n"

    if not leaderboard:
        text += "No participants yet.\n"
    else:
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for entry in leaderboard:
            rank = entry.get('rank', '?')
            medal = medals.get(rank, f"#{rank}")
            text += f"{medal} **{entry['full_name']}**\n"
            text += f"   ⭐ {entry.get('points_earned', 0)} points\n"
            if entry.get('class_name'):
                text += f"   🏫 {entry['class_name']}\n"
            text += "\n"

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("ca_active_competitions")
    )

@router.callback_query(F.data == "ca_competition_results")
async def view_competition_results(callback: CallbackQuery, state: FSMContext):
    """View past competition results"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT * FROM competitions
            WHERE center_id = ? AND end_date < date('now')
            ORDER BY end_date DESC
            LIMIT 10
        """, (center_id,))
        competitions = [dict(row) for row in await cursor.fetchall()]

    if not competitions:
        await callback.message.edit_text(
            "🏆 No past competitions.",
            reply_markup=get_back_keyboard("ca_back")
        )
        return

    text = "🏆 **Past Competitions**\n\n"
    buttons = []

    for comp in competitions:
        text += f"**{comp['title']}**\n"
        text += f"  📅 {comp['start_date'][:10]} - {comp['end_date'][:10]}\n\n"

        buttons.append([InlineKeyboardButton(
            text=f"📊 {comp['title'][:40]} - Results",
            callback_data=f"ca_comp_leaderboard_{comp['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
