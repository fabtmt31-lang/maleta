"""Abstraction du lecteur NFC.

Meme esprit que sur Histoires du Soir : un import "materiel" ne doit jamais
empecher le reste de l'appli de demarrer (import paresseux, uniquement au
moment de start()), et un seul point d'entree (`on_uid`) qu'on branche a la
logique applicative -- que le tag serve a jouer ou a etre associe a un objet
depuis l'admin, c'est a l'appelant de decider quoi faire de l'UID recu.

Pivot materiel (13/09/2026) : la cible n'est plus le Raspberry Pi + PN532
(I2C) mais un petit PC x86 sous Debian, avec un lecteur OMNIKEY en USB/PC-SC.
Le TODO Pn532TagReader qui existait dans cette etape est remplace par
OmnikeyTagReader, qui reprend la brique deja validee sur Histoires du Soir
(lecteur OMNIKEY 5422 utilise comme lecteur de test PC, abstraction pyscard/
CardMonitor confirmee fonctionnelle y compris en headless moyennant deux
regles polkit pour pcscd). Ici ce lecteur devient le lecteur de production :
plus besoin de maintenir deux lecteurs en parallele.

Deux implementations :

- SimulatedTagReader : utilisee en mode "dev" (config.HARDWARE_MODE == "dev"),
  tant qu'on developpe/teste sans lecteur branche. Pas de polling reel : on
  declenche un scan "a la main" via simulate_uid(), ce que fait l'admin
  (bouton "Simuler un scan") et le panneau /dev/panel. Inchangee depuis
  l'etape 1.

- OmnikeyTagReader : lecteur PC/SC reel (OMNIKEY 5422 ou compatible) via
  pyscard. Utilisee en mode "pc" (et toujours acceptee sous l'alias "pi"
  pour ne pas casser une config.py existante).
"""

import logging
import threading

logger = logging.getLogger(__name__)


class TagReader:
    """Interface commune. Ne pas instancier directement."""

    def start(self, on_uid):
        """on_uid: callable(uid: str) -> None, appelee a chaque nouveau tag pose."""
        raise NotImplementedError

    def stop(self):
        raise NotImplementedError

    def status(self):
        """v1.22 : etat du lecteur pour le tableau de bord de l'admin.
        dict {"kind": "simulated"|"pcsc", "connected": bool, "readers": [...],
        "message": str}."""
        raise NotImplementedError


class SimulatedTagReader(TagReader):
    """Pour le developpement sans lecteur NFC branche."""

    def __init__(self):
        self._on_uid = None

    def start(self, on_uid):
        self._on_uid = on_uid
        logger.info("SimulatedTagReader demarre (mode dev, pas de materiel reel)")

    def stop(self):
        self._on_uid = None

    def status(self):
        return {"kind": "simulated", "connected": True, "readers": [],
                "message": "Lecteur simulé (mode dev / démo, pas de lecteur réel)"}

    def simulate_uid(self, uid):
        """Appelee depuis une route Flask (kiosque en test, ou admin) pour
        simuler la pose d'un tag sans avoir de lecteur physique."""
        if self._on_uid is None:
            logger.warning("simulate_uid appele alors que le reader n'est pas demarre")
            return
        logger.info("Tag simule : %s", uid)
        self._on_uid(uid)


