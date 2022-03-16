from django import template
from django.utils.safestring import mark_safe
from markdownx.utils import markdownify  # type: ignore

from page_fragments.models import PageFragment

register = template.Library()


@register.simple_tag(takes_context=True)
def get_page_fragment(context, identifier):
    """Return rendered HTML for the page fragment with identifier, in the current language"""

    fragment = PageFragment.objects.get(identifier=identifier)

    return mark_safe(
        markdownify(fragment.get_content_in(context.request.LANGUAGE_CODE))
    )
