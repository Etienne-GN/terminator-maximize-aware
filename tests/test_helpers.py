import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from maximise_aware import (render_marker, collect_terminals, as_bool,
                            build_border_css, rgba_to_hex, hex_to_rgb)


class FakeWidget:
    def __init__(self, children=None, terminal=False):
        self._children = children or []
        self.terminal = terminal

    def get_children(self):
        return self._children


def is_term(widget):
    return getattr(widget, "terminal", False)


def test_render_marker_substitutes_n():
    assert render_marker("[⊞ {n}]", 3) == "[⊞ 3]"
    assert render_marker(" ⊞×{n}", 2) == " ⊞×2"


def test_render_marker_bad_format_falls_back():
    assert render_marker("broken {x}", 4) == " [4 hidden]"
    assert render_marker("{", 1) == " [1 hidden]"


def test_collect_terminals_counts_leaves_only():
    tree = FakeWidget(children=[
        FakeWidget(terminal=True),
        FakeWidget(children=[FakeWidget(terminal=True), FakeWidget(terminal=True)]),
    ])
    assert len(collect_terminals(tree, is_term)) == 3


def test_collect_terminals_empty_subtree():
    assert collect_terminals(FakeWidget(), is_term) == []


def test_collect_terminals_widget_is_terminal():
    assert len(collect_terminals(FakeWidget(terminal=True), is_term)) == 1


def test_as_bool():
    assert as_bool(True, False) is True
    assert as_bool(False, True) is False
    assert as_bool(None, True) is True
    assert as_bool("False", True) is False
    assert as_bool("true", False) is True
    assert as_bool("1", False) is True
    assert as_bool("0", True) is False


def test_build_border_css():
    css = build_border_css("maximise-aware-border", 1, "#5294e2")
    assert css == ".maximise-aware-border { border: 1px solid #5294e2; }"


def test_rgba_to_hex_basic():
    assert rgba_to_hex(0.0, 0.0, 0.0) == "#000000"
    assert rgba_to_hex(1.0, 1.0, 1.0) == "#ffffff"
    assert rgba_to_hex(82 / 255, 148 / 255, 226 / 255) == "#5294e2"


def test_rgba_to_hex_clamps_out_of_range():
    assert rgba_to_hex(-0.5, 1.5, 0.5) == "#00ff80"


def test_hex_to_rgb_valid():
    r, g, b = hex_to_rgb("#5294e2", (0.0, 0.0, 0.0))
    assert (round(r, 3), round(g, 3), round(b, 3)) == (0.322, 0.58, 0.886)


def test_hex_to_rgb_no_hash_and_uppercase():
    assert hex_to_rgb("5294E2", (0.0, 0.0, 0.0)) == hex_to_rgb("#5294e2", (0.0, 0.0, 0.0))


def test_hex_to_rgb_invalid_returns_default():
    default = (0.1, 0.2, 0.3)
    assert hex_to_rgb("nope", default) == default
    assert hex_to_rgb("#12", default) == default
    assert hex_to_rgb("", default) == default
    assert hex_to_rgb(None, default) == default


def test_color_round_trip():
    for h in ("#5294e2", "#000000", "#ffffff", "#ff5555"):
        assert rgba_to_hex(*hex_to_rgb(h, (0.0, 0.0, 0.0))) == h
