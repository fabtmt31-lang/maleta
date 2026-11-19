"""Jaquettes automatiques du centre de jòcs (v1.33).

Les jaquettes viennent de la base libre de vignettes de libretro
(thumbnails.libretro.com, celle de RetroArch), classee par console et par
nom de jeu "No-Intro" (ex. "Super Mario Bros. 3 (USA).png"). La borne doit
avoir acces a Internet (Admin > Wi-Fi) ; sans reseau, la recherche echoue
proprement et la jaquette reste ajoutable a la main.

Correspondance titre <-> fichier : comparaison "normalisee" (minuscules,
sans accents, sans les mentions entre parentheses, sans "The", ponctuation
ignoree), puis sans le sous-titre, puis la plus proche a 90 %, puis celle
qui contient tous les mots du titre (3 mots de plus au plus) ; parmi plusieurs versions
du meme jeu, la version France, puis Europe, puis Monde, puis USA.

La liste des jeux de chaque console (un fichier d'index de quelques Mo) est
gardee 30 jours dans media/roms/.index-jaquettes/ (jamais exporte, comme les
jeux).
"""

import difflib
import html
import os
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request

import config

BASE_URL = "https://thumbnails.libretro.com"
TIMEOUT = 20
INDEX_MAX_AGE = 30 * 24 * 3600
INDEX_MAX_BYTES = 20 * 1024 * 1024
IMAGE_MAX_BYTES = 4 * 1024 * 1024
FUZZY_CUTOFF = 0.9
USER_AGENT = "MaletaOccitana-jocs"

_REGION_ORDER = ("france", "europe", "world", "usa")
_UNWANTED = re.compile(r"\b(beta|proto|prototype|demo|sample|hack|pirate|unl|program|aftermarket)\b|\[[hbt]", re.I)


class CoverError(Exception):
    """Erreur affichable (pas de reseau, site indisponible...)."""


def normalize(name):
    name = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    name = re.sub(r"[\(\[][^\)\]]*[\)\]]", " ", name)
    name = name.replace("&", " and ")
    words = [w for w in re.split(r"[^a-z0-9]+", name) if w and w != "the"]
    return " ".join(words)


def _rank(name):
    """Plus petit = prefere : region, puis versions officielles, puis nom court."""
    tags = " ".join(re.findall(r"\(([^\)]*)\)", name)).lower()
    region = next((i for i, r in enumerate(_REGION_ORDER) if r in tags), len(_REGION_ORDER))
    return (1 if _UNWANTED.search(name) else 0, region, len(name))


def best_match(title, names):
    """Nom de fichier (sans .png) le plus proche du titre, ou None."""
    wanted = normalize(title)
    if not wanted:
        return None
    by_norm = {}
    for name in names:
        by_norm.setdefault(normalize(name), []).append(name)
    candidates = by_norm.get(wanted)
    if not candidates:
        # Titre sans son sous-titre : "Pitfall!" = "Pitfall! - Pitfall Harry's Jungle Adventure"
        candidates = [name for name in names if " - " in name and normalize(name.split(" - ")[0]) == wanted]
    if not candidates:
        close = difflib.get_close_matches(wanted, list(by_norm), n=1, cutoff=FUZZY_CUTOFF)
        candidates = by_norm[close[0]] if close else None
    if not candidates and len(wanted.split()) >= 2:
        # Tous les mots du titre, dans l'ordre, avec au plus 3 mots en plus :
        # "Zelda A Link to the Past" = "Legend of Zelda, The - A Link to the Past"
        pattern = re.compile(r"(^|.* )" + r" (?:\S+ )*?".join(map(re.escape, wanted.split())) + r"( .*|$)")
        extra = {key: len(key.split()) - len(wanted.split()) for key in by_norm if pattern.match(key)}
        extra = {key: n for key, n in extra.items() if n <= 3}
        if extra:
            fewest = min(extra.values())
            candidates = [name for key, n in extra.items() if n == fewest for name in by_norm[key]]
    if not candidates:
        return None
    return sorted(candidates, key=_rank)[0]


