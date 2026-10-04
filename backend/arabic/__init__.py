"""
Tesserae V6 - Arabic Language Support (Plugin)

Self-contained Arabic language module. All Arabic-specific logic lives here.
To remove Arabic support entirely, delete this package and texts/ar/.

Registration is triggered by importing this module and calling register().
All hooks in the main codebase are guarded by try/except ImportError.
"""

ARABIC_ENABLED = False
_registered = False


def register():
    """Register Arabic language support with the Tesserae backend.

    Called from app.py at startup. Registers:
    - Language handler in text_processor registry
    - Arabic stoplist in fusion._STOPLISTS
    - 'arabic' in allowed_languages for text requests
    - Cross-lingual pairs in search.VALID_CROSSLINGUAL_PAIRS
    """
    global ARABIC_ENABLED, _registered
    if _registered:
        return

    try:
        from backend.arabic.processor import ArabicLanguageHandler
        from backend.text_processor import register_language_handler
        register_language_handler('ar', ArabicLanguageHandler())

        # Register stoplist
        try:
            from backend.arabic.stopwords import ARABIC_STOP_WORDS
            from backend import fusion
            fusion._STOPLISTS['ar'] = ARABIC_STOP_WORDS
        except Exception:
            pass

        ARABIC_ENABLED = True
        _registered = True
        from backend.logging_config import get_logger
        get_logger('arabic').info('Arabic language support registered')

    except Exception as e:
        from backend.logging_config import get_logger
        get_logger('arabic').warning(f'Arabic registration failed: {e}')
        ARABIC_ENABLED = False
