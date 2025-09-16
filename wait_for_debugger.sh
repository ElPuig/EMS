#!/bin/bash
echo "Waiting for the debugger:"
while [ $(lsof -i :5678 | grep -c "LISTEN") -eq 0 ];
do
    echo -n "."
    sleep 1    
done

echo "Ready!"