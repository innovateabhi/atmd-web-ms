from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from sqlalchemy import func, case
from app.models import db, Website, MonitoringLog, Incident, utc_now

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='')

def get_dashboard_summary():
    """Compute aggregate monitoring metrics across all monitors."""
    websites = Website.query.all()
    total_sites = len(websites)
    operational_sites = sum(1 for w in websites if w.is_active and w.current_status == 'operational')
    unavailable_sites = sum(1 for w in websites if w.is_active and w.current_status == 'unavailable')
    paused_sites = sum(1 for w in websites if not w.is_active)
    pending_sites = sum(1 for w in websites if w.is_active and w.current_status == 'pending')

    # Check-based uptime & average response time in the last 24 hours
    since_24h = utc_now() - timedelta(hours=24)

    stats_24h = db.session.query(
        func.count(MonitoringLog.id).label('total_checks'),
        func.sum(case((MonitoringLog.is_available == True, 1), else_=0)).label('successful_checks'),
        func.avg(MonitoringLog.response_time_ms).label('avg_rt')
    ).filter(MonitoringLog.checked_at >= since_24h).first()

    total_checks = stats_24h.total_checks or 0
    successful_checks = stats_24h.successful_checks or 0
    avg_response_time = round(stats_24h.avg_rt, 2) if stats_24h.avg_rt else 0.0

    if total_checks > 0:
        overall_uptime_pct = round((successful_checks / total_checks) * 100.0, 2)
    else:
        overall_uptime_pct = 100.0 if (total_sites > 0 and unavailable_sites == 0) else 0.0

    recent_incidents = Incident.query.order_by(Incident.started_at.desc()).limit(5).all()

    last_log = MonitoringLog.query.order_by(MonitoringLog.checked_at.desc()).first()
    last_check_timestamp = last_log.checked_at.strftime('%Y-%m-%d %H:%M:%S UTC') if last_log else 'No checks yet'

    return {
        'total_sites': total_sites,
        'operational_sites': operational_sites,
        'unavailable_sites': unavailable_sites,
        'paused_sites': paused_sites,
        'pending_sites': pending_sites,
        'avg_response_time': avg_response_time,
        'overall_uptime_pct': overall_uptime_pct,
        'total_checks_24h': total_checks,
        'recent_incidents': recent_incidents,
        'last_check_timestamp': last_check_timestamp,
        'websites': websites
    }

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    summary = get_dashboard_summary()
    return render_template('dashboard/index.html', **summary)

@dashboard_bp.route('/api/dashboard-stats')
@login_required
def dashboard_stats_api():
    summary = get_dashboard_summary()

    # Build response time hourly chart data for the past 24 hours
    now = utc_now()
    hourly_labels = []
    hourly_rt = []
    hourly_availability = []

    for i in range(23, -1, -1):
        window_start = now - timedelta(hours=i+1)
        window_end = now - timedelta(hours=i)
        label = window_end.strftime('%H:00')
        hourly_labels.append(label)

        hour_stats = db.session.query(
            func.count(MonitoringLog.id).label('cnt'),
            func.sum(case((MonitoringLog.is_available == True, 1), else_=0)).label('avail_cnt'),
            func.avg(MonitoringLog.response_time_ms).label('avg_rt')
        ).filter(MonitoringLog.checked_at >= window_start, MonitoringLog.checked_at < window_end).first()

        avg_rt = round(hour_stats.avg_rt, 1) if hour_stats.avg_rt else 0
        hourly_rt.append(avg_rt)

        if hour_stats.cnt and hour_stats.cnt > 0:
            pct = round((hour_stats.avail_cnt / hour_stats.cnt) * 100.0, 1)
        else:
            pct = 100.0
        hourly_availability.append(pct)

    # Simplified site list for JSON
    sites_data = [{
        'id': w.id,
        'name': w.name,
        'url': w.url,
        'current_status': w.current_status,
        'is_active': w.is_active,
        'last_rt': w.last_response_time_ms,
        'last_status_code': w.last_status_code,
        'last_checked': w.last_checked_at.strftime('%Y-%m-%d %H:%M:%S') if w.last_checked_at else 'Pending'
    } for w in summary['websites']]

    return jsonify({
        'total_sites': summary['total_sites'],
        'operational_sites': summary['operational_sites'],
        'unavailable_sites': summary['unavailable_sites'],
        'paused_sites': summary['paused_sites'],
        'avg_response_time': summary['avg_response_time'],
        'overall_uptime_pct': summary['overall_uptime_pct'],
        'last_check_timestamp': summary['last_check_timestamp'],
        'chart_labels': hourly_labels,
        'chart_rt': hourly_rt,
        'chart_availability': hourly_availability,
        'sites': sites_data
    })
