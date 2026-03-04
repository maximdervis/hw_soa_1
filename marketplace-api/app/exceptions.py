"""API business exceptions."""


class ApiException(Exception):
    def __init__(self, error_code: str, message: str, details: dict | None = None):
        self.error_code = error_code
        self.message = message
        self.details = details
        super().__init__(message)
