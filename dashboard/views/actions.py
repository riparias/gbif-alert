"""Actions are simple views that issue a redirect"""

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _

from dashboard.models import Observation, Alert, Area
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
            messages.success(request, _("Your alert has been deleted."))
            return redirect("dashboard:pages:my-alerts")
        else:
            return HttpResponseForbidden()


# We don't use the @login_required decorator here because we don't want a redirect to the login page, but rather
# a simple 403. We do that in the function body.
def delete_own_account(request: AuthenticatedHttpRequest):
    if request.method == "POST":
        if request.user.is_authenticated:
            request.user.delete()
            logout(request)
            messages.success(request, _("Your account has been deleted."))
            return redirect("dashboard:pages:index")
        else:
            return HttpResponseForbidden()


@login_required
def area_delete(
    request: AuthenticatedHttpRequest, id: int
) -> HttpResponseRedirect | HttpResponseForbidden:
    """Delete an area"""
    if request.method == "POST":
        area = get_object_or_404(Area, pk=id)
        if area.owner == request.user:
            try:
                area.delete()
                messages.success(request, _("The area has been deleted."))
            except Area.HasAlerts:
                messages.error(
                    request,
                    _(
                        "The area could not be deleted because it has alerts associated with it."
                    ),
                )
            return redirect("dashboard:pages:my-custom-areas")

    return HttpResponseForbidden()
