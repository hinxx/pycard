from __future__ import annotations


DEFAULT_LANGUAGE = "en"
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
        "button.personalize_user": "Uporabnik",
        "button.personalize_admin": "Admin",
        "card.admin": "ADMIN",
        "message.no_card": "Kartica ni prisotna",
        "message.card_update_done": "Posodobitev kartice je končana",
        "message.reader_error": "Napaka bralnika",
        "message.pin_saved": "Osebni PIN je bil shranjen v konfiguracijo.",
        "message.pin_incorrect": "Napačen PIN. Število preostalih poskusov: {attempts}. Ne poskušajte znova, dokler ne preverite, kateri PIN uporablja kartica. Za nadaljevanje odstranite in znova vstavite kartico.",
        "message.pin_locked": "PIN kartice je trajno zaklenjen. Zaščiteno pisanje ni več mogoče in programska oprema kartice ne more odkleniti.",
        "message.blank_card_waiting": "Prazna kartica čaka na personalizacijo.",
        "message.blank_card_confirming": "Preverjanje, ali je kartica res prazna...",
        "message.blank_card_cancelled": "Prazna kartica ni bila personalizirana. Odstranite jo in jo znova vstavite za ponovni poskus.",
        "message.personal_pin_required": "Pred personalizacijo prazne kartice nastavite osebni PIN, ki ni FF FF FF.",
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
        "prompt.blank_card_title": "Personalizacija prazne kartice",
        "prompt.blank_card_message": "Zaznana je prazna kartica. Izberite, ali jo želite personalizirati kot uporabniško ali admin kartico.",
        "status.card_update_in_progress": "Posodabljanje kartice...",
        "status.card_personalization_in_progress": "Personalizacija kartice...",
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
        "button.personalize_user": "User",
        "button.personalize_admin": "Admin",
        "card.admin": "ADMIN",
        "message.no_card": "No card present",
        "message.card_update_done": "Card update done",
        "message.reader_error": "Reader error",
        "message.pin_saved": "Personal PIN was saved to the config file.",
        "message.pin_incorrect": "Incorrect PIN. Remaining attempts: {attempts}. Do not retry until you have confirmed which PIN the card uses. Remove and reinsert the card to continue.",
        "message.pin_locked": "The card PIN is permanently locked. Protected writes are no longer possible, and software cannot unlock the card.",
        "message.blank_card_waiting": "The blank card is waiting to be personalized.",
        "message.blank_card_confirming": "Confirming that the card is really blank...",
        "message.blank_card_cancelled": "The blank card was not personalized. Remove and reinsert it to try again.",
        "message.personal_pin_required": "Set a non-default personal PIN before personalizing a blank card.",
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
        "prompt.blank_card_title": "Personalize Blank Card",
        "prompt.blank_card_message": "A blank card was detected. Choose whether to personalize it as a user or admin card.",
        "status.card_update_in_progress": "Card update in progress...",
        "status.card_personalization_in_progress": "Personalizing card...",
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
