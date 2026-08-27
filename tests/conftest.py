"""Make the API prefix the same for every test, whatever order they run in.

THE BUG THIS EXISTS TO KILL

backend.app decides API_PREFIX once, at import time, from TESSERAE_DIRECT_SERVER:

    API_PREFIX = "/api" if DIRECT_SERVER else ""

Several test modules set that variable inside a fixture and then import
backend.app. That works for whichever module imports it FIRST, and silently
does nothing for every module after it, because the import is already cached.
So the routes a test asked for either existed or did not depending on
collection order:

    pytest tests/test_app.py                  ->  5 passed
    pytest tests/                             ->  test_app.py fails, 404
    pytest tests/test_endpoints.py            ->  passes
    pytest tests/test_assistant_conversation.py tests/test_endpoints.py
                                              ->  30 failed, all 404 and 405

Thirty endpoint tests reporting 404 look exactly like thirty broken endpoints.
That is the same shape of failure that let the Coptic quotation channel sit dead
in production for eleven weeks: a suite that passes for a reason unrelated to
the code being correct. Setting the variable here, before collection imports
anything, makes the prefix a property of the test run rather than of the order.
"""
import os
import tempfile

# Must happen at import of conftest, which pytest loads before it imports any
# test module -- setting it in a fixture would already be too late.
os.environ.setdefault('TESSERAE_DIRECT_SERVER', '1')

# A SECRET FOR THE TEST RUN, which otherwise cannot import the app at all.
#
# CI has been red on main since at least 2026-08-27, and not because of any
# test: collection died importing backend.app, so all 349 tests were skipped
# and the suite reported one error. Any of the seven modules that import the
# app would have triggered it.
#
# The cause is a contradiction inside backend/app.py, which reads the same
# variable with two different defaults:
#
#     line 102:  DEPLOYMENT_ENV = os.environ.get("DEPLOYMENT_ENV", "dev")
#     line 144:  elif os.environ.get("DEPLOYMENT_ENV", "production") == "dev":
#
# With the variable unset the app considers itself dev everywhere except the
# secret check, which considers itself production and raises.
#
# DELIBERATELY NOT FIXED THERE. Making line 144 use the constant would resolve
# the contradiction and also mean a real deployment that forgot to set
# DEPLOYMENT_ENV would silently run on an ephemeral secret -- sessions breaking
# on every restart -- where today it refuses to start. Failing loudly on a
# misconfigured deploy is worth more than tidiness, so the fix belongs here, in
# the configuration of the test run, rather than in the guard.
#
# setdefault, so a real SESSION_SECRET in the environment still wins.
os.environ.setdefault('SESSION_SECRET', 'test-run-only-not-a-real-secret')

# A DATABASE FOR THE TEST RUN. The second thing collection died on, once the
# secret was in place: app.py reads DATABASE_URL and hands it straight to
# SQLAlchemy, which refuses None. CI has no Postgres, and the suite should not
# need one to import the app.
#
# A file rather than :memory:, because Flask-SQLAlchemy opens connections per
# thread and an in-memory SQLite database is private to the connection that
# created it, so a threaded test would find an empty schema. Under the system
# temp directory, so it is not written into the repository.
#
# Again setdefault: a real DATABASE_URL wins, which is what happens locally and
# on the server.
_TEST_DB = os.path.join(tempfile.gettempdir(), 'tesserae_test.sqlite')
os.environ.setdefault('DATABASE_URL', f'sqlite:///{_TEST_DB}')

# NON-DEV, for the same reason the prefix is set here rather than in a module.
#
# test_security_headers.py asserts the app sends Strict-Transport-Security,
# which app.py only does when DEPLOYMENT_ENV != 'dev'. That module sets the
# variable itself -- at line 10, immediately before importing the app -- which
# works only when it is the FIRST module to import it, and silently does
# nothing otherwise, because the import is already cached. Precisely the
# order-dependence this file was written to kill, in a second variable nobody
# had noticed.
#
# Non-dev turns on exactly two things: the HSTS header and SESSION_COOKIE_SECURE.
# Neither troubles a test client, and 'test' is what that module already chose.
os.environ.setdefault('DEPLOYMENT_ENV', 'test')
