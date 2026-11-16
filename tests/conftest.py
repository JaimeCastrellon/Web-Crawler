import httpx
import pytest


@pytest.fixture(autouse=True)
def block_network(request, monkeypatch):
    """Offline tests must provide a MockTransport instead of making real requests."""
    if request.node.get_closest_marker("live"):
        return

    def blocked(*args, **kwargs):
        raise AssertionError("network access is forbidden in offline tests")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)