class OmnikeyTagReader(TagReader):
    """Lecteur PC/SC reel (OMNIKEY 5422 ou compatible) via pyscard.

    Repris de la brique deja validee sur Histoires du Soir :
    - CardMonitor/CardObserver de pyscard pour detecter l'arrivee d'un tag
      sans polling manuel
    - lecture de l'UID via la commande PC/SC standard "Get Data"
      (FF CA 00 00 00), qui fonctionne pour la quasi-totalite des tags
      NFC/MIFARE passes sur un lecteur PC/SC -- methode deja eprouvee sur
      HDP, pas une nouvelle piste a valider
    - import de `smartcard` fait a l'interieur de start() (import paresseux) :
      si pyscard ou pcscd ne sont pas installes/actifs, l'erreur n'arrive
      qu'au demarrage reel du lecteur, jamais au simple import de ce module

    Decision deja actee (reprise de HDP, cf. concept-borne-interactive.md) :
    declenchement uniquement a l'ARRIVEE du tag, le retrait n'a aucun effet
    -- pas de callback on_removed, coherent avec l'interface TagReader/on_uid
    deja en place dans app.py.

    Pre-requis systeme (voir install.sh) :
    - paquets : pcscd, libpcsclite-dev (ou libpcsclite1 a l'execution), swig,
      python3-dev, build-essential
    - pip : pyscard
    - service pcscd demarre et actif
    - regles polkit pour un acces headless a pcscd (pas de session graphique
      active au sens polkit -- obligatoire sur un Debian CLI sans bureau)
    """

    # Commande PC/SC standard pour recuperer l'UID d'une carte/tag contactless
    _GET_UID_APDU = [0xFF, 0xCA, 0x00, 0x00, 0x00]

    def __init__(self, reader_name_filter="OMNIKEY"):
        """reader_name_filter : sous-chaine a retrouver dans le nom du lecteur
        PC/SC (utile si plusieurs lecteurs sont presents en meme temps, ex.
        en VM avec plusieurs devices USB passthrough). None pour prendre le
        premier lecteur PC/SC trouve, quel qu'il soit."""
        self._reader_name_filter = reader_name_filter
        self._on_uid = None
        self._card_monitor = None
        self._observer = None
        self._lock = threading.Lock()
        # v1.22 : surveillance du lecteur (voir _watch). `_readers` : derniers
        # lecteurs PC/SC vus ; `_problem` : message d'erreur courant (pyscard
        # ou pcscd absent), None si tout va bien.
        self._readers = []
        self._problem = None
        self._stop_event = threading.Event()
        self._watch_thread = None

    def start(self, on_uid):
        # Import paresseux : ne casse rien si pyscard/pcscd sont absents tant
        # qu'on n'a pas reellement besoin du lecteur.
        try:
            from smartcard.CardMonitoring import CardMonitor, CardObserver
            from smartcard.util import toHexString
            from smartcard.System import readers as pcsc_readers
        except ImportError as exc:
            logger.error(
                "pyscard n'est pas installe ou pcscd n'est pas accessible (%s) "
                "- lecteur NFC desactive. Voir install.sh (paquets "
                "systeme pcscd/libpcsclite-dev/swig, puis `pip install pyscard`).",
                exc,
            )
            self._problem = "pyscard non installé (voir install.sh)"
            return

        self._on_uid = on_uid
        self._pcsc = (CardMonitor, CardObserver, toHexString, pcsc_readers)
        # v1.22 : avant, un lecteur absent au demarrage (branche apres coup,
        # pcscd pas encore pret) desactivait le NFC jusqu'au redemarrage du
        # service. Le lecteur est desormais surveille en tache de fond.
        self._stop_event.clear()
        self._watch_thread = threading.Thread(target=self._watch, name="nfc-watch", daemon=True)
        self._watch_thread.start()

    # Intervalle de surveillance du lecteur (secondes).
    WATCH_SECONDS = 5

    def _watch(self):
        """Toutes les WATCH_SECONDS : liste les lecteurs PC/SC, active la
        lecture des tags des qu'un lecteur est present, et journalise chaque
        changement (branche / debranche) une seule fois -- pas a chaque tour."""
        was_present = None
        while not self._stop_event.is_set():
            available = self._list_readers()
            present = bool(available)
            if present != was_present:
                if present:
                    logger.info("Lecteur(s) PC/SC detecte(s) : %s", available)
                    self._warn_if_filter_mismatch(available)
                elif was_present:
                    logger.warning("Lecteur NFC debranche - en attente de son retour")
                else:
                    logger.error(
                        "Aucun lecteur PC/SC detecte - nouvelle tentative toutes les %s s. "
                        "Verifie : le lecteur OMNIKEY est branche, le service pcscd est demarre "
                        "(`systemctl status pcscd`), et - en VM - que le passthrough USB du "
                        "lecteur est actif cote hyperviseur.",
                        self.WATCH_SECONDS,
                    )
                was_present = present
            if present and self._card_monitor is None:
                self._attach_monitor()
            self._stop_event.wait(self.WATCH_SECONDS)

    def _list_readers(self):
        pcsc_readers = self._pcsc[3]
        try:
            available = [str(r) for r in pcsc_readers()]
            self._problem = None
        except Exception as exc:  # pcscd arrete, contexte PC/SC impossible...
            available = []
            if self._problem is None:
                logger.error("Service PC/SC inaccessible (%s) - pcscd est-il demarre ?", exc)
            self._problem = "Service pcscd inaccessible"
        with self._lock:
            self._readers = available
        return available

    def _warn_if_filter_mismatch(self, available):
        if self._reader_name_filter and not any(
            self._reader_name_filter.lower() in r.lower() for r in available
        ):
            logger.warning(
                "Aucun lecteur ne correspond au filtre %r parmi %s - "
                "utilisation du premier lecteur PC/SC disponible",
                self._reader_name_filter, available,
            )

    def _attach_monitor(self):
        CardMonitor, CardObserver, toHexString, _ = self._pcsc
        outer_self = self

        class _TagObserver(CardObserver):
            def update(self, observable, actions):
                added_cards, _removed_cards = actions
                for card in added_cards:
                    outer_self._handle_card_added(card, toHexString)

        try:
            self._observer = _TagObserver()
            self._card_monitor = CardMonitor()
            self._card_monitor.addObserver(self._observer)
        except Exception:
            logger.exception("Impossible de demarrer la surveillance des tags - nouvel essai")
            self._card_monitor = None
            self._observer = None
            return
        logger.info("OmnikeyTagReader demarre (surveillance PC/SC active)")

    def status(self):
        with self._lock:
            readers = list(self._readers)
        if self._problem:
            message = f"{self._problem} — le lecteur est recherché toutes les {self.WATCH_SECONDS} s"
        elif readers:
            message = "Lecteur détecté : " + ", ".join(readers)
        else:
            message = f"Aucun lecteur branché — recherché toutes les {self.WATCH_SECONDS} s"
        return {"kind": "pcsc", "connected": bool(readers), "readers": readers, "message": message}

    def _handle_card_added(self, card, to_hex_string):
        # v1.03 (revue de code) : la connexion PC/SC est desormais refermee
        # explicitement une fois l'UID lu (elle restait ouverte jusqu'au
        # ramasse-miettes), et le traitement applicatif du tag (base de
        # donnees, changement d'ecran...) se fait APRES, hors du verrou du
        # lecteur et sans garder la carte ouverte pendant ce temps.
        uid = None
        with self._lock:
            connection = None
            try:
                connection = card.createConnection()
                connection.connect()
                data, sw1, sw2 = connection.transmit(self._GET_UID_APDU)
                if (sw1, sw2) != (0x90, 0x00):
                    logger.warning(
                        "Reponse inattendue a la lecture d'UID (sw1=%02X sw2=%02X) - tag ignore",
                        sw1, sw2,
                    )
                    return
                uid = to_hex_string(data).replace(" ", "")
            except Exception:
                logger.exception("Erreur pendant la lecture d'un tag")
                return
            finally:
                if connection is not None:
                    try:
                        connection.disconnect()
                    except Exception:
                        pass

        logger.info("Tag detecte, UID=%s", uid)
        if self._on_uid:
            try:
                self._on_uid(uid)
            except Exception:
                logger.exception("Erreur pendant le traitement du tag %s", uid)

    def stop(self):
        self._stop_event.set()
        if self._card_monitor and self._observer:
            self._card_monitor.deleteObserver(self._observer)
        self._card_monitor = None
        self._observer = None
        self._on_uid = None


def get_tag_reader(hardware_mode):
    # "pi" reste accepte comme alias pour ne pas casser un config.py/variable
    # d'environnement MALETA_HARDWARE existants -- il pointe desormais vers
    # l'OMNIKEY (PC/SC), plus vers le PN532.
    if hardware_mode in ("pi", "pc", "omnikey"):
        return OmnikeyTagReader()
    return SimulatedTagReader()
