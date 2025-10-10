

class CallListException(Exception):
    def __init__(self, *args):
        super(CallListException, self).__init__(*args)
        self.error = args[0] if args else None

    def dict(self):
        if isinstance(self.error, dict):
            return self.error
        return dict(error=self.error)


class BitrixApiError(Exception):
    def __init__(self, status_code: int, json_response=None, message: str = ""):
        super().__init__(message or f"Bitrix API error {status_code}")
        self.status_code = status_code
        self.json_response = json_response or {}

class ExpiredToken(Exception):
    """Маркер для 401 expired_token, чтобы BitrixUserToken мог перезапросить токен и повторить вызов."""
    pass

class PermissionDenied(Exception):
    """403 — нет прав/не передан AUTH_ID."""
    pass