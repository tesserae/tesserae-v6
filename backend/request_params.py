"""One rule for a bad number in a request: a 400 with a plain message.

``int_param`` and ``float_param`` read a numeric parameter from a query string,
a form or a JSON body. An absent or empty value gives the default. A value that
is not a whole number (or a number, for ``float_param``), or that falls outside
the allowed range, aborts the request with a 400 and ``{"error": "<name> must
be a whole number"}``.

The abort is an HTTPException, so a route that wraps its work in
``except Exception`` must let it through with ``except HTTPException: raise``
placed before the broad clause.
"""
from flask import jsonify
from werkzeug.exceptions import HTTPException


class BadParameter(HTTPException):
    """A 400 whose body is JSON with an ``error`` field."""
    code = 400
    description = 'Bad parameter'

    def __init__(self, message):
        super().__init__(description=message)
        self.message = message

    def get_response(self, environ=None, scope=None):
        response = jsonify({'error': self.message})
        response.status_code = 400
        return response


def _absent(value):
    return value is None or value == ''


def int_param(source, name, default, minimum=None, maximum=None):
    """Return ``source[name]`` as an int, or ``default`` when absent."""
    value = source.get(name)
    if _absent(value):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise BadParameter(f'{name} must be a whole number')
    _check_range(name, number, minimum, maximum)
    return number


def float_param(source, name, default, minimum=None, maximum=None):
    """Return ``source[name]`` as a float, or ``default`` when absent."""
    value = source.get(name)
    if _absent(value):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise BadParameter(f'{name} must be a number')
    _check_range(name, number, minimum, maximum)
    return number


def _check_range(name, number, minimum, maximum):
    if minimum is not None and number < minimum:
        raise BadParameter(f'{name} must be {minimum} or greater')
    if maximum is not None and number > maximum:
        raise BadParameter(f'{name} must be {maximum} or less')
