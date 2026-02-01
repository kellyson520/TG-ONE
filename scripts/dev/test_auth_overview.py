import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from web_admin.app import app


def run():
    client = app.test_client()

    r1 = client.get('/api/stats/overview', headers={'Accept': 'application/json'})
    print('Unauthenticated /api/stats/overview:', r1.status_code)
    assert r1.status_code == 401, f'Expected 401, got {r1.status_code}'

    from core.config import settings
    username = settings.WEB_ADMIN_USERNAME or ''
    password = settings.WEB_ADMIN_PASSWORD or ''
    assert username and password, 'WEB_ADMIN_USERNAME/WEB_ADMIN_PASSWORD must be set in settings or .env'

    # JSON 登录流程，验证 200 + Set-Cookie
    r2 = client.post('/login', json={'username': username, 'password': password}, follow_redirects=False, headers={'Accept': 'application/json'})
    print('Login POST:', r2.status_code)
    assert r2.status_code == 200, f'Expected 200 after JSON login, got {r2.status_code}'

    r3 = client.get('/api/stats/overview', headers={'Accept': 'application/json'})
    print('Authenticated /api/stats/overview:', r3.status_code)
    assert r3.status_code == 200, f'Expected 200, got {r3.status_code}'
    print('Mimetype:', r3.mimetype)
    js = r3.get_json(silent=True)
    if not isinstance(js, dict):
        print('Body length:', len(r3.data))
        print('Body sample:', r3.data[:500])
    assert isinstance(js, dict), 'Invalid JSON body'
    print('JSON keys:', list(js.keys()))
    # 接受两种结构：{'success': True, 'data': ...} 或直接数据结构
    assert (js.get('success') is True) or ('overview' in (js.get('data') or js)), 'Missing expected fields'


if __name__ == '__main__':
    run()
