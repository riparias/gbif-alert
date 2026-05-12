"""djangoproject URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include, re_path, reverse_lazy

from dashboard.api_v2 import api_v2
from dashboard.views.healthz import healthz
from dashboard.views.pages import spa_shell

urlpatterns = [
    path("api/v2/", api_v2.urls),
    path("", include("dashboard.urls")),
    # User accounts
    path("i18n/", include("django.conf.urls.i18n")),
    path("accounts/signin/", spa_shell, name="signin"),
    path("accounts/signout/", auth_views.LogoutView.as_view(), name="signout"),
    path(
        "accounts/password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="dashboard/password_reset.html",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path("accounts/password-change/", spa_shell, name="password_change"),
    path(
        "accounts/password-reset-done",
        auth_views.PasswordResetDoneView.as_view(
            template_name="dashboard/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="dashboard/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/done",
        auth_views.PasswordResetDoneView.as_view(
            template_name="dashboard/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("admin/", admin.site.urls),
    path("markdownx/", include("markdownx.urls")),
    path("django-rq/", include("django_rq.urls")),
    path("healthz", healthz, name="healthz"),
    # Catch-all for Vue Router history mode: any path not matched by an explicit
    # Django URL returns the SPA shell so Vue Router can handle direct-load navigation.
    # The negative lookahead excludes Django-owned prefixes so that paths like /admin
    # (without trailing slash) still get redirected correctly by APPEND_SLASH middleware
    # rather than being swallowed by this rule. MUST be last.
    re_path(r"^(?!admin|api/|accounts/|i18n/|markdownx/|django-rq/|healthz).*$", spa_shell, name="spa-shell"),
]
