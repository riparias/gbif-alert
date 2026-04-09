"""Views that return HTML pages"""
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpRequest,
    HttpResponse,
)
from django.shortcuts import render, get_object_or_404

from dashboard.models import Alert
from dashboard.views.helpers import (
    AuthenticatedHttpRequest,
)


def spa_shell(request: HttpRequest, **kwargs) -> HttpResponse:
    """Serve the Vue SPA shell for all Vue Router-managed routes."""
    return render(request, "dashboard/base.html")


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
def alert_edit_page(
    request: AuthenticatedHttpRequest, alert_id: int
) -> HttpResponse:
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
def area_editor_edit_page(request: AuthenticatedHttpRequest, area_id: int) -> HttpResponse:
    return spa_shell(request)
