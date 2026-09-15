"""Runner-specific error types."""


class AuthorizationError(Exception):
    """All 12 preflight checks did not pass."""


class PreflightFailure(AuthorizationError):
    def __init__(
        self,
        failing_check: str,
        cause: Exception,
        completed_checks: tuple[str, ...],
        manifest_sha256: str,
        environment_record: dict[str, str],
    ) -> None:
        super().__init__(f"{failing_check}: {cause}")
        self.failing_check = failing_check
        self.cause = cause
        self.completed_checks = completed_checks
        self.manifest_sha256 = manifest_sha256
        self.environment_record = environment_record


class ReproducibilityError(Exception):
    """A deterministic rerun produced different core result hashes."""


class PerformanceQualificationError(Exception):
    """Pre-baseline synthetic performance qualification failed."""
