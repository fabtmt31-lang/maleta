"""Centre de jòcs (v1.3, jeu cache) : pages affichees par le navigateur de
la borne pendant que le centre est lance depuis Admin > Jòcs amagats.

/jocs/          liste des jeux (tuiles), navigation manette/clavier
/jocs/joc/<id>  partie (EmulatorJS, servi en local)

Ces pages ne sont accessibles QUE pendant que le centre de jòcs est lance
(etat STATE_EXTERNE, kind "jocs") : sinon, retour a l'ecran de la borne.
"""

from flask import Blueprint, abort, current_app, redirect, render_template, send_from_directory, url_for

import config
from managers import rom_manager, settings_manager

jocs_bp = Blueprint("jocs", __name__)

# Boutons de l'interface d'EmulatorJS : tous masques (la borne se joue a la
# manette, Echap pour sortir).
EMULATORJS_BUTTONS = {name: False for name in (
    "playPause", "play", "pause", "restart", "mute", "unmute", "settings", "fullscreen",
    "enterFullscreen", "exitFullscreen", "saveState", "loadState", "screenRecord", "gamepad",
    "cheat", "volumeSlider", "saveSavFiles", "loadSavFiles", "quickSave", "quickLoad",
    "screenshot", "cacheManager", "exitEmulation", "netplay", "diskButton", "rightClick",
)}


def _running():
    status = current_app.extensions["game_controller"].external_status()
    return bool(status and status.get("kind") == "jocs")


def _page_context():
    branding = settings_manager.get_branding()
    return {"branding": branding, "template": branding["theme"], "texts": settings_manager.get_kiosk_texts()}


@jocs_bp.route("/")
def centre():
    if not _running():
        return redirect(url_for("kiosk.index"))
    games = [
        {
            "id": rom["id"], "title": rom["title"], "players": rom["players"],
            "system": rom_manager.SYSTEMS[rom["system"]]["label"],
            "cover": url_for("jocs.cover", filename=rom["cover_filename"]) if rom["cover_filename"] else None,
            "url": url_for("jocs.play", rom_id=rom["id"]),
        }
        for rom in rom_manager.list_roms(only_active=True)
        if rom["system"] in rom_manager.SYSTEMS
    ]
    return render_template("jocs/centre.html", games=games, **_page_context())


@jocs_bp.route("/joc/<int:rom_id>")
def play(rom_id):
    if not _running():
        return redirect(url_for("kiosk.index"))
    rom = rom_manager.get_rom(rom_id)
    if rom is None or not rom["active"] or rom["system"] not in rom_manager.SYSTEMS:
        return redirect(url_for("jocs.centre"))
    system = rom_manager.SYSTEMS[rom["system"]]
    return render_template(
        "jocs/joc.html",
        rom=rom,
        core=system["core"],
        control_scheme=system["scheme"],
        rom_url=url_for("jocs.rom_file", rom_id=rom_id),
        controls=rom_manager.emulatorjs_controls(rom["system"]),
        buttons=EMULATORJS_BUTTONS,
        diagnostic=rom_manager.get_diagnostic(),
        retroarch_cfg=rom_manager.retroarch_extra_config(),
        quit_combo=rom_manager.get_quit_combo(),
        quit_combo_label=rom_manager.quit_combo_label(),
        **_page_context(),
    )


@jocs_bp.route("/rom/<int:rom_id>")
def rom_file(rom_id):
    if not _running():
        abort(404)
    rom = rom_manager.get_rom(rom_id)
    if rom is None:
        abort(404)
    return send_from_directory(config.ROMS_DIR, rom["filename"], mimetype="application/octet-stream")


@jocs_bp.route("/jaquette/<path:filename>")
def cover(filename):
    return send_from_directory(config.ROM_COVERS_DIR, filename)
