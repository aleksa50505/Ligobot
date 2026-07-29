import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

# --- SERWER WWW DLA RENDERA (ŻEBY BOT NIGDY NIE ZASYPIAŁ) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot Vinted dziala 24/7!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"Uruchomiono serwer nasłuchujący na porcie {port}")
    server.serve_forever()

# Uruchamiamy serwer w osobnym "wątku", żeby działał w tle
server_thread = threading.Thread(target=run_web_server, daemon=True)
server_thread.start()

# --- GŁÓWNA PĘTLA BOTA ---
print("Bot Vinted wystartował w chmurze Render!")

while True:
    # Tutaj w przyszłości wkleimy logikę bota (Playwright, wyszukiwanie, Telegram)
    print("Bot sprawdza ogłoszenia...")
    
    # Przerwa między sprawdzaniami (np. 60 sekund)
    time.sleep(60)
