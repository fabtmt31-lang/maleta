"""Acces SQLite - pas d'ORM, meme choix que sur Histoires du Soir.

Un connexion par requete (via `get_db()`), fermee automatiquement a la fin
de la requete Flask par `close_db` (enregistre dans app.py). Cela evite les
soucis de connexion SQLite partagee entre threads (important ici car le
lecteur NFC et le poll manette tournent dans des threads a part).
"""

import sqlite3

from flask import g

import config


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(config.DATABASE_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Cree les tables si elles n'existent pas encore. Ne supprime jamais rien."""
    with open(config.SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = f.read()
    conn = sqlite3.connect(config.DATABASE_PATH)
    try:
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()
