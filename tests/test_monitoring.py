from unittest.mock import patch, MagicMock
import requests
from app.services.checker import execute_single_check

def test_check_success_200():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.is_redirect = False

    with patch('requests.Session.get', return_value=mock_resp):
        res = execute_single_check(
            url='http://127.0.0.1:8085/health',
            timeout_seconds=5,
            expected_codes=[200],
            allow_localhost=True
        )
        assert res['is_available'] is True
        assert res['status_code'] == 200
        assert res['error_type'] == 'none'
        assert res['response_time_ms'] is not None

def test_check_unexpected_http_status_503():
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.is_redirect = False

    with patch('requests.Session.get', return_value=mock_resp):
        res = execute_single_check(
            url='http://127.0.0.1:8085/health',
            timeout_seconds=5,
            expected_codes=[200],
            allow_localhost=True
        )
        assert res['is_available'] is False
        assert res['status_code'] == 503
        assert res['error_type'] == 'http_error'

def test_check_timeout():
    with patch('requests.Session.get', side_effect=requests.exceptions.Timeout("Connection timed out")):
        res = execute_single_check(
            url='http://127.0.0.1:8085/health',
            timeout_seconds=2,
            allow_localhost=True
        )
        assert res['is_available'] is False
        assert res['error_type'] == 'timeout'

def test_check_ssl_error():
    with patch('requests.Session.get', side_effect=requests.exceptions.SSLError("Certificate verify failed")):
        res = execute_single_check(
            url='http://127.0.0.1:8085/health',
            timeout_seconds=5,
            allow_localhost=True
        )
        assert res['is_available'] is False
        assert res['error_type'] == 'ssl_error'

def test_check_connection_error():
    with patch('requests.Session.get', side_effect=requests.exceptions.ConnectionError("Connection refused")):
        res = execute_single_check(
            url='http://127.0.0.1:8085/health',
            timeout_seconds=5,
            allow_localhost=True
        )
        assert res['is_available'] is False
        assert res['error_type'] == 'connection_error'
