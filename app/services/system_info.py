import os
import time
import socket
import platform
import psutil

def format_uptime(seconds: int) -> str:
    """Format total uptime seconds into human-readable days, hours, minutes."""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts) or "0m"

def get_system_metrics() -> dict:
    """Collect real-time system performance and OS health indicators."""
    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.1)
    cpu_count_logical = psutil.cpu_count(logical=True)
    cpu_count_physical = psutil.cpu_count(logical=False) or cpu_count_logical

    # Memory
    mem = psutil.virtual_memory()
    ram_total_gb = round(mem.total / (1024 ** 3), 2)
    ram_used_gb = round(mem.used / (1024 ** 3), 2)
    ram_available_gb = round(mem.available / (1024 ** 3), 2)
    ram_percent = mem.percent

    # Disk
    root_path = '/' if platform.system() != 'Windows' else os.path.splitdrive(os.getcwd())[0] + '\\'
    try:
        disk = psutil.disk_usage(root_path)
        disk_total_gb = round(disk.total / (1024 ** 3), 2)
        disk_used_gb = round(disk.used / (1024 ** 3), 2)
        disk_free_gb = round(disk.free / (1024 ** 3), 2)
        disk_percent = disk.percent
    except Exception:
        disk_total_gb = disk_used_gb = disk_free_gb = disk_percent = 0.0

    # Boot time & system uptime
    boot_time = psutil.boot_time()
    uptime_seconds = int(time.time() - boot_time)
    uptime_str = format_uptime(uptime_seconds)

    # OS & Host
    hostname = socket.gethostname()
    os_name = f"{platform.system()} {platform.release()}"
    architecture = platform.machine()
    python_version = platform.python_version()

    # Load average if supported (Linux / Unix)
    load_avg = None
    if hasattr(os, 'getloadavg'):
        try:
            load_avg = [round(x, 2) for x in os.getloadavg()]
        except Exception:
            load_avg = None

    return {
        'hostname': hostname,
        'os_name': os_name,
        'architecture': architecture,
        'python_version': python_version,
        'cpu_percent': cpu_percent,
        'cpu_count_logical': cpu_count_logical,
        'cpu_count_physical': cpu_count_physical,
        'ram_total_gb': ram_total_gb,
        'ram_used_gb': ram_used_gb,
        'ram_available_gb': ram_available_gb,
        'ram_percent': ram_percent,
        'disk_total_gb': disk_total_gb,
        'disk_used_gb': disk_used_gb,
        'disk_free_gb': disk_free_gb,
        'disk_percent': disk_percent,
        'uptime_seconds': uptime_seconds,
        'uptime_formatted': uptime_str,
        'load_average': load_avg
    }
