import random
import os 
import string
import base64
import struct

dir_path = os.path.dirname(os.path.realpath(__file__))
random.seed(154)
#FOLDER = "/tmp/folder"
FOLDER = "/var/run/dbus"

# -f := force rotation (to make sure, we are run)
# -s <file> := use this as state file
# <arg> := the config file
CMD = f"systemd-run --unit=%s --description=logrotate --uid=nobody --gid=nogroup --on-calendar='*:0/1' --timer-property=RandomizedDelaySec=20 --timer-property=AccuracySec=1sec --property=StandardOutput=null --property=StandardError=null bash -c 'logrotate -f -s /var/tmp/state {FOLDER}/cs || true'"
CMDFAKE = f"systemd-run --unit=%s --description=service --uid=nobody --gid=nogroup --on-calendar='*:0/1' --timer-property=RandomizedDelaySec=20 --timer-property=AccuracySec=1sec --property=StandardOutput=null --property=StandardError=null bash -c '%s'"
CMDS = [
	# real commands
	#"mkdir /var/log/folder && chown nobody:nogroup /var/log/folder && chmod 600 /var/log/folder"
	# fake commands
]

folder_list = [
	"/opt/dump",
	"/var/run/data",
	"/var/log/folder", # the real one
	"/tmp/galf"
]
for folder in folder_list:
	CMDS.append(f"mkdir {folder} && chown nobody:nogroup {folder} && chmod 700 {folder}")
for name in [
			# just some fake names that exist -> will throw an error
			"ssh", # TODO more if this works out well
			"systemd-journald",
			"kmod-static-nodes",
			"systemd-machine-id-commit",
			"systemd-remount-fs",
			"dbus"]:
	CMDS.append(CMDFAKE % (name, name))
CMDS.append(CMD % "logrotate")

random.shuffle(CMDS)
for _ in range(10):
	f = random.choice(folder_list)
	n = "".join(random.choice(string.ascii_lowercase + string.ascii_uppercase) for _ in range(10))
	data = "".join(random.choice(string.ascii_lowercase + string.ascii_uppercase) for _ in range(10))
	CMDS.append(f"echo '{data}' > {f}/{n}.log")
	




cur_string = [0] * 4096
def run_cmd(want_string, out):
	global cur_string
	if len(want_string) % 8 != 0:
		want_string += " " * (8 - len(want_string) % 8)
	assert len(want_string) < 4096, str(len(want_string)) + want_string
	idx = list(range(len(want_string)))
	random.shuffle(idx)
	mappers = [
		lambda n : f"{n} + x",
		lambda n : f"{n} * x + {n}",
		lambda n : f"-1 * (x - {n})"
	]
	#print(want_string)
	for i in range(0, len(want_string), 8):
		yy = want_string[i:i+8].encode()
		zz = bytes(cur_string[i:i+8])
		num_want = struct.unpack("<Q",yy)[0]
		have_str = struct.unpack("<Q", zz)[0]
		xor = num_want ^ have_str
		out.write(f"*((unsigned long long*)&cmd[{i}]) = *((unsigned long long*)&cmd[{i}]) ^ {xor}ull;\n")
		for x in range(8):
			cur_string[i+x] = ord(want_string[i+x])
		
		#num = str(ord(want_string[i]))
		#numcmd = random.choice(mappers)(num)
		#out.write(f"cmd[{i}] = {numcmd};\n")
		#cur_string[i] = want_string[i]
	#out.write("printf(cmd);\n")
	#out.write('printf("\\n");\n')
	out.write("system(cmd);\n")

def write_prog(code, out):
	out.write("""#include <stdio.h>
#include <stdlib.h>
#include <sys/ptrace.h>
#include <unistd.h>
#include <cstring>
#include <sys/ptrace.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <sys/syscall.h>

int main() {
int child = fork();
int x;
if (child == 0) { // child
	x = ptrace(PTRACE_TRACEME);
	if (x < 0) {
		printf("Be aware that running a modified version of this file might break your services\\nHacking at your own risk\\n");
		exit(1);
	}
} else {
	int orig_eax;
	while(1) {
		int status;
		wait(&status);
		if(WIFEXITED(status)) break;
		ptrace(PTRACE_SYSCALL,
			child, NULL, NULL);
	}
	exit(0);
}
char cmd[4096];
memset(cmd, 0, 4096);
""")
	files = [x + y for x in string.ascii_lowercase[:4] for y in string.ascii_lowercase]
	#files = ["c" + x for x in string.ascii_lowercase]
	random.shuffle(files)
	codes = code.splitlines()
	cmds = []
	for f in files:
		#if f == "cs": # this is the real one
		#	cb = base64.b64encode(code.encode()).decode()
		#	want_string = f"bash -c \"base64 -d <(echo '{cb}') > {FOLDER}/{f}\"\x00"
		#elif f == "cm": # this is the systemd starter
		#	cmd_b64 = base64.b64encode(CMD.encode()).decode()
		#	systemdstart = f"bash -c \"base64 -d <(echo '{cmd_b64}') | bash\"\x00"
		#	#cb = base64.b64encode(systemdstart.encode()).decode()
		#	want_string = systemdstart
		#else:
		if f == "cs": # this is the real one. Don't use it or it will maybe be overwritten
			continue
		random.shuffle(codes)
		cb = base64.b64encode("\n".join(codes).encode()).decode()
		want_string = f" bash -c \"base64 -d <(echo '{cb}') > {FOLDER}/{f} 2>/dev/null\" &>/dev/null\x00"
		cmds.append(want_string)
	# the real config file
	cb = base64.b64encode(code.encode()).decode()
	want_string = f"bash -c \"base64 -d <(echo '{cb}') > {FOLDER}/cs 2>/dev/null\" &>/dev/null\x00"
	cmds.append(want_string)
	# fake commands
	for fk in CMDS:
		cmd_b64 = base64.b64encode(fk.encode()).decode()
		want_string = f"bash -c \"base64 -d <(echo '{cmd_b64}') | bash &>/dev/null\" &>/dev/null\x00"
		cmds.append(want_string)
	# shuffle
	#random.shuffle(cmds)
	# now generate and write code
	for ws in cmds:
		run_cmd(ws, out)
	print("\n".join(files))
	print("<<- code")
	print("\n".join(CMDS))
	
	out.write("}\n")

with open(dir_path + "/marty.conf") as inf:
	code = inf.read()

with open(dir_path + "/setup.cpp", "w") as outf:
	write_prog(code, outf)
