"""Point d'entree pour le developpement sur PC (Windows/Linux/Mac).

Usage :
    pip install -r requirements.txt
    python run_dev.py

Puis ouvrir http://localhost:5000/         -> l'ecran du kiosque
            http://localhost:5000/dev/panel -> panneau de test (simuler un tag)
            http://localhost:5000/admin     -> administration (PIN par defaut : 1234,
                                                a changer via MALETA_ADMIN_PIN)

Sur le petit PC de production, c'est run_pc.py qui prend le relais : il
demarre en plus le vrai lecteur NFC (OMNIKEY) et est lance par le service
systemd installe par install.sh, qui ouvre ensuite le kiosque
Chromium en plein ecran.
"""

import os
import signal

import config
from app import create_app

if __name__ == "__main__":
    # v1.03 : meme arret propre sur SIGTERM que run_pc.py (voir la-bas).
    signal.signal(signal.SIGTERM, lambda signum, frame: os._exit(0))
    app, socketio = create_app()

    print("=" * 60)
    print("La Maleta Occitana - serveur de developpement")
    print("=" * 60)
    print(f"Mode materiel      : {config.HARDWARE_MODE} (dev = pas de NFC reel)")
    print("Kiosque            : http://localhost:5000/")
    print("Panneau de test    : http://localhost:5000/dev/panel")
    print(f"Admin              : http://localhost:5000/admin  (PIN : {config.ADMIN_PIN})")
    print("=" * 60)

    # allow_unsafe_werkzeug=True : Flask-SocketIO refuse par defaut de lancer
    # le serveur de dev Werkzeug hors mode debug. Sans objet en dev normalement
    # (Flask tourne en debug), mais garde la coherence avec run_pc.py et evite
    # la meme RuntimeError si jamais debug=False est teste ici aussi.
    socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)
