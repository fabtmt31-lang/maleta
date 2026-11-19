// v1.3 : reglage de la manette du centre de jòcs depuis l'admin. Quand
// l'admin lance « Assignar » (Jòcs amagats > Manèta), le serveur envoie
// "pad_capture" : ce navigateur (ecran de la borne, ou page admin ouverte sur
// la borne) lit alors la manette et renvoie le premier bouton appuye, au
// format d'EmulatorJS (BUTTON_1, DPAD_UP, LEFT_STICK_X:+1...).
(function () {
  const BUTTONS = ["BUTTON_1", "BUTTON_2", "BUTTON_3", "BUTTON_4", "LEFT_TOP_SHOULDER",
    "RIGHT_TOP_SHOULDER", "LEFT_BOTTOM_SHOULDER", "RIGHT_BOTTOM_SHOULDER", "SELECT", "START",
    "LEFT_STICK", "RIGHT_STICK", "DPAD_UP", "DPAD_DOWN", "DPAD_LEFT", "DPAD_RIGHT"];
  const AXES = ["LEFT_STICK_X", "LEFT_STICK_Y", "RIGHT_STICK_X", "RIGHT_STICK_Y"];

  function snapshot() {
    const pads = navigator.getGamepads ? Array.from(navigator.getGamepads()).filter(Boolean) : [];
    return pads.map((pad) => ({
      buttons: pad.buttons.map((b) => b.pressed),
      axes: pad.axes.map((a) => (a > 0.6 ? 1 : a < -0.6 ? -1 : 0)),
    }));
  }

  function capture(seconds) {
    const start = snapshot();
    const until = performance.now() + seconds * 1000;
    function loop() {
      if (performance.now() > until) return;
      const now = snapshot();
      for (let p = 0; p < now.length; p++) {
        const before = start[p] || { buttons: [], axes: [] };
        for (let i = 0; i < now[p].buttons.length; i++) {
          if (now[p].buttons[i] && !before.buttons[i]) return send(BUTTONS[i] || "GAMEPAD_" + i);
        }
        for (let i = 0; i < now[p].axes.length; i++) {
          const v = now[p].axes[i];
          if (v && v !== before.axes[i]) return send((AXES[i] || "EXTRA_STICK_" + i) + ":" + (v > 0 ? "+1" : "-1"));
        }
      }
      requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);
  }

  function send(label) {
    fetch("/externe/manette", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ label }),
    });
  }

  if (typeof io === "function") {
    io("/kiosk").on("pad_capture", (data) => capture((data && data.seconds) || 10));
  }
})();
