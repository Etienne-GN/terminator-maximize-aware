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


def rgba_to_hex(r, g, b):
    """Convert RGB floats in [0,1] to a '#rrggbb' string (clamped)."""
    def channel(value):
        clamped = max(0.0, min(1.0, value))
        return '%02x' % int(round(clamped * 255))
    return '#' + channel(r) + channel(g) + channel(b)


def hex_to_rgb(hexstr, default_rgb):
    """Parse '#rrggbb' (with/without '#', any case) to RGB floats in [0,1].

    Return default_rgb on any malformed input."""
    text = (hexstr or '').strip().lstrip('#')
    if len(text) != 6:
        return default_rgb
    try:
        r = int(text[0:2], 16) / 255.0
        g = int(text[2:4], 16) / 255.0
        b = int(text[4:6], 16) / 255.0
    except ValueError:
        return default_rgb
    return (r, g, b)


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
        # A manually renamed titlebar (EditableLabel._custom) ignores set_text,
        # so the badge is skipped there; the title and border cues still show.
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

        notebook = find_notebook(window)
        if notebook is not None:
            tabnum = notebook.page_num_descendant(terminal)
            if tabnum != -1:
                page = notebook.get_nth_page(tabnum)
                tablabel = notebook.get_tab_label(page)
                if tablabel is not None:
                    base_tab = tablabel.get_label()
                    if not base_tab.endswith(marker):
                        self._orig_tab[tablabel] = base_tab
                        tablabel.set_label(base_tab + marker)

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


class MaximiseAware(plugin.Plugin):
    """Coordinator: reads config, builds enabled indicators, and drives them
    from maximise/unmaximise events."""

    capabilities = ['maximise_aware']

    DEFAULTS = {
        'enable_badge': True,
        'enable_title': True,
        'enable_border': True,
        'badge_format': '[⊞ {n}]',
        'title_format': '   ◆ ⊞ {n} HIDDEN',
        'border_color': '#5294e2',
        'border_width': 1,
    }

    def __init__(self):
        plugin.Plugin.__init__(self)
        self.terminator = Terminator()
        self.maker = Factory()
        self.indicators = self._build_indicators()
        self._handlers = {}  # terminal -> [handler ids]
        self._orig_register = None
        self._orig_deregister = None
        self._install()

    def _get(self, key):
        config = Config()
        return config.plugin_get(self.__class__.__name__, key, self.DEFAULTS[key])

    def _build_indicators(self):
        indicators = []
        if as_bool(self._get('enable_badge'), self.DEFAULTS['enable_badge']):
            indicators.append(BadgeIndicator(str(self._get('badge_format'))))
        if as_bool(self._get('enable_title'), self.DEFAULTS['enable_title']):
            indicators.append(TitleIndicator(str(self._get('title_format'))))
        if as_bool(self._get('enable_border'), self.DEFAULTS['enable_border']):
            try:
                width = int(self._get('border_width'))
            except (TypeError, ValueError):
                width = self.DEFAULTS['border_width']
            indicators.append(BorderIndicator(str(self._get('border_color')), width))
        return indicators

    def count_hidden(self, window, terminal):
        """Count hidden sibling terminals in the maximised terminal's tab."""
        zoom_data = getattr(window, 'zoom_data', None)
        if not zoom_data:
            return 0
        subtree = zoom_data.get('old_child')
        if subtree is None:
            return 0
        if 'notebook_tabnum' in zoom_data and self.maker.isinstance(subtree, 'Notebook'):
            page = subtree.get_nth_page(zoom_data['notebook_tabnum'])
            if page is not None:
                subtree = page
        is_term = lambda w: self.maker.isinstance(w, 'Terminal')
        return len(collect_terminals(subtree, is_term))

    def _install(self):
        if getattr(self.terminator, '_maximise_aware_installed', False):
            return
        for terminal in list(self.terminator.terminals):
            self._connect_terminal(terminal)
        # Wrap registry methods so future terminals are tracked too.
        self._orig_register = self.terminator.register_terminal
        self._orig_deregister = self.terminator.deregister_terminal

        def register(terminal, _orig=self._orig_register):
            _orig(terminal)
            self._connect_terminal(terminal)

        def deregister(terminal, _orig=self._orig_deregister):
            self._disconnect_terminal(terminal)
            _orig(terminal)

        self.terminator.register_terminal = register
        self.terminator.deregister_terminal = deregister
        self.terminator._maximise_aware_installed = True

    def _connect_terminal(self, terminal):
        if terminal in self._handlers:
            return
        ids = [
            terminal.connect_after('maximise', self._on_maximise),
            terminal.connect_after('zoom', self._on_maximise),
            terminal.connect_after('unzoom', self._on_unmaximise),
        ]
        self._handlers[terminal] = ids

    def _disconnect_terminal(self, terminal):
        self._clear_all(terminal)
        ids = self._handlers.pop(terminal, [])
        for hid in ids:
            try:
                terminal.disconnect(hid)
            except Exception:
                pass

    def _on_maximise(self, terminal, *args):
        window = terminal.get_toplevel()
        count = self.count_hidden(window, terminal)
        if count <= 0:
            return
        for indicator in self.indicators:
            try:
                indicator.show(terminal, count)
            except Exception as ex:
                err('MaximiseAware: indicator.show failed: %s' % ex)

    def _on_unmaximise(self, terminal, *args):
        self._clear_all(terminal)

    def _clear_all(self, terminal):
        for indicator in self.indicators:
            try:
                indicator.clear(terminal)
            except Exception as ex:
                err('MaximiseAware: indicator.clear failed: %s' % ex)

    def unload(self):
        if self._orig_register is not None:
            self.terminator.register_terminal = self._orig_register
            self._orig_register = None
        if self._orig_deregister is not None:
            self.terminator.deregister_terminal = self._orig_deregister
            self._orig_deregister = None
        for terminal in list(self._handlers.keys()):
            self._disconnect_terminal(terminal)
        self.terminator._maximise_aware_installed = False
