#!/bin/bash
# setup_webserver.sh
# Sets up Apache, PHP, and MySQLi on Ubuntu 24.04 with basic hardening
# No HTTPS!

set -e

echo "=== Updating system ==="
sudo apt update -y && sudo apt upgrade -y

echo "=== Installing Apache, PHP, and required modules ==="
sudo apt install -y apache2 php libapache2-mod-php php-mysqli php-cli php-curl php-xml php-mbstring ufw fail2ban unattended-upgrades

echo "=== Enabling Apache modules ==="
sudo a2enmod rewrite headers ssl

echo "=== Setting up firewall ==="
sudo ufw allow OpenSSH
sudo ufw allow 'Apache Full'
sudo ufw --force enable

echo "=== Securing Apache configuration ==="

# Backup default config
sudo cp /etc/apache2/conf-available/security.conf /etc/apache2/conf-available/security.conf.bak

sudo tee /etc/apache2/conf-available/security.conf > /dev/null <<'EOF'
ServerTokens Prod
ServerSignature Off
TraceEnable Off
FileETag None
Header always unset X-Powered-By
Header always unset X-CF-Powered-By
Header always unset X-AspNet-Version
EOF

echo "=== Setting up default secure Virtual Host ==="

sudo tee /etc/apache2/sites-available/000-default.conf > /dev/null <<'EOF'
<VirtualHost *:80>
    ServerAdmin webmaster@localhost
    DocumentRoot /var/www/html
    <Directory /var/www/html>
        Options -Indexes +FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    ErrorLog ${APACHE_LOG_DIR}/error.log
    CustomLog ${APACHE_LOG_DIR}/access.log combined
</VirtualHost>
EOF

echo "=== Hardening PHP configuration ==="

PHPINI=$(php -r "echo php_ini_loaded_file();")

sudo cp "$PHPINI" "${PHPINI}.bak"

sudo sed -i 's/^expose_php = On/expose_php = Off/' "$PHPINI"
sudo sed -i 's/^display_errors = On/display_errors = Off/' "$PHPINI"
sudo sed -i 's/^;cgi.fix_pathinfo=1/cgi.fix_pathinfo=0/' "$PHPINI"
sudo sed -i 's/^upload_max_filesize.*/upload_max_filesize = 10M/' "$PHPINI"
sudo sed -i 's/^post_max_size.*/post_max_size = 10M/' "$PHPINI"

echo "=== Enabling automatic security updates ==="
sudo dpkg-reconfigure -plow unattended-upgrades

echo "=== Restarting Apache ==="
sudo systemctl restart apache2
sudo systemctl enable apache2

echo "=== System hardening: disabling root login via SSH (optional) ==="
sudo sed -i 's/^PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart ssh

echo "=== Installing Fail2Ban for brute-force protection ==="
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

echo "=== Testing PHP setup ==="
echo "<?php phpinfo(); ?>" | sudo tee /var/www/html/info.php > /dev/null

echo "=== Setup complete ==="
echo "You can test your server at: http://$(hostname -I | awk '{print $1}')/info.php"
