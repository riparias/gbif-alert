"""Long-running tasks to be used with Django-rq"""
from django.db.models import QuerySet
from django_rq import job  # type: ignore

from dashboard.models import Observation, ObservationUnseen, User


@job
def mark_many_observations_as_seen(observations: QuerySet[Observation], user: User):
    """Delete the user's unseen rows for every observation in the queryset.

    Two queries, not one DELETE per observation: on a 150k-observation alert
    the per-row loop ran for minutes, right when the user went back to
    browsing that alert. Starting from the unseen join keeps the cost with
    the user's unseen rows (small by design) rather than with the alert -
    measured at 0.16 s for 2.6k rows and 1.5 s for 16k on a production copy.

    Not `observation__in=observations`: the area filter's `.extra()` clause
    names the observation table, which Django aliases inside a subquery.
    """
    unseen_ids = list(
        observations.filter(observationunseen__user=user).values_list("id", flat=True)
    )
    ObservationUnseen.objects.filter(user=user, observation_id__in=unseen_ids).delete()
