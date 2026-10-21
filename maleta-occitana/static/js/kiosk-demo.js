// v1.2 : version de demonstration (MALETA_DEMO=1), chargee uniquement en
// mode demo. Tout doit marcher au clavier ET a la souris, sans manette ni
// lecteur NFC :
// - panneau "Pausar un objècte" (bouton en bas a gauche ou F2) : cliquer sur
//   un objet, ou le choisir aux fleches + Entree, revient a le poser sur le
//   lecteur (route /demo/place/<id>, voir blueprints/kiosk.py) ;
// - clic sur une tuile du menu / de "Quantas cartas ?", une carte Memòria,
//   une reponse : la choisit directement (route /demo/pointer, voir
//   GameController.on_pointer) ;
// - clic sur un ecran sans choix (veille, diaporama, Descobèrta, fins de
//   partie) : continue ; clic droit n'importe ou : retour au menu.
(function () {
  const toggle = document.getElementById("demo-nfc-toggle");
  const panel = document.getElementById("demo-nfc-panel");
  const list = document.getElementById("demo-nfc-list");
  const closeBtn = document.getElementById("demo-nfc-close");
  if (!toggle || !panel || !list) return;

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    }).catch((err) => console.error("[demo]", url, err));
  }
  const action = (name) => post("/dev/action/" + encodeURIComponent(name));
  const pointer = (kind, extra) => post("/demo/pointer", Object.assign({ kind }, extra));

  // --- Panneau "Pausar un objècte" -----------------------------------------

  let panelIndex = 0;

  function panelItems() {
    return Array.from(list.querySelectorAll(".demo-nfc-item"));
  }

  function highlight(index) {
    const items = panelItems();
    if (items.length === 0) return;
    panelIndex = (index + items.length) % items.length;
    items.forEach((el, i) => el.classList.toggle("active", i === panelIndex));
    items[panelIndex].scrollIntoView({ block: "nearest" });
  }

  function render(objects) {
    list.textContent = "";
    if (objects.length === 0) {
      const empty = document.createElement("p");
      empty.className = "demo-nfc-help";
      empty.textContent = "Aucun objet actif : en ajouter depuis l'admin (Objèctes & tags).";
      list.appendChild(empty);
      return;
    }
    objects.forEach((obj) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "demo-nfc-item";
      item.tabIndex = -1;
      if (obj.image) {
        const img = document.createElement("img");
        img.src = obj.image;
        img.alt = "";
        item.appendChild(img);
      }
      const label = document.createElement("span");
      label.innerHTML = "<strong></strong><small></small>";
      label.querySelector("strong").textContent = obj.name_oc;
      label.querySelector("small").textContent = obj.name_fr;
      item.appendChild(label);
      item.addEventListener("click", () => post("/demo/place/" + obj.id));
      list.appendChild(item);
    });
    highlight(panelIndex);
  }

  function isOpen() { return !panel.classList.contains("hidden"); }
  function open() {
    panel.classList.remove("hidden");
    fetch("/demo/objects")
      .then((r) => r.json())
      .then((data) => render(data.objects || []))
      .catch(() => render([]));
  }
  function close() { panel.classList.add("hidden"); }
  function flip() { isOpen() ? close() : open(); }

  toggle.addEventListener("click", (event) => { event.stopPropagation(); flip(); toggle.blur(); });
  closeBtn.addEventListener("click", (event) => { event.stopPropagation(); close(); });
  panel.addEventListener("click", (event) => event.stopPropagation());

  // Phase de capture sur document : passe AVANT le clavier du kiosque
  // (kiosk.js, sur window) -- panneau ouvert, fleches/Entree/Echap pilotent
  // le panneau et ne sont pas envoyees au jeu.
  document.addEventListener("keydown", (event) => {
    if (event.key === "F2") {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (!event.repeat) flip();
      return;
    }
    if (!isOpen() || event.ctrlKey || event.altKey || event.metaKey) return;
    const handled = { ArrowUp: true, ArrowDown: true, Enter: true, Escape: true };
    if (!handled[event.key]) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (event.key === "ArrowUp") highlight(panelIndex - 1);
    else if (event.key === "ArrowDown") highlight(panelIndex + 1);
    else if (event.key === "Escape") close();
    else if (event.key === "Enter" && !event.repeat) {
      const item = panelItems()[panelIndex];
      if (item) item.click();
    }
  }, true);

  // --- Souris sur l'ecran du kiosque ----------------------------------------

  function indexIn(container, el) {
    return Array.prototype.indexOf.call(container.children, el);
  }

  // Ecrans sans choix a faire : un clic fait la meme chose qu'une touche.
  const CLICK_ACTION = {
    "screen-attract": "select",
    "screen-diaporama": "select",
    "screen-descoberta": "back",
    "screen-troba-fin": "select",
    "screen-vertadier-fin": "select",
    "screen-duel-fin": "select",
    "screen-memoria-fin": "select",
    "screen-quiz-fin": "select",
  };

  document.addEventListener("click", (event) => {
    if (event.button !== 0) return;
    const target = event.target;
    // Icones Cadre fotó / Admin : deja gerees par kiosk.js.
    if (target.closest("#menu-admin-icon, #menu-diaporama-icon, .demo-nfc-toggle, .demo-nfc-panel")) return;

    let el;
    if ((el = target.closest("#menu-tiles > .tile"))) {
      pointer("menu", { index: indexIn(el.parentElement, el) });
    } else if ((el = target.closest("#memoria-choice-tiles > .tile"))) {
      pointer("memoria_choice", { index: indexIn(el.parentElement, el) });
    } else if ((el = target.closest("#memoria-grid > .memoria-card"))) {
      pointer("memoria_card", { index: indexIn(el.parentElement, el) });
    } else if (target.closest("#vertadier-answer-true")) {
      action("answer_1");
    } else if (target.closest("#vertadier-answer-false")) {
      action("answer_2");
    } else if ((el = target.closest("#quiz-choice-a, #quiz-choice-b, #quiz-choice-c"))) {
      action({ "quiz-choice-a": "answer_1", "quiz-choice-b": "answer_2", "quiz-choice-c": "answer_3" }[el.id]);
    } else if ((el = target.closest("#duel-choice-a, #duel-choice-b"))) {
      pointer("duel", { choice: el.id === "duel-choice-a" ? "a" : "b" });
    } else {
      const screen = target.closest(".screen");
      if (screen && CLICK_ACTION[screen.id]) action(CLICK_ACTION[screen.id]);
    }
  });

  // Clic droit : retour au menu (comme Echap), sans menu contextuel.
  document.addEventListener("contextmenu", (event) => {
    if (event.target.closest(".demo-nfc-panel")) return;
    event.preventDefault();
    action("back");
  });
})();
