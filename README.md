# EMS
**Currently under development, do not apply under production environments if you're not an Odoo developer.**
## What is it, and who we are
The aim of the EMS (Educational Management System) is to provide an open-source, cost free and intuitive environment in order to manage an educational center in the most comprehensive way as possible.

This implementation is performed over Odoo Community Edition (an open-source and cost free fully configurable ERP) and some of its OCA's (Odoo Community Association) modules, and it's being directed and developed by a group of VET IT teachers from the Puig Castellar Institute (Santa Coloma de Gramenet, Barcelona, Spain).

You can check the *wiki* for more information: https://github.com/ElPuig/EMS/wiki

# Installation
We have some scripts prepared but are just for development, so we still don't have anything ready to automatically install everything running a single file, but we will do in a near future.

## Environment
We have developed and tested the EMS just over Ubuntu 24.04 LTS and derivates (like Linux Mint 22.x) but it should work fine whatever Odoo v18 supports officially. But, because we are an open-source community, we recommend to use Linux distributions (native, virtualized or within a container) so you can run our automated shell-scripts (if you're running on Windows, check out the WSL).

## Odoo install
You can follow the [official Odoo instructions](https://docs.advanceinsight.dev/administration/on_premise/packages.html)  or, if you're cool as us and running on Ubuntu (desktop or server), just run the following commands:
```
sudo su
apt update && apt upgrade -y
apt install wget git nano gpg -y

wget -q -O - https://nightly.odoo.com/odoo.key | sudo gpg --dearmor -o /usr/share/keyrings/odoo-archive-keyring.gpg

echo 'deb [signed-by=/usr/share/keyrings/odoo-archive-keyring.gpg] https://nightly.odoo.com/18.0/nightly/deb/ ./' | sudo tee /etc/apt/sources.list.d/odoo.list

apt update && apt install odoo xfonts-base fontconfig -y

wget http://es.archive.ubuntu.com/ubuntu/pool/universe/x/xfonts-75dpi/xfonts-75dpi_1.0.4+nmu1.1_all.deb -O xfonts-75dpi.deb
sudo dpkg -i xfonts-75dpi.deb
rm xfonts-75dpi.deb

wget http://launchpadlibrarian.net/668074287/libssl1.1_1.1.1f-1ubuntu2.19_amd64.deb -O libssl1.1.deb
sudo dpkg -i libssl1.1.deb
rm libssl1.1.deb

wget https://github.com/wkhtmltopdf/wkhtmltopdf/releases/download/0.12.5/wkhtmltox_0.12.5-1.focal_amd64.deb -O wkhtmltox_0.12.5.deb
sudo dpkg -i wkhtmltox_0.12.5.deb
rm wkhtmltox_0.12.5.deb
```

After that, open a browser and go to the IP of the machine using the 8069 port (for example: https://10.0.1.29:8069). You should see your Odoo server working. 

## EMS (download and setup)
### Common
Run the following commands:
```
mkdir myModules
sudo nano /etc/odoo/odoo.conf
```

Edit the following lines or add them if does not exist:
```
addons_path = /usr/lib/python3/dist-packages/odoo/addons, /root/myModules, /root/myModules/queue, /root/myModules/partner-contact

server_wide_modules = web,queue_job
```
Save the changes and close the file (CTRL+O; CTRL+X), then continue with the following commands:
```
sudo adduser root odoo
sudo chown root:odoo /root
sudo chmod 750 /root

cd /root
sudo chown -R root:odoo myModules
sudo chmod g+s myModules

apt install pip -y
apt install python3-lxml python3-lxml-html-clean python3-phonenumbers -y

cd myModules
git clone https://github.com/ElPuig/EMS.git ems
git clone -b 18.0 https://github.com/OCA/queue.git queue
git clone -b 18.0 https://github.com/OCA/partner-contact.git partner-contact
cd ems

python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

```

Copy the generated secret key and use it to setup the odoo configuration file as follows:
```
sudo nano /etc/odoo/odoo.conf
```

Add the following line to the end of the file:
```
secret = PASTE_HERE_THE_SECRET_KEY

```
Save the changes and close the file (CTRL+O; CTRL+X).

### Only under production environments
Enable multithreading to improve performance:
```
sudo nano /etc/odoo/odoo.conf
```

Add the following lines at the end of the file:
```
workers = 2
max-cron-threads = 2
```
Save the changes and close the file (CTRL+O; CTRL+X).

### Only under development environments
Enable the debugger and disable timeouts:
```
apt install python3-debugpy -y
sudo nano /etc/odoo/odoo.conf
```
Add the following lines at the end of the file:
```
limit_time_cpu = 0
limit_time_real = 0
```
Save the changes and close the file (CTRL+O; CTRL+X).  

Also, the debugger must run with Odoo:
```
nano  /lib/systemd/system/odoo.service
```

Change the '_ExecStart_' line with the following:
```
ExecStart=/usr/bin/python3 -m debugpy --listen 0.0.0.0:5678 /usr/bin/odoo --config /etc/odoo/odoo.conf --logfile /var/log/odoo/odoo-server.log
```
Save the changes and close the file (CTRL+O; CTRL+X).  

Finally, in order to run the tests (front and back):
```
pip install websocket-client

curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg 

echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list 

apt update 
apt install -y google-chrome-stable
```

## EMS (install and update)
First of all, check the `data` folder and fit it to your needs. You'll find the following folders:
- **cat**: contains the data about the Catalonian Educational System. If you're setting up the EMS in a Catalan school, this should fit your needs; otherwise, you can use it as a template (but please, share with us your setup).

- **custom**: contains custom data for a concrete institution, so here you'll find our data. Feel free to change whatever in order to fit it to your needs.

- **main**: contains basic data that should be fine for all EMS users. Because we are in an early development stage, the data within `main` could be not perfectly selected (please, share with us all your concerns and needs).  

Also, verify the `__manifest__.py` file in order to add or remove files. 

### First install
If you want to install the EMS with demo data, just run 
```
./demo.sh
```
**Warning**: demo data could be outdated, due development priorities; request us all the demo data that you need.

Otherwise, if you don't want any demo data, run:
```
./install.sh
```

### Upgrade
If the EMS is already installed and you want to upgrade it to the last version, just run:
```
./update.sh && ./upgrade.sh
```

### Development only
If you're an EMS developer, first of all: THANK YOU! Also, you can run the following script to fix the debugger after an Odoo update, and also perform additional operations (like changing the customer's emails, disabling the pending tasks, etc.).
```
./devel.sh
```

# DISCLAIMER: A note on AI-assisted development

We want to be fully transparent: we are a group of VET IT teachers who built this project entirely in our spare time which means evenings, weekends, and whatever gaps we could find between classes. Our motivation is simple: public schools face a chronic shortage of good, affordable educational management tools, and we wanted to do something about it.

Everything we use and produce is open-source. We believe in free software, and we want to give back to the community as much as we can.

That said, we have to be honest: parts of this project were developed with the assistance of [Claude Code](https://claude.ai/code), an AI coding tool by Anthropic. We would have preferred to build everything without it (as it was since we started at year 2022) because we value human craftsmanship and wanted this to be fully ours. However, the reality is that without AI assistance, we simply could not have delivered a working system within the time constraints we faced to meet our school's needs.

We are not proud of needing a shortcut, but we are proud of what we built and why we built it. We discussed, designed, analyzed and tested every line of code in this repository with all our love, and we assume every mistake as humans we are.

Please don't hate us. 🙏

# DISCLAIMER: No Warranty & Limitation of Liability

THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, TITLE, AND NON-INFRINGEMENT. THE AUTHORS AND CONTRIBUTORS MAKE NO REPRESENTATIONS OR WARRANTIES OF ANY KIND CONCERNING THE SAFETY, SUITABILITY, LACK OF VIRUSES, INACCURACIES, TYPOGRAPHICAL ERRORS, OR OTHER HARMFUL COMPONENTS OF THIS SOFTWARE.

**USE THIS SOFTWARE AT YOUR OWN RISK.**

IN NO EVENT SHALL THE AUTHORS, CONTRIBUTORS, OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY — WHETHER IN AN ACTION OF CONTRACT, TORT, OR OTHERWISE — ARISING FROM, OUT OF, OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE. THIS INCLUDES, WITHOUT LIMITATION:

- Loss, corruption, or destruction of data.
- System failures, service interruptions, or downtime.
- Loss of business, revenue, profits, or goodwill.
- Any indirect, incidental, special, exemplary, or consequential damages of any kind.

**DATA RESPONSIBILITY & BACKUPS**

You are solely and exclusively responsible for maintaining up-to-date backups of all your data before installing, upgrading, configuring, or using this software in any way. The authors provide no backup mechanism and assume no responsibility whatsoever for any data loss resulting from the use, misuse, inability to use, or failure of this software.

Do not use this software in a production environment without a tested and verified backup and recovery strategy in place.

**ACCEPTANCE OF TERMS**

By downloading, installing, configuring, or using this software in any way, you acknowledge that you have read, understood, and agreed to the terms of this disclaimer. If you do not agree with these terms, do not use this software.

