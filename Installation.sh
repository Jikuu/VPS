sudo apt update && sudo apt upgrade -y

sudo apt full-upgrade -y

sudo apt autoremove -y
sudo apt clean

sudo apt install mariadb-server screen python3-mysqldb -y

sudo sed -i 's/^bind-address\s*=.*/bind-address = 0.0.0.0/' /etc/mysql/mariadb.conf.d/50-server.cnf
sudo systemctl restart mariadb

sudo mysql_secure_installation








###############

cd ~

mkdir wurm
cd wurm
wget http://86.20.72.184/wurm_scraper.py

mkdir data
cd data
wget http://86.20.72.184/wurm_all_wurm.sql
wget http://86.20.72.184/wurm_deeds.sql
wget http://86.20.72.184/wurm_wurm_scrape.sql

sudo mysql

###############

CREATE database wurm;

CREATE USER 'wurm'@'localhost' IDENTIFIED BY 'Wurming1!';
GRANT ALL PRIVILEGES ON wurm.* TO 'wurm'@'localhost';
CREATE USER 'wurm'@'%' IDENTIFIED BY 'Wurming1!';
GRANT ALL PRIVILEGES ON wurm.* TO 'wurm'@'%';
FLUSH PRIVILEGES;

USE wurm;

source wurm_all_wurm.sql
source wurm_deeds.sql
source wurm_wurm_scrape.sql

exit

################

cd ..

