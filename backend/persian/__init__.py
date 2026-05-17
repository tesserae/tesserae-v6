"""
Tesserae V6 - Persian Language Support (Plugin)

Self-contained Persian language module. All Persian-specific logic lives here.
To remove Persian support entirely, delete this package and texts/fa/.
"""

PERSIAN_ENABLED = False
_registered = False


def register():
    """Register Persian language support with the Tesserae backend."""
    global PERSIAN_ENABLED, _registered
    if _registered:
        return

    try:
        from backend.persian.processor import PersianLanguageHandler
        from backend.text_processor import register_language_handler
        register_language_handler('fa', PersianLanguageHandler())

        try:
            from backend.persian.stopwords import PERSIAN_STOP_WORDS
            from backend import fusion
            fusion._STOPLISTS['fa'] = PERSIAN_STOP_WORDS
        except Exception:
            pass

        PERSIAN_ENABLED = True
        _registered = True
        from backend.logging_config import get_logger
        get_logger('persian').info('Persian language support registered')

    except Exception as e:
        from backend.logging_config import get_logger
        get_logger('persian').warning(f'Persian registration failed: {e}')
        PERSIAN_ENABLED = False
