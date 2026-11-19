#!/usr/bin/env python3
"""Serve only the bundled UI on loopback; invoke the actual costing engine."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from calculate import calculate

HTML=Path(__file__).resolve().parents[1]/'assets/interface/index.html'
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass  # Never log payroll or recipe content.
    def send(self,status,body,kind='application/json; charset=utf-8'):
        self.send_response(status); self.send_header('Content-Type',kind)
        self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers(); self.wfile.write(body)
    def valid_host(self):
        return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
    def do_GET(self):
        if not self.valid_host(): self.send(403,b'{}'); return
        if self.path not in ('/','/index.html'): self.send(404,b'{}'); return
        self.send(200,HTML.read_bytes(),'text/html; charset=utf-8')
    def do_POST(self):
        if not self.valid_host(): self.send(403,b'{}'); return
        origins=(f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}')
        if self.headers.get('Origin') not in origins: self.send(403,b'{}'); return
        if self.path!='/api/calculate': self.send(404,b'{}'); return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=2_000_000: raise ValueError('input must be 1 byte to 2 MB')
            data=json.loads(self.rfile.read(length)); result=calculate(data)
            self.send(200,json.dumps(result,ensure_ascii=False).encode())
        except (ValueError,KeyError,TypeError,AttributeError,ArithmeticError) as error:
            self.send(400,json.dumps({'status':'validation_error','error':str(error)},ensure_ascii=False).encode())
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8765); args=parser.parse_args()
    server=HTTPServer(('127.0.0.1',args.port),Handler)
    print(f'POUR: http://127.0.0.1:{server.server_port}/',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
if __name__=='__main__': main()
