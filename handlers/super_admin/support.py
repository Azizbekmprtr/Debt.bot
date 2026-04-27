# handlers/super_admin/support.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import database.queries as db
from keyboards.all_keyboards import (
    get_super_admin_main_menu, get_cancel_keyboard,
    get_confirm_keyboard, get_back_keyboard
)
import json

router = Router()

# ========================
# SUPPORT STATES
# ========================

class RespondTicketStates(StatesGroup):
    selecting_ticket = State()
    entering_response = State()
    confirm_send = State()

class CreateAnnouncementStates(StatesGroup):
    selecting_center = State()
    entering_title = State()
    entering_content = State()
    selecting_target = State()
    confirm_send = State()

class KnowledgeBaseStates(StatesGroup):
    selecting_action = State()
    entering_title = State()
    entering_content = State()
    entering_category = State()
    confirm_create = State()

# ========================
# SUPPORT MAIN MENU
# ========================

@router.message(F.text == "🤝 Support")
async def support_main_menu(message: Message, state: FSMContext):
    """Show support management main menu"""
    # Get ticket stats
    async with db.get_db() as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'open'")
        open_tickets = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'in_progress'")
        in_progress = (await cursor.fetchone())[0]

        cursor = await conn.execute("SELECT COUNT(*) FROM support_tickets WHERE priority = 'urgent' AND status != 'closed'")
        urgent = (await cursor.fetchone())[0]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📋 View All Tickets ({open_tickets} open)", callback_data="sa_all_tickets")],
        [InlineKeyboardButton(text=f"🔥 Urgent Tickets ({urgent})", callback_data="sa_urgent_tickets")],
        [InlineKeyboardButton(text="📊 Ticket Analytics", callback_data="sa_ticket_analytics")],
        [InlineKeyboardButton(text="📢 Create Announcement", callback_data="sa_create_announcement")],
        [InlineKeyboardButton(text="📚 Knowledge Base", callback_data="sa_knowledge_base")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    text = "🤝 **Support & Help Desk**\n\n"
    text += f"📊 **Ticket Overview:**\n"
    text += f"• Open: **{open_tickets}**\n"
    text += f"• In Progress: **{in_progress}**\n"
    text += f"• Urgent: **{urgent}**\n\n"
    text += "Select action:"

    await message.answer(text, reply_markup=keyboard)

# ========================
# VIEW ALL TICKETS
# ========================

@router.callback_query(F.data == "sa_all_tickets")
async def view_all_tickets(callback: CallbackQuery, state: FSMContext):
    """View all support tickets"""
    tickets = await get_all_tickets()

    if not tickets:
        await callback.message.edit_text(
            "✅ No support tickets found.",
            reply_markup=get_back_keyboard("sa_back")
        )
        return

    await state.update_data(ticket_list=tickets, ticket_page=0)
    await display_tickets_page(callback.message, state, 0)

async def get_all_tickets(status: str = None, priority: str = None) -> list:
    """Get tickets with optional filters"""
    async with db.get_db() as conn:
        query = """
            SELECT st.*, u.full_name as user_name, c.name as center_name,
                   (SELECT COUNT(*) FROM ticket_responses WHERE ticket_id = st.id) as response_count
            FROM support_tickets st
            JOIN users u ON st.user_id = u.id
            JOIN centers c ON st.center_id = c.id
            WHERE 1=1
        """
        params = []

        if status:
            query += " AND st.status = ?"
            params.append(status)
        if priority:
            query += " AND st.priority = ?"
            params.append(priority)

        query += " ORDER BY
            CASE st.priority
                WHEN 'urgent' THEN 0
                WHEN 'high' THEN 1
                WHEN 'normal' THEN 2
                WHEN 'low' THEN 3
            END,
            st.created_at DESC"

        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def display_tickets_page(message, state: FSMContext, page: int):
    """Display paginated tickets"""
    data = await state.get_data()
    tickets = data.get('ticket_list', [])
    per_page = 5
    total_pages = max(1, (len(tickets) + per_page - 1) // per_page)
    start = page * per_page
    end = start + per_page
    page_tickets = tickets[start:end]

    priority_icons = {'urgent': '🔴', 'high': '🟠', 'normal': '🟡', 'low': '🟢'}
    status_icons = {'open': '📬', 'in_progress': '🔄', 'resolved': '✅', 'closed': '🔒'}

    text = "📋 **Support Tickets**\n\n"

    for ticket in page_tickets:
        p_icon = priority_icons.get(ticket.get('priority', 'normal'), '⚪')
        s_icon = status_icons.get(ticket.get('status', 'open'), '❓')

        text += f"{p_icon} **#{ticket['id']}** - {ticket['subject'][:50]}\n"
        text += f"   {s_icon} Status: {ticket['status'].replace('_', ' ').title()}\n"
        text += f"   🏢 {ticket.get('center_name', 'N/A')}\n"
        text += f"   👤 {ticket.get('user_name', 'N/A')}\n"
        text += f"   📅 {ticket['created_at'][:10] if ticket.get('created_at') else 'N/A'}\n"
        text += f"   💬 Responses: {ticket.get('response_count', 0)}\n"
        text += "─" * 30 + "\n"

    # Build action buttons
    buttons = []
    for ticket in page_tickets:
        buttons.append([InlineKeyboardButton(
            text=f"📝 #{ticket['id']} - {ticket['subject'][:40]}",
            callback_data=f"sa_ticket_detail_{ticket['id']}"
        )])

    # Pagination
    pagination = []
    if page > 0:
        pagination.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"ticket_page_{page-1}"))
    pagination.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        pagination.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"ticket_page_{page+1}"))
    buttons.append(pagination)

    # Filter buttons
    buttons.append([
        InlineKeyboardButton(text="📬 Open", callback_data="sa_tickets_open"),
        InlineKeyboardButton(text="🔄 In Progress", callback_data="sa_tickets_in_progress"),
        InlineKeyboardButton(text="✅ Resolved", callback_data="sa_tickets_resolved")
    ])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.edit_text(text, reply_markup=keyboard)
    await state.update_data(ticket_page=page)

