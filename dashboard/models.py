import datetime
import hashlib
import logging
import os
import smtplib
from typing import Any, Self

import html2text
from django.conf import settings
from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.contrib.gis.db import models
from django.contrib.gis.db.models.aggregates import Union as AggregateUnion
from django.core.mail import send_mail
from django.db.models import QuerySet, Q
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import localize
from django.utils.timezone import localtime
from django.utils.translation import gettext_lazy as _
from taggit.managers import TaggableManager

from page_fragments.models import PageFragment, NEWS_PAGE_IDENTIFIER

DATA_SRID = 3857  # Let's keep everything in Google Mercator to avoid reprojections

import gettext

THIS_FILE_DIR = os.path.dirname(os.path.abspath(__file__))


# Approach from https://stackoverflow.com/questions/37998300/python-gettext-specify-locale-in
def get_translator(lang: str = "en"):
    if lang == "en":
        # Don't try to get a translation if the language is English (would raise an exception)
        return lambda s: s
    else:
        trans = gettext.translation(
            "django",
            localedir=os.path.join(THIS_FILE_DIR, "locale"),
            languages=(lang,),
        )
        return trans.gettext


class User(AbstractUser):
    last_visit_news_page = models.DateTimeField(null=True, blank=True)
    language = models.CharField(
        max_length=10, choices=settings.LANGUAGES, default=settings.LANGUAGE_CODE
    )

    def get_language(self) -> str:
        # Use this method instead of self.language to get the language code (some got en-us as a default value, that will cause issues)
        if self.language == "en-us":
            return "en"
        return self.language

    @property
    def has_alerts_with_unseen_observations(self) -> bool:
        """True if the users has unseen observations in one of their alerts"""
        for alert in self.alert_set.all():
            if alert.has_unseen_observations:
                return True
        return False

    def mark_news_as_visited_now(self) -> None:
        """Mark the news page as visited now"""
        self.last_visit_news_page = timezone.now()
        self.save()

    @property
    def has_unseen_news(self) -> bool:
        """True if the user has unseen news"""
        return (
            self.last_visit_news_page is None
            or self.last_visit_news_page
            < PageFragment.objects.get(identifier=NEWS_PAGE_IDENTIFIER).updated_at
        )

    def empty_all_comments(self) -> None:
        """Empty all comments for this user (to be used prior to deletion)"""
        for comment in self.observationcomment_set.all():
            comment.make_empty()

    class Meta(object):
        unique_together = ("email",)


# Make sure we empty all comments before deleting the user, regardless of the deletion method (bulk, individual,
# admin, ...)
@receiver(pre_delete, sender=User)
def empty_user_comments(sender, instance, **kwargs):
    instance.empty_all_comments()


WebsiteUser = User | AnonymousUser


class Species(models.Model):  # type: ignore
    name = models.CharField(max_length=100)  # Scientific name
    vernacular_name = models.CharField(max_length=100, blank=True)
    gbif_taxon_key = models.IntegerField(unique=True)

    tags = TaggableManager(blank=True)

    class Meta:
        verbose_name_plural = "species"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def display_name_html(self) -> str:
        name = f"<i>{self.name}</i>"
        if self.vernacular_name:
            name = name + f" ({self.vernacular_name})"

        return name

    @property
    def as_dict(self) -> dict[str, Any]:
        # ! keep the return value in sync with the frontend's SpeciesInformation interface
        return {  # To be consumed on the frontend: we use JS naming conventions
            "id": self.pk,
            "scientificName": self.name,
            "vernacularName": self.vernacular_name,
            "gbifTaxonKey": self.gbif_taxon_key,
            "tags": [tag.name for tag in self.tags.all()],
        }


