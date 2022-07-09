import socket
import threading
import socketserver
import json
import base64
import random

HOST = "localhost"
PORT = 1235
PORTGET = 3333

class ThreadedAnswerHandler(socketserver.BaseRequestHandler):
	def handle(self):
		data = self.request.recv(1024)
		print("Got: ", data)
		print(">> ", base64.b64decode(data.strip()))

class ThreadedAnswer(socketserver.ThreadingMixIn, socketserver.TCPServer):
	address_family = socket.AF_INET6
	def __init__(self, addr, handler):
		self.allow_reuse_address = True
		socketserver.TCPServer.__init__(self, addr, handler)

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
	def handle(self):
		num = random.randint(0, 100000)
		print("Handling a request from ", self.request.getpeername())
		sender = self.request.getpeername()[0]
		j = [
			{"cmd": "INFO", "outid": num},
			{"cmd": "GETFILE", "outid": num}
		]
		self.request.sendall(json.dumps(j).encode())

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
	address_family = socket.AF_INET6
	def __init__(self, addr, handler):
		self.allow_reuse_address = True
		socketserver.TCPServer.__init__(self, addr, handler)

def main():
	# Second channel to get the responses
	answer = ThreadedAnswer((HOST, PORTGET), ThreadedAnswerHandler)
	answer_thread = threading.Thread(target=answer.serve_forever)
	answer_thread.daemon = True
	answer_thread.start()
	
	# First channel send the data
	server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
	try:
		server.serve_forever()
	finally:
		server.shutdown()
#	input("Press [RETURN] to end server ... ")

if __name__ == "__main__":
	main()
