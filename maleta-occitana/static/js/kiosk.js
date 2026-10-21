// Ecran du kiosque : recoit l'etat du jeu par websocket (namespace /kiosk)
// et bascule entre les differents ecrans.
//
// v1.1 (refonte « 3 directions ») : les ecrans sont dessines pour une scene
// de 1280x720 mise a l'echelle de l'ecran reel (voir kiosk.html), et existent
// en 3 modeles (Senhal, Mercat, Nuèch) qui partagent EXACTEMENT les memes
// identifiants HTML -- ce fichier ne connait le modele actif que pour
// quelques details de presentation (numerotation des tuiles, « sus 10 » ou
// « / 10 », libelles des cartes Memòria). Plus aucun rappel de touche sur
// les tuiles du menu : il etait faux des que les touches etaient
// reassignees, et la barre d'aide en bas d'ecran l'indique deja (demande de
// Fabien).

const TEMPLATE = window.MALETA_TEMPLATE || document.body.dataset.template || "senhal";

const screens = {
  attract: document.getElementById("screen-attract"),
  diaporama: document.getElementById("screen-diaporama"),
  descoberta: document.getElementById("screen-descoberta"),
  menu: document.getElementById("screen-menu"),
  troba: document.getElementById("screen-troba"),
  trobaFin: document.getElementById("screen-troba-fin"),
  vertadier: document.getElementById("screen-vertadier"),
  vertadierFin: document.getElementById("screen-vertadier-fin"),
  duel: document.getElementById("screen-duel"),
  duelFin: document.getElementById("screen-duel-fin"),
  memoriaChoice: document.getElementById("screen-memoria-choice"),
  memoria: document.getElementById("screen-memoria"),
  memoriaFin: document.getElementById("screen-memoria-fin"),
  quiz: document.getElementById("screen-quiz"),
  quizFin: document.getElementById("screen-quiz-fin"),
};

function showOnly(name) {
  for (const key in screens) {
    screens[key].classList.toggle("hidden", key !== name);
  }
}

function $(id) {
  return document.getElementById(id);
}

// --- Ajustement automatique de la taille du texte (v1.1) --------------------
//
// Remplace les classes question-medium/long/xlong de la v1.03 : chaque texte
// variable (mot, question, reponse) part de la taille prevue par la maquette
// (font-size du CSS) et diminue jusqu'a tenir dans sa boite (largeur ET
// hauteur maximales definies dans le CSS du modele). Un mot occitan long ou
// une question de Quiz de 3 lignes reste ainsi toujours entierement visible.
// Les mesures se font dans le repere de la scene (avant mise a l'echelle),
// donc independamment de la resolution de l'ecran.
const fittedElements = new Set();

function fitText(el, minPx) {
  if (!el) return;
  fittedElements.add(el);
  el.dataset.fitMin = String(minPx || 14);
  el.style.fontSize = "";
  if (!el.offsetParent || !el.textContent) return; // ecran cache : refait a l'affichage
  const min = minPx || 14;
  const style = getComputedStyle(el);
  let size = parseFloat(style.fontSize) || 32;
  // Hauteur : on compare a la hauteur MAXIMALE prevue par le CSS (et non a la
  // boite courante, que les jambages des lettres depassent toujours un peu).
  const maxHeight = parseFloat(style.maxHeight);
  const tooBig = () =>
    el.scrollWidth > el.clientWidth + 1 ||
    (!isNaN(maxHeight) && el.scrollHeight > maxHeight + 2);
  let guard = 0;
  while (size > min && guard < 80 && tooBig()) {
    size = Math.max(min, size - Math.max(1, Math.round(size * 0.06)));
    el.style.fontSize = size + "px";
    guard++;
  }
}

function refitVisible() {
  fittedElements.forEach((el) => {
    if (el.offsetParent) fitText(el, Number(el.dataset.fitMin) || 14);
  });
}
window.maletaRefit = refitVisible;
if (document.fonts && document.fonts.ready) {
  // Les polices locales arrivent juste apres le premier rendu : les mesures
  // faites avant leur chargement seraient fausses.
  document.fonts.ready.then(refitVisible);
}

// --- Petits elements communs -------------------------------------------------

// Barre de progression (un segment/point par question) : faites, en cours, a venir.
function renderSteps(container, index, total) {
  if (!container) return;
  const count = Math.max(0, Math.min(total || 0, 30));
  container.innerHTML = "";
  for (let i = 0; i < count; i++) {
    const step = document.createElement("span");
    step.className = "step " + (i < index ? "step-done" : i === index ? "step-current" : "step-todo");
    container.appendChild(step);
  }
}

function totalLabel(total) {
  return TEMPLATE === "mercat" ? "/ " + total : "sus " + total;
}

// Etoiles du modele Mercat (masquees par le CSS des autres modeles).
function setStars(screen, stars) {
  const icons = screen.querySelectorAll(".fin-stars .icon");
  icons.forEach((icon, i) => icon.classList.toggle("on", i < stars));
}

function starsForRatio(ratio) {
  if (ratio >= 0.8) return 3;
  if (ratio >= 0.5) return 2;
  if (ratio > 0) return 1;
  return 0;
}

function setFin(screen, valueEl, totalEl, value, totalText, stars) {
  valueEl.textContent = value;
  totalEl.textContent = totalText;
  setStars(screen, stars);
  fitText(valueEl, 28);
}

