from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dashboard"

    def ready(self):
        # Imported here, not at module level: the checks import models, which
        # cannot be loaded before the app registry is ready.
        from django.core.checks import register

        from dashboard.checks import check_areas_have_parts, check_download_geometry

        register(check_areas_have_parts)
        register(check_download_geometry)
