from ninja import NinjaAPI

# Internal API v2 - powered by Django Ninja.
# This replaces the old internal-api/ endpoints incrementally (Phase 2+).
# The public api/ endpoints are left unchanged.
api_v2 = NinjaAPI(urls_namespace="api-v2")