// Retour visuel (Bravo ! / Fals ! / Temps acabat !) affiche sur la carte de
// la question. kind : "correct" | "wrong" | "" (rien).
function setFeedback(el, text, kind) {
  el.textContent = text || "";
  el.className = "q-feedback" + (kind ? " feedback-" + kind : "");
  const card = el.closest(".q-card");
  if (card) {
    card.classList.toggle("is-correct", kind === "correct");
    card.classList.toggle("is-wrong", kind === "wrong");
  }
}

function setAnswerState(el, state) {
  el.classList.toggle("is-right", state === "right");
  el.classList.toggle("is-dim", state === "dim");
}

// v1.03 (revue de code) : la barre de temps d'une question repartait a 100 %
// a CHAQUE nouvel etat recu sans retour visuel -- au Duèl, des que le joueur 1
// repondait, la barre se remplissait a nouveau alors que le minuteur du
// serveur continuait de tourner. Le serveur envoie desormais le temps restant
// ("time_left", en secondes) : on reconstitue le point de depart de la barre
// a partir de lui. Absent (null) = question qui vient de commencer.
function timerStartFor(timeLeft, durationMs) {
  if (typeof timeLeft !== "number") return performance.now();
  const leftMs = Math.min(durationMs, Math.max(0, timeLeft * 1000));
  return performance.now() - (durationMs - leftMs);
}

// Barre de temps animee cote client (le serveur ne pousse pas un tick par
// seconde). Un minuteur par ecran, pour ne jamais interferer entre jeux.
const timers = {};

function startTimer(name, barId, screenKey, durationMs, timeLeft) {
  stopTimer(name);
  const t = { start: timerStartFor(timeLeft, durationMs), duration: durationMs, raf: null };
  timers[name] = t;
  const bar = $(barId);
  const step = () => {
    const remaining = Math.max(0, 1 - (performance.now() - t.start) / t.duration);
    bar.style.width = (remaining * 100) + "%";
    bar.classList.toggle("timer-low", remaining < 0.25);
    if (remaining > 0 && !screens[screenKey].classList.contains("hidden") && timers[name] === t) {
      t.raf = requestAnimationFrame(step);
    }
  };
  step();
}

function stopTimer(name, barId) {
  const t = timers[name];
  if (t && t.raf) cancelAnimationFrame(t.raf);
  timers[name] = null;
  if (barId) {
    const bar = $(barId);
    bar.style.width = "0%";
    bar.classList.remove("timer-low");
  }
}

// v1.03 : la prononciation d'un objet continuait de jouer par-dessus l'ecran
// suivant (ex. retour au menu depuis Descobèrta) -- coupee des qu'on quitte
// les ecrans qui l'utilisent.
const AUDIO_STATES = ["descoberta", "troba", "troba_fin"];
function pauseObjectAudio() {
  const audio = $("object-audio");
  if (!audio.paused) audio.pause();
}

function playObjectAudio(filename) {
  const audio = $("object-audio");
  audio.src = "/media/objects/audio/" + encodeURIComponent(filename);
  audio.play().catch(() => {
    // lecture auto bloquee tant qu'il n'y a pas eu d'interaction -- sans
    // consequence en Chromium --kiosk avec l'autoplay autorise.
  });
}

function renderState(payload) {
  if (!AUDIO_STATES.includes(payload.state)) pauseObjectAudio();
  if (payload.state === "descoberta" && payload.object) {
    showDescoberta(payload.object);
  } else if (payload.state === "veille") {
    showVeille(payload.media || []);
  } else if (payload.state === "menu") {
    showMenu(payload);
  } else if (payload.state === "troba") {
    showTroba(payload);
  } else if (payload.state === "troba_fin") {
    showTrobaFin(payload);
  } else if (payload.state === "vertadier") {
    showVertadier(payload);
  } else if (payload.state === "vertadier_fin") {
    showVertadierFin(payload);
  } else if (payload.state === "duel") {
    showDuel(payload);
  } else if (payload.state === "duel_fin") {
    showDuelFin(payload);
  } else if (payload.state === "memoria_choice" || payload.state === "memoria_vilatge_choice") {
    // v0.9 : ecran "Quantas cartas ?" (un seul gabarit pour les 2 variantes).
    showMemoriaChoice(payload);
  } else if (payload.state === "memoria" || payload.state === "memoria_vilatge") {
    // v0.8 : "Memòria" et "Memòria vilatge" partagent le MEME gabarit.
    showMemoria(payload);
  } else if (payload.state === "memoria_fin" || payload.state === "memoria_vilatge_fin") {
    showMemoriaFin(payload);
  } else if (payload.state === "quiz") {
    showQuiz(payload);
  } else if (payload.state === "quiz_fin") {
    showQuizFin(payload);
  } else {
    showVeille([]);
  }
}

// --- Veille : diaporama si des medias actifs existent, sinon l'ecran
// "Pausa un objècte" (borne toute neuve, sans contenu photo/video). -------

let diaporamaMedia = [];
let diaporamaIndex = 0;
let diaporamaTimer = null;
// v1.03 (revue de code) : "generation" du diaporama, incrementee a chaque
// arret -- une video dont la lecture echouait APRES l'arret ne relance plus
// de minuteur fantome.
let diaporamaGeneration = 0;
let diaporamaKey = null;

