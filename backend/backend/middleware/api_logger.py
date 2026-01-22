import time
from lms.log_app import loggers


class APILoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()

        try:
            response = self.get_response(request)
            status_code = response.status_code

        except Exception:
            status_code = 500
            loggers.error(
                f"API Exception | {request.method} {request.path}",
                exc_info=True
            )
            raise

        duration = round(time.time() - start_time, 3)

        user = (
            request.user.username
            if hasattr(request, "user") and request.user.is_authenticated
            else "Anonymous"
        )

        loggers.info(
            f"{request.method} {request.path} | "
            f"User: {user} | "
            f"Status: {status_code} | "
            f"Duration: {duration}s"
        )

        return response
