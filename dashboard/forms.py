from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _

from dashboard.models import ObservationComment


class NewCustomAreaForm(forms.Form):
    name = forms.CharField(
        label=_("Area name"),
        max_length=255,
        help_text=_("A short name to identify this area"),
    )
    data_file = forms.FileField(
        label=_("Data file"),
    )


def _enabled_languages_as_tuple():
    """
    Return a tuple of tuples of the form (language_code, language_name) for all enabled languages

    Enabled languages: according to the GBIF_ALERT["ENABLED_LANGUAGES"] settings
    Output format: identical to the settings.LANGUAGES format, so it can be used as a replacement
    """
    return tuple(
        (language_code, language_name)
        for language_code, language_name in settings.LANGUAGES
        if language_code in settings.GBIF_ALERT["ENABLED_LANGUAGES"]
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
        label=_("Language"),
        choices=_enabled_languages_as_tuple(),
        help_text=_("This language will be used for emails."),
    )

    class Meta:
        model = get_user_model()

        fields: tuple[str, ...] = (
            "username",
            "first_name",
            "last_name",
            "language",
            "email",
        )


class EditProfileForm(CommonUsersFields, UserChangeForm):
    # No password change on the profile form
    password = None  # type: ignore

    notification_delay_days = forms.IntegerField(
        label=_("Notification delay"),
        help_text=_(
            "Observations older than this number of days will be automatically considered as 'seen'"
        ),
    )

    class Meta(CommonUsersFields.Meta):
        fields = CommonUsersFields.Meta.fields + ("notification_delay_days",)

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
