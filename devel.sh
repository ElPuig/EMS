#!/bin/bash
echo "Setting up the EMS for a developement environment:"

echo ">> Stopping the Odoo service:"
sudo service odoo stop
echo "<< Odoo service stopped."

echo ">> Checking debugpy availability:"
if ! python3 -c "import debugpy" 2>/dev/null; then
    echo "debugpy not found for /usr/bin/python3, installing via apt..."
    sudo apt-get install -y python3-debugpy
fi

echo ">> Enabling the debugger on Odoo startup:"
sudo sed -i 's@ExecStart=/usr/bin/odoo --config /etc/odoo/odoo.conf --logfile /var/log/odoo/odoo-server.log@ExecStart=/usr/bin/python3 -m debugpy --listen 0.0.0.0:5678 /usr/bin/odoo --config /etc/odoo/odoo.conf --logfile /var/log/odoo/odoo-server.log@' /lib/systemd/system/odoo.service
sudo systemctl daemon-reload
echo "<< Debugger enabled."

echo ">> Cancelling all pending emails and jobs:"
sudo -u odoo bash -c "psql -d ems -c \"UPDATE queue_job SET state='cancelled' WHERE state IN ('started', 'enqueued', 'pending');\""
echo "<< Jobs canelled."

echo "Replacing all real email addresses is mandatory in this development environment, to avoid accidentally sending emails to real people."
google_account="$1"
if [[ -z "$google_account" ]]; then
    read -p "Please, write your Google account (the part before the @): " google_account
    while [[ -z "$google_account" ]]; do
        read -p "A Google account is required. Please, write your Google account (the part before the @): " google_account
    done
fi

# The domain every replaced email lands on always gets overwritten with this one, regardless of
# the original domain - keeping the original domain (as an earlier version of this script did)
# only actually reaches the developer's own inbox when that original domain happens to be one
# they personally control (e.g. this centre's own Google Workspace domain) - a family/student
# email on gmail.com, hotmail.com, etc. would not. EMS's own 'google_ws_domain' setting (the same
# one the Google Workspace integration uses to build corporate emails) is offered as the default.
domain="$2"
if [[ -z "$domain" ]]; then
    default_domain=$(sudo -u odoo psql -d ems -t -c "SELECT google_ws_domain FROM res_company LIMIT 1;" | tr -d ' \n')
    read -p "Domain to redirect every replaced email to [${default_domain}]: " domain
    domain="${domain:-$default_domain}"
    while [[ -z "$domain" ]]; do
        read -p "A domain is required. Domain to redirect every replaced email to [${default_domain}]: " domain
        domain="${domain:-$default_domain}"
    done
fi

echo ">> Replacing every real email with ${google_account}+<original_email, '@' encoded as '_at_'>@${domain}, so test emails reach your inbox regardless of the original domain, while still showing the original recipient..."
sudo -u odoo bash -c "psql -d ems -c \"UPDATE res_partner SET email = '${google_account}+' || replace(email, '@', '_at_') || '@${domain}' WHERE email IS NOT NULL AND email NOT LIKE '${google_account}+%';\""
sudo -u odoo bash -c "psql -d ems -c \"UPDATE res_partner SET email_normalized = lower('${google_account}+' || replace(email_normalized, '@', '_at_') || '@${domain}') WHERE email_normalized IS NOT NULL AND email_normalized NOT LIKE '${google_account}+%';\""
sudo -u odoo bash -c "psql -d ems -c \"UPDATE res_partner SET student_email = '${google_account}+' || replace(student_email, '@', '_at_') || '@${domain}' WHERE student_email IS NOT NULL AND student_email NOT LIKE '${google_account}+%';\""
echo "<< Email addresses replaced."

echo ">> Refreshing hr.employee.work_email (a stored compute of work_contact_id.email that a raw SQL update on res_partner does not recompute):"
sudo -u odoo bash -c "psql -d ems -c \"UPDATE hr_employee SET work_email = rp.email FROM res_partner rp WHERE rp.id = hr_employee.work_contact_id AND rp.email IS NOT NULL AND hr_employee.work_email IS DISTINCT FROM rp.email;\""
echo "<< hr.employee.work_email refreshed."

echo ">> Declaring this environment as 'dev' (see CLAUDE.md's 'Development vs. production environment declaration'):"
sudo -u odoo bash -c "psql -d ems -c \"INSERT INTO ir_config_parameter (key, value) VALUES ('ems.environment_type', 'dev') ON CONFLICT (key) DO UPDATE SET value = 'dev';\""
echo "<< Declared."

echo ">> Starting the Odoo service..."
sudo service odoo start
echo "<< Odoo service started."