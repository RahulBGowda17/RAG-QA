import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from run import create_app
from app.database import init_db


@pytest.fixture(scope="session")
def app():
    test_app = create_app()
    test_app.config["TESTING"] = True
    with test_app.app_context():
        init_db()
    return test_app


@pytest.fixture
def client(app):
    return app.test_client()
