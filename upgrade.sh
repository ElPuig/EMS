#!/bin/bash
echo "Upgrading the EMS..."
sudo service odoo stop

# Job queue must be cleaned
# source: https://github.com/OCA/queue/tree/18.0/queue_job#known-issues-roadmap
sudo -u odoo bash -c "psql -d ems -c \"UPDATE queue_job SET state='pending' WHERE state IN ('started', 'enqueued');\""

sudo -u odoo bash -c 'odoo -d ems -u ems --i18n-overwrite --stop-after-init -c /etc/odoo/odoo.conf --dev=all'
sudo service odoo start
