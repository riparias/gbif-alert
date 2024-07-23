from modeltranslation.translator import register, TranslationOptions  # type: ignore

from dashboard.models import Species


@register(Species)
class SpeciesTranslationOptions(TranslationOptions):
    fields = ("vernacular_name",)  # type: ignore
