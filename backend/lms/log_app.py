import logging
import os
from django.conf import settings

LOG_DIR = os.path.join(settings.BASE_DIR, "app_logs")
os.makedirs(LOG_DIR, exist_ok=True)

formatter = logging.Formatter(
    "%(levelname)s | %(asctime)s | %(name)s | %(message)s"
)


info_handler = logging.FileHandler(os.path.join(LOG_DIR, "info.log"))
info_handler.setLevel(logging.INFO)
info_handler.setFormatter(formatter)

warning_handler = logging.FileHandler(os.path.join(LOG_DIR, "warning.log"))
warning_handler.setLevel(logging.WARNING)
warning_handler.setFormatter(formatter)

error_handler = logging.FileHandler(os.path.join(LOG_DIR, "error.log"))
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)



loggers = logging.getLogger("app_logger")
loggers.setLevel(logging.INFO)

loggers.addHandler(info_handler)
loggers.addHandler(warning_handler)
loggers.addHandler(error_handler)
loggers.addHandler(console_handler)

loggers.propagate = False
