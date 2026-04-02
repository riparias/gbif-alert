from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _
from crispy_forms.helper import FormHelper  # type: ignore
from crispy_forms.layout import Layout, Div, HTML  # type: ignore

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


_DELAY_UNIT_CHOICES = [
    ("days", _("days")),
    ("weeks", _("weeks")),
    ("months", _("months")),
    ("years", _("years")),
]

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


class EditProfileForm(CommonUsersFields, UserChangeForm):
    # No password change on the profile form
    password = None  # type: ignore

    delay_value = forms.IntegerField(
        label=_("Notification delay"),
        min_value=1,
    )
    delay_unit = forms.ChoiceField(
        label=_("Delay unit"),
        choices=_DELAY_UNIT_CHOICES,
    )

    class Meta(CommonUsersFields.Meta):
        fields = CommonUsersFields.Meta.fields

    def __init__(self, *args, **kwargs):
        super(UserChangeForm, self).__init__(*args, **kwargs)
        self.fields["username"].disabled = True  # Username is readonly
        if self.instance and self.instance.pk:
            value, unit = _days_to_value_unit(self.instance.notification_delay_days)
            self.initial["delay_value"] = value
            self.initial["delay_unit"] = unit
        self.helper = FormHelper()
        self.helper.form_tag = False  # The template already wraps the form
        self.helper.layout = Layout(
            "username",
            "first_name",
            "last_name",
            "language",
            "email",
            Div(
                Div("delay_value", css_class="col-sm-4"),
                Div("delay_unit", css_class="col-sm-3"),
                css_class="row",
            ),
            HTML(
                "<p class='form-text'>"
                + str(
                    _(
                        "Observations older than this delay will be automatically considered as 'seen'. "
                        "Note: 1 month = 30 days, 1 year = 365 days."
                    )
                )
                + "</p>"
            ),
        )

    def clean(self):
        cleaned = super().clean()
        value = cleaned.get("delay_value")
        unit = cleaned.get("delay_unit")
        if value is not None and unit:
            cleaned["notification_delay_days"] = _value_unit_to_days(value, unit)
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.notification_delay_days = self.cleaned_data["notification_delay_days"]
        if commit:
            instance.save()
        return instance


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
