"""Views that return HTML pages"""
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpRequest,
    HttpResponse,
)
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.translation import gettext as _

from dashboard.forms import (
    SignUpForm,
    EditProfileForm,
)
from dashboard.models import DataImport, Alert
from dashboard.views.helpers import (
    AuthenticatedHttpRequest,
)


def spa_shell(request: HttpRequest, **kwargs) -> HttpResponse:
    """Serve the Vue SPA shell for all Vue Router-managed routes."""
    return render(request, "dashboard/base.html")


def index_page(request: HttpRequest) -> HttpResponse:
    return spa_shell(request)


def about_site_page(request: HttpRequest) -> HttpResponse:
    return render(request, "dashboard/about_site.html")


def about_data_page(request: HttpRequest) -> HttpResponse:
    data_imports = DataImport.objects.all().order_by("-start")
    return render(request, "dashboard/about_data.html", {"data_imports": data_imports})


def news_page(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        request.user.mark_news_as_visited_now()

    return render(request, "dashboard/news.html")


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
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            raw_password = form.cleaned_data.get("password1")
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect("dashboard:pages:index")
    else:
        form = SignUpForm()
    return render(request, "dashboard/user_signup.html", {"form": form})


@login_required
def user_profile_page(request: AuthenticatedHttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = EditProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, _("Your profile was successfully updated."))
            return redirect("dashboard:pages:index")
    else:
        form = EditProfileForm(instance=request.user)
    return render(request, "dashboard/user_profile.html", {"form": form})


@login_required
def user_alerts_page(request: AuthenticatedHttpRequest) -> HttpResponse:
    return spa_shell(request)


@login_required
def user_areas_page(request: AuthenticatedHttpRequest) -> HttpResponse:
    return spa_shell(request)
