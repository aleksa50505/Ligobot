import os
import time
import html
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any
import requests
from bs4 import BeautifulSoup

VINTED_CATALOG_URL = "https://www.vinted.pl/catalog?search_text=lego&order=newest_first"
VINTED_HOME_URL = "https://www.vinted.pl/"
SEEN_FILE = "seen_ids.txt"

FRAZY_GRUPY: tuple[tuple[str, ...], ...] = (
    ("pudełko", "knights"),
    ("pudelko", "knights"),
    ("lego", "mix"),
    ("lego", "miks"),
    ("pudełko", "lego"),
    ("pudelko", "lego"),
    ("różne", "zestawy", "lego"),
    ("rozne", "zestawy", "lego"),
    ("pudełko", "ninjago"),
    ("pudelko", "ninjago"),
    ("pudełko", "star", "wars", "lego"),
    ("pudelko", "star", "wars", "lego"),
    ("pudełko", "minecraft", "lego"),
    ("pudelko", "minecraft", "lego"),
    ("lot", "lego"),
    ("lego", "po", "dzieciach"),
    ("lego", "po", "dziecku"),
    ("laatikollinen", "lego"),
    ("many", "lego"),
    ("many", "sets", "lego"),
    ("lego", "box"),
    ("lego", "bundle"),
    ("lego", "lot"),
    ("lego", "collection"),
    ("krabice", "lego"),
    ("lego", "směs"),
    ("lego", "smes"),
    ("lego", "kiste"),
    ("lego", "sammlung"),
    ("lego", "kostky"),
    ("kostičky", "lega"),
    ("kosticky", "lega"),
    ("různé", "kostičky"),
    ("ruzne", "kosticky"),
    ("lego", "używane"),
    ("lego", "uzywane"),
    ("różne", "lego"),
    ("rozne", "lego"),
    ("mieszanka", "lego"),
    ("mieszanki", "lego"),
    ("lego", "mieszane"),
    ("sporo", "lego"),
    ("lego", "kg"),
    ("partia", "lego"),
    ("lego", "elementy"),
    ("lego", "luzem"),
    ("lego", "luz"),
    ("lego", "pudełku"),
    ("lego", "pudelku"),
    ("dużo", "lego"),
    ("duzo", "lego"),
    ("lego", "części"),
    ("lego", "czesci"),
    ("lego", "sprzedam"),
    ("torba", "lego"),
    ("sets", "lego"),
)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Ligobot LEGO dziala 24/7!")

def run_server():
    server_address = ('0.0.0.0', 10000)
    httpd = HTTPServer(server_address, SimpleHandler)
    httpd.serve_forever()

server_thread = threading.Thread(target=run_server)
server_thread.daemon = True
server_thread.start()


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    telegram_chat_id: str
    proxy_url: str
    interval_seconds: int = 120

    @classmethod
    def from_environment(cls) -> Config:
        # Pobieranie proxy ze zmiennych środowiskowych Render (obsługa PROXY_URL, HTTP_PROXY lub HTTPS_PROXY)
        proxy = (
            os.environ.get("PROXY_URL", "").strip() or
            os.environ.get("HTTP_PROXY", "").strip() or
            os.environ.get("HTTPS_PROXY", "").strip()
        )
        return cls(
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
            proxy_url=proxy,
            interval_seconds=int(os.environ.get("CHECK_INTERVAL_SECONDS", "120")),
        )


