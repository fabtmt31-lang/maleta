"""CRUD du contenu du jeu "Memòria vilatge" (v0.8).

Même esprit que vertadier_manager.py/duel_manager.py : pas d'ORM, accès
direct via get_db(). Aucun contenu n'est pré-rempli à la livraison -- voir
concept-borne-interactive.md ("Memòria vilatge") : la liste de villes/
vilatges (nom français + nom occitan) doit être construite avec une source
fiable (linguiste, Institut d'Estudis Occitan, CNRTL...), jamais improvisée
au moment du développement. C'est Fabien qui saisit les noms depuis cette
interface, une fois leur graphie occitane vérifiée.
"""

from db.database import get_db


def list_villages(only_active=False):
    db = get_db()
    query = "SELECT * FROM villages"
    if only_active:
        query += " WHERE active = 1"
    query += " ORDER BY sort_order ASC, id ASC"
    return db.execute(query).fetchall()


def get_village(village_id):
    db = get_db()
    return db.execute("SELECT * FROM villages WHERE id = ?", (village_id,)).fetchone()


def create_village(name_fr, name_oc, source=None):
    db = get_db()
    max_order = db.execute("SELECT MAX(sort_order) AS m FROM villages").fetchone()["m"]
    sort_order = (max_order or 0) + 1
    cur = db.execute(
        """
        INSERT INTO villages (name_fr, name_oc, source, sort_order)
        VALUES (?, ?, ?, ?)
        """,
        (name_fr, name_oc, source, sort_order),
    )
    db.commit()
    return cur.lastrowid


def update_village(village_id, name_fr, name_oc, source, active):
    db = get_db()
    db.execute(
        """
        UPDATE villages
        SET name_fr = ?, name_oc = ?, source = ?, active = ?
        WHERE id = ?
        """,
        (name_fr, name_oc, source, 1 if active else 0, village_id),
    )
    db.commit()


def delete_village(village_id):
    db = get_db()
    db.execute("DELETE FROM villages WHERE id = ?", (village_id,))
    db.commit()


def set_village_active(village_id, active):
    db = get_db()
    db.execute("UPDATE villages SET active = ? WHERE id = ?", (1 if active else 0, village_id))
    db.commit()
