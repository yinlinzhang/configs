#!/usr/bin/env python

import socket, os, logging, re, threading
import signal, sys

host = ''
port = 50045

# Catch Ctrl-C(KeyInterrupt) signal
def sigint_handler(sig, sf):
	""" SIGINT handler """
	logging.info("SIGINT received, main thread exit.")
	os._exit(1)
signal.signal(signal.SIGINT, sigint_handler)

logging.basicConfig(level=logging.DEBUG,
		format='%(levelname)s -- %(asctime)s %(message)s',
		datefmt='[%d/%b/%Y %H:%M:%S]')

def thread_announce_start(cls):
	logging.info(' '.join(['thread:', repr(cls), 'start running.']))

def thread_announce_stop(cls):
	logging.info(' '.join(['thread:', repr(cls), 'stop running.']))


class InfoCollector(object):
	def __init__(self):
		self.load_info = {}

	def top(self):
		""" top command """
		f = os.popen('top -bi -n 2 -d 0.5')
		lines = f.readlines()
		top_output = ''.join(lines[len(lines)/2:])
		# Cpu(s):
		regex = re.compile(r'Cpu.*[^0-9]+(?P<id>\d+\.\d+%).*?id', re.I)
		m_obj = regex.search(top_output)
		self.load_info['Cpu'] = m_obj.group('id')
		# Mem:
		regex = re.compile(
				r'Mem.*?(?P<total>\d+k).*total.*?(?P<free>\d+k).*free',
				re.I)
		m_obj = regex.search(top_output)
		self.load_info['Mem'] = {}
		self.load_info['Mem']['total'] = m_obj.group('total')
		self.load_info['Mem']['free'] = m_obj.group('free')

	def collect(self, request):
		self.top()
		logging.debug("Load information: %s", self.load_info)
		return repr(self.load_info)


class HandlerThread(threading.Thread):
	def __init__(self, server):
		self.collector = InfoCollector()
		self.sockobj, self.addr = server[0], server[1]
		threading.Thread.__init__(self)

	def run(self):
		thread_announce_start(self.__class__)
		while True:
			request = self.sockobj.recv(1024)
			# blocking until server's request coming
			if not request:
				break
			logging.debug("Received from server: %s", request)
			self.sockobj.sendall(self.collector.collect(request))
		self.sockobj.close()
		thread_announce_stop(self.__class__)
		

class Target(object):
	def __init__(self):
		self.sock = socket.socket()
		self.sock.bind((host, port))
		self.sock.listen(100)
		self.mutex = threading.Lock() # protect thread pool
		self.thread_pool = []

	def run(self):
		try:
			while True:
				sockobj, addr = self.sock.accept()
				self.mutex.acquire()
				thread = HandlerThread((sockobj, addr))
				thread.start()
				self.thread_pool.append(thread)
				self.mutex.release()
		except socket.error:
			pass
		self.sock.close()


if __name__ == '__main__':
	Target().run()
	#print InfoCollector().collect('')
