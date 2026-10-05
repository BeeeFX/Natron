# Written by hand for the layer's tests, in the shape of an artist's ~/.nuke/menu.py. It's only parsed, never run.
import nuke

import mytools

toolbar = nuke.menu("Nodes")
toolbar.addCommand("Filter/Blur", 'nuke.createNode("Blur")', "ctrl+b")
nuke.menu("Nodes").addCommand("Merge/Merge", "nuke.createNode('Merge2')", "M")
toolbar.addCommand("Channel/Copy", lambda: nuke.createNode("Copy"), shortcut="#c")
nuke.menu("Nuke").addCommand("Edit/My tool", "mytools.run()", "ctrl+shift+e")
nuke.menu("Nodes").findItem("Keyer/Keylight").setShortcut("^+k")
toolbar.addCommand("Other/Dot", 'nuke.createNode("Dot")', "shift+d")
toolbar.addCommand("Filter/Fancy defocus", 'nuke.createNode("ZDefocus2")', "z")
toolbar.addCommand("Filter/Blur again", 'nuke.createNode("Blur")', "ctrl+b")
toolbar.addCommand("Draw/No key", 'nuke.createNode("Roto")')
