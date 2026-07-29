import os
import time
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from playwright.async_api import async_playwright
import requests

# Konfiguracja Telegrama (wstaw swoje dane)
TELEGRAM_BOT_TOKEN = "8616098944:AAF18VtLKoU4Tc9mceOISyOYsMb8FuAkhfM"
TELEGRAM_CHAT_ID = "8652334073"

# Link do wyszukiwania na Vinted (skopiuj swój przefiltrowany link z przeglądarki)
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

# Główna pętla bota Vinted z Playwright
async def vinted_bot_loop():
    print("Uruchamianie bota Vinted z Playwright...")
    send_telegram_message("🤖 *Ligobot Vinted* wystartował i monitoruje oferty!")
    
    seen_items = set()

    async with async_playwright() as p:
        # Uruchomienie przeglądarki w tle (headless)
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        while True:
            try:
                print(f"Sprawdzam Vinted: {VINTED_SEARCH_URL}")
                await page.goto(VINTED_SEARCH_URL, timeout=60000)
                await page.wait_for_timeout(5000)  # Czekaj na załadowanie elementów

                # Pobieranie linków do ofert z widoku katalogu Vinted
                items = await page.eval_on_selector_all(
                    'a[href*="/items/"]',
                    '(elements) => elements.map(e => e.href)'
                )
                
                # Usuwamy duplikaty i puste wartości
                unique_items = list(set([item.split('?')[0] for item in items if item]))
                
                print Znaleziono ofert: {len(unique_items)}
                
                # Jeśli to pierwsze uruchomienie, zapisujemy aktualne oferty, żeby nie spamować starymi
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
                            await asyncio.sleep(1)

            except Exception as e:
                print(f"Błąd podczas pobierania Vinted: {e}")

            # Odczekaj 3 minuty przed kolejnym sprawdzeniem (żeby nie zablokowało IP)
            await asyncio.sleep(180)

if __name__ == "__main__":
    asyncio.run(vinted_bot_loop())
