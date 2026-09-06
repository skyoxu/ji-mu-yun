class IdempotencyLedger:
    def __init__(self):
        self._reservations = {}

    def _has_active_reservation(self, key, now):
        expires_at = self._reservations.get(key)
        return expires_at is not None and now < expires_at

    def claim(self, key, now, ttl_seconds):
        if ttl_seconds <= 0:
            return 'invalid-ttl'

        if self._has_active_reservation(key, now):
            return 'duplicate'

        self._reservations[key] = now + ttl_seconds
        return 'accepted'

    def release(self, key):
        if key not in self._reservations:
            return 'not-found'

        del self._reservations[key]
        return 'released'