@router.callback_query(F.data.startswith("ticket_page_"))
async def handle_ticket_pagination(callback: CallbackQuery, state: FSMContext):
    """Handle ticket list pagination"""
    page = int(callback.data.replace("ticket_page_", ""))
    await display_tickets_page(callback.message, state, page)

@router.callback_query(F.data.startswith("sa_tickets_"))
async def filter_tickets_by_status(callback: CallbackQuery, state: FSMContext):
    """Filter tickets by status"""
    status = callback.data.replace("sa_tickets_", "")

    if status == "open":
        tickets = await get_all_tickets(status='open')
    elif status == "in_progress":
        tickets = await get_all_tickets(status='in_progress')
    elif status == "resolved":
        tickets = await get_all_tickets(status='resolved')
    else:
        tickets = await get_all_tickets()

    await state.update_data(ticket_list=tickets, ticket_page=0)
    await display_tickets_page(callback.message, state, 0)

@router.callback_query(F.data == "sa_urgent_tickets")
async def view_urgent_tickets(callback: CallbackQuery, state: FSMContext):
    """View urgent priority tickets"""
    tickets = await get_all_tickets(priority='urgent')

    if not tickets:
        await callback.message.edit_text(
            "✅ No urgent tickets!",
            reply_markup=get_back_keyboard("sa_back")
        )
        return

    await state.update_data(ticket_list=tickets, ticket_page=0)
    await display_tickets_page(callback.message, state, 0)

# ========================
# TICKET DETAIL & RESPONSE
# ========================

