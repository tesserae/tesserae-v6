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

# Must happen at import of conftest, which pytest loads before it imports any
# test module -- setting it in a fixture would already be too late.
os.environ.setdefault('TESSERAE_DIRECT_SERVER', '1')
