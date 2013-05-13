from gi.repository import Gtk, Gdk, GObject
import os

def make_color(spec):
    return Gdk.Color.parse(spec)[1]

def get_color(gdk_color):
    return '#%02x%02x%02x' % tuple(map(lambda x: x/65535.*255, (gdk_color.red, gdk_color.green, gdk_color.blue)))

class ReaderSettings(object):
    
    DEFAULT_SETTINGS = {'text_color': '#000',
                        'background_color': '#fff',
                        'font': 'normal normal 12pt "Serif"',
                        'font_scale': 1.0,
                        'default_font': True,
                        'line_height': 1.2,
                        'margin_top': 5,
                        'margin_left': 10,
                        'margin_right': 10,
                        'margin_bottom': 10,
                       }
    
    def __init__(self, parent, **kw):
        self.parent = parent
        
        builder = Gtk.Builder()
        builder.add_from_file(os.path.join(os.path.dirname(__file__), 'settings.glade'))
        builder.connect_signals(self)
        self.dialog = builder.get_object('settings-dialog')
        self.dialog.set_transient_for(self.parent)
        self.dialog.set_modal(True)
        
        self._background_color = builder.get_object('background-color-button')
        self._text_color = builder.get_object('text-color-button')
        self._font = builder.get_object('font-button')
        self._font_scale = builder.get_object('font-scale')
        self._font_scale_timeout = None
        self._default_font = builder.get_object('default-font-button')
        self._line_height = builder.get_object('line-height-button')
        self._line_height_label = builder.get_object('line-height-label')
        self._margin_top = builder.get_object('margin-top-button')
        self._margin_left = builder.get_object('margin-left-button')
        self._margin_right = builder.get_object('margin-right-button')
        self._margin_bottom = builder.get_object('margin-bottom-button')
        
        settings = self.DEFAULT_SETTINGS.copy()
        settings.update(kw)
        self._updating = True
        self.dict = settings
        self._updating = False
    
    @property
    def background_color(self):
        return get_color(self._background_color.get_color())
    @background_color.setter
    def background_color(self, value):
        self._background_color.set_color(make_color(value))
    
    @property
    def text_color(self):
        return get_color(self._text_color.get_color())
    @text_color.setter
    def text_color(self, value):
        self._text_color.set_color(make_color(value))
    
    @property
    def font(self):
        font, size = self._font.get_font().rsplit(' ', 1)
        style = 'normal'
        weight = 'normal'
        if ' Italic' in font:
            font = font.replace(' Italic', '')
            style = 'italic'
        elif ' Oblique' in font:
            font = font.replace(' Oblique', '')
            style = 'oblique'
        if ' Bold' in font:
            font = font.replace(' Bold', '')
            weight = 'bold'
        elif ' Light' in font:
            font = font.replace(' Light', '')
            weight = 'lighter'
        # Some fonts have a comma here that we don't want.
        if font[-1] == ',':
            font = font[:-1]
        return '%s %s %spt "%s"' % (style, weight, size, font)
    @font.setter
    def font(self, value):
        style, weight, size, font = value.split(' ', 3)
        size = size[:-2]
        font = font[1:-1] + ','  # Sometimes extra, but doesn't seem to hurt
        if weight == 'bold':
            font += ' Bold'
        elif weight == 'lighter':
            font += ' Light'
        if style == 'italic':
            font += ' Italic'
        elif style == 'oblique':
            font += ' Oblique'
        self._font.set_font('%s %s' % (font, size))
    
    @property
    def font_scale(self):
        return self._font_scale.get_value()
    @font_scale.setter
    def font_scale(self, value):
        self._font_scale.set_value(value)
    
    @property
    def default_font(self):
        return self._default_font.get_active()
    @default_font.setter
    def default_font(self, value):
        self._default_font.set_active(value)
    
    @property
    def line_height(self):
        return self._line_height.get_value()
    @line_height.setter
    def line_height(self, value):
        self._line_height.set_value(value)
    
    @property
    def margin_top(self):
        return self._margin_top.get_value()
    @margin_top.setter
    def margin_top(self, value):
        self._margin_top.set_value(value)
    
    @property
    def margin_left(self):
        return self._margin_left.get_value()
    @margin_left.setter
    def margin_left(self, value):
        self._margin_left.set_value(value)
    
    @property
    def margin_right(self):
        return self._margin_right.get_value()
    @margin_right.setter
    def margin_right(self, value):
        self._margin_right.set_value(value)
    
    @property
    def margin_bottom(self):
        return self._margin_bottom.get_value()
    @margin_bottom.setter
    def margin_bottom(self, value):
        self._margin_bottom.set_value(value)
    
    @property
    def dict(self):
        d = {}
        for k in self.DEFAULT_SETTINGS:
            d[k] = getattr(self, k)
        return d
    @dict.setter
    def dict(self, value):
        for k in value:
            if k in self.DEFAULT_SETTINGS:
                setattr(self, k, value[k])
    
    def update_styles(self, *args):
        if not self._updating:
            self.parent.view.execute_script(("updateStyles('{text_color}', '{background_color}', " +
                "'{font}', {line_height}, {default_font:b}, {font_scale}, {margin_top}, {margin_left}, " +
                "{margin_right}, {margin_bottom});").format(**self.dict))
    
    def on_font_scale(self, widget):
        if self._font_scale_timeout is not None:
            GObject.source_remove(self._font_scale_timeout)
        self._font_scale_timeout = GObject.timeout_add(500, self.update_styles)
    
    def on_default_font_toggled(self, widget):
        self._font.set_sensitive(not self.default_font)
        self._line_height.set_sensitive(not self.default_font)
        self._line_height_label.set_sensitive(not self.default_font)
        self.update_styles()
    
    def on_margin_output(self, widget):
        value = widget.get_value()
        widget.set_text('%d%%' % value)
        return True
    
    def on_close(self, *args):
        self.dialog.hide()
    
    def show(self):
        self.dialog.show()
