# tests/unit/test_consumer.py (only test_persist_new_order)
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

# _persist is the internal function that writes an order to the DB if it doesn't exist yet
from app.consumers.orders_consumer import _persist
from app.schemas.order import OrderIn


@pytest.mark.asyncio
async def test_persist_new_order():
    """
    Ensures that _persist() inserts a *new* order and commits the transaction.

    Test strategy:
    - Mock the DB session so no real database is touched.
    - Make session.execute(...) return a result whose scalar_one_or_none() is None,
      which simulates "no existing record with this order_id".
    - Verify that:
        * session.execute(...) was awaited exactly once (the existence check).
        * session.add(...) was called exactly once (the insert).
        * session.commit(...) was awaited exactly once (the transaction is committed).
      And that _persist(...) returns True to indicate success.
    """

    # Async DB session mock (so we can await its methods like .execute() / .commit())
    mock_session = AsyncMock()

    # Result of the SELECT existence check: "no row found"
    # In SQLAlchemy, scalar_one_or_none() -> None means nothing matched the query.
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = None

    # session.execute(...) should yield the mocked result object above
    mock_session.execute.return_value = mock_result

    # session.add is synchronous in SQLAlchemy, a plain Mock is enough
    mock_session.add = Mock()

    # Build a valid inbound schema object as the consumer would produce after parsing the message
    order = OrderIn(
        order_id="o-1",
        user_id="u-1",
        amount=25.0,
        country="ES",
        created_at=datetime.now(timezone.utc),
    )

    # Exercise: attempt to persist a brand new order
    ok = await _persist(mock_session, order)

    # Assert that the function reports success
    assert ok is True

    # Verify the expected DB interactions:
    # 1) A single existence check
    mock_session.execute.assert_awaited_once()
    # 2) One insert into the session
    mock_session.add.assert_called_once()
    # 3) Commit of the transaction
    mock_session.commit.assert_awaited_once()
