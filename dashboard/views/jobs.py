"""Long-running tasks to be used with Django-rq"""
from typing import Any

from django_rq import job  # type: ignore

from dashboard.api_v2_schemas import FiltersQuery
from dashboard.models import ObservationUnseen, User
from dashboard.views.helpers import observations_for_filters


@job
def mark_many_observations_as_seen(filters: dict[str, Any], user_id: int) -> None:
    """Delete the user's unseen rows for every observation matching `filters`.

    `filters` is the JSON form of a FiltersQuery (what the API endpoint
    enqueues) and `user_id` the requesting user's pk: plain data that a job
    can carry across a deploy, unlike a pickled queryset (tied to the Django
    version that produced it) or a pickled User (password hash in Redis). The
    queryset is rebuilt here, with the code running at execution time.

    Two queries, not one DELETE per observation: on a 150k-observation alert
    the per-row loop ran for minutes, right when the user went back to
    browsing that alert. Starting from the unseen join keeps the cost with
    the user's unseen rows (small by design) rather than with the alert -
    measured at 0.16 s for 2.6k rows and 1.5 s for 16k on a production copy.

    Not `observation__in=observations`: the area filter's `.extra()` clause
    names the observation table, which Django aliases inside a subquery.
    """
    user = User.objects.filter(pk=user_id).first()
    if user is None:  # deleted between enqueue and run: nothing left to flip
        return
    observations = observations_for_filters(FiltersQuery(**filters), user)
    unseen_ids = list(
        observations.filter(observationunseen__user=user).values_list("id", flat=True)
    )
    ObservationUnseen.objects.filter(user=user, observation_id__in=unseen_ids).delete()