function showVeille(media) {
  pauseObjectAudio();

  if (media.length === 0) {
    stopDiaporama();
    showOnly("attract");
    return;
  }
  // v1.03 : le meme etat "veille" arrive deux fois au chargement de la page
  // (etat initial, puis connexion websocket) -- on ne relance pas le
  // diaporama depuis le debut s'il tourne deja avec les memes medias.
  const key = JSON.stringify(media.map((m) => [m.filename, m.media_type, m.display_seconds, m.caption]));
  if (!screens.diaporama.classList.contains("hidden") && key === diaporamaKey) {
    return;
  }
  stopDiaporama();
  showOnly("diaporama");
  diaporamaKey = key;
  diaporamaMedia = media;
  diaporamaIndex = 0;
  playDiaporamaItem();
}

function stopDiaporama() {
  diaporamaGeneration++;
  diaporamaKey = null;
  if (diaporamaTimer) {
    clearTimeout(diaporamaTimer);
    diaporamaTimer = null;
  }
  const video = $("diaporama-video");
  video.pause();
  video.onended = null;
}

function playDiaporamaItem() {
  if (diaporamaMedia.length === 0) return;
  const generation = diaporamaGeneration;
  const item = diaporamaMedia[diaporamaIndex % diaporamaMedia.length];
  const img = $("diaporama-image");
  const video = $("diaporama-video");
  const caption = $("diaporama-caption");

  caption.textContent = item.caption || "";
  caption.classList.toggle("hidden", !item.caption);

  if (item.media_type === "video") {
    img.classList.add("hidden");
    video.classList.remove("hidden");
    video.src = "/media/library/" + encodeURIComponent(item.filename);
    video.currentTime = 0;
    video.onended = advanceDiaporama;
    video.play().catch(() => {
      // autoplay bloque : on passe au media suivant apres la duree prevue.
      // v1.03 : ignore si le diaporama a ete arrete entre-temps.
      if (generation !== diaporamaGeneration) return;
      diaporamaTimer = setTimeout(advanceDiaporama, (item.display_seconds || 6) * 1000);
    });
  } else {
    video.classList.add("hidden");
    video.pause();
    img.classList.remove("hidden");
    img.src = "/media/library/" + encodeURIComponent(item.filename);
    diaporamaTimer = setTimeout(advanceDiaporama, (item.display_seconds || 6) * 1000);
  }
}

function advanceDiaporama() {
  if (diaporamaMedia.length === 0) return;
  diaporamaIndex = (diaporamaIndex + 1) % diaporamaMedia.length;
  playDiaporamaItem();
}

// --- Descobèrta d'objèctes ---------------------------------------------------

let descobertaAudioFile = null;

function showDescoberta(obj) {
  stopDiaporama();
  showOnly("descoberta");

  $("object-name-oc").textContent = obj.name_oc;
  $("object-name-fr").textContent = obj.name_fr;
  const category = $("object-category");
  category.textContent = obj.category || "";
  category.classList.toggle("hidden", !obj.category);
  fitText($("object-name-oc"), 34);
  fitText($("object-name-fr"), 18);

  const img = $("object-image");
  const frame = img.closest(".desc-frame");
  if (obj.image_filename) {
    img.src = "/media/objects/images/" + encodeURIComponent(obj.image_filename);
    img.style.display = "";
    frame.classList.add("has-image");
  } else {
    img.removeAttribute("src");
    img.style.display = "none";
    frame.classList.remove("has-image");
  }

  // Le bouton « Escota » n'apparait que si une prononciation existe.
  const audioBtn = $("object-audio-btn");
  descobertaAudioFile = obj.audio_filename || null;
  audioBtn.classList.toggle("hidden", !descobertaAudioFile);
  if (descobertaAudioFile) playObjectAudio(descobertaAudioFile);
}

// --- Menu "Tria un jòc" ----------------------------------------------------

const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"];

function tileNumber(index) {
  if (TEMPLATE === "nuech") return ROMAN[index] || String(index + 1);
  if (TEMPLATE === "senhal") return String(index + 1).padStart(2, "0");
  return "";
}

// v1.1 : icones des tuiles rendues une seule fois par le serveur (template
// #tile-icons dans kiosk.html) et clonees ici.
function tileIcon(activityId) {
  const tpl = $("tile-icons");
  const source = tpl.content.querySelector('[data-icon="' + activityId + '"]') ||
    tpl.content.querySelector('[data-icon="_fallback"]');
  return source ? source.firstElementChild.cloneNode(true) : document.createElement("span");
}

function buildTile(className, number, iconNode, labelOc, labelFr) {
  const tile = document.createElement("div");
  tile.className = className;
  const num = document.createElement("span");
  num.className = "tile-num";
  num.textContent = number;
  const icon = document.createElement("span");
  icon.className = "tile-icon";
  icon.appendChild(iconNode);
  const text = document.createElement("span");
  text.className = "tile-text";
  const oc = document.createElement("span");
  oc.className = "tile-label-oc";
  oc.textContent = labelOc;
  const fr = document.createElement("span");
  fr.className = "tile-label-fr";
  fr.textContent = labelFr;
  text.append(oc, fr);
  tile.append(num, icon, text);
  return tile;
}

