from taskiq_broker import broker
from post_service_v2 import process_product_task


@broker.task(task_name="posts.process_product")
async def process_product_background(product_id: int, file_paths: list[str]) -> None:
    await process_product_task(product_id=product_id, file_paths=file_paths)