class LegoDealMonitor:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.seen_ids: set[str] = self._load_seen_ids()
        self.telegram_error_reported = False
        
        # Konfiguracja sesji requests z rotacyjnymi proxy rezydencjalnymi
        self.session = requests.Session()
        if self.config.proxy_url:
            self.session.proxies = {
                "http": self.config.proxy_url,
                "https": self.config.proxy_url,
            }
            print("🌐 Włączono obsługę rotacyjnych proxy rezydencjalnych.")
        else:
            print("⚠️ OSTRZEŻENIE: Brak skonfigurowanego PROXY w zmiennych środowiskowych!")

        self.send_telegram("🤖 <b>Ligobot LEGO aktywowany i gotowy do pracy (z proxy)!</b>")

    def _load_seen_ids(self) -> set[str]:
        seen = set()
        if os.path.exists(SEEN_FILE):
            try:
                with open(SEEN_FILE, "r", encoding="utf-8") as f:
                    for line in f.readlines()[-5000:]:
                        if item_id := line.strip():
                            seen.add(item_id)
            except Exception:
                pass
        return seen

    def _save_seen_id_to_disk(self, item_id: str = "") -> None:
        try:
            with open(SEEN_FILE, "a", encoding="utf-8") as f:
                f.write(f"{item_id}\n")
            if len(self.seen_ids) > 6000:
                recent = list(self.seen_ids)[-5000:]
                with open(SEEN_FILE, "w", encoding="utf-8") as f:
                    f.write("\n".join(recent) + "\n")
                self.seen_ids = set(recent)
        except Exception:
            pass

    def send_telegram(self, text: str) -> None:
        if not self.config.telegram_bot_token or not self.config.telegram_chat_id:
            return
        payload = urllib.parse.urlencode({
            "chat_id": self.config.telegram_chat_id,
            "text": text,
            "parse_mode": "HTML",
        }).encode("utf-8")
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                pass
            self.telegram_error_reported = False
        except Exception as error:
            if not self.telegram_error_reported:
                print(f"Telegram error: {error}")
                self.telegram_error_reported = True

    def fetch_catalog_items(self) -> list[dict[str, Any]]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9",
        }
        
        try:
            # Użycie sesji przechodzącej przez rotacyjne proxy rezydencjalne
            self.session.get(VINTED_HOME_URL, headers=headers, timeout=20)
            time.sleep(1)
            response = self.session.get(VINTED_CATALOG_URL, headers=headers, timeout=25)
            
            if response.status_code != 200:
                print(f"Błąd HTTP Vinted (przez proxy): {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            parsed_items = []
            
            for a in soup.find_all('a', href=True):
                href = a['href']
                if "/items/" in href:
                    if not href.startswith("http"):
                        href = "https://www.vinted.pl" + href
                    clean_url = href.split('?')[0]
                    
                    parts = clean_url.split('/')
                    item_id = ""
                    for p in parts:
                        if p.isdigit():
                            item_id = p
                            break
                    if not item_id:
                        continue
                    
                    title = a.get('title', '') or a.get_text(strip=True)
                    
                    parsed_items.append({
                        "id": item_id,
                        "title": title,
                        "url": clean_url
                    })
            
            return parsed_items
        except Exception as exc:
            print(f"Błąd parsowania katalogu przez proxy: {exc}")
            return []

    @staticmethod
    def matches(title: str) -> bool:
        full_text = title.casefold()
        for group in FRAZY_GRUPY:
            if all(word.casefold() in full_text for word in group):
                return True
        return False

    def check_vinted(self) -> None:
        print("🔍 Sprawdzam najnowsze oferty na Vinted (z użyciem proxy)...")
        items = self.fetch_catalog_items()
        if not items:
            return

        is_first_run = len(self.seen_ids) == 0

        for item in reversed(items):
            item_id = str(item["id"])
            if item_id in self.seen_ids:
                continue
            
            self.seen_ids.add(item_id)
            self._save_seen_id_to_disk(item_id)

            if is_first_run:
                continue

            title = str(item.get("title", "")).strip()
            
            if not self.matches(title):
                continue

            url = str(item.get("url", VINTED_HOME_URL))
            
            msg = (
                "🧱 <b>ZNALEZIONO OKAZJĘ LEGO!</b>\n\n"
                f"📌 <b>Tytuł:</b> {html.escape(title)}\n\n"
                f"🔗 <a href=\"{html.escape(url, quote=True)}\">Otwórz w Vinted</a>"
            )
            self.send_telegram(msg)
            print(f"✅ Alert wysłany: {title}")

        if is_first_run:
            print(f"Inicjalizacja zakończona. Zindeksowano {len(self.seen_ids)} ofert.")

    def run(self) -> None:
        while True:
            self.check_vinted()
            time.sleep(self.config.interval_seconds)

if __name__ == "__main__":
    try:
        config = Config.from_environment()
        monitor = LegoDealMonitor(config)
        monitor.run()
    except Exception as exc:
        print(f"Błąd krytyczny bota: {exc}")
