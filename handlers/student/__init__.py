# handlers/student/__init__.py
from aiogram import Router
from .lessons import router as lessons_router
from .quizzes import router as quizzes_router
from .homework import router as homework_router
from .attendance import router as attendance_router
from .leaderboard import router as leaderboard_router
from .achievements import router as achievements_router
from .speaking import router as speaking_router
from .profile import router as profile_router
from .communication import router as communication_router

router = Router()
router.include_router(lessons_router)
router.include_router(quizzes_router)
router.include_router(homework_router)
router.include_router(attendance_router)
router.include_router(leaderboard_router)
router.include_router(achievements_router)
router.include_router(speaking_router)
router.include_router(profile_router)
router.include_router(communication_router)

__all__ = ['router']
