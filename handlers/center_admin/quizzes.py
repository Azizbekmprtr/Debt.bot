# handlers/center_admin/quizzes.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import database.queries as db
from keyboards.all_keyboards import (
    get_center_admin_main_menu, get_cancel_keyboard,
    get_confirm_keyboard, get_back_keyboard,
    get_question_type_keyboard
)
import json

router = Router()

# ========================
# QUIZ MANAGEMENT STATES
# ========================

class CreateQuizStates(StatesGroup):
    selecting_unit = State()
    entering_title = State()
    selecting_type = State()
    entering_description = State()
    entering_passing_score = State()
    entering_time_limit = State()
    entering_max_attempts = State()
    confirm = State()

class AddQuestionStates(StatesGroup):
    selecting_quiz = State()
    selecting_type = State()
    entering_text = State()
    entering_points = State()
    entering_options = State()
    entering_correct_answer = State()
    entering_explanation = State()
    confirm = State()

class EditQuestionStates(StatesGroup):
    selecting_question = State()
    selecting_field = State()
    entering_value = State()

# ========================
# HELPER
# ========================

async def get_center_context(state: FSMContext) -> dict:
    data = await state.get_data()
    center_id = data.get('current_center_id')
    center = await db.get_center_by_id(center_id) if center_id else None
    return {'center_id': center_id, 'center': center}

# ========================
# QUIZZES MAIN MENU
# ========================

@router.message(F.text == "📝 Quizzes")
async def quizzes_main_menu(message: Message, state: FSMContext):
    """Show quizzes management main menu"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT COUNT(*) FROM quizzes q
            JOIN units u ON q.unit_id = u.id
            JOIN classes c ON u.class_id = c.id
            WHERE c.center_id = ? AND q.is_active = 1
        """, (center_id,))
        quiz_count = (await cursor.fetchone())[0]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Create Quiz", callback_data="ca_create_quiz")],
        [InlineKeyboardButton(text="📋 View All Quizzes", callback_data="ca_list_quizzes")],
        [InlineKeyboardButton(text="➕ Add Question", callback_data="ca_add_question")],
        [InlineKeyboardButton(text="✏️ Edit Question", callback_data="ca_edit_question")],
        [InlineKeyboardButton(text="📊 View Results", callback_data="ca_quiz_results")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")]
    ])

    text = "📝 **Quiz Management**\n\n"
    text += f"📊 Total Active Quizzes: **{quiz_count}**\n\n"
    text += "Create and manage quizzes, questions, and view results."

    await message.answer(text, reply_markup=keyboard)

# ========================
# CREATE QUIZ
# ========================

