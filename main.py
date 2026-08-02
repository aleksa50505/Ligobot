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

DEFAULT_VINTED_URL = (
    "https://www.vinted.pl/api/v2/catalog/items"
    "?search_text=lego&order=newest_first&per_page=96"
)
VINTED_HOME_URL = "https://www.vinted.pl/catalog?search_text=lego"
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

KURSY_WALUT: dict[str, float] = {
    "PLN": 1.0,
    "EUR": 4.35,
    "CZK": 0.17,
    "HUF": 0.011,
    "SEK": 0.38,
    "RON": 0.87,
}

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
    vinted_url: str = DEFAULT_VINTED_URL
    max_price_pln: float = 120.0
    interval_seconds: int = 120

    @classmethod
    def from_environment(cls) -> Config:
        return cls(
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
            vinted_url=DEFAULT_VINTED_URL,
            max_price_pln=float(os.environ.get("MAX_CENA_PLN", "120")),
            interval_seconds=int(os.environ.get("CHECK_INTERVAL_SECONDS", "120")),
        )


class LegoDealMonitor:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.seen_ids: set[str] = self._load_seen_ids()
        self.telegram_error_reported = False
        self.last_vinted_error: str | None = None
        self._session: requests.Session | None = None
        self._init_session_with_retry()

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

    def _init_session_with_retry(self) -> None:
        while True:
            try:
                self._init_session()
                return
            except Exception as e:
                print(f"[OSTRZEŻENIE] Inicjalizacja sesji nie powiodła się: {e}. Ponawiam za 15 sekund...")
                time.sleep(15)

    def _init_session(self) -> None:
        print("Inicjalizacja nowej sesji HTTP z parametrami Web...")
        session = requests.Session()
        
        # Realistyczne nagłówki nowoczesnej przeglądarki z zachowaniem struktury TLS
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        })

        try:
            resp = session.get("https://www.vinted.pl/", timeout=15)
            # Pobieramy ciasteczko sesyjne, które jest kluczowe dla API
            if resp.status_code in (200, 302, 403):
                self._session = session
                print("Sesja nawiązana, ciasteczka zapisane w pamięci podręcznej.")
                return
        except Exception as exc:
            raise RuntimeError(f"Błąd sieci przy pobieraniu strony głównej: {exc}") from exc

        raise RuntimeError(f"Vinted odrzuciło połączenie wstępne, status: {resp.status_code}")

    def _refresh_session(self) -> None:
        try:
            self._init_session()
        except Exception:
            time.sleep(10)

    def send_telegram(self, text: str) -> None:
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

    def fetch_items(self) -> list[dict[str, Any]]:
        assert self._session is not None
        
        # Unikalne nagłówki dla zapytań XHR do katalogu Vinted
        api_headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://www.vinted.pl/catalog?search_text=lego",
            "Origin": "https://www.vinted.pl",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
        }

        for attempt in range(2):
            try:
                # Dodajemy losowy parametr buforujący, aby pominąć cache Cloudflare na serwerze pośredniczącym
                url_with_cache_buster = f"{self.config.vinted_url}&_={int(time.time() * 1000)}"
                resp = self._session.get(
                    url_with_cache_buster,
                    headers=api_headers,
                    timeout=15,
                )
            except Exception as exc:
                raise RuntimeError(f"Błąd sieci podczas pobierania ofert: {exc}") from exc

            if resp.status_code == 200:
                try:
                    # Sprawdzamy czy fizycznie otrzymaliśmy JSON, a nie stronę HTML blokady
                    if not resp.text.strip().startswith("{"):
                        raise ValueError("Otrzymano odpowiedź HTML zamiast obiektu JSON")
                    
                    data = resp.json()
                    if not isinstance(data, dict):
                        raise ValueError("Struktura JSON nie jest słownikiem")
                    
                    items = data.get("items", [])
                    return [i for i in items if isinstance(i, dict)]
                except Exception as json_err:
                    if attempt == 0:
                        print("Wykryto niezgodność formatu danych, odświeżam tokeny sesyjne...")
                        self._refresh_session()
                        continue
                    raise RuntimeError(f"Vinted zwróciło blokadę HTML w odpowiedzi na API: {json_err}") from json_err

            if resp.status_code in (401, 403, 429) and attempt == 0:
                print(f"Ostrzeżenie o statusie blokady {resp.status_code}, ponawiam sesję...")
                self._refresh_session()
                continue

            raise RuntimeError(f"Vinted API zwróciło niedozwolony status HTTP: {resp.status_code}")
        
        raise RuntimeError("Vinted API odrzuciło wszystkie żądania.")

    @staticmethod
    def price_in_pln(item: dict[str, Any]) -> tuple[float, float, str]:
        price_field = item.get("price") or {}
        if isinstance(price_field, dict):
            raw_str = price_field.get("amount", "9999")
            currency = str(price_field.get("currency_code", "PLN")).upper()
        else:
            raw_str = str(price_field)
            currency = str(item.get("currency", "PLN")).upper()
        try:
            raw_price = float(raw_str)
        except (TypeError, ValueError):
            raw_price = 9999.0
        return raw_price * KURSY_WALUT.get(currency, 1.0), raw_price, currency

    @staticmethod
    def matches(title: str, description: str) -> bool:
        full_text = f"{title} {description}".casefold()
        for group in FRAZY_GRUPY:
            if all(word.casefold() in full_text for word in group):
                return True
        return False

    def format_alert(
        self, title: str, description: str, price_pln: float, raw_price: float, currency: str, url: str
    ) -> str:
        original = f" ({raw_price:.2f} {html.escape(currency)})" if currency != "PLN" else ""
        desc_short = (description[:100] + "...") if len(description) > 100 else description
        return (
            "🧱 <b>ZNALEZIONO OKAZJĘ LEGO!</b>\n\n"
            f"📌 <b>Tytuł:</b> {html.escape(title)}\n"
            f"📝 <b>Opis:</b> {html.escape(desc_short) if desc_short else 'Brak opisu'}\n"
            f"💰 <b>Cena:</b> ~{price_pln:.2f} zł{original}\n\n"
            f"🔗 <a href=\"{html.escape(url, quote=True)}\">Otwórz w Vinted</a>"
        )

    def check_vinted(self) -> None:
        try:
            items = self.fetch_items()
        except Exception as error:
            msg = str(error)
            if msg != self.last_vinted_error:
                print(f"Vinted error: {msg}")
                self.last_vinted_error = msg
            return

        if self.last_vinted_error is not None:
            self.last_vinted_error = None

        is_first_run = len(self.seen_ids) == 0

        for item in reversed(items):
            if "id" not in item:
                continue
            item_id = str(item["id"])
            if item_id in self.seen_ids:
                continue
            
            self.seen_ids.add(item_id)
            self._save_seen_id_to_disk(item_id)

            if is_first_run:
                continue

            title = str(item.get("title", "")).strip()
            description = str(item.get("description", "")).strip() if "description" in item else ""
            price_pln, raw_price, currency = self.price_in_pln(item)

            if price_pln > self.config.max_price_pln or not self.matches(title, description):
                continue

            url = str(item.get("url", VINTED_HOME_URL))
            self.send_telegram(self.format_alert(title, description, price_pln, raw_price, currency, url))
            print(f"✅ Alert wysłany [{price_pln:.2f} PLN]: {title}")

        if is_first_run:
            self.send_telegram("🤖 <b>Ligobot LEGO aktywowany!</b>")
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
