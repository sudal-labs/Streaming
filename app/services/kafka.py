import json
import logging

from aiokafka import AIOKafkaProducer

from app.config import settings

logger = logging.getLogger(__name__)

_producer: AIOKafkaProducer | None = None

async def get_producer() -> AIOKafkaProducer | None:
    global _producer
    if _producer is None:
        _producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode(),
        )
        await _producer.start()
    return _producer

async def stop_producer():
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None

async def publish_transcode_event(
        video_id: str,
        object_key: str
):
    producer = await get_producer()
    message = {
        "video_id": video_id,
        "object_key": object_key,
    }

    await producer.send_and_wait(
        topic=settings.KAFKA_TOPIC_TRANSCODE,
        value=message,
        key=video_id.encode(),
    )
    logger.info(f"[{video_id}] 트랜스코딩 이벤트 발행")