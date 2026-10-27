# This is a simple Django app that allows to define simple page fragments in templates (a piece of Markdown, per
# language) and configure them in the Django Admin.
#
# This simple approach allows us to avoid bloated CMSes
# This app relies on Django-Markdownx
#
# Setup:
#   - add to `INSTALLED_APPS`
#   - add `modeltranslation` to `INSTALLED_APPS`: `content` is translated per language in settings.LANGUAGES, and
#     falls back to the default language (the first one) when a fragment is not translated yet.
#   - make sure 'django.middleware.locale.LocaleMiddleware' is listed in the MIDDLEWARE settings.
#
# Mini-tutorial
# =============
#
# 1. Add a page fragment in your template:
#
#  {% load page_fragments %}
#  ...
#  <div>{% get_page_fragment 'welcome' %}</div>
#
# 2. In the Admin, create a fragment with the same name ('welcome') and fill the Markdown text. You can also create the
#    entries via other means: python console, fixtures, ... (PageFragment is just a regular Django model)
#
#
# - To add support for a language, add it to settings.LANGUAGES and run `makemigrations`.

from django.apps import AppConfig


class PageFragmentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "page_fragments"
