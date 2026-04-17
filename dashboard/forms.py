from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _

from dashboard.models import ObservationComment


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


_UNIT_TO_DAYS = {"days": 1, "weeks": 7, "months": 30, "years": 365}


def _days_to_value_unit(days):
    """Convert a number of days to the most natural (value, unit) pair.

    Parameters
    ----------
    days : int
        Number of days.

    Returns
    -------
    value : int
        Numeric part of the duration.
    unit : str
        One of 'days', 'weeks', 'months', 'years'.
    """
    for unit in ("years", "months", "weeks"):
        divisor = _UNIT_TO_DAYS[unit]
        if days % divisor == 0:
            return days // divisor, unit
    return days, "days"


def _value_unit_to_days(value, unit):
    """Convert a (value, unit) pair back to a number of days.

    Parameters
    ----------
    value : int
        Numeric part of the duration.
    unit : str
        One of 'days', 'weeks', 'months', 'years'.

    Returns
    -------
    int
        Equivalent number of days (1 month = 30 days, 1 year = 365 days).
    """
    return value * _UNIT_TO_DAYS[unit]


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