@router.callback_query(F.data == "ca_create_quiz")
async def create_quiz_start(callback: CallbackQuery, state: FSMContext):
    """Start creating a new quiz"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    # Get all units for this center
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT u.*, c.name as class_name, c.level
            FROM units u
            JOIN classes c ON u.class_id = c.id
            WHERE c.center_id = ? AND u.is_active = 1
            ORDER BY c.name, u.unit_number
        """, (center_id,))
        units = [dict(row) for row in await cursor.fetchall()]

    if not units:
        await callback.message.edit_text(
            "❌ No units found. Create units first.",
            reply_markup=get_back_keyboard("ca_back")
        )
        return

    buttons = []
    for unit in units:
        buttons.append([InlineKeyboardButton(
            text=f"{unit['class_name']} - Unit {unit['unit_number']}: {unit['title'][:30]}",
            callback_data=f"quiz_unit_{unit['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")])

    await callback.message.edit_text(
        "📝 **Create New Quiz**\n\n"
        "Select the unit for this quiz:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(CreateQuizStates.selecting_unit)

@router.callback_query(CreateQuizStates.selecting_unit, F.data.startswith("quiz_unit_"))
async def process_quiz_unit(callback: CallbackQuery, state: FSMContext):
    """Process unit selection"""
    unit_id = int(callback.data.replace("quiz_unit_", ""))
    await state.update_data(quiz_unit_id=unit_id)

    await callback.message.edit_text(
        "Enter quiz title:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateQuizStates.entering_title)

@router.message(CreateQuizStates.entering_title, F.text)
async def process_quiz_title(message: Message, state: FSMContext):
    """Process quiz title"""
    title = message.text.strip()
    if len(title) < 2 or len(title) > 200:
        await message.answer("❌ Title must be between 2 and 200 characters.")
        return

    await state.update_data(quiz_title=title)

    await message.answer(
        f"✅ Title: **{title}**\n\n"
        "Select quiz type:",
        reply_markup=get_question_type_keyboard()
    )
    await state.set_state(CreateQuizStates.selecting_type)

@router.callback_query(CreateQuizStates.selecting_type, F.data.startswith("qtype_"))
async def process_quiz_type(callback: CallbackQuery, state: FSMContext):
    """Process quiz type"""
    quiz_type = callback.data.replace("qtype_", "")

    type_names = {
        'mcq': 'Multiple Choice',
        'short_answer': 'Short Answer',
        'fill_gap': 'Fill in the Gap',
        'listening': 'Listening',
        'sentence_building': 'Sentence Building',
        'error_detection': 'Error Detection',
        'matching_pairs': 'Matching Pairs'
    }

    await state.update_data(quiz_type=quiz_type)

    await callback.message.edit_text(
        f"✅ Type: **{type_names.get(quiz_type, quiz_type)}**\n\n"
        "Enter description (optional, type 'skip'):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateQuizStates.entering_description)

@router.message(CreateQuizStates.entering_description, F.text)
async def process_quiz_description(message: Message, state: FSMContext):
    """Process quiz description"""
    desc = message.text.strip()
    if desc.lower() == 'skip':
        desc = None

    await state.update_data(quiz_description=desc)

    await message.answer(
        "Enter passing score percentage (e.g., 60 for 60%):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateQuizStates.entering_passing_score)

@router.message(CreateQuizStates.entering_passing_score, F.text)
async def process_quiz_passing_score(message: Message, state: FSMContext):
    """Process passing score"""
    try:
        score = int(message.text.strip())
        if score < 0 or score > 100:
            raise ValueError
    except ValueError:
        await message.answer("❌ Enter a number between 0 and 100:")
        return

    await state.update_data(quiz_passing_score=score)

    await message.answer(
        "Enter time limit in minutes (0 for no limit):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateQuizStates.entering_time_limit)

@router.message(CreateQuizStates.entering_time_limit, F.text)
async def process_quiz_time_limit(message: Message, state: FSMContext):
    """Process time limit"""
    try:
        time_limit = int(message.text.strip())
        if time_limit < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Enter 0 or a positive number:")
        return

    await state.update_data(quiz_time_limit=time_limit if time_limit > 0 else None)

    await message.answer(
        "Enter maximum attempts allowed (1-10):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(CreateQuizStates.entering_max_attempts)

@router.message(CreateQuizStates.entering_max_attempts, F.text)
async def process_quiz_max_attempts(message: Message, state: FSMContext):
    """Process max attempts and confirm"""
    try:
        max_attempts = int(message.text.strip())
        if max_attempts < 1 or max_attempts > 10:
            raise ValueError
    except ValueError:
        await message.answer("❌ Enter a number between 1 and 10:")
        return

    data = await state.get_data()

    type_names = {
        'mcq': 'Multiple Choice',
        'short_answer': 'Short Answer',
        'fill_gap': 'Fill in the Gap',
        'listening': 'Listening',
        'sentence_building': 'Sentence Building',
        'error_detection': 'Error Detection',
        'matching_pairs': 'Matching Pairs'
    }

    text = "📝 **Confirm Quiz Creation**\n\n"
    text += f"📌 **Title:** {data['quiz_title']}\n"
    text += f"📋 **Type:** {type_names.get(data['quiz_type'], data['quiz_type'])}\n"
    if data.get('quiz_description'):
        text += f"📄 **Description:** {data['quiz_description']}\n"
    text += f"✅ **Passing Score:** {data['quiz_passing_score']}%\n"
    text += f"⏱️ **Time Limit:** {data.get('quiz_time_limit', 'No limit')} min\n"
    text += f"🔄 **Max Attempts:** {max_attempts}\n"
    text += "\nCreate this quiz?"

    await state.update_data(quiz_max_attempts=max_attempts)

    await message.answer(text, reply_markup=get_confirm_keyboard("confirm_create_quiz", "cancel"))
    await state.set_state(CreateQuizStates.confirm)

@router.callback_query(CreateQuizStates.confirm, F.data == "confirm_create_quiz")
async def confirm_create_quiz(callback: CallbackQuery, state: FSMContext):
    """Finalize quiz creation"""
    data = await state.get_data()

    quiz_id = await db.create_quiz(
        unit_id=data['quiz_unit_id'],
        title=data['quiz_title'],
        quiz_type=data['quiz_type'],
        description=data.get('quiz_description'),
        passing_score=data['quiz_passing_score'],
        time_limit_minutes=data.get('quiz_time_limit'),
        max_attempts=data['quiz_max_attempts'],
        created_by=callback.from_user.id
    )

    if quiz_id:
        await db.log_audit(
            user_id=callback.from_user.id,
            action='create_quiz',
            entity_type='quiz',
            entity_id=quiz_id,
            new_values={'title': data['quiz_title'], 'type': data['quiz_type']}
        )

        await callback.message.edit_text(
            f"✅ **Quiz Created!**\n\n"
            f"📌 {data['quiz_title']}\n"
            f"🆔 ID: {quiz_id}\n\n"
            "Now add questions to this quiz!",
            reply_markup=get_back_keyboard("ca_add_question")
        )
    else:
        await callback.message.edit_text(
            "❌ Failed to create quiz.",
            reply_markup=get_back_keyboard("ca_back")
        )

    await state.clear()

# ========================
# ADD QUESTION TO QUIZ
# ========================

@router.callback_query(F.data == "ca_add_question")
async def add_question_start(callback: CallbackQuery, state: FSMContext):
    """Start adding a question to a quiz"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    # Get all quizzes for this center
    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT q.*, u.title as unit_title, u.unit_number, c.name as class_name
            FROM quizzes q
            JOIN units u ON q.unit_id = u.id
            JOIN classes c ON u.class_id = c.id
            WHERE c.center_id = ? AND q.is_active = 1
            ORDER BY c.name, u.unit_number
        """, (center_id,))
        quizzes = [dict(row) for row in await cursor.fetchall()]

    if not quizzes:
        await callback.message.edit_text(
            "❌ No quizzes found. Create a quiz first.",
            reply_markup=get_back_keyboard("ca_back")
        )
        return

    buttons = []
    for quiz in quizzes:
        buttons.append([InlineKeyboardButton(
            text=f"{quiz['class_name']} - {quiz['title'][:40]}",
            callback_data=f"addq_quiz_{quiz['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")])

    await callback.message.edit_text(
        "➕ **Add Question**\n\n"
        "Select quiz to add question to:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await state.set_state(AddQuestionStates.selecting_quiz)

@router.callback_query(AddQuestionStates.selecting_quiz, F.data.startswith("addq_quiz_"))
async def process_addq_quiz(callback: CallbackQuery, state: FSMContext):
    """Process quiz selection for question"""
    quiz_id = int(callback.data.replace("addq_quiz_", ""))
    quiz = await db.get_quiz_by_id(quiz_id)

    await state.update_data(addq_quiz_id=quiz_id, addq_quiz_type=quiz['quiz_type'])

    # If quiz has a specific type, use that; otherwise ask
    if quiz['quiz_type']:
        await process_question_type(quiz['quiz_type'], callback, state)
    else:
        await callback.message.edit_text(
            "Select question type:",
            reply_markup=get_question_type_keyboard()
        )
        await state.set_state(AddQuestionStates.selecting_type)

@router.callback_query(AddQuestionStates.selecting_type, F.data.startswith("qtype_"))
async def process_addq_type(callback: CallbackQuery, state: FSMContext):
    """Process question type"""
    qtype = callback.data.replace("qtype_", "")
    await process_question_type(qtype, callback, state)

async def process_question_type(qtype: str, callback: CallbackQuery, state: FSMContext):
    """Process question type and ask for text"""
    await state.update_data(addq_type=qtype)

    await callback.message.edit_text(
        "Enter the question text:",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AddQuestionStates.entering_text)

@router.message(AddQuestionStates.entering_text, F.text)
async def process_question_text(message: Message, state: FSMContext):
    """Process question text"""
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("❌ Question text must be at least 5 characters.")
        return

    await state.update_data(addq_text=text)

    await message.answer(
        "Enter points for this question (default: 1):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AddQuestionStates.entering_points)

@router.message(AddQuestionStates.entering_points, F.text)
async def process_question_points(message: Message, state: FSMContext):
    """Process question points"""
    try:
        points = int(message.text.strip())
        if points < 1:
            raise ValueError
    except ValueError:
        await message.answer("❌ Enter a positive number:")
        return

    data = await state.get_data()
    qtype = data.get('addq_type', 'mcq')

    await state.update_data(addq_points=points)

    if qtype == 'mcq':
        await message.answer(
            "Enter answer options. Format:\n"
            "`A) Option text`\n"
            "`B) Option text`\n"
            "`C) Option text`\n"
            "`D) Option text`\n\n"
            "Mark the correct answer with * at the beginning:\n"
            "`*A) Correct option`\n\n"
            "Enter options:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(AddQuestionStates.entering_options)
    elif qtype in ['short_answer', 'fill_gap']:
        await message.answer(
            "Enter the correct answer:",
            reply_markup=get_cancel_keyboard()
        )
        await state.set_state(AddQuestionStates.entering_correct_answer)
    else:
        # For other types, save and confirm
        await save_question_and_confirm(message, state)

@router.message(AddQuestionStates.entering_options, F.text)
async def process_question_options(message: Message, state: FSMContext):
    """Process MCQ options"""
    lines = message.text.strip().split('\n')
    options = []
    correct_index = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        is_correct = line.startswith('*')
        if is_correct:
            line = line[1:].strip()

        # Extract option letter and text
        if ')' in line:
            parts = line.split(')', 1)
            option_text = parts[1].strip()
        else:
            option_text = line

        options.append(option_text)
        if is_correct:
            correct_index = len(options) - 1

    if len(options) < 2:
        await message.answer("❌ Please provide at least 2 options.")
        return

    if correct_index is None:
        await message.answer("❌ Please mark the correct answer with *")
        return

    await state.update_data(addq_options=options, addq_correct_index=correct_index)

    await message.answer(
        "Enter explanation for the correct answer (optional, type 'skip'):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AddQuestionStates.entering_explanation)

@router.message(AddQuestionStates.entering_correct_answer, F.text)
async def process_correct_answer(message: Message, state: FSMContext):
    """Process correct answer"""
    answer = message.text.strip()
    await state.update_data(addq_correct_answer=answer)

    await message.answer(
        "Enter explanation (optional, type 'skip'):",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AddQuestionStates.entering_explanation)

@router.message(AddQuestionStates.entering_explanation, F.text)
async def process_question_explanation(message: Message, state: FSMContext):
    """Process explanation and save"""
    explanation = message.text.strip()
    if explanation.lower() == 'skip':
        explanation = None

    await state.update_data(addq_explanation=explanation)
    await save_question_and_confirm(message, state)

async def save_question_and_confirm(message: Message, state: FSMContext):
    """Save question and show confirmation"""
    data = await state.get_data()

    # Add question to database
    question_id = await db.add_quiz_question(
        quiz_id=data['addq_quiz_id'],
        question_type=data.get('addq_type', 'mcq'),
        question_text=data['addq_text'],
        points=data.get('addq_points', 1),
        order_number=1,
        explanation=data.get('addq_explanation')
    )

    # Add options if MCQ
    if data.get('addq_type') == 'mcq' and data.get('addq_options'):
        for i, opt_text in enumerate(data['addq_options']):
            is_correct = (i == data.get('addq_correct_index'))
            await db.add_question_option(question_id, opt_text, is_correct, i)

    # Add fill gap answer
    if data.get('addq_type') == 'fill_gap' and data.get('addq_correct_answer'):
        await db.set_fill_answer(question_id, data['addq_correct_answer'])

    await message.answer(
        f"✅ Question added to quiz! (ID: {question_id})\n\n"
        "Add another question?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add Another", callback_data="ca_add_question")],
            [InlineKeyboardButton(text="📋 View Quiz", callback_data=f"ca_view_quiz_{data['addq_quiz_id']}")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")]
        ])
    )
    await state.clear()

# ========================
# VIEW QUIZ WITH QUESTIONS
# ========================

@router.callback_query(F.data.startswith("ca_view_quiz_"))
async def view_quiz_with_questions(callback: CallbackQuery, state: FSMContext):
    """View quiz with all questions"""
    quiz_id = int(callback.data.replace("ca_view_quiz_", ""))
    quiz = await db.get_quiz_with_questions(quiz_id)

    if not quiz:
        await callback.answer("Quiz not found", show_alert=True)
        return

    text = f"📝 **{quiz['title']}**\n\n"
    text += f"📋 Type: {quiz['quiz_type']}\n"
    text += f"✅ Passing: {quiz['passing_score']}%\n"
    text += f"🔄 Max Attempts: {quiz['max_attempts']}\n\n"

    questions = quiz.get('questions', [])
    text += f"📊 **Questions ({len(questions)}):**\n\n"

    for i, q in enumerate(questions, 1):
        text += f"**Q{i}.** ({q['points']} pts) {q['question_text'][:100]}\n"

        if q.get('options'):
            for opt in q['options']:
                correct = "✅" if opt.get('is_correct') else "  "
                text += f"  {correct} {opt['option_text'][:40]}\n"

        if q.get('fill_answer'):
            text += f"  Answer: {q['fill_answer']['correct_answer']}\n"

        text += "\n"

    # Action buttons
    buttons = []
    for q in questions:
        buttons.append([InlineKeyboardButton(
            text=f"✏️ Edit Q{i}",
            callback_data=f"ca_edit_question_{q['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="➕ Add Question", callback_data="ca_add_question")])
    buttons.append([InlineKeyboardButton(text="🗑️ Delete Quiz", callback_data=f"ca_delete_quiz_{quiz_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_list_quizzes")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ========================
# VIEW QUIZ RESULTS
# ========================

@router.callback_query(F.data == "ca_quiz_results")
async def view_quiz_results_start(callback: CallbackQuery, state: FSMContext):
    """Start viewing quiz results"""
    ctx = await get_center_context(state)
    center_id = ctx['center_id']

    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT q.*, u.title as unit_title, u.unit_number, c.name as class_name,
                   COUNT(DISTINCT qa.id) as attempt_count,
                   COUNT(DISTINCT CASE WHEN qa.passed = 1 THEN qa.student_id END) as passed_count
            FROM quizzes q
            JOIN units u ON q.unit_id = u.id
            JOIN classes c ON u.class_id = c.id
            LEFT JOIN quiz_attempts qa ON q.id = qa.quiz_id
            WHERE c.center_id = ?
            GROUP BY q.id
            ORDER BY c.name, u.unit_number
        """, (center_id,))
        quizzes = [dict(row) for row in await cursor.fetchall()]

    if not quizzes:
        await callback.message.edit_text(
            "📊 No quizzes with attempts found.",
            reply_markup=get_back_keyboard("ca_back")
        )
        return

    text = "📊 **Quiz Results**\n\n"
    buttons = []

    for quiz in quizzes:
        pass_rate = (quiz['passed_count'] / quiz['attempt_count'] * 100) if quiz['attempt_count'] > 0 else 0
        text += f"**{quiz['title']}** ({quiz['class_name']})\n"
        text += f"  Attempts: {quiz['attempt_count']} | Pass Rate: {pass_rate:.1f}%\n\n"

        buttons.append([InlineKeyboardButton(
            text=f"📊 {quiz['title'][:40]}",
            callback_data=f"ca_quiz_detail_results_{quiz['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="ca_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("ca_quiz_detail_results_"))
async def view_quiz_detail_results(callback: CallbackQuery, state: FSMContext):
    """View detailed results for a quiz"""
    quiz_id = int(callback.data.replace("ca_quiz_detail_results_", ""))

    async with db.get_db() as conn:
        cursor = await conn.execute("""
            SELECT qa.*, u.full_name,
                   ROUND(CAST(qa.score AS FLOAT) / CAST(qa.max_score AS FLOAT) * 100, 1) as percentage
            FROM quiz_attempts qa
            JOIN users u ON qa.student_id = u.id
            WHERE qa.quiz_id = ? AND qa.completed_at IS NOT NULL
            ORDER BY qa.completed_at DESC
            LIMIT 50
        """, (quiz_id,))
        results = [dict(row) for row in await cursor.fetchall()]

    quiz = await db.get_quiz_by_id(quiz_id)

    text = f"📊 **Results: {quiz['title']}**\n\n"

    if results:
        for result in results:
            passed = "✅" if result.get('passed') else "❌"
            text += f"{passed} **{result['full_name']}**\n"
            text += f"  Score: {result['score']}/{result['max_score']} ({result['percentage']}%)\n"
            text += f"  Attempt #{result['attempt_number']} | {result['completed_at'][:19]}\n\n"
    else:
        text += "No attempts yet.\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Export Results", callback_data=f"ca_export_results_{quiz_id}")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="ca_quiz_results")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
