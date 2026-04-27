# handlers/center_admin/__init__.py
from aiogram import Router
from .users import router as users_router
from .classes import router as classes_router
from .units import router as units_router
from .quizzes import router as quizzes_router
from .homework import router as homework_router
from .attendance import router as attendance_router
from .payments import router as payments_router
from .competitions import router as competitions_router
from .communication import router as communication_router
from .reports import router as reports_router
from .settings import router as settings_router
from .support import router as support_router

router = Router()
router.include_router(users_router)
router.include_router(classes_router)
router.include_router(units_router)
router.include_router(quizzes_router)
router.include_router(homework_router)
router.include_router(attendance_router)
router.include_router(payments_router)
router.include_router(competitions_router)
router.include_router(communication_router)
router.include_router(reports_router)
router.include_router(settings_router)
router.include_router(support_router)

__all__ = ['router']
