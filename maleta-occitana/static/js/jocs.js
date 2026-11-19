// v1.3 : centre de jòcs (jeu cache, Admin > Jòcs amagats).
// - Ces pages lisent elles-memes la manette (API Gamepad du navigateur) : la
//   borne, elle, ignore ses actions pendant un jeu cache.
// - Echap : depuis le centre -> retour a la Maleta ; pendant une partie ->
//   retour au centre.
// - Si le centre est arrete (bouton « Arrêter » de l'admin...), retour
//   automatique a l'ecran de la borne.

(function () {
  if (typeof io === "function") {
    io("/kiosk").on("state_changed", (payload) => {
      if (payload.state !== "externe" || payload.kind !== "jocs") window.location.href = "/";
    });
  }
})();

function onEscape(callback) {
  // Phase de capture : passe avant EmulatorJS.
  window.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || event.repeat) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    callback();
  }, true);
}

// Manette -> evenements "up", "down", "left", "right", "ok" (front montant).
function pollGamepads(callback) {
  const previous = {};
  function read(pad) {
    const b = (i) => !!(pad.buttons[i] && pad.buttons[i].pressed);
    const ax = (i) => pad.axes[i] || 0;
    return {
      up: b(12) || ax(1) < -0.5, down: b(13) || ax(1) > 0.5,
      left: b(14) || ax(0) < -0.5, right: b(15) || ax(0) > 0.5,
      ok: b(0) || b(1) || b(2) || b(3) || b(9),
    };
  }
  function loop() {
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    for (const pad of pads) {
      if (!pad) continue;
      const state = read(pad);
      const before = previous[pad.index] || {};
      for (const name in state) {
        if (state[name] && !before[name]) callback(name);
      }
      previous[pad.index] = state;
    }
    requestAnimationFrame(loop);
  }
  requestAnimationFrame(loop);
}

function jocsCentre() {
  const PER_PAGE = 6;
  const COLUMNS = 3;
  const tiles = Array.from(document.querySelectorAll(".tile-jocs"));
  const pageLabel = document.getElementById("jocs-page");
  let index = 0;

  function render() {
    const page = Math.floor(index / PER_PAGE);
    const pages = Math.max(1, Math.ceil(tiles.length / PER_PAGE));
    tiles.forEach((tile, i) => {
      tile.classList.toggle("selected", i === index);
      tile.classList.toggle("page-hidden", Math.floor(i / PER_PAGE) !== page);
    });
    pageLabel.textContent = pages > 1 ? `${page + 1} / ${pages}` : "";
  }
  function move(delta) {
    if (!tiles.length) return;
    index = Math.min(tiles.length - 1, Math.max(0, index + delta));
    render();
  }
  function open() {
    if (tiles[index]) window.location.href = tiles[index].dataset.url;
  }
  function action(name) {
    if (name === "left") move(-1);
    else if (name === "right") move(1);
    else if (name === "up") move(-COLUMNS);
    else if (name === "down") move(COLUMNS);
    else if (name === "ok") open();
  }

  window.addEventListener("keydown", (event) => {
    const keys = { ArrowLeft: "left", ArrowRight: "right", ArrowUp: "up", ArrowDown: "down", Enter: "ok", " ": "ok" };
    if (keys[event.key] && !event.repeat) {
      event.preventDefault();
      action(keys[event.key]);
    }
  });
  tiles.forEach((tile, i) => tile.addEventListener("click", () => { index = i; open(); }));
  pollGamepads(action);
  onEscape(() => {
    fetch("/externe/quitter", { method: "POST" }).finally(() => { window.location.href = "/"; });
  });
  render();
}

