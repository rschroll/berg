from gi.repository import Gtk, Soup
import os
import mimetypes
import posixpath
import zipfile
from xml.dom import minidom
import json

class Epub(zipfile.ZipFile):
    
    def __init__(self, *args):
        zipfile.ZipFile.__init__(self, *args)
        self.spine = []
        self.metadata = {}
        self.contents = []
        self.parseOPF()
    
    def parseOPF(self):
        container = minidom.parseString(self.read('META-INF/container.xml'))
        contentsfn = None
        for rootfile in container.getElementsByTagName('rootfile'):
            if rootfile.getAttribute('media-type') == "application/oebps-package+xml":
                contentsfn = rootfile.getAttribute('full-path')
                break
        if not contentsfn:
            raise zipfile.BadZipFile("Could not find contents file")
        contentsdir, _, _ = contentsfn.rpartition('/')
        if contentsdir:
            contentsdir += '/'
        
        idmap = {}
        contents = minidom.parseString(self.read(contentsfn))
        manifest = contents.getElementsByTagName('manifest')[0]
        nav_href = None
        for item in manifest.getElementsByTagName('item'):
            idmap[item.getAttribute('id')] = contentsdir + item.getAttribute('href')
            if 'nav' in item.getAttribute('properties').split(' '):
                nav_href = idmap[item.getAttribute('id')]
        spine = contents.getElementsByTagName('spine')[0]
        for item in spine.getElementsByTagName('itemref'):
            self.spine.append(idmap[item.getAttribute('idref')])
        metadata = contents.getElementsByTagName('metadata')[0]
        for node in metadata.childNodes:
            if node.nodeType is minidom.Node.ELEMENT_NODE:
                try:
                    self.metadata[node.localName] = node.firstChild.nodeValue
                except AttributeError:
                    pass
        if nav_href:  # EPUB 3
            self.parse_nav(nav_href)
        else:
            try:  # EPUB 2
                self.parse_NCX(idmap[spine.getAttribute('toc')])
            except KeyError:
                pass
    
    def parse_nav(self, navfile):
        self.navdir, _, _ = navfile.rpartition('/')
        if self.navdir:
            self.navdir += '/'
        navdoc = minidom.parseString(self.read(navfile))
        for nav in navdoc.getElementsByTagName('nav'):
            if nav.getAttribute('epub:type') == 'toc':
                self.contents = self.parse_nav_list(nav.getElementsByTagName('ol')[0])
    
    def parse_nav_list(self, element):
        children = []
        for item in element.childNodes:
            if item.nodeType is minidom.Node.ELEMENT_NODE and item.nodeName == 'li':
                try:
                    link = item.getElementsByTagName('a')[0]
                except IndexError:
                    continue
                children.append({'title': link.firstChild.nodeValue,
                                 'src': self.navdir + link.getAttribute('href')})
                olist = item.getElementsByTagName('ol')
                if olist:
                    children[-1]['children'] = self.parse_nav_list(olist[0])
        return children
    
    def parse_NCX(self, ncxfile):
        self.navdir, _, _ = ncxfile.rpartition('/')
        if self.navdir:
            self.navdir += '/'
        ncx = minidom.parseString(self.read(ncxfile))
        navmap = ncx.getElementsByTagName('navMap')[0]
        self.contents = self.parse_NCX_children(navmap)
    
    def parse_NCX_children(self, element):
        children = []
        for node in element.childNodes:
            if node.nodeType is minidom.Node.ELEMENT_NODE and node.nodeName == 'navPoint':
                children.append({})
                nav_label = node.getElementsByTagName('text')[0]
                children[-1]['title'] = nav_label.firstChild.nodeValue
                content = node.getElementsByTagName('content')[0]
                children[-1]['src'] = self.navdir + content.getAttribute('src')
                child_nav = self.parse_NCX_children(node)
                if child_nav:
                    children[-1]['children'] = child_nav
        return children
    
    @property
    def book_data(self):
        return '''{
            getComponents: function () {
                return %s;
            },
            getContents: function () {
                return %s;
            },
            getComponent: function (component) {
                return { url: component };
            },
            getMetaData: function (key) {
                return %s[key];
            }
        }''' % (json.dumps(self.spine), json.dumps(self.contents), json.dumps(self.metadata))


class EpubServer(Soup.Server):
    
    def __init__(self, *args, **kw):
        """Arguments are passed to Soup.Server."""
        Soup.Server.__init__(self, *args, **kw)
        self.epub = None
        
        self.add_handler('/.bookdata.js', self.book_data)
        self.add_handler('/.application_menu', self.app_menu_icon)
        self.add_handler('/.', self.static)
        self.add_handler('/', self.root)
        
        self.run_async()
    
    def book_data(self, server, message, path, query, client):
        if not self.epub:
            message.set_status(Soup.Status.NOT_FOUND)
            return
        
        message.set_status(Soup.Status.OK)
        message.set_response('application/javascript', Soup.MemoryUse.COPY,
            "var bookData = %s" % self.epub.book_data)
    
    def app_menu_icon(self, server, message, path, query, client):
        icon = Gtk.IconTheme.get_default().lookup_icon('emblem-system', 20, 0)
        self.serve_resource(message, icon.get_filename())
    
    def static(self, server, message, path, query, client):
        self.serve_resource(message, path[2:])
    
    def serve_resource(self, message, path):
        resource_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')
        try:
            f = open(os.path.join(resource_dir, path), 'rb')
        except IOError:
            message.set_status(Soup.Status.NOT_FOUND)
            return
        
        message.set_status(Soup.Status.OK)
        message.set_response(self.guess_type(path), Soup.MemoryUse.COPY, f.read())
    
    def root(self, server, message, path, query, client):
        if path == '/':
            return self.index(message, query)
        if self.epub is None:
            message.set_status(Soup.Status.INTERNAL_SERVER_ERROR)
            return
        if path[1:] in self.epub.namelist():
            return self.from_epub(message, path[1:])
        message.set_status(Soup.Status.NOT_FOUND)
    
    def index(self, message, query):
        epub_path = query.get('load')
        if epub_path:
            if self.epub is not None:
                self.epub.close()
            try:
                self.epub = Epub(epub_path, 'r')
            except (IOError, zipfile.BadZipfile):
                message.set_status(Soup.Status.INTERNAL_SERVER_ERROR)
                message.set_response('text/plain', Soup.MemoryUse.COPY,
                    "Could not load epub at " + epub_path)
                self.epub = None
                return
        
        if self.epub:
            self.serve_resource(message, 'index.html')
        else:
            self.serve_resource(message, 'load.html')
    
    def from_epub(self, message, path):
        info = self.epub.getinfo(path)
        message.set_status(Soup.Status.OK)
        f = self.epub.open(info, 'r')
        message.set_response(self.guess_type(path), Soup.MemoryUse.COPY, f.read())
    
    def guess_type(self, path):
        base, ext = posixpath.splitext(path)
        if not mimetypes.inited:
            mimetypes.init()
        try:
            return mimetypes.types_map[ext]
        except KeyError:
            try:
                return mimetypes.types_map[ext.lower()]
            except KeyError:
                return 'application/octet-stream'


if __name__ == '__main__':
    import sys
    import webbrowser
    from gi.repository import GLib
    
    if len(sys.argv) == 1:
        print "Pass the path the the EPUB file as the first argument"
        raise SystemExit
    
    server = EpubServer(port=8080)
    webbrowser.open('http://localhost:8080/?load=%s' % os.path.abspath(sys.argv[1]))
    loop = GLib.MainLoop()
    loop.run()
