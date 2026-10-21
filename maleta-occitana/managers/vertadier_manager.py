"""CRUD du contenu du jeu "Ven de l'occitan (ex-« Ven de l'occitan »)" (v0.2).

Même esprit que object_manager.py/media_manager.py : pas d'ORM, accès direct
via get_db(). Aucun contenu n'est pré-rempli à la livraison -- voir
concept-borne-interactive.md ("Ven de l'occitan") : la liste doit être
construite avec une source fiable (linguiste, IEO, CNRTL...), jamais
improvisée au moment du développement. C'est Fabien qui saisit les mots
depuis cette interface, une fois leur origine vérifiée.
"""

from db.database import get_db


def list_words(only_active=False):
    db = get_db()
    query = "SELECT * FROM vertadier_words"
    if only_active:
        query += " WHERE active = 1"
    query += " ORDER BY sort_order ASC, id ASC"
    return db.execute(query).fetchall()


def get_word(word_id):
    db = get_db()
    return db.execute("SELECT * FROM vertadier_words WHERE id = ?", (word_id,)).fetchone()


def create_word(word_fr, is_occitan, explanation=None, source=None):
    db = get_db()
    max_order = db.execute("SELECT MAX(sort_order) AS m FROM vertadier_words").fetchone()["m"]
    sort_order = (max_order or 0) + 1
    cur = db.execute(
        """
        INSERT INTO vertadier_words (word_fr, is_occitan, explanation, source, sort_order)
        VALUES (?, ?, ?, ?, ?)
        """,
        (word_fr, 1 if is_occitan else 0, explanation, source, sort_order),
    )
    db.commit()
    return cur.lastrowid


def update_word(word_id, word_fr, is_occitan, explanation, source, active):
    db = get_db()
    db.execute(
        """
        UPDATE vertadier_words
        SET word_fr = ?, is_occitan = ?, explanation = ?, source = ?, active = ?
        WHERE id = ?
        """,
        (word_fr, 1 if is_occitan else 0, explanation, source, 1 if active else 0, word_id),
    )
    db.commit()


def delete_word(word_id):
    db = get_db()
    db.execute("DELETE FROM vertadier_words WHERE id = ?", (word_id,))
    db.commit()


def set_word_active(word_id, active):
    db = get_db()
    db.execute("UPDATE vertadier_words SET active = ? WHERE id = ?", (1 if active else 0, word_id))
    db.commit()
