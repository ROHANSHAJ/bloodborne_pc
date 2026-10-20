# SPDX-License-Identifier: GPL-2.0-or-later
"""Small GTK 4/libadwaita compatibility shims for older Ubuntu desktop runtimes."""

from pathlib import Path


def install_compat(Adw, Gio, GLib, GObject, Gtk):
    """Fill in widgets added after libadwaita 1.1 / GTK 4.6 when the system lacks them."""
    if not hasattr(Adw, "SwitchRow"):
        class SwitchRow(Adw.ActionRow):
            __gtype_name__ = "BbportCompatSwitchRow"
            active = GObject.Property(type=bool, default=False)

            def __init__(self, title="", subtitle="", active=False):
                super().__init__(title=title, subtitle=subtitle)
                self._switch = Gtk.Switch(valign=Gtk.Align.CENTER)
                self.add_suffix(self._switch)
                self.set_activatable_widget(self._switch)
                self._switch.connect("notify::active", self._on_switch)
                self.props.active = bool(active)
                self._switch.set_active(bool(active))

            def _on_switch(self, *_args):
                self.props.active = self._switch.get_active()

            def get_active(self):
                return self._switch.get_active()

            def set_active(self, active):
                self._switch.set_active(bool(active))

        Adw.SwitchRow = SwitchRow

    if not hasattr(Adw, "SpinRow"):
        class SpinRow(Adw.ActionRow):
            __gtype_name__ = "BbportCompatSpinRow"

            def __init__(self, lower=0, upper=100, step=1):
                super().__init__()
                self._spin = Gtk.SpinButton.new_with_range(lower, upper, step)
                self._spin.set_valign(Gtk.Align.CENTER)
                self.add_suffix(self._spin)
                self.set_activatable_widget(self._spin)

            @classmethod
            def new_with_range(cls, lower, upper, step):
                return cls(lower, upper, step)

            def set_digits(self, digits):
                self._spin.set_digits(digits)

            def set_value(self, value):
                self._spin.set_value(value)

            def get_value(self):
                return self._spin.get_value()

        Adw.SpinRow = SpinRow

    if not hasattr(Adw, "EntryRow"):
        class EntryRow(Adw.ActionRow):
            __gtype_name__ = "BbportCompatEntryRow"

            def __init__(self, title="", text=""):
                super().__init__(title=title)
                self._entry = Gtk.Entry(hexpand=True, text=text, valign=Gtk.Align.CENTER)
                self.add_suffix(self._entry)
                self.set_activatable_widget(self._entry)

            def get_text(self):
                return self._entry.get_text()

            def set_text(self, text):
                self._entry.set_text(text)

        Adw.EntryRow = EntryRow

    if not hasattr(Adw, "PasswordEntryRow"):
        class PasswordEntryRow(Adw.EntryRow):
            __gtype_name__ = "BbportCompatPasswordEntryRow"

            def __init__(self, title="", text=""):
                super().__init__(title=title, text=text)
                self._entry.set_visibility(False)
                self._entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)

        Adw.PasswordEntryRow = PasswordEntryRow

    if not hasattr(Gtk, "FileDialog"):
        class FileDialog:
            def __init__(self, title=""):
                self.title = title
                self.initial_folder = None
                self.initial_name = None
                self.filters = []
                self.default_filter = None
                self.selected_file = None

            def set_initial_folder(self, folder):
                self.initial_folder = folder

            def set_initial_name(self, name):
                self.initial_name = name

            def set_filters(self, filters):
                self.filters = [filters.get_item(i) for i in range(filters.get_n_items())]

            def set_default_filter(self, file_filter):
                self.default_filter = file_filter

            def _show(self, parent, action, callback):
                native = Gtk.FileChooserNative.new(self.title, parent, action, "Select", "Cancel")
                if self.initial_folder is not None:
                    native.set_current_folder(self.initial_folder)
                if self.initial_name is not None:
                    native.set_current_name(self.initial_name)
                for file_filter in self.filters:
                    native.add_filter(file_filter)
                if self.default_filter is not None:
                    native.set_filter(self.default_filter)

                def response(dialog, result):
                    self.selected_file = (dialog.get_file()
                                          if result == Gtk.ResponseType.ACCEPT else None)
                    callback(self, None)
                    dialog.hide()

                native.connect("response", response)
                native.show()
                self._native = native

            def select_folder(self, parent, _cancellable, callback):
                self._show(parent, Gtk.FileChooserAction.SELECT_FOLDER, callback)

            def open(self, parent, _cancellable, callback):
                self._show(parent, Gtk.FileChooserAction.OPEN, callback)

            def save(self, parent, _cancellable, callback):
                self._show(parent, Gtk.FileChooserAction.SAVE, callback)

            def select_folder_finish(self, _result):
                return self.selected_file

            def open_finish(self, _result):
                return self.selected_file

            def save_finish(self, _result):
                return self.selected_file

        Gtk.FileDialog = FileDialog


def add_view_page(stack, child, name, title, icon):
    """Add a titled page, using icons only where the installed Adwaita provides that API."""
    if hasattr(stack, "add_titled_with_icon"):
        return stack.add_titled_with_icon(child, name, title, icon)
    return stack.add_titled(child, name, title)


def launch_file(window, path, Gio, Gtk):
    """Open a folder in the desktop file manager on GTK versions without FileLauncher."""
    file = Gio.File.new_for_path(str(Path(path)))
    if hasattr(Gtk, "FileLauncher"):
        Gtk.FileLauncher.new(file).launch(window, None, None)
    else:
        Gio.AppInfo.launch_default_for_uri(file.get_uri(), None)
