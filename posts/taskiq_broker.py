import os

from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
REDIS_RESULT_URL = os.getenv("REDIS_RESULT_URL", "redis://redis:6379/1")

broker = ListQueueBroker(REDIS_URL).with_result_backend(RedisAsyncResultBackend(REDIS_RESULT_URL))
