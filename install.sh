#!/bin/bash
echo "Installing the EMS..."
sudo service odoo stop
sudo -u odoo bash -c 'odoo -d ems --stop-after-init -i ems -c /etc/odoo/odoo.conf --without-demo=WITHOUT_DEMO'
sudo service odoo start
echo "Done!"