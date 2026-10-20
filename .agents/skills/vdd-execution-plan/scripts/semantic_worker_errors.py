"""ADR-0041: transport failures are not malformed semantic output."""

class WorkerTransportError(RuntimeError):
    def __init__(self, stage, category, attempts, detail):
        self.stage = stage
        self.category = category
        self.attempts = attempts
        super().__init__(f"semantic worker {stage} transport {category} after {attempts} attempt(s): {detail}")
