#!/bin/bash

TEAM_INTERVAL=15 # normally 1 minute
TICK_INTERVAL=30 # normally 3 minutes

what=${1}
if [ "$what" = "team" ]; then
	echo "Starting team service"
	while true; do
		echo "--------------------------------------"
		python -O src/code_ips.py local
		sleep ${TEAM_INTERVAL}
	done
elif [ "$what" = "checker" ]; then
	echo "Starting team service"
	tick=0
	while true; do
		echo "--------------------------------------"
		export GHOST=local
		python checker/ghost_checker.py ::1 1 ${tick}
		tick=$((tick+1))
		sleep ${TICK_INTERVAL}
	done
elif [ "$what" = "team" ]; then
	python exploit/expl_server.py # infinite
elif [ "$what" = "perma" ]; then
	python checker/perma_server.py local # infinite
else
	echo "Unknown cmd"
fi