def _http_get(url, max_bytes):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            data = response.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        raise CoverError(f"site des jaquettes : erreur {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise CoverError("pas d'accès à Internet (vérifier le Wi-Fi dans l'admin)") from exc
    if len(data) > max_bytes:
        raise CoverError("réponse trop volumineuse")
    return data


def _system_url(libretro_dir):
    return f"{BASE_URL}/{urllib.parse.quote(libretro_dir)}/Named_Boxarts/"


def parse_index(page):
    names = []
    for href in re.findall(r'href="([^"?/][^"]*\.png)"', page):
        names.append(urllib.parse.unquote(html.unescape(href))[:-4])
    return names


def fetch_index(system_key, libretro_dir, http_get=_http_get):
    cache_dir = os.path.join(config.ROMS_DIR, ".index-jaquettes")
    cache = os.path.join(cache_dir, f"libretro-{system_key}.txt")
    try:
        if time.time() - os.path.getmtime(cache) < INDEX_MAX_AGE:
            with open(cache, encoding="utf-8") as f:
                return [line for line in f.read().split("\n") if line]
    except OSError:
        pass
    names = parse_index(http_get(_system_url(libretro_dir), INDEX_MAX_BYTES).decode("utf-8", "replace"))
    if names:
        os.makedirs(cache_dir, exist_ok=True)
        with open(cache, "w", encoding="utf-8") as f:
            f.write("\n".join(names))
    return names


def download_cover(libretro_dir, name, http_get=_http_get):
    data = http_get(_system_url(libretro_dir) + urllib.parse.quote(name + ".png"), IMAGE_MAX_BYTES)
    if not data.startswith(b"\x89PNG"):
        raise CoverError("image invalide")
    return data


class CoverSearch:
    """Recherche des jaquettes manquantes, en arriere-plan (le telechargement
    peut prendre quelques secondes par console). Une seule a la fois ;
    status() est affiche dans Admin > Jòcs amagats > Bibliotèca."""

    def __init__(self, app, http_get=None):
        self.app = app
        self.http_get = http_get or _http_get
        self._lock = threading.Lock()
        self._thread = None
        self._status = None

    def start(self, rom_ids=None):
        """rom_ids : jeux a traiter (None = tous les jeux sans jaquette).
        Renvoie False si une recherche est deja en cours."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._status = {"running": True, "found": [], "missing": [], "error": None}
            self._thread = threading.Thread(target=self._run, args=(rom_ids,), daemon=True)
            self._thread.start()
            return True

    def wait(self, timeout=None):
        thread = self._thread
        if thread:
            thread.join(timeout)

    def status(self):
        with self._lock:
            return dict(self._status) if self._status else None

    def _run(self, rom_ids):
        from managers import rom_manager
        found, missing, error = [], [], None
        try:
            with self.app.app_context():
                roms = [rom for rom in rom_manager.list_roms()
                        if rom["system"] in rom_manager.SYSTEMS and not rom["cover_filename"]
                        and (rom_ids is None or rom["id"] in rom_ids)]
                indexes = {}
                for rom in roms:
                    system = rom_manager.SYSTEMS[rom["system"]]
                    if rom["system"] not in indexes:
                        indexes[rom["system"]] = fetch_index(rom["system"], system["libretro"], self.http_get)
                    name = best_match(rom["title"], indexes[rom["system"]])
                    if name is None:
                        missing.append(rom["title"])
                        continue
                    data = download_cover(system["libretro"], name, self.http_get)
                    filename = rom_manager.save_cover_bytes(data, "png")
                    rom_manager.set_cover(rom["id"], filename)
                    found.append(rom["title"])
        except CoverError as exc:
            error = str(exc)
        except Exception as exc:  # jamais d'exception perdue dans le fil
            error = f"erreur inattendue ({exc.__class__.__name__})"
        with self._lock:
            self._status = {"running": False, "found": found, "missing": missing, "error": error}
