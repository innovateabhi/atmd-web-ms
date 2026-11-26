import io
import csv
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from sqlalchemy import func, case
from app.models import db, MonitoringLog, Incident, Website, utc_now

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('')
@login_required
def index():
    website_id = request.args.get('website_id', type=int)
    days = request.args.get('days', default=7, type=int)

    since_dt = utc_now() - timedelta(days=days)
    websites = Website.query.order_by(Website.name.asc()).all()

    # Query summary metrics
    log_query = db.session.query(
        func.count(MonitoringLog.id).label('total_checks'),
        func.sum(case((MonitoringLog.is_available == True, 1), else_=0)).label('success_checks'),
        func.avg(MonitoringLog.response_time_ms).label('avg_rt'),
        func.min(MonitoringLog.response_time_ms).label('min_rt'),
        func.max(MonitoringLog.response_time_ms).label('max_rt')
    ).filter(MonitoringLog.checked_at >= since_dt)

    incident_query = Incident.query.filter(Incident.started_at >= since_dt)

    if website_id:
        log_query = log_query.filter(MonitoringLog.website_id == website_id)
        incident_query = incident_query.filter(Incident.website_id == website_id)

    log_stats = log_query.first()
    incidents = incident_query.order_by(Incident.started_at.desc()).all()

    total_checks = log_stats.total_checks or 0
    success_checks = log_stats.success_checks or 0
    avg_rt = round(log_stats.avg_rt, 2) if log_stats.avg_rt else 0.0
    min_rt = round(log_stats.min_rt, 2) if log_stats.min_rt else 0.0
    max_rt = round(log_stats.max_rt, 2) if log_stats.max_rt else 0.0
    uptime_pct = round((success_checks / total_checks) * 100.0, 2) if total_checks > 0 else 100.0

    return render_template(
        'reports/index.html',
        websites=websites,
        current_website_id=website_id,
        days=days,
        total_checks=total_checks,
        success_checks=success_checks,
        uptime_pct=uptime_pct,
        avg_rt=avg_rt,
        min_rt=min_rt,
        max_rt=max_rt,
        incident_count=len(incidents),
        incidents=incidents[:20]
    )

@reports_bp.route('/export/logs.csv')
@login_required
def export_logs_csv():
    website_id = request.args.get('website_id', type=int)
    days = request.args.get('days', default=7, type=int)

    since_dt = utc_now() - timedelta(days=days)
    query = MonitoringLog.query.filter(MonitoringLog.checked_at >= since_dt)

    if website_id:
        query = query.filter(MonitoringLog.website_id == website_id)

    logs = query.order_by(MonitoringLog.checked_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Log ID',
        'Website ID',
        'Website Name',
        'Website URL',
        'Checked At (UTC)',
        'Is Available',
        'HTTP Status Code',
        'Response Time (ms)',
        'Error Category',
        'Error Message'
    ])

    for log in logs:
        writer.writerow([
            log.id,
            log.website_id,
            log.website.name if log.website else 'N/A',
            log.website.url if log.website else 'N/A',
            log.checked_at.strftime('%Y-%m-%d %H:%M:%S'),
            'UP' if log.is_available else 'DOWN',
            log.status_code or '',
            log.response_time_ms if log.response_time_ms is not None else '',
            log.error_type or 'none',
            log.error_message or ''
        ])

    output.seek(0)
    filename = f"monitoring_logs_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@reports_bp.route('/export/incidents.csv')
@login_required
def export_incidents_csv():
    website_id = request.args.get('website_id', type=int)
    days = request.args.get('days', default=30, type=int)

    since_dt = utc_now() - timedelta(days=days)
    query = Incident.query.filter(Incident.started_at >= since_dt)

    if website_id:
        query = query.filter(Incident.website_id == website_id)

    incidents = query.order_by(Incident.started_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Incident ID',
        'Website ID',
        'Website Name',
        'Website URL',
        'Started At (UTC)',
        'Resolved At (UTC)',
        'Status',
        'Duration (Seconds)',
        'Error Category',
        'Cause / Error Message',
        'Resolved By'
    ])

    for inc in incidents:
        writer.writerow([
            inc.id,
            inc.website_id,
            inc.website.name if inc.website else 'N/A',
            inc.website.url if inc.website else 'N/A',
            inc.started_at.strftime('%Y-%m-%d %H:%M:%S'),
            inc.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if inc.resolved_at else '',
            'RESOLVED' if inc.is_resolved else 'ACTIVE',
            inc.duration_seconds if inc.duration_seconds is not None else '',
            inc.error_type or '',
            inc.cause or '',
            inc.resolved_by or ''
        ])

    output.seek(0)
    filename = f"incidents_{utc_now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
