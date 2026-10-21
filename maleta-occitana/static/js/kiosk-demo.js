// v1.2 : version de demonstration (MALETA_DEMO=1) -- sans lecteur NFC, ce
// panneau remplace la pose d'un objet : cliquer sur un objet le "pose" sur
// le lecteur (route /demo/place/<id>, voir blueprints/kiosk.py). Ouvert par
// le bouton en bas a gauche ou la touche F2. Charge uniquement en mode demo.
(function () {
  const toggle = document.getElementById("demo-nfc-toggle");
  const panel = document.getElementById("demo-nfc-panel");
  const list = document.getElementById("demo-nfc-list");
  const closeBtn = document.getElementById("demo-nfc-close");
  if (!toggle || !panel || !list) return;

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
      item.addEventListener("click", () => {
        fetch("/demo/place/" + obj.id, { method: "POST" });
        item.blur();
      });
      list.appendChild(item);
    });
  }

  function open() {
    panel.classList.remove("hidden");
    fetch("/demo/objects")
      .then((r) => r.json())
      .then((data) => render(data.objects || []))
      .catch(() => render([]));
  }
  function close() { panel.classList.add("hidden"); }
  function flip() { panel.classList.contains("hidden") ? open() : close(); }

  toggle.addEventListener("click", () => { flip(); toggle.blur(); });
  closeBtn.addEventListener("click", close);
  window.addEventListener("keydown", (event) => {
    if (event.key === "F2") {
      event.preventDefault();
      flip();
    }
  });
})();