function setNotice(el, text) {
  el.textContent = text || "";
  el.classList.toggle("hidden", !text);
}

function showMenu(payload) {
  stopDiaporama();
  showOnly("menu");

  const tiles = $("menu-tiles");
  tiles.innerHTML = "";
  tiles.style.setProperty("--tile-count", payload.activities.length);
  payload.activities.forEach((activity, index) => {
    const selected = index === payload.selected_index;
    const tile = buildTile(
      "tile tile-" + activity.id + (selected ? " selected" : ""),
      tileNumber(index), tileIcon(activity.id), activity.label_oc, activity.label_fr
    );
    tiles.appendChild(tile);
  });
  tiles.querySelectorAll(".tile-label-oc").forEach((el) => fitText(el, 16));

  setNotice($("menu-notice"), payload.notice);

  // v0.8 : DEUX icones-slots de navigation virtuels juste apres la derniere
  // tuile (MENU_EXTRA_ICONS cote serveur) : "Cadre fotó" (index
  // activities.length) puis Admin (index activities.length + 1).
  $("menu-diaporama-icon").classList.toggle("selected", payload.selected_index === payload.activities.length);
  $("menu-admin-icon").classList.toggle("selected", payload.selected_index === payload.activities.length + 1);
}

// --- Tròba l'objècte --------------------------------------------------------

let lastTrobaAudioKey = null; // v0.83 : evite de rejouer le son a chaque re-render

function showTroba(payload) {
  stopDiaporama();
  showOnly("troba");

  $("troba-progress").textContent = (payload.index + 1) + " / " + payload.total;
  renderSteps($("troba-steps"), payload.index, payload.total);
  $("troba-score").textContent = "Punts : " + payload.score;
  $("troba-word-oc").textContent = payload.word_oc;

  const feedbackEl = $("troba-feedback");
  if (payload.feedback === "correct") setFeedback(feedbackEl, "Bravo !", "correct");
  else if (payload.feedback === "wrong") setFeedback(feedbackEl, "Ensaja tornarmai !", "wrong");
  else if (payload.feedback === "timeout") setFeedback(feedbackEl, "Temps acabat !", "wrong");
  else setFeedback(feedbackEl, "", "");

  // v0.6 : revele l'image de l'objet uniquement pendant le retour visuel
  // (le serveur ne l'envoie que dans ce cas, voir game_controller.py).
  const revealCircle = $("troba-reveal-circle");
  const revealImage = $("troba-reveal-image");
  if (payload.feedback && payload.image_filename) {
    revealImage.src = "/media/objects/images/" + encodeURIComponent(payload.image_filename);
    revealCircle.classList.remove("hidden");
  } else {
    revealImage.removeAttribute("src");
    revealCircle.classList.add("hidden");
  }
  fitText($("troba-word-oc"), 28);

  // v0.83 : joue la prononciation de l'objet des qu'il est trouve -- une
  // seule fois par reponse (le serveur repousse l'etat courant a chaque
  // connexion/reconnexion websocket).
  if (payload.feedback === "correct" && payload.audio_filename) {
    const audioKey = payload.index + ":" + payload.feedback;
    if (lastTrobaAudioKey !== audioKey) {
      lastTrobaAudioKey = audioKey;
      playObjectAudio(payload.audio_filename);
    }
  } else if (!payload.feedback) {
    lastTrobaAudioKey = null;
  }

  if (!payload.feedback) {
    startTimer("troba", "troba-timer-bar", "troba", payload.seconds_per_word * 1000, payload.time_left);
  } else {
    stopTimer("troba", "troba-timer-bar");
  }
}

function showTrobaFin(payload) {
  stopDiaporama();
  stopTimer("troba");
  showOnly("trobaFin");
  setFin(screens.trobaFin, $("troba-fin-score"), $("troba-fin-total"),
    String(payload.score), totalLabel(payload.total),
    starsForRatio(payload.total ? payload.score / payload.total : 0));
}

// --- Ven de l'occitan ? (ex-« Vertadièr o Occitan », v0.2) ------------------
//
// Reponse a la manette (answer_1 = « Vertadièr », answer_2 = « Fals ») : le
// mot francais est affiche, le serveur revele feedback + explication une fois
// qu'une reponse a ete donnee (ou le temps ecoule).

function showVertadier(payload) {
  stopDiaporama();
  showOnly("vertadier");

  $("vertadier-progress").textContent = (payload.index + 1) + " / " + payload.total;
  renderSteps($("vertadier-steps"), payload.index, payload.total);
  $("vertadier-score").textContent = "Punts : " + payload.score;
  $("vertadier-word-fr").textContent = payload.word_fr || "";
  fitText($("vertadier-word-fr"), 24);

  const feedbackEl = $("vertadier-feedback");
  const explanationEl = $("vertadier-explanation");
  if (payload.feedback === "correct") setFeedback(feedbackEl, "Bravo !", "correct");
  else if (payload.feedback === "wrong") setFeedback(feedbackEl, "Fals !", "wrong");
  else if (payload.feedback === "timeout") setFeedback(feedbackEl, "Temps acabat !", "wrong");
  else setFeedback(feedbackEl, "", "");

  const answerTrue = $("vertadier-answer-true");
  const answerFalse = $("vertadier-answer-false");
  if (payload.feedback && "is_occitan" in payload) {
    explanationEl.textContent =
      (payload.is_occitan ? "Vertadièr — " : "Fals — ") + (payload.explanation || "");
    setAnswerState(answerTrue, payload.is_occitan ? "right" : "dim");
    setAnswerState(answerFalse, payload.is_occitan ? "dim" : "right");
  } else {
    explanationEl.textContent = "";
    setAnswerState(answerTrue, "");
    setAnswerState(answerFalse, "");
  }
  fitText(explanationEl, 14);

  if (!payload.feedback) {
    startTimer("vertadier", "vertadier-timer-bar", "vertadier", payload.seconds_per_word * 1000, payload.time_left);
  } else {
    stopTimer("vertadier", "vertadier-timer-bar");
  }
}

function showVertadierFin(payload) {
  stopDiaporama();
  stopTimer("vertadier");
  showOnly("vertadierFin");
  setFin(screens.vertadierFin, $("vertadier-fin-score"), $("vertadier-fin-total"),
    String(payload.score), totalLabel(payload.total),
    starsForRatio(payload.total ? payload.score / payload.total : 0));
}

// --- Duèl Occitan (v0.7, jeu a 2 joueurs) ----------------------------------
//
// Deux reponses independantes (answered_p1/answered_p2) et deux scores. Tant
// que feedback est absent, les blocs A/B restent neutres : le serveur ne
// revele jamais la bonne reponse avant que les deux joueurs aient repondu.

function showDuel(payload) {
  stopDiaporama();
  showOnly("duel");

  $("duel-progress").textContent = (payload.index + 1) + " / " + payload.total;
  renderSteps($("duel-steps"), payload.index, payload.total);
  $("duel-score-p1").textContent = payload.score_p1;
  $("duel-score-p2").textContent = payload.score_p2;
  $("duel-question").textContent = payload.question_fr || "";
  fitText($("duel-question"), 18);

  const choiceA = $("duel-choice-a");
  const choiceB = $("duel-choice-b");
  $("duel-choice-a-label").textContent = payload.choice_a;
  $("duel-choice-b-label").textContent = payload.choice_b;

  const feedbackEl = $("duel-feedback");
  const explanationEl = $("duel-explanation");
  const revealed = payload.feedback === "revealed";

  if (revealed) {
    setFeedback(feedbackEl, "Responsa revelada !", "correct");
    explanationEl.textContent = payload.explanation || "";
    setAnswerState(choiceA, payload.correct_choice === "a" ? "right" : "dim");
    setAnswerState(choiceB, payload.correct_choice === "b" ? "right" : "dim");
  } else {
    setFeedback(feedbackEl, "", "");
    explanationEl.textContent = "";
    setAnswerState(choiceA, "");
    setAnswerState(choiceB, "");
  }
  fitText($("duel-choice-a-label"), 16);
  fitText($("duel-choice-b-label"), 16);
  fitText(explanationEl, 14);

  updateDuelPlayerStatus("p1", payload.answered_p1, revealed, payload.correct_choice);
  updateDuelPlayerStatus("p2", payload.answered_p2, revealed, payload.correct_choice);

  if (!payload.feedback) {
    startTimer("duel", "duel-timer-bar", "duel", payload.seconds_per_question * 1000, payload.time_left);
  } else {
    stopTimer("duel", "duel-timer-bar");
  }
}

function updateDuelPlayerStatus(player, answered, revealed, correctChoice) {
  const statusEl = $("duel-player-" + player + "-status");
  const rowEl = $("duel-player-" + player);
  const base = "duel-player duel-player-" + player.slice(1);
  if (revealed) {
    if (answered === null) {
      statusEl.textContent = "Cap de responsa";
      rowEl.className = base + " duel-player-wrong";
    } else if (answered === correctChoice) {
      statusEl.textContent = "Bravo ! (" + answered.toUpperCase() + ")";
      rowEl.className = base + " duel-player-correct";
    } else {
      statusEl.textContent = "Fals (" + answered.toUpperCase() + ")";
      rowEl.className = base + " duel-player-wrong";
    }
  } else if (answered !== null) {
    statusEl.textContent = "A respondut !";
    rowEl.className = base + " duel-player-answered";
  } else {
    statusEl.textContent = "…";
    rowEl.className = base;
  }
}

function showDuelFin(payload) {
  stopDiaporama();
  stopTimer("duel");
  showOnly("duelFin");

  const winnerEl = $("duel-fin-winner");
  if (payload.winner === "tie") {
    winnerEl.textContent = "Egalitat !";
  } else if (payload.winner === "p1") {
    winnerEl.textContent = "Jogador 1 ganha !";
  } else {
    winnerEl.textContent = "Jogador 2 ganha !";
  }
  $("duel-fin-scores").textContent =
    "Jogador 1 : " + payload.score_p1 + " / " + payload.total +
    "  —  Jogador 2 : " + payload.score_p2 + " / " + payload.total;
  const best = Math.max(payload.score_p1, payload.score_p2);
  setFin(screens.duelFin, $("duel-fin-score"), $("duel-fin-total"),
    payload.score_p1 + " – " + payload.score_p2, totalLabel(payload.total),
    starsForRatio(payload.total ? best / payload.total : 0));
}

