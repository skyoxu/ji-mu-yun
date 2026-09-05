class IdempotencyLedger:
    def claim(self, key, now, ttl_seconds):
        return 'accepted'

    def release(self, key):
        return 'released'
