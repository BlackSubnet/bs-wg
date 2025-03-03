from database import get_db_connection
from config import (
    PUBLIC_IP,
    WG_PORT,
    WG_INTERFACE,
    WG_CONFIG_PATH,
    WG_SUBNET,
    WG_DNS,
    WG_MTU,
    WG_PERSISTENT_KEEPALIVE
)
import subprocess
import os
import base64
import qrcode
import io
import datetime

def generate_keypair():
    """Generate a WireGuard private/public key pair"""
    private_key = subprocess.check_output(['wg', 'genkey']).decode('utf-8').strip()
    public_key = subprocess.check_output(['wg', 'pubkey'], input=private_key.encode()).decode('utf-8').strip()
    return private_key, public_key

def generate_preshared_key():
    """Generate a WireGuard preshared key"""
    return subprocess.check_output(['wg', 'genpsk']).decode('utf-8').strip()

def generate_client_config(client, server_config):
    """Generate a client configuration file"""
    if not client or not server_config:
        raise ValueError("Client and server configuration are required")

    client_config = f"""[Interface]
PrivateKey = {client['private_key']}
Address = {client['assigned_ip']}/24
DNS = 1.1.1.1, 1.0.0.1
MTU = 1420

[Peer]
PublicKey = {server_config['public_key']}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {PUBLIC_IP}:{WG_PORT}
PersistentKeepalive = 25
"""
    
    return client_config

