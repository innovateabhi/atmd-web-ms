# System Architecture & Technical Specifications

This document outlines the architecture, data pipeline, and security model of the **Linux Automated Website Uptime Monitoring System**.

## 1. High-Level Architecture

The system decouples the presentation tier (Flask web application served by Gunicorn and reverse-proxied by Nginx) from the monitoring evaluation tier (APScheduler background worker daemon). Both processes interact with an embedded SQLite database configured in Write-Ahead Logging (WAL) mode.

```
 +----------------------------------------------------------------------+
 |                          Client Web Browser                          |
 +----------------------------------------------------------------------+
                                    | HTTP / Port 80
                                    v
 +----------------------------------------------------------------------+
 |                             Nginx                                    |
 |           - Serves static assets (/static/) directly                 |
 |           - Reverse proxies dynamic requests to Gunicorn             |
 +----------------------------------------------------------------------+
                                    | Reverse Proxy (127.0.0.1:8000)
                                    v
 +----------------------------------------------------------------------+
 |                    Gunicorn WSGI Application                         |
 |                       (Flask Web Server)                             |
 |       - Session Authentication & RBAC                                |
 |       - Overview Dashboard & Live Telemetry APIs                     |
 |       - Monitor CRUD & Manual Check Triggers                         |
 |       - CSV Analytics & Report Exporters                             |
 +----------------------------------------------------------------------+
                                    |
                                    v
 +----------------------------------------------------------------------+
 |                        SQLite 3 Database                             |
 |                   (WAL Mode, Foreign Keys On)                        |
 +----------------------------------------------------------------------+
                                    ^
                                    | Reads targets / Writes check logs
 +----------------------------------------------------------------------+
 |                 APScheduler Monitoring Worker Daemon                 |
 |                  (Standalone Python Background Unit)                 |
 |       - Non-blocking ThreadPoolExecutor                              |
 |       - Per-target Concurrency Locks (Zero overlap)                  |
 |       - SSRF-safe Network Evaluation & Redirect Inspector            |
 |       - Incident State Machine & Downtime Duration Tracker           |
 |       - Optional SMTP Alert Dispatcher                               |
 +----------------------------------------------------------------------+
```

## 2. Decoupled Process Model

Running background scheduling inside Gunicorn WSGI workers causes duplicate triggers when Gunicorn forks multiple worker processes. By isolating the scheduler into a dedicated systemd service (`uptime-worker.service`), monitoring intervals remain strict, reliable, and immune to web traffic fluctuations.

## 3. Concurrency & Overlap Prevention

When a monitored endpoint experiences extreme latency or a stalled connection, subsequent scheduled checks could pile up. The worker implements an in-memory lock registry:

1. When a monitor becomes due, its ID is placed in `_active_checks`.
2. Any subsequent dispatcher cycle checks if the target is already in `_active_checks`. If true, the check is skipped and a warning is logged.
3. Upon check completion or error handling in `finally`, the lock is discarded.

## 4. SSRF Defense Matrix

To defend host infrastructure in multi-tenant or enterprise environments:
- Schemes are strictly restricted to `http` and `https`.
- Hostnames are resolved through DNS and IP addresses are evaluated against IPv4/IPv6 private, loopback, link-local, and multicast ranges.
- Redirects are not blindly followed: each hop is inspected and validated before making outbound requests.
- For controlled academic demonstrations, `ALLOW_LOCALHOST_MONITORING=true` can be enabled in `.env`.
