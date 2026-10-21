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


class SimulatedTagReader(TagReader):
    """Pour le developpement sans lecteur NFC branche."""

    def __init__(self):
        self._on_uid = None

    def start(self, on_uid):
        self._on_uid = on_uid
        logger.info("SimulatedTagReader demarre (mode dev, pas de materiel reel)")

    def stop(self):
        self._on_uid = None

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
            return

        self._on_uid = on_uid

        available = [str(r) for r in pcsc_readers()]
        if not available:
            logger.error(
                "Aucun lecteur PC/SC detecte - lecteur NFC desactive. Verifie : "
                "le lecteur OMNIKEY est branche, le service pcscd est demarre "
                "(`systemctl status pcscd`), et - en VM - que le passthrough "
                "USB du lecteur est actif cote hyperviseur."
            )
            return
        if self._reader_name_filter and not any(
            self._reader_name_filter.lower() in r.lower() for r in available
        ):
            logger.warning(
                "Aucun lecteur ne correspond au filtre %r parmi %s - "
                "utilisation du premier lecteur PC/SC disponible",
                self._reader_name_filter, available,
            )
        logger.info("Lecteurs PC/SC detectes : %s", available)

        outer_self = self

        class _TagObserver(CardObserver):
            def update(self, observable, actions):
                added_cards, _removed_cards = actions
                for card in added_cards:
                    outer_self._handle_card_added(card, toHexString)

        self._observer = _TagObserver()
        self._card_monitor = CardMonitor()
        self._card_monitor.addObserver(self._observer)
        logger.info("OmnikeyTagReader demarre (surveillance PC/SC active)")

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
