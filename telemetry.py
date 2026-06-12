# --------------------------------------
# HyprRings - Telemetry Module
# Author: Lukas Grumlik (Rakosn1cek)
# Version: 0.1.0
# --------------------------------------

import os
import json
import math
import time
import datetime
import subprocess

def fetch_system_state():
    try:
        active_raw = subprocess.check_output(["hyprctl", "activeworkspace", "-j"], text=True)
        active_workspace_id = json.loads(active_raw).get("id", 1)

        clients_raw = subprocess.check_output(["hyprctl", "clients", "-j"], text=True)
        workspaces_raw = subprocess.check_output(["hyprctl", "workspaces", "-j"], text=True)
        
        clients = json.loads(clients_raw)
        workspaces = json.loads(workspaces_raw)
        
        total_windows_count = len(clients)
        workspaces_data = {}
        special_workspaces = {}
        
        for ws in workspaces:
            ws_id = ws["id"]
            ws_name = ws.get("name", "")
            
            if ws_id >= 1:
                workspaces_data[ws_id] = {
                    "monitor": ws.get("monitor", "").upper(),
                    "fullscreen": False,
                    "windows": [],
                    "focused_win_title": "",
                    "focused_win_class": ""
                }
            elif ws_name.startswith("special:"):
                clean_name = ws_name.replace("special:", "")
                special_workspaces[ws_name] = {
                    "clean_name": clean_name,
                    "windows": [],
                    "monitor": ws.get("monitor", "").upper()
                }
        
        for client in clients:
            ws_id = client["workspace"]["id"]
            ws_name = client["workspace"]["name"]
            c_class = client.get("class", "").lower()
            c_title = client.get("title", "").lower()
            app_name = c_class if c_class else c_title
            if not app_name:
                continue
                
            if ws_id >= 1 and ws_id in workspaces_data:
                if client.get("focused", False):
                    workspaces_data[ws_id]["focused_win_class"] = c_class
                    workspaces_data[ws_id]["focused_win_title"] = c_title
                if client.get("fullscreen", False):
                    workspaces_data[ws_id]["fullscreen"] = True
                if app_name[:15] not in workspaces_data[ws_id]["windows"]:
                    workspaces_data[ws_id]["windows"].append(app_name[:15])
                    
            elif ws_name.startswith("special:") and ws_name in special_workspaces:
                if app_name[:12] not in special_workspaces[ws_name]["windows"]:
                    special_workspaces[ws_name]["windows"].append(app_name[:12])

        if active_workspace_id not in workspaces_data:
            workspaces_data[active_workspace_id] = {
                "monitor": "UNKNOWN" if not workspaces else workspaces[0].get("monitor", "").upper(),
                "fullscreen": False,
                "windows": [],
                "focused_win_title": "",
                "focused_win_class": ""
            }
        return active_workspace_id, total_windows_count, workspaces_data, special_workspaces
                    
    except Exception:
        return 1, 0, {}, {}

