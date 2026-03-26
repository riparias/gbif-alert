"""Export the Django Ninja OpenAPI schema to a JSON file.

Used by the `generate-types` npm script to produce TypeScript types without
requiring the development server to be running.

Usage:
    DJANGO_SETTINGS_MODULE=djangoproject.local_settings python scripts/export_openapi_schema.py
"""

import json
import os
import sys

# Allow running from the project root without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoproject.local_settings")
django.setup()

from dashboard.api_v2 import api_v2  # noqa: E402 (import after django.setup())

output_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "openapi-schema.json"
)

with open(output_path, "w") as f:
    json.dump(api_v2.get_openapi_schema(), f, indent=2)

print(f"OpenAPI schema written to {output_path}")
