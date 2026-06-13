#!/bin/bash
set -e

cd /root/myModules/ems
echo ">> New EMS release detected: starting deployment for $1"
./update.sh
./upgrade.sh
echo ">> Deployment completed for $1"
