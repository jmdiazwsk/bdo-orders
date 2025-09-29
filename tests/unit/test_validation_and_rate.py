# tests/unit/test_validation_and_rate.py
import pytest, time
from app.schemas.order import OrderIn

def test_order_validation_ok():
    o = OrderIn(order_id="o-1", user_id="u-1", amount=10.5, country="ES", created_at="2025-09-28T12:00:00Z")
    assert o.order_id == "o-1"

def test_order_validation_fail():
    with pytest.raises(Exception):
        OrderIn(order_id="o-1", user_id="u-1", amount="xx", country="ES", created_at="bad")

def test_rate_window_logic():
    # Simula la lógica de ventana (>20 en 60s)
    from collections import deque
    WINDOW = 60
    times = deque()
    now = time.time()
    for i in range(21):
        times.append(now - 59 + i*0.5)
    # purge
    while times and (now - times[0]) > WINDOW:
        times.popleft()
    assert len(times) > 20