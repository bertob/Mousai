# main_window.py
#
# Copyright 2021 SeaDve
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from collections import namedtuple

from gi.repository import GLib, Gtk, Adw, Gio, GObject

from mousai.widgets.song_row import SongRow
from mousai.backend.voice_recorder import VoiceRecorder
from mousai.backend.utils import Utils

Song = namedtuple('Song', 'title artist song_link audio_src')


@Gtk.Template(resource_path='/io/github/seadve/Mousai/ui/main_window.ui')
class MainWindow(Adw.ApplicationWindow):
    __gtype_name__ = 'MainWindow'

    listen_cancel_stack = Gtk.Template.Child()
    main_stack = Gtk.Template.Child()
    recording_box = Gtk.Template.Child()
    history_listbox = Gtk.Template.Child()

    def __init__(self, settings, **kwargs):
        super().__init__(**kwargs)
        self.settings = settings
        self.memory_list = list(self.settings.get_value('memory-list'))

        self.history_model = Gio.ListStore.new(SongRow)
        self.history_listbox.bind_model(self.history_model, lambda song: song)

        self.voice_recorder = VoiceRecorder()
        self.voice_recorder.connect('record-done', self.on_record_done)
        self.voice_recorder.connect('notify::peak', self.on_peak_changed)

        self.return_default_page()
        self.load_window_size()
        self.load_memory_list()

    @Gtk.Template.Callback()
    def on_start_button_clicked(self, button):
        self.voice_recorder.start()
        self.main_stack.set_visible_child_name('recording')
        self.listen_cancel_stack.set_visible_child_name('cancel')

    @Gtk.Template.Callback()
    def on_cancel_button_clicked(self, button):
        self.voice_recorder.cancel()
        self.return_default_page()

    @Gtk.Template.Callback()
    def on_quit(self, window=None):
        self.settings.set_value('memory-list', GLib.Variant('aa{ss}', self.memory_list))
        self.save_window_size()

    def on_peak_changed(self, recorder, peak):
        peak = recorder.peak
        if -6 < peak <= 0:
            icon_name = 'microphone-sensitivity-high-symbolic'
            title = "Listening"
        elif -15 < peak <= -6:
            icon_name = 'microphone-sensitivity-medium-symbolic'
            title = "Listening"
        elif -349 < peak <= -15:
            icon_name = 'microphone-sensitivity-low-symbolic'
            title = "Listening"
        else:
            icon_name = 'microphone-sensitivity-muted-symbolic'
            title = "Muted"

        self.recording_box.set_icon_name(icon_name)
        self.recording_box.set_title(title)

    def on_record_done(self, recorder):
        song_file = f'{Utils.get_tmp_dir()}/mousaitmp.ogg'
        token = self.settings.get_string('token-value')
        output = Utils.guess_song(song_file, token)
        status = output['status']

        try:
            result = output['result']
            song = Song(*list(result.values())[:-1])
        except (AttributeError, KeyError):
            error = Gtk.MessageDialog(transient_for=self, modal=True,
                                      buttons=Gtk.ButtonsType.OK, title=_("Sorry"))
            if status == 'error':
                error.props.text = output['error_message']
            elif status == 'success' and not result:
                error.props.text = _("The song was not recognized.")
            else:
                error.props.text = _("Something went wrong.")
            error.present()
            error.connect('response', lambda *_: error.close())
        else:
            if image_src := result['image_src']:
                icon_dir = f'{Utils.get_tmp_dir()}/{song[0]}{song[1]}.jpg'
                Utils.download_image(image_src, icon_dir)

            self.remove_duplicates(song.song_link)
            self.new_song_row(song)
            self.memory_list.append(dict(song._asdict()))

        self.return_default_page()

    def remove_duplicates(self, song_id):
        song_link_list = [item['song_link'] for item in self.memory_list]
        if song_id in song_link_list:
            self.history_model.remove_all()
            song_link_index = song_link_list.index(song_id)
            self.memory_list.pop(song_link_index)
            self.load_memory_list()

    def new_song_row(self, song):
        song_row = SongRow(*song)
        self.history_model.insert(0, song_row)

    def return_default_page(self):
        if self.memory_list:
            self.main_stack.set_visible_child_name('main-screen')
        else:
            self.main_stack.set_visible_child_name('empty-state')
        self.listen_cancel_stack.set_visible_child_name('listen')

    def load_memory_list(self):
        for song in self.memory_list:
            self.new_song_row(song.values())

    def clear_memory_list(self):
        self.settings.set_value('memory-list', GLib.Variant('aa{ss}', []))
        self.memory_list = []
        self.history_model.remove_all()
        self.main_stack.set_visible_child_name('empty-state')

    def save_window_size(self):
        size = (
            self.get_size(Gtk.Orientation.HORIZONTAL),
            self.get_size(Gtk.Orientation.VERTICAL)
        )
        self.settings.set_value('window-size', GLib.Variant('ai', [*size]))

    def load_window_size(self):
        size = self.settings.get_value('window-size')
        self.set_default_size(*size)
