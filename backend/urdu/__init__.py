"""
Tesserae V6 - Urdu Language Support (Plugin)

Self-contained Urdu language module. All Urdu-specific logic lives here.
To remove Urdu support entirely, delete this package and texts/ur/.

Registration is triggered by importing this module and calling register().
All hooks in the main codebase are guarded by try/except ImportError.
"""

URDU_ENABLED = False
_registered = False


def register():
    """Register Urdu language support with the Tesserae backend."""
    global URDU_ENABLED, _registered
    if _registered:
        return

    try:
        from backend.urdu.processor import UrduLanguageHandler
        from backend.text_processor import register_language_handler
        register_language_handler('ur', UrduLanguageHandler())

        try:
            from backend.urdu.stopwords import URDU_STOP_WORDS
            from backend import fusion
            fusion._STOPLISTS['ur'] = URDU_STOP_WORDS
        except Exception:
            pass

        URDU_ENABLED = True
        _registered = True
        from backend.logging_config import get_logger
        get_logger('urdu').info('Urdu language support registered')

    except Exception as e:
        from backend.logging_config import get_logger
        get_logger('urdu').warning(f'Urdu registration failed: {e}')
        URDU_ENABLED = False
