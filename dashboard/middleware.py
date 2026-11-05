from django.conf import settings
from django.middleware.locale import LocaleMiddleware
from django.utils import translation
from django.utils.translation.trans_real import parse_accept_lang_header

from dashboard.utils import enabled_language


class EnabledLanguagesLocaleMiddleware(LocaleMiddleware):
    """LocaleMiddleware restricted to GBIF_ALERT["ENABLED_LANGUAGES"].

    Django negotiates against settings.LANGUAGES, every language this version
    supports. Here the language cookie and Accept-Language are tried the same
    way, but a language the site has not enabled is skipped (#513). Responses
    are handled by LocaleMiddleware (Content-Language, Vary). This project uses
    no i18n_patterns, so the URL path is not checked.
    """

    def process_request(self, request):
        accept = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
        translation.activate(
            enabled_language(
                request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME),
                *(lang for lang, _q in parse_accept_lang_header(accept)),
            )
        )
        request.LANGUAGE_CODE = translation.get_language()
