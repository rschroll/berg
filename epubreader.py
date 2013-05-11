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
        
        vbox = Gtk.VBox()
        topbar = self.establish_actions()
        vbox.pack_start(topbar, False, False, 0)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.view = DNDWebView()
        self.view.connect('drag-drop', self.on_drag_drop)
        #self.enable_dnd()
        sw.add(self.view)
        vbox.pack_start(sw, True, True, 0)
        self.add(vbox)
        
        self.show_all()
        
        self.spawn_server()
        
        Gtk.main()
    
    def establish_actions(self):
        action_group = Gtk.ActionGroup('main')
        action_group.add_actions((
                ('open',    Gtk.STOCK_OPEN,     "_Open EPUB",   "<control>o", None, self.on_open),
                ('quit',    Gtk.STOCK_QUIT,     "Quit",         "<control>w", None, self.on_quit),
                ('prefs',   Gtk.STOCK_PREFERENCES,  "Preferences", None, None, self.on_prefs),
                ('prevp',   Gtk.STOCK_GO_BACK,  "Previous Page", None, None, self.page_back),
                ('nextp',   Gtk.STOCK_GO_FORWARD, "Next Page", None, None, self.page_forward),
                ('reload', Gtk.STOCK_REFRESH,  "Refresh",      "<control>r", None, self.on_reload)
        ))
        
        ui_manager = Gtk.UIManager()
        ui_manager.insert_action_group(action_group)
        ui_manager.add_ui_from_string('''
                <ui>
                    <toolbar name="topbar" action="toolbar">
                        <toolitem action="prevp"/>
                        <toolitem action="nextp"/>
                        <separator/>
                        <toolitem action="open"/>
                        <toolitem action="prefs"/>
                        <toolitem action="reload"/>
                    </toolbar>
                    <accelerator action="open"/>
                    <accelerator action="quit"/>
                    <accelerator action="reload"/>
                </ui>
        ''')
        
        ui_manager.ensure_update()
        self.add_accel_group(ui_manager.get_accel_group())
        return ui_manager.get_widget('/topbar')
    
    def enable_dnd(self):
        self.view.connect('drag-data-received', self.on_drag_data_received)
        self.view.connect('drag-drop', self.on_drag_drop)
        self.view.connect('drag-motion', self.on_drag_motion)
        self.view.connect('drag-leave', self.on_drag_leave)
    
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
    
    def on_drag_data_received(self, widget, drag_context, x, y, data, info, time):
        print "Drag datrec", data.get_text(), info
        #Gtk.drag_finish(drag_context, False, False, time)
    
    def on_drag_drop(self, widget, context, x, y, time, data=None):
        filename = self.view.dnd_data
        if filename.startswith('file://'):
            filename = filename[7:]
        self.load_file_lazy(filename)
    
    def on_drag_motion(self, *args):
        print "Motion!", args
        return False
    
    def on_drag_leave(self, *args):
        print "Drag leave"
    
    def on_prefs(self, *args):
        pass
    
    def page_back(self, *args):
        pass
    
    def page_forward(self, *args):
        pass
    
    def on_reload(self, *args):
        self.view.reload()
        

if __name__ == '__main__':
    import sys
    EpubReader(*sys.argv[1:])
