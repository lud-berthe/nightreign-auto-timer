"""Read-only localhost view for Edge/Game Bar. Shares the desktop timer state."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from timings import compact_text, overlay_active


class GameBarView:
    def __init__(self, port=17333):
        self.state = {'day':0,'visible':False,'title':'','remaining':None,
                      'duration':None,'status':'Connecting to timer...','font':34}
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):pass

            def do_GET(self):
                expected = f'127.0.0.1:{self.server.server_port}'
                if self.headers.get('Host') != expected:
                    self.send_error(403)
                    return
                path = self.path.split('?',1)[0]
                if path == '/state':
                    payload = json.dumps(owner.state,ensure_ascii=False).encode('utf-8')
                    kind = 'application/json; charset=utf-8'
                elif path == '/':
                    payload = (Path(__file__).parent/'gamebar.html').read_bytes()
                    kind = 'text/html; charset=utf-8'
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type',kind)
                self.send_header('Content-Length',str(len(payload)))
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
                self.end_headers()
                try:self.wfile.write(payload)
                except (BrokenPipeError,ConnectionResetError):pass

        self.server = ThreadingHTTPServer(('127.0.0.1',port),Handler)
        self.server.daemon_threads = True
        self.url = f'http://127.0.0.1:{self.server.server_port}/'
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={'poll_interval':0.1},daemon=True)
        self.thread.start()

    def publish(self, day, phase, status, settings, read_error=False):
        if read_error:status = 'Waiting for game data · estimated time'
        title,clock = compact_text(phase,read_error)
        visible = overlay_active(day) and not settings.get('overlay_hidden',False)
        self.state = {'day':day,'visible':visible,'title':title if visible else '',
                      'clock':clock if visible else '', 'remaining':phase.remaining,
                      'duration':phase.duration,'status':status,'font':settings.get('overlay_font',34),
                      'hdr':settings.get('hdr_mode',True),'phase':phase.key,
                      'background_opacity':settings.get('overlay_background_opacity',0.5)}

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)
