import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient
from web_service.server import create_web_app
from models.models import get_session, User


def run():
    app = create_web_app()
    client = TestClient(app)

    # ensure user absent
    from core.config import settings
    username = settings.WEB_ADMIN_USERNAME or ''
    password = settings.WEB_ADMIN_PASSWORD or ''
    assert username and password, 'WEB_ADMIN_USERNAME/WEB_ADMIN_PASSWORD must be set in settings or .env'
    with get_session() as s:
        u = s.query(User).filter(User.username == username).first()
        if u:
            s.delete(u)
            s.commit()

    # JSON login
    r = client.post('/login', json={'username': username, 'password': password}, headers={'Accept': 'application/json'})
    print('Login POST:', r.status_code, r.json())
    assert r.status_code == 200 and r.json().get('success') is True

    # access protected api
    r2 = client.get('/api/stats/overview', headers={'Accept': 'application/json'})
    print('Overview:', r2.status_code)
    assert r2.status_code == 200


if __name__ == '__main__':
    run()
