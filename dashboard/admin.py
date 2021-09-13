from django.contrib import admin

from .models import Species, Occurrence, DataImport

admin.site.site_header = "LIFE RIPARIAS early warning administration"


@admin.register(Occurrence)
class OccurrenceAdmin(admin.ModelAdmin):
    list_filter = ["data_import"]


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    pass


@admin.register(DataImport)
class DataImportAdmin(admin.ModelAdmin):
    pass
