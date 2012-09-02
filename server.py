#!/usr/bin/env python

import os, threading, socket, logging, traceback
import time, ConfigParser, re, sys, signal

server_host = ''
poll_port = 50045

request_port = 6767
time_interval = 10

# Catch Ctrl-C(KeyInerrupt) signal
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


class Singleton(object):
	_inst = None # the one, true Singleton

	def __new__(cls, *args, **kwargs):
		""" Check to see if a _inst exists already for this class
			Compare class types instead of just looking for None so
			that subclasses will create their own _inst objects """
		if cls != type(cls._inst):
			cls._inst = object.__new__(cls, *args, **kwargs)
		return cls._inst


class ConnectionPool(Singleton):
	""" Maintain connections pool of Monitor targets,
		put mutex and targets static """
	# protect [active|inactive]_targets list
	mutex = threading.Lock()
	# active_targets: dictionary
	# { sockobj : [('ip address', port), load information] }
	active_targets = {}
	# inactive_targets: ip address list of inactive targets
	inactive_targets = []
	# 'ipaddr|cpu|mem'
	target_url = '' 

	@staticmethod
	def cal_target_url():
		def parse_cpu_idle(info):
			regex = re.compile('Cpu.*?(?P<id>\d+\.\d*)%', re.I)
			m_obj = regex.search(info)
			return float(m_obj.group('id'))

		def parse_mem(info):
			regex = re.compile('free.*?(?P<free>\d+k)', re.I)
			m_obj = regex.search(info)
			return m_obj.group('free')

		target_, cpu_, mem_ = '', 0, ''
		# { sockobj : [('ip address', port), load information] }
		try:
			target_ = (max(ConnectionPool.active_targets.values(),
					key = lambda value: parse_cpu_idle(value[1])))
			cpu_ = parse_cpu_idle(target_[1])
			mem_ = parse_mem(target_[1])
		except ValueError:
			logging.debug("ConnectionPool: no active targets.")
			# pass
		ConnectionPool.target_url = (('|'.join([target_[0][0],
			'%.2f' % cpu_, mem_]))
			if target_ else 'No target found.')
		logging.debug("Target url: %s", ConnectionPool.target_url)

	@staticmethod
	def init(hosts):
		for host in hosts:
			ConnectionPool.inactive_targets.append(host)

	@staticmethod
	def add_active_target(target):
		""" Add target to connection pool """
		ConnectionPool.mutex.acquire()
		ConnectionPool.active_targets[target[0]] = [target[1], '']
		if target[1][0] in ConnectionPool.inactive_targets:
			idx = ConnectionPool.inactive_targets.index(target[1][0])
			del ConnectionPool.inactive_targets[idx]
		ConnectionPool.mutex.release()

	@staticmethod
	def remove_active_target(sockobj):
		""" Remove target from connection pool """
		ConnectionPool.mutex.acquire()
		ipaddr = ConnectionPool.active_targets[sockobj][0][0]
		ConnectionPool.inactive_targets.append(ipaddr)
		del ConnectionPool.active_targets[sockobj] # delete key(sockobj)
		ConnectionPool.mutex.release()

	@staticmethod
	def operate_targets(callback, args):
		""" Operate callback on each target """
		# if Connection.active_targets is empty, do nothing
		for target in ConnectionPool.active_targets.keys():
			#ConnectionPool.mutex.acquire()
			callback(target, args) # target: sockobj
			#ConnectionPool.mutex.release()

	@staticmethod
	def update_target(target, info):
		ConnectionPool.mutex.acquire()
		ConnectionPool.active_targets[target][1] = info
		ConnectionPool.mutex.release()
		logging.debug("Received from %s" %
				repr(ConnectionPool.active_targets[target]))

	@staticmethod
	def dump():
		""" Dump connections info """
		for sockobj,target_info in ConnectionPool.active_targets.items():
			logging.debug("Dump: %s => %s" %
					(repr(sockobj), repr(target_info)))

	@staticmethod
	def dump_inactive():
		""" Dump inactive targets info """
		logging.debug("Inactive target: %s",
				repr(ConnectionPool.inactive_targets))

	@staticmethod
	def dump_log():
		return (repr(ConnectionPool.active_targets.values())
				if ConnectionPool.active_targets else "No log.")

	@staticmethod
	def active_targets_ip():
		return [addr for addr, info in ConnectionPool.active_targets.values()]

	@staticmethod
	def remove_inactive_target(target):
		""" Remove inactive target """
		ConnectionPool.mutex.acquire()
		idx = ConnectionPool.inactive_targets.index(target)
		del ConnectionPool.inactive_targets[idx]
		ConnectionPool.mutex.release()

	@staticmethod
	def probe():
		for target in ConnectionPool.inactive_targets:
			try:
				sock = socket.socket()
				sock.connect((target, poll_port))
			except:
				sock.close()
				continue
			# TODO: combine remove+add
			logging.debug("Remove inactive target: %s", target)
			ConnectionPool.remove_inactive_target(target)
			logging.debug("Add active target: %s", sock.getpeername())
			ConnectionPool.add_active_target((sock, sock.getpeername()))
			ConnectionPool.dump()


class ConnectionManager(threading.Thread):
	""" Thread of listen socket """
	def __init__(self):
		""" Init listen socket, mutex, connections pool """
		self.sock = socket.socket()
		self.sock.bind((host, listen_port))
		self.sock.listen(100)
		threading.Thread.__init__(self)

	def run(self):
		""" Listen socket ready to accept external connection """
		thread_announce_start(self.__class__)
		while True:
			sockobj, addr = self.sock.accept()
			# TODO: ip address duplicated, with different port:
			sockobj.setblocking(0)
			ConnectionPool.add_active_target((sockobj, addr))
			logging.info("Monitor target: %s connected." % repr(addr))
			ConnectionPool.dump()
		thread_announce_stop(self.__class__)