@router.callback_query(F.data.startswith("sa_ticket_detail_"))
async def view_ticket_detail(callback: CallbackQuery, state: FSMContext):
    """View detailed ticket information"""
    ticket_id = int(callback.data.replace("sa_ticket_detail_", ""))

    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT st.*, u.full_name as user_name, u.telegram_id,
                   c.name as center_name
            FROM support_tickets st
            JOIN users u ON st.user_id = u.id
            JOIN centers c ON st.center_id = c.id
            WHERE st.id = ?
        """, (ticket_id,))
        ticket = await cursor.fetchone()

        if not ticket:
            await callback.answer("Ticket not found", show_alert=True)
            return
        ticket = dict(ticket)

        # Get responses
        cursor = await conn.execute("""
            SELECT tr.*, u.full_name as responder_name
            FROM ticket_responses tr
            JOIN users u ON tr.user_id = u.id
            WHERE tr.ticket_id = ?
            ORDER BY tr.created_at ASC
        """, (ticket_id,))
        responses = [dict(row) for row in await cursor.fetchall()]

    await state.update_data(current_ticket=ticket, current_ticket_id=ticket_id)

    priority_emoji = {'urgent': '🔴', 'high': '🟠', 'normal': '🟡', 'low': '🟢'}
    status_emoji = {'open': '📬', 'in_progress': '🔄', 'resolved': '✅', 'closed': '🔒'}

    text = f"{priority_emoji.get(ticket['priority'], '⚪')} **Ticket #{ticket_id}**\n\n"
    text += f"📌 **Subject:** {ticket['subject']}\n"
    text += f"📄 **Description:** {ticket['description']}\n\n"
    text += f"🏢 **Center:** {ticket['center_name']}\n"
    text += f"👤 **Reporter:** {ticket['user_name']} (TG: {ticket['telegram_id']})\n"
    text += f"{status_emoji.get(ticket['status'], '❓')} **Status:** {ticket['status'].replace('_', ' ').title()}\n"
    text += f"⚠️ **Priority:** {ticket['priority'].title()}\n"
    text += f"📅 **Created:** {ticket['created_at'][:19] if ticket.get('created_at') else 'N/A'}\n"

    if ticket.get('resolved_at'):
        text += f"✅ **Resolved:** {ticket['resolved_at'][:19]}\n"

    if responses:
        text += f"\n💬 **Responses ({len(responses)}):**\n"
        for resp in responses:
            text += f"\n{'─' * 20}\n"
            text += f"👤 {resp['responder_name']}\n"
            text += f"🕐 {resp['created_at'][:19] if resp.get('created_at') else 'N/A'}\n"
            text += f"💬 {resp['message']}\n"

    # Action buttons
    buttons = []

    if ticket['status'] != 'closed':
        buttons.append([InlineKeyboardButton(text="💬 Respond", callback_data=f"sa_respond_ticket_{ticket_id}")])

        if ticket['status'] == 'open':
            buttons.append([InlineKeyboardButton(text="🔄 Mark In Progress", callback_data=f"sa_ticket_progress_{ticket_id}")])

        if ticket['status'] != 'resolved':
            buttons.append([InlineKeyboardButton(text="✅ Mark Resolved", callback_data=f"sa_ticket_resolve_{ticket_id}")])

    buttons.append([
        InlineKeyboardButton(text="🔴 Urgent", callback_data=f"sa_ticket_priority_{ticket_id}_urgent"),
        InlineKeyboardButton(text="🟠 High", callback_data=f"sa_ticket_priority_{ticket_id}_high"),
        InlineKeyboardButton(text="🟡 Normal", callback_data=f"sa_ticket_priority_{ticket_id}_normal")
    ])
    buttons.append([InlineKeyboardButton(text="🗑️ Delete Ticket", callback_data=f"sa_delete_ticket_{ticket_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Back to List", callback_data="sa_all_tickets")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data.startswith("sa_respond_ticket_"))
async def respond_to_ticket_start(callback: CallbackQuery, state: FSMContext):
    """Start responding to a ticket"""
    ticket_id = int(callback.data.replace("sa_respond_ticket_", ""))
    await state.update_data(respond_ticket_id=ticket_id)

    await callback.message.edit_text(
        f"💬 **Respond to Ticket #{ticket_id}**\n\n"
        "Enter your response:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(RespondTicketStates.entering_response)

@router.message(RespondTicketStates.entering_response, F.text)
async def process_ticket_response(message: Message, state: FSMContext):
    """Process ticket response"""
    data = await state.get_data()
    ticket_id = data['respond_ticket_id']
    response_text = message.text.strip()

    # Save response
    await db.add_ticket_response(
        ticket_id=ticket_id,
        user_id=message.from_user.id,
        message=response_text
    )

    # Update ticket status to in_progress if open
    await db.update_ticket_status(ticket_id, 'in_progress')

    # Log audit
    await db.log_audit(
        user_id=message.from_user.id,
        action='respond_ticket',
        entity_type='support_ticket',
        entity_id=ticket_id
    )

    await message.answer(
        f"✅ Response sent to ticket #{ticket_id}",
        reply_markup=get_back_keyboard(f"sa_ticket_detail_{ticket_id}")
    )
    await state.clear()

@router.callback_query(F.data.startswith("sa_ticket_progress_"))
async def mark_ticket_in_progress(callback: CallbackQuery, state: FSMContext):
    """Mark ticket as in progress"""
    ticket_id = int(callback.data.replace("sa_ticket_progress_", ""))
    await db.update_ticket_status(ticket_id, 'in_progress')
    await callback.answer("✅ Ticket marked as In Progress")
    await view_ticket_detail(callback, state)

@router.callback_query(F.data.startswith("sa_ticket_resolve_"))
async def resolve_ticket(callback: CallbackQuery, state: FSMContext):
    """Resolve a ticket"""
    ticket_id = int(callback.data.replace("sa_ticket_resolve_", ""))
    await db.update_ticket_status(ticket_id, 'resolved')
    await callback.answer("✅ Ticket resolved!")
    await view_ticket_detail(callback, state)

@router.callback_query(F.data.startswith("sa_ticket_priority_"))
async def change_ticket_priority(callback: CallbackQuery, state: FSMContext):
    """Change ticket priority"""
    parts = callback.data.replace("sa_ticket_priority_", "").split("_")
    ticket_id = int(parts[0])
    priority = parts[1]

    await db.update_ticket_priority(ticket_id, priority)
    await callback.answer(f"✅ Priority set to {priority.title()}")
    await view_ticket_detail(callback, state)

@router.callback_query(F.data.startswith("sa_delete_ticket_"))
async def delete_ticket(callback: CallbackQuery, state: FSMContext):
    """Delete a ticket"""
    ticket_id = int(callback.data.replace("sa_delete_ticket_", ""))

    await db.delete_ticket(ticket_id)

    # Log audit
    await db.log_audit(
        user_id=callback.from_user.id,
        action='delete_ticket',
        entity_type='support_ticket',
        entity_id=ticket_id
    )

    await callback.message.edit_text(
        f"✅ Ticket #{ticket_id} deleted.",
        reply_markup=get_back_keyboard("sa_all_tickets")
    )

# ========================
# TICKET ANALYTICS
# ========================

@router.callback_query(F.data == "sa_ticket_analytics")
async def show_ticket_analytics(callback: CallbackQuery, state: FSMContext):
    """Show ticket analytics"""
    async with db.get_db() as conn:
        # Total tickets
        cursor = await conn.execute("SELECT COUNT(*) FROM support_tickets")
        total = (await cursor.fetchone())[0]

        # By status
        cursor = await conn.execute("""
            SELECT status, COUNT(*) as count FROM support_tickets GROUP BY status
        """)
        by_status = [dict(row) for row in await cursor.fetchall()]

        # By priority
        cursor = await conn.execute("""
            SELECT priority, COUNT(*) as count FROM support_tickets GROUP BY priority
        """)
        by_priority = [dict(row) for row in await cursor.fetchall()]

        # By center
        cursor = await conn.execute("""
            SELECT c.name, COUNT(st.id) as count
            FROM support_tickets st
            JOIN centers c ON st.center_id = c.id
            GROUP BY st.center_id
            ORDER BY count DESC
            LIMIT 10
        """)
        by_center = [dict(row) for row in await cursor.fetchall()]

        # Average response time
        cursor = await conn.execute("""
            SELECT AVG(
                (SELECT MIN(tr.created_at) FROM ticket_responses tr WHERE tr.ticket_id = st.id)
                - st.created_at
            ) as avg_response_seconds
            FROM support_tickets st
            WHERE EXISTS (SELECT 1 FROM ticket_responses WHERE ticket_id = st.id)
        """)
        avg_response = await cursor.fetchone()
        avg_hours = (avg_response[0] or 0) / 3600 if avg_response else 0

        # Resolution rate
        cursor = await conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'resolved' OR status = 'closed' THEN 1 END) as resolved
            FROM support_tickets
        """)
        resolution = await cursor.fetchone()
        resolution_rate = (resolution[1] / resolution[0] * 100) if resolution and resolution[0] > 0 else 0

    text = "📊 **Ticket Analytics**\n\n"
    text += f"📬 **Total Tickets:** {total}\n"
    text += f"⏱️ **Avg Response Time:** {avg_hours:.1f} hours\n"
    text += f"✅ **Resolution Rate:** {resolution_rate:.1f}%\n\n"

    text += "**By Status:**\n"
    for bs in by_status:
        text += f"• {bs['status'].replace('_', ' ').title()}: {bs['count']}\n"

    text += "\n**By Priority:**\n"
    for bp in by_priority:
        text += f"• {bp['priority'].title()}: {bp['count']}\n"

    text += "\n**Top Centers by Tickets:**\n"
    for bc in by_center[:5]:
        text += f"• {bc['name']}: {bc['count']}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Export Report", callback_data="sa_export_ticket_report")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

