from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, get_object_or_404, redirect

from dashboard.forms import SignUpForm, EditProfileForm, NewOccurrenceCommentForm
from dashboard.models import DataImport, Occurrence


def index_page(request):
    return render(request, "dashboard/index.html")


def about_page(request):
    data_imports = DataImport.objects.all().order_by("-start")
    return render(request, "dashboard/about.html", {"data_imports": data_imports})


def occurrence_details_page(request, stable_id):
    occurrence = get_object_or_404(Occurrence, stable_id=stable_id)
    occurrence.mark_as_viewed_by(request.user)
    first_viewed = occurrence.first_viewed_at(request.user)

    if request.method == "POST":
        if (
            not request.user.is_authenticated
        ):  # Only authenticated users can post comments
            return HttpResponseForbidden()

        form = NewOccurrenceCommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.author = request.user
            comment.occurrence = occurrence
            comment.save()
            form = NewOccurrenceCommentForm()  # Show a new empty one to the user
    else:
        form = NewOccurrenceCommentForm()

    return render(
        request,
        "dashboard/occurrence_details.html",
        {
            "occurrence": occurrence,
            "new_comment_form": form,
            "first_view_by_user_timestamp": first_viewed,
        },
    )


def user_signup_page(request):
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
def user_profile_page(request):
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
def mark_occurrence_as_not_viewed(request):
    if request.method == "POST":
        occurrence = get_object_or_404(Occurrence, id=request.POST["occurrenceId"])
        success = occurrence.mark_as_not_viewed_by(user=request.user)
        if success:
            return redirect("dashboard:page-index")
        else:
            return redirect(occurrence)  # Error? Stay where we came from
