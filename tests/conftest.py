# tests/conftest.py
import pytest
import time

@pytest.fixture(autouse=True)
def rate_limit_guard(request):
    yield
    if request.node.get_closest_marker("integration"):
        time.sleep(5)