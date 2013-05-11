import os
from gi.repository import Gtk, Gio
from optparse import OptionParser
from epubreader import EpubReader

class NoExitParser(OptionParser):
    
    def __init__(self, *args, **kw):
        OptionParser.__init__(self, *args, **kw)
        self.exit_status = None
    
    def exit(self, status=0, msg=None):
        if msg:
            sys.stderr.write(msg)
        self.exit_status = status
    
    def check_values(self, values, args):
        return (values, args, self.exit_status)

class Application(Gtk.Application):
    
    def __init__(self):
        Gtk.Application.__init__(self, application_id='apps.berg',
                                 flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.connect('startup', self.startup)
        #self.connect('activate', self.activate)
        self.connect('command-line', self.command_line)
    
    def startup(self, data=None):
        for name, callback in (('open', self.on_open), ('quit', self.on_quit)):
            action = Gio.SimpleAction(name=name)
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
    
    def command_line(self, application, command_line):
        parser = NoExitParser(usage="Usage", description="Description", version="version")
        parser.add_option('-d', '--debug', action='store_true', default=False,
                          help='print debugging information')
        
        options, args, exit_status = parser.parse_args(command_line.get_arguments()[1:])
        if exit_status != None:
            print "Should exit with status", exit_status
            return 0
        
        self.debug = options.debug
        for arg in args:
            if os.path.isfile(arg):
                self.load_file(arg)
        
        windows = self.get_windows()
        if windows:
            for window in windows:
                if window.is_active():
                    break
            else:
                windows[0].present()
        else:
            EpubReader(self)
        
        return 0
    
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
    app = Application()
    app.register(None)
    if app.get_is_remote():
        print "Already running"
    app.run(sys.argv)
