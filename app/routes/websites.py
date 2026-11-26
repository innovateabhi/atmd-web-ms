from datetime import timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required
from sqlalchemy import func, case
from app.models import db, Website, MonitoringLog, Incident, Setting, utc_now
from app.forms import WebsiteForm
from app.services.checker import check_website, validate_target_url

websites_bp = Blueprint('websites', __name__, url_prefix='/websites')

@websites_bp.route('')
@login_required
def index():
    websites = Website.query.order_by(Website.name.asc()).all()
    # Compute check-based 24h uptime for each site
    since_24h = utc_now() - timedelta(hours=24)
    stats_map = {}

    for site in websites:
        stats = db.session.query(
            func.count(MonitoringLog.id).label('total'),
            func.sum(case((MonitoringLog.is_available == True, 1), else_=0)).label('success'),
            func.avg(MonitoringLog.response_time_ms).label('avg_rt')
        ).filter(MonitoringLog.website_id == site.id, MonitoringLog.checked_at >= since_24h).first()

        total = stats.total or 0
        success = stats.success or 0
        avg_rt = round(stats.avg_rt, 2) if stats.avg_rt else None
        uptime = round((success / total) * 100.0, 2) if total > 0 else (100.0 if site.current_status == 'operational' else 0.0)
        stats_map[site.id] = {
            'uptime_24h': uptime,
            'avg_rt_24h': avg_rt,
            'total_checks_24h': total
        }

    return render_template('websites/index.html', websites=websites, stats_map=stats_map)

@websites_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    form = WebsiteForm()
    # Default interval and timeout from settings if available
    if request.method == 'GET':
        def_int = Setting.get_value('default_interval', '60')
        def_to = Setting.get_value('default_timeout', '10')
        try:
            form.check_interval_seconds.data = int(def_int)
            form.timeout_seconds.data = int(def_to)
        except ValueError:
            pass

    if form.validate_on_submit():
        url = form.url.data.strip()
        allow_localhost = current_app.config.get('ALLOW_LOCALHOST_MONITORING', False)
        if not allow_localhost:
            allow_localhost = Setting.get_value('allow_localhost_monitoring', 'false').lower() in ('true', '1', 'yes')
        if not allow_localhost:
            allow_localhost = os.environ.get('ALLOW_LOCALHOST_MONITORING', 'false').lower() in ('true', '1', 'yes')

        is_valid, err_msg, _ = validate_target_url(url, allow_localhost=allow_localhost)
        if not is_valid:
            flash(f"URL Validation Error: {err_msg}", "danger")
            return render_template('websites/form.html', form=form, title='Add Website Monitor')

        website = Website(
            name=form.name.data.strip(),
            url=url,
            check_interval_seconds=form.check_interval_seconds.data,
            timeout_seconds=form.timeout_seconds.data,
            expected_status_code=form.expected_status_code.data.strip(),
            is_active=form.is_active.data,
            current_status='pending'
        )
        db.session.add(website)
        db.session.commit()

        # Perform initial health check immediately
        if website.is_active:
            try:
                check_website(website.id)
            except Exception:
                pass

        flash(f'Website monitor "{website.name}" registered successfully.', 'success')
        return redirect(url_for('websites.detail', website_id=website.id))

    return render_template('websites/form.html', form=form, title='Add Website Monitor')

@websites_bp.route('/<int:website_id>')
@login_required
def detail(website_id):
    website = Website.query.get_or_404(website_id)
    time_range = request.args.get('range', '24h')

    hours = 168 if time_range == '7d' else 24
    since_dt = utc_now() - timedelta(hours=hours)

    stats = db.session.query(
        func.count(MonitoringLog.id).label('total'),
        func.sum(case((MonitoringLog.is_available == True, 1), else_=0)).label('success'),
        func.avg(MonitoringLog.response_time_ms).label('avg_rt'),
        func.min(MonitoringLog.response_time_ms).label('min_rt'),
        func.max(MonitoringLog.response_time_ms).label('max_rt')
    ).filter(MonitoringLog.website_id == website.id, MonitoringLog.checked_at >= since_dt).first()

    total_checks = stats.total or 0
    success_checks = stats.success or 0
    avg_rt = round(stats.avg_rt, 2) if stats.avg_rt else 0.0
    min_rt = round(stats.min_rt, 2) if stats.min_rt else 0.0
    max_rt = round(stats.max_rt, 2) if stats.max_rt else 0.0

    uptime_pct = round((success_checks / total_checks) * 100.0, 2) if total_checks > 0 else (100.0 if website.current_status == 'operational' else 0.0)

    # Recent 50 logs
    recent_logs = website.logs.order_by(MonitoringLog.checked_at.desc()).limit(50).all()
    recent_incidents = website.incidents.order_by(Incident.started_at.desc()).limit(10).all()

    return render_template(
        'websites/detail.html',
        website=website,
        time_range=time_range,
        total_checks=total_checks,
        success_checks=success_checks,
        uptime_pct=uptime_pct,
        avg_rt=avg_rt,
        min_rt=min_rt,
        max_rt=max_rt,
        recent_logs=recent_logs,
        recent_incidents=recent_incidents
    )

