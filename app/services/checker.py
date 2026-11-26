import os
import time
import socket
import ipaddress
from urllib.parse import urlparse, urljoin
import requests
from flask import current_app
from app.models import db, Website, MonitoringLog, Setting, utc_now
from app.services.incident_manager import handle_monitoring_result

def is_ip_allowed(ip_str: str, allow_localhost: bool = False) -> bool:
    """Validate whether an IP address is permissible for outbound monitoring requests."""
    try:
        ip = ipaddress.ip_address(ip_str)
        if allow_localhost:
            # Allow loopback/local address explicitly for controlled academic lab demonstrations
            return True
        if ip.is_loopback or ip.is_private or ip.is_reserved or ip.is_link_local or ip.is_multicast:
            return False
        return True
    except ValueError:
        return False

def validate_target_url(url: str, allow_localhost: bool = False) -> tuple[bool, str, str]:
    """
    Validate target URL format and verify target IP resolves safely against SSRF.
    Returns (is_valid, resolved_ip_or_error, error_type).
    """
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False, "Invalid URL scheme. Only HTTP and HTTPS protocols are supported.", "invalid_scheme"

    hostname = parsed.hostname
    if not hostname:
        return False, "Invalid URL host.", "invalid_host"

    port = parsed.port or (443 if parsed.scheme == 'https' else 80)

    try:
        addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        if not addr_info:
            return False, f"Could not resolve DNS hostname: {hostname}", "dns_error"
        resolved_ip = addr_info[0][4][0]
    except socket.gaierror as e:
        return False, f"DNS resolution failed for {hostname}: {str(e)}", "dns_error"
    except Exception as e:
        return False, f"Host resolution error: {str(e)}", "dns_error"

    if not is_ip_allowed(resolved_ip, allow_localhost=allow_localhost):
        return False, f"Access to private/reserved IP destination {resolved_ip} is blocked by SSRF policy.", "ssrf_blocked"

    return True, resolved_ip, "none"