class Dataset(models.Model):
    name = models.CharField(max_length=255)
    gbif_dataset_key = models.CharField(max_length=255, unique=True)

    __original_gbif_dataset_key = None

    def __str__(self) -> str:
        return self.name

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.__original_gbif_dataset_key = (
            self.gbif_dataset_key
        )  # So we're able to check if it has changed in save()

    class Meta:
        ordering = ["name"]

    @property
    def as_dict(self) -> dict[str, Any]:
        return {  # To be consumed on the frontend: we use JS naming conventions
            "id": self.pk,
            "gbifKey": self.gbif_dataset_key,
            "name": self.name,
        }

    def save(self, force_insert=False, force_update=False, *args, **kwargs) -> None:
        super().save(force_insert, force_update, *args, **kwargs)

        if self.gbif_dataset_key != self.__original_gbif_dataset_key:
            # We updated the gbif dataset key, so all related observations should have a new stable_id
            for occ in self.observation_set.all():
                occ.save()

        self.__original_gbif_dataset_key = self.gbif_dataset_key


class DataImport(models.Model):
    start = models.DateTimeField()
    end = models.DateTimeField(blank=True, null=True)
    completed = models.BooleanField(default=False)
    gbif_download_id = models.CharField(max_length=255, blank=True)
    imported_observations_counter = models.IntegerField(default=0)
    skipped_observations_counter = models.IntegerField(default=0)
    gbif_predicate = models.JSONField(
        blank=True, null=True
    )  # Null if a DwC-A file was provided - no GBIF download

    class Meta:
        ordering = ["-pk"]

    def set_gbif_download_id(self, download_id: str) -> None:
        """Set the download id and immediately save the entry"""
        self.gbif_download_id = download_id
        self.save()

    def complete(self) -> None:
        """Method to be called at the end of the import process to finalize this entry"""
        self.end = timezone.now()
        self.completed = True
        self.imported_observations_counter = Observation.objects.filter(
            data_import=self
        ).count()
        self.save()

    def __str__(self) -> str:
        return (
            f"Data import #{self.pk} ({localize(localtime(self.start), use_l10n=True)})"
        )

    @property
    def as_dict(self) -> dict[str, Any]:
        return {  # To be consumed on the frontend: we use JS naming conventions
            "id": self.pk,
            "str": self.__str__(),
            "startTimestamp": self.start,
        }


class ObservationManager(models.Manager["Observation"]):
    def filtered_from_my_params(
        self,
        species_ids: list[int],
        datasets_ids: list[int],
        start_date: datetime.date | None,
        end_date: datetime.date | None,
        areas_ids: list[int],
        status_for_user: str | None,
        initial_data_import_ids: list[int],
        user: User | None,  # mandatory if status_for_user is set
    ) -> QuerySet["Observation"]:
        # !! IMPORTANT !! Make sure the observation filtering here is equivalent to what's done in
        # views.maps.JINJASQL_FRAGMENT_FILTER_OBSERVATIONS. Otherwise, observations returned on the map and on other
        # components (table, ...) will be inconsistent.
        # !! If adding new filters, make also sure they are properly documented in the docstrings of "api.py"
        qs = self.model.objects.select_related(
            "species",
            "source_dataset",
        ).all()

        if species_ids:
            qs = qs.filter(species_id__in=species_ids)
        if datasets_ids:
            qs = qs.filter(source_dataset_id__in=datasets_ids)
        if start_date:
            qs = qs.filter(date__gte=start_date)
        if end_date:
            qs = qs.filter(date__lte=end_date)
        if areas_ids:
            combined_areas = Area.objects.filter(pk__in=areas_ids).aggregate(
                area=AggregateUnion("mpoly")
            )["area"]
            qs = qs.filter(location__within=combined_areas)
        if initial_data_import_ids:
            qs = qs.filter(initial_data_import_id__in=initial_data_import_ids)

        if status_for_user and user:
            ov = ObservationView.objects.filter(user=user)
            if status_for_user == "seen":
                qs = qs.filter(observationview__in=ov)
            elif status_for_user == "unseen":
                qs = qs.exclude(observationview__in=ov)

        return qs


