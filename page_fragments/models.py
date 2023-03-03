from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from markdownx.models import MarkdownxField  # type: ignore

NEWS_PAGE_IDENTIFIER = "news_page_content"


class PageFragment(models.Model):
    identifier = models.SlugField(unique=True)
    content_nl = MarkdownxField(blank=True)
    content_en = MarkdownxField(blank=True)
    content_fr = MarkdownxField(blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.identifier

    @staticmethod
    def _get_content_field_name(language_code):
        return "content_{}".format(language_code)

    def get_content_in(self, language_code):
        # We try to get the content in language_code, but fallback to settings.PAGE_FRAGMENTS_FALLBACK_LANGUAGE if no
        # translation exists of if the requested language is not supported

        content_in_fallback_language = getattr(
            self,
            PageFragment._get_content_field_name(
                settings.PAGE_FRAGMENTS_FALLBACK_LANGUAGE
            ),
        )

        translated_content = getattr(
            self,
            PageFragment._get_content_field_name(language_code),
            content_in_fallback_language,
        )
        if translated_content == "":
            translated_content = content_in_fallback_language

        return translated_content

    def clean(self):
        fallback_language_code = settings.PAGE_FRAGMENTS_FALLBACK_LANGUAGE

        if (
            getattr(self, PageFragment._get_content_field_name(fallback_language_code))
            == ""
        ):
            raise ValidationError(
                "Content is mandatory for the fallback language ({})".format(
                    fallback_language_code
                )
            )
