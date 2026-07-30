import os
import time
import html
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any
from curl_cffi import requests as cffi_requests

# ---------------------------------------------------------------------------
# Constants & Rules
# ---------------------------------------------------------------------------

DEFAULT_VINTED_URL = (
    "https://www.vinted.pl/api/v2/catalog/items"
    "?search_text=lego&order=newest_first&per_page=96"
)
VINTED_HOME_URL = "https://www.vinted.pl/"
SEEN_FILE = "seen_ids.txt"

# Rygorystyczne grupy fraz: WSZYSTKIE słowa z danej grupy muszą wystąpić w ogłoszeniu
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

# ---------------------------------------------------------------------------
# Serwer HTTP dla Render 24/7
# ---------------------------------------------------------------------------
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Ligobot LEGO dziala 24/7!")

def run_server():
    server_address = ('0.0.0.0', 10000)
    httpd = HTTPServer(server_address, SimpleHandler)
    print("Serwer HTTP wystartowal na porcie 10000")
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
    proxy_url: str = ""

    @classmethod
    def from_environment(cls) -> Config:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        proxy = os.environ.get("PROXY_URL", "").strip()

        return cls(
            telegram_bot_token=token,
            telegram_chat_id=chat_id,
            vinted_url=DEFAULT_VINTED_URL,
            max_price_pln=float(os.environ.get("MAX_CENA_PLN", "120")),
            interval_seconds=int(os.environ.get("CHECK_INTERVAL_SECONDS", "120")),
            proxy_url=proxy,
        )