class Observation(models.Model):
    # Pay attention to the fact that this model actually has 4(!) different "identifiers" which serve different
    # purposes. gbif_id, occurrence_id and stable_id are documented below, Django also adds the usual and implicit "pk"
    # field.

    # The GBIF-assigned identifier. We show it to the user (links to GBIF.org, ...) but don't rely on it as a stable
    # identifier anymore. See: https://github.com/riparias/gbif-alert/issues/35#issuecomment-944073702 and
    # https://github.com/gbif/pipelines/issues/604,
    gbif_id = models.CharField(max_length=100)

    # The raw occurrenceId GBIF field, as provided by GBIF data providers retrieved from the data download.
    # It is an important data source, we use it to compute stable_id
    occurrence_id = models.TextField()

    # The computed stable identifier that we can use to identify the same records between data import
    stable_id = models.CharField(max_length=40)

    species = models.ForeignKey(Species, on_delete=models.CASCADE)
    location = models.PointField(blank=True, null=True, srid=DATA_SRID)
    date = models.DateField()
    individual_count = models.IntegerField(blank=True, null=True)
    locality = models.TextField(blank=True)
    municipality = models.TextField(blank=True)
    basis_of_record = models.TextField(blank=True)
    recorded_by = models.TextField(blank=True)
    coordinate_uncertainty_in_meters = models.FloatField(blank=True, null=True)
    references = models.TextField(blank=True)

    data_import = models.ForeignKey(DataImport, on_delete=models.PROTECT)
    initial_data_import = models.ForeignKey(
        DataImport,
        on_delete=models.PROTECT,
        related_name="occurrences_initially_imported",
    )
    source_dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)

    objects = ObservationManager()

    class Meta:
        unique_together = [("gbif_id", "data_import"), ("stable_id", "data_import")]

    def __str__(self):
        return f"Observation of {self.species} on {self.date} (stable_id: {self.stable_id})"

    class OtherIdenticalObservationIsNewer(Exception):
        pass

    def get_admin_url(self) -> str:
        return reverse(
            "admin:%s_%s_change" % (self._meta.app_label, self._meta.model_name),
            args=(self.id,),
        )

    def mark_as_seen_by(self, user: WebsiteUser) -> None:
        """
        Mark the observation as "seen" by a given user.

        Note that this is a high-level function designed to be called directly from a view (for example)
            - Does nothing if the user is anonymous (not signed in)
            - Does nothing if the user has already previously seen this observation
        """

        if user.is_authenticated:
            try:
                self.observationview_set.get(user=user)
            except ObservationView.DoesNotExist:
                ObservationView.objects.create(observation=self, user=user)

    def first_seen_at(self, user: WebsiteUser) -> datetime.datetime | None:
        """Return the time a user as first seen this observation

        Returns none if the user is not logged in, or if they have not seen the observation yet
        """

        # We want to check if user is not anonymous, but apparently is_authenticated is the preferred method
        if user.is_authenticated:
            try:
                return self.observationview_set.get(user=user).timestamp
            except ObservationView.DoesNotExist:
                return None
        return None

    def mark_as_unseen_by(self, user: WebsiteUser) -> bool:
        """Mark the observation as "unseen" for a given user.

        :return: True is successful (most probable causes of failure: user has not seen this observation yet / user is
        anonymous)"""
        if user.is_authenticated:
            try:
                self.observationview_set.get(user=user).delete()
                return True
            except ObservationView.DoesNotExist:
                return False

        return False

    def save(self, *args, **kwargs) -> None:
        self.stable_id = Observation.build_stable_id(
            self.occurrence_id, self.source_dataset.gbif_dataset_key
        )
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse(
            "dashboard:pages:observation-details", kwargs={"stable_id": self.stable_id}
        )

    def set_or_migrate_initial_data_import(
        self, current_data_import: DataImport
    ) -> None:
        """If this is the first import of this observation, set initial_data_import to the current import. Otherwise, migrate its value from the previous observation."""
        replaced_observation = self.replaced_observation
        if replaced_observation is None:
            self.initial_data_import = current_data_import
        else:
            self.initial_data_import = replaced_observation.initial_data_import

    def migrate_linked_entities(self) -> None:
        """Migrate existing entities (comments, ...) linked to a previous observation that share the stable ID

        Does nothing if there's no replaced observation
        """
        replaced_observation = self.replaced_observation
        if replaced_observation is not None:
            # 1. Migrating comments
            for comment in replaced_observation.observationcomment_set.all():
                comment.observation = self
                comment.save()
            # 2. Migrating user views
            for observation_view in replaced_observation.observationview_set.all():
                observation_view.observation = self
                observation_view.save()

    @property
    def replaced_observation(self) -> Self | None:
        """Return the observation (from a previous import) that will be replaced by this one

        return None if this observation is new to the system
        raises:
        - Observation.MultipleObjectsReturned if multiple old observations match
        - Observation.OtherIdenticalObservationIsNewer if another one has the same stable identifier, but is more recent
        """

        identical_observations = self.get_identical_observations()
        if identical_observations.count() == 0:
            return None
        elif identical_observations.count() == 1:
            the_other_one = identical_observations[0]
            if the_other_one.data_import.pk < self.data_import.pk:
                return the_other_one
            else:
                raise Observation.OtherIdenticalObservationIsNewer

        else:  # Multiple observations found, this is abnormal
            raise Observation.MultipleObjectsReturned

    def get_identical_observations(self) -> QuerySet[Self]:
        """Return 'identical' observations (same stable_id), excluding myself"""
        return Observation.objects.exclude(pk=self.pk).filter(  # type: ignore
            stable_id=Observation.build_stable_id(
                self.occurrence_id, self.source_dataset.gbif_dataset_key
            )
        )

    @property
    def sorted_comments_set(self) -> QuerySet["ObservationComment"]:
        return self.observationcomment_set.order_by("-created_at")

    @staticmethod
    def build_stable_id(occurrence_id: str, dataset_key: str) -> str:
        """Compute a unique/portable/repeatable hash depending on occurrence_id and dataset_key

        Return value is a 40-char string containing only hexadecimal characters
        """
        s = f"occ_id: {occurrence_id} d_id: {dataset_key}"
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    @property
    def lat(self) -> float | None:
        return self.lonlat_4326_tuple[1]

    @property
    def lon(self) -> float | None:
        return self.lonlat_4326_tuple[0]

    @property
    def lonlat_4326_tuple(self) -> tuple[float | None, float | None]:
        """Coordinates as a (lon, lat) tuple, in EPSG:4326

        (None, None) in case the observation has no location
        """
        if self.location:
            coords = self.location.transform(4326, clone=True).coords
            return coords[0], coords[1]
        return None, None

    # Keep in sync with JsonObservation (TypeScript interface)
    def as_dict(self, for_user: WebsiteUser) -> dict[str, Any]:
        """Returns the model representation has a dict.

        If the user is not anonymous, it also contains status data (seen / unseen)"""
        lon, lat = self.lonlat_4326_tuple

        d = {
            "id": self.pk,
            "stableId": self.stable_id,
            "gbifId": self.gbif_id,
            "lat": lat,
            "lon": lon,
            "speciesName": self.species.name,
            "datasetName": self.source_dataset.name,
            "date": str(self.date),
        }

        if for_user.is_authenticated:
            try:
                self.observationview_set.get(user=for_user)
                d["seenByCurrentUser"] = True
            except ObservationView.DoesNotExist:
                d["seenByCurrentUser"] = False

        return d