def fetch_hardware_metrics(last_cpu_idle, last_cpu_total):
    cpu_usage = 0
    ram_usage = 0
    core_temp = 0
    battery_percent = 100
    battery_detailed_info = "Error"
    uptime_str = "0h 0m"
    power_profile = "unknown"
    volume_level = 0
    brightness_level = 0
    tracker_status_str = "Inactive"
    wifi_connected = False
    bt_connected = False

    try:
        wifi_connected = subprocess.run("nmcli -t -f TYPE,STATE dev | grep -q '^wifi:connected'", shell=True).returncode == 0
        bt_connected = subprocess.run("bluetoothctl devices Connected | grep -q '.'", shell=True).returncode == 0
    except Exception:
        pass

    except Exception:
        pass

    try:
        with open("/proc/stat", "r") as f:
            fields = [float(col) for col in f.readline().strip().split()[1:]]
        idle = fields[3]
        total = sum(fields)
        diff_idle = idle - last_cpu_idle
        diff_total = total - last_cpu_total
        if diff_total > 0:
            cpu_usage = int((1.0 - diff_idle / diff_total) * 100)
        last_cpu_idle = idle
        last_cpu_total = total

        with open("/proc/meminfo", "r") as f:
            lines = f.readlines()
        total_ram = int(lines[0].split()[1])
        avail_ram = int(lines[2].split()[1])
        ram_usage = int(((total_ram - avail_ram) / total_ram) * 100)

        bat_path = "/sys/class/power_supply/BAT0"
        if not os.path.exists(bat_path):
            bat_path = "/sys/class/power_supply/BAT1"
            
        def read_sys_bat(file):
            try:
                with open(f"{bat_path}/{file}", 'r') as f:
                    return int(f.read().strip())
            except: return 0

        battery_percent = read_sys_bat("capacity")
        pwr_now = read_sys_bat("power_now")
        pwr = pwr_now / 1000000
        vlt = read_sys_bat("voltage_now") / 1000000
        full = read_sys_bat("energy_full") or read_sys_bat("charge_full")
        now = read_sys_bat("energy_now") or read_sys_bat("charge_now")
        design = read_sys_bat("energy_full_design") or read_sys_bat("charge_full_design")
        health = int(100 * full / design) if design > 0 else 0
        
        try:
            with open(f"{bat_path}/status", 'r') as f:
                status = f.read().strip()
        except: status = "Unknown"
        
        time_info = "Calculating..."
        if pwr_now > 0:
            if status == "Discharging":
                hours = now / pwr_now
                time_info = f"{int(hours)}h {int((hours % 1) * 60)}m left"
            elif status == "Charging":
                hours = (full - now) / pwr_now
                time_info = f"{int(hours)}h {int((hours % 1) * 60)}m to full"
        elif status == "Full": time_info = "Battery Full"
        
        battery_detailed_info = f"{pwr:.1f}W | {vlt:.1f}V | Hlth: {health}% | {time_info}"

        with open("/proc/uptime", "r") as f:
            uptime_secs = float(f.readline().split()[0])
        uptime_str = f"{int(uptime_secs // 3600)}h {int((uptime_secs % 3600) // 60)}m"
        
        try:
            with open("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", "r", encoding='utf-8') as f:
                power_profile = f.read().strip()
        except:
            pass

        try:
            # Search the hardware monitoring tree for dedicated CPU silicon drivers
            for hwmon_dir in os.listdir("/sys/class/hwmon"):
                with open(f"/sys/class/hwmon/{hwmon_dir}/name", "r") as f:
                    sensor_name = f.read().strip()
                if sensor_name in ["coretemp", "cpu_thermal", "k10temp", "zenpower"]:
                    with open(f"/sys/class/hwmon/{hwmon_dir}/temp1_input", "r") as f:
                        core_temp = int(f.read().strip()) // 1000
                    break
            else:
                # Fallback to scanning thermal zone labels if hwmon handles are unavailable
                for zone in os.listdir("/sys/class/thermal"):
                    if zone.startswith("thermal_zone"):
                        with open(f"/sys/class/thermal/{zone}/type", "r") as f:
                            zone_type = f.read().strip().lower()
                        if "pkg" in zone_type or "cpu" in zone_type:
                            with open(f"/sys/class/thermal/{zone}/temp", "r") as f:
                                core_temp = int(f.read().strip()) // 1000
                            break
        except Exception:
            pass
        
        try:
            vol_raw = subprocess.check_output("wpctl get-volume @DEFAULT_AUDIO_SINK@", shell=True, text=True)
            volume_level = int(float(vol_raw.split(":")[1].strip()) * 100)
        except:
            pass
            
        try:
            bright_raw = subprocess.check_output("brightnessctl g", shell=True, text=True).strip()
            max_bright_raw = subprocess.check_output("brightnessctl m", shell=True, text=True).strip()
            if bright_raw and max_bright_raw:
                brightness_level = int((int(bright_raw) / int(max_bright_raw)) * 100)
        except:
            pass
            
        tracker_log = os.path.expanduser("~/.tt_running")
        if os.path.exists(tracker_log):
            try:
                with open(tracker_log, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
                if len(lines) >= 2:
                    start_time = int(lines[0])
                    proj_name = lines[1]
                    elapsed = max(0, int(time.time()) - start_time)
                    h, r = divmod(elapsed, 3600)
                    m, _ = divmod(r, 60)
                    tracker_status_str = f"{proj_name} ({h:02d}:{m:02d})"
            except:
                pass
                
    except Exception:
        pass

    return cpu_usage, last_cpu_idle, last_cpu_total, ram_usage, battery_percent, battery_detailed_info, uptime_str, power_profile, volume_level, brightness_level, tracker_status_str, core_temp, wifi_connected, bt_connected

def calculate_astronomy_data():
    now = datetime.datetime.now()
    week_num_str = f"{now.isocalendar()[1]}"
    
    lat = 51.5074 
    day_of_year = now.timetuple().tm_yday
    declination = 23.45 * math.sin(math.radians((360 / 365) * (284 + day_of_year)))
    
    cos_hour_angle = -math.tan(math.radians(lat)) * math.tan(math.radians(declination))
    cos_hour_angle = max(-1.0, min(1.0, cos_hour_angle))
    
    hour_angle = math.degrees(math.acos(cos_hour_angle))
    daylight_hours = (hour_angle * 2) / 15
    
    solar_noon = 12.0 + (declination * 0.05) 
    sunrise_decimal = solar_noon - (daylight_hours / 2)
    sunset_decimal = solar_noon + (daylight_hours / 2)
    
    s_min, s_hr = math.modf(sunrise_decimal)
    sunrise_str = f"{int(s_hr):02d}:{int(s_min * 60):02d}"
    
    set_min, set_hr = math.modf(sunset_decimal)
    sunset_str = f"{int(set_hr):02d}:{int(set_min * 60):02d}"
    
    diff = now - datetime.datetime(2000, 1, 6, 18, 14)
    lunar_days = diff.total_seconds() / 86400.0
    cycle_position = (lunar_days % 29.530588853) / 29.530588853
    
    lunar_illum_pct = int((1 - math.cos(cycle_position * 2 * math.pi)) * 50)
    
    if cycle_position < 0.034:
        lunar_phase_str = "New Moon"
        lunar_icon = "󰽔"
    elif cycle_position < 0.216:
        lunar_phase_str = "Waxing Crescent"
        lunar_icon = "󰽕"
    elif cycle_position < 0.284:
        lunar_phase_str = "First Quarter"
        lunar_icon = "󰽖"
    elif cycle_position < 0.466:
        lunar_phase_str = "Waxing Gibbous"
        lunar_icon = "󰽗"
    elif cycle_position < 0.534:
        lunar_phase_str = "Full Moon"
        lunar_icon = "󰽢"
    elif cycle_position < 0.716:
        lunar_phase_str = "Waning Gibbous"
        lunar_icon = "󰽚"
    elif cycle_position < 0.784:
        lunar_phase_str = "Third Quarter"
        lunar_icon = "󰽛"
    else:
        lunar_phase_str = "Waning Crescent"
        lunar_icon = "󰽜"

    return week_num_str, sunrise_str, sunset_str, lunar_phase_str, lunar_illum_pct, lunar_icon
