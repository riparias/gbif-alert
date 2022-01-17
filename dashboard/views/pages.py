from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpRequest
from django.shortcuts import render, get_object_or_404, redirect

from dashboard.forms import (
    SignUpForm,
    EditProfileForm,
    NewObservationCommentForm,
    AlertForm,
)
from dashboard.models import DataImport, Observation, Alert
from dashboard.views.helpers import AuthenticatedHttpRequest


def index_page(request: HttpRequest):
    return render(request, "dashboard/index.html")


def about_page(request: HttpRequest):
    data_imports = DataImport.objects.all().order_by("-start")
    return render(request, "dashboard/about.html", {"data_imports": data_imports})


def observation_details_page(request: HttpRequest, stable_id: str):
    observation = get_object_or_404(Observation, stable_id=stable_id)
    observation.mark_as_viewed_by(request.user)
    first_viewed = observation.first_viewed_at(request.user)

    if request.method == "POST":
        if (
            not request.user.is_authenticated
        ):  # Only authenticated users can post comments
            return HttpResponseForbidden()

        form = NewObservationCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.author = request.user
            comment.observation = observation
            comment.save()
            form = NewObservationCommentForm()  # Show a new empty one to the user
    else:
        form = NewObservationCommentForm()

    return render(
        request,
        "dashboard/observation_details.html",
        {
            "observation": observation,
            "new_comment_form": form,
            "first_view_by_user_timestamp": first_viewed,
        },
    )


@login_required
def alert_details_page(request: AuthenticatedHttpRequest, alert_id: int):
    alert = get_object_or_404(Alert, id=alert_id)

    if alert.user == request.user:
        return render(request, "dashboard/alert_details.html", {"alert": alert})
    else:
        return HttpResponseForbidden()


@login_required
def alert_create_page(request: AuthenticatedHttpRequest):
    if request.method == "POST":
        form = AlertForm(request.user, request.POST)
        if form.is_valid():
            alert = form.save(commit=False)
            alert.user = request.user
            alert.save()
            form.save_m2m()
            return redirect(alert)
    else:
        form = AlertForm(for_user=request.user)

    return render(request, "dashboard/alert_create.html", {"form": form})


def user_signup_page(request: HttpRequest):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get("username")
            raw_password = form.cleaned_data.get("password1")
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect("dashboard:page-index")
    else:
        form = SignUpForm()
    return render(request, "dashboard/user_signup.html", {"form": form})


@login_required
def user_profile_page(request: AuthenticatedHttpRequest):
    if request.method == "POST":
        form = EditProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile was successfully updated.")
            return redirect("dashboard:page-index")
    else:
        form = EditProfileForm(instance=request.user)
    return render(request, "dashboard/user_profile.html", {"form": form})


@login_required
def user_alerts_page(request: AuthenticatedHttpRequest):
    alerts = Alert.objects.filter(user=request.user).order_by("id")
    return render(request, "dashboard/user_alerts.html", {"alerts": alerts})


@login_required
def mark_observation_as_not_viewed(request: AuthenticatedHttpRequest):
    if request.method == "POST":
        observation = get_object_or_404(Observation, id=request.POST["observationId"])
        success = observation.mark_as_not_viewed_by(user=request.user)
        if success:
            return redirect("dashboard:page-index")
        else:
            return redirect(observation)  # Error? Stay where we came from


@login_required
def action_alert_delete(request: AuthenticatedHttpRequest):
    if request.method == "POST":
        alert = get_object_or_404(Alert, pk=request.POST.get("alert_id"))
        if alert.user == request.user:
            alert.delete()
            messages.success(request, "Alert deleted.")
            return redirect("dashboard:page-my-alerts")
        else:
            return HttpResponseForbidden
