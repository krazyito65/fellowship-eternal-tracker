import pytest
import os

@pytest.fixture(scope="session")
def server_url():
    port = os.environ.get("PORT", 8099)
    yield f"http://localhost:{port}"
