Berg - A Basic Epub Reader for Gnome
====================================
Berg is a basic Epub reader for Gnome and other GTK environments.  It
uses the [Monocle library][1] to display DRM-free Epub files in a GTK
container.  Berg is basically the result of a weekend's exploration of
Monocle and Gtk.Application.  It is not, and will probably never be,
done.

[1]: http://monocle.inventivelabs.com.au/

Usage
-----
After cloning the repository, launch Berg with
```
python berg/application.py <filename>
```
Additional files may be opened through the application menu or by
dragging-and-dropping the files on an open window.

You can turn pages with the arrow keys, space and backspace, or by
clicking on the left and right halves of the page.  The drop-down menu
at the top offers a table of contents and a number of options for the
display of the epub.  Neither these settings nor your location in the
book are currently saved.

For a more complete implementation, check out [Beru][2].

[2]: http://rschroll.github.io/beru

License
-------
Berg is distributed under the MIT license:

Copyright 2013-2014 Robert Schroll

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
