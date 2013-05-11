from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import urlparse
import os
import shutil
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


class EpubServer(HTTPServer):
    
    def __init__(self, *args):
        HTTPServer.__init__(self, *args)
        self.epub = None
        self.keep_running = True
    
    def run(self):
        while self.keep_running:
            self.handle_request()

class EpubHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        parsed_path = urlparse.urlparse(self.path)
        path = parsed_path.path[1:]  # strip leading /
        if path == '.halt':
            return self.halt()
        if path == '.bookdata.js':
            return self.book_data()
        if path.startswith('.'):
            return self.static(path[1:])
        if path == '':
            return self.index(parsed_path.query)
        if self.server.epub is None:
            self.send_error(500, "Epub not loaded")
            return
        if path in self.server.epub.namelist():
            return self.from_epub(path)
        self.send_error(404)
    
    def halt(self):
        self.server.keep_running = False
        self.send_response(200)
        self.end_headers()
        self.wfile.write("Good-bye")
    
    def book_data(self):
        if not self.server.epub:
            self.send_error(404)
            return
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write("var bookData = %s" % self.server.epub.book_data)
    
    def index(self, epub_path):
        if epub_path:
            if self.server.epub is not None:
                self.server.epub.close()
            try:
                self.server.epub = Epub(epub_path, 'r')
            except (IOError, zipfile.BadZipfile):
                self.send_error(500, "Could not load epub at " + epub_path)
                self.server.epub = None
                return
        
        if self.server.epub:
            self.static('index.html')
        else:
            self.static('load.html')
    
    def static(self, path):
        resource_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources')
        try:
            f = open(os.path.join(resource_dir, path), 'rb')
        except IOError:
            self.send_error(404)
            return
        
        self.send_response(200)
        self.send_header("Content-type", self.guess_type(path))
        fs = os.fstat(f.fileno())
        self.send_header("Content-Length", str(fs[6]))
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        shutil.copyfileobj(f, self.wfile)
    
    def from_epub(self, path):
        info = self.server.epub.getinfo(path)
        self.send_response(200)
        self.send_header("Content-type", self.guess_type(path))
        self.send_header("Content-Length", info.file_size)
        self.end_headers()
        f = self.server.epub.open(info, 'r')
        shutil.copyfileobj(f, self.wfile)
    
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
    import webbrowser
    server = EpubServer(('localhost', 8080), EpubHandler)
    webbrowser.open('http://localhost:8080')
    server.run()
