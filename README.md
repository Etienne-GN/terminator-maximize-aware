# Terminator MaximiseAware

Passive cues that other terminals are hidden while a terminal is maximised:

- a titlebar badge (`[⊞ N]`),
- a window-title and tab-title suffix (` ⊞×N`),
- a subtle 1px border around the maximised terminal.

All three count only the hidden siblings in the **current tab**, and clear on
unmaximise.

## Install

    cp maximise_aware.py ~/.config/terminator/plugins/

Then enable **MaximiseAware** in Terminator: Preferences -> Plugins.

## Configuration

Optional, in `~/.config/terminator/config` under `[plugins][[MaximiseAware]]`:

    [plugins]
      [[MaximiseAware]]
        enable_badge = True
        enable_title = True
        enable_border = True
        badge_format = "[⊞ {n}]"
        title_format = "   ◆ ⊞ {n} HIDDEN"
        border_color = "#5294e2"
        border_width = 1

`{n}` is the hidden-terminal count. Each cue can be toggled independently.

## Compatibility

Verified against Terminator 2.1.5.
