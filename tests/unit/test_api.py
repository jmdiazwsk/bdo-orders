# tests/unit/test_api.py
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock
from fastapi.testclient import TestClient

from app.main import app
from app.models.order import Order
# Import the *same* dependency the endpoint uses, so we can override it in tests
from app.db.session import get_session as real_get_session


class TestHealthEndpoint:
    def test_health_check_success(self):
        """
        Verifies /health returns 200 and a JSON body with a 'status' field.

        Strategy:
        - Create a TestClient for the app.
        - Override the DB session dependency with an AsyncMock to avoid touching the real DB.
        - Call the /health endpoint and assert the contract.
        """
        with TestClient(app) as client:
            # Create a fake DB session. It is never awaited directly; it's yielded by the dependency.
            mock_session = AsyncMock()

            async def override_get_session():
                # FastAPI dependencies that are async generators must yield the object.
                yield mock_session

            # Apply the dependency override so endpoints that depend on get_session use our mock.
            app.dependency_overrides[real_get_session] = override_get_session

            # Exercise
            resp = client.get("/health")

            # Verify response shape and code
            assert resp.status_code == 200
            data = resp.json()
            assert "status" in data

            # Always clean up overrides to avoid leaking state across tests
            app.dependency_overrides.clear()


class TestOrdersEndpoint:
    def test_get_order_success(self):
        """
        Verifies /orders/{order_id} returns a mapped Order serialized to JSON.

        Strategy:
        - Mock the DB session.execute() to return an object whose scalar_one_or_none()
          yields a fully populated Order instance.
        - Override the DB session dependency with that mock.
        - Call the endpoint and assert the serialized fields.
        """
        with TestClient(app) as client:
            mock_session = AsyncMock()

            # The result of session.execute(...) is a synchronous result-like object.
            # We mimic it with a normal Mock that provides scalar_one_or_none().
            mock_result = Mock()

            # Build a realistic Order model as the endpoint would fetch from the DB.
            mock_order = Order()
            mock_order.order_id = "o-test-123"
            mock_order.user_id = "u-test-456"
            mock_order.amount = Decimal("125.50")
            mock_order.country = "ES"
            mock_order.created_at = datetime(2025, 9, 28, 10, 0, 0, tzinfo=timezone.utc)

            # When the endpoint runs query.scalar_one_or_none(), return our model.
            mock_result.scalar_one_or_none.return_value = mock_order
            # And make session.execute(...) return that result object.
            mock_session.execute.return_value = mock_result

            async def override_get_session():
                yield mock_session

            app.dependency_overrides[real_get_session] = override_get_session

            # Exercise
            resp = client.get("/orders/o-test-123")

            # Verify: 200 + properly serialized payload
            assert resp.status_code == 200
            data = resp.json()
            assert data["order_id"] == "o-test-123"
            assert data["user_id"] == "u-test-456"
            # Decimal should be rendered to a float in JSON
            assert data["amount"] == 125.5
            assert data["country"] == "ES"
            # created_at presence is enough (exact format is handled by pydantic/jsonable_encoder)
            assert "created_at" in data

            app.dependency_overrides.clear()


class TestMetricsEndpoint:
    def test_get_metrics_default_window(self):
        """
        Verifies /metrics returns aggregated KPIs when called with default parameters.

        Strategy:
        - The endpoint performs (at least) three DB calls:
            1) total count of orders
            2) total sum of amount
            3) top countries by count
          We simulate those by making session.execute(...) return different mocked
          "result" objects on each call via side_effect.
        - Assert the endpoint composes those values into the expected JSON response.
        """
        with TestClient(app) as client:
            mock_session = AsyncMock()

            # For scalar queries, the SQLAlchemy result exposes .scalar_one()
            mock_total_orders = Mock()
            mock_total_orders.scalar_one.return_value = 15

            mock_total_amount = Mock()
            mock_total_amount.scalar_one.return_value = 2450.5

            # For list queries, we mimic .all() returning tuples (country, count)
            mock_top_countries = Mock()
            mock_top_countries.all.return_value = [("ES", 5), ("FR", 4), ("US", 3)]

            # Make each session.execute(...) call yield the corresponding mock, in order.
            mock_session.execute.side_effect = [
                mock_total_orders,   # first query -> count
                mock_total_amount,   # second query -> sum
                mock_top_countries,  # third query -> top countries
            ]

            async def override_get_session():
                yield mock_session

            app.dependency_overrides[real_get_session] = override_get_session

            # Exercise
            resp = client.get("/metrics")

            # Verify aggregated contract
            assert resp.status_code == 200
            data = resp.json()
            assert data["count_orders"] == 15
            assert data["sum_amount"] == 2450.5
            # Endpoint is expected to flatten tuples to just the country codes in order
            assert data["top_countries"] == ["ES", "FR", "US"]

            app.dependency_overrides.clear()
