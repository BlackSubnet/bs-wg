from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
import os
import io
import json
import datetime
import subprocess
from database import cleanup_old_traffic_logs, aggregate_traffic_data
from wireguard import get_client_status
from database import (
    init_db, get_db_connection, add_client, get_client, get_all_clients, 
    get_active_clients, update_client, delete_client, update_client_status,
    find_available_ip, update_data_usage, get_server_config, update_server_config,
    get_traffic_stats
)
from wireguard import (
    generate_keypair, generate_preshared_key, restart_wireguard, apply_server_config,
    generate_client_config, generate_qr_code, add_client_to_wireguard,
    remove_client_from_wireguard, get_client_status
)
from utils import format_bytes, format_timestamp, get_server_stats
# from config import SECRET_KEY, DEBUG, DATABASE_PATH
from config import (
    SECRET_KEY, DEBUG, DATABASE_PATH, 
    WG_INTERFACE, PUBLIC_IP, WG_PORT, ADMIN_PASSWORD
)
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
from apscheduler.schedulers.background import BackgroundScheduler
from functools import wraps
from flask import session, redirect, url_for

# Initialize database using an app context instead of before_first_request
def initialize_database():
    with app.app_context():
        init_db()

# Call the initialize function
initialize_database()

ADMIN_PASSWORD = ADMIN_PASSWORD # Change this!
SECRET_KEY = SECRET_KEY  # Change this!




#login path

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['password'] == ADMIN_PASSWORD:
            session['authenticated'] = True
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid password')
    return render_template('login.html')

# Logout route
@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('login'))



# Main dashboard route
@app.route('/')
@login_required
def index():
    # Get basic stats
    traffic_stats = get_traffic_stats()
    active_clients = traffic_stats['active_clients']
    total_clients = traffic_stats['total_clients']
    monthly_traffic = format_bytes(traffic_stats['monthly_traffic_bytes'])
    
    # Get server stats
    server_stats = get_server_stats()
    
    # Format uptime for display
    uptime = server_stats['uptime']['formatted']
    
    return render_template(
        'index.html',
        active_clients=active_clients,
        total_clients=total_clients,
        monthly_traffic=monthly_traffic,
        uptime=uptime
    )



@app.route('/clients')
@login_required
def clients():  # This is the main clients page route
    all_clients = get_all_clients()
    client_status = get_client_status()
    
    # Merge client data with status
    for client in all_clients:
        status = client_status.get(client['public_key'], {})
        client['online'] = status.get('online', False)
        client['last_seen_formatted'] = format_timestamp(client['last_seen'])
        client['data_usage_formatted'] = format_bytes(client['data_usage'] * 1024 * 1024)
    
    return render_template('clients.html', clients=all_clients)


# Client management routes
@app.route('/api/clients')
@login_required
def clients_api():
    """API endpoint returning all clients with their status"""
    all_clients = get_all_clients()
    client_status = get_client_status()
    
    # Merge client data with status
    for client in all_clients:
        status = client_status.get(client['public_key'], {})
        client['online'] = status.get('online', False)
        client['last_seen_formatted'] = format_timestamp(client['last_seen'])
        client['data_usage_formatted'] = format_bytes(client['data_usage'] * 1024 * 1024)  # Convert MB to bytes
    
    return jsonify(all_clients)
@app.route('/api/available-ips')
@login_required
def available_ips_api():
    """API endpoint returning available IP addresses"""
    available_ips = []
    base_ip = '10.8.0.'
    
    with get_db_connection() as conn:
        used_ips = [row[0] for row in conn.execute('SELECT assigned_ip FROM clients').fetchall()]
    
    for i in range(2, 255):
        ip = f"{base_ip}{i}"
        if ip not in used_ips:
            available_ips.append(ip)
            if len(available_ips) >= 10:  # Limit to 10 suggestions
                break
    
    return jsonify(available_ips)


