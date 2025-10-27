from celery import Celery
from app.config import settings

# Create Celery instance
celery_app = Celery(
    "phantom_security",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=['app.tasks.scan_tasks']
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Important: Set result backend
    result_backend=settings.redis_url,
    # Important: Set default queue
    task_default_queue='celery',
    task_routes={
        'app.tasks.scan_tasks.start_scan_task': {'queue': 'celery'},
        'app.tasks.scan_tasks.quick_scan_task': {'queue': 'celery'},
        'app.tasks.scan_tasks.analyze_with_ai_task': {'queue': 'celery'},
    }
)
