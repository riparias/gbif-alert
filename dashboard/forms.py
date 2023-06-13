from typing import Tuple

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from dashboard.models import ObservationComment, Alert, Area, User


def get_initial_alert_name(user: User) -> str:
    """Return a nice name such as "My alert #3", depending on the existing user alerts"""
    alert_number = 1
    existing_alert_names = Alert.objects.filter(user=user).values_list(
        "name", flat=True
    )
    while f"My alert #{alert_number}" in existing_alert_names:
        alert_number += 1

    return f"My alert #{alert_number}"


# TODO: I guess this will not be necessary anymore?
class AlertForm(forms.ModelForm):
    def __init__(self, for_user, *args, **kwargs):
        super(AlertForm, self).__init__(*args, **kwargs)
        self.user = for_user
        self.fields["name"].initial = get_initial_alert_name(self.user)
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

    # TODO: Move this to model?
    def clean(self):
        cleaned_data = self.cleaned_data
        try:
            if (
                Alert.objects.filter(name=cleaned_data["name"], user=self.user)
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                raise ValidationError(
                    _(
                        "You already have another alert with this name. Please choose a different name."
                    )
                )
        except KeyError:  # name is not provided, skip the check
            pass
        return cleaned_data


def _enabled_languages_as_tuple():
    """
    Return a tuple of tuples of the form (language_code, language_name) for all enabled languages

    Enabled languages: according to the PTEROIS["ENABLED_LANGUAGES"] settings
    Output format: identical to the settings.LANGUAGES format, so it can be used as a replacement
    """
    return tuple(
        (language_code, language_name)
        for language_code, language_name in settings.LANGUAGES
        if language_code in settings.PTEROIS["ENABLED_LANGUAGES"]
    )


class CommonUsersFields(forms.ModelForm):
    first_name = forms.CharField(
        label=_("First name"), max_length=30, required=False, help_text=_("Optional.")
    )
    last_name = forms.CharField(
        label=_("Last name"), max_length=30, required=False, help_text=_("Optional.")
    )
    email = forms.EmailField(
        label=_("Email"),
        max_length=254,
        help_text=_("Required. Enter a valid email address."),
    )

    language = forms.ChoiceField(
        label=_("Language"), choices=_enabled_languages_as_tuple()
    )

    class Meta:
        model = get_user_model()

        fields: Tuple[str, ...] = (
            "username",
            "first_name",
            "last_name",
            "language",
            "email",
        )


class EditProfileForm(CommonUsersFields, UserChangeForm):
    # No password change on the profile form
    password = None  # type: ignore

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
            "language",
            "password1",
            "password2",
        )


class NewObservationCommentForm(forms.ModelForm):
    class Meta:
        model = ObservationComment
        fields = ("text",)
