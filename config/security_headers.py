"""Custom middleware to attach explicit security headers."""

from django.conf import settings


class SecurityHeadersMiddleware:
    """Attach CSP and additional security headers to each response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # CSP is intentionally managed at Nginx layer as single source of truth.
        response.setdefault('Referrer-Policy', self._setting('SECURE_REFERRER_POLICY'))
        response.setdefault('X-Content-Type-Options', 'nosniff')
        response.setdefault('X-Frame-Options', 'DENY')

        return response

    @staticmethod
    def _setting(key):
        return getattr(settings, key)
