from django.contrib import admin
from markdownx.admin import MarkdownxModelAdmin  # type: ignore
from modeltranslation.admin import TranslationAdmin  # type: ignore

from page_fragments.models import PageFragment


@admin.register(PageFragment)
class PageFragmentAdmin(TranslationAdmin, MarkdownxModelAdmin):  # type: ignore[misc]
    list_display = ("identifier", "get_summary")
    readonly_fields = ("updated_at",)

    @admin.display(description="Content")
    def get_summary(self, obj) -> str:
        return (obj.content[:75] + "...") if len(obj.content) > 75 else obj.content
