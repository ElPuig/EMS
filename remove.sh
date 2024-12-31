#!/bin/bash
echo "Removing the EMS..."
sudo service odoo stop
sudo -u odoo bash -c 'dropdb ems'
sudo service odoo start
echo "Done!"
