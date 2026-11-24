"""Statistiques d'utilisation de la borne (v1.4) -- Admin > Estadísticas.

Voir docs/cahier-des-charges-statistiques.md (definitions validees par Fabien).

ENREGISTREMENT (StatsRecorder) : la borne ne modifie aucun jeu. Le
GameController passe a observe() un instantane de son etat a CHAQUE
changement d'ecran (_broadcast_state) ; le recorder en deduit :
  - les visites : de la sortie de veille au retour en veille ;
  - les parties : debut (nouvelle manche), fin (ecran de fin = « finie »,
    sinon « abandon ») et score ;
  - les reponses (juste / faux) question par question ;
  - les consultations d'objets (Descoberta) et aprene.
Les jeux retro du centre de jòcs sont signales par blueprints/jocs.py
(start_rom / end_rom) : l'etat de la borne ne change pas pendant qu'on y joue.
Anonyme : heure, jeu, duree, fin, score -- rien sur les joueurs.

Fin par mise en veille (inactivite) : le temps d'inactivite n'est pas compte
(fin = dernier evenement, ou heure de mise en veille moins le delai
d'inactivite). Coupure de courant : les lignes restees ouvertes sont closes
au demarrage suivant (abandon, fin = dernier signe de vie).

CALCULS (overview, day, activity_detail...) : a l'affichage, en Python sur
les parties de la periode ; une partie a cheval sur deux heures est repartie
entre les deux. Detail garde 2 ans (KEEP_DAYS), puis resume par jour dans
stats_daily.
"""

import csv
import datetime
import io
import logging
import os
import sqlite3
import statistics
import threading

import config

logger = logging.getLogger(__name__)

KEEP_DAYS = 730
FMT = "%Y-%m-%d %H:%M:%S"

# Ordre et couleurs fixes (palette verifiee pour le daltonisme, voir
# docs/cahier-des-charges-statistiques.md) ; « group » : couleur et ligne des
# graphiques (aprene et jeux retro regroupes en « Jòcs amagats »).
ACTIVITIES = {
    "descoberta": {"label": "Descoberta (objèctes)", "group": "descoberta", "scored": False},
    "vertadier": {"label": "Ven de l'occitan ?", "group": "vertadier", "scored": True},
    "duel_occitan": {"label": "Duèl Occitan", "group": "duel_occitan", "scored": True},
    "memoria": {"label": "Memòria", "group": "memoria", "scored": False},
    "memoria_vilatge": {"label": "Vilatges (Memòria)", "group": "memoria_vilatge", "scored": False},
    "quiz_calandreta": {"label": "Quiz Calandreta", "group": "quiz_calandreta", "scored": True},
    "troba_objecte": {"label": "Tròba l'objècte", "group": "troba_objecte", "scored": True},
    "aprene": {"label": "aprene", "group": "jocs_amagats", "scored": False},
    "jocs": {"label": "Centre de jòcs", "group": "jocs_amagats", "scored": False},
}
GROUPS = [
    ("descoberta", "Descoberta (objèctes)", "#2a78d6"),
    ("vertadier", "Ven de l'occitan ?", "#eb6834"),
    ("duel_occitan", "Duèl Occitan", "#1baf7a"),
    ("memoria", "Memòria", "#eda100"),
    ("memoria_vilatge", "Vilatges (Memòria)", "#e87ba4"),
    ("quiz_calandreta", "Quiz Calandreta", "#008300"),
    ("troba_objecte", "Tròba l'objècte", "#6250d6"),
    ("jocs_amagats", "Jòcs amagats", "#e34948"),
]
GROUP_COLOR = {key: color for key, _, color in GROUPS}
# Parties « jouees » (les consultations d'objets ne sont pas des parties).
GAMES = [key for key in ACTIVITIES if key != "descoberta"]
WITH_END = ("troba_objecte", "vertadier", "duel_occitan", "memoria", "memoria_vilatge", "quiz_calandreta")

