from django.contrib import admin

from .models import Species, Occurrence

admin.site.site_header = 'Riparias early warning administration'


@admin.register(Occurrence)
class OccurrenceAdmin(admin.ModelAdmin):
    pass


@admin.register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    pass
