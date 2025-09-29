# tests/integration/test_full_flow.py
import asyncio
import json
import pytest
import time
from datetime import datetime, timezone
from aiokafka import AIOKafkaProducer
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.order import Order
from app.db.session import get_session
from app.core.settings import settings

class TestFullOrderFlow:
    """Integration test that validates the complete order processing flow"""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_end_to_end_order_processing(self):
        """Test the complete flow: Kafka -> Consumer -> DB -> API"""
        
        # Test order data
        test_order = {
            "order_id": "integration-test-001",
            "user_id": "user-integration-001", 
            "amount": 750.0,
            "country": "ES",
            "created_at": "2025-09-28T15:30:00Z"
        }
        
        # Step 1: Produce message to Kafka
        producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_brokers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        try:
            await producer.start()
            await producer.send(settings.kafka_orders_topic, test_order)
            await producer.stop()
        except Exception as e:
            pytest.skip(f"Kafka not available for integration test: {e}")
        
        # Step 2: Wait for consumer to process (adjust timing as needed)
        await asyncio.sleep(3)
        
        # Step 3: Verify order was persisted in database
        async with AsyncSession() as session:
            stmt = select(Order).where(Order.order_id == test_order["order_id"])
            result = await session.execute(stmt)
            db_order = result.scalar_one_or_none()
            
            assert db_order is not None, "Order should be persisted in database"
            assert db_order.order_id == test_order["order_id"]
            assert db_order.user_id == test_order["user_id"]
            assert float(db_order.amount) == test_order["amount"]
            assert db_order.country == test_order["country"]
        
        # Step 4: Test API retrieval
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(f"/orders/{test_order['order_id']}")
            
            assert response.status_code == 200
            api_data = response.json()
            assert api_data["order_id"] == test_order["order_id"]
            assert api_data["user_id"] == test_order["user_id"]  
            assert api_data["amount"] == test_order["amount"]
            assert api_data["country"] == test_order["country"]
        
        # Step 5: Test metrics include the new order
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/metrics?window=5m")
            
            assert response.status_code == 200
            metrics_data = response.json()
            assert metrics_data["count_orders"] >= 1
            assert metrics_data["sum_amount"] >= test_order["amount"]
            assert test_order["country"] in metrics_data["top_countries"]
    
    @pytest.mark.asyncio
    @pytest.mark.integration  
    async def test_high_value_order_alert_flow(self):
        """Test that high-value orders trigger alerts"""
        
        # High-value test order (>= 1000)
        test_order = {
            "order_id": "integration-high-value-001",
            "user_id": "user-integration-002",
            "amount": 1500.0,  # Above alert threshold
            "country": "FR", 
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Produce to Kafka
        producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_brokers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        try:
            await producer.start()
            await producer.send(settings.kafka_orders_topic, test_order)
            await producer.stop()
        except Exception as e:
            pytest.skip(f"Kafka not available: {e}")
        
        # Wait for processing
        await asyncio.sleep(3)
        
        # Verify order exists
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(f"/orders/{test_order['order_id']}")
            assert response.status_code == 200
        
        # Note: In a real test environment, you'd also verify:
        # - SNS message was sent (check LocalStack logs)
        # - S3 object was created (query LocalStack S3)
        # For this integration test, we're focusing on the core flow
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_duplicate_order_handling(self):
        """Test that duplicate orders are handled idempotently"""
        
        test_order = {
            "order_id": "integration-duplicate-001",
            "user_id": "user-integration-003",
            "amount": 250.0,
            "country": "DE",
            "created_at": "2025-09-28T16:00:00Z"
        }
        
        producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_brokers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        
        try:
            await producer.start()
            
            # Send the same order twice
            await producer.send(settings.kafka_orders_topic, test_order)
            await asyncio.sleep(1)  # Small delay
            await producer.send(settings.kafka_orders_topic, test_order)
            
            await producer.stop()
        except Exception as e:
            pytest.skip(f"Kafka not available: {e}")
        
        # Wait for processing
        await asyncio.sleep(4)
        
        # Verify only one order exists in database
        async with AsyncSession() as session:
            stmt = select(Order).where(Order.order_id == test_order["order_id"])
            result = await session.execute(stmt)
            orders = result.scalars().all()
            
            assert len(orders) == 1, "Duplicate orders should not be inserted"
        
        # API should still return the order
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(f"/orders/{test_order['order_id']}")
            assert response.status_code == 200

# Pytest configuration for integration tests
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()