import os

# Override DATABASE_URL before any app imports
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest  # noqa: E402

from app.database import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
