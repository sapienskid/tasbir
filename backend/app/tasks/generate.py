from app.tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=3, acks_late=True)
def generate_task(self, task_id: str, source_data: dict):
    """Main generation task — runs the LangGraph agent pipeline."""
    pass
