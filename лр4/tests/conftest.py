from pathlib import Path
from uuid import uuid4

import pytest

from app import create_app
from app.db import get_db


@pytest.fixture
def app():
    test_db_dir = Path.cwd() / "test_dbs"
    test_db_dir.mkdir(exist_ok=True)
    database = test_db_dir / f"{uuid4().hex}.sqlite"

    app = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test",
            "DATABASE": str(database),
        }
    )

    yield app

    if database.exists():
        database.unlink()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth(client):
    class AuthActions:
        def login(self, login="admin", password="Admin123!"):
            return client.post(
                "/auth/login",
                data={"login": login, "password": password},
                follow_redirects=True,
            )

        def logout(self):
            return client.get("/auth/logout", follow_redirects=True)

    return AuthActions()


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()
