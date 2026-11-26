#!/usr/bin/env python3
"""
Controlled HTTP Test Server for Academic Demonstrations & Automated Testing.
Simulates HTTP 200 success, HTTP 503 outage, slow responses, and outage recovery.
"""
import time
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from urllib.parse import urlparse, parse_qs

# Mutable server state for simulating dynamic recovery
STATE = {
    'status_code': 200,
    'latency_seconds': 0.0,
    'message': 'Service operational'
}

class TestServerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Keep test server output clean and concise
        print(f"[TestServer] {self.address_string()} - {format % args}")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path in ('/', '/health', '/success'):
            self.send_response_json(200, {'status': 'healthy', 'message': 'System operational'})
        elif path == '/fail' or path == '/503':
            self.send_response_json(503, {'status': 'error', 'message': 'Simulated service outage'})
        elif path == '/slow':
            delay = float(query.get('delay', [2.5])[0])
            time.sleep(delay)
            self.send_response_json(200, {'status': 'slow', 'delay_seconds': delay})
        elif path == '/dynamic':
            # Returns whatever current state is configured
            if STATE['latency_seconds'] > 0:
                time.sleep(STATE['latency_seconds'])
            self.send_response_json(STATE['status_code'], {'status': 'dynamic', 'state': STATE})
        elif path == '/simulate/down':
            STATE['status_code'] = 503
            STATE['message'] = 'Simulated incident started'
            self.send_response_json(200, {'message': 'State updated: Simulating 503 outage', 'state': STATE})
        elif path == '/simulate/recover':
            STATE['status_code'] = 200
            STATE['message'] = 'Simulated incident recovered'
            self.send_response_json(200, {'message': 'State updated: Service recovered (200 OK)', 'state': STATE})
        elif path == '/simulate/slow':
            STATE['latency_seconds'] = 3.0
            self.send_response_json(200, {'message': 'State updated: Injected 3.0s latency', 'state': STATE})
        elif path == '/simulate/reset':
            STATE['status_code'] = 200
            STATE['latency_seconds'] = 0.0
            STATE['message'] = 'Service operational'
            self.send_response_json(200, {'message': 'State reset to normal', 'state': STATE})
        else:
            self.send_response_json(404, {'status': 'not_found', 'message': f'Route {path} not recognized'})

    def send_response_json(self, status_code: int, data: dict):
        body = json.dumps(data, indent=2).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

def run_server(port: int = 8085):
    server_address = ('127.0.0.1', port)
    httpd = HTTPServer(server_address, TestServerHandler)
    print(f"================================================================")
    print(f" Controlled Academic Test Server Running on http://127.0.0.1:{port}")
    print(f" Endpoints available:")
    print(f"   - http://127.0.0.1:{port}/health          -> HTTP 200 OK")
    print(f"   - http://127.0.0.1:{port}/fail            -> HTTP 503 Service Unavailable")
    print(f"   - http://127.0.0.1:{port}/slow            -> Delayed response (2.5s)")
    print(f"   - http://127.0.0.1:{port}/dynamic         -> Dynamic state check")
    print(f"   - http://127.0.0.1:{port}/simulate/down   -> Trigger simulated outage")
    print(f"   - http://127.0.0.1:{port}/simulate/recover-> Trigger recovery to 200")
    print(f"================================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nTest server stopping...")
        httpd.server_close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run controlled test server for uptime monitoring demonstration.")
    parser.add_argument('--port', type=int, default=8085, help='Port to bind (default 8085)')
    args = parser.parse_args()
    run_server(args.port)
