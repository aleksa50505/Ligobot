import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from bs4 import BeautifulSoup

# Konfiguracja Telegrama
TELEGRAM_BOT_TOKEN = "8616098944:AAF18VtLKoU4Tc9mceOISyOYsMb8FuAkhfM"
TELEGRAM_CHAT_ID = "8652334073"

# Link do wyszukiwania na Vinted
VINTED_SEARCH_URL = "https://www.vinted.pl/catalog?search_text=nike"

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Blad wysylania na Telegram: {e}")

# Prosty serwer HTTP dla Render 24/7
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

# Uruchomienie serwera w tle
server_thread = threading.Thread(target=run_server)
server_thread.daemon = True
server_thread.start()

# Główna pętla bota
def vinted_bot_loop():
    print("Uruchamianie bota Vinted...")
    send_telegram_message("🤖 *Ligobot Vinted* wystartował!")
    
    seen_items = set()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    while True:
        try:
            print(f"Sprawdzam Vinted: {VINTED_SEARCH_URL}")
            response = requests.get(VINTED_SEARCH_URL, headers=headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                links = soup.find_all('a', href=True)
                
                unique_items = set()
                for l in links:
                    href = l['href']
                    if "/items/" in href:
                        if not href.startswith("http"):
                            href = "https://www.vinted.pl" + href
                        clean_link = href.split('?')[0]
                        unique_items.add(clean_link)
                
                print(f"Znaleziono ofert: {len(unique_items)}")
                
                if not seen_items and unique_items:
                    seen_items.update(unique_items)
                    print("Zainicjowano bazę znanych ofert.")
                else:
                    for link in unique_items:
                        if link not in seen_items:
                            seen_items.add(link)
                            msg = f"🔥 **Nowa oferta na Vinted!**\n\n[Sprawdź ofertę]({link})"
                            print(f"Wysyłam powiadomienie: {link}")
                            send_telegram_message(msg)
            else:
                print(f"Błąd HTTP: {response.status_code}")

        except Exception as e:
            print(f"Błąd podczas pobierania Vinted: {e}")

        # Czekaj 3 minuty
        time.sleep(180)

if __name__ == "__main__":
    vinted_bot_loop()
