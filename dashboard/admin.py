from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Species, Occurrence, DataImport, User

admin.site.site_header = "LIFE RIPARIAS early warning administration"


@admin.register(User)
class RipariasUserAdmin(UserAdmin):
    pass


@admin.register(Occurrence)
class OccurrenceAdmin(admin.ModelAdmin):
    list_filter = ["data_import"]


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    pass


@admin.register(DataImport)
class DataImportAdmin(admin.ModelAdmin):
    pass
