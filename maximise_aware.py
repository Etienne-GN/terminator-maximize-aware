"""Terminator plugin: show passive cues when a terminal is maximised while
sibling terminals in the current tab are hidden."""

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
