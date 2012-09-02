import socket, os, logging, re, threading
import signal, sys

# Catch Ctrl-C(KeyInerrupt) signal
def sigint_handler(sig, sf):
	""" SIGINT handler """
	logging.info("SIGINT received, main thread exit.")
	sys.exit(1)
signal.signal(signal.SIGINT, sigint_handler)
