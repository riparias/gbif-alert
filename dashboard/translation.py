from modeltranslation.translator import register, TranslationOptions

from dashboard.models import Species


@register(Species)
class SpeciesTranslationOptions(TranslationOptions):
    fields = ("vernacular_name",)
