import os
import sys
import time
import signal
import logging
import threading
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from apscheduler.schedulers.blocking import BlockingScheduler

# Add project root to sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from app.models import db, Website, utc_now
from app.services.checker import check_website

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [MonitoringWorker] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('MonitoringWorker')

# Active check registry to prevent overlapping checks for the same monitor
_active_checks = set()
_active_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix='MonitorWorker')

def run_website_check_task(app, website_id: int):
    """Executes a health check within application context, ensuring concurrency guards."""
    with _active_lock:
        if website_id in _active_checks:
            logger.warning(f"Check for website ID {website_id} already in progress. Skipping to prevent overlap.")
            return
        _active_checks.add(website_id)

    try:
        with app.app_context():
            website = Website.query.get(website_id)
            if not website or not website.is_active:
                return

            logger.info(f"Checking target [{website.id}] {website.name} ({website.url})...")
            result = check_website(website_id)
            status_desc = "UP" if result.get('is_available') else f"DOWN ({result.get('error_type')})"
            rt = f"{result.get('response_time_ms')}ms" if result.get('response_time_ms') is not None else "N/A"
            logger.info(f"Target [{website.id}] {website.name} -> {status_desc} | RT: {rt} | Code: {result.get('status_code')}")
    except Exception as e:
        logger.error(f"Unexpected error running check for website ID {website_id}: {str(e)}", exc_info=True)
    finally:
        with _active_lock:
            _active_checks.discard(website_id)

def dispatch_due_monitors(app):
    """Scan active monitors and dispatch health checks for targets that are due."""
    try:
        with app.app_context():
            now = utc_now()
            active_websites = Website.query.filter_by(is_active=True).all()

            for site in active_websites:
                interval = site.check_interval_seconds or 60
                is_due = False

                if site.last_checked_at is None:
                    is_due = True
                else:
                    last_check = site.last_checked_at
                    if last_check.tzinfo is None:
                        last_check = last_check.replace(tzinfo=timezone.utc)
                    elapsed = (now - last_check).total_seconds()
                    if elapsed >= interval:
                        is_due = True

                if is_due:
                    _executor.submit(run_website_check_task, app, site.id)
    except Exception as e:
        logger.error(f"Error in monitor dispatcher cycle: {str(e)}", exc_info=True)

def start_worker():
    """Initializes and runs the standalone APScheduler monitoring daemon."""
    logger.info("Initializing Linux Automated Website Uptime Monitoring Background Engine...")
    app = create_app()

    scheduler = BlockingScheduler()

    # Dispatcher runs frequently (every 5 seconds) to trigger any monitor whose individual interval has elapsed
    scheduler.add_job(
        func=lambda: dispatch_due_monitors(app),
        trigger='interval',
        seconds=5,
        id='monitor_dispatcher_job',
        name='Dispatch Due Monitors',
        replace_existing=True,
        max_instances=1
    )

    def signal_handler(signum, frame):
        logger.info("Received termination signal. Shutting down worker gracefully...")
        try:
            scheduler.shutdown(wait=False)
            _executor.shutdown(wait=False)
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)

    logger.info("Monitoring engine started successfully. Running background scheduler...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker process terminated.")

if __name__ == '__main__':
    start_worker()