class ObservationComment(models.Model):
    """ " A comment on an observation, left by an authenticated visitor"""

    observation = models.ForeignKey(Observation, on_delete=models.CASCADE)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    # If an author deletes their account, we keep track of the comment's existence
    # (so a conversation under an observation doesn't seem too absurd) but delete its content. Such records can be
    # detected with the 'emptied_because_author_deleted_account' flag
    emptied_because_author_deleted_account = models.BooleanField(default=False)

    def make_empty(self):
        """
        Make the comment empty, and mark it as such.

        This is the method to be called before deleting a user account.
        """
        self.text = ""
        self.author = None
        self.emptied_because_author_deleted_account = True
        self.save()


class MyAreaManager(models.Manager["Area"]):
    def owned_by(self, user: WebsiteUser) -> QuerySet["Area"]:
        return super(MyAreaManager, self).get_queryset().filter(owner=user)

    def public(self) -> QuerySet["Area"]:
        return super(MyAreaManager, self).get_queryset().filter(owner=None)

    def available_to(self, user: WebsiteUser) -> QuerySet["Area"]:
        if user.is_authenticated:
            return (
                super(MyAreaManager, self)
                .get_queryset()
                .filter(Q(owner=user) | Q(owner=None))
            )
        else:
            return self.public()


class Area(models.Model):
    """An area that can be shown to the user, or used to filter observations"""

    mpoly = models.MultiPolygonField(srid=DATA_SRID)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, blank=True, null=True
    )  # an area can be public or user-specific
    name = models.CharField(max_length=255)

    tags = TaggableManager(blank=True)
    objects = MyAreaManager()

    class Meta:
        ordering = ["name"]

    class HasAlerts(Exception):
        """This area is referenced by at least one alert"""

    def delete(self, *args, **kwargs):
        if self.alert_set.count() > 0:
            raise Area.HasAlerts
        super(Area, self).delete(*args, **kwargs)

    @property
    def is_public(self) -> bool:
        return self.owner is None

    @property
    def is_user_specific(self) -> bool:
        return not self.is_public

    def is_owned_by(self, user: WebsiteUser) -> bool:
        return self.is_user_specific and self.owner == user

    def is_available_to(self, user: WebsiteUser) -> bool:
        return self.is_public or self.is_owned_by(user)

    def __str__(self) -> str:
        return self.name

    def to_dict(self, include_geojson: bool):
        d = {
            "id": self.pk,
            "name": self.name,
            "isUserSpecific": self.is_user_specific,
            "tags": [tag.name for tag in self.tags.all()],
        }

        if include_geojson:
            d["geojson_str"] = self.mpoly.geojson

        return d


