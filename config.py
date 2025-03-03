import os

# WireGuard Configuration
PUBLIC_IP = ""  # Replace with your actual public IP
WG_PORT = 51820
WG_CONFIG_PATH = '/etc/wireguard/wg0.conf'
WG_INTERFACE = 'wg0'

# Network Configuration
WG_SUBNET = '10.8.0.0/24'
WG_DNS = '1.1.1.1, 1.0.0.1'
WG_MTU = 1420
WG_PERSISTENT_KEEPALIVE = 25

# Application Configuration
SECRET_KEY = 'your-secret-key-here' 
ADMIN_PASSWORD = "PASSWORD" # Change this to a secure random value
DATABASE_PATH = os.path.join('instance', 'clients.db')
DEBUG = True