// --- Memòria (v0.72, jeu 100% ecran/manette) --------------------------------
//
// v0.9 : ecran de choix de la taille de partie ("Quantas cartas ?"). Une
// option non jouable (pas assez de contenu) est grisee mais reste affichee --
// tenter de la valider affiche un message (payload.notice).
function showMemoriaChoice(payload) {
  stopDiaporama();
  showOnly("memoriaChoice");

  $("memoria-choice-eyebrow").textContent = payload.activity_label_oc || "Memòria";

  const tiles = $("memoria-choice-tiles");
  tiles.innerHTML = "";
  tiles.style.setProperty("--tile-count", payload.options.length);
  payload.options.forEach((option, index) => {
    const selected = index === payload.selected_index;
    let className = "tile tile-choice tile-memoria" + (selected ? " selected" : "");
    if (!option.available) className += " unavailable";
    const tile = buildTile(
      className, tileNumber(index), tileIcon("memoria"),
      option.pairs + " parelhs",
      option.cards + " cartas" + (option.available ? "" : " — pas pro de contengut")
    );
    tiles.appendChild(tile);
  });

  setNotice($("memoria-choice-notice"), payload.notice);
}

// Grille de cartes construite dynamiquement, sur un nombre de colonnes FIXE
// (config.MEMORIA_GRID_COLUMNS, transmis par kiosk.html) pour que la
// navigation haut/bas cote serveur corresponde a un vrai deplacement de
// rangee. Une carte face cachee n'a AUCUN contenu cote client (le serveur ne
// l'envoie qu'une fois retournee ou trouvee) : elle affiche le dos du modele
// actif (template #memoria-card-back-tpl).

const MEMORIA_LANG_LABELS = TEMPLATE === "nuech"
  ? { fr: "francés", oc: "occitan" }
  : { fr: "FR", oc: "OC" };

function memoriaCheckIcon() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("class", "icon memoria-card-check");
  const path = document.createElementNS(ns, "path");
  path.setAttribute("d", "M4 12.5l5 5L20 6.5");
  path.setAttribute("fill", "none");
  path.setAttribute("stroke", "currentColor");
  path.setAttribute("stroke-width", "2.6");
  path.setAttribute("stroke-linecap", "round");
  path.setAttribute("stroke-linejoin", "round");
  svg.appendChild(path);
  return svg;
}

function showMemoria(payload) {
  stopDiaporama();
  showOnly("memoria");

  // v0.8 : titre = libelle de la variante en cours ("Memòria" ou "Memòria vilatge").
  $("memoria-eyebrow").textContent = payload.activity_label_oc || "Memòria";
  $("memoria-progress").textContent = payload.matched_pairs + " / " + payload.total_pairs;
  $("memoria-attempts").textContent = payload.attempts;

  const feedbackEl = $("memoria-feedback");
  if (payload.feedback === "match") {
    feedbackEl.textContent = "Parelh trobat !";
    feedbackEl.className = "mem-feedback feedback-correct";
  } else {
    // "mismatch" ne merite pas de message d'echec : retrouver deux cartes qui
    // ne vont pas ensemble fait partie normale du jeu de memoire.
    feedbackEl.textContent = "";
    feedbackEl.className = "mem-feedback";
  }

  const grid = $("memoria-grid");
  grid.innerHTML = "";
  const columns = Number(getComputedStyle(grid).getPropertyValue("--mem-cols")) || 6;
  const rows = Math.ceil(payload.cards.length / columns);
  grid.style.setProperty("--mem-rows", rows);
  grid.classList.toggle("memoria-grid-tall", rows > 2);
  const backTpl = $("memoria-card-back-tpl");

  payload.cards.forEach((card, index) => {
    const cell = document.createElement("div");
    let className = "memoria-card";
    if (card.matched) className += " matched";
    else if (card.flipped) className += " flipped";
    if (index === payload.cursor) className += " selected";
    cell.className = className;

    if (card.kind === "fr" || card.kind === "oc") {
      // v0.8 : chaque carte montre un mot FRANCAIS ou OCCITAN, avec un petit
      // badge de langue. v1.03 : texte insere via textContent (un mot saisi
      // dans l'admin contenant "<" ou "&" cassait l'affichage).
      const face = document.createElement("div");
      face.className = "memoria-card-face memoria-card-front memoria-card-word memoria-card-word-" + card.kind;
      if (card.matched) {
        face.appendChild(memoriaCheckIcon());
      } else {
        const lang = document.createElement("span");
        lang.className = "memoria-card-lang";
        lang.textContent = MEMORIA_LANG_LABELS[card.kind];
        face.appendChild(lang);
      }
      const text = document.createElement("span");
      text.className = "memoria-card-text";
      text.textContent = card.text;
      face.appendChild(text);
      cell.appendChild(face);
    } else {
      cell.appendChild(backTpl.content.firstElementChild.cloneNode(true));
    }
    grid.appendChild(cell);
  });
  grid.querySelectorAll(".memoria-card-text").forEach((el) => fitText(el, 11));
}

function showMemoriaFin(payload) {
  stopDiaporama();
  showOnly("memoriaFin");
  screens.memoriaFin.querySelector(".fin-eyebrow span").textContent = payload.activity_label_oc || "Memòria";
  $("memoria-fin-score").textContent =
    payload.total_pairs + " parelhs trobats en " + payload.attempts + " ensages";
  // Etoiles (modele Mercat) : moins il a fallu d'essais par paire, mieux c'est.
  const perPair = payload.total_pairs ? payload.attempts / payload.total_pairs : 99;
  const stars = perPair <= 1.5 ? 3 : perPair <= 2.5 ? 2 : 1;
  setFin(screens.memoriaFin, $("memoria-fin-attempts"), $("memoria-fin-total"),
    String(payload.attempts), "ensages", stars);
}

