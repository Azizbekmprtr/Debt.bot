# handlers/super_admin/subscriptions.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime, timedelta
import database.queries as db
from keyboards.all_keyboards import (
    get_super_admin_subscriptions_menu, get_super_admin_main_menu,
    get_cancel_keyboard, get_confirm_keyboard, get_back_keyboard
)
import json

router = Router()

class CreatePlanStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_slug = State()
    waiting_for_description = State()
    waiting_for_max_students = State()
    waiting_for_max_teachers = State()
    waiting_for_max_classes = State()
    waiting_for_price_monthly = State()
    waiting_for_price_yearly = State()
    waiting_for_trial_days = State()
    waiting_for_features = State()
    confirm_creation = State()

class AssignPlanStates(StatesGroup):
    selecting_center = State()
    selecting_plan = State()
    selecting_period = State()
    confirm_assignment = State()

# ========================
# SUBSCRIPTIONS MAIN MENU
# ========================

@router.message(F.text == "💰 Subscriptions")
async def subscriptions_main_menu(message: Message, state: FSMContext):
    """Show subscriptions management main menu"""
    await message.answer(
        "💰 **Subscriptions & Billing Management**\n\n"
        "Manage subscription plans and center billing.",
        reply_markup=get_super_admin_subscriptions_menu()
    )

# ========================
# VIEW ALL PLANS
# ========================

