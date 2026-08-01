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
read -p "Please, write your Google account (the part before the @): " google_account
while [[ -z "$google_account" ]]; do
    read -p "A Google account is required. Please, write your Google account (the part before the @): " google_account
done

echo ">> Replacing every real email with ${google_account}+<original_user>@<original_domain>, so test emails reach your inbox while still showing the original recipient..."
sudo -u odoo bash -c "psql -d ems -c \"UPDATE res_partner SET email = '${google_account}+' || split_part(email, '@', 1) || '@' || split_part(email, '@', 2) WHERE email IS NOT NULL AND email NOT LIKE '${google_account}+%';\""
sudo -u odoo bash -c "psql -d ems -c \"UPDATE res_partner SET email_normalized = lower('${google_account}+' || split_part(email_normalized, '@', 1) || '@' || split_part(email_normalized, '@', 2)) WHERE email_normalized IS NOT NULL AND email_normalized NOT LIKE '${google_account}+%';\""
sudo -u odoo bash -c "psql -d ems -c \"UPDATE res_partner SET student_email = '${google_account}+' || split_part(student_email, '@', 1) || '@' || split_part(student_email, '@', 2) WHERE student_email IS NOT NULL AND student_email NOT LIKE '${google_account}+%';\""
echo "<< Email addresses replaced."

echo ">> Refreshing hr.employee.work_email (a stored compute of work_contact_id.email that a raw SQL update on res_partner does not recompute):"
sudo -u odoo bash -c "psql -d ems -c \"UPDATE hr_employee SET work_email = rp.email FROM res_partner rp WHERE rp.id = hr_employee.work_contact_id AND rp.email IS NOT NULL AND hr_employee.work_email IS DISTINCT FROM rp.email;\""
echo "<< hr.employee.work_email refreshed."

echo ">> Starting the Odoo service..."
sudo service odoo start
echo "<< Odoo service started."