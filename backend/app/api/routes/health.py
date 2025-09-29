#C:\bdo-orders-platform\backend\app\api\routes\health.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_session

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)):
    """Health check endpoint"""
    try:
        # Verificar conectividad con la base de datos
        await session.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": "2025-09-28T19:36:35Z"  # o usar datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }