from django.contrib import admin
from markdownx.admin import MarkdownxModelAdmin  # type: ignore

from page_fragments.models import PageFragment


@admin.register(PageFragment)
class PageFragmentAdmin(MarkdownxModelAdmin):
    list_display = ("identifier", "get_summary_nl", "get_summary_en", "get_summary_fr")

    @staticmethod
    def summarize_str(str):
        return (str[:75] + "...") if len(str) > 75 else str

    @admin.action(description="Content NL")
    def get_summary_nl(self, obj):
        return self.summarize_str(obj.content_nl)

    @admin.action(description="Content EN")
    def get_summary_en(self, obj):
        return self.summarize_str(obj.content_en)

    @admin.action(description="Content FR")
    def get_summary_fr(self, obj):
        return self.summarize_str(obj.content_fr)
