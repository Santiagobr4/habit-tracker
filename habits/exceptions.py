"""Custom DRF exception handler with a unified response contract."""

from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Wrap DRF exceptions into a stable API error shape.

    The handler preserves existing details while exposing a top-level
    `error` key to keep compatibility with current frontend parsing.
    """
    response = exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data

    message = ''
    if isinstance(detail, dict):
        if isinstance(detail.get('detail'), str):
            message = detail['detail']
        elif isinstance(detail.get('error'), str):
            message = detail['error']
        elif detail:
            first_value = next(iter(detail.values()))
            if isinstance(first_value, list) and first_value:
                message = str(first_value[0])
            else:
                message = str(first_value)
    elif isinstance(detail, list) and detail:
        message = str(detail[0])
    else:
        message = str(detail)

    response.data = {
        'error': message,
        'detail': message,
        'errors': detail,
    }
    return response
