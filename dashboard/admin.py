from django.contrib.gis import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Species,
    Occurrence,
    DataImport,
    User,
    Dataset,
    OccurrenceComment,
    Area,
    OccurrenceView,
)

admin.site.site_header = "LIFE RIPARIAS early warning administration"


@admin.register(User)
class RipariasUserAdmin(UserAdmin):
    pass


class OccurrenceCommentInline(admin.TabularInline):
    model = OccurrenceComment


class OccurrenceViewInline(admin.TabularInline):
    model = OccurrenceView
    readonly_fields = ["user", "timestamp"]

    # Make that inline read-only
    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Occurrence)
class OccurrenceAdmin(admin.OSMGeoAdmin):
    list_display = ("stable_id", "date", "species", "source_dataset")
    list_filter = ["data_import"]
    inlines = [OccurrenceCommentInline, OccurrenceViewInline]


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    pass


@admin.register(DataImport)
class DataImportAdmin(admin.ModelAdmin):
    list_display = ("pk", "start", "imported_occurrences_counter")


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    pass


@admin.register(Area)
class AreaAdmin(admin.OSMGeoAdmin):
    list_display = ("name", "owner")
