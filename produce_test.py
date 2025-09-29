import json
import asyncio
from aiokafka import AIOKafkaProducer

async def produce_test_messages():
    producer = AIOKafkaProducer(
        bootstrap_servers='localhost:9092',
        value_serializer=lambda x: json.dumps(x).encode('utf-8')
    )
    
    await producer.start()
    try:
        messages = [
            {
                "order_id": "o-100",
                "user_id": "u-100",
                "amount": 42.0,
                "country": "FR",
                "created_at": "2024-12-29T10:40:00Z"
            },
            {
                "order_id": "o-101", 
                "user_id": "u-101",
                "amount": 2000.0,
                "country": "ES", 
                "created_at": "2024-12-29T10:41:00Z"
            },
            {
                "order_id": "o-102",
                "user_id": "u-102", 
                "amount": 150.0,
                "country": "US",
                "created_at": "2024-12-29T10:42:00Z"
            }
        ]
        
        for msg in messages:
            await producer.send_and_wait("orders", msg)
            print(f"Sent: {msg['order_id']}")
            
    finally:
        await producer.stop()

if __name__ == "__main__":
    asyncio.run(produce_test_messages())