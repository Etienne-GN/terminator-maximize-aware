"""Terminator plugin: show passive cues when a terminal is maximised while
sibling terminals in the current tab are hidden."""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from terminatorlib import plugin
from terminatorlib.config import Config
from terminatorlib.factory import Factory
from terminatorlib.terminator import Terminator
from terminatorlib.util import dbg, err

AVAILABLE = ['MaximiseAware']


def render_marker(fmt, n):
    """Format a marker string with the hidden count, falling back safely."""
    try:
        return fmt.format(n=n)
    except (KeyError, IndexError, ValueError):
        return ' [%d hidden]' % n


def collect_terminals(widget, is_terminal):
    """Recursively collect terminal-like leaves under a widget subtree."""
    if is_terminal(widget):
        return [widget]
    found = []
    get_children = getattr(widget, 'get_children', None)
    if get_children is not None:
        for child in get_children():
            found.extend(collect_terminals(child, is_terminal))
    return found


def as_bool(value, default):
    """Coerce a config value (bool or string) to a boolean."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ('true', '1', 'yes', 'on')


def build_border_css(css_class, width, color):
    """Build the CSS rule for the subtle border indicator."""
    return '.%s { border: %dpx solid %s; }' % (css_class, int(width), color)


def find_notebook(window):
    """Return the window's Notebook child, or None if there are no tabs."""
    maker = Factory()
    children = window.get_children()
    if children and maker.isinstance(children[0], 'Notebook'):
        return children[0]
    return None


class BorderIndicator(object):
    """Draws a subtle border around the maximised terminal via per-terminal CSS."""

    CSS_CLASS = 'maximise-aware-border'

    def __init__(self, color, width):
        self.provider = Gtk.CssProvider()
        self._active = set()
        css = build_border_css(self.CSS_CLASS, width, color)
        try:
            self.provider.load_from_data(css.encode('utf-8'))
        except Exception as ex:
            err('MaximiseAware: bad border CSS %r: %s' % (css, ex))
            self.provider = None

    def show(self, terminal, count):
        if self.provider is None or terminal in self._active:
            return
        ctx = terminal.get_style_context()
        ctx.add_provider(self.provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        ctx.add_class(self.CSS_CLASS)
        self._active.add(terminal)

    def clear(self, terminal):
        if self.provider is None or terminal not in self._active:
            return
        ctx = terminal.get_style_context()
        ctx.remove_class(self.CSS_CLASS)
        ctx.remove_provider(self.provider)
        self._active.discard(terminal)


class BadgeIndicator(object):
    """Appends a badge to the maximised terminal's titlebar label."""

    def __init__(self, fmt):
        self.fmt = fmt
        self._markers = {}   # terminal -> marker string
        self._handlers = {}  # terminal -> title-change handler id

    def show(self, terminal, count):
        marker = render_marker(self.fmt, count)
        self._markers[terminal] = marker
        self._append(terminal)
        if terminal not in self._handlers:
            self._handlers[terminal] = terminal.connect_after(
                'title-change', self._on_title_change)

    def _on_title_change(self, terminal, *args):
        if terminal in self._markers:
            self._append(terminal)

    def _append(self, terminal):
        marker = self._markers.get(terminal)
        if not marker:
            return
        label = terminal.titlebar.label
        text = label.get_text()
        if not text.endswith(marker):
            label.set_text(text + marker)

    def clear(self, terminal):
        marker = self._markers.pop(terminal, None)
        handler = self._handlers.pop(terminal, None)
        if handler is not None:
            terminal.disconnect(handler)
        if marker:
            label = terminal.titlebar.label
            text = label.get_text()
            if text.endswith(marker):
                label.set_text(text[:-len(marker)])


class TitleIndicator(object):
    """Appends a marker to the window title (always) and tab title (if tabs)."""

    def __init__(self, fmt):
        self.fmt = fmt
        self._markers = {}        # terminal -> marker string
        self._orig_window = {}    # window -> original title
        self._orig_tab = {}       # TabLabel -> original label text
        self._handlers = {}       # terminal -> title-change handler id

    def show(self, terminal, count):
        marker = render_marker(self.fmt, count)
        self._markers[terminal] = marker
        window = terminal.get_toplevel()

        if window not in self._orig_window:
            self._orig_window[window] = window.get_title() or ''
        window.set_title(self._orig_window[window] + marker)
        if terminal not in self._handlers:
            self._handlers[terminal] = terminal.connect_after(
                'title-change', self._on_title_change)

        notebook = find_notebook(window)
        if notebook is not None:
            tabnum = notebook.page_num_descendant(terminal)
            if tabnum != -1:
                page = notebook.get_nth_page(tabnum)
                tablabel = notebook.get_tab_label(page)
                if tablabel is not None and tablabel not in self._orig_tab:
                    self._orig_tab[tablabel] = tablabel.get_label()
                    tablabel.set_label(self._orig_tab[tablabel] + marker)

    def _on_title_change(self, terminal, *args):
        marker = self._markers.get(terminal)
        if marker is None:
            return
        window = terminal.get_toplevel()
        base = window.get_title() or ''
        if not base.endswith(marker):
            self._orig_window[window] = base
            window.set_title(base + marker)

    def clear(self, terminal):
        marker = self._markers.pop(terminal, None)
        handler = self._handlers.pop(terminal, None)
        if handler is not None:
            try:
                terminal.disconnect(handler)
            except Exception:
                pass
        window = terminal.get_toplevel()
        orig = self._orig_window.pop(window, None)
        if orig is not None:
            window.set_title(orig)

        notebook = find_notebook(window)
        if notebook is not None and marker:
            tabnum = notebook.page_num_descendant(terminal)
            if tabnum != -1:
                page = notebook.get_nth_page(tabnum)
                tablabel = notebook.get_tab_label(page)
                if tablabel is not None and tablabel in self._orig_tab:
                    tablabel.set_label(self._orig_tab.pop(tablabel))
