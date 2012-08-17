#!/usr/bin/python
from gi.repository import Gtk, Gdk, GLib, GdkX11, Clutter
from core import Player
import sys, urllib

UI_INFO = """
<ui>
  <popup name='PopupMenu'>
    <menuitem action='PopupFileOpen'/>
    <menu action='PopupFileMenu'>
        <menuitem action='PopupFileRecent'/>
        <menuitem action='PopupFileClose'/>
    </menu>
    <menu action='PopupVideoMenu'>
      <menuitem action='PopupVideoSettings'/>
      <menuitem action='PopupVideoAspect'/>
    </menu>
    <menu action='PopupAudioMenu'>
      <menuitem action='PopupAudioExternal'/>
      <menuitem action='PopupAudioUnload'/>
    </menu>
    <menu action='PopupSubtitlesMenu'>
      <menuitem action='PopupSubtitlesExternal'/>
      <menuitem action='PopupSubtitlesSource'/>
    </menu>
    <menu action='PopupViewMenu'>
      <menuitem action='PopupViewOnTop'/>
      <menuitem action='PopupViewBorderless'/>
    </menu>
    <menuitem action='PopupSettings' />
    <menuitem action='PopupQuit' />
  </popup>
</ui>
"""

class ShellPlayer(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self, title="Shell Player")

        self.set_default_size(640, 360)
        self.set_position(Gtk.WindowPosition.CENTER)

        action_group = Gtk.ActionGroup("shell_player_actions")

        self.add_popup_menu_actions(action_group)
        self.add_file_menu_actions(action_group)
        self.add_view_menu_actions(action_group)
        self.add_video_menu_actions(action_group)
        self.add_audio_menu_actions(action_group)
        self.add_subtitles_menu_actions(action_group)

        self.uimanager = self.create_ui_manager()
        self.uimanager.insert_action_group(action_group)

        ui_css = """GtkEventBox {
                        background:black;
                    }
                    """
        css_provider = Gtk.CssProvider()
        screen = Gdk.Screen.get_default()
        context = Gtk.StyleContext()        
        css_provider.load_from_data(ui_css)
        context.add_provider_for_screen(screen, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        eventbox = Gtk.EventBox()
        eventbox.connect("draw", self.on_expose_event)
        
        eventbox.drag_dest_set(Gtk.DestDefaults.ALL, [], Gdk.DragAction.LINK)
        eventbox.drag_dest_add_uri_targets()

        self.connect("key-press-event", self.on_key_press_event)
        self.connect("motion-notify-event", self.on_motion_notify_event)
        self.connect("scroll-event", self.on_scroll_wheel_event)
        eventbox.connect("button-press-event", self.on_button_press_event)
        eventbox.connect("drag-data-received", self.on_drag_data_received)
        self.set_events(Gdk.EventMask.LEAVE_NOTIFY_MASK
             | Gdk.EventMask.BUTTON_PRESS_MASK
             | Gdk.EventMask.BUTTON_RELEASE_MASK
             | Gdk.EventMask.POINTER_MOTION_MASK
             | Gdk.EventMask.POINTER_MOTION_HINT_MASK
             | Gdk.EventMask.SCROLL_MASK)
        box.pack_start(eventbox, True, True, 0)

        manager = Gtk.RecentManager.get_default()
        self.recentchooser = Gtk.RecentChooserMenu()
        recentfilter = Gtk.RecentFilter()
        recentfilter.set_name('Video Files')
        recentfilter.add_mime_type('video/*')        
        self.recentchooser.add_filter(recentfilter)
        self.recentchooser.connect("item-activated", self.display_info)

        self.uimanager.get_widget("/PopupMenu/PopupFileMenu/PopupFileRecent").set_submenu(self.recentchooser)

        self.popup = self.uimanager.get_widget("/PopupMenu")

        self.add(box)

        self.mplayer = None
        self.above = False
        self.fullscreened = False
        self.compactness = 0
        self.resize_grip = 10
        self.playlist = []
        self.audio_source_merge_id = None

    def play_file(self, filename, args=[]):
        if self.mplayer.is_alive():
            self.mplayer.quit()
            self.mplayer = Player(args=stdargs + args)
        
        del self.playlist[:]
        self.playlist.append(filename)
        if not self.mplayer.filename:
            self.mplayer.loadfile(self.playlist[0])
        print self.mplayer.info
        if self.audio_source_merge_id:
             self.uimanager.remove_ui(self.audio_source_merge_id)
        AUDIO_INFO = """
        <ui>
          <popup name='PopupMenu'>
            <menu action='PopupAudioMenu'>
                <separator />
        """

        for key in self.mplayer.info['audio']:
            AUDIO_INFO += "<menuitem action='PopupAudioSource" + key + "'/>"

        AUDIO_INFO += """
            </menu>
          </popup>
        </ui>
        """
        action_group = Gtk.ActionGroup("audio_source_actions")
        self.add_audio_source_actions(action_group)
        self.uimanager.insert_action_group(action_group)
        self.audio_source_merge_id = self.uimanager.add_ui_from_string(AUDIO_INFO)

        self.resize(self.mplayer.width, self.mplayer.height)
        pass

    def choose_file(self, mime):
        dialog = Gtk.FileChooserDialog("Please choose a file", self,
            Gtk.FileChooserAction.OPEN,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_OPEN, Gtk.ResponseType.OK))

        self.add_filters(dialog, mime)

        response = dialog.run()
        filename = None
        if response == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
        elif response == Gtk.ResponseType.CANCEL:
            pass
        dialog.destroy()
        return filename

    def on_file_clicked(self, widget):
        filename = self.choose_file({'Media Files':['video/*', 'audio/*'], 'Any Files':['*']})
        if filename:
            self.play_file(filename)
        else:
            print 'canceled or wrong filename'

    def add_filters(self, dialog, mime):
        filter_text = Gtk.FileFilter()

        for key in mime:
            filefilter = Gtk.FileFilter()
            filefilter.set_name(key)
            for mime_type in mime[key]:
                filefilter.add_mime_type(mime_type)            
            dialog.add_filter(filefilter)

    def on_folder_clicked(self, widget):
        dialog = Gtk.FileChooserDialog("Please choose a folder", self,
            Gtk.FileChooserAction.SELECT_FOLDER,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             "Select", Gtk.ResponseType.OK))
        dialog.set_default_size(800, 400)

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            print "Select clicked"
            print "Folder selected: " + dialog.get_filename()
        elif response == Gtk.ResponseType.CANCEL:
            print "Cancel clicked"

        dialog.destroy()

    def add_popup_menu_actions(self, action_group):
        #settings button
        action_group.add_actions([
            ("PopupMenu", None, "Popup"),
            ("PopupSettings", Gtk.STOCK_PREFERENCES, None, None, None,
             self.on_menu_others)
        ])
        #quit button
        action_filequit = Gtk.Action("PopupQuit", "Quit", None, Gtk.STOCK_QUIT)
        action_filequit.connect("activate", self.on_menu_file_quit)
        action_group.add_action_with_accel(action_filequit, "Escape")

    def add_file_menu_actions(self, action_group):
        action_group.add_action(Gtk.Action("PopupFileMenu", "File", None, None))

        action_group.add_actions([
            ("PopupFileOpen", Gtk.STOCK_OPEN, None, None, None,
             self.on_file_clicked),
            ("PopupFileClose", Gtk.STOCK_CLOSE, None, None, None,
             self.on_folder_clicked),
            ("PopupFileRecent", None, 'Open Recent', None, None,
             None)
        ])

    def add_view_menu_actions(self, action_group):
        action_group.add_action(Gtk.Action("PopupViewMenu", "View", None, None))

        on_top = Gtk.ToggleAction("PopupViewOnTop", "On Top", None, None)
        on_top.connect("toggled", self.on_keep_on_top)
        action_group.add_action(on_top)

        borderless = Gtk.ToggleAction("PopupViewBorderless", "No Frame", None, None)
        borderless.set_active(True)
        borderless.connect("toggled", self.on_border_switch)
        action_group.add_action(borderless)

    def add_video_menu_actions(self, action_group):
        action_group.add_action(Gtk.Action("PopupVideoMenu", "Video", None, None))

        action_group.add_actions([
            ("PopupVideoSettings", None, "Settings", None, None,
             self.on_menu_others),
            ("PopupVideoAspect", None, "Aspect", None, None,
             self.on_menu_others)
        ])

    def add_audio_menu_actions(self, action_group):
        action_group.add_action(Gtk.Action("PopupAudioMenu", "Audio", None, None))

        action_group.add_actions([
            ("PopupAudioExternal", None, "External Audio", None, None,
             self.on_audio_external),
            ("PopupAudioUnload", None, "Unload External Audio", None, None,
             self.on_audio_unload)
        ])

    def add_audio_source_actions(self, action_group):
        for key in self.mplayer.info['audio']:
            info = ""
            lang = ""
            if 'info' in self.mplayer.info['audio'][key]:
                info = self.mplayer.info['audio'][key]['info']
            if 'lang' in self.mplayer.info['audio'][key]:
                lang = self.mplayer.info['audio'][key]['lang']
            action_group.add_actions([
                ("PopupAudioSource" + key, None, 'Audio: ' + key + ' ' + info + ' ' + lang, None, None,
                 self.on_audio_source)
            ])
        pass

    def add_subtitles_menu_actions(self, action_group):
        action_group.add_action(Gtk.Action("PopupSubtitlesMenu", "Subtitles", None, None))

        action_group.add_actions([
            ("PopupSubtitlesExternal", None, "Load External", None, None,
             self.on_menu_others),
            ("PopupSubtitlesSource", None, "Select Builtin", None, None,
             self.on_menu_others)
        ])

    def display_info(self, widget):
        selected = self.recentchooser.get_current_item().get_uri()
        path = self.get_file_path_from_dnd_dropped_uri(selected)
        self.play_file(path)

    def on_keep_on_top(self, widget):
        self.set_keep_above(not self.above)
        self.above = not self.above

    def on_border_switch(self, widget):
        self.set_decorated(not self.get_decorated())

    def on_audio_external(self, widget):
        if self.mplayer.is_alive() and self.mplayer.filename:
            self.mplayer.pause()
            audiofile = self.choose_file({'Media Files':['audio/*'], 'Any Files':['*']})
            if audiofile:
                filename = self.mplayer.path
                position = int(self.mplayer.time_pos)
                self.play_file(None, ['-audiofile', audiofile, '-ss', position, filename])
            else:
                self.mplayer.pause()
        pass

    def on_audio_unload(self, widget):
        if self.mplayer.is_alive() and self.mplayer.filename:
            filename = self.mplayer.path
            position = int(self.mplayer.time_pos)
            self.play_file(None, ['-ss', position, filename])
        pass

    def on_audio_source(self, widget):
        s = widget.get_name()
        if s[-2:].isdigit():
            idx = s[-2:]
        else:
            idx = s[-1]        
        if self.mplayer.switch_audio != idx:
            self.mplayer.pause()
            self.mplayer._run_command('switch_audio', idx)
            self.mplayer.pause()
        return True

    def create_ui_manager(self):
        uimanager = Gtk.UIManager()

        # Throws exception if something went wrong
        uimanager.add_ui_from_string(UI_INFO)

        # Add the accelerator group to the toplevel window
        accelgroup = uimanager.get_accel_group()
        self.add_accel_group(accelgroup)
        return uimanager

    def on_menu_file_quit(self, widget):
        if self.mplayer:
            self.mplayer.quit()
        Gtk.main_quit()

    def on_menu_others(self, widget):
        print "Menu item " + widget.get_name() + " was selected"

    def on_menu_choices_toggled(self, widget):
        if widget.get_active():
            print widget.get_name() + " activated"
        else:
            print widget.get_name() + " deactivated"

    def on_button_press_event(self, widget, event):
        # Check if right mouse button was preseed
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            self.popup.popup(None, None, None, None, event.button, event.time)
            return True # event has been handled

        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
            some, x, y, mods = self.get_screen().get_root_window().get_pointer()
            mouse_position = self.get_pointer()
            window_size = (self.get_window().get_width(), self.get_window().get_height())
            if mouse_position[0] < self.resize_grip and mouse_position[1] < self.resize_grip:
                self.begin_resize_drag(Gdk.WindowEdge.NORTH_WEST, event.button, x, y, event.time)
                return True
            if mouse_position[0] > window_size[0] - self.resize_grip and mouse_position[1] > window_size[1] - self.resize_grip:
                self.begin_resize_drag(Gdk.WindowEdge.SOUTH_EAST, event.button, x, y, event.time)
                return True
            if mouse_position[0] < self.resize_grip and mouse_position[1] > window_size[1] - self.resize_grip:
                self.begin_resize_drag(Gdk.WindowEdge.SOUTH_WEST, event.button, x, y, event.time)
                return True
            if mouse_position[0] > window_size[0] - self.resize_grip and mouse_position[1] < self.resize_grip:
                self.begin_resize_drag(Gdk.WindowEdge.NORTH_EAST, event.button, x, y, event.time)
                return True
            if mouse_position[0] < self.resize_grip:
                self.begin_resize_drag(Gdk.WindowEdge.WEST, event.button, x, y, event.time)
                return True
            if mouse_position[0] > window_size[0] - self.resize_grip:
                self.begin_resize_drag(Gdk.WindowEdge.EAST, event.button, x, y, event.time)
                return True
            if mouse_position[1] > window_size[1] - self.resize_grip:
                self.begin_resize_drag(Gdk.WindowEdge.SOUTH, event.button, x, y, event.time)
                return True
            if mouse_position[1] < self.resize_grip:
                self.begin_resize_drag(Gdk.WindowEdge.NORTH, event.button, x, y, event.time)
                return True            
            self.begin_move_drag(event.button, x, y, event.time)
            return True

        if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
            if not self.fullscreened:
                self.fullscreen()
                self.fullscreened = True
            else:
                self.unfullscreen()
                self.fullscreened = False
            return True

    def on_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_space:
            if self.mplayer.filename:
                self.mplayer.pause()
            else:
                if len(self.playlist) > 0:
                    self.play_file(self.playlist[0])
            return True
        if event.keyval == Gdk.KEY_r:
            return True
        if event.keyval == Gdk.KEY_l:
            metadata = self.mplayer.metadata or {}
            print metadata
            return True
        if event.state == Gdk.ModifierType.MOD1_MASK and event.keyval == Gdk.KEY_1:
            if self.mplayer.filename:
                self.resize(self.mplayer.width / 2, self.mplayer.height / 2)
            return True
        if event.state == Gdk.ModifierType.MOD1_MASK and event.keyval == Gdk.KEY_2:
            if self.mplayer.filename:
                self.resize(self.mplayer.width / 1.75, self.mplayer.height / 1.75)
            return True
        if event.state == Gdk.ModifierType.MOD1_MASK and event.keyval == Gdk.KEY_3:
            if self.mplayer.filename:
                self.resize(self.mplayer.width, self.mplayer.height)
            return True
        if event.keyval == Gdk.KEY_1:
            self.compactness = 0
            self.set_decorated(False)
            return True
        if event.keyval == Gdk.KEY_2:
            self.compactness = 1
            self.set_decorated(True)
            return True

        # else pass event to mplayer
        if self.mplayer.is_alive():
            self.mplayer.key_down_event(int(event.keyval))
            return True

    def on_motion_notify_event(self, widget, event):
        if self.compactness == 0:
            if event.type == Gdk.EventType.MOTION_NOTIFY:
                mouse_position = self.get_pointer()
                window_size = (self.get_window().get_width(), self.get_window().get_height())
                if mouse_position[0] < self.resize_grip and mouse_position[1] < self.resize_grip:
                    self.get_window().set_cursor (Gdk.Cursor(Gdk.CursorType.TOP_LEFT_CORNER))
                    return True
                if mouse_position[0] > window_size[0] - self.resize_grip and mouse_position[1] > window_size[1] - self.resize_grip:
                    self.get_window().set_cursor (Gdk.Cursor(Gdk.CursorType.BOTTOM_RIGHT_CORNER))
                    return True
                if mouse_position[0] < self.resize_grip and mouse_position[1] > window_size[1] - self.resize_grip:
                    self.get_window().set_cursor (Gdk.Cursor(Gdk.CursorType.BOTTOM_LEFT_CORNER))
                    return True
                if mouse_position[0] > window_size[0] - self.resize_grip and mouse_position[1] < self.resize_grip:
                    self.get_window().set_cursor (Gdk.Cursor(Gdk.CursorType.TOP_RIGHT_CORNER))
                    return True
                if mouse_position[0] < self.resize_grip:
                    self.get_window().set_cursor (Gdk.Cursor(Gdk.CursorType.LEFT_SIDE))
                    return True
                if mouse_position[0] > window_size[0] - self.resize_grip:
                    self.get_window().set_cursor (Gdk.Cursor(Gdk.CursorType.RIGHT_SIDE))
                    return True
                if mouse_position[1] > window_size[1] - self.resize_grip:
                    self.get_window().set_cursor (Gdk.Cursor(Gdk.CursorType.BOTTOM_SIDE))
                    return True
                if mouse_position[1] < self.resize_grip:
                    self.get_window().set_cursor (Gdk.Cursor(Gdk.CursorType.TOP_SIDE))
                    return True
                if self.get_window().get_cursor() != None and self.get_window().get_cursor().get_cursor_type() != Gdk.CursorType.ARROW:
                    self.get_window().set_cursor (Gdk.Cursor(Gdk.CursorType.ARROW))
                    return True
                # else pass event to mplayer
                if self.mplayer.is_alive():
                    self.mplayer.set_mouse_pos(mouse_position[0], mouse_position[1])
                    return True
        pass


    def on_scroll_wheel_event(self, widget, event):
        if event.direction == Gdk.ScrollDirection.UP:
            if self.mplayer.filename:
                vol = self.mplayer.volume + 10
                self.mplayer.volume = vol if vol < 100 else 100
            return True
        if event.direction == Gdk.ScrollDirection.DOWN:
            if self.mplayer.filename:
                vol = self.mplayer.volume - 10
                self.mplayer.volume = vol if vol >= 0 else 0
            return True
        pass

    def on_drag_data_received(self, widget, drag_context, x, y, data, info, time):
        del self.playlist[:]
        for uri in data.get_uris():
            path = self.get_file_path_from_dnd_dropped_uri(uri)
            self.playlist.append(path)
        if self.mplayer.is_alive():
            self.mplayer.quit()
            self.mplayer = Player(args=stdargs)
        self.mplayer.loadfile(self.playlist[0])
        print self.playlist
        return True

    def get_file_path_from_dnd_dropped_uri(self, uri):
        path = ""
        if uri.startswith('file:\\\\\\'): # windows
            path = uri[8:] # 8 is len('file:///')
        elif uri.startswith('file://'): # nautilus, rox
            path = uri[7:] # 7 is len('file://')
        elif uri.startswith('file:'): # xffm
            path = uri[5:] # 5 is len('file:')

        path = urllib.url2pathname(path) # escape special chars
        path = path.strip('\r\n\x00') # remove \r\n and NULL

        return path

    def on_expose_event(self, widget, event):        
        # print('kok')
        # ctx = self.get_window().cairo_create()
        # Gtk.paint_resize_grip(self.get_default_style(), ctx, Gtk.StateType.NORMAL, self, "", Gdk.WindowEdge.WEST, -10, -10,
        #     0, 0)
        pass

# initialize window
window = ShellPlayer()
window.set_decorated(False)
window.connect("delete-event", Gtk.main_quit)
settings = Gtk.Settings.get_default()
settings.set_property("gtk-application-prefer-dark-theme", True)
window.show_all()

# bind mplayer.py instance
stdargs = ['-wid', str(window.get_window().get_xid()), '-fs', '-osdlevel', str(0), '-identify', '-ass']
if len(sys.argv) > 1:
    window.mplayer = Player(args=stdargs)
    window.mplayer.loadfile(sys.argv[1])
else:
    window.mplayer = Player(args=stdargs)

Gtk.main()