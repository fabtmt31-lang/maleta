"""CRUD du contenu du jeu "Quiz Calandreta" (v0.8, quiz solo a 3 reponses).

Même esprit que duel_manager.py/vertadier_manager.py : pas d'ORM, accès
direct via get_db(). Aucun contenu n'est pré-rempli à la livraison -- voir
concept-borne-interactive.md ("Décisions de contenu et nouvelles
activités (15/09/2026)") : la liste de questions doit être construite avec
une source fiable (linguiste, IEO, CNRTL...), jamais improvisée au moment
du développement. C'est Fabien qui saisit les questions depuis cette
interface, une fois leur contenu vérifié.

`correct_choice` vaut toujours "a", "b" ou "c" (jamais autre chose) --
validé à l'écriture par _normalize_choice() plutôt que côté appelant, pour
qu'aucune valeur incohérente ne puisse atteindre la base (même principe que
duel_manager.py, généralisé à 3 choix).
"""

from db.database import get_db


def list_questions(only_active=False):
    db = get_db()
    query = "SELECT * FROM quiz_questions"
    if only_active:
        query += " WHERE active = 1"
    query += " ORDER BY sort_order ASC, id ASC"
    return db.execute(query).fetchall()


def get_question(question_id):
    db = get_db()
    return db.execute("SELECT * FROM quiz_questions WHERE id = ?", (question_id,)).fetchone()


def create_question(question_fr, choice_a, choice_b, choice_c, correct_choice,
                     explanation=None, source=None):
    db = get_db()
    max_order = db.execute("SELECT MAX(sort_order) AS m FROM quiz_questions").fetchone()["m"]
    sort_order = (max_order or 0) + 1
    cur = db.execute(
        """
        INSERT INTO quiz_questions
            (question_fr, choice_a, choice_b, choice_c, correct_choice, explanation, source, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            question_fr,
            choice_a,
            choice_b,
            choice_c,
            _normalize_choice(correct_choice),
            explanation,
            source,
            sort_order,
        ),
    )
    db.commit()
    return cur.lastrowid


def update_question(question_id, question_fr, choice_a, choice_b, choice_c,
                     correct_choice, explanation, source, active):
    db = get_db()
    db.execute(
        """
        UPDATE quiz_questions
        SET question_fr = ?, choice_a = ?, choice_b = ?, choice_c = ?, correct_choice = ?,
            explanation = ?, source = ?, active = ?
        WHERE id = ?
        """,
        (
            question_fr,
            choice_a,
            choice_b,
            choice_c,
            _normalize_choice(correct_choice),
            explanation,
            source,
            1 if active else 0,
            question_id,
        ),
    )
    db.commit()


def delete_question(question_id):
    db = get_db()
    db.execute("DELETE FROM quiz_questions WHERE id = ?", (question_id,))
    db.commit()


def set_question_active(question_id, active):
    db = get_db()
    db.execute("UPDATE quiz_questions SET active = ? WHERE id = ?", (1 if active else 0, question_id))
    db.commit()


def _normalize_choice(correct_choice):
    value = str(correct_choice).strip().lower()
    if value not in ("a", "b", "c"):
        raise ValueError(f"correct_choice doit valoir 'a', 'b' ou 'c' (recu : {correct_choice!r})")
    return value
