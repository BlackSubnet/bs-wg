# 🌐 BlackSubnet WireGuard Panel (bs-wg)

<div align="center">
  <img src="https://i.ibb.co/GvmXK9rk/photo-2025-02-05-00-42-17.jpg" alt="BlackSubnet WireGuard Panel Logo" width="150">
  
  **Modern, Powerful & User-Friendly WireGuard VPN Management**
  
  [![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
  [![Python 3.9+](https://img.shields.io/badge/Python-3.9+-green.svg)](https://www.python.org/downloads/)
  [![WireGuard](https://img.shields.io/badge/WireGuard-Compatible-orange.svg)](https://www.wireguard.com/)
</div>

## ✨ Overview

Welcome to **bs-wg**, a powerful and elegant WireGuard VPN management panel developed by BlackSubnet. This tool transforms the complexity of VPN management into a seamless experience, offering an intuitive interface for administrators and users alike. Whether you're securing your network, managing remote access, or deploying VPNs at scale, bs-wg delivers simplicity without compromising on features.

## 🚀 Features

- **🔄 Effortless WireGuard Management** — Create, edit, and delete WireGuard peers with just a few clicks
- **🖥️ Sleek Web Interface** — Manage your VPN server from any browser, no command-line needed
- **🔐 Robust Authentication** — Secure access with comprehensive user management
- **📊 Live Monitoring** — Track connections and performance in real-time
- **💻 Cross-Platform** — Compatible with all Linux-based systems running WireGuard
- **⚙️ Highly Customizable** — Fine-tune every aspect of your VPN configuration
- **📈 Enterprise Ready** — Scales from personal use to large organizational deployments

## 📸 Screenshots

<div align="center">
  <table>
    <tr>
      <td align="center">
        <img src="https://i.ibb.co/219CmSjR/photo-2025-03-03-21-46-20.jpg" alt="Dashboard" width="100%">
        <br><strong>Dashboard Overview</strong>
        <br><em>Complete visibility into your VPN operations</em>
      </td>
    </tr>
    <tr>
      <td align="center">
        <img src="https://i.ibb.co/XNG68Kv/photo-2025-03-03-21-46-55.jpg" alt="Peer Management" width="100%">
        <br><strong>Peer Management</strong>
        <br><em>Intuitive peer configuration and control</em>
      </td>
    </tr>
    <tr>
      <td align="center">
        <img src="https://i.ibb.co/ymbXGq1Z/photo-2025-03-03-21-46-27.jpg" alt="Traffic Monitor" width="100%">
        <br><strong>Traffic Monitoring</strong>
        <br><em>Visualize network activity in real-time</em>
      </td>
    </tr>
  </table>
</div>

## 🛠️ Installation

### Prerequisites
- Linux server (Ubuntu LTS recommended)
- WireGuard installed (wg and wg-quick)
- Root or sudo privileges
- Python 3.9+
- Git

### Quick Setup Guide

#### 1️⃣ Clone the Repository
```bash
git clone https://github.com/BlackSubnet/bs-wg.git
cd bs-wg
```

#### 2️⃣ Install Dependencies
```bash
sudo apt update
sudo apt install wireguard python3-pip
pip3 install -r requirements.txt
```

#### 3️⃣ Configure the Panel
Edit `config.py` with your server details:
```python
PUBLIC_IP = "YOUR_SERVER_IP"  # Replace with your actual public IP
SECRET_KEY = 'your-secret-key-here'
ADMIN_PASSWORD = "PASSWORD"  # Change this to a secure random value
```

#### 4️⃣ Set Up WireGuard
```bash
python3 setup_wireguard.py
```

#### 5️⃣ Launch the Application
```bash
python3 app.py
```
> 💡 **Pro Tip:** For production environments, set up as a systemd service for reliability.

#### 6️⃣ Access Your Panel
Open your browser and navigate to:
```
http://your-server-ip:5000
```

## 📝 Usage Guide

### Getting Started

1. **Login** — Use your configured credentials (change default password immediately)
2. **Create Peers** — Navigate to "Peers" → "Add Peer" → Configure and download client config
3. **Monitor** — View active connections and performance metrics on the dashboard
4. **Configure** — Fine-tune WireGuard settings through the intuitive configuration editor

## 👥 Contributing

We welcome contributions from the community! Here's how to get started:

1. Fork the repository
2. Create your feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add some amazing feature'`
4. Push to the branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

## 📜 License

This project is licensed under the [MIT License](LICENSE) - see the LICENSE file for details.

## 📬 Contact & Support

<div align="center">
  
  Need help? Have questions? Get in touch with the BlackSubnet team:
  This project is still under development and there might be bugs.
  
  📧 **Email:** [support@blacksubnet.vip](mailto:support@blacksubnet.vip)  
  🐛 **Issues:** [Report on GitHub](https://github.com/BlackSubnet/bs-wg/issues)  
  🌐 **Website:** [blacksubnet.vip](https://blacksubnet.vip)
</div>

---

<div align="center">
  <b>Built with ❤️ by BlackSubnet</b><br>
  <i>Secure your network with confidence</i>
</div>
