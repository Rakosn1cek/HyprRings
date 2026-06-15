# -------------------------------------
# HyprRings - Configuration Module
# Author: Lukas Grumlik (Rakosn1cek)
# Version: 0.2.0
# -------------------------------------

import os
import re

def parse_css_color(color_string, default_tuple):
    color_string = color_string.strip()
    if color_string.startswith("#"):
        hex_val = color_string.lstrip("#")
        if len(hex_val) == 6:
            return (int(hex_val[0:2], 16) / 255.0, int(hex_val[2:4], 16) / 255.0, int(hex_val[4:6], 16) / 255.0, 1.0)
    elif color_string.startswith("rgba"):
        parts = [float(x) for x in re.findall(r"[\d.]+", color_string)]
        if len(parts) >= 4:
            return (parts[0] / 255.0, parts[1] / 255.0, parts[2] / 255.0, parts[3])
    elif color_string.startswith("rgb"):
        parts = [float(x) for x in re.findall(r"[\d.]+", color_string)]
        if len(parts) >= 3:
            return (parts[0] / 255.0, parts[1] / 255.0, parts[2] / 255.0, 1.0)
    return default_tuple

def load_system_theme():
    colors = {
        "bg": (20 / 255.0, 20 / 255.0, 30 / 255.0, 1.0),
        "text": (205 / 255.0, 214 / 255.0, 244 / 255.0, 1.0),
        "hint": (147 / 255.0, 153 / 255.0, 178 / 255.0, 1.0),
        "accent": (137 / 255.0, 180 / 255.0, 250 / 255.0, 1.0)
    }
    theme_path = os.path.expanduser("~/custom-scripts/Control-Panel/current-theme.css")
    if not os.path.exists(theme_path):
        return colors
            
    try:
        with open(theme_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        bg_match = re.search(r"background(?:-color)?:\s*(rgba?\([^)]+\)|#[0-9a-fA-F]+)", content)
        text_match = re.search(r"QLabel\s*\{\s*color:\s*([^;]+);", content)
        hint_match = re.search(r"QLabel#DateLabel\s*\{\s*color:\s*([^;]+);", content)
        accent_match = re.search(r"(?:border-color|border):\s*(?:[^;]*\s)?(rgba?\([^)]+\)|#[0-9a-fA-F]+)", content)
        
        if bg_match:
            colors["bg"] = parse_css_color(bg_match.group(1), colors["bg"])
        if text_match:
            colors["text"] = parse_css_color(text_match.group(1), colors["text"])
        if hint_match:
            colors["hint"] = parse_css_color(hint_match.group(1), colors["hint"])
        if accent_match:
            colors["accent"] = parse_css_color(accent_match.group(1), colors["accent"])
                
    except Exception:
        pass
    return colors