@app.route('/api/server-config')
@login_required
def server_config_api():
    """API endpoint returning server configuration"""
    config = get_server_config()
    if config:
        return jsonify(config)
    
    # Use values imported from config module
    return jsonify({
        'endpoint': f"{PUBLIC_IP}:{WG_PORT}",
        'subnet': '10.8.0.0/24',  # You might want to import this from config too
        'dns_servers': '1.1.1.1, 1.0.0.1',  # Consider importing this
        'mtu': 1420,  # Consider importing this
        'keepalive': 25  # Consider importing this
    })

@app.route('/clients/add', methods=['GET', 'POST'])
@login_required
def add_client_route():
    if request.method == 'POST':
        try:
            name = request.form['name']
            email = request.form['email'] if 'email' in request.form else None
            data_limit = int(request.form['data_limit']) if request.form['data_limit'] != 'none' else None
            expiry_date = request.form['expiry_date'] if request.form['expiry_date'] else None
            
            # Generate keys
            private_key, public_key = generate_keypair()
            preshared_key = generate_preshared_key()
            
            # Find available IP or use specified one
            if 'assigned_ip' in request.form and request.form['assigned_ip']:
                assigned_ip = request.form['assigned_ip']
            else:
                assigned_ip = find_available_ip()
                if not assigned_ip:
                    flash('No available IP addresses!', 'error')
                    return redirect(url_for('clients'))
            
            # Add to database
            client_id = add_client(
                name=name,
                email=email,
                private_key=private_key,
                public_key=public_key,
                assigned_ip=assigned_ip,
                preshared_key=preshared_key,
                data_limit=data_limit,
                expiry_date=expiry_date
            )
            
            # Add to WireGuard
            client = get_client(client_id)
            if add_client_to_wireguard(client):
                flash('Client added successfully!', 'success')
            else:
                flash('Client added to database but failed to configure WireGuard', 'warning')
            
            return redirect(url_for('client_detail', client_id=client_id))
            
        except Exception as e:
            flash(f'Error adding client: {str(e)}', 'error')
            return redirect(url_for('clients'))
    
    # For GET request
    available_ips = []
    base_ip = '10.8.0.'
    
    with get_db_connection() as conn:
        used_ips = [row[0] for row in conn.execute('SELECT assigned_ip FROM clients').fetchall()]
    
    for i in range(2, 255):
        ip = f"{base_ip}{i}"
        if ip not in used_ips:
            available_ips.append(ip)
            if len(available_ips) >= 10:  # Limit to 10 suggestions
                break
    
    return render_template('add_client.html', available_ips=available_ips)

@app.route('/clients/<int:client_id>')
@login_required
def client_detail(client_id):
    client = get_client(client_id)
    if not client:
        flash('Client not found!', 'error')
        return redirect(url_for('clients'))
    
    # Get client status from WireGuard
    client_status = get_client_status().get(client['public_key'], {})
    client['online'] = client_status.get('online', False)
    client['last_seen_formatted'] = format_timestamp(client['last_seen'])
    client['data_usage_formatted'] = format_bytes(client['data_usage'] * 1024 * 1024)
    
    # Generate client config and QR code
    server_config = get_server_config()
    client_config = generate_client_config(client, server_config)
    qr_code = generate_qr_code(client_config)
    
    return render_template(
        'client_detail.html', 
        client=client, 
        client_config=client_config, 
        qr_code=qr_code
    )

