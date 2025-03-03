# BlackSubnet WireGuard Panel (bs-wg)
<img src="https://i.ibb.co/GvmXK9rk/photo-2025-02-05-00-42-17.jpg" alt="BlackSubnet WireGuard Panel Logo" width="100" height="100">


Welcome to bs-wg, a powerful and user-friendly WireGuard VPN management panel developed by BlackSubnet. This tool simplifies the setup, configuration, and management of WireGuard VPN servers, offering an intuitive interface for administrators and users alike. Whether you're securing your network, managing remote access, or deploying VPNs at scale, bs-wg has you covered.

## Table of Contents

- [Features](#features)
- [Screenshots](#screenshots)
- [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Features

- Easy WireGuard Management: Seamlessly create, edit, and delete WireGuard peers and configurations.
- Web-Based Interface: Manage your VPN server from any browser without complex command-line interactions.
- User Authentication: Secure access with built-in user management and authentication.
- Real-Time Monitoring: Track VPN connection statuses and performance metrics.
- Cross-Platform Support: Compatible with Linux-based systems running WireGuard.
- Customizable Settings: Fine-tune VPN configurations to suit your needs.
- Scalable Design: Ideal for small setups or large-scale deployments.

## Screenshots

### Dashboard Overview
![Dashboard Screenshot](https://i.ibb.co/219CmSjR/photo-2025-03-03-21-46-20.jpg)
View real-time stats and manage your VPN with ease.

### Peer Management
![Peer Management](https://i.ibb.co/XNG68Kv/photo-2025-03-03-21-46-55.jpg)
Add, edit, or remove WireGuard peers effortlessly.

### Traffic Monitor
![Traffic Monitor](https://i.ibb.co/ymbXGq1Z/photo-2025-03-03-21-46-27.jpg)
Monitor your WireGuard traffic with a clean UI.

## Installation

Follow these steps to get the BlackSubnet WireGuard Panel up and running:

### Prerequisites
- A Linux server (Ubuntu LTS preffered)
- WireGuard installed (wg and wg-quick)
- Root or sudo privileges
- Python 3.9+ (if applicable, adjust based on project dependencies)
- Git

### Steps
1. Clone the Repository
   git clone https://github.com/BlackSubnet/bs-wg.git
   cd bs-wg

2. Install Dependencies
   sudo apt update
   sudo apt install wireguard python3-pip
   pip3 install -r requirements.txt

3. Configure the Panel
   - Edit the configuration file (config.py) with your server details.
   - Example:
    PUBLIC_IP = ""  # Replace with your actual public IP
  
    SECRET_KEY = 'your-secret-key-here' 
    ADMIN_PASSWORD = "PASSWORD" # Change this to a secure random value

4. Run the Application
   python3 main.py
   - Alternatively, set it up as a systemd service for persistence.

5. Access the Panel
   - Open your browser and navigate to http://your-server-ip:5000.


## Usage

1. Log In
   - Use the default credentials (PASSWORD) or set up your own during installation.
   - Change the password immediately for security.

2. Create a Peer
   - Navigate to the "Peers" section.
   - Click "Add Peer," configure the settings, and download the client config.

3. Monitor Connections
   - Check the dashboard for active connections and logs.

4. Manage Configurations
   - Adjust WireGuard settings via the configuration editor as needed.



## Contributing

We welcome contributions from the community! To get started:

1. Fork the repository.
2. Create a new branch (git checkout -b feature/your-feature).
3. Commit your changes (git commit -m "Add your feature").
4. Push to your branch (git push origin feature/your-feature).
5. Open a Pull Request.

## License

This project is licensed under the [MIT License](LICENSE). See the LICENSE file for details.

## Contact

For support or inquiries, reach out to the BlackSubnet team:

- Email: support@blacksubnet.vip
- GitHub Issues: [Open an Issue](https://github.com/BlackSubnet/bs-wg/issues)
- Website: [blacksubnet.vip](https://blacksubnet.vip)

---
Built with love by BlackSubnet. Secure your network today!
