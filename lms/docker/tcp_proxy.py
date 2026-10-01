#!/usr/bin/env python3

import argparse
import select
import socket
import socketserver


class ProxyHandler(socketserver.BaseRequestHandler):
	def handle(self):
		server = self.server
		try:
			with socket.create_connection((server.target_host, server.target_port), timeout=10) as upstream:
				self.request.settimeout(None)
				upstream.settimeout(None)
				sockets = [self.request, upstream]
				while True:
					readable, _, _ = select.select(sockets, [], [])
					for source in readable:
						data = source.recv(65536)
						if not data:
							return
						destination = upstream if source is self.request else self.request
						destination.sendall(data)
		except (ConnectionError, OSError):
			return


class ThreadedProxy(socketserver.ThreadingMixIn, socketserver.TCPServer):
	allow_reuse_address = True
	daemon_threads = True


def main():
	parser = argparse.ArgumentParser(description="TCP proxy for Frappe's loopback development server")
	parser.add_argument("--listen-host", required=True)
	parser.add_argument("--listen-port", type=int, required=True)
	parser.add_argument("--target-host", required=True)
	parser.add_argument("--target-port", type=int, required=True)
	args = parser.parse_args()

	with ThreadedProxy((args.listen_host, args.listen_port), ProxyHandler) as server:
		server.target_host = args.target_host
		server.target_port = args.target_port
		server.serve_forever()


if __name__ == "__main__":
	main()