# ========================
# CREATE ANNOUNCEMENT
# ========================

@router.callback_query(F.data == "sa_create_announcement")
async def create_announcement_start(callback: CallbackQuery, state: FSMContext):
    """Start creating a platform-wide announcement"""
    centers = await db.get_all_centers()

    buttons = [
        [InlineKeyboardButton(text="🌐 All Centers", callback_data="announce_all_centers")]
    ]

    for center in centers[:20]:
        buttons.append([InlineKeyboardButton(
            text=center['name'],
            callback_data=f"announce_center_{center['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")])

    await callback.message.edit_text(
        "📢 **Create Announcement**\n\n"
        "Select target centers:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(CreateAnnouncementStates.selecting_center)

@router.callback_query(CreateAnnouncementStates.selecting_center, F.data.startswith("announce_"))
async def process_announcement_center(callback: CallbackQuery, state: FSMContext):
    """Process center selection and ask for title"""
    target = callback.data.replace("announce_", "")

    await state.update_data(announce_target=target)

    await callback.message.edit_text(
        "Enter announcement title:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateAnnouncementStates.entering_title)

@router.message(CreateAnnouncementStates.entering_title, F.text)
async def process_announcement_title(message: Message, state: FSMContext):
    """Process announcement title"""
    title = message.text.strip()
    if len(title) < 3:
        await message.answer("❌ Title must be at least 3 characters.")
        return

    await state.update_data(announce_title=title)

    await message.answer(
        "Enter announcement content (supports markdown):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateAnnouncementStates.entering_content)

@router.message(CreateAnnouncementStates.entering_content, F.text)
async def process_announcement_content(message: Message, state: FSMContext):
    """Process announcement content and ask for target role"""
    content = message.text.strip()
    await state.update_data(announce_content=content)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 All Users", callback_data="announce_role_all")],
        [InlineKeyboardButton(text="👨‍🏫 Teachers Only", callback_data="announce_role_teachers")],
        [InlineKeyboardButton(text="🎓 Students Only", callback_data="announce_role_students")],
        [InlineKeyboardButton(text="👪 Parents Only", callback_data="announce_role_parents")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="cancel")]
    ])

    await message.answer(
        "Select target audience:",
        reply_markup=keyboard
    )
    await state.set_state(CreateAnnouncementStates.selecting_target)

