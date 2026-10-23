from .base import *  # noqa: F403

# Hashing passwords properly is slow on purpose; tests don't need that.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
STORAGES["staticfiles"]["BACKEND"] = "django.contrib.staticfiles.storage.StaticFilesStorage"  # noqa: F405
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []  # noqa: F405
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["demo"] = None  # noqa: F405
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["password_reset"] = None  # noqa: F405
# Run Celery tasks inline, so code that calls .delay() can be tested without a broker.
CELERY_TASK_ALWAYS_EAGER = True
# No collected static files in tests, so WhiteNoise would only warn.
MIDDLEWARE = [m for m in MIDDLEWARE if m != "whitenoise.middleware.WhiteNoiseMiddleware"]  # noqa: F405
