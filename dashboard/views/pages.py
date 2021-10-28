from django.contrib.auth import authenticate, login
from django.shortcuts import render, get_object_or_404, redirect

from dashboard.forms import SignUpForm
from dashboard.models import DataImport, Occurrence


def index_page(request):
    return render(request, "dashboard/index.html")


def about_page(request):
    data_imports = DataImport.objects.all().order_by("-start")
    return render(request, "dashboard/about.html", {"data_imports": data_imports})


def occurrence_details_page(request, pk):
    occurrence = get_object_or_404(Occurrence, pk=pk)
    return render(
        request, "dashboard/occurrence_details.html", {"occurrence": occurrence}
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