class LegoDealMonitor:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.seen_ids: set[str] = self._load_seen_ids()
        self.telegram_error_reported = False
        self.last_vinted_error: str | None = None
        self._session: cffi_requests.Session | None = None
        self._bearer_token: str = ""
        self._init_session()

    def _load_seen_ids(self) -> set[str]:
        """Wczytuje zapisane ID ofert z pliku na dysku, aby restarty nie resetowały pamięci bota."""
        seen = set()
        if os.path.exists(SEEN_FILE):
            try:
                with open(SEEN_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        item_id = line.strip()
                        if item_id:
                            seen.add(item_id)
                print(f"Wczytano {len(seen)} historycznych ID z pliku {SEEN_FILE}.")
            except Exception as e:
                print(f"Błąd odczytu pliku seen_ids: {e}")
        return seen

    def _save_seen_id_to_disk(self, item_id: string_type := "") -> None:
        """Dopisuje nowe ID bezpośrednio do pliku na dysku."""
        try:
            with open(SEEN_FILE, "a", encoding="utf-8") as f:
                f.write(f"{item_id}\n")
        except Exception as e:
            print(f"Błąd zapisu ID do pliku: {e}")

    def _init_session(self) -> None:
        print("Inicjalizacja sesji Vinted przez Bright Data Proxy...")
        proxies = {"http": self.config.proxy_url, "https": self.config.proxy_url} if self.config.proxy_url else None
        
        session = cffi_requests.Session(impersonate="chrome131", proxies=proxies)
        try:
            resp = session.get(
                VINTED_HOME_URL,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
                },
                timeout=25,
            )
        except Exception as exc:
            raise RuntimeError(f"Błąd sieci przy połączeniu przez proxy: {exc}") from exc

        if resp.status_code == 407:
            raise RuntimeError("Błąd 407: Proxy wymaga uwierzytelnienia.")

        if resp.status_code == 403:
            raise RuntimeError("Cloudflare zablokowało zapytanie (403).")

        if resp.status_code == 200:
            cookies = dict(session.cookies)
            token = cookies.get("access_token_web", "")
            if token:
                self._session = session
                self._bearer_token = token
                print(f"Sesja przez proxy gotowa — pobrano token ({len(token)} znaków).")
                return

        raise RuntimeError(f"Nie udało się zainicjalizować sesji Vinted przez proxy. Status: {resp.status_code}")

    def _api_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Authorization": f"Bearer {self._bearer_token}",
            "Referer": VINTED_HOME_URL,
            "Origin": "https://www.vinted.pl",
        }

    def _refresh_session(self) -> None:
        print("Odświeżanie sesji Vinted...")
        self._init_session()

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
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(f"Telegram returned HTTP {response.status}")
            self.telegram_error_reported = False
        except Exception as error:
            if not self.telegram_error_reported:
                print(f"Telegram error: {type(error).__name__}: {error}")
                self.telegram_error_reported = True

    def fetch_items(self) -> list[dict[str, Any]]:
        assert self._session is not None
        for attempt in range(2):
            try:
                resp = self._session.get(
                    self.config.vinted_url,
                    headers=self._api_headers(),
                    timeout=20,
                )
            except Exception as exc:
                raise RuntimeError(f"Network error: {exc}") from exc

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                if not isinstance(items, list):
                    raise RuntimeError("Nieprawidłowy format odpowiedzi z API Vinted.")
                return [i for i in items if isinstance(i, dict)]

            if resp.status_code in (401, 403, 407) and attempt == 0:
                print(f"HTTP {resp.status_code} — odświeżam sesję i proxy.")
                self._refresh_session()
                continue

            raise RuntimeError(f"Vinted API zwróciło HTTP {resp.status_code}")
        raise RuntimeError("Vinted API zwróciło błąd autoryzacji.")

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
        # Łączymy tytuł i opis, zamieniamy na małe litery dla pełnej niezależności od wielkości znaków
        full_text = f"{title} {description}".casefold()
        for group in FRAZY_GRUPY:
            # Sprawdzamy czy KAŻDE słowo z danej grupy występuje w tekście (kolejność nie ma znaczenia)
            if all(word.casefold() in full_text for word in group):
                return True
        return False

    def format_alert(
        self,
        title: str,
        description: str,
        price_pln: float,
        raw_price: float,
        currency: str,
        url: str,
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
            print(f"Vinted error: {msg}")
            if msg != self.last_vinted_error:
                self.last_vinted_error = msg
            return

        if self.last_vinted_error is not None:
            self.last_vinted_error = None

        # Jeśli to pierwsze uruchomienie i plik seen_ids.txt był pusty, wrzucamy obecne ID do bazy,
        # żeby odciąć przeszłość i nie spamować starymi ogłoszeniami z pierwszego pobrania.
        is_first_run = len(self.seen_ids) == 0

        for item in reversed(items):
            if "id" not in item:
                continue
            item_id = str(item["id"])
            
            if item_id in self.seen_ids:
                continue
            
            # Zapisujemy w pamięci i na dysku, żeby uniknąć duplikatów przy restartach
            self.seen_ids.add(item_id)
            self._save_seen_id_to_disk(item_id)

            if is_first_run:
                # Przy całkowicie pierwszym uruchomieniu tylko kolekcjonujemy ID, nic nie wysyłamy
                continue

            title = str(item.get("title", "")).strip()
            description = str(item.get("description", "")).strip()
            price_pln, raw_price, currency = self.price_in_pln(item)

            # 1. Filtr ceny (maksymalnie 120 zł)
            if price_pln > self.config.max_price_pln:
                continue

            # 2. Rygorystyczny filtr fraz (WSZYSTKIE słowa z grupy muszą wystąpić)
            if not self.matches(title, description):
                continue

            url = str(item.get("url", VINTED_HOME_URL))
            self.send_telegram(
                self.format_alert(title, description, price_pln, raw_price, currency, url)
            )
            print(f"✅ Alert wysłany [{price_pln:.2f} PLN]: {title}")

        if is_first_run:
            self.send_telegram(
                "🤖 <b>Ligobot LEGO aktywowany z trwałą pamięcią!</b>\n"
                "Od teraz monitoruję tylko świeże okazje (cena <= 120 zł, rygorystyczne frazy)."
            )
            print(f"Inicjalizacja zakończona. Zindeksowano {len(self.seen_ids)} ofert startowych.")

    def run(self) -> None:
        print("Uruchamianie monitora okazji LEGO przez Bright Data...")
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
