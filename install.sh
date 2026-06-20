#!/bin/bash
echo "Installing the EMS..."
sudo service odoo stop || true
sudo -u odoo bash -c 'odoo -d ems --stop-after-init -i ems -c /etc/odoo/odoo.conf --without-demo=WITHOUT_DEMO'
EXIT_CODE=$?
sudo service odoo start || true
echo "Done!"
exit $EXIT_CODE
