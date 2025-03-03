import sqlite3
import os
import datetime
from contextlib import contextmanager
from config import DATABASE_PATH
import subprocess
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


def generate_keypair():
    """Generate a WireGuard private/public key pair"""
    try:
        # Generate private key
        private_key = subprocess.check_output(['wg', 'genkey'], text=True).strip()
        
        # Generate public key from private key
        public_key = subprocess.run(
            ['wg', 'pubkey'],
            input=private_key,
            text=True,
            capture_output=True
        ).stdout.strip()
        
        return private_key, public_key
    except subprocess.CalledProcessError as e:
        print(f"Error generating keypair: {e}")
        return None, None

def generate_preshared_key():
    """Generate a WireGuard preshared key"""
    try:
        return subprocess.check_output(['wg', 'genpsk'], text=True).strip()
    except subprocess.CalledProcessError as e:
        print(f"Error generating preshared key: {e}")
        return None

def init_db():
    """Initialize the database with required tables"""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    with get_db_connection() as conn:
        # Create clients table
        conn.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            private_key TEXT NOT NULL,
            public_key TEXT NOT NULL,
            preshared_key TEXT,
            assigned_ip TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP,
            is_active INTEGER NOT NULL DEFAULT 1,
            data_limit INTEGER,  -- in GB, NULL means no limit
            data_usage INTEGER DEFAULT 0,  -- in MB
            expiry_date TIMESTAMP
        )
        ''')
        
        # Create server_config table
        conn.execute(f'''
        CREATE TABLE IF NOT EXISTS server_config (
             id INTEGER PRIMARY KEY CHECK (id = 1),
             endpoint TEXT NOT NULL DEFAULT '{PUBLIC_IP}:{WG_PORT}',
             subnet TEXT NOT NULL DEFAULT '{WG_SUBNET}',
             dns_servers TEXT NOT NULL DEFAULT '{WG_DNS}',
             mtu INTEGER NOT NULL DEFAULT {WG_MTU},
             keepalive INTEGER NOT NULL DEFAULT {WG_PERSISTENT_KEEPALIVE},
             private_key TEXT,
             public_key TEXT,
             last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
              )
           ''')
        
        # Create traffic_logs table
        conn.execute('''
        CREATE TABLE IF NOT EXISTS traffic_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            upload INTEGER NOT NULL DEFAULT 0,  -- in bytes
            download INTEGER NOT NULL DEFAULT 0,  -- in bytes
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients (id)
        )
        ''')
        
        # Create daily traffic logs table for aggregated data
        conn.execute('''
        CREATE TABLE IF NOT EXISTS traffic_logs_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            date DATE NOT NULL,
            total_upload INTEGER NOT NULL DEFAULT 0,  -- in bytes
            total_download INTEGER NOT NULL DEFAULT 0,  -- in bytes
            FOREIGN KEY (client_id) REFERENCES clients (id),
            UNIQUE(client_id, date)
        )
        ''')
        
        # Create stats table for general statistics
        conn.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            total_clients INTEGER NOT NULL DEFAULT 0,
            active_clients INTEGER NOT NULL DEFAULT 0,
            total_traffic INTEGER NOT NULL DEFAULT 0,  -- in bytes
            uptime INTEGER NOT NULL DEFAULT 0  -- in seconds
        )
        ''')

        # Create indexes for better performance
        conn.execute('CREATE INDEX IF NOT EXISTS idx_traffic_logs_timestamp ON traffic_logs(timestamp)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_traffic_logs_client ON traffic_logs(client_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_traffic_daily_date ON traffic_logs_daily(date)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_traffic_daily_client ON traffic_logs_daily(client_id)')
        
        conn.commit()

# Helper function to update traffic logs
def update_traffic_log(client_id, upload_bytes, download_bytes):
    """Update traffic logs for a client"""
    with get_db_connection() as conn:
        conn.execute('''
        INSERT INTO traffic_logs (client_id, upload, download)
        VALUES (?, ?, ?)
        ''', (client_id, upload_bytes, download_bytes))
        
        # Update client's total data usage
        conn.execute('''
        UPDATE clients 
        SET data_usage = data_usage + ?,
            last_seen = CURRENT_TIMESTAMP 
        WHERE id = ?
        ''', ((upload_bytes + download_bytes) / (1024 * 1024), client_id))  # Convert bytes to MB
        
        conn.commit()