class TargetCfgParser(object):
	""" Config file parser """
	def __init__(self):
		self.parser = ConfigParser.ConfigParser()
		self.parser.read('targets.cfg')

	def parse(self):
		""" Parse config file and establish targets list """
		hosts = self.parser.get('targets', 'hosts').split('|')
		# Init ConnectionPool's inactive_targets with config file
		ConnectionPool.init(hosts)
		ConnectionPool.dump_inactive()
		for target in hosts:
			sockobj = socket.socket()
			try:
				logging.debug("Trying to connect remote target: %s" %
						repr((target, poll_port)))
				sockobj.connect((target, poll_port))
			except socket.error:
				continue
			logging.debug("Target %s connected." %
					repr((sockobj, sockobj.getpeername())))
			ConnectionPool.remove_inactive_target(target)
			ConnectionPool.add_active_target(
					(sockobj, sockobj.getpeername()))
		ConnectionPool.dump()


class Poller(threading.Thread):
	""" Thread of Poller """
	def __init__(self):
		threading.Thread.__init__(self)

	@staticmethod
	def poll(sockobj, connectionpool):
		""" Poll each of active targets and collect load
			information, if targets closed or crashed,
			put them to inactive_targets """
		try:
			sockobj.sendall('GETINFO')
			load_info = sockobj.recv(1024)

			if not load_info: # target: socket closed or process exited
				msg = ("Target %s might closed." %
						repr((sockobj, sockobj.getpeername())))
				raise socket.error(msg)
			# update load information
			ConnectionPool.update_target(sockobj, load_info)
		except socket.error:
			# 1. non-blocking I/O, no response from target
			# 2. target: socket closed or process exited
			logging.debug(sys.exc_info()[1])
			ConnectionPool.remove_active_target(sockobj)
			# Debug purpose
			ConnectionPool.dump()
			ConnectionPool.dump_inactive()

	def run(self):
		""" Poll at interval of INTERVAL """
		thread_announce_start(self.__class__)
		while True:
			ConnectionPool.operate_targets(Poller.poll, ConnectionPool)
			ConnectionPool.cal_target_url()
			ConnectionPool.dump()
			time.sleep(time_interval)
		thread_announce_stop(self.__class__)


class MonitorThread(threading.Thread):
	""" MonitorThread: accept and handle client's request, then
		reply with load information(cpu, mem, etc.) or log """
	def request_url(self):
		""" requestURL command """
		logging.debug("request_url invoked.")
		return ConnectionPool.target_url

	def request_log(self):
		""" requestLOG command """
		logging.debug("request_log invoked.")
		return ConnectionPool.dump_log()

	def __init__(self, client):
		self.sockobj, self.addr = client[0], client[1]
		self.callbacks = {'requestURL':self.request_url,
				'requestLOG':self.request_log}
		threading.Thread.__init__(self)

	def run(self):
		thread_announce_start(self.__class__)
		try:
			while True:
				request = self.sockobj.recv(1024)
				# blocking until server's request coming
				if not request:
					break
				request = request.strip()
				logging.debug("request: %s" % request)
				reply = 'Unknown command'
				# TODO: IndexError
				if request == 'requestURL' or request == 'requestLOG':
					reply = self.callbacks[request]()
				reply += os.linesep
				logging.debug("reply: %s" % reply)
				self.sockobj.sendall(reply)
		except socket.error:
			pass
		thread_announce_stop(self.__class__)
		self.sockobj.close()


class MonitorServer(threading.Thread):
	""" MonitorServer: listen connection request from client,
		and maintain thread pool """
	def __init__(self):
		self.sock = socket.socket()
		self.sock.bind((server_host, request_port))
		self.sock.listen(100)
		self.mutex = threading.Lock() # protect thread pool
		self.thread_pool = []
		threading.Thread.__init__(self)
		
	def run(self):
		thread_announce_start(self.__class__)
		try:
			while True:
				sockobj, addr = self.sock.accept()
				logging.info("Client: %s connected." % repr(addr))
				self.mutex.acquire()
				thread = MonitorThread((sockobj, addr))
				self.thread_pool.append(thread)
				self.mutex.release()
				thread.start()
		except:
			pass
		self.sock.close()
		thread_announce_stop(self.__class__)


class TargetsProber(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
	
	def run(self):
		thread_announce_start(self.__class__)
		#try:
		while True:
			ConnectionPool.probe()
			time.sleep(20)
			logging.debug('TargetsProbe invoked.')
		#except:
			#pass
		thread_announce_stop(self.__class__)


class Server():
	""" Server: main thread """
	def __init__(self):
		# Threads list: Poller, MonitorServer, TargetsProber
		self.threads = [Poller(), MonitorServer(), TargetsProber()]

	def run(self):
		thread_announce_start(self.__class__)
		# TODO: try to try+except here
		# Kick off threads running
		for thread in self.threads:
			thread.start()
		for thread in self.threads:
			thread.join()
		del self.threads
		thread_announce_stop(self.__class__)


if __name__ == '__main__':
	try:
		TargetCfgParser().parse()
		Server().run()
	except:
		logging.info(sys.exc_info()[1])
		traceback.print_tb(sys.exc_info()[2])
		logging.info("Main thread exit.")
		os._exit(1)
