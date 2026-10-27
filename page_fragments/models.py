from django.db import models
from markdownx.models import MarkdownxField  # type: ignore

NEWS_PAGE_IDENTIFIER = "news_page_content"


class PageFragment(models.Model):
    """A piece of Markdown shown on the site, identified by `identifier`.

    `content` is translated with django-modeltranslation (see translation.py):
    there is one content_<lang> column per language in settings.LANGUAGES, and
    reading `content` returns the active language's text, falling back to the
    default language (English) when it is empty.
    """

    # modeltranslation swaps this for its MultilingualManager at runtime, which
    # django-stubs cannot resolve (same idiom as AlertTemplate).
    objects = models.Manager()  # type: ignore[django-manager-missing]

    identifier = models.SlugField(unique=True)
    # Not blank: the modeltranslation admin then requires the default language,
    # which every other language falls back to.
    content = MarkdownxField()

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.identifier