# Helper function to get traffic statistics
def get_traffic_stats():
    """Get traffic statistics"""
    with get_db_connection() as conn:
        # Get monthly traffic
        monthly_traffic = conn.execute('''
        SELECT COALESCE(SUM(upload) + SUM(download), 0) as total
        FROM traffic_logs 
        WHERE timestamp >= date('now', 'start of month')
        ''').fetchone()
        
        # Get client counts
        counts = conn.execute('''
        SELECT 
            COUNT(*) as total_clients,
            SUM(CASE WHEN is_active = 1 AND (expiry_date IS NULL OR expiry_date > CURRENT_TIMESTAMP) THEN 1 ELSE 0 END) as active_clients
        FROM clients
        ''').fetchone()
        
        return {
            'monthly_traffic_bytes': monthly_traffic['total'],
            'total_clients': counts['total_clients'],
            'active_clients': counts['active_clients']
        }

# Helper function to get client traffic history
def get_client_traffic_history(client_id, days=30):
    """Get traffic history for a specific client"""
    with get_db_connection() as conn:
        traffic_data = conn.execute('''
        SELECT 
            date(timestamp) as date,
            SUM(upload) as upload,
            SUM(download) as download
        FROM traffic_logs
        WHERE client_id = ? AND timestamp >= date('now', ?)
        GROUP BY date(timestamp)
        ORDER BY date(timestamp)
        ''', (client_id, f'-{days} days')).fetchall()
        
        return [dict(row) for row in traffic_data]

# Helper function to cleanup old traffic logs
def cleanup_old_traffic_logs(days_to_keep=90):
    """Remove traffic logs older than specified days"""
    with get_db_connection() as conn:
        conn.execute('''
        DELETE FROM traffic_logs
        WHERE timestamp < date('now', ?)
        ''', (f'-{days_to_keep} days',))
        conn.commit()

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        if conn:
            conn.close()

# Client CRUD operations
def add_client(name, email, private_key, public_key, assigned_ip, preshared_key=None, data_limit=None, expiry_date=None):
    """Add a new client to the database"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO clients (name, email, private_key, public_key, preshared_key, assigned_ip, data_limit, expiry_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, email, private_key, public_key, preshared_key, assigned_ip, data_limit, expiry_date))
        conn.commit()
        return cursor.lastrowid

def get_client(client_id):
    """Get a client by ID"""
    with get_db_connection() as conn:
        client = conn.execute('SELECT * FROM clients WHERE id = ?', (client_id,)).fetchone()
        return dict(client) if client else None


def cleanup_old_traffic_logs(days_to_keep=30):
    """Remove traffic logs older than specified days"""
    try:
        with get_db_connection() as conn:
            conn.execute('''
            DELETE FROM traffic_logs
            WHERE timestamp < datetime('now', '-' || ? || ' days')
            ''', (days_to_keep,))
            conn.commit()
    except Exception as e:
        print(f"Error cleaning up traffic logs: {e}")

def aggregate_traffic_data():
    """Aggregate traffic data for long-term storage"""
    try:
        with get_db_connection() as conn:
            # Aggregate daily data older than 7 days
            conn.execute('''
            INSERT INTO traffic_logs_daily (
                client_id,
                date,
                total_upload,
                total_download
            )
            SELECT 
                client_id,
                date(timestamp) as date,
                SUM(upload) as total_upload,
                SUM(download) as total_download
            FROM traffic_logs
            WHERE timestamp < datetime('now', '-7 days')
            GROUP BY client_id, date(timestamp)
            ''')
            
            # Remove the detailed logs that were aggregated
            conn.execute('''
            DELETE FROM traffic_logs
            WHERE timestamp < datetime('now', '-7 days')
            ''')
            
            conn.commit()
    except Exception as e:
        print(f"Error aggregating traffic data: {e}")



def get_all_clients():
    """Get all clients"""
    with get_db_connection() as conn:
        clients = conn.execute('SELECT * FROM clients ORDER BY created_at DESC').fetchall()
        return [dict(client) for client in clients]

def get_active_clients():
    """Get only active clients"""
    with get_db_connection() as conn:
        clients = conn.execute('SELECT * FROM clients WHERE is_active = 1 ORDER BY created_at DESC').fetchall()
        return [dict(client) for client in clients]

def update_client(client_id, **kwargs):
    """Update a client's details"""
    allowed_fields = {'name', 'email', 'is_active', 'data_limit', 'expiry_date', 'last_seen'}
    update_fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
    
    if not update_fields:
        return False
    
    set_clause = ', '.join([f"{field} = ?" for field in update_fields.keys()])
    values = list(update_fields.values())
    values.append(client_id)
    
    with get_db_connection() as conn:
        cursor = conn.execute(f'''
        UPDATE clients SET {set_clause} WHERE id = ?
        ''', values)
        conn.commit()
        return cursor.rowcount > 0

