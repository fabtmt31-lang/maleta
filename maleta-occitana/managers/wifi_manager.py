"""Wi-Fi de la borne depuis l'admin (v1.3) -- NetworkManager via nmcli.

Necessaire seulement pour aprene (jeu cache) : tout le reste de la borne
fonctionne sans reseau. install.sh installe NetworkManager et une regle
polkit qui autorise l'utilisateur de l'appli a gerer le Wi-Fi sans sudo.

Les mots de passe Wi-Fi sont confies a NetworkManager (fichiers systeme
lisibles par root seulement) : jamais dans la base de la Maleta, jamais
exportes, jamais reaffiches.
"""

import shutil
import subprocess

NMCLI = "nmcli"
TIMEOUT = 40  # une connexion Wi-Fi peut prendre une vingtaine de secondes


class WifiError(RuntimeError):
    """Message affichable tel quel dans l'admin."""


def available():
    return shutil.which(NMCLI) is not None


def _run(args, timeout=TIMEOUT):
    if not available():
        raise WifiError("NetworkManager n'est pas installé sur la borne (relancer install.sh).")
    try:
        result = subprocess.run([NMCLI, *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise WifiError("Le Wi-Fi ne répond pas (délai dépassé).") from exc
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip().replace("Error: ", "")
        raise WifiError(message or f"nmcli a échoué (code {result.returncode}).")
    return result.stdout


def _split(line):
    """Decoupe une ligne `nmcli -t` : champs separes par ':', avec '\\:' et
    '\\\\' pour un ':' ou un '\\' dans une valeur (ex. un nom de reseau)."""
    fields, current, escaped = [], [], False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
    fields.append("".join(current))
    return fields


def wifi_device():
    """(device, etat, connexion) de la premiere interface Wi-Fi, ou None."""
    for line in _run(["-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"]).splitlines():
        device, kind, state, connection = (_split(line) + ["", "", "", ""])[:4]
        if kind == "wifi":
            return device, state, connection
    return None


def status():
    """{"available", "device", "connected", "network", "ip", "message"}."""
    if not available():
        return {"available": False, "message": "NetworkManager n'est pas installé sur la borne (relancer install.sh)."}
    try:
        found = wifi_device()
    except WifiError as exc:
        return {"available": False, "message": str(exc)}
    if found is None:
        return {"available": False, "message": "Aucune carte Wi-Fi détectée sur la borne."}
    device, state, connection = found
    connected = state.startswith("connected") or state.startswith("connecté")
    ip = ""
    if connected:
        try:
            ip = _run(["-g", "IP4.ADDRESS", "device", "show", device]).split("|")[0].strip().split("/")[0]
        except WifiError:
            ip = ""
    return {"available": True, "device": device, "connected": connected,
            "network": connection if connected else "", "ip": ip, "message": ""}


def scan(rescan=True):
    """Reseaux visibles, du plus fort au plus faible, un par nom :
    [{"ssid", "signal", "security", "in_use", "saved"}]."""
    args = ["-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list"]
    if rescan:
        args += ["--rescan", "yes"]
    saved = saved_networks()
    networks = {}
    for line in _run(args).splitlines():
        in_use, ssid, signal, security = (_split(line) + ["", "", "", ""])[:4]
        if not ssid:
            continue  # reseau cache : se connecter avec son nom ("Réseau caché")
        try:
            signal = int(signal)
        except ValueError:
            signal = 0
        current = networks.get(ssid)
        if current is None or signal > current["signal"] or in_use == "*":
            networks[ssid] = {"ssid": ssid, "signal": signal, "security": security or "ouvert",
                              "in_use": in_use == "*" or (current or {}).get("in_use", False),
                              "saved": ssid in saved}
    return sorted(networks.values(), key=lambda n: (not n["in_use"], -n["signal"]))


def saved_networks():
    names = set()
    for line in _run(["-t", "-f", "NAME,TYPE", "connection", "show"]).splitlines():
        name, kind = (_split(line) + ["", ""])[:2]
        if kind in ("802-11-wireless", "wifi"):
            names.add(name)
    return names


def connect(ssid, password="", hidden=False):
    ssid = (ssid or "").strip()
    if not ssid:
        raise WifiError("Nom du réseau manquant.")
    args = ["device", "wifi", "connect", ssid]
    if password:
        args += ["password", password]
    if hidden:
        args += ["hidden", "yes"]
    _run(args)


def forget(ssid):
    _run(["connection", "delete", "id", ssid])


def disconnect():
    found = wifi_device()
    if found:
        _run(["device", "disconnect", found[0]])


def bars(signal):
    """Force du signal en 0 a 4 barres (affichage)."""
    return 4 if signal >= 75 else 3 if signal >= 50 else 2 if signal >= 30 else 1 if signal > 0 else 0
