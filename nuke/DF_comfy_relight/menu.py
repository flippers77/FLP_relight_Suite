# Copyright (c) Electric Theatre Collective. Internal use only. See LICENSE.
"""DF_comfy_relight - toolbar entry. Change SHORTCUT if it clashes."""
import nuke

SHORTCUT = 'ctrl+alt+r'

nuke.toolbar("Nodes").addCommand("ETC/DF_comfy_relight",
                                 "nuke.createNode('DF_comfy_relight')",
                                 SHORTCUT,
                                 icon="df_icon.png")
