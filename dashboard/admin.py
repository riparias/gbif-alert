from django.contrib.gis import admin
from django.contrib.auth.admin import UserAdmin
from import_export import resources
from import_export.admin import ImportExportModelAdmin

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

admin.site.site_header = "LIFE RIPARIAS early warning administration"


@admin.register(User)
class RipariasUserAdmin(UserAdmin):
    pass


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
    list_filter = ["data_import"]
    inlines = [ObservationCommentCommentInline, ObservationViewInline]


class SpeciesResource(resources.ModelResource):
    class Meta:
        model = Species


@admin.register(Species)
class SpeciesAdmin(ImportExportModelAdmin):
    resource_class = SpeciesResource


@admin.register(DataImport)
class DataImportAdmin(admin.ModelAdmin):
    list_display = ("pk", "start", "imported_observations_counter")


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    pass


@admin.register(Area)
class AreaAdmin(admin.OSMGeoAdmin):
    list_display = ("name", "owner")


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    pass