class ObservationView(models.Model):
    """
    This models keeps a history of when a user has first seen details about an observation

    - If no entry for the user/observation pair: the user has never seen details about this observation
    - Else: the timestamp of the *first* visit is kept (no sophisticated history mechanism)
    """

    observation = models.ForeignKey(Observation, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [
            ("observation", "user"),
        ]


class Alert(models.Model):
    """The per-user configured alerts

    An alert is user specific.
    Datasets is an optional filter. If left blank, all source datasets will be taken into account.
    Area is an optional filter. If left blank, data is not filtered by location (which might be more than the selection of all areas)
    We choose to not extend this logic to species. By keeping this list explicit, we allow site administrators
    to add new species and areas without having to worry about silently editing user alerts.
    """

    NO_EMAILS = "N"
    DAILY_EMAILS = "D"
    WEEKLY_EMAILS = "W"
    MONTHLY_EMAILS = "M"

    EMAIL_NOTIFICATION_CHOICES = [
        (NO_EMAILS, _("No emails")),
        (DAILY_EMAILS, _("Daily")),
        (WEEKLY_EMAILS, _("Weekly")),
        (MONTHLY_EMAILS, _("Monthly")),
    ]

    EMAIL_NOTIFICATION_DELTAS = (
        {  # After how much time should we be ready to send a new email
            DAILY_EMAILS: datetime.timedelta(hours=22),
            WEEKLY_EMAILS: datetime.timedelta(days=6, hours=22),
            MONTHLY_EMAILS: datetime.timedelta(weeks=4),
        }
    )

    name = models.CharField(verbose_name=_("name"), max_length=255)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    species = models.ManyToManyField(
        Species,
        verbose_name=_("species"),
        blank=False,
        help_text=_(
            "To select multiple items, press and hold the "
            "Ctrl or Command key and click the items."
        ),
    )
    datasets = models.ManyToManyField(
        Dataset,
        verbose_name=_("datasets"),
        blank=True,
        help_text=_(
            "Optional (no selection = notify me for all datasets). To select multiple items, press and hold the "
            "Ctrl or Command key and click the items."
        ),
    )
    areas = models.ManyToManyField(
        Area,
        blank=True,
        verbose_name=_("areas"),
        help_text=_(
            "Optional (no selection = notify me for all data in the system). To select multiple items, press and hold the "
            "Ctrl or Command key and click the items."
        ),
    )

    email_notifications_frequency = models.CharField(
        max_length=3,
        choices=EMAIL_NOTIFICATION_CHOICES,
        default=WEEKLY_EMAILS,
        verbose_name=_("email notifications frequency"),
    )

    last_email_sent_on = models.DateTimeField(blank=True, null=True, default=None)

    class Meta:
        unique_together = [("user", "name")]

    def get_absolute_url(self) -> str:
        return reverse("dashboard:pages:alert-details", kwargs={"alert_id": self.id})

    @property
    def areas_list(self) -> str:
        return ", ".join(self.areas.order_by("name").values_list("name", flat=True))

    @property
    def datasets_list(self) -> str:
        return ", ".join(self.datasets.order_by("name").values_list("name", flat=True))

    @property
    def species_list(self) -> str:
        return ", ".join(self.species.order_by("name").values_list("name", flat=True))

    @property
    def as_dashboard_filters(self) -> dict[str, Any]:
        """The alert represented as a dict

        Once converted to JSON, this dict is suitable for Observation filtering in the frontend
        (see DashboardFilters TypeScript interface).
        """
        return {
            "speciesIds": [s.pk for s in self.species.all()],
            "datasetsIds": [d.pk for d in self.datasets.all()],
            "areaIds": [a.pk for a in self.areas.all()],
            "startDate": None,
            "endDate": None,
            "status": None,
        }

    @property
    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.pk,
            "name": self.name,
            "speciesIds": [s.pk for s in self.species.all()],
            "datasetIds": [d.pk for d in self.datasets.all()],
            "areaIds": [a.pk for a in self.areas.all()],
            "emailNotificationsFrequency": self.email_notifications_frequency,
        }

    def unseen_observations(self) -> QuerySet[Observation]:
        return Observation.objects.filtered_from_my_params(
            species_ids=[s.pk for s in self.species.all()],
            datasets_ids=[d.pk for d in self.datasets.all()],
            areas_ids=[a.pk for a in self.areas.all()],
            start_date=None,
            end_date=None,
            initial_data_import_ids=[],
            status_for_user="unseen",
            user=self.user,
        )

    def unseen_observations_sample(self, sample_size=10) -> QuerySet[Observation]:
        """For notification emails: show max sample_size observations, most recent first"""
        obs = self.unseen_observations().order_by("-date")
        if obs.count() > sample_size:
            obs = obs[:sample_size]

        return obs

    @property
    def unseen_observations_count(self) -> int:
        """The number of unseen observations for this alert"""
        return self.unseen_observations().count()

    @property
    def has_unseen_observations(self) -> bool:
        """True if this alert has unseen observations"""
        return self.unseen_observations_count > 0

    def email_should_be_sent_now(self) -> bool:
        """Returns true if a notification email for this alert should be sent at the present time.

        Use some margins so emails are sent at a decent frequency if this is called daily.
        """
        if (
            self.email_notifications_frequency != self.NO_EMAILS
            and self.unseen_observations_count > 0
        ):
            if (
                self.last_email_sent_on is None
            ):  # the user wants e-mails, has unseen observations and has not received yet...
                return True  # ...so, now is  a good time
            else:
                # the user wants e-mails, has unseen observations but as already received notifications.
                # Is it now a good time for a new one?
                delta = self.EMAIL_NOTIFICATION_DELTAS[
                    self.email_notifications_frequency
                ]
                if self.last_email_sent_on + delta < timezone.now():
                    return True
        return False

    def send_notification_email(self) -> bool:
        """Send the notification e-mail

        No checks are done, it's the responsibility of the caller to use email_should_be_sent_now() before calling this
        method.
        """
        language_code = self.user.get_language()

        # Message subject
        _ = get_translator(language_code)
        unseen_obs_translated = _("unseen observation(s) for your alert")
        subject = f"{settings.EMAIL_SUBJECT_PREFIX} {self.unseen_observations().count()} {unseen_obs_translated} {self.name}"

        # Message body
        msg_html = render_to_string(
            f"dashboard/emails/alert_notification.{language_code}.html",
            {
                "alert": self,
                "site_base_url": settings.SITE_BASE_URL,
                "site_name": settings.GBIF_ALERT["SITE_NAME"],
            },
        )

        msg_plain = html2text.html2text(msg_html)

        try:
            send_mail(
                subject,
                msg_plain,
                settings.SERVER_EMAIL,
                [self.user.email],
                html_message=msg_html,
            )
        except smtplib.SMTPException:
            logging.exception("Error sending notification emails")
            return False

        self.last_email_sent_on = timezone.now()
        self.save(update_fields=["last_email_sent_on"])
        return True