@websites_bp.route('/<int:website_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(website_id):
    website = Website.query.get_or_404(website_id)
    form = WebsiteForm(obj=website)

    if form.validate_on_submit():
        url = form.url.data.strip()
        allow_localhost = current_app.config.get('ALLOW_LOCALHOST_MONITORING', False)
        if not allow_localhost:
            allow_localhost = Setting.get_value('allow_localhost_monitoring', 'false').lower() in ('true', '1', 'yes')
        if not allow_localhost:
            allow_localhost = os.environ.get('ALLOW_LOCALHOST_MONITORING', 'false').lower() in ('true', '1', 'yes')

        is_valid, err_msg, _ = validate_target_url(url, allow_localhost=allow_localhost)
        if not is_valid:
            flash(f"URL Validation Error: {err_msg}", "danger")
            return render_template('websites/form.html', form=form, title=f'Edit {website.name}', is_edit=True)

        website.name = form.name.data.strip()
        website.url = url
        website.check_interval_seconds = form.check_interval_seconds.data
        website.timeout_seconds = form.timeout_seconds.data
        website.expected_status_code = form.expected_status_code.data.strip()
        website.is_active = form.is_active.data
        db.session.commit()

        flash(f'Website monitor "{website.name}" updated successfully.', 'success')
        return redirect(url_for('websites.detail', website_id=website.id))

    return render_template('websites/form.html', form=form, title=f'Edit {website.name}', is_edit=True)

@websites_bp.route('/<int:website_id>/toggle', methods=['POST'])
@login_required
def toggle(website_id):
    website = Website.query.get_or_404(website_id)
    website.is_active = not website.is_active
    db.session.commit()
    status_str = "resumed" if website.is_active else "paused"
    flash(f'Monitoring for "{website.name}" has been {status_str}.', 'info')
    return redirect(request.referrer or url_for('websites.index'))

@websites_bp.route('/<int:website_id>/check-now', methods=['POST'])
@login_required
def manual_check(website_id):
    website = Website.query.get_or_404(website_id)
    result = check_website(website.id)
    if result.get('is_available'):
        flash(f'Health check for "{website.name}" succeeded! Response time: {result.get("response_time_ms")} ms.', 'success')
    else:
        flash(f'Health check for "{website.name}" failed: {result.get("error_message")}', 'danger')
    return redirect(request.referrer or url_for('websites.detail', website_id=website.id))

@websites_bp.route('/<int:website_id>/delete', methods=['POST'])
@login_required
def delete(website_id):
    website = Website.query.get_or_404(website_id)
    name = website.name
    db.session.delete(website)
    db.session.commit()
    flash(f'Website monitor "{name}" and all historical logs were deleted.', 'warning')
    return redirect(url_for('websites.index'))

@websites_bp.route('/<int:website_id>/chart-data')
@login_required
def chart_data(website_id):
    website = Website.query.get_or_404(website_id)
    time_range = request.args.get('range', '24h')
    hours = 168 if time_range == '7d' else 24
    since_dt = utc_now() - timedelta(hours=hours)

    logs = MonitoringLog.query.filter(
        MonitoringLog.website_id == website.id,
        MonitoringLog.checked_at >= since_dt
    ).order_by(MonitoringLog.checked_at.asc()).all()

    labels = []
    response_times = []
    statuses = []

    for log in logs:
        fmt = '%b %d %H:%M' if hours > 24 else '%H:%M:%S'
        labels.append(log.checked_at.strftime(fmt))
        response_times.append(log.response_time_ms if log.response_time_ms is not None else 0)
        statuses.append(1 if log.is_available else 0)

    return jsonify({
        'labels': labels,
        'response_times': response_times,
        'statuses': statuses
    })
