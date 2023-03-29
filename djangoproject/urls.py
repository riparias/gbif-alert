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
from django.urls import path, include, reverse_lazy
from django.views.i18n import JavaScriptCatalog

urlpatterns = [
    path("", include("dashboard.urls")),
    # User accounts
    path("i18n/", include("django.conf.urls.i18n")),
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    path(
        "accounts/signin/",
        auth_views.LoginView.as_view(template_name="dashboard/signin.html"),
        name="signin",
    ),
    path("accounts/signout/", auth_views.LogoutView.as_view(), name="signout"),
    path(
        "accounts/password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="dashboard/password_reset.html",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
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
]