@router.callback_query(F.data == "sa_list_plans")
async def list_all_plans(callback: CallbackQuery, state: FSMContext):
    """List all subscription plans"""
    plans = await db.get_all_subscription_plans()

    if not plans:
        await callback.message.edit_text(
            "No subscription plans found. Create your first plan!",
            reply_markup=get_back_keyboard("sa_back")
        )
        return

    text = "📋 **Subscription Plans**\n\n"
    buttons = []

    for plan in plans:
        status = "🟢 Active" if plan['is_active'] else "🔴 Inactive"
        features = json.loads(plan['features']) if isinstance(plan['features'], str) else plan['features']
        feature_count = len(features) if features else 0

        text += f"**{plan['name']}** ({plan['slug']})\n"
        text += f"   Status: {status}\n"
        text += f"   Max Students: {plan['max_students']}\n"
        text += f"   Max Teachers: {plan['max_teachers']}\n"
        text += f"   Monthly: ${plan['price_monthly']} | Yearly: ${plan['price_yearly']}\n"
        text += f"   Trial: {plan['trial_days']} days\n"
        text += f"   Features: {feature_count}\n"
        text += "─" * 30 + "\n"

        buttons.append([InlineKeyboardButton(
            text=f"✏️ Edit {plan['name']}",
            callback_data=f"sa_edit_plan_{plan['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="➕ Create New Plan", callback_data="sa_create_plan")])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ========================
# CREATE SUBSCRIPTION PLAN
# ========================

@router.callback_query(F.data == "sa_create_plan")
async def start_create_plan(callback: CallbackQuery, state: FSMContext):
    """Start plan creation flow"""
    await callback.message.edit_text(
        "💰 **Create New Subscription Plan**\n\n"
        "Enter plan name (e.g., 'Pro', 'Enterprise'):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreatePlanStates.waiting_for_name)

@router.message(CreatePlanStates.waiting_for_name, F.text)
async def process_plan_name(message: Message, state: FSMContext):
    """Process plan name"""
    name = message.text.strip()
    if len(name) < 2 or len(name) > 50:
        await message.answer("❌ Plan name must be between 2 and 50 characters.")
        return

    await state.update_data(plan_name=name)
    slug = name.lower().replace(' ', '_')

    await message.answer(
        f"✅ Name: **{name}**\n\n"
        f"Enter a unique slug (URL identifier)\n"
        f"Suggestion: `{slug}` (type 'use' to accept):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreatePlanStates.waiting_for_slug)

@router.message(CreatePlanStates.waiting_for_slug, F.text)
async def process_plan_slug(message: Message, state: FSMContext):
    """Process plan slug"""
    data = await state.get_data()

    if message.text.strip().lower() == 'use':
        slug = data['plan_name'].lower().replace(' ', '_')
    else:
        slug = message.text.strip().lower().replace(' ', '_')

    # Check uniqueness
    existing = await db.get_subscription_plan_by_slug(slug)
    if existing:
        await message.answer("❌ This slug is already taken. Choose another:")
        return

    await state.update_data(plan_slug=slug)

    await message.answer(
        "Enter plan description:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreatePlanStates.waiting_for_description)

@router.message(CreatePlanStates.waiting_for_description, F.text)
async def process_plan_description(message: Message, state: FSMContext):
    """Process plan description"""
    await state.update_data(plan_description=message.text.strip())

    await message.answer(
        "Enter maximum number of students allowed:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreatePlanStates.waiting_for_max_students)

@router.message(CreatePlanStates.waiting_for_max_students, F.text)
async def process_max_students(message: Message, state: FSMContext):
    """Process max students"""
    try:
        max_students = int(message.text.strip())
        if max_students < 1:
            raise ValueError
    except ValueError:
        await message.answer("❌ Please enter a valid positive number:")
        return

    await state.update_data(plan_max_students=max_students)

    await message.answer("Enter maximum number of teachers allowed:", reply_markup=get_cancel_keyboard())
    await state.set_state(CreatePlanStates.waiting_for_max_teachers)

@router.message(CreatePlanStates.waiting_for_max_teachers, F.text)
async def process_max_teachers(message: Message, state: FSMContext):
    """Process max teachers"""
    try:
        max_teachers = int(message.text.strip())
        if max_teachers < 1:
            raise ValueError
    except ValueError:
        await message.answer("❌ Please enter a valid positive number:")
        return

    await state.update_data(plan_max_teachers=max_teachers)

    await message.answer("Enter maximum number of classes allowed:", reply_markup=get_cancel_keyboard())
    await state.set_state(CreatePlanStates.waiting_for_max_classes)

@router.message(CreatePlanStates.waiting_for_max_classes, F.text)
async def process_max_classes(message: Message, state: FSMContext):
    """Process max classes"""
    try:
        max_classes = int(message.text.strip())
        if max_classes < 1:
            raise ValueError
    except ValueError:
        await message.answer("❌ Please enter a valid positive number:")
        return

    await state.update_data(plan_max_classes=max_classes)

    await message.answer(
        "Enter monthly price (USD, e.g., 29.99):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreatePlanStates.waiting_for_price_monthly)

@router.message(CreatePlanStates.waiting_for_price_monthly, F.text)
async def process_price_monthly(message: Message, state: FSMContext):
    """Process monthly price"""
    try:
        price_monthly = float(message.text.strip())
        if price_monthly < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Please enter a valid price (e.g., 29.99):")
        return

    await state.update_data(plan_price_monthly=price_monthly)

    await message.answer(
        "Enter yearly price (USD, e.g., 299.99):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreatePlanStates.waiting_for_price_yearly)

@router.message(CreatePlanStates.waiting_for_price_yearly, F.text)
async def process_price_yearly(message: Message, state: FSMContext):
    """Process yearly price"""
    try:
        price_yearly = float(message.text.strip())
        if price_yearly < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Please enter a valid price (e.g., 299.99):")
        return

    await state.update_data(plan_price_yearly=price_yearly)

    await message.answer(
        "Enter trial period (days, 0 for no trial):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreatePlanStates.waiting_for_trial_days)

@router.message(CreatePlanStates.waiting_for_trial_days, F.text)
async def process_trial_days(message: Message, state: FSMContext):
    """Process trial days"""
    try:
        trial_days = int(message.text.strip())
        if trial_days < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Please enter a valid number (0 or more):")
        return

    await state.update_data(plan_trial_days=trial_days)

    # Feature selection
    all_features = [
        "attendance", "homework", "quizzes", "competitions",
        "leaderboard", "payments", "speaking_partner", "achievements",
        "parent_dashboard", "reports", "custom_branding", "api_access"
    ]

    buttons = []
    for feature in all_features:
        buttons.append([InlineKeyboardButton(
            text=f"☐ {feature.replace('_', ' ').title()}",
            callback_data=f"feature_toggle_{feature}"
        )])
    buttons.append([InlineKeyboardButton(text="✅ Done", callback_data="features_done")])

    await state.update_data(selected_features=[], all_features=all_features)

    await message.answer(
        "Select features included in this plan (toggle on/off):\n\n"
        "Selected features will be marked with ☑",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(CreatePlanStates.waiting_for_features)

@router.callback_query(CreatePlanStates.waiting_for_features, F.data.startswith("feature_toggle_"))
async def toggle_feature(callback: CallbackQuery, state: FSMContext):
    """Toggle a feature selection"""
    feature = callback.data.replace("feature_toggle_", "")
    data = await state.get_data()
    selected = data.get('selected_features', [])
    all_features = data.get('all_features', [])

    if feature in selected:
        selected.remove(feature)
    else:
        selected.append(feature)

    await state.update_data(selected_features=selected)

    # Rebuild keyboard with updated selections
    buttons = []
    for feat in all_features:
        prefix = "☑" if feat in selected else "☐"
        buttons.append([InlineKeyboardButton(
            text=f"{prefix} {feat.replace('_', ' ').title()}",
            callback_data=f"feature_toggle_{feat}"
        )])
    buttons.append([InlineKeyboardButton(text="✅ Done", callback_data="features_done")])

    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(CreatePlanStates.waiting_for_features, F.data == "features_done")
async def finish_feature_selection(callback: CallbackQuery, state: FSMContext):
    """Finish feature selection and show confirmation"""
    data = await state.get_data()

    text = "📋 **Confirm Plan Creation**\n\n"
    text += f"📛 **Name:** {data['plan_name']}\n"
    text += f"🔗 **Slug:** {data['plan_slug']}\n"
    text += f"📄 **Description:** {data['plan_description']}\n"
    text += f"👥 **Max Students:** {data['plan_max_students']}\n"
    text += f"👨‍🏫 **Max Teachers:** {data['plan_max_teachers']}\n"
    text += f"🏫 **Max Classes:** {data['plan_max_classes']}\n"
    text += f"💰 **Monthly:** ${data['plan_price_monthly']}\n"
    text += f"💰 **Yearly:** ${data['plan_price_yearly']}\n"
    text += f"⏳ **Trial:** {data['plan_trial_days']} days\n"
    text += f"\n**Features:** {', '.join(data['selected_features'])}\n\n"
    text += "Create this plan?"

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Create", callback_data="confirm_create_plan"),
                InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")
            ]
        ])
    )
    await state.set_state(CreatePlanStates.confirm_creation)

@router.callback_query(CreatePlanStates.confirm_creation, F.data == "confirm_create_plan")
async def confirm_create_plan(callback: CallbackQuery, state: FSMContext):
    """Finalize plan creation"""
    data = await state.get_data()

    plan_id = await db.create_subscription_plan(
        name=data['plan_name'],
        slug=data['plan_slug'],
        description=data['plan_description'],
        max_students=data['plan_max_students'],
        max_teachers=data['plan_max_teachers'],
        max_classes=data['plan_max_classes'],
        price_monthly=data['plan_price_monthly'],
        price_yearly=data['plan_price_yearly'],
        trial_days=data['plan_trial_days'],
        features=json.dumps(data['selected_features'])
    )

    if plan_id:
        # Log audit
        await db.log_audit(
            user_id=callback.from_user.id,
            action='create_plan',
            entity_type='subscription_plan',
            entity_id=plan_id,
            new_values={'name': data['plan_name'], 'slug': data['plan_slug']}
        )

        await callback.message.edit_text(
            f"✅ **Plan Created Successfully!**\n\n"
            f"📛 {data['plan_name']} (ID: {plan_id})",
            reply_markup=get_back_keyboard("sa_list_plans")
        )
    else:
        await callback.message.edit_text(
            "❌ Failed to create plan.",
            reply_markup=get_back_keyboard("sa_back")
        )

    await state.clear()

# ========================
# VIEW ALL SUBSCRIPTIONS
# ========================

@router.callback_query(F.data == "sa_list_subscriptions")
async def list_all_subscriptions(callback: CallbackQuery, state: FSMContext):
    """List all center subscriptions"""
    centers = await db.get_all_centers(include_suspended=True)

    if not centers:
        await callback.message.edit_text(
            "No centers with subscriptions found.",
            reply_markup=get_back_keyboard("sa_back")
        )
        return

    text = "📋 **All Center Subscriptions**\n\n"
    buttons = []

    for center in centers:
        status = "🟢" if center['is_active'] and not center['is_suspended'] else "🔴"
        plan = center.get('subscription_plan', 'basic').title()
        expires = center.get('plan_expires_at', 'N/A')
        if expires != 'N/A':
            expires = expires[:10] if isinstance(expires, str) else str(expires)[:10]

        text += f"{status} **{center['name']}**\n"
        text += f"   Plan: {plan} | Expires: {expires}\n\n"

        buttons.append([InlineKeyboardButton(
            text=f"💰 Manage {center['name']}",
            callback_data=f"sa_center_subscription_{center['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ========================
# MANAGE CENTER SUBSCRIPTION
# ========================

@router.callback_query(F.data.startswith("sa_center_subscription_"))
async def manage_center_subscription(callback: CallbackQuery, state: FSMContext):
    """Manage subscription for a specific center"""
    center_id = int(callback.data.replace("sa_center_subscription_", ""))
    center = await db.get_center_by_id(center_id)

    if not center:
        await callback.answer("Center not found", show_alert=True)
        return

    await state.update_data(sub_center_id=center_id, sub_center=center)

    text = f"💰 **Manage Subscription: {center['name']}**\n\n"
    text += f"Current Plan: **{center.get('subscription_plan', 'basic').title()}**\n"
    text += f"Expires: **{center.get('plan_expires_at', 'N/A')}**\n\n"
    text += "Select action:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Change Plan", callback_data="sa_change_center_plan")],
        [InlineKeyboardButton(text="📅 Extend Subscription", callback_data="sa_extend_subscription")],
        [InlineKeyboardButton(text="⏸️ Cancel Subscription", callback_data="sa_cancel_subscription")],
        [InlineKeyboardButton(text="💰 Record Payment", callback_data="sa_record_payment")],
        [InlineKeyboardButton(text="📋 View Invoices", callback_data="sa_view_invoices")],
        [InlineKeyboardButton(text="🔙 Back", callback_data=f"sa_center_detail_{center_id}")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

@router.callback_query(F.data == "sa_change_center_plan")
async def change_center_plan_start(callback: CallbackQuery, state: FSMContext):
    """Start changing a center's plan"""
    plans = await db.get_all_subscription_plans()

    buttons = []
    for plan in plans:
        buttons.append([InlineKeyboardButton(
            text=f"{plan['name']} - ${plan['price_monthly']}/mo",
            callback_data=f"assign_plan_{plan['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")])

    await callback.message.edit_text(
        "Select new plan:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

@router.callback_query(F.data.startswith("assign_plan_"))
async def assign_plan_to_center(callback: CallbackQuery, state: FSMContext):
    """Assign a plan to the center"""
    plan_id = int(callback.data.replace("assign_plan_", ""))
    data = await state.get_data()
    center_id = data['sub_center_id']

    # Get plan details
    plan = await db.get_subscription_plan_by_id(plan_id)
    if not plan:
        await callback.answer("Plan not found", show_alert=True)
        return

    # Update center subscription
    await db.update_center_subscription(
        center_id=center_id,
        plan_slug=plan['slug'],
        max_students=plan['max_students'],
        max_teachers=plan['max_teachers'],
        max_classes=plan['max_classes']
    )

    # Create invoice
    await db.create_subscription_invoice(
        center_id=center_id,
        plan_id=plan_id,
        amount=plan['price_monthly'],
        period='monthly',
        start_date=datetime.now(),
        end_date=datetime.now() + timedelta(days=30)
    )

    # Log audit
    await db.log_audit(
        user_id=callback.from_user.id,
        action='change_center_plan',
        entity_type='center',
        entity_id=center_id,
        old_values={'plan': data.get('sub_center', {}).get('subscription_plan')},
        new_values={'plan': plan['slug']}
    )

    await callback.message.edit_text(
        f"✅ Subscription updated!\n\n"
        f"Center now on **{plan['name']}** plan\n"
        f"Monthly: ${plan['price_monthly']}",
        reply_markup=get_back_keyboard(f"sa_center_subscription_{center_id}")
    )

@router.callback_query(F.data == "sa_extend_subscription")
async def extend_subscription_start(callback: CallbackQuery, state: FSMContext):
    """Start extending a subscription"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 +1 Month", callback_data="extend_30")],
        [InlineKeyboardButton(text="📅 +3 Months", callback_data="extend_90")],
        [InlineKeyboardButton(text="📅 +6 Months", callback_data="extend_180")],
        [InlineKeyboardButton(text="📅 +1 Year", callback_data="extend_365")],
        [InlineKeyboardButton(text="📅 Custom Days", callback_data="extend_custom")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(
        "Select extension period:",
        reply_markup=keyboard
    )

@router.callback_query(F.data.startswith("extend_"))
async def extend_subscription(callback: CallbackQuery, state: FSMContext):
    """Process subscription extension"""
    period = callback.data.replace("extend_", "")
    data = await state.get_data()
    center_id = data['sub_center_id']

    if period == "custom":
        await callback.message.edit_text(
            "Enter number of days to extend:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state("custom_extension")
        return

    days = int(period)
    center = await db.get_center_by_id(center_id)

    if center and center.get('plan_expires_at'):
        current_expiry = datetime.fromisoformat(center['plan_expires_at']) if isinstance(center['plan_expires_at'], str) else center['plan_expires_at']
    else:
        current_expiry = datetime.now()

    new_expiry = current_expiry + timedelta(days=days)

    await db.update_center_expiry(center_id, new_expiry)

    # Log audit
    await db.log_audit(
        user_id=callback.from_user.id,
        action='extend_subscription',
        entity_type='center',
        entity_id=center_id,
        new_values={'days_added': days, 'new_expiry': new_expiry.isoformat()}
    )

    await callback.message.edit_text(
        f"✅ Subscription extended by {days} days!\n\n"
        f"New expiry: {new_expiry.strftime('%Y-%m-%d')}",
        reply_markup=get_back_keyboard(f"sa_center_subscription_{center_id}")
    )

# ========================
# REVENUE REPORT
# ========================

@router.callback_query(F.data == "sa_revenue_report")
async def show_revenue_report(callback: CallbackQuery, state: FSMContext):
    """Show platform revenue report"""
    # Get all payments
    async with db.get_db() as conn:
        # Total revenue
        cursor = await conn.execute("SELECT COALESCE(SUM(amount), 0) FROM payments")
        total_revenue = (await cursor.fetchone())[0]

        # This month revenue
        start_of_month = datetime.now().replace(day=1).strftime('%Y-%m-%d')
        cursor = await conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE payment_date >= ?",
            (start_of_month,)
        )
        month_revenue = (await cursor.fetchone())[0]

        # This year revenue
        start_of_year = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')
        cursor = await conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE payment_date >= ?",
            (start_of_year,)
        )
        year_revenue = (await cursor.fetchone())[0]

        # Revenue by center
        cursor = await conn.execute("""
            SELECT c.name, COALESCE(SUM(p.amount), 0) as revenue
            FROM centers c
            LEFT JOIN payments p ON c.id = p.center_id
            GROUP BY c.id
            ORDER BY revenue DESC
        """)
        center_revenues = [dict(row) for row in await cursor.fetchall()]

    text = "💰 **Platform Revenue Report**\n\n"
    text += f"📊 **Total Revenue:** {total_revenue:,.0f} UZS\n"
    text += f"📅 **This Month:** {month_revenue:,.0f} UZS\n"
    text += f"📆 **This Year:** {year_revenue:,.0f} UZS\n\n"
    text += "**Revenue by Center:**\n"

    for cr in center_revenues[:10]:
        text += f"• {cr['name']}: {cr['revenue']:,.0f} UZS\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Export Report", callback_data="sa_export_revenue")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="sa_back")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
