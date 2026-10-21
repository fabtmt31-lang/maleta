// v0.6 : sélecteur « choisir dans la médiathèque », utilisable a cote de
// n'importe quel champ d'upload de l'admin (objet, média, bannière) --
// evite d'avoir a re-uploader un fichier deja present sur le disque.
// Un seul modal partage (voir le markup dans admin/base.html), rempli via
// GET /admin/mediatheque/browse?key=<categorie> et pilote par les boutons
// portant l'attribut data-media-picker.
(function () {
  const modal = document.getElementById("mediatheque-picker-modal");
  if (!modal) return;
  const body = document.getElementById("mtp-modal-body");

  let activeTarget = null;

  function closeModal() {
    modal.classList.add("hidden");
    activeTarget = null;
  }

  modal.querySelectorAll("[data-mtp-close]").forEach((el) => {
    el.addEventListener("click", closeModal);
  });

  function cellIcon(kind) {
    if (kind === "audio") return "🔊";
    if (kind === "video") return "🎬";
    return "📄";
  }

  function renderItems(items) {
    if (!items.length) {
      body.innerHTML = '<p class="muted">Aucun fichier de ce type dans la médiathèque pour l\'instant.</p>';
      return;
    }
    body.innerHTML = "";
    const grid = document.createElement("div");
    grid.className = "mtp-grid";
    items.forEach((item) => {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "mtp-cell";
      cell.title = item.filename;

      if (item.preview_kind === "image") {
        const img = document.createElement("img");
        img.src = item.url;
        img.alt = "";
        cell.appendChild(img);
      } else {
        const icon = document.createElement("span");
        icon.className = "mtp-cell-icon";
        icon.textContent = cellIcon(item.preview_kind);
        cell.appendChild(icon);
      }

      const label = document.createElement("span");
      label.className = "mtp-cell-label";
      label.textContent = item.filename;
      cell.appendChild(label);

      cell.addEventListener("click", () => pickItem(item));
      grid.appendChild(cell);
    });
    body.appendChild(grid);
  }

  function pickItem(item) {
    if (!activeTarget) return;
    const { fileInput, hiddenInput, preview } = activeTarget;
    if (hiddenInput) hiddenInput.value = item.filename;
    if (fileInput) fileInput.value = "";
    if (preview) {
      preview.innerHTML = "";
      if (item.preview_kind === "image") {
        const img = document.createElement("img");
        img.className = "mtp-preview-img";
        img.src = item.url;
        img.alt = "";
        preview.appendChild(img);
      }
      const label = document.createElement("span");
      label.textContent = "Choisi dans la médiathèque : " + item.filename;
      preview.appendChild(label);
    }
    closeModal();
  }

  function openPicker(category, target) {
    activeTarget = target;
    modal.classList.remove("hidden");
    body.innerHTML = '<p class="muted">Chargement…</p>';
    fetch("/admin/mediatheque/browse?key=" + encodeURIComponent(category))
      .then((r) => r.json())
      .then((data) => renderItems(data.items || []))
      .catch(() => {
        body.innerHTML = '<p class="muted">Erreur de chargement.</p>';
      });
  }

  document.querySelectorAll("[data-media-picker]").forEach((btn) => {
    const category = btn.getAttribute("data-media-picker");
    const fileInput = document.getElementById(btn.getAttribute("data-file-input"));
    const hiddenInput = document.getElementById(btn.getAttribute("data-hidden-input"));
    const previewId = btn.getAttribute("data-preview");
    const preview = previewId ? document.getElementById(previewId) : null;

    btn.addEventListener("click", () => openPicker(category, { fileInput, hiddenInput, preview }));

    // Si l'utilisateur choisit finalement un fichier local, on annule le
    // choix "médiathèque" précédent pour ne jamais envoyer les deux a la
    // fois (voir _save_object_form et consorts cote serveur : le fichier
    // local est toujours prioritaire, mais autant nettoyer l'affichage).
    if (fileInput && hiddenInput) {
      fileInput.addEventListener("change", () => {
        if (fileInput.files && fileInput.files.length) {
          hiddenInput.value = "";
          if (preview) preview.innerHTML = "";
        }
      });
    }
  });
})();
