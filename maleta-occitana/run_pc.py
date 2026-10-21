"""Point d'entree pour le petit PC Debian de production.

Remplace le `run_pi.py` qui restait a ecrire (§ "pas encore fait" de l'etape
1) -- renomme pour coller a la nouvelle cible materielle decidee le
13/09/2026 (petit PC au lieu du Raspberry Pi), mais le role est le meme :
demarrer l'app Flask/SocketIO, prete a etre appelee par le service systemd
(voir install.sh) puis affichee par Chromium en mode kiosque une fois
le serveur pret.

A la difference de run_dev.py (ecoute sur 0.0.0.0, pratique pour tester
depuis un autre appareil du reseau pendant le developpement), ce point
d'entree ecoute sur 127.0.0.1 uniquement : decision deja actee dans le
concept ("administration en local sur la borne, pas d'acces web a distance"),
l'admin n'ayant plus besoin d'etre joignable depuis un autre appareil.

Usage (normalement lance par le service systemd, pas a la main) :
    MALETA_HARDWARE=pc venv/bin/python run_pc.py
"""

import logging
import os
import signal

import config
from app import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# v1.03 : adresse d'ecoute reglable sans toucher au code -- 127.0.0.1 par
# defaut (seul Chromium, sur la borne elle-meme, s'y connecte ; acces a
# distance possible par tunnel SSH : ssh -L 5000:localhost:5000 ...). Mettre
# MALETA_HOST=0.0.0.0 dans le service systemd (voir install.sh) pour ouvrir
# l'admin aux autres appareils du reseau -- a faire en connaissance de cause :
# le PIN est alors la seule protection.
HOST = os.environ.get("MALETA_HOST", "127.0.0.1")
PORT = 5000


def _exit_on_sigterm(signum, frame):
    """v1.03 (revue de code) : arret propre et immediat sur SIGTERM (envoye
    par `systemctl stop/restart`). Installe AVANT create_app(), donc avant
    que pygame/SDL ne demarre : SDL n'installe son propre gestionnaire que
    si le signal a encore son comportement par defaut -- c'est ce
    gestionnaire SDL qui avalait le SIGTERM et obligeait systemd a attendre
    10 s puis a tuer le process (SIGKILL), visible dans le journal."""
    # os._exit plutot que sys.exit : sortie immediate garantie, meme si un
    # thread de bibliotheque (pyscard, pygame...) n'etait pas "daemon" -- rien
    # a sauvegarder a ce moment-la (chaque ecriture SQLite est deja validee).
    logger.info("SIGTERM recu - arret du service")
    logging.shutdown()
    os._exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _exit_on_sigterm)
    app, socketio = create_app()

    logger.info("La Maleta Occitana - demarrage sur http://%s:%s", HOST, PORT)
    logger.info("Mode materiel : %s", config.HARDWARE_MODE)

    # allow_unsafe_werkzeug=True : Flask-SocketIO refuse par defaut de lancer
    # le serveur de dev Werkzeug hors mode debug ("The Werkzeug web server is
    # not designed to run in production"). Ici c'est le comportement voulu :
    # serveur local (127.0.0.1 uniquement), un seul visiteur a la fois (la
    # borne elle-meme), pas d'exposition reseau -- un vrai serveur WSGI
    # (eventlet/gunicorn) serait une complexite inutile pour ce cas d'usage.
    socketio.run(app, host=HOST, port=PORT, debug=False, allow_unsafe_werkzeug=True)
