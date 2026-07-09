from modeltranslation.translator import register, TranslationOptions  # type: ignore

from dashboard.models import AlertTemplate, Species


@register(Species)
class SpeciesTranslationOptions(TranslationOptions):
    fields = ("vernacular_name",)  # type: ignore


@register(AlertTemplate)
class AlertTemplateTranslationOptions(TranslationOptions):
    fields = ("name", "description")  # type: ignore