def execute_single_check(url: str, timeout_seconds: int = 10, expected_codes: list = None, allow_localhost: bool = False) -> dict:
    """
    Execute a secure HTTP/HTTPS health check with accurate timing, SSRF protection,
    and redirect validation.
    """
    if expected_codes is None:
        expected_codes = [200]

    # Validate primary target URL
    is_valid, ip_or_err, err_type = validate_target_url(url, allow_localhost=allow_localhost)
    if not is_valid:
        return {
            'is_available': False,
            'status_code': None,
            'response_time_ms': None,
            'error_type': err_type,
            'error_message': ip_or_err
        }

    headers = {
        'User-Agent': 'Linux-Automated-Uptime-Monitor/1.0 (+AcademicProject; HealthCheck)',
        'Accept': '*/*'
    }

    current_target = url
    max_redirects = 5
    redirect_count = 0
    total_start = time.perf_counter()

    try:
        session = requests.Session()
        session.headers.update(headers)

        while redirect_count <= max_redirects:
            req_start = time.perf_counter()
            response = session.get(
                current_target,
                timeout=timeout_seconds,
                allow_redirects=False,
                verify=True
            )
            req_duration = (time.perf_counter() - req_start) * 1000.0

            # Check if this is a redirect
            if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
                redirect_count += 1
                if redirect_count > max_redirects:
                    return {
                        'is_available': False,
                        'status_code': response.status_code,
                        'response_time_ms': round((time.perf_counter() - total_start) * 1000.0, 2),
                        'error_type': 'redirect_limit',
                        'error_message': 'Exceeded maximum allowable redirect hops (5).'
                    }

                location = response.headers.get('Location')
                if not location:
                    break

                next_url = urljoin(current_target, location)
                # Validate the redirect destination against SSRF policy
                next_valid, next_ip_err, next_err_type = validate_target_url(next_url, allow_localhost=allow_localhost)
                if not next_valid:
                    return {
                        'is_available': False,
                        'status_code': response.status_code,
                        'response_time_ms': round((time.perf_counter() - total_start) * 1000.0, 2),
                        'error_type': 'ssrf_redirect_blocked',
                        'error_message': f'Redirect to private/restricted target blocked: {next_ip_err}'
                    }
                current_target = next_url
                continue
            else:
                # Terminal response reached
                break

        total_elapsed_ms = round((time.perf_counter() - total_start) * 1000.0, 2)
        status_code = response.status_code

        if status_code in expected_codes:
            return {
                'is_available': True,
                'status_code': status_code,
                'response_time_ms': total_elapsed_ms,
                'error_type': 'none',
                'error_message': None
            }
        else:
            return {
                'is_available': False,
                'status_code': status_code,
                'response_time_ms': total_elapsed_ms,
                'error_type': 'http_error',
                'error_message': f'HTTP status {status_code} does not match expected status codes {expected_codes}.'
            }

    except requests.exceptions.SSLError as e:
        return {
            'is_available': False,
            'status_code': None,
            'response_time_ms': round((time.perf_counter() - total_start) * 1000.0, 2),
            'error_type': 'ssl_error',
            'error_message': f'TLS/SSL Certificate validation failed: {str(e)}'
        }
    except requests.exceptions.Timeout as e:
        return {
            'is_available': False,
            'status_code': None,
            'response_time_ms': round(timeout_seconds * 1000.0, 2),
            'error_type': 'timeout',
            'error_message': f'Request timed out after {timeout_seconds} seconds.'
        }
    except requests.exceptions.ConnectionError as e:
        err_str = str(e)
        if 'getaddrinfo failed' in err_str or 'Name or service not known' in err_str:
            err_type = 'dns_error'
            err_msg = f'DNS resolution error: {err_str}'
        else:
            err_type = 'connection_error'
            err_msg = f'Failed to establish network connection: {err_str}'
        return {
            'is_available': False,
            'status_code': None,
            'response_time_ms': round((time.perf_counter() - total_start) * 1000.0, 2),
            'error_type': err_type,
            'error_message': err_msg[:500]
        }
    except Exception as e:
        return {
            'is_available': False,
            'status_code': None,
            'response_time_ms': round((time.perf_counter() - total_start) * 1000.0, 2),
            'error_type': 'unknown_error',
            'error_message': f'Monitoring check failed: {str(e)}'[:500]
        }

def check_website(website_id: int) -> dict:
    """Check a specific website by ID, save log, update status, and handle incidents."""
    website = db.session.get(Website, website_id)
    if not website:
        return None

    # Check if localhost testing is permitted via config or env
    allow_localhost = False
    if current_app:
        allow_localhost = current_app.config.get('ALLOW_LOCALHOST_MONITORING', False)
    if not allow_localhost:
        allow_localhost = os.environ.get('ALLOW_LOCALHOST_MONITORING', 'false').lower() in ('true', '1', 'yes')

    result = execute_single_check(
        url=website.url,
        timeout_seconds=website.timeout_seconds,
        expected_codes=website.expected_status_list,
        allow_localhost=allow_localhost
    )

    now = utc_now()

    # Record monitoring log
    log = MonitoringLog(
        website_id=website.id,
        checked_at=now,
        is_available=result['is_available'],
        status_code=result['status_code'],
        response_time_ms=result['response_time_ms'],
        error_type=result['error_type'],
        error_message=result['error_message']
    )
    db.session.add(log)

    # Update website record state
    website.last_checked_at = now
    website.last_response_time_ms = result['response_time_ms']
    website.last_status_code = result['status_code']
    website.last_error_message = result['error_message']

    if result['is_available']:
        website.current_status = 'operational'
        website.consecutive_failures = 0
    else:
        website.current_status = 'unavailable'
        website.consecutive_failures += 1

    website.updated_at = now
    db.session.commit()

    # Trigger incident state machine & notifications
    handle_monitoring_result(website, result)

    return result

def run_all_checks():
    """Execute check on all active monitors."""
    websites = Website.query.filter_by(is_active=True).all()
    results = {}
    for website in websites:
        try:
            results[website.id] = check_website(website.id)
        except Exception as e:
            results[website.id] = {'error': str(e)}
    return results
