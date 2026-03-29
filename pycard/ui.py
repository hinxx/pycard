from __future__ import annotations

from pycard.i18n import DEFAULT_LANGUAGE, I18n

try:  # pragma: no cover - import depends on local install
    import customtkinter as ctk
except ImportError as exc:  # pragma: no cover - import depends on local install
    raise RuntimeError(
        "customtkinter is required. Install project dependencies first."
    ) from exc


class _BaseDialog(ctk.CTkToplevel):
    def __init__(self, parent: ctk.CTk, title: str) -> None:
        super().__init__(parent)
        self.parent = parent
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grid_columnconfigure(0, weight=1)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def show_modal(self):
        self.update_idletasks()
        self._center_over_parent()
        self.grab_set()
        self.focus()
        self.wait_window()

    def _center_over_parent(self) -> None:
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        x = parent_x + max((parent_width - width) // 2, 0)
        y = parent_y + max((parent_height - height) // 2, 0)
        self.geometry(f"+{x}+{y}")

    def _on_close(self) -> None:
        self.destroy()


class _ConfirmationDialog(_BaseDialog):
    def __init__(
        self,
        parent: ctk.CTk,
        title: str,
        message: str,
        confirm_text: str,
        cancel_text: str,
        confirm_color: str | None = None,
        confirm_hover_color: str | None = None,
    ) -> None:
        super().__init__(parent, title)
        self.result = False

        body = ctk.CTkFrame(self)
        body.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        label = ctk.CTkLabel(body, text=message, wraplength=360, justify="left")
        label.grid(row=0, column=0, columnspan=2, padx=16, pady=(16, 20), sticky="w")

        cancel_button = ctk.CTkButton(body, text=cancel_text, command=self._cancel)
        cancel_button.grid(row=1, column=0, padx=(16, 8), pady=(0, 16), sticky="ew")

        confirm_button = ctk.CTkButton(
            body,
            text=confirm_text,
            command=self._confirm,
            fg_color=confirm_color,
            hover_color=confirm_hover_color,
        )
        confirm_button.grid(row=1, column=1, padx=(8, 16), pady=(0, 16), sticky="ew")
        confirm_button.focus()

    def _confirm(self) -> None:
        self.result = True
        self.destroy()

    def _cancel(self) -> None:
        self.result = False
        self.destroy()


class _AlertDialog(_BaseDialog):
    def __init__(self, parent: ctk.CTk, title: str, message: str, button_text: str) -> None:
        super().__init__(parent, title)

        body = ctk.CTkFrame(self)
        body.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)

        label = ctk.CTkLabel(body, text=message, wraplength=360, justify="left")
        label.grid(row=0, column=0, padx=16, pady=(16, 20), sticky="w")

        ok_button = ctk.CTkButton(body, text=button_text, command=self.destroy)
        ok_button.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="ew")
        ok_button.focus()


class _PinInputDialog(_BaseDialog):
    def __init__(
        self,
        parent: ctk.CTk,
        title: str,
        prompt: str,
        save_text: str,
        cancel_text: str,
        initial_value: str = "",
    ) -> None:
        super().__init__(parent, title)
        self.result: str | None = None

        body = ctk.CTkFrame(self)
        body.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        label = ctk.CTkLabel(body, text=prompt, wraplength=360, justify="left")
        label.grid(row=0, column=0, columnspan=2, padx=16, pady=(16, 12), sticky="w")

        self.entry = ctk.CTkEntry(body, width=220)
        self.entry.grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 20))
        self.entry.insert(0, initial_value)
        self.entry.icursor(len(initial_value))

        cancel_button = ctk.CTkButton(body, text=cancel_text, command=self._cancel)
        cancel_button.grid(row=2, column=0, padx=(16, 8), pady=(0, 16), sticky="ew")

        save_button = ctk.CTkButton(body, text=save_text, command=self._save)
        save_button.grid(row=2, column=1, padx=(8, 16), pady=(0, 16), sticky="ew")
        self.entry.focus()

    def _save(self) -> None:
        self.result = self.entry.get()
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


