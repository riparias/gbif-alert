from modeltranslation.translator import register, TranslationOptions  # type: ignore

from page_fragments.models import PageFragment


@register(PageFragment)
class PageFragmentTranslationOptions(TranslationOptions):
    fields = ("content",)  # type: ignore
