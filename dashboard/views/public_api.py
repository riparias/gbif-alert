"""Public-facing API views"""

from django.http import JsonResponse

from dashboard.models import Species
from dashboard.views.helpers import model_to_json_list


def species_list_json(_) -> JsonResponse:
    """A list of all species known to the system, in JSON format

    Order: undetermined
    """
    return model_to_json_list(Species)
