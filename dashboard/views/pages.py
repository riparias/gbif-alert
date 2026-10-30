"""Views that return HTML pages"""
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpRequest,
    HttpResponse,
)
from django.shortcuts import redirect, render, get_object_or_404
from django.templatetags.static import static
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from maintenance_mode.decorators import force_maintenance_mode_off  # type: ignore

from dashboard.models import Alert, SiteIcon
from dashboard.views.helpers import (
    AuthenticatedHttpRequest,
)


@ensure_csrf_cookie
def spa_shell(request: HttpRequest, **kwargs) -> HttpResponse:
    """Serve the Vue SPA shell for all Vue Router-managed routes.

    The csrftoken cookie is forced on every response so the Vue navbar
    (and any other client-side form) can read it from document.cookie
    even on a fresh visit with no prior cookies.
    """
    return render(request, "dashboard/base.html")


# `force_maintenance_mode_off`: the 503 page links to the icon too.
@force_maintenance_mode_off
@cache_control(public=True, max_age=86400)
def site_icon(request: HttpRequest) -> HttpResponse:
    """Serve the icon uploaded for this instance, or redirect to the default.

    Pages link to this fixed URL, so rendering them never queries the icon.
    """
    # ponytail: Cache-Control limits this to about one query per browser per
    # day. Add cache_page on top if it ever shows up as load.
    icon = SiteIcon.objects.first()
    if icon is None:
        return redirect(static("site-icon-default.png"))
    return HttpResponse(icon.png, content_type="image/png")


def index_page(request: HttpRequest) -> HttpResponse:
    return spa_shell(request)


def about_site_page(request: HttpRequest) -> HttpResponse:
    return spa_shell(request)


def about_data_page(request: HttpRequest) -> HttpResponse:
    return spa_shell(request)


def news_page(request: HttpRequest) -> HttpResponse:
    return spa_shell(request)


def observation_details_page(request: HttpRequest, stable_id: str) -> HttpResponse:
    return spa_shell(request)


@login_required
def alert_details_page(
    request: AuthenticatedHttpRequest, alert_id: int
) -> HttpResponse:
    get_object_or_404(Alert, id=alert_id, user=request.user)
    return spa_shell(request)


@login_required
def alert_create_page(request: AuthenticatedHttpRequest) -> HttpResponse:
    return spa_shell(request)


@login_required
def alert_edit_page(request: AuthenticatedHttpRequest, alert_id: int) -> HttpResponse:
    get_object_or_404(Alert, id=alert_id, user=request.user)
    return spa_shell(request)


def user_signup_page(request: HttpRequest) -> HttpResponse:
    return spa_shell(request)


@login_required
def user_profile_page(request: AuthenticatedHttpRequest) -> HttpResponse:
    return spa_shell(request)


@login_required
def user_alerts_page(request: AuthenticatedHttpRequest) -> HttpResponse:
    return spa_shell(request)


@login_required
def user_areas_page(request: AuthenticatedHttpRequest) -> HttpResponse:
    return spa_shell(request)


@login_required
def area_editor_new_page(request: AuthenticatedHttpRequest) -> HttpResponse:
    return spa_shell(request)


@login_required
def area_editor_edit_page(
    request: AuthenticatedHttpRequest, area_id: int
) -> HttpResponse:
    return spa_shell(request)
