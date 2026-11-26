from datetime import timedelta
from sqlalchemy import func, case
from app.models import db, Website, MonitoringLog, utc_now

def test_check_based_uptime_calculation(app):
    with app.app_context():
        site = Website(name='Uptime Calc Site', url='http://127.0.0.1:8085/health')
        db.session.add(site)
        db.session.commit()

        now = utc_now()

        # Add 8 successful checks and 2 failed checks = 80.0% uptime
        for i in range(8):
            log = MonitoringLog(
                website_id=site.id,
                checked_at=now - timedelta(minutes=i*2),
                is_available=True,
                status_code=200,
                response_time_ms=100.0 + (i * 10),
                error_type='none'
            )
            db.session.add(log)

        for i in range(2):
            log = MonitoringLog(
                website_id=site.id,
                checked_at=now - timedelta(minutes=20 + i*2),
                is_available=False,
                status_code=503,
                response_time_ms=50.0,
                error_type='http_error',
                error_message='Service Unavailable'
            )
            db.session.add(log)

        db.session.commit()

        # Calculate check-based uptime
        stats = db.session.query(
            func.count(MonitoringLog.id).label('total'),
            func.sum(case((MonitoringLog.is_available == True, 1), else_=0)).label('success'),
            func.avg(MonitoringLog.response_time_ms).label('avg_rt'),
            func.min(MonitoringLog.response_time_ms).label('min_rt'),
            func.max(MonitoringLog.response_time_ms).label('max_rt')
        ).filter(MonitoringLog.website_id == site.id).first()

        assert stats.total == 10
        assert stats.success == 8
        uptime_pct = round((stats.success / stats.total) * 100.0, 2)
        assert uptime_pct == 80.0
        assert stats.min_rt == 50.0
        assert stats.max_rt == 170.0
        assert round(stats.avg_rt, 1) == 118.0

def test_csv_export_endpoint(auth_client, app):
    with app.app_context():
        site = Website(name='CSV Export Site', url='http://127.0.0.1:8085/health')
        db.session.add(site)
        db.session.commit()

        log = MonitoringLog(
            website_id=site.id,
            checked_at=utc_now(),
            is_available=True,
            status_code=200,
            response_time_ms=88.5,
            error_type='none'
        )
        db.session.add(log)
        db.session.commit()

    res = auth_client.get('/reports/export/logs.csv')
    assert res.status_code == 200
    assert 'text/csv' in res.content_type
    assert b'CSV Export Site' in res.data
    assert b'88.5' in res.data