// --- Quiz Calandreta (v0.8) -------------------------------------------------
//
// Meme structure que « Ven de l'occitan ? », generalisee a 3 reponses (A/B/C).

function showQuiz(payload) {
  stopDiaporama();
  showOnly("quiz");

  $("quiz-progress").textContent = (payload.index + 1) + " / " + payload.total;
  renderSteps($("quiz-steps"), payload.index, payload.total);
  $("quiz-score").textContent = "Punts : " + payload.score;
  $("quiz-question").textContent = payload.question_fr || "";
  fitText($("quiz-question"), 18);

  const choices = { a: $("quiz-choice-a"), b: $("quiz-choice-b"), c: $("quiz-choice-c") };
  $("quiz-choice-a-label").textContent = payload.choice_a;
  $("quiz-choice-b-label").textContent = payload.choice_b;
  $("quiz-choice-c-label").textContent = payload.choice_c;

  const feedbackEl = $("quiz-feedback");
  const explanationEl = $("quiz-explanation");
  if (payload.feedback === "correct") setFeedback(feedbackEl, "Bravo !", "correct");
  else if (payload.feedback === "wrong") setFeedback(feedbackEl, "Fals !", "wrong");
  else if (payload.feedback === "timeout") setFeedback(feedbackEl, "Temps acabat !", "wrong");
  else setFeedback(feedbackEl, "", "");

  if (payload.feedback && payload.correct_choice) {
    explanationEl.textContent = payload.explanation || "";
    Object.entries(choices).forEach(([key, el]) => {
      setAnswerState(el, key === payload.correct_choice ? "right" : "dim");
    });
  } else {
    explanationEl.textContent = "";
    Object.values(choices).forEach((el) => setAnswerState(el, ""));
  }
  ["a", "b", "c"].forEach((k) => fitText($("quiz-choice-" + k + "-label"), 15));
  fitText(explanationEl, 14);

  if (!payload.feedback) {
    startTimer("quiz", "quiz-timer-bar", "quiz", payload.seconds_per_question * 1000, payload.time_left);
  } else {
    stopTimer("quiz", "quiz-timer-bar");
  }
}

function showQuizFin(payload) {
  stopDiaporama();
  stopTimer("quiz");
  showOnly("quizFin");
  setFin(screens.quizFin, $("quiz-fin-score"), $("quiz-fin-total"),
    String(payload.score), totalLabel(payload.total),
    starsForRatio(payload.total ? payload.score / payload.total : 0));
}

// --- Decor du modele Nuèch : ciel etoile (positions fixes, tirees une fois) --

(function buildSky() {
  const sky = $("sky");
  if (!sky) return;
  let seed = 7;
  const rand = () => {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  };
  for (let i = 0; i < 70; i++) {
    const star = document.createElement("i");
    star.style.left = (rand() * 100).toFixed(2) + "%";
    star.style.top = (rand() * 100).toFixed(2) + "%";
    star.style.opacity = (0.2 + rand() * 0.45).toFixed(2);
    if (rand() > 0.85) star.className = "twinkle";
    sky.appendChild(star);
  }
})();

// Bouton « Escota » de Descobèrta : rejoue la prononciation (souris/tactile).
$("object-audio-btn").addEventListener("click", () => {
  if (descobertaAudioFile) playObjectAudio(descobertaAudioFile);
});

// --- Rendu initial + raccourcis admin : volontairement AVANT la connexion
// websocket ci-dessous, et independants d'elle (14/09/2026). -----------------
//
// Bug corrige ce jour-la : ce bloc etait place APRES `const socket =
// io("/kiosk")`. Si la bibliotheque socket.io ne se chargeait pas (jusqu'ici
// servie depuis un CDN externe -- voir kiosk.html, desormais servie en local)
// `io` n'existait pas et cette ligne levait une erreur JS qui arretait
// l'execution du reste du fichier : ni le rendu de l'etat initial, ni le
// raccourci Ctrl+Alt+A, ni le clic sur l'icone Admin ne s'executaient jamais.
// L'ecran restait bloque sur le HTML brut envoye par le serveur (l'ecran
// "Pausa un objècte", seul ecran visible par defaut avant que le JS ne
// bascule sur le bon etat). En les mettant ici, ces trois choses fonctionnent
// meme si la connexion temps reel echoue -- seules les mises a jour EN DIRECT
// (un autre visiteur qui joue, par ex.) resteraient alors indisponibles,
// jamais l'ecran d'accueil ni l'acces admin.

// Etat initial fourni par le serveur au chargement de la page (evite un
// flash "accueil" avant la premiere connexion websocket).
renderState(window.MALETA_INITIAL_STATE);

