from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Species, Occurrence, DataImport, User, Dataset, OccurrenceComment

admin.site.site_header = "LIFE RIPARIAS early warning administration"


@admin.register(User)
class RipariasUserAdmin(UserAdmin):
    pass


class OccurrenceCommentInline(admin.TabularInline):
    model = OccurrenceComment


@admin.register(Occurrence)
class OccurrenceAdmin(admin.ModelAdmin):
    list_display = ("stable_id", "date", "species", "source_dataset")
    list_filter = ["data_import"]
    inlines = [
        OccurrenceCommentInline,
    ]


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    pass


@admin.register(DataImport)
class DataImportAdmin(admin.ModelAdmin):
    list_display = ("pk", "start", "imported_occurrences_counter")


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    pass
