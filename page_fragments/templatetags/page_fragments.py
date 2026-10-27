from django import template
from django.utils.safestring import mark_safe
from markdownx.utils import markdownify  # type: ignore

from page_fragments.models import PageFragment

register = template.Library()


@register.simple_tag
def get_page_fragment(identifier):
    """Return rendered HTML for the page fragment with identifier, in the current language"""

    try:
        fragment = PageFragment.objects.get(identifier=identifier)

        return mark_safe(markdownify(fragment.content))
    except PageFragment.DoesNotExist:
        return ""
