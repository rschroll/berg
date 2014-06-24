from gi.repository import GObject, GLib, Gdk, Gtk, WebKit
import urllib2
import threading
import socket
import epubserver
from readersettings import ReaderSettings
GObject.threads_init()

NONE, WAITING, ACCEPT, REJECT = range(4)

class DNDWebView(WebKit.WebView):
    
    def __init__(self, *args):
        WebKit.WebView.__init__(self, *args)
        self.accept_dnd = NONE
        self.dnd_data = None
    
    def do_drag_motion(self, context, x, y, time, user_data=None):
        if self.accept_dnd is REJECT:
            Gdk.drag_status(context, 0, time)
        elif self.accept_dnd is NONE:
            target = self.drag_dest_find_target(context, None)
            if target == 0: #Gdk.NONE:
                self.accept_dnd = REJECT
                Gdk.drag_status(context, 0, time)
            else:
                self.drag_get_data(context, target, time)
                self.accept_dnd = WAITING
        return True  # Use drag_status to say yes or no; otherwise drag_leave called
    
    def do_drag_data_received(self, context, x, y, data, info, time):
        self.dnd_data = data.get_text().strip()
        if self.dnd_data.endswith('.epub'):
            self.accept_dnd = ACCEPT
            Gdk.drag_status(context, Gdk.DragAction.COPY, time)
        else:
            self.accept_dnd = REJECT
            Gdk.drag_status(context, 0, time)
    
    def do_drag_drop(self, context, x, y, time, user_data=None):
        Gtk.drag_finish(context, True, False, time)
    
    def do_drag_leave(self, context, time, user_data=None):
        self.accept_dnd = NONE

class EpubReader(Gtk.ApplicationWindow):
    
    def __init__(self, application, filename=""):
        Gtk.ApplicationWindow.__init__(self, application=application,
                                       default_width=450, default_height=600)
        self.application = application
        self.load_file_lazy(filename)
        
        self.set_title("Berg")
        # Work-around for application title
        # http://stackoverflow.com/questions/9324163/how-to-set-application-title-in-gnome-shell
        self.set_wmclass("Berg", "Berg")
        self.connect('key-press-event', self.on_key_press)
        self.connect('configure-event', self.on_configure)
        self._size = (0, 0)
        self._resize_timeout = None
        
        self.establish_actions()
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.view = DNDWebView()
        self.view.connect('drag-drop', self.on_drag_drop)
        sw.add(self.view)
        self.add(sw)
        self.view.connect('title-changed', self.on_title_changed)
        self.view.connect('navigation-policy-decision-requested', self.on_navigation_policy_decision_requested)
        self.view.connect('console-message', self.on_console_message)
        
        self.settings = ReaderSettings(self)
        
        self.show_all()
        
        self.spawn_server()
    
    def establish_actions(self):
        action_group = Gtk.ActionGroup('main')
        action_group.add_actions((
                ('quit',    Gtk.STOCK_QUIT,         "Quit",         "<control>w", None, self.on_quit),
                ('settings',Gtk.STOCK_PREFERENCES,  "Settings",     None,         None, self.on_settings),
                ('reload',  Gtk.STOCK_REFRESH,      "Refresh",      "<control>r", None, self.on_reload)
        ))
        
        # Note: ui_manager must be property of self, or accelerators don't work.  This is probably
        # because it would be garbage collected otherwise.
        self.ui_manager = Gtk.UIManager()
        self.ui_manager.insert_action_group(action_group)
        self.ui_manager.add_ui_from_string('''
                <ui>
                    <accelerator action="quit"/>
                    <accelerator action="reload"/>
                </ui>
        ''')
        
        self.ui_manager.ensure_update()
        self.add_accel_group(self.ui_manager.get_accel_group())
    
    def spawn_server(self):
        self.server = epubserver.EpubServer()
        self.port = self.server.get_port()
    
    def load_file_lazy(self, filename):
        GLib.idle_add(self.load_file, filename)
    
    def load_file(self, filename):
        self.view.load_uri("http://localhost:%i/?load=%s" % (self.port, filename))
    
    def on_drag_drop(self, widget, context, x, y, time, data=None):
        filename = self.view.dnd_data
        if filename.startswith('file://'):
            filename = filename[7:]
        self.application.load_file(filename)
    
    def on_quit(self, *args):
        self.destroy()
    
    def on_settings(self, *args):
        self.settings.show()
    
    def on_reload(self, *args):
        self.view.reload()
    
    def on_key_press(self, widget, event):
        # Check that none of Shift, Control, Alt are pressed
        if ((Gdk.ModifierType.SHIFT_MASK | Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.MOD1_MASK)
                & event.state) == 0:
            if event.keyval in (Gdk.KEY_Right, Gdk.KEY_Down, Gdk.KEY_space, Gdk.KEY_period):
                self.change_page(1)
                return True
            if event.keyval in (Gdk.KEY_Left, Gdk.KEY_Up, Gdk.KEY_BackSpace, Gdk.KEY_comma):
                self.change_page(-1)
                return True
        return False
    
    def on_configure(self, widget, event):
        if self._size == (event.width, event.height):
            return
        
        self._size = (event.width, event.height)
        if self._resize_timeout is not None:
            GObject.source_remove(self._resize_timeout)
        self._resize_timeout = GObject.timeout_add(500,
                lambda *args: self.view.execute_script('reader.resized();'))
    
    def on_title_changed(self, web_view, frame, title):
        self.set_title(title)
    
    def on_navigation_policy_decision_requested(self, web_view, frame, request, navigation, policy_decision):
        if request.get_uri() == 'settings://':
            policy_decision.ignore()
            self.on_settings()
            return True
        return False
    
    def on_console_message(self, web_view, message, line, source_id):
        if message == 'Ready':
            self.settings.update_styles()
            return True
        return not self.application.debug
    
    def change_page(self, direction=1):
        self.view.execute_script('reader.moveTo({direction: %i})' % direction)
