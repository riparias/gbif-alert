from django.contrib import admin
from markdownx.admin import MarkdownxModelAdmin  # type: ignore

from page_fragments.models import PageFragment


@admin.register(PageFragment)
class PageFragmentAdmin(MarkdownxModelAdmin):
    list_display = ("identifier", "get_summary_nl", "get_summary_en", "get_summary_fr")
    readonly_fields = ("updated_at",)

    @staticmethod
    def summarize_str(string: str) -> str:
        return (string[:75] + "...") if len(string) > 75 else string

    @admin.display(description="Content NL")
    def get_summary_nl(self, obj) -> str:
        return self.summarize_str(obj.content_nl)

    @admin.display(description="Content EN")
    def get_summary_en(self, obj) -> str:
        return self.summarize_str(obj.content_en)

    @admin.display(description="Content FR")
    def get_summary_fr(self, obj) -> str:
        return self.summarize_str(obj.content_fr)
