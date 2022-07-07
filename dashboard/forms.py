from typing import Tuple

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError

from dashboard.models import ObservationComment, Alert, Area


class AlertForm(forms.ModelForm):
    def __init__(self, for_user, *args, **kwargs):
        super(AlertForm, self).__init__(*args, **kwargs)
        self.user = for_user
        self.fields["areas"].queryset = Area.objects.available_to(user=self.user)

    class Meta:
        model = Alert
        fields: Tuple[str, ...] = (
            "name",
            "species",
            "areas",
            "datasets",
            "email_notifications_frequency",
        )

    def clean(self):
        cleaned_data = self.cleaned_data
        try:
            if Alert.objects.filter(name=cleaned_data["name"], user=self.user).exists():
                raise ValidationError(
                    "You already have an alert with this name. Please choose a different name."
                )
        except KeyError:  # name is not provided, skip the check
            pass
        return cleaned_data


class CommonUsersFields(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=False, help_text="Optional.")
    last_name = forms.CharField(max_length=30, required=False, help_text="Optional.")
    email = forms.EmailField(
        max_length=254, help_text="Required. Enter a valid email address."
    )

    class Meta:
        model = get_user_model()

        fields: Tuple[str, ...] = (
            "username",
            "first_name",
            "last_name",
            "email",
        )


class EditProfileForm(CommonUsersFields, UserChangeForm):
    password = None  # No password change on the profile form

    def __init__(self, *args, **kwargs):
        super(UserChangeForm, self).__init__(*args, **kwargs)
        self.fields["username"].disabled = True  # Username is readonly


class SignUpForm(CommonUsersFields, UserCreationForm):
    class Meta(CommonUsersFields.Meta):
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        )


class NewObservationCommentForm(forms.ModelForm):
    class Meta:
        model = ObservationComment
        fields = ("text",)
