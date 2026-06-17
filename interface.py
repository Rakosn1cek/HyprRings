# ---------------------------------------
# HyprRings - Interface Module
# Author: Lukas Grumlik (Rakosn1cek)
# Version: 0.2.0
# ---------------------------------------

import sys
import math
import subprocess
import os
import datetime
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Gdk, GLib, GtkLayerShell, Pango, PangoCairo
import cairo
import config
import animation
import telemetry

VERSION = "0.2.0"

class WorkspaceDashboard(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "hyprrings")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.BOTTOM)
        GtkLayerShell.set_exclusive_zone(self, 0)
        
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.ON_DEMAND)
        
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.LEFT, True)
        GtkLayerShell.set_anchor(self, GtkLayerShell.Edge.RIGHT, True)

        self.set_title("HyprRings")
        self.set_app_paintable(True)
        
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)
            
        self.center_radius = 65
        self.box_width = 190
        self.box_height = 95
        self.sp_width = 130
        self.sp_height = 60
        self.act_width = 75
        self.act_height = 32
        
        self.inner_orbit_radius = 150
        self.outer_orbit_radius = 330
        self.special_orbit_radius = 470
        
        self.hud_width = 250
        self.hud_base_height = 195  
        
        self.tilt_x = 0.0          
        self.tilt_y = 0.0          
        self.rotation_offset = 0.0  
        self.focal_length = 700.0   
        
        self.power_profile = "unknown"
        self.volume_level = 0
        self.brightness_level = 0
        self.tracker_status_str = "Inactive"
        self.battery_detailed_info = "Checking battery..."
        
        self.sunrise_str = "05:14"
        self.sunset_str = "21:23"
        self.lunar_phase_str = "Waning Gibbous"
        self.lunar_illum_pct = 74
        self.lunar_icon = "󰽚"
        self.week_num_str = "24"
        
        self.groups_manifest = ["inner_core", "workspaces", "specials", "power_menu", "battery_profile", "volume_hud", "brightness_hud", "custom_tasks"]
        self.active_group_idx = 0  
        self.internal_option_idx = 0 
        self.selected_target = None

        self.home = os.path.expanduser("~")
        self.custom_tools = [
            ("", "rtm", f"kitty --class rtm -e python3 {self.home}/arch-projects/RTM/rtm.py"),
            ("󱀇", "budget", f"kitty --class budget-buddy -e python3 {self.home}/arch-projects/Budget-Buddy/budget-buddy.py"),
            ("", "mirec", f"kitty --class Mirec -e {self.home}/arch-projects/MIREC/mirec"),
            (" ", "wifi", f"kitty --class floating_wifi -e {self.home}/custom-scripts/wifi/wwifi"),
            ("", "bt", f"kitty --class bt-menu -e {self.home}/custom-scripts/bluetooth/bt"),
            ("󱆟", "keys", f"kitty --class keybinds -e {self.home}/custom-scripts/Shell-Widgets/keybinds.sh"),
            ("󰬈", "alias", f"kitty --class show-aliases -e {self.home}/custom-scripts/Show-Aliases/show-aliases.sh"),
            ("󱫉", "clip", f"python3 {self.home}/custom-scripts/Python-Widgets/clipbox-widget2.py")
        ] 
        
        self.power_actions = [
            ("󰐥", "shutdown", "shutdown now"),
            ("󰑐", "reboot", "reboot"),
            ("󰤄", "suspend", "systemctl suspend"),
            ("󰈆", "logout", "hyprshutdown --vt 2"),
            ("󰖔", "nightlight", f"bash {self.home}/.local/bin/nightlight")
        ]
        
        self.drawer = animation.DrawerAnimator(280, 1500)
        self.colors = config.load_system_theme()
        
        self.workspaces_data = {}
        self.special_workspaces = {}
        self.active_workspace_id = 1
        self.total_windows_count = 0
        self.cpu_usage = 0
        self.ram_usage = 0
        self.core_temp = 0
        self.battery_percent = 100
        self.uptime_str = "0h 0m"
        self.last_cpu_idle = 0
        self.last_cpu_total = 0
        self.zoom_factor = 1.0
        
        self.set_events(Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("draw", self.on_draw)
        self.connect("motion-notify-event", self.on_mouse_move)
        self.connect("key-press-event", self.on_key_press)
        self.connect("button-press-event", self.on_button_press)

        self.tracker_status_str = "Inactive"
        self.battery_detailed_info = "Checking battery..."
        self.core_temp = 0
        self.wifi_connected = False
        self.bt_connected = False
        
        self.refresh_telemetry()
        self.synchronize_navigation_targets()
        
        GLib.timeout_add_seconds(1, self.refresh_telemetry)

    def render_text(self, cr, x, y, width, height, text, font_string, color, alignment="left"):
        cr.save()
        cr.set_source_rgba(*color)
        layout = self.create_pango_layout()
        layout.set_text(text, -1)
        desc = Pango.FontDescription.from_string(font_string)
        layout.set_font_description(desc)
        if width > 0:
            layout.set_width(int(width * Pango.SCALE))
            if alignment == "center":
                layout.set_alignment(Pango.Alignment.CENTER)
            elif alignment == "right":
                layout.set_alignment(Pango.Alignment.RIGHT)
        cr.move_to(x, y)
        PangoCairo.show_layout(cr, layout)
        cr.restore()

    def refresh_telemetry(self):
        self.colors = config.load_system_theme()
                
        self.active_workspace_id, self.total_windows_count, self.workspaces_data, self.special_workspaces = telemetry.fetch_system_state()
        self.cpu_usage, self.last_cpu_idle, self.last_cpu_total, self.ram_usage, self.battery_percent, \
        self.battery_detailed_info, self.uptime_str, self.power_profile, self.volume_level, \
        self.brightness_level, self.tracker_status_str, self.core_temp, self.wifi_connected, \
        self.bt_connected = telemetry.fetch_hardware_metrics(self.last_cpu_idle, self.last_cpu_total)
        
        if datetime.datetime.now().second == 0 and datetime.datetime.now().minute == 0:
            self.week_num_str, self.sunrise_str, self.sunset_str, self.lunar_phase_str, self.lunar_illum_pct, self.lunar_icon = telemetry.calculate_astronomy_data()
            
        GLib.timeout_add(500, self.trigger_delayed_mapping)
        return True

    def trigger_delayed_mapping(self):
        self.synchronize_navigation_targets()
        self.queue_draw()
        return False

    def get_options_for_group(self, group_name):
        if group_name == "inner_core":
            return [
                "cmd:togglefloating", "cmd:fullscreen 0", "cmd:pin", "cmd:togglesplit",
                "cmd:layout_master", "cmd:layout_dwindle", "cmd:layout_scrolling", "cmd:layout_monocle"
            ]
        elif group_name == "workspaces":
            return [str(ws_id) for ws_id in sorted(list(self.workspaces_data.keys()))]
        elif group_name == "battery_profile":
            return ["profile:powersave", "profile:performance"]
        elif group_name == "power_menu":
            return [f"power:{act[1]}" for act in self.power_actions]
        elif group_name == "volume_hud":
            return ["hw:vol:up", "hw:vol:down"]
        elif group_name == "brightness_hud":
            return ["hw:bright:up", "hw:bright:down"]
        elif group_name == "custom_tasks":
            return [f"task:{t[1]}" for t in self.custom_tools]
        elif group_name == "specials":
            return [f"sp:{ws_name}" for ws_name in sorted(list(self.special_workspaces.keys()))]
        return []

    def synchronize_navigation_targets(self):
        if self.active_group_idx < 0 or self.active_group_idx >= len(self.groups_manifest):
            self.selected_target = None
            return
            
        current_group = self.groups_manifest[self.active_group_idx]
        group_options = self.get_options_for_group(current_group)
        
        if not group_options or (len(group_options) == 1 and group_options[0] == "sp:none"):
            self.selected_target = None
            return
            
        if self.internal_option_idx >= len(group_options):
            self.internal_option_idx = 0
        elif self.internal_option_idx < 0:
            self.internal_option_idx = len(group_options) - 1
            
        self.selected_target = group_options[self.internal_option_idx]

    def send_hud_notification(self, title, message, icon):
        try:
            subprocess.run([
                "notify-send", 
                "-a", "HyprRings", 
                "-u", "low", 
                "-h", "string:x-canonical-private-synchronous:hyprrings-hardware", 
                f"{icon}  {title}", 
                message
            ])
        except Exception:
            pass

    def project_hybrid_point(self, cx, cy, radius, base_angle):
        angle = base_angle + self.rotation_offset
        x3d = radius * math.cos(angle)
        y3d = radius * math.sin(angle)
        z3d = 0.0
        
        rot_y = y3d * math.cos(self.tilt_x) - z3d * math.sin(self.tilt_x)
        rot_z = y3d * math.sin(self.tilt_x) + z3d * math.cos(self.tilt_x)
        rot_x = x3d * math.cos(self.tilt_y) - rot_z * math.sin(self.tilt_y)
        final_z = x3d * math.sin(self.tilt_y) + rot_z * math.cos(self.tilt_y)
        
        zoom_factor = self.focal_length / (self.focal_length + final_z)
        return cx + rot_x * zoom_factor, cy + rot_y * zoom_factor, zoom_factor

    def draw_rounded_rectangle(self, cr, x, y, width, height, radius):
        cr.new_sub_path()
        cr.arc(x + width - radius, y + radius, radius, -math.pi/2, 0)
        cr.arc(x + width - radius, y + height - radius, radius, 0, math.pi/2)
        cr.arc(x + radius, y + height - radius, radius, math.pi/2, math.pi)
        cr.arc(x + radius, y + radius, radius, math.pi, 3*math.pi/2)
        cr.close_path()

    def draw_hud_bar(self, cr, x, y, width, label, percent, accent):
        self.render_text(cr, x, y + 2, 120, 14, f"{label}: {percent}%", "JetBrainsMono NF 8", self.colors["text"])
        
        cr.set_source_rgba(self.colors["text"][0], self.colors["text"][1], self.colors["text"][2], 0.12)
        self.draw_rounded_rectangle(cr, x, y + 20, width, 5, 2)
        cr.fill()
        
        if percent > 0:
            fill = int((min(percent, 100) / 100.0) * width)
            cr.set_source_rgba(*accent)
            self.draw_rounded_rectangle(cr, x, y + 20, fill, 5, 2)
            cr.fill()

    def draw_curved_orbit_panel(self, cr, cx, cy, inner_radius, outer_radius, start_angle, end_angle, border_color, container_focused=False):
        cr.save()
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_antialias(cairo.ANTIALIAS_BEST)
        
        cr.new_sub_path()
        cr.arc(cx, cy, outer_radius, start_angle, end_angle)
        cr.line_to(cx + inner_radius * math.cos(end_angle), cy + inner_radius * math.sin(end_angle))
        cr.arc_negative(cx, cy, inner_radius, end_angle, start_angle)
        cr.line_to(cx + outer_radius * math.cos(start_angle), cy + outer_radius * math.sin(start_angle))
        cr.close_path()
        
        bg_filled = list(self.colors["bg"])
        bg_filled[3] = 0.92 if bg_filled[3] < 0.6 else 0.82
        cr.set_source_rgba(*bg_filled)
        cr.fill()
        
        # Border stroke operation completely stripped out to give the half moons a borderless profile
        cr.restore()

    def draw_corner_bounding_box(self, cr, x, y, width, height, border_color, container_focused=False):
        if container_focused:
            cr.set_source_rgba(166/255.0, 227/255.0, 161/255.0, 1.0)
            cr.set_line_width(1.8)
        else:
            cr.set_source_rgba(*border_color)
            cr.set_line_width(1.0)
            
        self.draw_rounded_rectangle(cr, x, y, width, height, 8)
        cr.stroke_preserve()
        
        bg_filled = list(self.colors["bg"])
        bg_filled[3] = 0.2 if bg_filled[3] < 0.6 else 0.82
        cr.set_source_rgba(*bg_filled)
        cr.fill()

    def draw_helper_drawer_panel(self, cr):
        x = int(self.drawer.drawer_current_x)
        if x <= -self.drawer.drawer_width:
            return  
            
        h = self.get_allocated_height()
        cr.set_source_rgba(self.colors["accent"][0], self.colors["accent"][1], self.colors["accent"][2], 1.0)
        cr.set_line_width(1.0)
        cr.rectangle(x, 0, self.drawer.drawer_width, h)
        cr.stroke_preserve()
        
        drawer_bg = list(self.colors["bg"])
        drawer_bg[3] = 0.96
        cr.set_source_rgba(*drawer_bg)
        cr.fill()
        
        p_x = x + 20
        self.render_text(cr, p_x, 20, self.drawer.drawer_width - 40, 25, "󰌌  SYSTEM MANIFEST", "JetBrainsMono NF Bold 11", self.colors["accent"])
        
        cr.set_source_rgba(self.colors["hint"][0], self.colors["hint"][1], self.colors["hint"][2], 0.8)
        cr.set_line_width(0.8)
        cr.move_to(p_x, 48)
        cr.line_to(x + self.drawer.drawer_width - 20, 48)
        cr.stroke()
        
        y_start = 75
        help_content = [
            ("GLOBAL ENGINE NAVIGATION", True),
            ("Tab Key", "Focus Next Module Box"),
            ("Shift + Tab", "Focus Prev Module Box"),
            ("Return / Enter", "Confirm Selected Option"),
            ("Escape Key", "Close Dashboard Realm"),
            ("", False),
            ("INTERNAL MODULE CONTROLS", True),
            ("Right / Down Arrow", "Cycle Forward Option"),
            ("Left / Up Arrow", "Cycle Backward Option"),
            ("", False),
            ("3D PERSPECTIVE CONTROLS", True),
            ("Mouse Move L/R", "Rotate Planetary Ring Map"),
            ("Shift + Mouse Move", "Tilt Perspective Map Axis"),
            ("", False),
            ("DRAWER MAP OVERLAYS", True),
            ("H Key / ?", "Toggle This Information")
        ]
        
        for row in help_content:
            if len(row) == 2 and row[1] is True:
                self.render_text(cr, p_x, y_start, self.drawer.drawer_width - 40, 20, row[0], "JetBrainsMono NF Bold 8", self.colors["text"])
                y_start += 22
            elif len(row) == 2 and row[1] is False:
                y_start += 12
            elif len(row) == 2:
                self.render_text(cr, p_x, y_start, 105, 20, row[0], "JetBrainsMono NF Bold 7", self.colors["accent"])
                self.render_text(cr, p_x + 105, y_start, self.drawer.drawer_width - 125, 20, row[1], "SansSerif 8", self.colors["hint"])
                y_start += 24

    def toggle_helper_drawer(self):
        import time
        self.drawer.drawer_open = not self.drawer.drawer_open
        self.drawer.last_frame_time = time.perf_counter()
        
        if not getattr(self, "anim_running", False):
            self.anim_running = True
            GLib.timeout_add(16, self.animate_drawer)

    def animate_drawer(self):
        self.drawer.process()
        self.queue_draw()
        
        target_x = 0.0 if self.drawer.drawer_open else float(-self.drawer.drawer_width)
        if self.drawer.drawer_current_x == target_x:
            self.anim_running = False
            return False
        return True

    def on_draw(self, widget, cr):
        cx = self.get_allocated_width() // 2
        cy = self.get_allocated_height() // 2
        
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.0)
        cr.set_operator(cairo.Operator.SOURCE)
        cr.paint()
        cr.set_operator(cairo.Operator.OVER)
        
        nodes = sorted(list(self.workspaces_data.keys()))
        total_nodes = len(nodes)
        sp_nodes = sorted(list(self.special_workspaces.keys()))
        total_sp_nodes = len(sp_nodes)
        focused_group = self.groups_manifest[self.active_group_idx]

        step_segments = 120
        cr.set_fill_rule(cairo.FillRule.WINDING)
        
        if total_sp_nodes > 0:
            if focused_group == "specials":
                cr.set_source_rgba(166/255.0, 227/255.0, 161/255.0, 0.78)
                cr.set_line_width(1.5)
            else:
                cr.set_source_rgba(self.colors["accent"][0], self.colors["accent"][1], self.colors["accent"][2], 0.35)
                cr.set_line_width(1.2)
            for i in range(step_segments + 1):
                ang = (2 * math.pi / step_segments) * i
                px, py, _ = self.project_hybrid_point(cx, cy, self.special_orbit_radius, ang)
                if i == 0: cr.move_to(px, py)
                else: cr.line_to(px, py)
            cr.stroke()

        if focused_group == "workspaces":
            cr.set_source_rgba(166/255.0, 227/255.0, 161/255.0, 0.86)
            cr.set_line_width(2.0)
        else:
            cr.set_source_rgba(self.colors["accent"][0], self.colors["accent"][1], self.colors["accent"][2], 0.5)
            cr.set_line_width(1.5)
        for i in range(step_segments + 1):
            ang = (2 * math.pi / step_segments) * i
            px, py, _ = self.project_hybrid_point(cx, cy, self.outer_orbit_radius, ang)
            if i == 0: cr.move_to(px, py)
            else: cr.line_to(px, py)
        cr.stroke()

        if focused_group == "inner_core":
            cr.set_source_rgba(166/255.0, 227/255.0, 161/255.0, 0.78)
            cr.set_line_width(1.5)
        else:
            cr.set_source_rgba(self.colors["accent"][0], self.colors["accent"][1], self.colors["accent"][2], 0.39)
            cr.set_line_width(1.2)
        for i in range(step_segments + 1):
            ang = (2 * math.pi / step_segments) * i
            px, py, _ = self.project_hybrid_point(cx, cy, self.inner_orbit_radius, ang)
            if i == 0: cr.move_to(px, py)
            else: cr.line_to(px, py)
        cr.stroke()

        render_queue = []
        actions = [
            {"name": "󰊓 FLOAT",  "cmd": "togglefloating",   "angle": -math.pi / 2},
            {"name": "󰊔 FULL",   "cmd": "fullscreen 0",     "angle": 0},
            {"name": "󰐃 PIN",    "cmd": "pin",              "angle": math.pi / 2},
            {"name": "󰕰 SPLIT",  "cmd": "togglesplit",      "angle": math.pi},
            {"name": "󱂬 MASTER", "cmd": "layout_master",    "angle": -math.pi / 4},
            {"name": "󱂳 DWINDLE", "cmd": "layout_dwindle",   "angle": math.pi / 4},
            {"name": "󰖯 SCROLL", "cmd": "layout_scrolling", "angle": 3 * math.pi / 4},
            {"name": "󰍉 MONOCL", "cmd": "layout_monocle",   "angle": -3 * math.pi / 4}
        ]
        for act in actions:
            ax, ay, z_scale = self.project_hybrid_point(cx, cy, self.inner_orbit_radius, act["angle"])
            render_queue.append((z_scale, "cmd", act, ax, ay, 0.0))

        if total_nodes > 0:
            for index, ws_id in enumerate(nodes):
                ang = (2 * math.pi / total_nodes) * index - (math.pi / 2)
                nx, ny, z_scale = self.project_hybrid_point(cx, cy, self.outer_orbit_radius, ang)
                render_queue.append((z_scale, "ws", ws_id, nx, ny, ang))

        if total_sp_nodes > 0:
            for index, ws_name in enumerate(sp_nodes):
                angle = (2 * math.pi / total_sp_nodes) * index - (math.pi / 4)
                sx, sy, z_scale = self.project_hybrid_point(cx, cy, self.special_orbit_radius, angle)
                render_queue.append((z_scale, "sp", ws_name, sx, sy, 0.0))

        render_queue.sort(key=lambda t: t[0])

        for item in render_queue:
            z_scale = item[0]
            item_type = item[1]
            
            if item_type == "cmd":
                act = item[2]
                ax, ay = item[3], item[4]
                w, h = int(self.act_width * z_scale), int(self.act_height * z_scale)
                abx, aby = int(ax - w / 2), int(ay - h / 2)
                
                if self.selected_target == f"cmd:{act['cmd']}":
                    cr.set_source_rgba(166/255.0, 227/255.0, 161/255.0, 1.0)
                    cr.set_line_width(2.0)
                    self.draw_rounded_rectangle(cr, abx, aby, w, h, 6)
                    cr.stroke_preserve()
                    cr.set_source_rgba(166/255.0, 227/255.0, 161/255.0, 0.17)
                    cr.fill()
                else:
                    cr.set_source_rgba(self.colors["accent"][0], self.colors["accent"][1], self.colors["accent"][2], 0.39)
                    cr.set_line_width(1.0)
                    self.draw_rounded_rectangle(cr, abx, aby, w, h, 6)
                    cr.stroke_preserve()
                    cr.set_source_rgba(*self.colors["bg"])
                    cr.fill()
                    
                self.render_text(cr, abx, aby + h//2 - 6, w, h, act["name"], f"JetBrainsMono NF Bold {max(5, int(8 * z_scale))}", self.colors["text"], "center")
                
            elif item_type == "ws":
                ws_id = item[2]
                nx, ny, ang = item[3], item[4], item[5]
                w, h = int(self.box_width * z_scale), int(self.box_height * z_scale)
                bx, by = int(nx - w / 2), int(ny - h / 2)
                
                is_selected = self.selected_target == str(ws_id)
                is_active = ws_id == self.active_workspace_id
                
                if is_selected and self.zoom_factor > 1.0:
                    cr.save()
                    cr.translate(nx, ny)
                    cr.scale(self.zoom_factor, self.zoom_factor)
                    cr.translate(-nx, -ny)
                
                if is_selected:
                    cr.set_source_rgba(166/255.0, 227/255.0, 161/255.0, 1.0)
                    cr.set_line_width(3.0)
                elif is_active:
                    cr.set_source_rgba(245/255.0, 194/255.0, 231/255.0, 1.0)
                    cr.set_line_width(2.0)
                else:
                    cr.set_source_rgba(self.colors["accent"][0], self.colors["accent"][1], self.colors["accent"][2], 0.7)
                    cr.set_line_width(1.5)
                    
                self.draw_rounded_rectangle(cr, bx, by, w, h, 12)
                cr.stroke_preserve()
                cr.set_source_rgba(*self.colors["bg"])
                cr.fill()
                
                if is_active:
                    cr.set_source_rgba(245/255.0, 194/255.0, 231/255.0, 0.58)
                    cr.set_line_width(1.0)
                    iax, iay, _ = self.project_hybrid_point(cx, cy, self.inner_orbit_radius, ang)
                    cr.move_to(int(nx), int(ny))
                    cr.line_to(int(iax), int(iay))
                    cr.stroke()
                
                active_marker = " * " if is_active else ""
                self.render_text(cr, bx + int(14 * z_scale), by + int(10 * z_scale), w, 20, f"0{ws_id}{active_marker}", f"JetBrainsMono NF Bold {max(6, int(10 * z_scale))}", self.colors["text"])
                
                meta_tag = self.workspaces_data[ws_id]["monitor"]
                if self.workspaces_data[ws_id]["fullscreen"]:
                    meta_tag = f"[FS] {meta_tag}"
                self.render_text(cr, bx + w - int(94 * z_scale), by + int(10 * z_scale), int(80 * z_scale), 20, meta_tag[:10], f"JetBrainsMono NF Bold {max(6, int(10 * z_scale))}", self.colors["text"], "right")
                
                cr.set_source_rgba(self.colors["text"][0], self.colors["text"][1], self.colors["text"][2], 0.15)
                cr.set_line_width(1.0)
                cr.move_to(bx + int(12 * z_scale), by + int(38 * z_scale))
                cr.line_to(bx + w - int(12 * z_scale), by + int(38 * z_scale))
                cr.stroke()
                
                apps = []
                f_class = self.workspaces_data[ws_id]["focused_win_class"]
                f_title = self.workspaces_data[ws_id]["focused_win_title"]
                for app in self.workspaces_data[ws_id]["windows"]:
                    if app == f_class or app == f_title or (f_class in app and f_class != ""):
                        apps.append(f"[{app}]")
                    else:
                        apps.append(app)
                
                apps_string = ", ".join(apps) if apps else "empty spatial slot"
                self.render_text(cr, bx + int(14 * z_scale), by + int(44 * z_scale), w - int(28 * z_scale), 38, apps_string[:28], f"SansSerif {max(5, int(9 * z_scale))}", self.colors["hint"])
                
                if is_selected and self.zoom_factor > 1.0:
                    cr.restore()
                
            elif item_type == "sp":
                ws_name = item[2]
                sx, sy = item[3], item[4]
                sw, sh = int(self.sp_width * z_scale), int(self.sp_height * z_scale)
                sbx, sby = int(sx - sw / 2), int(sy - sh / 2)
                
                if self.selected_target == f"sp:{ws_name}":
                    cr.set_source_rgba(166/255.0, 227/255.0, 161/255.0, 1.0)
                else:
                    cr.set_source_rgba(self.colors["accent"][0], self.colors["accent"][1], self.colors["accent"][2], 0.47)
                cr.set_line_width(1.0)
                self.draw_rounded_rectangle(cr, sbx, sby, sw, sh, 8)
                cr.stroke_preserve()
                cr.set_source_rgba(*self.colors["bg"])
                cr.fill()
                
                self.render_text(cr, sbx + int(10 * z_scale), sby + int(8 * z_scale), sw, 15, f" {self.special_workspaces[ws_name]['clean_name']}", f"JetBrainsMono NF Bold {max(5, int(8 * z_scale))}", self.colors["text"])
                
                sp_apps = ", ".join(self.special_workspaces[ws_name]["windows"]) if self.special_workspaces[ws_name]["windows"] else "empty space"
                self.render_text(cr, sbx + int(10 * z_scale), sby + int(26 * z_scale), sw - int(20 * z_scale), 20, sp_apps[:18], f"SansSerif {max(5, int(8 * z_scale))}", self.colors["hint"])

        cr.set_source_rgba(self.colors["accent"][0], self.colors["accent"][1], self.colors["accent"][2], 0.15)
        cr.set_line_width(1.0)
        cr.arc(cx, cy, self.center_radius + 15, 0, 2*math.pi)
        cr.stroke()
        
        cr.set_source_rgba(*self.colors["bg"])
        cr.arc(cx, cy, self.center_radius, 0, 2*math.pi)
        cr.fill_preserve()
        cr.set_source_rgba(*self.colors["accent"])
        cr.set_line_width(2.0)
        cr.stroke()
        
        self.render_text(cr, cx - 50, cy - 14, 100, 20, "HYPR", "JetBrainsMono NF Bold 12", self.colors["text"], "center")
        self.render_text(cr, cx - 50, cy + 4, 100, 20, "RINGS", "SansSerif 12", self.colors["hint"], "center")

        hud_pen_color = list(self.colors["accent"])
        hud_pen_color[3] = 0.39
        
        # Draw Left Half Moon (Border line weight logic bypassed)
        self.draw_curved_orbit_panel(cr, cx, cy, 580, 840, 145 * math.pi / 180, 215 * math.pi / 180, hud_pen_color, False)
        
        # Position adjusted to center the text blocks inside the curved hull lane perfectly (cx - 825)
        tl_x, tl_y = cx - 825, cy - 170
        self.render_text(cr, tl_x + 14, tl_y + 10, 150, 15, "  SYSTEM STATUS", "JetBrainsMono NF Bold 9", self.colors["accent"])
        self.draw_hud_bar(cr, tl_x + 14, tl_y + 28, self.hud_width - 28, "CPU", self.cpu_usage, (166/255.0, 227/255.0, 161/255.0, 1.0))
        self.draw_hud_bar(cr, tl_x + 14, tl_y + 58, self.hud_width - 28, "RAM", self.ram_usage, (249/255.0, 226/255.0, 175/255.0, 1.0))
        self.draw_hud_bar(cr, tl_x + 14, tl_y + 88, self.hud_width - 28, "BAT", self.battery_percent, (137/255.0, 220/255.0, 235/255.0, 1.0))
        self.draw_hud_bar(cr, tl_x + 14, tl_y + 118, self.hud_width - 28, "TMP", self.core_temp, (250/255.0, 179/255.0, 135/255.0, 1.0))
        self.render_text(cr, tl_x + 14, tl_y + 168, self.hud_width - 28, 14, f"  {self.battery_detailed_info[:42]}", "JetBrainsMono NF 7", self.colors["hint"])

        bl_x = cx - 820
        bl_y = tl_y + self.hud_base_height + 10
            
        self.render_text(cr, bl_x + 14, bl_y + 10, 180, 15, "   BATTERY PROFILE", "JetBrainsMono NF Bold 9", self.colors["accent"])
        
        p_saver_x, p_perf_x = bl_x + 14, bl_x + self.hud_width - 114
        p_btn_y = bl_y + 35
        p_btn_w, p_btn_h = 100, 30
        
        for p_key, label, px in [("profile:powersave", " POWERSAVER", p_saver_x), ("profile:performance", " PERFORMANCE", p_perf_x)]:
            p_name = p_key.split(":")[1]
            if self.selected_target == p_key:
                cr.set_source_rgba(166/255.0, 227/255.0, 161/255.0, 1.0)
                cr.set_line_width(1.5)
                self.draw_rounded_rectangle(cr, px, p_btn_y, p_btn_w, p_btn_h, 5)
                cr.stroke_preserve()
                cr.set_source_rgba(166/255.0, 227/255.0, 161/255.0, 0.13)
                cr.fill()
            elif self.power_profile == p_name:
                cr.set_source_rgba(249/255.0, 226/255.0, 175/255.0, 1.0)
                cr.set_line_width(1.5)
                self.draw_rounded_rectangle(cr, px, p_btn_y, p_btn_w, p_btn_h, 5)
                cr.stroke_preserve()
                cr.set_source_rgba(249/255.0, 226/255.0, 175/255.0, 0.17)
                cr.fill()
            else:
                cr.set_source_rgba(*self.colors["accent"])
                cr.set_line_width(1.0)
                self.draw_rounded_rectangle(cr, px, p_btn_y, p_btn_w, p_btn_h, 5)
                cr.stroke_preserve()
                cr.set_source_rgba(*self.colors["bg"])
                cr.fill()
            self.render_text(cr, px + 14, p_btn_y + 8, p_btn_w, p_btn_h, label, "JetBrainsMono NF Bold 8", self.colors["text"])

        pwr_x = cx - 810
        pwr_y = bl_y + 75 + 10
            
        self.render_text(cr, pwr_x + 14, pwr_y + 10, self.hud_width - 28, 15, "   POWER MANAGEMENT", "JetBrainsMono NF Bold 9", self.colors["accent"])

        p_btn_w, p_btn_h, p_pad = 40, 28, 6
        p_start_x, p_start_y = pwr_x + 13, pwr_y + 32

        for i, act in enumerate(self.power_actions):
            icon, name, _ = act
            bx = p_start_x + i * (p_btn_w + p_pad)
            p_key = f"power:{name}"
            
            if self.selected_target == p_key:
                cr.set_source_rgba(166/255.0, 227/255.0, 161/255.0, 1.0)
                cr.set_line_width(1.5)
                self.draw_rounded_rectangle(cr, bx, p_start_y, p_btn_w, p_btn_h, 4)
                cr.stroke_preserve()
                cr.set_source_rgba(166/255.0, 227/255.0, 161/255.0, 0.13)
                cr.fill()
            else:
                cr.set_source_rgba(*self.colors["accent"])
                cr.set_line_width(1.0)
                self.draw_rounded_rectangle(cr, bx, p_start_y, p_btn_w, p_btn_h, 4)
                cr.stroke_preserve()
                cr.set_source_rgba(*self.colors["bg"])
                cr.fill()
                
            self.render_text(cr, bx, p_start_y + 2, p_btn_w, p_btn_h, icon, "JetBrainsMono NF Bold 12", self.colors["text"], "center")

        nav_bl_y = pwr_y + 75
        self.render_text(cr, cx - 785, nav_bl_y + 15, self.hud_width - 28, 18, "   NAVIGATION MAP", "JetBrainsMono NF Bold 9", self.colors["accent"])
        self.render_text(cr, cx - 785, nav_bl_y + 35, self.hud_width - 28, 14, "  Press [ H ] or [ ? ] key to slide out manual", "SansSerif 8", self.colors["hint"])

        # Draw Right Half Moon (Border line weight logic bypassed)
        self.draw_curved_orbit_panel(cr, cx, cy, 580, 840, -35 * math.pi / 180, 35 * math.pi / 180, hud_pen_color, False)

        tr_x = cx + 550
        tr_y = cy - 230
        
        now_dt = datetime.datetime.now()
        self.render_text(cr, tr_x + 14, tr_y + 10, self.hud_width - 64, 40, now_dt.strftime("%H:%M"), "SansSerif 24", self.colors["text"], "right")
        self.render_text(cr, tr_x + self.hud_width - 45, tr_y + 16, 35, 20, f":{now_dt.strftime('%S')}", "JetBrainsMono NF 10", self.colors["hint"])
        self.render_text(cr, tr_x + 14, tr_y + 54, self.hud_width - 28, 20, now_dt.strftime("%a, %d %b %Y").upper(), "JetBrainsMono NF Bold 8", self.colors["hint"], "right")
        
        cr.set_source_rgba(self.colors["text"][0], self.colors["text"][1], self.colors["text"][2], 0.15)
        cr.set_line_width(0.8)
        cr.move_to(tr_x + 14, tr_y + 78)
        cr.line_to(tr_x + self.hud_width - 14, tr_y + 78)
        cr.stroke()
        
        mid_split_x = tr_x + (self.hud_width // 2)
        text_y_row1 = tr_y + 92
        text_y_row2 = tr_y + 118
        
        self.render_text(cr, tr_x + 14, text_y_row1, 100, 16, f"  SR: {self.sunrise_str}", "JetBrainsMono NF 8", self.colors["hint"])
        self.render_text(cr, tr_x + 14, text_y_row2, 100, 16, f"  SS: {self.sunset_str}", "JetBrainsMono NF 8", self.colors["hint"])
        self.render_text(cr, mid_split_x, text_y_row1, 110, 16, f"WK: {self.week_num_str} / 52", "JetBrainsMono NF 8", self.colors["hint"], "right")
        self.render_text(cr, mid_split_x, text_y_row2, 110, 16, f" {self.lunar_icon}  {self.lunar_illum_pct}%", "JetBrainsMono NF 8", self.colors["hint"], "right")

        hw_x = cx + 565
        hw_y_start = tr_y + self.hud_base_height + 10
        hw_box_h = 70
        
        for idx, hw_type in enumerate(["vol", "bright"]):
            hy = hw_y_start + idx * (hw_box_h + 10)
            is_box_focused = (focused_group == f"{hw_type}_hud")
            
            if is_box_focused:
                cr.set_source_rgba(166/255.0, 227/255.0, 161/255.0, 0.4)
                cr.set_line_width(1.5)
                cr.arc(cx, cy, 715, (-10 + idx * 11) * math.pi / 180, (-1 + idx * 11) * math.pi / 180)
                cr.stroke()
                
            btn_w = 45
            btn_up_key = f"hw:{hw_type}:up"
            btn_down_key = f"hw:{hw_type}:down"
            
            bx_up, by_up, bw_up, bh_up = (hw_x + self.hud_width - 105, hy + 20, btn_w, 30)
            bx_dn, by_dn, bw_dn, bh_dn = (hw_x + self.hud_width - 55, hy + 20, btn_w, 30)
            
            if hw_type == "vol":
                self.render_text(cr, hw_x + 14, hy + 26, 120, 20, f"  VOL: {self.volume_level}%", "JetBrainsMono NF Bold 9", self.colors["accent"])
            else:
                self.render_text(cr, hw_x + 14, hy + 26, 120, 20, f"  BRT: {self.brightness_level}%", "JetBrainsMono NF Bold 9", self.colors["accent"])
                
            for h_key, label, bx, by, bw, bh in [(btn_up_key, " + ", bx_up, by_up, bw_up, bh_up), (btn_down_key, " - ", bx_dn, by_dn, bw_dn, bh_dn)]:
                if self.selected_target == h_key:
                    cr.set_source_rgba(166/255.0, 227/255.0, 161/255.0, 1.0)
                    cr.set_line_width(1.5)
                    self.draw_rounded_rectangle(cr, bx, by, bw, bh, 4)
                    cr.stroke_preserve()
                    cr.set_source_rgba(166/255.0, 227/255.0, 161/255.0, 0.13)
                    cr.fill()
                else:
                    cr.set_source_rgba(*self.colors["accent"])
                    cr.set_line_width(1.0)
                    self.draw_rounded_rectangle(cr, bx, by, bw, bh, 4)
                    cr.stroke_preserve()
                    cr.set_source_rgba(*self.colors["bg"])
                    cr.fill()
                self.render_text(cr, bx + 12, by + 6, bw, bh, label, "JetBrainsMono NF Bold 9", self.colors["text"])

        tasks_x = cx + 550
        tasks_y = hw_y_start + 2 * (hw_box_h + 10) + 5
            
        self.render_text(cr, tasks_x + 14, tasks_y + 10, self.hud_width - 28, 20, "  CUSTOM LAUNCHER", "JetBrainsMono NF Bold 9", self.colors["accent"])

        btn_w, btn_h, pad_x, pad_y = 46, 28, 8, 8
        start_x, start_y = tasks_x + 18, tasks_y + 32
        
        for i, t in enumerate(self.custom_tools):
            icon, tid, _ = t
            row, col = i // 4, i % 4
            bx = start_x + col * (btn_w + pad_x)
            by = start_y + row * (btn_h + pad_y)
            t_key = f"task:{tid}"
            
            if self.selected_target == t_key:
                br, bg, bb = 166/255.0, 227/255.0, 161/255.0
                fill_alpha = 0.13
                line_w = 1.5
            else:
                br, bg, bb = self.colors["accent"][0], self.colors["accent"][1], self.colors["accent"][2]
                fill_alpha = 0.0
                line_w = 1.0
                
            cr.set_source_rgba(br, bg, bb, 1.0)
            cr.set_line_width(line_w)
            self.draw_rounded_rectangle(cr, bx, by, btn_w, btn_h, 4)
            cr.stroke_preserve()
            
            if fill_alpha > 0.0:
                cr.set_source_rgba(br, bg, bb, fill_alpha)
                cr.fill()
            else:
                cr.set_source_rgba(*self.colors["bg"])
                cr.fill()
                
            if tid == "wifi" and self.wifi_connected:
                icon_color = (166/255.0, 227/255.0, 161/255.0, 1.0)
            elif tid == "bt" and self.bt_connected:
                icon_color = (137/255.0, 180/255.0, 250/255.0, 1.0)
            else:
                icon_color = self.colors["text"]
                
            self.render_text(cr, bx, by + 4, btn_w, btn_h, icon, "JetBrainsMono NF Bold 12", icon_color, "center")
            
        nav_br_y = tasks_y + 115
        self.render_text(cr, cx + 535, nav_br_y + 5, self.hud_width - 28, 14, f"windows: {self.total_windows_count}  |  uptime: {self.uptime_str}", "SansSerif 8", self.colors["hint"], "right")
        self.render_text(cr, cx + 535, nav_br_y + 22, self.hud_width - 28, 14, f"TRACKER: {self.tracker_status_str}", "JetBrainsMono NF Bold 8", self.colors["text"], "right")

        self.draw_helper_drawer_panel(cr)

    def on_mouse_move(self, widget, event):
        if event.x == 0.0 and event.y == 0.0:
            return True

        cx = self.get_allocated_width() / 2.0
        cy = self.get_allocated_height() / 2.0
        dx = event.x - cx
        dy = event.y - cy
        
        if event.state & Gdk.ModifierType.SHIFT_MASK:
            self.tilt_x = -(dy / self.get_allocated_height()) * (math.pi / 2)
            self.tilt_y = (dx / self.get_allocated_width()) * (math.pi / 2)
        else:
            self.rotation_offset = (dx / self.get_allocated_width()) * (2 * math.pi)
            
        self.queue_draw()
        return True

    def on_button_press(self, widget, event):
        if event.button != 1:
            return False
        x, y = event.x, event.y
        
        cx = self.get_allocated_width() / 2.0
        cy = self.get_allocated_height() / 2.0
        dx = x - cx
        dy = y - cy
        radial_distance = math.sqrt(dx*dx + dy*dy)
        polar_angle = math.atan2(dy, dx)
        
        if polar_angle < 0:
            polar_angle += 2 * math.pi
            
        if 580 <= radial_distance <= 840 and (145 * math.pi / 180) <= polar_angle <= (215 * math.pi / 180):
            tl_y = cy - 170
            bl_x = cx - 820
            bl_y = tl_y + self.hud_base_height + 10
            p_saver_x = bl_x + 14
            p_perf_x = bl_x + self.hud_width - 114
            p_btn_y = bl_y + 35
            p_btn_w, p_btn_h = 100, 30
            
            if p_btn_y <= y <= p_btn_y + p_btn_h:
                if p_saver_x <= x <= p_saver_x + p_btn_w:
                    self.execute_option("profile:powersave")
                    return True
                if p_perf_x <= x <= p_perf_x + p_btn_w:
                    self.execute_option("profile:performance")
                    return True
                    
            pwr_x = cx - 810
            pwr_y = bl_y + 75 + 10
            p_btn_w, p_btn_h, p_pad = 40, 28, 6
            p_start_x, p_start_y = pwr_x + 13, pwr_y + 32
            
            if p_start_y <= y <= p_start_y + p_btn_h:
                for i, act in enumerate(self.power_actions):
                    bx = p_start_x + i * (p_btn_w + p_pad)
                    if bx <= x <= bx + p_btn_w:
                        self.execute_option(f"power:{act[1]}")
                        return True
                        
        elif 580 <= radial_distance <= 840 and (polar_angle <= 35 * math.pi / 180 or polar_angle >= 325 * math.pi / 180):
            tr_x = cx + 550
            hw_y_start = cy - 230 + self.hud_base_height + 10
            hw_box_h = 70
            
            for idx, hw_type in enumerate(["vol", "bright"]):
                hw_x = cx + 565
                hy = hw_y_start + idx * (hw_box_h + 10)
                bx_up = hw_x + self.hud_width - 105
                bx_dn = hw_x + self.hud_width - 55
                by = hy + 20
                bw, bh = 45, 30
                
                if by <= y <= by + bh:
                    if bx_up <= x <= bx_up + bw:
                        self.execute_option(f"hw:{hw_type}:up")
                        return True
                    if bx_dn <= x <= bx_dn + bw:
                        self.execute_option(f"hw:{hw_type}:down")
                        return True
                        
            tasks_y = hw_y_start + 2 * (hw_box_h + 10) + 5
            btn_w, btn_h, pad_x, pad_y = 46, 28, 8, 8
            start_x, start_y = tr_x + 18, tasks_y + 32
            
            for i, t in enumerate(self.custom_tools):
                row, col = i // 4, i % 4
                bx = start_x + col * (btn_w + pad_x)
                by = start_y + row * (btn_h + pad_y)
                if bx <= x <= bx + btn_w and by <= y <= by + btn_h:
                    self.execute_option(f"task:{t[1]}")
                    return True
        return False

    def execute_option(self, target):
        if not target:
            return
            
        if target.startswith("profile:"):
            requested_profile = target.split("profile:")[1]
            subprocess.Popen(['pkexec', '/usr/local/bin/set-governor.sh', requested_profile])
            self.power_profile = requested_profile
            self.send_hud_notification("CPU Governor Profile", f"Active State: {self.power_profile.upper()}", "󱐌")
            self.queue_draw()
            return  
            
        elif target.startswith("hw:"):
            parts = target.split(":")
            hw_type = parts[1]
            direction = parts[2]
            
            if hw_type == "vol":
                if direction == "up":
                    self.volume_level = min(100, self.volume_level + 5)
                else:
                    self.volume_level = max(0, self.volume_level - 5)
                subprocess.run(f"wpctl set-volume @DEFAULT_AUDIO_SINK@ {self.volume_level/100:.2f}", shell=True)
                self.send_hud_notification("Volume Updated", f"Current Level: {self.volume_level}%", "")
            else:
                if direction == "up":
                    self.brightness_level = min(100, self.brightness_level + 10)
                else:
                    self.brightness_level = max(0, self.brightness_level - 10)
                subprocess.run(f"brightnessctl set {self.brightness_level}%", shell=True)
                self.send_hud_notification("Screen Brightness", f"Current Backlight: {self.brightness_level}%", "󰃠")
                
            self.queue_draw()
            return

        elif target.startswith("power:"):
            act_name = target.split("power:")[1]
            for act in self.power_actions:
                if act[1] == act_name:
                    subprocess.Popen(act[2], shell=True, start_new_session=True)
                    break
            return

        elif target.startswith("task:"):
            tid = target.split("task:")[1]
            for t in self.custom_tools:
                if t[1] == tid:
                    subprocess.Popen(t[2], shell=True, start_new_session=True)
                    break
            return

        elif target.startswith("cmd:"):
            cmd_type = target.split("cmd:")[1]
            if cmd_type == "togglefloating":
                lua_expr = 'hl.dsp.window.float({ action = "toggle" })'
            elif cmd_type == "fullscreen 0":
                lua_expr = 'hl.dsp.window.fullscreen({ action = "toggle" })'
            elif cmd_type == "pin":
                lua_expr = 'hl.dsp.window.pin({ action = "toggle" })'
            elif cmd_type == "togglesplit":
                lua_expr = 'hl.dsp.layout("togglesplit")'
            elif cmd_type.startswith("layout_"):
                layout_name = cmd_type.split("_")[1]
                lua_expr = f'hl.workspace_rule({{ workspace = "{self.active_workspace_id}", layout = "{layout_name}" }})'
            
            subprocess.run(["hyprctl", "eval", lua_expr])
            return

        elif target.startswith("sp:"):
            if "minimize" in target:
                subprocess.Popen(["python3", os.path.expanduser("~/.config/hypr/scripts/hypr-minimize.py"), "restore"], start_new_session=True)
            return
            
        else:
            lua_expr = f'hl.dispatch(hl.dsp.focus({{ workspace = "{target}" }}))'
            subprocess.run(["hyprctl", "eval", lua_expr])
            self.queue_draw()
            return
        
    def on_key_press(self, widget, event):
        keyval = event.keyval
        keyname = Gdk.keyval_name(keyval)
        
        if keyname in ("h", "question"):
            self.toggle_helper_drawer()
            return True
            
        if keyname == "Escape":
            if self.drawer.drawer_open:
                self.toggle_helper_drawer()
            return True
            
        elif keyname == "Tab":
            if event.state & Gdk.ModifierType.SHIFT_MASK:
                self.active_group_idx = (self.active_group_idx - 1) % len(self.groups_manifest)
            else:
                self.active_group_idx = (self.active_group_idx + 1) % len(self.groups_manifest)
            self.internal_option_idx = 0 
            self.synchronize_navigation_targets()
            self.queue_draw()
            return True
            
        elif keyname in ("Right", "Down"):
            self.internal_option_idx += 1
            self.synchronize_navigation_targets()
            self.queue_draw()
            return True
            
        elif keyname in ("Left", "Up"):
            self.internal_option_idx -= 1
            self.synchronize_navigation_targets()
            self.queue_draw()
            return True

        elif keyname in ("equal", "plus"):
            self.zoom_factor = min(2.0, self.zoom_factor + 0.25)
            self.queue_draw()
            return True
            
        elif keyname == "minus":
            self.zoom_factor = max(1.0, self.zoom_factor - 0.25)
            self.queue_draw()
            return True
            
        elif keyname in ("Return", "KP_Enter"):
            if self.selected_target:
                self.execute_option(self.selected_target)
            return True
            
        return False
