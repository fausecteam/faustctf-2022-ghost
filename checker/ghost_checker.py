#!/usr/bin/env python3

from ctf_gameserver import checkerlib

import logging
import utils
import requests
import http
import os
import time

from common.server import *

CHECKFLAG_TIMEOUT = 120 # because check_flag in perma may wait  up to 90s already

# TODO config
#PERMASERVER_HOST = "127.0.0.1"
#PERMASERVER_PORT = 7788
#URL = "http://127.0.0.1:7788"
if 'GHOST' in os.environ and os.environ["GHOST"] == 'local':
	logging.info("Local mode")
	URL = "http://[::1]:7788"
else:
	logging.info("normal mode")
	URL = "http://[fd66:777::6]:7788"

URLS = [
#	"http://[fe80::4001:aff:fe43:20]:7788",
#	"http://[fd66:777::6]:7788",
#	"http://[2600:1900:4010:f9:0:1e::]:7788",
#	"http://[fe80::4001:c0ff:fea8:20]:7788",
#	"http://[fe80::dce0:8cff:fed5:5087]:7788"
]

class GhostChecker(checkerlib.BaseChecker):
	def place_flag(self, tick):
		flag = checkerlib.get_flag(tick).replace("/", "-") # we need this to make it URL safe
		logging.info("Flag for tick " + str(tick) + " ready to be deployed")
		path = URL + "/place_flag/" + self.ip + "/" + flag + "/" + str(tick)
		# just for testing something
		#p2 = "http://" + self.ip + "/place_flag/" + self.ip + "/" + flag + "/" + str(tick)
		#print(p2)
		try:
			logging.info("Trying " + path)
			r = requests.get(path)
		#except http.client.RemoteDisconnected as e:
		except Exception as e: # TODO 
			logging.error("Failed to connect to perma " + path)
			#raise e
		# TODO flag can contain '/' ? -> remap
		return checkerlib.CheckResult.OK

	def check_service(self):
		r = requests.get(URL + "/check_service/" + self.ip)
		if r.text == "YES":
			return checkerlib.CheckResult.OK
		elif r.text.startswith("LONGAGO"):
			logging.warning("Last connect is " + r.text[7:] + " s ago")
			return checkerlib.CheckResult.FAULTY
		else:
			logging.warning("Service not working: " + r.text)
			return checkerlib.CheckResult.FAULTY # TODO more precise

	def check_flag(self, tick):
		while True:
			logging.info("Checking flag for")
			r = requests.get(URL + "/check_flag/" + self.ip + "/" + str(tick))
			if r.text.startswith("WAIT"):
				ts = int(r.text.replace("WAIT", ""))
				logging.info(f"Waiting for {ts} seconds")
				time.sleep(ts + 1)
			else:
				break
		if r.text == "YES":
			return checkerlib.CheckResult.OK
		elif r.text == "NOT_FOUND":
			return checkerlib.CheckResult.FLAG_NOT_FOUND
		else:
			logging.error("Unknown response " + r.text)
			return checkerlib.CheckResult.FAULTY # TODO more precise


if __name__ == '__main__':

	checkerlib.run_check(GhostChecker)
