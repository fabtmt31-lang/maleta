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

function jocsPartida() {
  onEscape(() => { window.location.href = "/jocs/"; });
  const hint = document.getElementById("jocs-exit-hint");
  setTimeout(() => hint.classList.add("faded"), 4000);
}
