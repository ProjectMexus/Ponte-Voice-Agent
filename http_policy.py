"""Shared outbound policy for explicitly configured model and backend endpoints."""
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener


class FixedEndpointRedirectHandler(HTTPRedirectHandler):
    """Fail closed on redirects instead of forwarding credentials or changing hosts."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fixed_endpoint_opener():
    """Use only the configured endpoint, without environment proxy interception."""
    return build_opener(ProxyHandler({}), FixedEndpointRedirectHandler())
