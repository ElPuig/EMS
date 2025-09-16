#!/bin/bash
echo "Installing the EMS (with demo data)..."
sudo service odoo stop
sudo -u odoo bash -c 'odoo -d ems --stop-after-init -i ems -c /etc/odoo/odoo.conf'
sudo service odoo start
echo "Done!"