@app.route('/clients/<int:client_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_client(client_id):
    client = get_client(client_id)
    if not client:
        flash('Client not found!', 'error')
        return redirect(url_for('clients'))
    
    if request.method == 'POST':
        # Handle the POST request
        updates = {
            'name': request.form['name'],
            'email': request.form['email'],
            'data_limit': int(request.form['data_limit']) if request.form['data_limit'] != 'none' else None,
            'expiry_date': request.form['expiry_date'] if request.form['expiry_date'] else None,
            'is_active': 1 if 'is_active' in request.form else 0
        }
        
        update_client(client_id, **updates)
        flash('Client updated successfully!', 'success')
        return redirect(url_for('client_detail', client_id=client_id))
    
    # For GET request
    server_config = get_server_config()
    client_config = generate_client_config(client, server_config)
    qr_code = generate_qr_code(client_config)
    
    # Get activity logs (implement this function)
    activity_logs = get_client_activity_logs(client_id)
    
    return render_template('edit_client.html',
                         client=client,
                         client_config=client_config,
                         qr_code=qr_code,
                         activity_logs=activity_logs)

@app.route('/clients/<int:client_id>/delete', methods=['POST'])
@login_required
def delete_client_route(client_id):
    client = get_client(client_id)
    if not client:
        flash('Client not found!', 'error')
        return redirect(url_for('clients'))
    
    # Remove from WireGuard
    remove_client_from_wireguard(client['public_key'])
    
    # Delete from database
    delete_client(client_id)
    
    flash('Client deleted successfully!', 'success')
    return redirect(url_for('clients'))


@app.route('/logs')
@login_required
def logs():
    # Get WireGuard and system logs
    try:
        # Get last 100 lines of WireGuard logs
        wg_logs = subprocess.check_output(
            ['journalctl', '-u', f'wg-quick@{WG_INTERFACE}', '-n', '100', '--no-pager'],
            universal_newlines=True
        )
        
        # Get system logs related to WireGuard
        sys_logs = subprocess.check_output(
            ['dmesg', '|', 'grep', '-i', 'wireguard'],
            shell=True,
            universal_newlines=True
        )
    except subprocess.CalledProcessError:
        wg_logs = "Unable to retrieve WireGuard logs"
        sys_logs = "Unable to retrieve system logs"
    
    return render_template('logs.html', wg_logs=wg_logs, sys_logs=sys_logs)

@app.route('/settings')
@login_required
def settings():
    # Get current settings
    server_config = get_server_config()
    return render_template('settings.html', config=server_config)

@app.route('/clients/<int:client_id>/toggle', methods=['POST'])
@login_required
def toggle_client(client_id):
    client = get_client(client_id)
    if not client:
        return jsonify({'success': False, 'message': 'Client not found!'})
    
    new_status = request.json.get('active', False)
    update_client_status(client_id, new_status)
    
    # Update in WireGuard
    if new_status:
        add_client_to_wireguard(client)
    else:
        remove_client_from_wireguard(client['public_key'])
    
    return jsonify({'success': True})

@app.route('/clients/<int:client_id>/download')
@login_required
def download_client_config(client_id):
    client = get_client(client_id)
    if not client:
        flash('Client not found!', 'error')
        return redirect(url_for('clients'))
    
    server_config = get_server_config()
    client_config = generate_client_config(client, server_config)
    
    # Create a file-like object
    config_file = io.BytesIO(client_config.encode('utf-8'))
    
    return send_file(
        config_file,
        mimetype='text/plain',
        as_attachment=True,
        download_name=f"{client['name']}.conf"
    )

@app.route('/clients/<int:client_id>/qr')
@login_required
def client_qr_code(client_id):
    client = get_client(client_id)
    if not client:
        flash('Client not found!', 'error')
        return redirect(url_for('clients'))
    
    server_config = get_server_config()
    client_config = generate_client_config(client, server_config)
    qr_code = generate_qr_code(client_config)
    
    return jsonify({'qr_code': qr_code})

# Server configuration routes
@app.route('/server-config', methods=['GET', 'POST'])
@login_required
def server_config():
    config = get_server_config()
    
    if request.method == 'POST':
        updates = {
            'endpoint': request.form['endpoint'],
            'subnet': request.form['subnet'],
            'dns_servers': request.form['dns_servers'],
            'mtu': int(request.form['mtu']),
            'keepalive': int(request.form['keepalive'])
        }
        
        # Update in database
        update_server_config(**updates)
        
        # Apply changes to WireGuard
        config = get_server_config()  # Get updated config with keys
        apply_server_config(config)
        
        flash('Server configuration updated successfully!', 'success')
        return redirect(url_for('server_config'))
    
    return render_template('server_config.html', config=config)

# Traffic monitoring routes
@app.route('/traffic')
@login_required
def traffic():
    try:
        # Get traffic statistics
        traffic_stats = get_traffic_stats()
        
        # Get client traffic data
        with get_db_connection() as conn:
            client_traffic = conn.execute('''
                SELECT 
                    c.name,
                    c.last_seen,
                    COALESCE(SUM(t.upload), 0) as upload,
                    COALESCE(SUM(t.download), 0) as download
                FROM clients c
                LEFT JOIN traffic_logs t ON c.id = t.client_id
                WHERE t.timestamp >= date('now', '-30 days') OR t.timestamp IS NULL
                GROUP BY c.id
                ORDER BY c.name
            ''').fetchall()
        
        return render_template('traffic.html',
                             stats=traffic_stats,
                             client_traffic=client_traffic,
                             format_bytes=format_bytes,
                             format_timestamp=format_timestamp)
    except Exception as e:
        flash(f'Error loading traffic data: {str(e)}', 'error')
        return render_template('traffic.html',
                             stats={'monthly_traffic_formatted': '0 B',
                                   'total_clients': 0,
                                   'active_clients': 0},
                             client_traffic=[])

@app.route('/api/traffic/stats')
@login_required
def traffic_stats_api():
    stats = get_traffic_stats()
    stats['monthly_traffic_formatted'] = format_bytes(stats['monthly_traffic_bytes'])
    return jsonify(stats)

@app.route('/api/traffic/history')
@login_required
def traffic_history_api():
    days = int(request.args.get('days', 30))
    
    with get_db_connection() as conn:
        # Get recent detailed logs
        recent_data = conn.execute('''
        SELECT 
            date(timestamp) as date,
            SUM(upload) as upload,
            SUM(download) as download
        FROM traffic_logs
        WHERE timestamp >= date('now', '-7 days')
        GROUP BY date(timestamp)
        ''').fetchall()
        
        # Get aggregated historical data
        historical_data = conn.execute('''
        SELECT 
            date,
            SUM(total_upload) as upload,
            SUM(total_download) as download
        FROM traffic_logs_daily
        WHERE date >= date('now', ?)
        AND date < date('now', '-7 days')
        GROUP BY date
        ORDER BY date
        ''', (f'-{days} days',)).fetchall()
        
        # Combine the data
        traffic_data = historical_data + recent_data
        
        result = []
        for row in traffic_data:
            result.append({
                'date': row['date'],
                'upload': row['upload'],
                'download': row['download'],
                'upload_formatted': format_bytes(row['upload']),
                'download_formatted': format_bytes(row['download'])
            })
    
    return jsonify(sorted(result, key=lambda x: x['date']))


@app.route('/api/traffic/clients')
@login_required
def client_traffic_api():
    with get_db_connection() as conn:
        client_traffic = conn.execute('''
        SELECT 
            c.id,
            c.name,
            c.assigned_ip,
            SUM(t.upload) as upload,
            SUM(t.download) as download
        FROM clients c
        LEFT JOIN traffic_logs t ON c.id = t.client_id
        WHERE t.timestamp >= date('now', '-30 days') OR t.timestamp IS NULL
        GROUP BY c.id
        ORDER BY (SUM(t.upload) + SUM(t.download)) DESC
        ''').fetchall()
    
    result = []
    for row in client_traffic:
        upload = row['upload'] if row['upload'] else 0
        download = row['download'] if row['download'] else 0
        
        result.append({
            'id': row['id'],
            'name': row['name'],
            'ip': row['assigned_ip'],
            'upload': upload,
            'download': download,
            'upload_formatted': format_bytes(upload),
            'download_formatted': format_bytes(download),
            'total_formatted': format_bytes(upload + download)
        })
    
    return jsonify(result)

# System status route
@app.route('/api/system-status')
@login_required
def system_status_api():
    stats = get_server_stats()
    return jsonify(stats)

# Logs page
# @app.route('/logs')
# def logs():
#     # Get WireGuard logs
#     try:
#         journal_logs = subprocess.check_output([
#             'journalctl', '-u', f'wg-quick@{WG_INTERFACE}', '-n', '100', '--no-pager'
#         ]).decode('utf-8')
#     except:
#         journal_logs = "Unable to retrieve logs"
    
#     return render_template('logs.html', logs=journal_logs)

# # Settings page
# @app.route('/settings')
# def settings():
#     return render_template('settings.html')

# Dynamic API endpoints for real-time data
@app.route('/api/dashboard-stats')
@login_required
def dashboard_stats_api():
    traffic_stats = get_traffic_stats()
    server_stats = get_server_stats()
    client_status = get_client_status()
    
    # Count online clients
    online_count = sum(1 for status in client_status.values() if status.get('online', False))
    
    return jsonify({
        'active_clients': traffic_stats['active_clients'],
        'online_clients': online_count,
        'total_clients': traffic_stats['total_clients'],
        'monthly_traffic': format_bytes(traffic_stats['monthly_traffic_bytes']),
        'load': server_stats['load'],
        'memory': {
            'used': format_bytes(server_stats['memory']['used']),
            'total': format_bytes(server_stats['memory']['total']),
            'percentage': server_stats['memory']['percentage']
        },
        'disk': {
            'used': format_bytes(server_stats['disk']['used']),
            'total': format_bytes(server_stats['disk']['total']),
            'percentage': server_stats['disk']['percentage']
        },
        'uptime': server_stats['uptime']['formatted']
    })

@app.route('/api/backup')
@login_required
def backup_config():
    try:
        with get_db_connection() as conn:
            # Get server config
            server_config = dict(conn.execute('SELECT * FROM server_config').fetchone())
            # Get clients
            clients = [dict(row) for row in conn.execute('SELECT * FROM clients').fetchall()]
            
            backup = {
                'server_config': server_config,
                'clients': clients,
                'timestamp': datetime.datetime.now().isoformat()
            }
            
            return jsonify(backup)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/restore', methods=['POST'])
@login_required
def restore_config():
    try:
        backup = request.json
        
        with get_db_connection() as conn:
            # Restore server config
            conn.execute('DELETE FROM server_config')
            conn.execute('''
                INSERT INTO server_config (endpoint, subnet, dns_servers, mtu, keepalive, private_key, public_key)
                VALUES (:endpoint, :subnet, :dns_servers, :mtu, :keepalive, :private_key, :public_key)
            ''', backup['server_config'])
            
            # Restore clients
            conn.execute('DELETE FROM clients')
            for client in backup['clients']:
                conn.execute('''
                    INSERT INTO clients (name, email, private_key, public_key, preshared_key, assigned_ip, 
                                       created_at, last_seen, is_active, data_limit, data_usage, expiry_date)
                    VALUES (:name, :email, :private_key, :public_key, :preshared_key, :assigned_ip,
                            :created_at, :last_seen, :is_active, :data_limit, :data_usage, :expiry_date)
                ''', client)
            
            conn.commit()
        
        # Restart WireGuard with new config
        apply_server_config(backup['server_config'])
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500





@app.route('/api/reset', methods=['POST'])
@login_required
def reset_server():
    try:
        # Initialize new server configuration
        init_db()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear-logs', methods=['POST'])
@login_required
def clear_logs():
    try:
        with get_db_connection() as conn:
            conn.execute('DELETE FROM traffic_logs')
            conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def setup_scheduled_tasks():
    """Setup scheduled maintenance tasks"""
    scheduler = BackgroundScheduler()
    
    # Update client status every minute
    scheduler.add_job(get_client_status, 'interval', minutes=1)
    
    # Aggregate traffic data daily
    scheduler.add_job(aggregate_traffic_data, 'cron', hour=0, minute=5)
    
    # Clean up old traffic logs weekly
    scheduler.add_job(
        cleanup_old_traffic_logs, 
        'cron', 
        day_of_week='sun', 
        hour=1, 
        minute=0,
        args=[30]  # Keep 30 days of detailed logs
    )
    
    scheduler.start()

if __name__ == '__main__':
    setup_scheduled_tasks()
    app.run(debug=True, host='0.0.0.0')
