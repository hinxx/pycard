from __future__ import annotations


DEFAULT_LANGUAGE = "sl"
SUPPORTED_LANGUAGES = ("sl", "en")


STRINGS = {
    "sl": {
        "app.title": "pycard",
        "app.version": "različica {version}",
        "lang.label": "Jezik",
        "lang.sl": "SL",
        "lang.en": "EN",
        "presence.reader_connected": "Bralnik: povezan ({reader_name})",
        "presence.reader_missing": "Bralnik: ni povezan",
        "presence.card_inserted": "Kartica: vstavljena",
        "presence.card_missing": "Kartica: ni vstavljena",
        "presence.card_unavailable": "Kartica: ni na voljo",
        "label.current_value": "Trenutno stanje",
        "label.add_value": "Dodaj vrednost",
        "label.new_total": "Novo stanje",
        "button.yes": "Da",
        "button.no": "Ne",
        "button.cancel": "Prekliči",
        "button.save": "Shrani",
        "button.ok": "V redu",
        "button.update_card": "Posodobi kartico",
        "button.switch_to_admin": "Preklopi v admin",
        "button.switch_to_user": "Preklopi v uporabnika",
        "card.admin": "ADMIN",
        "message.no_card": "Kartica ni prisotna",
        "message.card_update_done": "Posodobitev kartice je končana",
        "message.reader_error": "Napaka bralnika",
        "message.pin_saved": "Osebni PIN je bil shranjen v konfiguracijo.",
        "prompt.pin_setup_title": "Nastavitev osebnega PIN",
        "prompt.pin_setup_message": "V konfiguraciji je še vedno privzeti PIN FF FF FF. Ali želite nastaviti osebni PIN?",
        "prompt.pin_input_title": "Osebni PIN",
        "prompt.pin_input_message": "Vnesite tri šestnajstiške bajte PIN, ločene s presledki, na primer 11 22 33",
        "prompt.pin_input_error_title": "Neveljaven PIN",
        "prompt.pin_input_error_message": "PIN mora vsebovati natanko tri šestnajstiške bajte med 00 in FF, ločene s presledki.",
        "prompt.switch_to_admin_title": "Potrdi preklop",
        "prompt.switch_to_admin_message": "Ali res želite preklopiti kartico v admin način?",
        "prompt.switch_to_user_title": "Potrdi preklop",
        "prompt.switch_to_user_message": "Ali res želite preklopiti kartico v uporabniški način?",
        "status.card_update_in_progress": "Posodabljanje kartice...",
    },
    "en": {
        "app.title": "pycard",
        "app.version": "version {version}",
        "lang.label": "Language",
        "lang.sl": "SL",
        "lang.en": "EN",
        "presence.reader_connected": "Reader: connected ({reader_name})",
        "presence.reader_missing": "Reader: not connected",
        "presence.card_inserted": "Card: inserted",
        "presence.card_missing": "Card: not inserted",
        "presence.card_unavailable": "Card: unavailable",
        "label.current_value": "Current value",
        "label.add_value": "Add value",
        "label.new_total": "New total",
        "button.yes": "Yes",
        "button.no": "No",
        "button.cancel": "Cancel",
        "button.save": "Save",
        "button.ok": "OK",
        "button.update_card": "Update card",
        "button.switch_to_admin": "Switch to admin",
        "button.switch_to_user": "Switch to user",
        "card.admin": "ADMIN",
        "message.no_card": "No card present",
        "message.card_update_done": "Card update done",
        "message.reader_error": "Reader error",
        "message.pin_saved": "Personal PIN was saved to the config file.",
        "prompt.pin_setup_title": "Personal PIN Setup",
        "prompt.pin_setup_message": "The config file still uses the default PIN FF FF FF. Do you want to set a personal PIN?",
        "prompt.pin_input_title": "Personal PIN",
        "prompt.pin_input_message": "Enter three hexadecimal PIN bytes separated by spaces, for example 11 22 33",
        "prompt.pin_input_error_title": "Invalid PIN",
        "prompt.pin_input_error_message": "The PIN must contain exactly three hexadecimal bytes between 00 and FF, separated by spaces.",
        "prompt.switch_to_admin_title": "Confirm Switch",
        "prompt.switch_to_admin_message": "Do you really want to switch this card to admin mode?",
        "prompt.switch_to_user_title": "Confirm Switch",
        "prompt.switch_to_user_message": "Do you really want to switch this card to user mode?",
        "status.card_update_in_progress": "Card update in progress...",
    },
}


class I18n:
    def __init__(self, language: str = DEFAULT_LANGUAGE) -> None:
        self.language = DEFAULT_LANGUAGE
        self.set_language(language)

    def set_language(self, language: str) -> None:
        if language in SUPPORTED_LANGUAGES:
            self.language = language
        else:
            self.language = DEFAULT_LANGUAGE

    def t(self, key: str, **kwargs) -> str:
        template = STRINGS[self.language].get(key) or STRINGS[DEFAULT_LANGUAGE].get(key) or key
        return template.format(**kwargs)
