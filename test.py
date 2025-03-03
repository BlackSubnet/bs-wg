# test_wireguard.py
import subprocess
import json

def test_wireguard_setup():
    results = {
        "ip_forward": False,
        "wireguard_running": False,
        "interface_up": False,
        "port_listening": False
    }
    
    # Check IP forwarding
    try:
        with open('/proc/sys/net/ipv4/ip_forward', 'r') as f:
            if f.read().strip() == '1':
                results["ip_forward"] = True
    except:
        pass

    # Check WireGuard service
    try:
        status = subprocess.run(['systemctl', 'is-active', 'wg-quick@wg0'], 
                              capture_output=True, text=True)
        if status.stdout.strip() == 'active':
            results["wireguard_running"] = True
    except:
        pass

    # Check interface
    try:
        ifconfig = subprocess.run(['ip', 'a', 'show', 'wg0'], 
                                capture_output=True, text=True)
        if 'state UP' in ifconfig.stdout:
            results["interface_up"] = True
    except:
        pass

    # Check port
    try:
        netstat = subprocess.run(['netstat', '-lnup'], 
                               capture_output=True, text=True)
        if ':51820' in netstat.stdout:
            results["port_listening"] = True
    except:
        pass

    return results

if __name__ == "__main__":
    results = test_wireguard_setup()
    print(json.dumps(results, indent=2))