_STATE_ACTIVITY = {
    "troba": "troba_objecte", "troba_fin": "troba_objecte",
    "vertadier": "vertadier", "vertadier_fin": "vertadier",
    "duel": "duel_occitan", "duel_fin": "duel_occitan",
    "quiz": "quiz_calandreta", "quiz_fin": "quiz_calandreta",
    "memoria": "memoria", "memoria_fin": "memoria",
    "memoria_vilatge": "memoria", "memoria_vilatge_fin": "memoria",
}
# Ou trouver les questions de chaque jeu dans l'instantane du GameController.
_ITEMS = {
    "troba_objecte": ("troba", "words", "name_oc"),
    "vertadier": ("vertadier", "words", "word_fr"),
    "quiz_calandreta": ("quiz", "questions", "question_fr"),
    "duel_occitan": ("duel", "questions", "question_fr"),
}


def now():
    return datetime.datetime.now().replace(microsecond=0)


def _fmt(moment):
    return moment.strftime(FMT)


def _parse(text):
    return datetime.datetime.strptime(text, FMT)


def _connect():
    conn = sqlite3.connect(config.DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


# --- Enregistrement ------------------------------------------------------------------

class StatsRecorder:
    def __init__(self, app=None):
        self.app = app
        self._lock = threading.Lock()
        self.visit_id = None
        self.session = None  # {id, activity, key, feedback, finished}
        try:
            self.recover()
            purge()
        except sqlite3.Error:
            logger.exception("Statistiques : reprise au demarrage impossible")

    # Appele par le GameController a chaque changement d'ecran.
    def observe(self, snap):
        try:
            with self._lock:
                self._observe(snap, now())
        except Exception:  # jamais de plantage de la borne a cause des statistiques
            logger.exception("Statistiques : evenement non enregistre")

    def _observe(self, snap, t):
        state = snap.get("state")
        conn = _connect()
        try:
            if state == "veille":
                end = _fmt(t - datetime.timedelta(seconds=config.IDLE_TIMEOUT_SECONDS))
                self._close_session(conn, t, idle_end=end)
                self._close_visit(conn, t, idle_end=end)
                return
            if self.visit_id is None:
                cur = conn.execute("INSERT INTO stats_visits (started_at, last_seen) VALUES (?, ?)", (_fmt(t), _fmt(t)))
                self.visit_id = cur.lastrowid
            else:
                conn.execute("UPDATE stats_visits SET last_seen = ? WHERE id = ?", (_fmt(t), self.visit_id))

            activity, key, detail = self._identify(snap)
            if activity == "keep":
                if self.session:
                    conn.execute("UPDATE stats_sessions SET last_seen = ? WHERE id = ?", (_fmt(t), self.session["id"]))
                return
            if self.session and self.session["key"] != key:
                self._close_session(conn, t)
            if activity is None:
                return
            fin = state.endswith("_fin")
            if self.session is None:
                if fin:
                    return  # ecran de fin sans debut observe (redemarrage...)
                self._open_session(conn, t, activity, key, detail)
            conn.execute("UPDATE stats_sessions SET last_seen = ? WHERE id = ?", (_fmt(t), self.session["id"]))
            self._record_answers(conn, snap, activity, t)
            if fin and not self.session["finished"]:
                score, total = _score(snap, activity)
                conn.execute("UPDATE stats_sessions SET ended_at = ?, outcome = 'finie', score = ?, total = ? WHERE id = ?",
                             (_fmt(t), score, total, self.session["id"]))
                self.session["finished"] = True
        finally:
            conn.commit()
            conn.close()

    def _identify(self, snap):
        """(activite, cle de la partie, detail). Une nouvelle cle = une
        nouvelle partie. "keep" : ne rien changer (centre de jòcs, dont les
        jeux sont signales par start_rom/end_rom)."""
        state, epoch = snap.get("state"), snap.get("epoch")
        if state in _STATE_ACTIVITY:
            activity = _STATE_ACTIVITY[state]
            if activity == "memoria":
                activity = (snap.get("memoria") or {}).get("activity_id") or "memoria"
            return activity, (activity, epoch), None
        if state == "descoberta":
            obj = snap.get("current_object") or {}
            return "descoberta", ("descoberta", obj.get("id"), epoch), obj.get("name_oc") or obj.get("name_fr")
        if state == "externe":
            external = snap.get("external") or {}
            if external.get("kind") == "jocs":
                return "keep", None, None
            if external.get("kind") == "aprene":
                return "aprene", ("aprene", epoch), external.get("title")
        return None, None, None

    def _open_session(self, conn, t, activity, key, detail):
        cur = conn.execute(
            "INSERT INTO stats_sessions (visit_id, activity, detail, started_at, last_seen) VALUES (?, ?, ?, ?, ?)",
            (self.visit_id, activity, detail, _fmt(t), _fmt(t)))
        self.session = {"id": cur.lastrowid, "activity": activity, "key": key, "feedback": None, "finished": False}

    def _close_session(self, conn, t, idle_end=None):
        """Partie quittee avant son ecran de fin = abandon (sauf activites
        sans notion de fin : consultation d'objet, aprene, jeu retro)."""
        session, self.session = self.session, None
        if session is None or session["finished"]:
            return
        row = conn.execute("SELECT started_at, last_seen FROM stats_sessions WHERE id = ?", (session["id"],)).fetchone()
        end = _fmt(t)
        if idle_end and row:
            end = max(row["started_at"], min(end, max(row["last_seen"], idle_end)))
        outcome = "abandon" if session["activity"] in WITH_END else None
        conn.execute("UPDATE stats_sessions SET ended_at = ?, outcome = ? WHERE id = ?", (end, outcome, session["id"]))

    def _close_visit(self, conn, t, idle_end):
        if self.visit_id is None:
            return
        row = conn.execute("SELECT started_at, last_seen FROM stats_visits WHERE id = ?", (self.visit_id,)).fetchone()
        if row:
            end = max(row["started_at"], min(_fmt(t), max(row["last_seen"], idle_end)))
            conn.execute("UPDATE stats_visits SET ended_at = ? WHERE id = ?", (end, self.visit_id))
        self.visit_id = None

    def _record_answers(self, conn, snap, activity, t):
        """Reponse = passage du retour visuel ("feedback") de rien a
        juste / faux / temps ecoule (Duèl : "revealed", deux joueurs)."""
        if activity not in _ITEMS:
            return
        game_key, list_key, label_key = _ITEMS[activity]
        game = snap.get(game_key) or {}
        feedback = game.get("feedback")
        previous, self.session["feedback"] = self.session["feedback"], feedback
        if not feedback or feedback == previous:
            return
        items = game.get(list_key) or []
        index = game.get("index", 0)
        if not 0 <= index < len(items):
            return
        item = items[index]
        if activity == "duel_occitan":
            results = [game.get(f"answered_{p}") == item.get("correct_choice") for p in ("p1", "p2")]
        else:
            results = [feedback == "correct"]
        for correct in results:
            conn.execute("INSERT INTO stats_answers (session_id, activity, item_id, label, correct, at) VALUES (?, ?, ?, ?, ?, ?)",
                         (self.session["id"], activity, item.get("id"), item.get(label_key), 1 if correct else 0, _fmt(t)))

    # --- Centre de jòcs (blueprints/jocs.py) ---------------------------------------
    def start_rom(self, title, system_label):
        detail = f"{title} ({system_label})"
        try:
            with self._lock:
                t = now()
                conn = _connect()
                try:
                    if self.session and self.session["activity"] == "jocs" and self.session["key"] == ("jocs", detail):
                        conn.execute("UPDATE stats_sessions SET last_seen = ? WHERE id = ?", (_fmt(t), self.session["id"]))
                        return
                    self._close_session(conn, t)
                    self._open_session(conn, t, "jocs", ("jocs", detail), detail)
                finally:
                    conn.commit()
                    conn.close()
        except Exception:
            logger.exception("Statistiques : lancement de jeu non enregistre")

    def end_rom(self):
        try:
            with self._lock:
                if self.session and self.session["activity"] == "jocs":
                    conn = _connect()
                    try:
                        self._close_session(conn, now())
                    finally:
                        conn.commit()
                        conn.close()
        except Exception:
            logger.exception("Statistiques : fin de jeu non enregistree")

    def recover(self):
        """Lignes restees ouvertes (coupure de courant) : closes a leur
        dernier signe de vie, parties comptees comme abandonnees."""
        conn = _connect()
        try:
            conn.execute("UPDATE stats_visits SET ended_at = last_seen WHERE ended_at IS NULL")
            conn.execute(
                "UPDATE stats_sessions SET ended_at = last_seen, outcome = CASE WHEN activity IN (%s) THEN 'abandon' ELSE NULL END "
                "WHERE ended_at IS NULL" % ",".join("?" * len(WITH_END)), WITH_END)
            conn.commit()
        finally:
            conn.close()


def _score(snap, activity):
    if activity in ("memoria", "memoria_vilatge"):
        game = snap.get("memoria") or {}
        return game.get("attempts"), game.get("total_pairs")
    game_key, list_key, _ = _ITEMS[activity]
    game = snap.get(game_key) or {}
    total = len(game.get(list_key) or [])
    if activity == "duel_occitan":
        return (game.get("score_p1") or 0) + (game.get("score_p2") or 0), 2 * total
    return game.get("score"), total


# --- Conservation ---------------------------------------------------------------------

def purge(keep_days=KEEP_DAYS, today=None):
    """Detail de plus de keep_days jours -> totaux par jour (stats_daily),
    puis efface."""
    limit = _fmt(datetime.datetime.combine((today or datetime.date.today()) - datetime.timedelta(days=keep_days),
                                           datetime.time()))
    conn = _connect()
    try:
        old = conn.execute("SELECT * FROM stats_sessions WHERE started_at < ? AND ended_at IS NOT NULL", (limit,)).fetchall()
        totals = {}
        for row in old:
            entry = totals.setdefault((row["started_at"][:10], row["activity"]), [0, 0, 0])
            entry[0] += 1
            entry[1] += 1 if row["outcome"] == "finie" else 0
            entry[2] += _seconds(row)
        for row in conn.execute("SELECT * FROM stats_visits WHERE started_at < ? AND ended_at IS NOT NULL", (limit,)):
            entry = totals.setdefault((row["started_at"][:10], "_visites"), [0, 0, 0])
            entry[0] += 1
            entry[2] += _seconds(row)
        for (day, activity), (sessions, finished, seconds) in totals.items():
            conn.execute(
                "INSERT INTO stats_daily (day, activity, sessions, finished, seconds) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(day, activity) DO UPDATE SET sessions = sessions + excluded.sessions, "
                "finished = finished + excluded.finished, seconds = seconds + excluded.seconds",
                (day, activity, sessions, finished, seconds))
        conn.execute("DELETE FROM stats_sessions WHERE started_at < ? AND ended_at IS NOT NULL", (limit,))
        conn.execute("DELETE FROM stats_visits WHERE started_at < ? AND ended_at IS NOT NULL", (limit,))
        conn.execute("DELETE FROM stats_answers WHERE at < ?", (limit,))
        conn.commit()
    finally:
        conn.close()


# --- Calculs pour l'admin --------------------------------------------------------------

def _seconds(row):
    if not row["ended_at"]:
        return 0
    return max(0, int((_parse(row["ended_at"]) - _parse(row["started_at"])).total_seconds()))


def period(name, today=None):
    """(debut inclus, fin exclue, libelle) d'une periode nommee."""
    today = today or datetime.date.today()
    start_of = lambda d: datetime.datetime.combine(d, datetime.time())  # noqa: E731
    end = start_of(today + datetime.timedelta(days=1))
    if name == "jorn":
        return start_of(today), end, "aujourd'hui"
    if name == "30":
        return start_of(today - datetime.timedelta(days=29)), end, "30 derniers jours"
    if name == "tot":
        return datetime.datetime(2000, 1, 1), end, "depuis le début"
    return start_of(today - datetime.timedelta(days=6)), end, "7 derniers jours"


def _sessions(conn, start, end, activity=None):
    query = "SELECT * FROM stats_sessions WHERE started_at >= ? AND started_at < ?"
    args = [_fmt(start), _fmt(end)]
    if activity:
        query += " AND activity = ?"
        args.append(activity)
    return conn.execute(query + " ORDER BY started_at", args).fetchall()


def _split_by_hour(row):
    """[(datetime de l'heure pleine, secondes)] : une partie a cheval sur
    deux heures compte dans les deux."""
    if not row["ended_at"]:
        return []
    start, end = _parse(row["started_at"]), _parse(row["ended_at"])
    parts = []
    while start < end:
        hour = start.replace(minute=0, second=0)
        stop = min(end, hour + datetime.timedelta(hours=1))
        parts.append((hour, (stop - start).total_seconds()))
        start = stop
    return parts


def format_duration(seconds):
    seconds = int(round(seconds or 0))
    if seconds < 60:
        return f"{seconds} s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d}"


def _rate(part, whole):
    return round(100 * part / whole) if whole else None


def _activity_rows(rows, answers_by_activity):
    out = []
    by_activity = {}
    for row in rows:
        by_activity.setdefault(row["activity"], []).append(row)
    for key, info in ACTIVITIES.items():
        items = by_activity.get(key, [])
        if not items:
            continue
        seconds = sum(_seconds(r) for r in items)
        finished = [r for r in items if r["outcome"] == "finie"]
        entry = {
            "key": key, "label": info["label"], "color": GROUP_COLOR[info["group"]],
            "count": len(items), "seconds": seconds, "duration": format_duration(seconds),
            "average": format_duration(seconds / len(items)),
            "finished": len(finished) if key in WITH_END else None,
            "finished_rate": _rate(len(finished), len(items)) if key in WITH_END else None,
            "result": None,
        }
        if info["scored"] and finished:
            good = sum(r["score"] or 0 for r in finished)
            asked = sum(r["total"] or 0 for r in finished)
            if asked:
                entry["result"] = f"{_rate(good, asked)} % de bonnes réponses"
                entry["result_value"], entry["result_label"] = f"{_rate(good, asked)} %", "de bonnes réponses"
        elif key in ("memoria", "memoria_vilatge") and finished:
            mean = statistics.mean(r["score"] or 0 for r in finished)
            entry["result"] = f"{mean:.0f} coups en moyenne"
            entry["result_value"], entry["result_label"] = f"{mean:.0f}", "coups en moyenne"
        out.append(entry)
    out.sort(key=lambda e: -e["seconds"])
    top = max((e["seconds"] for e in out), default=0)
    for entry in out:
        entry["bar"] = round(100 * entry["seconds"] / top) if top else 0
    return out


def overview(start, end):
    conn = _connect()
    try:
        rows = _sessions(conn, start, end)
        visits = conn.execute("SELECT * FROM stats_visits WHERE started_at >= ? AND started_at < ?",
                              (_fmt(start), _fmt(end))).fetchall()
        daily = conn.execute("SELECT activity, SUM(sessions) AS s, SUM(finished) AS f, SUM(seconds) AS sec "
                             "FROM stats_daily WHERE day >= ? AND day < ? GROUP BY activity",
                             (start.date().isoformat(), end.date().isoformat())).fetchall()
    finally:
        conn.close()
    games = [r for r in rows if r["activity"] in GAMES]
    finished = [r for r in games if r["outcome"] == "finie"]
    with_end = [r for r in games if r["activity"] in WITH_END]
    play_seconds = sum(_seconds(r) for r in rows)
    visit_seconds = [_seconds(v) for v in visits if v["ended_at"]]
    old = {r["activity"]: r for r in daily}
    old_visits = old.pop("_visites", None)
    old_games = sum(r["s"] for k, r in old.items() if k in GAMES)

    # Heure par heure (24 h) et grille jour de la semaine x heure, en minutes.
    by_hour = [[0.0] * len(GROUPS) for _ in range(24)]
    week = [[0.0] * 24 for _ in range(7)]
    group_index = {key: i for i, (key, _, _) in enumerate(GROUPS)}
    for row in rows:
        g = group_index[ACTIVITIES.get(row["activity"], ACTIVITIES["jocs"])["group"]]
        for hour, seconds in _split_by_hour(row):
            by_hour[hour.hour][g] += seconds / 60
            week[hour.weekday()][hour.hour] += seconds / 60

    return {
        "kpis": {
            "visits": len(visits) + (old_visits["s"] if old_visits else 0),
            "games": len(games) + old_games,
            "per_visit": f"{len(games) / len(visits):.1f}".replace(".", ",") if visits else None,
            "finished": len(finished) + sum(r["f"] for k, r in old.items() if k in GAMES),
            "finished_rate": _rate(len(finished), len(with_end)),
            "play": format_duration(play_seconds + sum(r["sec"] for r in old.values())),
            "visit_median": format_duration(statistics.median(visit_seconds)) if visit_seconds else "—",
            "consultations": sum(1 for r in rows if r["activity"] == "descoberta"),
        },
        "hours_chart": _stacked_chart(by_hour),
        "week_chart": _heatmap(week),
        "activities": _activity_rows(rows, None),
        "has_old_totals": bool(daily),
        "empty": not rows and not visits,
    }


def _stacked_chart(by_hour):
    """Geometrie du graphique en barres empilees (SVG, 24 heures)."""
    width, height, left, bottom, top = 1000, 250, 44, 24, 24
    totals = [sum(row) for row in by_hour]
    peak = max(totals) or 1
    step = _nice_step(peak)
    scale_max = step * (int(peak // step) + 1)
    slot = (width - left) / 24
    bar = slot * 0.72
    y = lambda v: (height - bottom) - v * (height - bottom - top) / scale_max  # noqa: E731
    bars, labels = [], []
    for hour, row in enumerate(by_hour):
        x = left + hour * slot + (slot - bar) / 2
        acc = 0.0
        for g, minutes in enumerate(row):
            if minutes < 0.05:
                continue
            y0, y1 = y(acc), y(acc + minutes)
            bars.append({"x": round(x, 1), "y": round(y1 + 1, 1), "w": round(bar, 1), "h": round(max(0.5, y0 - y1 - 2), 1),
                         "color": GROUPS[g][2], "title": f"{hour} h – {GROUPS[g][1]} : {format_duration(minutes * 60)}"})
            acc += minutes
        labels.append({"x": round(x + bar / 2, 1), "text": f"{hour}", "total": round(totals[hour]),
                       "title": f"{hour} h : {format_duration(totals[hour] * 60)} de jeu"})
    grid = [{"y": round(y(v), 1), "text": str(int(v))} for v in range(0, int(scale_max) + 1, int(step))]
    return {"width": width, "height": height, "bars": bars, "labels": labels, "grid": grid, "left": left,
            "empty": peak <= 1 and not any(totals)}


def _nice_step(peak):
    for step in (1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1200):
        if peak / step <= 5:
            return step
    return 3000


def _heatmap(week):
    days = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
    peak = max(max(row) for row in week) or 1
    cells = []
    for d, row in enumerate(week):
        for h, minutes in enumerate(row):
            level = minutes / peak
            cells.append({"d": d, "h": h, "minutes": round(minutes), "level": round(level, 2),
                          "fill": f"rgba(42,120,214,{0.15 + 0.85 * level:.2f})" if minutes >= 0.5 else None,
                          "title": f"{days[d]} {h} h : {format_duration(minutes * 60)} de jeu"})
    return {"days": days, "cells": cells}


def day(date):
    start = datetime.datetime.combine(date, datetime.time())
    end = start + datetime.timedelta(days=1)
    data = overview(start, end)
    conn = _connect()
    try:
        rows = _sessions(conn, start, end)
        visits = conn.execute("SELECT started_at FROM stats_visits WHERE started_at >= ? AND started_at < ? ORDER BY started_at",
                              (_fmt(start), _fmt(end))).fetchall()
    finally:
        conn.close()
    hours = []
    for h in range(24):
        h_start, h_end = start + datetime.timedelta(hours=h), start + datetime.timedelta(hours=h + 1)
        in_hour = [r for r in rows if _fmt(h_start) <= r["started_at"] < _fmt(h_end)]
        minutes = {}
        for row in rows:
            for hour, seconds in _split_by_hour(row):
                if hour == h_start:
                    minutes[row["activity"]] = minutes.get(row["activity"], 0) + seconds
        if not in_hour and not minutes:
            continue
        top = max(minutes, key=minutes.get) if minutes else None
        hours.append({
            "label": f"{h} h – {h + 1} h",
            "visits": sum(1 for v in visits if _fmt(h_start) <= v["started_at"] < _fmt(h_end)),
            "games": sum(1 for r in in_hour if r["activity"] in GAMES),
            "finished": sum(1 for r in in_hour if r["outcome"] == "finie"),
            "consultations": sum(1 for r in in_hour if r["activity"] == "descoberta"),
            "play": format_duration(sum(minutes.values())),
            "top": ACTIVITIES[top]["label"] if top else None,
            "top_color": GROUP_COLOR[ACTIVITIES[top]["group"]] if top else None,
        })
    data.update({
        "timeline": _timeline(rows, start),
        "hours": hours,
        "journal": [_journal_row(r) for r in rows],
        "first_visit": _hm(visits[0]["started_at"]) if visits else None,
    })
    return data


def _timeline(rows, day_start):
    """Frise de la journee : une ligne par jeu, chaque partie de son debut a sa
    fin. Axe resserre sur les heures utilisees (au moins 8 h - 18 h)."""
    used = [r for r in rows if r["ended_at"]]
    first = min([_parse(r["started_at"]).hour for r in used] + [8])
    last = max([_parse(r["ended_at"]).hour + 1 for r in used] + [18])
    last = min(24, max(last, first + 1))
    width, left, row_h, top = 1000, 190, 30, 10
    span = (last - first) * 3600
    x = lambda moment: left + (moment - day_start - datetime.timedelta(hours=first)).total_seconds() * (width - left - 10) / span  # noqa: E731
    activities = [key for key in ACTIVITIES if any(r["activity"] == key for r in used)]
    marks = []
    for row in used:
        start, end = _parse(row["started_at"]), _parse(row["ended_at"])
        i = activities.index(row["activity"])
        x0 = x(start)
        title = f"{ACTIVITIES[row['activity']]['label']}{' – ' + row['detail'] if row['detail'] else ''} · " \
                f"{start:%H:%M} → {end:%H:%M} · {format_duration(_seconds(row))}" + _outcome_text(row)
        marks.append({"x": round(x0, 1), "y": top + i * row_h + 5, "w": round(max(4, x(end) - x0), 1), "h": row_h - 10,
                      "color": GROUP_COLOR[ACTIVITIES[row["activity"]]["group"]],
                      "hatched": row["outcome"] == "abandon", "title": title})
    height = top + len(activities) * row_h + 26
    ticks = [{"x": round(x(day_start + datetime.timedelta(hours=h)), 1), "text": f"{h} h"} for h in range(first, last + 1)]
    lines = [{"y": top + i * row_h + row_h / 2 + 4, "text": ACTIVITIES[key]["label"]} for i, key in enumerate(activities)]
    return {"width": width, "height": height, "marks": marks, "ticks": ticks, "rows": lines, "left": left,
            "axis_y": height - 8, "empty": not used}


def _outcome_text(row):
    if row["outcome"] == "finie":
        result = _result_text(row)
        return " · finie" + (f" · {result}" if result else "")
    if row["outcome"] == "abandon":
        return " · abandonnée"
    return ""


def _result_text(row):
    if row["outcome"] != "finie" or row["score"] is None:
        return ""
    if row["activity"] in ("memoria", "memoria_vilatge"):
        return f"{row['score']} coups ({row['total']} paires)"
    return f"{row['score']} / {row['total']}"


def _hm(text):
    """"2026-11-24 09:05:00" -> "9 h 05"."""
    return f"{int(text[11:13])} h {text[14:16]}"


def _journal_row(row):
    return {
        "start": _hm(row["started_at"]),
        "activity": ACTIVITIES.get(row["activity"], {"label": row["activity"]})["label"],
        "color": GROUP_COLOR[ACTIVITIES.get(row["activity"], ACTIVITIES["jocs"])["group"]],
        "detail": row["detail"] or "",
        "duration": format_duration(_seconds(row)) if row["ended_at"] else "en cours",
        "outcome": row["outcome"],
        "result": _result_text(row),
    }


def activity_detail(activity, start, end):
    conn = _connect()
    try:
        rows = _sessions(conn, start, end, activity)
        answers = conn.execute(
            "SELECT item_id, label, COUNT(*) AS asked, SUM(correct) AS good FROM stats_answers "
            "WHERE activity = ? AND at >= ? AND at < ? GROUP BY item_id, label", (activity, _fmt(start), _fmt(end))).fetchall()
    finally:
        conn.close()
    info = ACTIVITIES[activity]
    finished = [r for r in rows if r["outcome"] == "finie"]
    seconds = sum(_seconds(r) for r in rows)
    missed = sorted(({"label": a["label"] or "—", "asked": a["asked"], "rate": _rate(a["good"], a["asked"])}
                     for a in answers if a["asked"] >= 3), key=lambda a: (a["rate"], -a["asked"]))[:10]
    distribution = None
    if info["scored"] and finished:
        buckets = [0] * 11
        for row in finished:
            if row["total"]:
                buckets[round(10 * (row["score"] or 0) / row["total"])] += 1
        peak = max(buckets) or 1
        distribution = [{"label": f"{10 * i} %", "count": n, "height": round(100 * n / peak)} for i, n in enumerate(buckets)]
    details = {}
    for row in rows:
        if row["detail"]:
            entry = details.setdefault(row["detail"], {"label": row["detail"], "count": 0, "seconds": 0})
            entry["count"] += 1
            entry["seconds"] += _seconds(row)
    top_details = sorted(details.values(), key=lambda d: (-d["seconds"] if activity != "descoberta" else -d["count"]))[:15]
    top = max([d["seconds"] if activity != "descoberta" else d["count"] for d in top_details] or [0])
    for entry in top_details:
        entry["duration"] = format_duration(entry["seconds"])
        value = entry["seconds"] if activity != "descoberta" else entry["count"]
        entry["bar"] = round(100 * value / top) if top else 0
    return {
        "info": info, "color": GROUP_COLOR[info["group"]],
        "count": len(rows), "finished": len(finished) if activity in WITH_END else None,
        "finished_rate": _rate(len(finished), len(rows)) if activity in WITH_END else None,
        "play": format_duration(seconds), "average": format_duration(seconds / len(rows)) if rows else "—",
        "result_value": (_activity_rows(rows, None) or [{}])[0].get("result_value"),
        "result_label": (_activity_rows(rows, None) or [{}])[0].get("result_label"),
        "distribution": distribution, "missed": missed, "details": top_details,
    }


def today_summary():
    start, end, _ = period("jorn")
    data = overview(start, end)
    return {"kpis": data["kpis"], "top": data["activities"][:3], "empty": data["empty"]}


# --- Export et effacement --------------------------------------------------------------

CSV_COLUMNS = ["date", "debut", "fin", "duree_secondes", "jeu", "detail", "fin_de_partie", "score", "total"]


def export_csv(start, end):
    """Journal des parties en CSV (point-virgule, UTF-8 avec BOM : s'ouvre tel
    quel dans un tableur francais)."""
    conn = _connect()
    try:
        rows = _sessions(conn, start, end)
    finally:
        conn.close()
    out = io.StringIO()
    out.write("﻿")
    writer = csv.writer(out, delimiter=";")
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        writer.writerow([
            row["started_at"][:10], row["started_at"][11:], (row["ended_at"] or "")[11:], _seconds(row),
            ACTIVITIES.get(row["activity"], {"label": row["activity"]})["label"], row["detail"] or "",
            {"finie": "finie", "abandon": "abandonnée"}.get(row["outcome"], ""),
            "" if row["score"] is None else row["score"], "" if row["total"] is None else row["total"],
        ])
    return out.getvalue()


def reset(recorder=None):
    """Efface toutes les statistiques apres en avoir garde le journal (CSV)
    dans sauvegardes/. Renvoie le nom du fichier de sauvegarde."""
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(config.DATABASE_PATH)), "sauvegardes")
    os.makedirs(backup_dir, exist_ok=True)
    name = f"maleta-statistiques-{now():%Y%m%d-%H%M%S}.csv"
    start, end, _ = period("tot")
    with open(os.path.join(backup_dir, name), "w", encoding="utf-8", newline="") as f:
        f.write(export_csv(start, end))
    lock = recorder._lock if recorder else threading.Lock()
    with lock:
        conn = _connect()
        try:
            for table in ("stats_answers", "stats_sessions", "stats_visits", "stats_daily"):
                conn.execute(f"DELETE FROM {table}")
            conn.commit()
        finally:
            conn.close()
        if recorder:
            recorder.visit_id = None
            recorder.session = None
    return name