// Raccourci admin (Ctrl+Alt+A) : le kiosque tourne en Chromium --kiosk, sans
// barre d'adresse, ce raccourci reste disponible en secours (au cas ou la
// manette ne serait pas branchee) en plus de l'icone Admin du menu -- Fabien
// a demande de garder les deux (14/09/2026). Choisi plutot que Ctrl+Alt+Suppr,
// deja intercepte par Debian lui-meme (redemarrage de la machine) avant meme
// que le navigateur ne voie l'appui clavier.
window.addEventListener("keydown", (event) => {
  if (event.ctrlKey && event.altKey && event.key.toLowerCase() === "a") {
    window.location.href = "/admin";
  }
});

// Souris/tactile (facultatif) : l'icone Admin reste egalement cliquable
// directement, pour un futur ecran tactile ou une souris branchee en admin,
// sans devoir passer par la manette. v0.8 : meme principe pour la nouvelle
// icone "Cadre fotó" (ex-tuile) -- clic direct = bascule veille, sans passer
// par /dev/action pour rester coherent avec un futur clic tactile reel.
document.addEventListener("DOMContentLoaded", () => {
  const adminIcon = document.getElementById("menu-admin-icon");
  if (adminIcon) {
    adminIcon.addEventListener("click", () => {
      window.location.href = "/admin";
    });
  }
  const diaporamaIcon = document.getElementById("menu-diaporama-icon");
  if (diaporamaIcon) {
    diaporamaIcon.addEventListener("click", () => {
      fetch("/dev/action/start_idle", { method: "POST" });
    });
  }
});

// --- Clavier (v0.8) ---------------------------------------------------------
//
// Demande par Fabien : en plus de la manette, chaque action logique peut
// aussi etre declenchee par une touche de clavier assignee depuis
// Configuration > Manèta & clavièr (voir managers/settings_manager.py,
// get_gamepad_key_map()) -- LES DEUX COEXISTENT, jamais l'un ne remplace
// l'autre. Le mapping {touche: action} est fourni au chargement de page
// (voir kiosk.html, window.MALETA_KEY_MAP) ; reutilise la route existante
// /dev/action/<action> (deja utilisee par le panneau de dev et par le clic
// souris ci-dessus), pas besoin d'une nouvelle route serveur puisqu'elle
// est deja non protegee et appelle directement game_controller.on_action().
//
// Garde-fous : ignore un appui accompagne de Ctrl/Alt/Meta (pour ne jamais
// interferer avec le raccourci Ctrl+Alt+A ci-dessus, ni avec un raccourci
// navigateur/systeme quelconque) ; meme normalisation de la touche que cote
// admin (config.html) pour que les cles stockees correspondent bien.
//
// v0.81 : une meme touche peut desormais declencher PLUSIEURS actions (ex.
// la touche Entree peut a la fois valider un menu et repondre a un quiz) --
// window.MALETA_KEY_MAP associe donc chaque touche a une LISTE d'actions
// (voir managers/settings_manager.get_gamepad_key_map) ; on les envoie
// toutes, sans risque puisque GameController.on_action() ignore deja toute
// action non pertinente pour l'ecran affiche.
//
// v1.03 (revue de code) :
// - une touche MAINTENUE enfoncee se repete toute seule (~2 fois par seconde
//   apres un demi-seconde) : chaque repetition etait envoyee comme un nouvel
//   appui -- ex. Entree gardee enfoncee sur la tuile du Quiz ouvrait le jeu
//   puis validait la premiere reponse. Les repetitions sont ignorees.
// - les actions d'une meme touche partaient en parallele et pouvaient
//   arriver au serveur dans le desordre : elles sont envoyees une par une,
//   dans l'ordre.
// - une touche assignee n'a plus d'effet navigateur en plus (ex. Espace ou
//   Entree sur un bouton qui aurait le focus).
let keyQueue = Promise.resolve();
window.addEventListener("keydown", (event) => {
  if (event.ctrlKey || event.altKey || event.metaKey) return;
  const keyMap = window.MALETA_KEY_MAP || {};
  const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
  const actions = keyMap[key] || [];
  if (actions.length === 0) return;
  event.preventDefault();
  if (event.repeat) return;
  keyQueue = keyQueue.then(async () => {
    for (const action of actions) {
      try {
        await fetch("/dev/action/" + encodeURIComponent(action), { method: "POST" });
      } catch (err) {
        console.error("[kiosk] action clavier non envoyee :", action, err);
      }
    }
  });
});

// --- connexion websocket (mises a jour en direct) -------------------------
//
// Protegee par ce garde-fou : si `io` n'existe pas (bibliotheque absente ou
// non chargee, voir plus haut), on le signale dans la console au lieu de
// planter -- l'ecran reste utilisable (etat initial + admin, voir ci-dessus),
// seules les mises a jour temps reel manquent.
if (typeof io === "function") {
  const socket = io("/kiosk");

  socket.on("connect", () => {
    console.log("[kiosk] connecte au serveur");
  });

  socket.on("state_changed", (payload) => {
    renderState(payload);
  });

  // Icone Admin du menu (voir showMenu ci-dessus / game_controller.py) :
  // evenement ponctuel, distinct de "state_changed", puisque selectionner
  // l'icone ne change aucun etat serveur -- seul le navigateur doit reagir.
  socket.on("open_admin", () => {
    window.location.href = "/admin";
  });
} else {
  console.error(
    "[kiosk] bibliotheque socket.io introuvable (static/js/socket.io.min.js) " +
    "-- l'ecran reste utilisable mais sans mises a jour en direct. " +
    "Voir README.md pour la reinstaller."
  );
}