def delete_client(client_id):
    """Delete a client"""
    with get_db_connection() as conn:
        cursor = conn.execute('DELETE FROM clients WHERE id = ?', (client_id,))
        conn.commit()
        return cursor.rowcount > 0

def update_client_status(client_id, is_active):
    """Update a client's active status"""
    with get_db_connection() as conn:
        conn.execute('UPDATE clients SET is_active = ? WHERE id = ?', (1 if is_active else 0, client_id))
        conn.commit()

def find_available_ip():
    """Find an available IP address in the network range"""
    subnet_base = '10.8.0.'
    with get_db_connection() as conn:
        used_ips = [row[0] for row in conn.execute('SELECT assigned_ip FROM clients').fetchall()]
    
    # Start from .2 since .1 is typically the server
    for i in range(2, 255):
        candidate_ip = f"{subnet_base}{i}"
        if candidate_ip not in used_ips:
            return candidate_ip
    
    return None  # No available IPs

def update_data_usage(client_id, upload_bytes, download_bytes):
    """Update a client's data usage and log traffic"""
    with get_db_connection() as conn:
        # Log the traffic
        conn.execute('''
        INSERT INTO traffic_logs (client_id, upload, download)
        VALUES (?, ?, ?)
        ''', (client_id, upload_bytes, download_bytes))
        
        # Update the client's data usage (convert bytes to MB)
        total_mb = (upload_bytes + download_bytes) / (1024 * 1024)
        conn.execute('''
        UPDATE clients 
        SET data_usage = data_usage + ?, last_seen = CURRENT_TIMESTAMP 
        WHERE id = ?
        ''', (total_mb, client_id))
        conn.commit()

def get_server_config():
    """Get the server configuration"""
    with get_db_connection() as conn:
        config = conn.execute('SELECT * FROM server_config WHERE id = 1').fetchone()
        if config is None:
            # Generate new keys
            private_key, public_key = generate_keypair()
            
            # Initialize with default values
            conn.execute('''
                INSERT INTO server_config (
                    endpoint, subnet, dns_servers, mtu, keepalive, private_key, public_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                f"{PUBLIC_IP}:{WG_PORT}",  # Use actual public IP
                WG_SUBNET,
                WG_DNS,
                WG_MTU,
                WG_PERSISTENT_KEEPALIVE,
                private_key,
                public_key
            ))
            conn.commit()
            config = conn.execute('SELECT * FROM server_config WHERE id = 1').fetchone()
        return dict(config)


def update_server_config(endpoint, subnet, dns_servers, mtu, keepalive):
    """Update the server configuration"""
    with get_db_connection() as conn:
        conn.execute('''
        UPDATE server_config 
        SET endpoint = ?, subnet = ?, dns_servers = ?, mtu = ?, keepalive = ?, last_updated = CURRENT_TIMESTAMP
        WHERE id = 1
        ''', (endpoint, subnet, dns_servers, mtu, keepalive))
        conn.commit()

def get_traffic_stats():
    """Get traffic statistics"""
    with get_db_connection() as conn:
        # Total monthly traffic
        monthly_traffic = conn.execute('''
        SELECT SUM(upload) + SUM(download) as total 
        FROM traffic_logs 
        WHERE timestamp >= date('now', 'start of month')
        ''').fetchone()
        
        # Client count stats
        counts = conn.execute('''
        SELECT 
            COUNT(*) as total_clients,
            SUM(CASE WHEN is_active = 1 AND (expiry_date IS NULL OR expiry_date > CURRENT_TIMESTAMP) THEN 1 ELSE 0 END) as active_clients
        FROM clients
        ''').fetchone()
        
        return {
            'monthly_traffic_bytes': monthly_traffic['total'] if monthly_traffic['total'] else 0,
            'total_clients': counts['total_clients'],
            'active_clients': counts['active_clients']
        }
