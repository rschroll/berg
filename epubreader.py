from gi.repository import GObject, GLib, Gdk, Gtk, WebKit
import urllib2
import threading
import socket
import epubserver
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

class EpubReader(Gtk.Window):
    
    def __init__(self, filename=""):
        Gtk.Window.__init__(self)
        self.load_file_lazy(filename)
        
        self.set_title("Epub Reader")
        self.connect('destroy', self.on_quit)
        self.set_default_size(300,400)
        
        self.establish_actions()
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.view = DNDWebView()
        self.view.connect('drag-drop', self.on_drag_drop)
        sw.add(self.view)
        self.add(sw)
        
        self.show_all()
        
        self.spawn_server()
        
        Gtk.main()
    
    def establish_actions(self):
        action_group = Gtk.ActionGroup('main')
        action_group.add_actions((
                ('open',    Gtk.STOCK_OPEN,     "_Open EPUB",   "<control>o", None, self.on_open),
                ('quit',    Gtk.STOCK_QUIT,     "Quit",         "<control>w", None, self.on_quit),
                ('prefs',   Gtk.STOCK_PREFERENCES,  "Preferences", None, None, self.on_prefs),
                ('reload',  Gtk.STOCK_REFRESH,  "Refresh",      "<control>r", None, self.on_reload)
        ))
        
        # Note: ui_manager must be property of self, or accelerators don't work.  This is probably
        # because it would be garbage collected otherwise.
        self.ui_manager = Gtk.UIManager()
        self.ui_manager.insert_action_group(action_group)
        self.ui_manager.add_ui_from_string('''
                <ui>
                    <accelerator action="open"/>
                    <accelerator action="quit"/>
                    <accelerator action="reload"/>
                </ui>
        ''')
        
        self.ui_manager.ensure_update()
        self.add_accel_group(self.ui_manager.get_accel_group())
    
    def spawn_server(self):
        self.server = epubserver.EpubServer(('localhost', 0), epubserver.EpubHandler)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.run)
        self.thread.start()
        
    def on_quit(self, *args):
        try:
            urllib2.urlopen("http://localhost:%s/.halt" % self.port).read()
        except urllib2.URLError:
            pass
        Gtk.main_quit()
        self.thread.join(2)
        if self.thread.isAlive():
            print "Server thread won't die!"
    
    def load_file_lazy(self, filename):
        GLib.idle_add(self.load_file, filename)
    
    def load_file(self, filename):
        if self.server.epub:
            EpubReader(filename)
        else:
            self.view.load_uri("http://localhost:%i/?%s" % (self.port, filename))
    
    def on_open(self, *args):
        dialog = Gtk.FileChooserDialog("Open...", self, Gtk.FileChooserAction.OPEN,
                                       (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                                        Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        for name, pattern in (('Epub Files', '*.epub'), ('All Files', '*')):
            filt = Gtk.FileFilter()
            filt.set_name(name)
            filt.add_pattern(pattern)
            dialog.add_filter(filt)
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
            self.load_file_lazy(filename)
        dialog.destroy()
    
    def on_drag_drop(self, widget, context, x, y, time, data=None):
        filename = self.view.dnd_data
        if filename.startswith('file://'):
            filename = filename[7:]
        self.load_file_lazy(filename)
    
    def on_prefs(self, *args):
        pass
    
    def on_reload(self, *args):
        self.view.reload()
        

if __name__ == '__main__':
    import sys
    EpubReader(*sys.argv[1:])
