"""
Tesserae V6 - Coptic Language Support (Plugin)

Self-contained Coptic language module. All Coptic-specific logic lives here.
To remove Coptic support entirely, delete this package and texts/cop/.

Registration is triggered by importing this module and calling register().
All hooks in the main codebase are guarded by try/except ImportError.
"""

COPTIC_ENABLED = False
_registered = False


def register():
    """Register Coptic language support with the Tesserae backend.

    Called from app.py at startup. Registers:
    - Language handler in text_processor registry
    - Coptic stoplist in fusion._STOPLISTS
    """
    global COPTIC_ENABLED, _registered
    if _registered:
        return

    try:
        from backend.coptic.processor import CopticLanguageHandler
        from backend.text_processor import register_language_handler
        register_language_handler('cop', CopticLanguageHandler())

        try:
            from backend.coptic.stopwords import COPTIC_STOP_WORDS
            from backend import fusion
            fusion._STOPLISTS['cop'] = COPTIC_STOP_WORDS
        except Exception:
            pass

        COPTIC_ENABLED = True
        _registered = True
        from backend.logging_config import get_logger
        get_logger('coptic').info('Coptic language support registered')

    except Exception as e:
        from backend.logging_config import get_logger
        get_logger('coptic').warning(f'Coptic registration failed: {e}')
        COPTIC_ENABLED = False
