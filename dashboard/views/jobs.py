"""Long-running tasks to be used with Django-rq"""
from django.db.models import QuerySet
from django_rq import job  # type: ignore

from dashboard.models import Observation, User


@job
def mark_many_observations_as_seen(observations: QuerySet[Observation], user: User):
    for observation in observations:
        observation.mark_as_seen_by(user)
