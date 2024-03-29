from django.conf import settings
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.gis import admin
from import_export import resources  # type: ignore
from import_export.admin import ImportExportModelAdmin  # type: ignore
from modeltranslation.admin import TranslationAdmin  # type: ignore

from .models import (
    Species,
    Observation,
    DataImport,
    User,
    Dataset,
    ObservationComment,
    Area,
    ObservationView,
    Alert,
)

admin.site.site_header = f'{settings.GBIF_ALERT["SITE_NAME"]} administration'


@admin.register(User)
class GbifAlertUserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (  # type: ignore
        (
            "Custom fields",
            {
                "fields": ("last_visit_news_page", "language"),
            },
        ),
    )


class ObservationCommentCommentInline(admin.TabularInline):
    model = ObservationComment


class ObservationViewInline(admin.TabularInline):
    model = ObservationView
    readonly_fields = ["user", "timestamp"]

    # Make that inline read-only
    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Observation)
class ObservationAdmin(admin.OSMGeoAdmin):
    list_display = ("stable_id", "date", "species", "source_dataset")
    list_filter = ["data_import", "species"]
    search_fields = ["stable_id"]
    inlines = [ObservationCommentCommentInline, ObservationViewInline]


class SpeciesResource(resources.ModelResource):
    class Meta:
        model = Species


@admin.register(Species)
class SpeciesAdmin(ImportExportModelAdmin, TranslationAdmin):
    resource_class = SpeciesResource
    list_display = ("name", "vernacular_name", "gbif_taxon_key", "tag_list")
    search_fields = ["name", "vernacular_name", "gbif_taxon_key"]

    def tag_list(self, obj):
        return ", ".join(o.name for o in obj.tags.all())


@admin.register(DataImport)
class DataImportAdmin(admin.ModelAdmin):
    list_display = ("pk", "start", "imported_observations_counter")


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    pass


@admin.register(Area)
class AreaAdmin(admin.OSMGeoAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("tags")

    def tag_list(self, obj):
        return ", ".join(o.name for o in obj.tags.all())

    list_display = ("name", "owner", "tag_list")


# Beware: the following action is mostly for debugging purposes and will send an email if the usual criteria are not
# met, for example:
# - no unseen observations for the alert
# - the alert is configured for no email notifications
# - a notification e-mail has already been sent recently
@admin.action(description="Send e-mail notifications now for selected alerts")  # type: ignore
def send_alert_notification_email(_modeladmin, _request, queryset):
    for alert in queryset:
        alert.send_notification_email()


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "name",
        "unseen_observations_count",
        "species_list",
        "datasets_list",
        "areas_list",
        "email_notifications_frequency",
    )
    list_filter = ["user", "email_notifications_frequency"]

    actions = [send_alert_notification_email]


@admin.register(ObservationComment)
class ObservationCommentAdmin(admin.ModelAdmin):
    list_display = ("author", "observation")
    list_filter = ["author"]
    raw_id_fields = ("observation",)
