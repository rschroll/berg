import os
from gi.repository import Gtk, Gio, GObject, GLib
from optparse import OptionParser
from epubreader import EpubReader

class Application(Gtk.Application):
    
    def __init__(self):
        Gtk.Application.__init__(self, application_id='apps.berg',
                                 flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.connect('startup', self.on_startup)
        self.connect('activate', self.on_activate)
        self.files = None
        self.debug = False
    
    def on_startup(self, data=None):
        for name, ptype, callback in (('open', None, self.on_open),
                                      ('quit', None, self.on_quit),
                                      ('set-files', GLib.VariantType.new('as'), self.on_set_files),
                                      ('set-debug', GLib.VariantType.new('b'), self.on_set_debug)):
            action = Gio.SimpleAction(name=name, parameter_type=ptype)
            action.connect('activate', callback)
            self.add_action(action)
        
        builder = Gtk.Builder()
        builder.add_from_string('''
        <interface>
            <menu id="app-menu">
                <section>
                    <item>
                        <attribute name="label" translatable="yes">Open File</attribute>
                        <attribute name="action">app.open</attribute>
                        <attribute name="accel">&lt;Primary&gt;o</attribute>
                    </item>
                </section>
                <section>
                    <item>
                        <attribute name="label" translatable="yes">_Quit</attribute>
                        <attribute name="action">app.quit</attribute>
                        <attribute name="accel">&lt;Primary&gt;q</attribute>
                    </item>
                </section>
            </menu>
        </interface>
        ''')
        self.set_app_menu(builder.get_object('app-menu'))
    
    def on_activate(self, application, data=None):
        if self.files is None:
            return
        
        for f in self.files:
            self.load_file(f)
        self.args = None
        
        windows = self.get_windows()
        if windows:
            for window in windows:
                if window.is_active():
                    break
            else:
                windows[0].present()
        else:
            EpubReader(self)
    
    def run(self, args):
        parser = OptionParser(usage="Usage", description="Description", version="version")
        parser.add_option('-d', '--debug', action='store_true', default=False,
                          help='print debugging information')
        options, args = parser.parse_args(args)
        files = [os.path.abspath(arg) for arg in args if os.path.isfile(arg)]
        
        self.register(None)
        if self.get_is_remote():
            self.activate_action('set-files', GLib.Variant('as', files))
            self.activate_action('set-debug', GLib.Variant('b', options.debug))
        else:
            self.files = files
            self.debug = options.debug
        Gtk.Application.run(self, None)  # Will trigger 'activate' signal
    
    def on_set_files(self, action, gv_files):
        self.files = gv_files.unpack()
    
    def on_set_debug(self, action, gv_debug):
        self.debug = gv_debug.unpack()
    
    def on_open(self, action, data=None):
        dialog = Gtk.FileChooserDialog("Open...", None, Gtk.FileChooserAction.OPEN,
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
            self.load_file(filename)
        dialog.destroy()
    
    def on_quit(self, action, data=None):
        for window in self.get_windows():
            window.on_quit()
        self.quit()
    
    def load_file(self, filename):
        for window in self.get_windows():
            if window.server.epub is None:
                window.load_file_lazy(filename)
                return
        
        EpubReader(self, filename)


if __name__ == '__main__':
    import sys
    
    # From https://github.com/MicahCarrick/python-bloatpad
    old_hook = sys.excepthook
    def new_hook(etype, evalue, etb):
        old_hook(etype, evalue, etb)
        while Gtk.main_level():
            Gtk.main_quit()
        sys.exit()
    sys.excepthook = new_hook
    
    app = Application()
    app.run(sys.argv[1:])
