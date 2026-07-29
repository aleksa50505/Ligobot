import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# Prosty serwer HTTP, żeby Render widział, że aplikacja żyje (zapobiega uśpieniu)
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot Vinted dziala 24/7!")

def run_server():
    server_address = ('0.0.0.0', 10000)
    httpd = HTTPServer(server_address, SimpleHandler)
    print("Serwer HTTP wystartowal na porcie 10000")
    httpd.serve_forever()

# Uruchomienie serwera w osobnym wątku
server_thread = threading.Thread(target=run_server)
server_thread.daemon = True
server_thread.start()

print("Inicjalizacja bota Vinted...")

# Tutaj w przyszłości dodamy główną pętlę Playwright i powiadomień Telegram
while True:
    pass