class MainWindow(ctk.CTk):
    def __init__(self, language: str = DEFAULT_LANGUAGE, version_text: str = "") -> None:
        super().__init__()
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.i18n = I18n(language)
        self._presence_state = (False, "", False)
        self._version_text = version_text
        self._language_display_to_code = {"SL": "sl", "EN": "en"}
        self._language_code_to_display = {value: key for key, value in self._language_display_to_code.items()}

        self.title(self.t("app.title"))
        self.geometry("720x420")
        self.minsize(640, 360)

        self.controller = None
        self._amount_var = ctk.StringVar(value="2")
        self._amount_var.trace_add("write", self._handle_amount_changed)
        self._language_var = ctk.StringVar(value=self._language_code_to_display[self.i18n.language])

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.header = ctk.CTkFrame(self)
        self.header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        self.header.grid_columnconfigure(0, weight=1)
        self.header.grid_columnconfigure(1, weight=0)
        self.header.grid_columnconfigure(2, weight=0)
        self.header.grid_columnconfigure(3, weight=0)
        self.header.grid_columnconfigure(4, weight=0)

        self.app_label = ctk.CTkLabel(
            self.header,
            text=self.t("app.title"),
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        self.app_label.grid(row=0, column=0, sticky="w", padx=16, pady=16)

        self.language_label = ctk.CTkLabel(self.header, text=self.t("lang.label"))
        self.language_label.grid(row=0, column=1, sticky="e", padx=(16, 8), pady=16)

        self.language_menu = ctk.CTkOptionMenu(
            self.header,
            values=list(self._language_display_to_code),
            variable=self._language_var,
            command=self._handle_language_changed,
            width=80,
        )
        self.language_menu.grid(row=0, column=2, sticky="e", padx=(0, 16), pady=16)

        self.version_label = ctk.CTkLabel(self.header, text=self.t("app.version", version=self._version_text))
        self.version_label.grid(row=0, column=3, sticky="e", padx=(0, 16), pady=16)

        self.datetime_label = ctk.CTkLabel(self.header, text="")
        self.datetime_label.grid(row=0, column=4, sticky="e", padx=16, pady=16)

        self.presence_frame = ctk.CTkFrame(self)
        self.presence_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(8, 0))
        self.presence_frame.grid_columnconfigure(0, weight=1)

        self.presence_label = ctk.CTkLabel(
            self.presence_frame,
            text="Reader: unknown | Card: unknown",
            anchor="w",
        )
        self.presence_label.grid(row=0, column=0, sticky="ew", padx=16, pady=12)

        self.body = ctk.CTkFrame(self)
        self.body.grid(row=2, column=0, sticky="nsew", padx=16, pady=16)
        self.body.grid_columnconfigure(0, weight=1)
        self.body.grid_rowconfigure(0, weight=1)

        self.message_frame = self._build_message_frame(self.body)
        self.user_frame = self._build_user_frame(self.body)
        self.admin_frame = self._build_admin_frame(self.body)
        self.show_idle()

    def bind_controller(self, controller) -> None:
        self.controller = controller
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        if self.controller is not None:
            self.controller.shutdown()
        self.destroy()

    def _build_message_frame(self, parent):
        frame = ctk.CTkFrame(parent)
        frame.grid_columnconfigure(0, weight=1)
        self.message_label = ctk.CTkLabel(
            frame,
            text="",
            wraplength=560,
            justify="left",
            font=ctk.CTkFont(size=18),
        )
        self.message_label.grid(row=0, column=0, padx=24, pady=24, sticky="nsew")
        return frame

    def _build_user_frame(self, parent):
        frame = ctk.CTkFrame(parent)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(2, weight=1)

        label_font = ctk.CTkFont(size=13)
        value_font = ctk.CTkFont(size=28, weight="bold")
        entry_font = ctk.CTkFont(size=24, weight="bold")

        self.current_value_title = ctk.CTkLabel(frame, text=self.t("label.current_value"), font=label_font)
        self.current_value_title.grid(row=0, column=0, padx=16, pady=(16, 6))
        self.add_value_title = ctk.CTkLabel(frame, text=self.t("label.add_value"), font=label_font)
        self.add_value_title.grid(row=0, column=1, padx=16, pady=(16, 6))
        self.new_total_title = ctk.CTkLabel(frame, text=self.t("label.new_total"), font=label_font)
        self.new_total_title.grid(row=0, column=2, padx=16, pady=(16, 6))

        self.current_value_label = ctk.CTkLabel(frame, text="0", font=value_font)
        self.current_value_label.grid(row=1, column=0, padx=16, pady=(0, 16))

        self.add_value_entry = ctk.CTkEntry(
            frame,
            textvariable=self._amount_var,
            font=entry_font,
            justify="center",
            width=110,
        )
        self.add_value_entry.grid(row=1, column=1, padx=16, pady=(0, 16))

        self.new_total_label = ctk.CTkLabel(frame, text="0", font=value_font)
        self.new_total_label.grid(row=1, column=2, padx=16, pady=(0, 16))

        self.go_admin_button = ctk.CTkButton(
            frame,
            text=self.t("button.switch_to_admin"),
            command=self._handle_switch_to_admin,
            fg_color="#b45309",
            hover_color="#92400e",
        )
        self.go_admin_button.grid(row=4, column=1, padx=16, pady=(0, 16), sticky="ew")

        self.user_update_button = ctk.CTkButton(
            frame,
            text=self.t("button.update_card"),
            command=self._handle_update_card,
        )
        self.user_update_button.grid(row=2, column=1, padx=16, pady=(0, 16), sticky="ew")
        return frame

    def _build_admin_frame(self, parent):
        frame = ctk.CTkFrame(parent)
        frame.grid_columnconfigure(0, weight=1)
        self.admin_label = ctk.CTkLabel(
            frame,
            text=self.t("card.admin"),
            font=ctk.CTkFont(size=28, weight="bold"),
        )
        self.admin_label.grid(row=0, column=0, padx=16, pady=(32, 16))
        self.go_user_button = ctk.CTkButton(
            frame,
            text=self.t("button.switch_to_user"),
            command=self._handle_switch_to_user,
        )
        self.go_user_button.grid(row=1, column=0, padx=16, pady=(16, 32))
        return frame

    def _show_frame(self, frame) -> None:
        for candidate in (self.message_frame, self.user_frame, self.admin_frame):
            candidate.grid_forget()
        frame.grid(row=0, column=0, sticky="nsew")

    def set_datetime(self, text: str) -> None:
        self.datetime_label.configure(text=text)

    def t(self, key: str, **kwargs) -> str:
        return self.i18n.t(key, **kwargs)

    def set_presence(self, reader_present: bool, reader_name: str, card_present: bool) -> None:
        self._presence_state = (reader_present, reader_name, card_present)
        if reader_present:
            reader_text = self.t("presence.reader_connected", reader_name=reader_name)
            card_text = self.t("presence.card_inserted") if card_present else self.t("presence.card_missing")
            if card_present:
                text_color = "#14532d"
                frame_color = "#dcfce7"
            else:
                text_color = "#9a3412"
                frame_color = "#ffedd5"
        else:
            reader_text = self.t("presence.reader_missing")
            card_text = self.t("presence.card_unavailable")
            text_color = "#7f1d1d"
            frame_color = "#fee2e2"
        self.presence_frame.configure(fg_color=frame_color)
        self.presence_label.configure(text_color=text_color)
        self.presence_label.configure(text=f"{reader_text} | {card_text}")

    def show_idle(self) -> None:
        self.message_label.configure(text="", text_color=("#1f2937", "#e5e7eb"))
        self.message_frame.configure(fg_color="transparent")
        self._show_frame(self.message_frame)

    def show_message(self, text: str, kind: str = "info") -> None:
        color = {
            "info": ("#1f2937", "#e5e7eb"),
            "success": ("#14532d", "#dcfce7"),
            "error": ("#7f1d1d", "#fee2e2"),
        }.get(kind, ("#1f2937", "#e5e7eb"))
        self.message_frame.configure(fg_color=color[1])
        self.message_label.configure(text=text, text_color=color[0])
        self._show_frame(self.message_frame)

    def show_user_card(self, current_value: int, add_value: str, new_total: int, reader_name: str) -> None:
        self.current_value_label.configure(text=str(current_value))
        self.new_total_label.configure(text=str(new_total))
        self._amount_var.set(add_value)
        self._show_frame(self.user_frame)
        self.add_value_entry.focus()
        self.add_value_entry.icursor(len(self._amount_var.get()))

    def update_user_totals(self, current_value: int, new_total: int) -> None:
        self.current_value_label.configure(text=str(current_value))
        self.new_total_label.configure(text=str(new_total))

    def show_admin_card(self, reader_name: str) -> None:
        self._show_frame(self.admin_frame)

    def set_busy(self, is_busy: bool, status_text: str | None = None) -> None:
        state = "disabled" if is_busy else "normal"
        self.user_update_button.configure(state=state)
        self.go_admin_button.configure(state=state)
        self.go_user_button.configure(state=state)
        self.add_value_entry.configure(state=state)

    def _handle_amount_changed(self, *_args) -> None:
        if self.controller is not None:
            self.controller.on_amount_changed(self._amount_var.get())

    def _handle_switch_to_admin(self) -> None:
        if self.controller is not None:
            self.controller.on_switch_to_admin()

    def _handle_switch_to_user(self) -> None:
        if self.controller is not None:
            self.controller.on_switch_to_user()

    def _handle_update_card(self) -> None:
        if self.controller is not None:
            self.controller.on_card_update_requested()

    def _handle_language_changed(self, language: str) -> None:
        language_code = self._language_display_to_code.get(language, DEFAULT_LANGUAGE)
        self.i18n.set_language(language_code)
        self._language_var.set(self._language_code_to_display[self.i18n.language])
        self._apply_translations()
        if self.controller is not None:
            self.controller.refresh(force=True)

    def _apply_translations(self) -> None:
        self.title(self.t("app.title"))
        self.app_label.configure(text=self.t("app.title"))
        self.language_label.configure(text=self.t("lang.label"))
        self.version_label.configure(text=self.t("app.version", version=self._version_text))
        self.current_value_title.configure(text=self.t("label.current_value"))
        self.add_value_title.configure(text=self.t("label.add_value"))
        self.new_total_title.configure(text=self.t("label.new_total"))
        self.user_update_button.configure(text=self.t("button.update_card"))
        self.go_admin_button.configure(text=self.t("button.switch_to_admin"))
        self.go_user_button.configure(text=self.t("button.switch_to_user"))
        self.admin_label.configure(text=self.t("card.admin"))
        self.set_presence(*self._presence_state)

    def prompt_for_personalized_pin(self) -> tuple[int, int, int] | None:
        should_set_dialog = _ConfirmationDialog(
            parent=self,
            title=self.t("prompt.pin_setup_title"),
            message=self.t("prompt.pin_setup_message"),
            confirm_text=self.t("button.yes"),
            cancel_text=self.t("button.no"),
        )
        should_set_dialog.show_modal()
        if not should_set_dialog.result:
            return None

        while True:
            dialog = _PinInputDialog(
                parent=self,
                title=self.t("prompt.pin_input_title"),
                prompt=self.t("prompt.pin_input_message"),
                save_text=self.t("button.save"),
                cancel_text=self.t("button.cancel"),
            )
            dialog.show_modal()
            if dialog.result is None:
                return None

            pin = self._parse_pin_input(dialog.result)
            if pin is not None:
                return pin

            error_dialog = _AlertDialog(
                parent=self,
                title=self.t("prompt.pin_input_error_title"),
                message=self.t("prompt.pin_input_error_message"),
                button_text=self.t("button.ok"),
            )
            error_dialog.show_modal()

    @staticmethod
    def _parse_pin_input(value: str) -> tuple[int, int, int] | None:
        parts = value.split()
        if len(parts) != 3:
            return None
        try:
            numbers = tuple(int(part, 16) for part in parts)
        except ValueError:
            return None
        if any(number < 0 or number > 255 for number in numbers):
            return None
        return numbers

    def confirm_switch_to_admin(self) -> bool:
        dialog = _ConfirmationDialog(
            parent=self,
            title=self.t("prompt.switch_to_admin_title"),
            message=self.t("prompt.switch_to_admin_message"),
            confirm_text=self.t("button.yes"),
            cancel_text=self.t("button.no"),
            confirm_color="#b45309",
            confirm_hover_color="#92400e",
        )
        dialog.show_modal()
        return dialog.result

    def confirm_switch_to_user(self) -> bool:
        dialog = _ConfirmationDialog(
            parent=self,
            title=self.t("prompt.switch_to_user_title"),
            message=self.t("prompt.switch_to_user_message"),
            confirm_text=self.t("button.yes"),
            cancel_text=self.t("button.no"),
        )
        dialog.show_modal()
        return dialog.result
