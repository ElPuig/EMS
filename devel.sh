#!/bin/bash
echo "Setting up the EMS for a developement environment:"

echo "Stopping the Odoo service..."
sudo service odoo stop

read -p "Do you want to cancel all pending emails and jobs? [Y/n]: " answer
if [[ -z "$answer" || "$answer" =~ ^[Yy]$ ]]; then
    sudo -u odoo bash -c "psql -d ems -c \"UPDATE queue_job SET state='cancelled' WHERE state IN ('started', 'enqueued', 'pending');\""
fi

read -p "Do you want to replace all the email addresses? [Y/n]: " answer
if [[ -z "$answer" || "$answer" =~ ^[Yy]$ ]]; then
    read -p "Please, write the email to replace with [example@domain.com]: " email
    email=${email:-example@domain.com}

    sudo -u odoo bash -c "psql -d ems -c \"UPDATE res_partner SET email='${email}' WHERE email IS NOT NULL;\""
    sudo -u odoo bash -c "psql -d ems -c \"UPDATE res_partner SET email_normalized='${email}' WHERE email_normalized IS NOT NULL;\""
    sudo -u odoo bash -c "psql -d ems -c \"UPDATE res_partner SET student_email='${email}' WHERE student_email IS NOT NULL;\""
fi

echo "Starting the Odoo service..."
sudo service odoo start
