from fastapi import APIRouter
from .health import router as health_router
from .orders import router as orders_router
from .metrics import router as metrics_router

router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(orders_router, tags=["orders"])
router.include_router(metrics_router, tags=["metrics"])