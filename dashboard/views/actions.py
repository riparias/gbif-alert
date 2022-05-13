"""Actions are simple views that issue a redirect"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect

from dashboard.models import Observation, Alert
from dashboard.views.helpers import AuthenticatedHttpRequest, extract_str_request


@login_required
def mark_observation_as_unseen(request: AuthenticatedHttpRequest):
    if request.method == "POST":
        observation = get_object_or_404(Observation, id=request.POST["observationId"])
        origin_url = extract_str_request(request, "originUrl")
        success = observation.mark_as_unseen_by(user=request.user)
        if success:
            if origin_url and origin_url != "None":
                destination = origin_url
            else:
                destination = "dashboard:pages:index"
            return redirect(destination)
        else:
            return redirect(observation)  # Error? Stay where we came from


@login_required
def delete_alert(request: AuthenticatedHttpRequest):
    if request.method == "POST":
        alert = get_object_or_404(Alert, pk=request.POST.get("alert_id"))
        if alert.user == request.user:
            alert.delete()
            messages.success(request, "Alert deleted.")
            return redirect("dashboard:pages:my-alerts")
        else:
            return HttpResponseForbidden()
