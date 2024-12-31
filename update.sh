#!/bin/bash
echo "Updating the EMS..."
sudo service odoo stop
sudo -u odoo bash -c 'odoo -d ems -u ems --stop-after-init -c /etc/odoo/odoo.conf --dev=all'
sudo service odoo start
