import os

# pytest-playwright installs an asyncio event loop at session scope.
# Django detects it and refuses synchronous DB operations by default.
# This flag disables that guard - safe in a test context.
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "1"
