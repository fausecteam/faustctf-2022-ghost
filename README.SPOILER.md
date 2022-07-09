Service Ghost - Explanation -- Spoiler 
================

This service is similar to a malware contacting a C&C server for tasks to execute.

It's main prinziple is to be hidden quite well in the system.

## Basic Principle
- The service is *not* a running server, but a client running periodically. The teams have to setup an always running server.
- Once activated, the service connects to all known IPs (teams + checker) and asks for tasks
- Tasks include storing values (e.g. flags) and exfiltrating files

## Details
- The malware reconfigures the logrotate.timer file to execute every minute
- The malware itself is hidden inside the logrotate config file /etc/logrotate.d/marty.conf
	- logrotate allows a "firstaction" to be executed before rotating
	- The malware is a gzip+base64 string of a python script
	- The "firstaction" unpacks the malware script and executes it in python for each IP

## Ports
What			for what	Game	localtest
-------------------------------------
exploit-serv	send cmds	1236	1236
exploit-serv	recv files	3334	3334
