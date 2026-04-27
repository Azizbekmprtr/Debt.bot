# handlers/super_admin/__init__.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from .centers import router as centers_router
from .subscriptions import router as subscriptions_router
from .users import router as users_router
from .analytics import router as analytics_router
from .support import router as support_router
from .system import router as system_router
from .security import router as security_router
from .backup import router as backup_router

router = Router()
router.include_router(centers_router)
router.include_router(subscriptions_router)
router.include_router(users_router)
router.include_router(analytics_router)
router.include_router(support_router)
router.include_router(system_router)
router.include_router(security_router)
router.include_router(backup_router)

__all__ = ['router']
