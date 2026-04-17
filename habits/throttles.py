"""API throttle classes for auth-sensitive endpoints."""

from rest_framework.throttling import ScopedRateThrottle


class LoginRateThrottle(ScopedRateThrottle):
    """Throttle login attempts to reduce brute-force risk."""

    scope = 'auth_login'


class RegisterRateThrottle(ScopedRateThrottle):
    """Throttle registration attempts to reduce abuse."""

    scope = 'auth_register'
