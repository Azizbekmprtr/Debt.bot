# handlers/student/quizzes.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import database.queries as db
from keyboards.all_keyboards import (
    get_student_main_menu, get_cancel_keyboard,
    get_back_keyboard, get_mcq_answer_keyboard
)

router = Router()

class QuizTakingStates(StatesGroup):
    in_progress = State()
    answer_pending = State()

async def get_student_context(state: FSMContext) -> dict:
    data = await state.get_data()
    telegram_id = data.get('telegram_id', 0)
    student = await db.get_user_by_telegram_id(telegram_id) if telegram_id else None
    return {'student': student, 'student_id': student['id'] if student else None}

@router.message(F.text == "📝 Quizzes")
async def quizzes_menu(message: Message, state: FSMContext):
    """Show available quizzes"""
    ctx = await get_student_context(state)
    student_id = ctx.get('student_id')

    if not student_id:
        await message.answer("❌ Student not found.")
        return

    # Get quizzes for student's classes
    classes = await db.get_classes_for_student(student_id)

    all_quizzes = []
    for cls in classes:
        quizzes = await db.get_quizzes_for_class(cls['id'])
        for quiz in quizzes:
            quiz['class_name'] = cls['name']
            all_quizzes.append(quiz)

    if not all_quizzes:
        await message.answer(
            "📝 No quizzes available yet.",
            reply_markup=get_student_main_menu()
        )
        return

    text = "📝 **Available Quizzes**\n\n"
    buttons = []

    for quiz in all_quizzes[:20]:
        text += f"**{quiz['title']}** ({quiz['class_name']})\n"
        text += f"  📋 Type: {quiz['quiz_type']}\n"

        # Check if already attempted
        attempts = await db.get_student_quiz_attempts(student_id, quiz['id'])
        if attempts:
            best_score = max(a.get('score', 0) for a in attempts)
            text += f"  📊 Best: {best_score} pts\n"

        text += "\n"

        buttons.append([InlineKeyboardButton(
            text=f"▶️ {quiz['title'][:40]}",
            callback_data=f"s_start_quiz_{quiz['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="🔙 Back", callback_data="s_back")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@router.callback_query(F.data.startswith("s_start_quiz_"))
async def start_quiz(callback: CallbackQuery, state: FSMContext):
    """Start taking a quiz"""
    quiz_id = int(callback.data.replace("s_start_quiz_", ""))
    ctx = await get_student_context(state)
    student_id = ctx['student_id']

    if not student_id:
        await callback.answer("Student not found", show_alert=True)
        return

    # Start attempt
    attempt_id = await db.start_quiz_attempt(quiz_id, student_id)

    if attempt_id == -1:
        await callback.answer("❌ Maximum attempts reached!", show_alert=True)
        return

    if not attempt_id:
        await callback.answer("❌ Failed to start quiz", show_alert=True)
        return

    # Get quiz with questions
    quiz = await db.get_quiz_with_questions(quiz_id)

    if not quiz or not quiz.get('questions'):
        await callback.answer("Quiz has no questions", show_alert=True)
        return

    await state.update_data(
        quiz_id=quiz_id,
        attempt_id=attempt_id,
        quiz_questions=quiz['questions'],
        current_question_index=0,
        quiz_answers={},
        quiz_points=0
    )

    await show_question(callback, state)

async def show_question(callback: CallbackQuery, state: FSMContext):
    """Show current question"""
    data = await state.get_data()
    questions = data['quiz_questions']
    current_index = data['current_question_index']

    if current_index >= len(questions):
        await finish_quiz(callback, state)
        return

    question = questions[current_index]
    total = len(questions)

    text = f"📝 **Question {current_index + 1}/{total}**\n\n"
    text += f"**{question['question_text']}**\n"
    text += f"Points: {question['points']}\n\n"

    if question['question_type'] == 'mcq' and question.get('options'):
        options = question['options']
        for i, opt in enumerate(options):
            letter = chr(65 + i)
            text += f"{letter}) {opt['option_text']}\n"

        await callback.message.edit_text(
            text,
            reply_markup=get_mcq_answer_keyboard(options, current_index, total)
        )
    elif question['question_type'] in ['short_answer', 'fill_gap']:
        text += "✍️ Type your answer:"
        await callback.message.edit_text(text, reply_markup=get_cancel_keyboard())
        await state.set_state(QuizTakingStates.answer_pending)
    else:
        # Other types - advance with skip
        await advance_to_next_question(callback, state)

@router.callback_query(F.data.startswith("mcq_answer_"))
async def handle_mcq_answer(callback: CallbackQuery, state: FSMContext):
    """Handle MCQ answer selection"""
    parts = callback.data.replace("mcq_answer_", "").split("_")
    option_id = int(parts[0])
    question_index = int(parts[1])

    data = await state.get_data()
    questions = data['quiz_questions']
    question = questions[question_index]
    attempt_id = data['attempt_id']

    # Submit answer
    is_correct, points = await db.submit_quiz_answer(
        attempt_id=attempt_id,
        question_id=question['id'],
        selected_option_id=option_id
    )

    # Update points
    answers = data.get('quiz_answers', {})
    answers[str(question['id'])] = {'option_id': option_id, 'correct': is_correct, 'points': points}

    total_points = data.get('quiz_points', 0) + points

    await state.update_data(
        quiz_answers=answers,
        quiz_points=total_points,
        current_question_index=question_index + 1
    )

    # Show feedback
    if is_correct:
        await callback.answer(f"✅ Correct! +{points} pts")
    else:
        await callback.answer(f"❌ Incorrect")

    await show_question(callback, state)

@router.message(QuizTakingStates.answer_pending, F.text)
async def handle_text_answer(message: Message, state: FSMContext):
    """Handle text/essay answer"""
    answer_text = message.text.strip()

    data = await state.get_data()
    questions = data['quiz_questions']
    current_index = data['current_question_index']
    question = questions[current_index]
    attempt_id = data['attempt_id']

    # Submit answer
    is_correct, points = await db.submit_quiz_answer(
        attempt_id=attempt_id,
        question_id=question['id'],
        answer_text=answer_text
    )

    answers = data.get('quiz_answers', {})
    answers[str(question['id'])] = {'text': answer_text, 'correct': is_correct, 'points': points}

    total_points = data.get('quiz_points', 0) + points

    await state.update_data(
        quiz_answers=answers,
        quiz_points=total_points,
        current_question_index=current_index + 1
    )

    if is_correct is not None:
        await message.answer(f"{'✅ Correct!' if is_correct else '❌ Incorrect'} +{points} pts")

    await state.set_state(QuizTakingStates.in_progress)
    await show_question_from_message(message, state)

async def show_question_from_message(message: Message, state: FSMContext):
    """Show question from text message context"""
    data = await state.get_data()
    questions = data['quiz_questions']
    current_index = data['current_question_index']

    if current_index >= len(questions):
        await finish_quiz_from_message(message, state)
        return

    question = questions[current_index]
    total = len(questions)

    text = f"📝 **Question {current_index + 1}/{total}**\n\n"
    text += f"**{question['question_text']}**\n"
    text += f"Points: {question['points']}\n\n"

    if question['question_type'] == 'mcq' and question.get('options'):
        options = question['options']
        for i, opt in enumerate(options):
            letter = chr(65 + i)
            text += f"{letter}) {opt['option_text']}\n"

        await message.answer(
            text,
            reply_markup=get_mcq_answer_keyboard(options, current_index, total)
        )
    else:
        text += "✍️ Type your answer:"
        await message.answer(text, reply_markup=get_cancel_keyboard())
        await state.set_state(QuizTakingStates.answer_pending)

@router.callback_query(F.data.startswith("skip_question_"))
async def advance_to_next_question(callback: CallbackQuery, state: FSMContext):
    """Skip current question"""
    data = await state.get_data()
    current_index = data['current_question_index']

    await state.update_data(current_question_index=current_index + 1)
    await show_question(callback, state)

async def finish_quiz(callback: CallbackQuery, state: FSMContext):
    """Finish quiz and show results"""
    data = await state.get_data()
    attempt_id = data['attempt_id']

    result = await db.complete_quiz_attempt(attempt_id)

    if not result:
        await callback.message.edit_text("❌ Error completing quiz.")
        await state.clear()
        return

    # Check and award achievements
    await db.check_and_award_badges(data.get('student_id'))

    text = "🎉 **Quiz Completed!**\n\n"
    text += f"📝 **{result['quiz_title']}**\n"
    text += f"📊 **Score:** {result['score']}/{result['max_score']}\n"
    text += f"📈 **Percentage:** {result['percentage']}%\n"
    text += f"{'✅ PASSED!' if result['passed'] else '❌ Not Passed'}\n"
    text += f"🏅 Passing: {result['passing_score']}%\n"
    text += f"🔄 Attempt: #{result['attempt_number']}\n\n"

    if result['passed']:
        text += "🎊 Congratulations! You passed the quiz!\n"
        text += "⭐ Points have been added to your account.\n"
    else:
        text += "💪 Keep studying and try again!\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 View All Quizzes", callback_data="s_back")],
        [InlineKeyboardButton(text="🏠 Main Menu", callback_data="s_main")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.clear()

async def finish_quiz_from_message(message: Message, state: FSMContext):
    """Finish quiz from message context"""
    data = await state.get_data()
    attempt_id = data['attempt_id']

    result = await db.complete_quiz_attempt(attempt_id)

    text = "🎉 **Quiz Completed!**\n\n"
    text += f"📊 **Score:** {result['score']}/{result['max_score']}\n"
    text += f"{'✅ PASSED!' if result['passed'] else '❌ Not Passed'}\n"

    await message.answer(text, reply_markup=get_student_main_menu())
    await state.clear()

@router.callback_query(F.data == "s_main")
async def back_to_student_main(callback: CallbackQuery, state: FSMContext):
    """Return to student main menu"""
    await callback.message.delete()
    await callback.message.answer(
        "🎓 Student Panel",
        reply_markup=get_student_main_menu()
    )
