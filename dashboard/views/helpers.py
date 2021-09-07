from datetime import datetime
from typing import Tuple

from django.core.handlers.wsgi import WSGIRequest


def extract_int_request(request, param_name):
    """Returns an integer, or None if the parameter doesn't exist or is 'null' """
    val = request.GET.get(param_name, None)
    if val == '' or val == 'null' or val is None:
        return None
    else:
        return int(val)


def extract_date_request(request, param_name, date_format="%Y-%m-%d"):
    """Return a datetime.date object (or None is the param doesn't exist or is empty)

    format: see https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior
    """
    val = request.GET.get(param_name, None)

    if val is not None and val != '':
        return datetime.strptime(val, date_format).date()

    return None


def filters_from_request(request: WSGIRequest) -> Tuple[int, datetime.date, datetime.date]:
    species_id = extract_int_request(request, 'speciesId')
    start_date = extract_date_request(request, 'startDate')
    end_date = extract_date_request(request, 'endDate')

    return species_id, start_date, end_date
