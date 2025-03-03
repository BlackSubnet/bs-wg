import datetime
import subprocess
import re

def format_bytes(bytes_value):
    """Format bytes to human-readable format"""
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value/1024:.2f} KB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value/(1024*1024):.2f} MB"
    elif bytes_value < 1024 * 1024 * 1024 * 1024:
        return f"{bytes_value/(1024*1024*1024):.2f} GB"
    else:
        return f"{bytes_value/(1024*1024*1024*1024):.2f} TB"

def format_timestamp(ts):
    """Format a timestamp to human-readable format"""
    if not ts:
        return "Never"
    
    try:
        if isinstance(ts, str):
            dt = datetime.datetime.fromisoformat(ts.replace('Z', '+00:00'))
        else:
            dt = ts
            
        now = datetime.datetime.now()
        delta = now - dt
        
        if delta.days > 30:
            return dt.strftime("%Y-%m-%d")
        elif delta.days > 0:
            return f"{delta.days} days ago"
        elif delta.seconds > 3600:
            return f"{delta.seconds // 3600} hours ago"
        elif delta.seconds > 60:
            return f"{delta.seconds // 60} minutes ago"
        elif delta.seconds > 0:
            return f"{delta.seconds} seconds ago"
        else:
            return "Just now"
    except Exception:
        return "Invalid date"
        
def get_server_stats():
    """Get server statistics"""
    stats = {}
    
    # Get load averages
    try:
        with open('/proc/loadavg', 'r') as f:
            load = f.read().strip().split()
            stats['load'] = {
                '1min': float(load[0]),
                '5min': float(load[1]),
                '15min': float(load[2])
            }
    except:
        stats['load'] = {'1min': 0, '5min': 0, '15min': 0}
    
    # Get memory usage
    try:
        with open('/proc/meminfo', 'r') as f:
            mem_info = {}
            for line in f:
                key, value = line.split(':')
                mem_info[key.strip()] = int(value.strip().split()[0])
            
            total = mem_info['MemTotal']
            free = mem_info['MemFree']
            buffers = mem_info.get('Buffers', 0)
            cached = mem_info.get('Cached', 0)
            
            used = total - free - buffers - cached
            stats['memory'] = {
                'total': total * 1024,  # Convert to bytes
                'used': used * 1024,
                'percentage': (used / total) * 100
            }
    except:
        stats['memory'] = {'total': 0, 'used': 0, 'percentage': 0}
    
    # Get disk usage
    try:
        df = subprocess.check_output(['df', '-B1', '/']).decode().strip().split('\n')[1]
        parts = re.split(r'\s+', df)
        stats['disk'] = {
            'total': int(parts[1]),
            'used': int(parts[2]),
            'percentage': int(parts[4].rstrip('%'))
        }
    except:
        stats['disk'] = {'total': 0, 'used': 0, 'percentage': 0}
    
    # Get uptime
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.read().split()[0])
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            stats['uptime'] = {
                'days': days,
                'hours': hours,
                'minutes': minutes,
                'formatted': f"{days} days, {hours} hours, {minutes} minutes"
            }
    except:
        stats['uptime'] = {'days': 0, 'hours': 0, 'minutes': 0, 'formatted': "Unknown"}
    
    # Get WireGuard version
    try:
        wg_version = subprocess.check_output(['wg', 'version']).decode().strip()
        stats['wg_version'] = wg_version
    except:
        stats['wg_version'] = "Unknown"
    
    return stats