@router.callback_query(CreateAnnouncementStates.selecting_target, F.data.startswith("announce_role_"))
async def process_announcement_target(callback: CallbackQuery, state: FSMContext):
    """Process target role and confirm"""
    target_role = callback.data.replace("announce_role_", "")
    await state.update_data(announce_role=target_role)

    data = await state.get_data()

    text = "📢 **Confirm Announcement**\n\n"
    text += f"📌 **Title:** {data['announce_title']}\n"
    text += f"🎯 **Target:** {target_role.replace('_', ' ').title()}\n"
    text += f"📄 **Content:**\n{data['announce_content'][:200]}...\n\n"
    text += "Send this announcement?"

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Send", callback_data="confirm_send_announcement"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")
            ]
        ])
    )
    await state.set_state(CreateAnnouncementStates.confirm_send)

@router.callback_query(CreateAnnouncementStates.confirm_send, F.data == "confirm_send_announcement")
async def send_announcement(callback: CallbackQuery, state: FSMContext):
    """Send the announcement"""
    data = await state.get_data()

    # Create announcements for target centers
    target = data['announce_target']
    centers = []

    if target == "all_centers":
        centers = await db.get_all_centers()
    else:
        center_id = int(target.replace("center_", ""))
        center = await db.get_center_by_id(center_id)
        if center:
            centers = [center]

    announcement_count = 0
    for center in centers:
        await db.create_announcement(
            center_id=center['id'],
            title=data['announce_title'],
            content=data['announce_content'],
            target_role=data['announce_role'],
            created_by=callback.from_user.id
        )
        announcement_count += 1

    # Log audit
    await db.log_audit(
        user_id=callback.from_user.id,
        action='create_announcement',
        entity_type='announcement',
        new_values={'target': target, 'role': data['announce_role'], 'centers': announcement_count}
    )

    await callback.message.edit_text(
        f"✅ **Announcement Sent!**\n\n"
        f"📊 Sent to {announcement_count} center(s)\n"
        f"🎯 Target: {data['announce_role'].replace('_', ' ').title()}\n"
        f"📌 Title: {data['announce_title']}",
        reply_markup=get_back_keyboard("sa_back")
    )
    await state.clear()
