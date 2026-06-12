# --------------------------------------
# HyprRings - Main Entry Point
# Author: Lukas Grumlik (Rakosn1cek)
# Version: 0.1.0
# --------------------------------------

import sys
import os
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
from gi.repository import Gtk
from interface import WorkspaceDashboard

VERSION = "0.1.0"

if __name__ == "__main__":
    win = WorkspaceDashboard()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()