def generate_qr_code(config_text):
    """Generate a QR code for a client configuration"""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(config_text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert image to base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def apply_server_config(server_config):
    """Apply server configuration to WireGuard"""
    config_content = f"""[Interface]
PrivateKey = {server_config['private_key']}
Address = 10.8.0.1/24
ListenPort = {WG_PORT}
MTU = {WG_MTU}

PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -A FORWARD -o %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -D FORWARD -o %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE
"""

    # Write peer configurations
    with get_db_connection() as conn:
        clients = conn.execute('SELECT * FROM clients WHERE is_active = 1').fetchall()
        for client in clients:
            config_content += f"""
[Peer]
PublicKey = {client['public_key']}
AllowedIPs = {client['assigned_ip']}/32
"""

    # Write the configuration
    with open(WG_CONFIG_PATH, 'w') as f:
        f.write(config_content)
    os.chmod(WG_CONFIG_PATH, 0o600)

    # Restart WireGuard
    restart_wireguard()
    return True

def restart_wireguard():
    """Restart the WireGuard interface"""
    try:
        subprocess.run(['systemctl', 'restart', f'wg-quick@{WG_INTERFACE}'], check=True)
        return True
    except subprocess.CalledProcessError:
        return False




def update_client_traffic(client_id, client_status):
    """Update client traffic data"""
    try:
        # Get transfer data from client status
        transfer = client_status.get('transfer', {})
        upload = transfer.get('tx', 0)  # tx is upload from client perspective
        download = transfer.get('rx', 0)  # rx is download from client perspective
        
        with get_db_connection() as conn:
            # Update traffic logs
            conn.execute('''
            INSERT INTO traffic_logs (client_id, upload, download, timestamp)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (client_id, upload, download))
            
            # Update client's last seen and data usage
            conn.execute('''
            UPDATE clients 
            SET last_seen = CURRENT_TIMESTAMP,
                data_usage = data_usage + ?
            WHERE id = ?
            ''', ((upload + download) / (1024 * 1024), client_id))  # Convert to MB
            
            conn.commit()
            
    except Exception as e:
        print(f"Error updating client traffic: {e}")


# def get_client_status():
#     """Get the status of all WireGuard clients"""
#     try:
#         output = subprocess.check_output(['wg', 'show', WG_INTERFACE], universal_newlines=True)
#         clients = {}
#         current_peer = None
        
#         for line in output.splitlines():
#             line = line.strip()
#             if line.startswith('peer:'):
#                 current_peer = line.split('peer:')[1].strip()
#                 clients[current_peer] = {'online': False, 'latest_handshake': None, 'transfer': {'rx': 0, 'tx': 0}}
#             elif current_peer and line.startswith('latest handshake:'):
#                 handshake_time = line.split('latest handshake:')[1].strip()
#                 clients[current_peer]['latest_handshake'] = handshake_time
#                 if 'minute' in handshake_time and int(handshake_time.split()[0]) <= 3:
#                     clients[current_peer]['online'] = True
#             elif current_peer and line.startswith('transfer:'):
#                 parts = line.split('transfer:')[1].strip().split(',')
#                 rx = parts[0].strip().split('received')[0].strip()
#                 tx = parts[1].strip().split('sent')[0].strip()
#                 clients[current_peer]['transfer']['rx'] = convert_to_bytes(rx)
#                 clients[current_peer]['transfer']['tx'] = convert_to_bytes(tx)
        
#         return clients
#     except subprocess.CalledProcessError:
#         return {}

def convert_to_bytes(size_str):
    """Convert a size string (e.g., '1.23 KiB') to bytes"""
    if not size_str:
        return 0
    
    size_str = size_str.strip()
    try:
        size = float(size_str.split()[0])
        unit = size_str.split()[1].upper()
        
        multipliers = {
            'B': 1,
            'KIB': 1024,
            'MIB': 1024 ** 2,
            'GIB': 1024 ** 3,
            'TIB': 1024 ** 4
        }
        
        return int(size * multipliers.get(unit, 1))
    except (IndexError, ValueError):
        return 0

def add_client_to_wireguard(client):
    """Add a client to the WireGuard configuration"""
    try:
        subprocess.run(['wg', 'set', WG_INTERFACE, 
                       'peer', client['public_key'],
                       'allowed-ips', f"{client['assigned_ip']}/32"],
                      check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def remove_client_from_wireguard(public_key):
    """Remove a client from the WireGuard configuration"""
    try:
        subprocess.run(['wg', 'set', WG_INTERFACE, 
                       'peer', public_key,
                       'remove'], 
                      check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def get_client_status():
    """Get the status of all WireGuard clients"""
    try:
        output = subprocess.check_output(['wg', 'show', WG_INTERFACE], universal_newlines=True)
        
        clients = {}
        current_peer = None
        
        for line in output.splitlines():
            line = line.strip()
            
            if line.startswith('peer:'):
                current_peer = line.split('peer:')[1].strip()
                clients[current_peer] = {
                    'online': False,
                    'latest_handshake': None,
                    'transfer': {'rx': 0, 'tx': 0}
                }
            
            elif current_peer and line.startswith('latest handshake:'):
                handshake_time = line.split('latest handshake:')[1].strip()
                
                if 'never' in handshake_time.lower():
                    clients[current_peer]['latest_handshake'] = None
                    clients[current_peer]['online'] = False
                else:
                    clients[current_peer]['latest_handshake'] = handshake_time
                    # Get the current time for comparison
                    current_time = datetime.datetime.now()
                    
                    try:
                        # Parse the handshake time
                        if 'minutes' in handshake_time or 'minute' in handshake_time:
                            minutes = int(handshake_time.split()[0])
                            clients[current_peer]['online'] = minutes <= 3
                            
                            # Update last seen in database only if online
                            if clients[current_peer]['online']:
                                with get_db_connection() as conn:
                                    conn.execute('''
                                        UPDATE clients 
                                        SET last_seen = datetime('now')
                                        WHERE public_key = ? AND is_active = 1
                                    ''', (current_peer,))
                                    conn.commit()
                                    
                        elif 'seconds' in handshake_time or 'second' in handshake_time:
                            clients[current_peer]['online'] = True
                            # Update last seen for active connections
                            with get_db_connection() as conn:
                                conn.execute('''
                                    UPDATE clients 
                                    SET last_seen = datetime('now')
                                    WHERE public_key = ? AND is_active = 1
                                ''', (current_peer,))
                                conn.commit()
                        else:
                            # If handshake is older, mark as offline
                            clients[current_peer]['online'] = False
                    except ValueError:
                        clients[current_peer]['online'] = False
            
            elif current_peer and line.startswith('transfer:'):
                parts = line.split('transfer:')[1].strip().split(',')
                rx = parts[0].strip().split('received')[0].strip()
                tx = parts[1].strip().split('sent')[0].strip()
                clients[current_peer]['transfer']['rx'] = convert_to_bytes(rx)
                clients[current_peer]['transfer']['tx'] = convert_to_bytes(tx)
                
                # If there's transfer data but no recent handshake, check recent traffic
                if not clients[current_peer]['online']:
                    rx_bytes = convert_to_bytes(rx)
                    tx_bytes = convert_to_bytes(tx)
                    if rx_bytes > 0 or tx_bytes > 0:
                        # Update traffic data
                        with get_db_connection() as conn:
                            # Get the last traffic log
                            last_traffic = conn.execute('''
                                SELECT upload, download 
                                FROM traffic_logs 
                                WHERE client_id = (
                                    SELECT id FROM clients WHERE public_key = ?
                                )
                                ORDER BY timestamp DESC LIMIT 1
                            ''', (current_peer,)).fetchone()
                            
                            if last_traffic:
                                # If there's new traffic, consider the client online
                                if rx_bytes > last_traffic['download'] or tx_bytes > last_traffic['upload']:
                                    clients[current_peer]['online'] = True
                                    conn.execute('''
                                        UPDATE clients 
                                        SET last_seen = datetime('now')
                                        WHERE public_key = ? AND is_active = 1
                                    ''', (current_peer,))
                                    conn.commit()
        
        # Update traffic data for each client
        with get_db_connection() as conn:
            client_records = conn.execute('SELECT id, public_key FROM clients').fetchall()
            for client in client_records:
                if client['public_key'] in clients:
                    update_client_traffic(client['id'], clients[client['public_key']])
        
        return clients
    except subprocess.CalledProcessError as e:
        print(f"Error getting client status: {e}")
        return {}

def convert_to_bytes(size_str):
    """Convert a size string (e.g., '1.23 KiB') to bytes"""
    size_str = size_str.strip()
    size = float(size_str.split()[0])
    unit = size_str.split()[1]
    
    if unit == 'B':
        return int(size)
    elif unit == 'KiB':
        return int(size * 1024)
    elif unit == 'MiB':
        return int(size * 1024 * 1024)
    elif unit == 'GiB':
        return int(size * 1024 * 1024 * 1024)
    elif unit == 'TiB':
        return int(size * 1024 * 1024 * 1024 * 1024)
    return 0