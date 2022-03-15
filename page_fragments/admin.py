from django.contrib import admin
from markdownx.admin import MarkdownxModelAdmin

from page_fragments.models import PageFragment


@admin.register(PageFragment)
class PageFragmentAdmin(MarkdownxModelAdmin):
    list_display = ("identifier", "get_summary_nl", "get_summary_en", "get_summary_fr")

    @staticmethod
    def summarize_str(str):
        return (str[:75] + "...") if len(str) > 75 else str

    def get_summary_nl(self, obj):
        return self.summarize_str(obj.content_nl)

    get_summary_nl.short_description = "Content NL"

    def get_summary_en(self, obj):
        return self.summarize_str(obj.content_en)

    get_summary_en.short_description = "Content EN"

    def get_summary_fr(self, obj):
        return self.summarize_str(obj.content_fr)

    get_summary_fr.short_description = "Content FR"
