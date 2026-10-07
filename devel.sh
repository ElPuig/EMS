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
# Run as the postgres superuser, before anything else touches the database: a freshly restored
# production copy may be locked against the odoo role (REVOKE CONNECT, see CLAUDE.md "Lock a
# restored production copy") and still carries production's pending work. Everything that has not
# finished is cancelled, whatever its state: queue jobs (notices, notifications...), including those
# waiting on another one, Odoo's own outgoing mail queue (its recipients are stored as plain text,
# so the address rewrite below never reaches them) and outgoing SMS.
sudo -u postgres psql -d ems -v ON_ERROR_STOP=1 \
    -c "UPDATE queue_job SET state='cancelled' WHERE state NOT IN ('done', 'cancelled', 'failed');" \
    -c "UPDATE mail_mail SET state='cancel' WHERE state IN ('outgoing', 'exception');" \
    -c "DO \$\$ BEGIN IF to_regclass('sms_sms') IS NOT NULL THEN UPDATE sms_sms SET state='canceled' WHERE state='outgoing'; END IF; END \$\$;" \
    || { echo "!! Could not cancel the pending jobs and emails: stopping here, the Odoo service stays stopped."; exit 1; }
pending=$(sudo -u postgres psql -d ems -At -c "SELECT count(*) FROM queue_job WHERE state NOT IN ('done', 'cancelled', 'failed');")
if [ "$pending" != "0" ]; then
    echo "!! ${pending} jobs are still pending: stopping here, the Odoo service stays stopped."
    exit 1
fi
# Only now may the odoo role (and the service, at the end of this script) reach the database.
sudo -u postgres psql -c "GRANT CONNECT ON DATABASE ems TO PUBLIC, odoo;"
echo "<< Jobs and emails cancelled."

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
# Email columns that live outside res_partner and are not a stored related of it: each one holds
# its own independent real address, so res_partner's rewrite above never reaches them and they
# need the exact same treatment applied directly.
sudo -u odoo bash -c "psql -d ems -c \"UPDATE ems_limesurvey_recipient SET email = '${google_account}+' || replace(email, '@', '_at_') || '@${domain}' WHERE email IS NOT NULL AND email NOT LIKE '${google_account}+%';\""
sudo -u odoo bash -c "psql -d ems -c \"UPDATE hr_employee SET private_email = '${google_account}+' || replace(private_email, '@', '_at_') || '@${domain}' WHERE private_email IS NOT NULL AND private_email NOT LIKE '${google_account}+%';\""
sudo -u odoo bash -c "psql -d ems -c \"UPDATE res_company SET secretariat_email = '${google_account}+' || replace(secretariat_email, '@', '_at_') || '@${domain}' WHERE secretariat_email IS NOT NULL AND secretariat_email NOT LIKE '${google_account}+%';\""
echo "<< Email addresses replaced."

echo ">> Refreshing the stored copies of res_partner.email (relateds/computes a raw SQL update on res_partner does not recompute):"
sudo -u odoo bash -c "psql -d ems -c \"UPDATE hr_employee SET work_email = rp.email FROM res_partner rp WHERE rp.id = hr_employee.work_contact_id AND rp.email IS NOT NULL AND hr_employee.work_email IS DISTINCT FROM rp.email;\""
sudo -u odoo bash -c "psql -d ems -c \"UPDATE res_company SET email = rp.email FROM res_partner rp WHERE rp.id = res_company.partner_id AND rp.email IS NOT NULL AND res_company.email IS DISTINCT FROM rp.email;\""
echo "<< hr.employee.work_email and res.company.email refreshed."

echo ">> Pointing the PDF renderer (report.url) at this server:"
# wkhtmltopdf loads a report's stylesheets, logo and fonts from 'report.url'. A database restored from
# production carries production's own value, http://127.0.0.1 - the reverse proxy that listens on port
# 80 in front of Odoo there. Here Odoo listens directly on its own port, so the connection is refused
# and every PDF comes out unstyled, without header or footer ("wkhtmltopdf: Exit with code 1 due to
# network error: ConnectionRefusedError" in the log).
odoo_port=$(sed -n 's/^[[:space:]]*http_port[[:space:]]*=[[:space:]]*\([0-9]*\).*/\1/p' /etc/odoo/odoo.conf | head -1)
odoo_port="${odoo_port:-8069}"
sudo -u odoo bash -c "psql -d ems -c \"INSERT INTO ir_config_parameter (key, value) VALUES ('report.url', 'http://127.0.0.1:${odoo_port}') ON CONFLICT (key) DO UPDATE SET value = 'http://127.0.0.1:${odoo_port}';\""
echo "<< PDF renderer pointed at http://127.0.0.1:${odoo_port}."

echo ">> Forcing the Google Workspace integration into dry-run mode:"
# A database restored from production carries production's live Google Workspace service account.
# The address rewrite above keeps every corporate address on the centre's own domain, so without
# dry-run any account creation (by hand, or automatic once a student/employee is complete) would
# create a real account in the centre's real Google Workspace, and suspend/rename/reset calls would
# reach it too. Dry-run only logs the payloads.
sudo -u odoo bash -c "psql -d ems -c \"UPDATE res_company SET google_ws_dry_run = TRUE;\""
echo "<< Google Workspace in dry-run mode."

echo ">> Declaring this environment as 'dev' (see CLAUDE.md's 'Development vs. production environment declaration'):"
sudo -u odoo bash -c "psql -d ems -c \"INSERT INTO ir_config_parameter (key, value) VALUES ('ems.environment_type', 'dev') ON CONFLICT (key) DO UPDATE SET value = 'dev';\""
echo "<< Declared."

echo ">> Guarding outgoing email on this machine (issue #590):"
# A development machine only ever sends to the developer's own inbox (every address redirected
# above) and to an explicit allowlist; EMS refuses anything else, and everything from a database
# that didn't go through this script (see models/settings/mail_guard.py). The allowlist is only
# seeded once: edit it in Settings > Technical > System Parameters.
sudo -u odoo bash -c "psql -d ems -c \"INSERT INTO ir_config_parameter (key, value) VALUES ('ems.dev_mail_redirect', '${google_account}@${domain}') ON CONFLICT (key) DO UPDATE SET value = '${google_account}@${domain}';\""
sudo -u odoo bash -c "psql -d ems -c \"INSERT INTO ir_config_parameter (key, value) VALUES ('ems.dev_mail_allowlist', 'ems@elpuig.xeill.net') ON CONFLICT (key) DO NOTHING;\""
# The machine itself, not just this database: a production dump restored into any other database
# on this box carries production's live mail servers and pending jobs. db_name/dbfilter keep the
# Odoo service (queue_job runner, crons, web) on 'ems' only, so such a copy stays inert, and
# ems_server_role makes EMS block its email if it is ever opened anyway. On 2026-10-06 a copy
# restored here sent 412 real notifications to students and families.
sudo sed -i '/^[[:space:]]*\(db_name\|dbfilter\|ems_server_role\)[[:space:]]*=/d' /etc/odoo/odoo.conf
sudo sed -i '/^\[options\]/a db_name = ems\ndbfilter = ^ems$\nems_server_role = dev' /etc/odoo/odoo.conf
echo "<< Email guarded: only ${google_account}+...@${domain} and the allowlist; the Odoo service only serves 'ems'."

echo ">> Starting the Odoo service..."
sudo service odoo start
echo "<< Odoo service started."