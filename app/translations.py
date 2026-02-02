# Simple dictionary for static UI strings
# Key: Language code (matches Babel/ISO codes)
# Value: Dictionary of UI strings

TRANSLATIONS = {
    'en': {
        'today': 'TODAY',
        'no_events': 'No events',
        'all_day': 'All Day'
    },
    'de': {
        'today': 'HEUTE',
        'no_events': 'Keine Termine',
        'all_day': 'Ganztägig'
    }
}

DEFAULT_LANGUAGE = 'en'

def get_text(lang, key):
    """
    Retrieve translated text. Falls back to English if lang or key is missing.
    """
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANGUAGE])
    return lang_dict.get(key, TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key))
