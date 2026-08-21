"""
Tesserae V6 - Hebrew Language Support (Plugin)

Self-contained Hebrew language module. All Hebrew-specific logic lives here.
To remove Hebrew support entirely, delete this package and texts/he/.

Registration is triggered by importing this module and calling register().
All hooks in the main codebase are guarded by try/except ImportError.
"""

HEBREW_ENABLED = False
_registered = False


def register():
    """Register Hebrew language support with the Tesserae backend.

    Called from app.py at startup. Registers:
    - Language handler in text_processor registry
    - Hebrew stoplist in fusion._STOPLISTS
    """
    global HEBREW_ENABLED, _registered
    if _registered:
        return

    try:
        from backend.hebrew.processor import HebrewLanguageHandler
        from backend.text_processor import register_language_handler
        register_language_handler('he', HebrewLanguageHandler())

        try:
            from backend.hebrew.stopwords import HEBREW_STOP_WORDS
            from backend import fusion
            fusion._STOPLISTS['he'] = HEBREW_STOP_WORDS
        except Exception:
            pass

        HEBREW_ENABLED = True
        _registered = True
        from backend.logging_config import get_logger
        get_logger('hebrew').info('Hebrew language support registered')

    except Exception as e:
        from backend.logging_config import get_logger
        get_logger('hebrew').warning(f'Hebrew registration failed: {e}')
        HEBREW_ENABLED = False
