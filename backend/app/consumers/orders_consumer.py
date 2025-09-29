# C:\bdo-orders-platform\backend\app\consumers\orders_consumer.py
import asyncio
import json
import signal
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from aiokafka import AIOKafkaConsumer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.settings import settings
from app.db.session import get_async_session_maker
from app.models.order import Order
from app.schemas.order import OrderIn
from app.services.alerts import sns_notify, s3_put_object
from aiokafka.admin import AIOKafkaAdminClient, NewTopic

# Per-minute order counter for burst/spike alerts
order_counter = defaultdict(int)

def _parse_message(raw: bytes) -> OrderIn:
    """Validate and parse a Kafka message into OrderIn (Pydantic)."""
    data = json.loads(raw.decode("utf-8"))
    return OrderIn.model_validate(data)

async def ensure_topic():
    """Ensure the orders topic exists; create it if missing (idempotent-ish)."""
    admin = AIOKafkaAdminClient(bootstrap_servers=settings.kafka_brokers)
    await admin.start()
    try:
        topics = await admin.list_topics()
        if settings.kafka_orders_topic not in topics:
            await admin.create_topics([
                NewTopic(
                    name=settings.kafka_orders_topic,
                    num_partitions=3,
                    replication_factor=1
                )
            ])
    finally:
        await admin.close()

async def _persist(session: AsyncSession, payload: OrderIn) -> bool:
    """Insert a new order; return True if inserted, False if already existed or failed."""
    try:
        # Check for existence by order_id (idempotency at DB level)
        existing = await session.execute(
            select(Order).where(Order.order_id == payload.order_id)
        )
        if existing.scalar_one_or_none():
            return False  # duplicate

        # Insert and commit new order
        new_order = Order(
            order_id=payload.order_id,
            user_id=payload.user_id,
            amount=payload.amount,
            country=payload.country,
            created_at=payload.created_at,
        )
        session.add(new_order)
        await session.commit()
        return True
    except Exception as e:
        # Rollback on failure to keep the session consistent
        await session.rollback()
        print(f"Error persisting order: {e}")
        return False

async def _check_alerts(session: AsyncSession, order: OrderIn):
    """Apply simple business rules and send alerts (high value, traffic spikes)."""
    # Rule 1: High-value order (amount >= 1000)
    if order.amount >= 1000:
        alert_data = {
            "alert_type": "high_value_order",
            "order_id": order.order_id,
            "amount": float(order.amount),
            "country": order.country,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        try:
            sns_notify("High Value Order Alert", alert_data)
            s3_put_object("alerts/high-value", alert_data)
            print(f"[consumer] High value alert sent for order: {order.order_id}")
        except Exception as e:
            print(f"Error sending high value alert: {e}")

    # Rule 2: More than 20 orders within a single minute (spike)
    now = datetime.now(timezone.utc)
    minute_key = now.strftime("%Y-%m-%d %H:%M")

    # Increment current minute counter
    order_counter[minute_key] += 1

    # Garbage-collect old minute buckets (> 2 minutes old)
    cutoff = now - timedelta(minutes=2)
    cutoff_key = cutoff.strftime("%Y-%m-%d %H:%M")
    keys_to_remove = [k for k in order_counter.keys() if k < cutoff_key]
    for k in keys_to_remove:
        del order_counter[k]

    # Trigger spike alert if threshold exceeded
    if order_counter[minute_key] > 20:
        alert_data = {
            "alert_type": "high_traffic_spike",
            "minute": minute_key,
            "order_count": order_counter[minute_key],
            "timestamp": now.isoformat()
        }
        try:
            sns_notify("High Traffic Spike Alert", alert_data)
            s3_put_object("alerts/traffic-spike", alert_data)
            print(f"[consumer] Traffic spike alert sent for minute: {minute_key}")
        except Exception as e:
            print(f"Error sending traffic spike alert: {e}")

def _is_valid_json(raw: bytes) -> bool:
    """Quick JSON sanity check to skip obviously malformed/empty messages."""
    try:
        content = raw.decode("utf-8").strip()
        if not content:
            return False
        json.loads(content)
        return True
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False

async def consume():
    """Main consumption loop: poll, validate, persist, alert, commit offsets."""
    consumer = AIOKafkaConsumer(
        settings.kafka_orders_topic,
        bootstrap_servers=settings.kafka_brokers,
        group_id="orders-consumer-group",  # consumer group for horizontal scaling
        enable_auto_commit=False,          # manual commits after processing
        auto_offset_reset="earliest",
    )
    SessionLocal = get_async_session_maker()

    try:
        await ensure_topic()
        await consumer.start()
        print(f"[consumer] Started. Topic={settings.kafka_orders_topic}, Group=orders-consumer-group")

        while True:
            # Batch fetch; small timeout to keep loop responsive
            records = await consumer.getmany(timeout_ms=1000, max_records=200)
            if not records:
                await asyncio.sleep(0.1)
                continue

            for tp, msgs in records.items():
                # One DB session per partition batch
                async with SessionLocal() as session:
                    for msg in msgs:
                        # Drop invalid JSON early
                        if not _is_valid_json(msg.value):
                            print(f"[consumer] Skipping invalid message: {msg.value.decode('utf-8', 'ignore')[:50]}...")
                            continue

                        try:
                            # Schema validation & parsing
                            order = _parse_message(msg.value)

                            # Persist (idempotent at app/DB level)
                            inserted = await _persist(session, order)

                            if inserted:
                                # Only alert on newly inserted orders
                                await _check_alerts(session, order)
                                print(f"[consumer] Processed order: {order.order_id}")
                            else:
                                print(f"[consumer] Duplicate order skipped: {order.order_id}")

                        except Exception as e:
                            # Log and proceed with other messages; commit happens per batch
                            print(f"[consumer] Error processing message: {e}")
                            print(f"[consumer] Raw message: {msg.value.decode('utf-8', 'ignore')}")
                            continue

                # Commit offsets after the batch to achieve at-least-once semantics
                await consumer.commit()

    except Exception as e:
        print(f"[consumer] Fatal error: {e}")
        raise
    finally:
        # Ensure proper shutdown of the consumer
        await consumer.stop()
        print("[consumer] Stopped.")

async def main():
    """Entry point with graceful shutdown on SIGINT/SIGTERM."""
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    # Register signal handlers (best-effort on Windows)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass  # Windows

    task = asyncio.create_task(consume())

    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        pass

    # Cancel the consumer task and await clean termination
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    asyncio.run(main())
