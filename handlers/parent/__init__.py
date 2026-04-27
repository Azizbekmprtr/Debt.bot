# handlers/parent/__init__.py
from aiogram import Router
from .dashboard import router as dashboard_router
from .progress import router as progress_router
from .attendance import router as attendance_router
from .payments import router as payments_router
from .communication import router as communication_router
from .settings import router as settings_router

router = Router()
router.include_router(dashboard_router)
router.include_router(progress_router)
router.include_router(attendance_router)
router.include_router(payments_router)
router.include_router(communication_router)
router.include_router(settings_router)

__all__ = ['router']
