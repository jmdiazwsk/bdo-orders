from fastapi import APIRouter

router = APIRouter(prefix="/metrics")

@router.get("/")
async def metrics(window: str = "5m"):
    return {"count_orders": 0, "sum_amount": 0, "top_countries": []}