// v1.31 : diagnostic de fluidite -- quelle carte graphique le navigateur
// utilise-t-il ? « SwiftShader » / « llvmpipe » = rendu logiciel (sans carte
// graphique), cause la plus probable d'un jeu saccade.
// v1.34 : + images par seconde du jeu ET de l'ecran, et etat de la sortie
// son. Jeu a 45 i/s avec un ecran a 60 Hz et la vitesse calee sur le son =
// la sortie son du navigateur ralentit le jeu.
function jocsDiagnostic(audioSync) {
  const box = document.getElementById("jocs-diagnostic");
  if (!box) return;
  let renderer = "inconnue";
  try {
    const gl = document.createElement("canvas").getContext("webgl2") || document.createElement("canvas").getContext("webgl");
    const info = gl && gl.getExtension("WEBGL_debug_renderer_info");
    renderer = gl ? (info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER)) : "aucune (WebGL indisponible)";
  } catch (e) { renderer = "erreur : " + e.message; }
  const software = /swiftshader|llvmpipe|software|aucune/i.test(renderer);
  const gpu = "Carte graphique : " + renderer + (software ? " — RENDU LOGICIEL (sans carte graphique) : jeu ralenti" : "") +
    " · WebGL2 : " + (document.createElement("canvas").getContext("webgl2") ? "oui" : "non");
  box.classList.toggle("warn", software);
  box.textContent = gpu;

  let screenFrames = 0;
  (function count() { screenFrames++; requestAnimationFrame(count); })();
  let lastGame = null, lastTime = performance.now();
  setInterval(() => {
    const now = performance.now();
    const seconds = (now - lastTime) / 1000;
    let game = null;
    try { game = window.EJS_emulator.gameManager.getFrameNum(); } catch (e) { /* pas encore demarre */ }
    const gameFps = game !== null && lastGame !== null ? Math.round((game - lastGame) / seconds) : null;
    const screenHz = Math.round(screenFrames / seconds);
    let audio = "son : pas encore";
    try {
      const ctx = window.EJS_emulator.Module.AL.currentCtx.audioCtx;
      audio = `son : ${ctx.sampleRate} Hz, ${ctx.state}, latence ${Math.round(((ctx.baseLatency || 0) + (ctx.outputLatency || 0)) * 1000)} ms`;
    } catch (e) { /* pas de son */ }
    lastGame = game; lastTime = now; screenFrames = 0;
    box.textContent = `Jeu : ${gameFps === null ? "—" : gameFps} i/s · écran : ${screenHz} Hz · ${audio} · vitesse calée sur ` +
      (audioSync ? "le son" : "l'image") + " · " + gpu;
  }, 1000);
}

// v1.34 : ajoute des reglages au retroarch.cfg qu'EmulatorJS ecrit au
// demarrage (EJS_GameManager.getRetroArchCfg), avant le lancement du jeu.
// EmulatorJS est cree par loader.js ; le setter ci-dessous passe juste apres.
function jocsRetroarchConfig(extra) {
  let emulator;
  Object.defineProperty(window, "EJS_emulator", {
    configurable: true,
    get() { return emulator; },
    set(value) {
      emulator = value;
      const manager = window.EJS_GameManager;
      if (typeof manager === "function" && !manager.prototype.maletaConfig) {
        const original = manager.prototype.getRetroArchCfg;
        manager.prototype.getRetroArchCfg = function () { return original.call(this) + extra; };
        manager.prototype.maletaConfig = extra;
      }
    },
  });
}

// Noms des boutons de manette au format d'EmulatorJS, par numero de bouton
// du navigateur (meme liste que static/js/pad-capture.js).
const PAD_BUTTONS = ["BUTTON_1", "BUTTON_2", "BUTTON_3", "BUTTON_4", "LEFT_TOP_SHOULDER",
  "RIGHT_TOP_SHOULDER", "LEFT_BOTTOM_SHOULDER", "RIGHT_BOTTOM_SHOULDER", "SELECT", "START",
  "LEFT_STICK", "RIGHT_STICK", "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT"];

// v1.34 : combinaison de boutons pour quitter le jeu (n'importe quelle
// manette), maintenue `hold` secondes.
function watchQuitCombo(combo, callback) {
  const indexes = (combo && combo.buttons || []).map((name) => PAD_BUTTONS.indexOf(name));
  if (indexes.length < 2 || indexes.includes(-1)) return;
  let since = null, done = false;
  (function loop() {
    if (done) return;
    const pads = navigator.getGamepads ? Array.from(navigator.getGamepads()).filter(Boolean) : [];
    const pressed = pads.some((pad) => indexes.every((i) => pad.buttons[i] && pad.buttons[i].pressed));
    if (!pressed) since = null;
    else if (since === null) since = performance.now();
    if (since !== null && performance.now() - since >= (combo.hold || 0) * 1000) {
      done = true;
      callback();
      return;
    }
    requestAnimationFrame(loop);
  })();
}

function jocsPartida(quitCombo) {
  const leave = () => { window.location.href = "/jocs/"; };
  onEscape(leave);
  watchQuitCombo(quitCombo, leave);
  const hint = document.getElementById("jocs-exit-hint");
  setTimeout(() => hint.classList.add("faded"), 4000);
  // Une fois effacee, l'aide ne reste pas en calque par-dessus le jeu.
  setTimeout(() => { hint.style.display = "none"; }, 5000);
}
