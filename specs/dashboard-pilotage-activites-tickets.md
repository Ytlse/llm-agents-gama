# Spec — Pilotage : expériences en cours, onglet Activités, statut des tickets

## Problème

La vue d'ensemble du tableau de bord ne dit pas si une expérience ou la préparation d'un jeu
tourne en ce moment ; il faut aller dans l'onglet Expériences pour le savoir. L'onglet
« Commandes » double des actions que chaque onglet porte désormais lui-même, et « Lancements »
ne dit pas ce qu'il contient. Changer le statut d'un ticket oblige à éditer à la main un
fichier YAML de 1 470 lignes.

## Utilisateurs

- **Le chercheur** qui pilote la plateforme sur sa machine : seul utilisateur, application
  locale, tous droits (lecture et écriture du dépôt). Aucun autre rôle.

## Règles métier

### Vue d'ensemble

- **R1** — Une tuile « Expériences » liste chaque exécution d'expérience à l'état `en_cours`
  avec son avancement (déplacements faits / attendus, pourcentage, reste estimé). L'état est lu
  dans les fichiers de l'exécution, pas dans le registre de jobs : une exécution lancée depuis un
  terminal est vue aussi.
- **R2** — La même tuile liste chaque jeu de déplacements **non clos** : avec sa progression
  (faits / total, pourcentage, reste) quand elle existe, « en préparation » sinon.
- **R3** — Sans exécution ni jeu en cours, la tuile dit « aucune expérience en cours » et donne
  deux compteurs : expériences définies, exécutions terminées.
- **R4** — La tuile se rafraîchit au même rythme que les autres tuiles de la vue (10 s).
- **R4b** *(déduite)* — Un fichier de progression absent, tronqué ou aux champs manquants ne
  casse pas la vue : la ligne est affichée avec « ? » pour les valeurs inconnues, le pourcentage
  est borné à [0, 100].

### Onglet Commandes

- **R5** — L'onglet « Commandes » disparaît. Plus aucun texte de l'interface n'y renvoie : les
  trois renvois actuels (évals payantes de la synthèse, `make ui` de la calibration, message de
  l'onglet vide) donnent à la place la commande à taper dans un terminal.
- **R6** *(déduite)* — Les boutons contextuels des onglets Run GAMA, Providers, Calibration et
  Expériences, qui empruntaient le même chemin que Commandes, fonctionnent à l'identique :
  registre de jobs, journal dans `experiments/.dashboard/`, arrêt par « Stop ».

### Onglet Activités en cours

- **R7** — L'onglet « Lancements » s'appelle « Activités en cours ». Tous les messages
  « suivi dans 📟 Lancements » (y compris ceux de l'onglet Expériences) utilisent le nouveau nom.
- **R8** *(déduite)* — L'onglet montre en tête les exécutions et jeux en cours (mêmes données que
  R1–R2), puis les jobs `make` : **ceux qui tournent d'abord**, les terminés ensuite, le plus
  récent en premier à l'intérieur de chaque groupe, avec la purge de l'historique.
  Raison : le nom promet *toutes* les activités ; une exécution démarrée hors du tableau de bord
  n'apparaîtrait sinon nulle part dans cet onglet.

### Exécutions arrêtées (ajouté le 2026-09-09)

- **R31** — Entre les deux blocs existants, l'onglet liste chaque exécution **arrêtée et
  reprenable**, avec la **cause** de son arrêt : quota épuisé, coupure réseau / passerelle
  injoignable, PC ou conteneur arrêté, pause automatique, pause voulue, arrêt incomplet. La
  cause est **dérivée de ce qui est écrit** — `etat.json` (état, raison, heure de reprise
  annoncée), fraîcheur de `progression.json`, type de la dernière ligne de `erreurs.jsonl` — et
  le détail affiché cite toujours la ficelle d'origine. Une cause hors de cette liste s'affiche
  « inconnue » avec l'état brut : rien n'est inventé pour combler le trou.
- **R32** — Les causes que seul `erreurs.jsonl` peut nommer — **prompt refusé**, **sous-agent
  muet**, **passerelle saturée**, **coupure réseau** — ne remplacent que les causes qui ne se
  nomment pas elles-mêmes : sur une exécution épuisée, le quota et son heure de reprise
  l'emportent. Leur ordre de priorité est porteur de sens : la **saturation avant le réseau**,
  `passerelle_occupee: Timeout expiré` étant une passerelle débordée et non un câble coupé.
- **R32b** — Le détail affiche le **message** du dernier échec, pas seulement son type : c'est
  lui qui dit quoi corriger (`variante de prompt 'expert_chaine_m5' introuvable dans
  prompts.yaml`). S'y ajoutent l'**instance** qui a lâché (champ `fournisseur` de l'erreur) et
  le **nombre d'échecs identiques consécutifs**, borné par la fenêtre relue et alors préfixé
  `≥` — écrire « 12 fois de suite » sur un mur de 800 lignes serait faux.
- **R33** — Chaque ligne porte **« ▶ Reprendre »** (`make experience-reprendre`, services requis
  garantis d'abord) et le nombre de décisions déjà archivées, qui ne seront pas repayées.
- **R34** — N'y figurent ni une **archive scellée** (immuable, E19), ni une exécution qui tourne
  ou dort en attente de quota (elle repartira seule), ni une exécution **obsolète** ; les
  obsolètes qui auraient été reprenables sont **comptées** en légende, jamais escamotées.
- **R35** — Une durée restante s'écrit en `hh:mm:ss`, partout où elle s'affiche (exécution, jeu,
  registre), heures non bornées à 24. « reste ≈ 6765 s » ne se lit pas.

### Exécutions obsolètes (ajouté le 2026-09-09)

- **R36** — Une exécution qui n'est pas la **plus récente** de son expérience est *obsolète*.
  C'est un état de **vue** calculé à la lecture, jamais écrit dans `etat.json` : le runner reste
  seul propriétaire de l'état réel.
- **R37** — Une exécution obsolète n'est pas reprenable, parce que `make experience-reprendre`
  ne porte que sur la dernière exécution de l'expérience. « ▶ Reprendre » et l'avertissement
  « a une exécution reprenable » du formulaire s'en tiennent donc à la dernière.
- **R38** — Le registre l'annonce dans sa colonne `etat` **avec ce qu'elle coûte** :
  « obsolète (résultat complet) » sur une exécution menée à terme — ses scores restent lisibles
  et comparables —, « obsolète (partielle) » sinon.
- **R39** — La case « Terminées seulement » est remplacée par **« Masquer les obsolètes »**,
  cochée d'office. Elle masque, compte ce qu'elle masque, et se décoche d'un clic. La dernière
  exécution de chaque expérience reste toujours visible.

### Fournisseur des décisions (ajouté le 2026-09-09)

- **R45** — Le registre porte une colonne **`fournisseur`** après `decideur`, et chaque ligne
  d'exécution des deux blocs de l'onglet Activités en cours en est **préfixée**. La valeur est
  dérivée de `providers.yaml` : `local` pour une instance LM Studio (reconnue à son `base_url`),
  sinon l'`adapter` de l'instance — `google`, `groq`, `cerebras`, `mistral`, `openai`… — jamais
  le nom d'instance, qui porte un suffixe `_key1`.
- **R46** — Un décideur `antigravity` affiche `antigravity` quel que soit le nom de son modèle :
  la décision passe par un sous-agent, pas par la passerelle. Un décideur qui ne sollicite aucun
  LLM affiche `—` et **aucun préfixe**. Un modèle absent de `providers.yaml` affiche `inconnu` ;
  un modèle servi par plusieurs familles les affiche toutes (`cerebras · groq`).
- **R47** — Le fournisseur suit le **snapshot figé** de l'exécution, comme le décideur et le
  prompt (R6) : afficher celui de la définition courante mentirait sur l'archive.

### Démarrage des services (ajouté le 2026-09-09)

- **R40** — Le bouton « Démarrer les N service(s) manquant(s) » disparaît. Le **lancement**
  garantit lui-même les services dont il a besoin : `make experience-lancer`,
  `experience-reprendre`, `experience-lancer-arret` et `jeu` commencent par
  `make services-pretes REQUIS="…"` (`docker compose up -d --no-recreate --wait`, idempotent,
  borné par `ATTENTE`, 600 s par défaut). La garantie vaut donc aussi depuis un terminal.
- **R40b** *(déduite, non négociable)* — Cette garantie ne recrée **jamais** un conteneur
  (`--no-recreate`) : recréer `controller` tuerait le runner d'une expérience en cours, qui y
  vit par `docker compose exec`, alors que la cible est chaînée à chaque lancement — y compris
  pendant qu'une autre expérience travaille. Elle démarre ce qui manque, rien d'autre.
- **R41** — Le bloc « 🐳 Services nécessaires » reste, en lecture seule, et **annonce à
  l'avance** le nombre de services à démarrer : un démarrage à froid coûte plusieurs minutes de
  chargement des graphes OTP/OSMnx, visibles dans le journal du lancement.
- **R42** — Un `controller` éteint ne grise plus « ▶ Lancer » ni « 🔥 Warm-up ». Il grise encore
  « 🧮 Estimer le coût », qui lit la réponse de la plateforme en direct. Ce qui grise le
  lancement, c'est un **démon Docker muet** : là, rien ne peut être démarré.
- **R43** *(déduite)* — `REQUIS=` (ce qu'on garantit avant de lancer) et `SERVICES=` (ce qu'on
  arrête à la fin) sont deux variables distinctes : les confondre arrêterait ce qu'on vient de
  démarrer.

### Arrêt d'une exécution (modifié le 2026-09-09)

- **R44** — La case « Je confirme l'arrêt définitif » est retirée : « ⏹ Arrêter » est cliquable
  directement. Ce qui garde ce geste irréversible : le libellé, l'aide au survol, et une
  légende sous les deux boutons qui écrit la différence entre pause et arrêt. Les deux boutons
  continuent de disparaître sur une exécution qui n'écrit plus (correctif du 2026-09-08).

### Statut des tickets

- **R9** — Dans le détail de chaque ticket, l'utilisateur choisit un statut parmi le vocabulaire
  fermé (`à faire`, `en cours`, `terminé`, `bloqué`, `en veille`, `abandonné`), peut modifier la
  note, et « Enregistrer » écrit dans la source de vérité des statuts.
- **R10** — L'écriture préserve à l'octet tout ce qui n'est pas l'entrée modifiée : commentaires
  d'en-tête, ordre des entrées, notes et style des autres tickets.
- **R11** — Un ticket sans entrée dans la source de vérité en reçoit une à l'enregistrement, avec
  pour clé le **nom de fichier complet** (jamais la forme courte), ajoutée en fin de liste.
- **R12** — Après enregistrement, le tableau, les compteurs et le détail reflètent le nouveau
  statut sans redémarrer l'application ; la colonne « Source » affiche « surcharge ».
- **R13** *(déduite)* — Enregistrer sans rien changer (même statut, même note, entrée déjà
  présente) n'écrit pas le fichier : pas de modification git parasite.
- **R14** *(déduite)* — L'enregistrement relit le fichier au moment du clic et n'y applique que
  le changement demandé : une édition manuelle faite entre-temps n'est pas écrasée. Cela vaut
  aussi pour la note du ticket édité : une note laissée telle qu'elle s'affichait n'est pas
  réécrite, donc une modification faite à la main dans le fichier lui survit.
- **R15** *(déduite)* — Une note vidée retire la clé `note` de l'entrée ; une note non vide est
  écrite en bloc replié (`>-`) replié autour de 88 colonnes, comme les notes existantes. Les
  espaces multiples d'un paragraphe sont normalisés, les paragraphes séparés par une ligne
  vide sont conservés.
- **R16** *(déduite)* — Le sélecteur est pré-positionné sur le statut en vigueur (surchargé ou
  déduit). Un statut « sans statut » n'est pas proposé à l'enregistrement.

### Jeu de déplacements : ce que le formulaire voit

- **R17** — Un jeu en préparation apparaît dans la liste des jeux de sa population, marqué
  « en préparation » et accompagné de sa progression. L'avertissement « aucun jeu préparé » ne
  s'affiche que si la population n'a réellement aucun jeu, préparé ou en cours.
- **R18** — Tant qu'un jeu de la population choisie est en préparation, ou qu'une construction
  vient d'être lancée, le bloc de progression du formulaire se rafraîchit seul toutes les 5 s.
  Quand la liste des jeux de cette population change — un jeu apparaît, ou devient clos — la page
  se recharge une fois d'elle-même pour que le jeu devienne sélectionnable, sans action manuelle.
- **R19** — Le bouton de construction du jeu est désactivé tant qu'une construction tourne pour
  ce nom de jeu, avec le motif écrit. Un jeu non clos dont rien n'écrit plus la progression reste
  relançable : la construction reprend où elle s'était arrêtée.
- **R20** — Les quatre boutons d'action du formulaire d'expérience, « ⏹ make stop-run » et
  « ▶ Reprendre » disent **en une ligne écrite** ce qui leur manque : nom d'expérience vide,
  aucun jeu, jeu non clos, service `controller` arrêté, registre de lancements absent, aucun run
  en cours, aucune exécution reprenable. Et **aucun** bouton désactivé du tableau de bord ne reste
  sans aucun signal : à défaut d'une ligne écrite, il porte une aide au survol qui dit ce qu'il
  attend. Une case « Je confirme » ou un champ requis vide placés juste à côté sont des signaux
  visibles, mais ils ne dispensent pas de l'aide au survol. La règle vaut pour **tout contrôle**
  désactivé, pas seulement les boutons : un champ numérique ou une case grisés portent aussi leur
  aide au survol.

### Ce que l'utilisateur a saisi

- **R27** *(déduite)* — Le texte saisi dans une note n'est jamais jeté. S'il a été modifié dans
  le formulaire, il gagne sur une édition concurrente du fichier : c'est une intention explicite.
  S'il ne l'a pas été, la valeur du fichier est conservée (R14), et le tiroir dit que la note y a
  changé depuis l'ouverture. Aucun message ne peut annoncer « rien à enregistrer » alors que du
  texte a été saisi : une retouche qui ne change que des espaces n'écrit rien — ils sont
  normalisés à l'écriture (R15) — et le tiroir dit **cela**, pas l'inverse. La comparaison porte
  donc sur le texte tel qu'il sera stocké, jamais sur la frappe brute.
- **N1** *(spec `nommage-canonique-experiences.md`)* — Le nom d'une expérience **ne se saisit
  plus** : il se calcule de ses paramètres et le formulaire l'affiche. R29 et R30 ci-dessous en
  gardent la seule part qui subsiste : la garde à l'écriture (un nom sert à construire un chemin
  et une variable `make`) et l'obligation de dire ce qui manque quand aucun nom n'est composable.
- **R29** *(déduite, amendée par N1)* — Le nom d'une expérience ne porte que des caractères de mot Unicode, plus
  tiret, souligné et point, 64 au plus, et commence par une lettre ou un chiffre. Il devient un
  nom de dossier sous `data/experiences/` **et** la valeur de `EXP=` passée à `make`, qui
  développe `$(EXP)` sans guillemets dans une commande shell. Ce qui est refusé est donc ce qui
  est dangereux — séparateurs de chemin, espaces, métacaractères — et non ce qui est inhabituel :
  « Prompt_Éco » est valide. L'écriture le refuse de son côté (`enregistrer` lève) : le nom étant
  calculé, cette garde ne s'exerce plus sur une frappe mais sur un défaut de programmation.
- **R30** *(déduite, remplacée par N1)* — Il n'y a plus de nom à corriger, donc plus
  d'identifiant sûr à proposer : le formulaire montre le nom calculé, et quand un paramètre
  l'empêche (`decideur.modele` vide) le motif sous le bouton grisé **nomme ce paramètre** au lieu
  de constater un nom vide. Rien n'est renommé en silence, et rien n'est inventé pour combler le
  trou.

### Robustesse et honnêteté de l'affichage

- **R23** *(déduite)* — Un statut inconnu dans le fichier des statuts — une faute de frappe faite
  à la main, que R14 rend légitime — n'affiche aucun ticket et le dit dans l'onglet Tickets, en
  nommant la valeur fautive et les valeurs admises. Il n'interrompt pas les autres onglets.
- **R24** *(déduite)* — Une exécution en cours affiche l'âge de sa progression ; au-delà de dix
  minutes sans écriture, sa ligne le signale. **Un jeu en préparation de même**, au-delà de deux
  minutes : son manifeste reste `clos: false` si son conteneur est tué, et sa dernière barre
  resterait affichée indéfiniment. L'âge est écrit dans la tuile compacte comme dans l'onglet. Aucun gel n'est diagnostiqué : une pénurie de quota
  peut légitimement faire attendre, seul le fait « plus rien d'écrit depuis N minutes » est écrit.
  Sans ce repère, une exécution dont le conteneur a été tué garde `en_cours` et sa dernière barre
  indéfiniment — le symétrique exact de l'incident qui a motivé R18.
- **R25** *(déduite)* — Un ticket sans entrée dans le fichier des statuts le dit dans son tiroir,
  avec la source de son statut affiché, avant tout enregistrement : rien ne doit laisser croire
  que `à faire` pré-sélectionné est une décision déjà prise.
- **R28** *(déduite)* — Toute clé du fichier des statuts désigne **exactement un** ticket. Une clé
  courte (`ticket_005`) ou mal orthographiée est refusée, en nommant les tickets qu'elle viserait :
  la première appliquerait un seul statut aux deux tickets qui partagent ce numéro, la seconde ne
  s'appliquerait à rien — on croirait avoir posé un statut qui n'est nulle part. L'écriture la
  refuse aussi, sans quoi l'interface produirait un fichier qu'elle ne saurait plus relire. Une
  clé invalide et un statut inconnu sont **deux causes distinctes** : chacune s'affiche avec la
  sienne, jamais celle de l'autre.
- **R26** *(déduite)* — Les cibles `make` documentées restent listables hors du tableau de bord.
  L'onglet Commandes était le seul endroit qui les montrait toutes ; le supprimer sans rien mettre
  à la place rendrait invisible un catalogue de 79 cibles.

### Mémoire du formulaire

- **R21** — Les choix du formulaire sont conservés sur disque et restaurés au démarrage suivant du
  tableau de bord, dans un fichier ignoré par git.
- **R21b** *(déduite)* — Un fichier de reprise illisible, ou portant une valeur qui n'existe plus
  (population supprimée, variante de prompt retirée, jeu effacé), ne bloque pas le formulaire :
  chaque valeur inconnue revient à son défaut, les autres sont conservées.
- **R22** *(déduite)* — La restauration ne remplit que les champs du formulaire. Aucun fichier
  `experience.yaml` n'est écrit sans clic sur « Enregistrer », « Estimer » ou « Lancer ».

## Critères d'acceptation

- **R1** — une exécution dont `etat.json` dit `en_cours` et dont `progression.json` dit
  `faits=120, attendus=400, pourcent=30, reste_s=600` → la tuile affiche « 120 / 400 · 30 % ·
  reste ≈ 600 s » pour cette exécution ; une exécution `terminee` n'y figure pas.
- **R2** — un jeu dont le manifeste n'est pas `clos` et dont la progression dit `1753 / 2693`
  → ligne « 1753 / 2693 · 65 % » ; sans fichier de progression → « en préparation » ; un jeu
  `clos` n'y figure pas.
- **R3** — aucun `en_cours`, tous jeux clos, 3 expériences définies et 5 exécutions terminées →
  « aucune expérience en cours · 3 définies · 5 exécutions terminées ».
- **R4** — la tuile est dans le fragment rafraîchi toutes les 10 s (même mécanisme que les
  tuiles Services / Run / Providers).
- **R4b** — `progression.json` contenant `{}` ou un JSON tronqué → ligne affichée avec « ? »,
  aucune exception ; `pourcent=140` → barre pleine. Jeu non clos, dont le manifeste ne porte
  encore ni `couverts` ni `attendus` → son libellé dans la liste dit « ?/? déplacements », jamais
  « None/None ».
- **R5** — la liste des onglets ne contient plus « Commandes » ; `grep -n "Commandes"` sur les
  fichiers du tableau de bord ne renvoie rien.
- **R6** — cliquer « 🔄 make synthesis » dans l'onglet 📊 Métriques appelle le registre avec la
  cible résolue depuis le Makefile ; un job lancé porte son journal, et « Stop » l'arrête.
- **R7** — la liste des onglets contient « Activités en cours » et `grep -n "Lancements"` sur
  les fichiers du tableau de bord ne renvoie rien.
- **R8** — un jeu en préparation apparaît en tête d'Activités en cours même si aucun job `make`
  n'est enregistré dans le registre ; avec un job terminé et un job encore en cours plus ancien,
  celui qui tourne s'affiche au-dessus.
- **R9** — choisir `terminé` sur le ticket 011 et enregistrer → l'entrée
  `ticket_011_arrivees_perdues_gama` du fichier porte `status: terminé`.
- **R10** — après l'enregistrement de R9, le `diff` du fichier ne touche que les lignes de
  l'entrée du ticket 011 (statut, note) : aucune autre ligne ajoutée, retirée ou déplacée.
- **R11** — un ticket `ticket_099_test` sans entrée, enregistré `en cours` → nouvelle entrée
  `ticket_099_test:` en fin de liste, avec `status: en cours` ; la clé `ticket_099` n'apparaît
  pas.
- **R12** — après R9, la ligne du ticket 011 dans le tableau affiche 🟢 `terminé`, source
  « surcharge », et le compteur « Terminé » a augmenté de 1 sans redémarrage.
- **R13** — enregistrer le ticket 011 avec son statut et sa note actuels → la date de
  modification du fichier ne change pas.
- **R14** — modifier à la main la note du ticket 002 pendant que le détail du 011 est ouvert,
  puis enregistrer le 011 → la note du 002 modifiée à la main est conservée.
- **R15** — note vidée → l'entrée ne contient plus de clé `note` ; note « ligne 1 ligne 2 »
  → écrite en `>-`.
- **R16** — un ticket sans entrée dont les cases donnent `en cours` → sélecteur sur `en cours` ;
  l'option « sans statut » n'est pas dans la liste.

- **R17** — un dossier de jeu dont le manifeste porte `clos: false` → le jeu figure dans la liste
  de sa population, libellé « EN PRÉPARATION », et l'avertissement « aucun jeu préparé » est
  absent ; population sans aucun dossier de jeu → avertissement présent.
- **R18** — un jeu passe de `clos: false` à `clos: true` pendant que la page est ouverte → dans
  les 5 s le jeu devient sélectionnable et clos, sans clic ; la page ne se recharge pas en boucle
  une fois l'état stabilisé.
- **R19** — progression du jeu écrite il y a 10 s → bouton de construction désactivé, motif
  « une construction est déjà en cours » ; progression vieille de 10 min → bouton actif.
- **R20** — nom d'expérience vide → sous les boutons, « ▶ Lancer indisponible : le nom de
  l'expérience est vide » ; nom renseigné et jeu clos et contrôleur actif → aucun motif affiché
  et le bouton est actif. Au premier chargement, chaque bouton désactivé de toute la page porte
  une aide au survol non vide.
- **R23** — le fichier des statuts porte `status: a faire` (sans accent) → l'onglet Tickets
  affiche une erreur nommant la valeur et la liste admise, aucun ticket n'est listé, et l'onglet
  🧪 Expériences reste affiché.
- **R24** — progression d'une exécution écrite il y a 3 s → la ligne dit « progression écrite il
  y a 3 s » ; écrite il y a 15 minutes → « ⚠ plus rien d'écrit depuis 15 min » ; le mot « gelée »
  n'apparaît pas. Jeu en préparation dont la progression date de 20 minutes → « ⚠ plus rien
  d'écrit depuis 20 min », dans l'onglet **et** dans la tuile compacte.
- **R25** — ticket dont le statut vient des cases à cocher → son tiroir dit qu'il n'a pas
  d'entrée et donne la source ; ticket surchargé → aucune mention de ce genre.
- **R26** — `make help` liste au moins la cible `dashboard` avec sa documentation, et ne cite
  aucune ligne `.PHONY`.
- **R27** — la note du ticket est modifiée dans le formulaire pendant qu'elle change dans le
  fichier → le texte saisi est écrit, aucun message ne dit « rien à enregistrer » ; note non
  touchée et fichier modifié → la valeur du fichier est conservée et le tiroir le dit ; note
  retouchée d'un double espace seulement → rien n'est écrit et le tiroir dit que ce sont les
  espaces, pas « rien à enregistrer ».
- **R28** — une clé `ticket_005` dans le fichier → `load_tickets` refuse en nommant les deux
  tickets 005, et l'onglet Tickets annonce une **clé** invalide, pas un statut inconnu ; une clé
  `ticket_faute` → refus disant qu'elle ne désigne aucun ticket ; enregistrer sous la clé
  `ticket_005` → refusé sans rien écrire ; les clés réellement présentes dans le fichier passent.
- **R29** — nom `../../evade` → boutons désactivés avec le motif, et `enregistrer` lève ; noms
  `premiere_minimal`, `Prompt_Éco` et `jeu.v5-1` → acceptés ; noms `Prompt Minimaliste`, `a/b`,
  `-flag` et `a;rm -rf` → refusés.
- **N1/R30** — le formulaire n'a plus de champ « Nom de l'expérience » ; le nom calculé est
  affiché une fois et satisfait R29 ; un modèle non choisi laisse le nom vide et le motif du
  bouton grisé cite `decideur.modele` ; une définition déjà enregistrée est annoncée comme telle
  (« lancer ajoutera une exécution ») ; une définition différente de même nom calculé reçoit
  l'indice `_2`.
- **R21** — remplir le formulaire, redémarrer l'application, réouvrir l'onglet → population,
  jeu, prompt, modèle, mode et réglages avancés sont ceux d'avant le redémarrage (le nom, lui,
  se recalcule et n'est plus retenu).
- **R21b** — fichier de reprise tronqué → formulaire aux valeurs par défaut, aucune exception ;
  fichier citant une variante de prompt absente, un jeu effacé ou un modèle retiré → chacune de
  ces trois valeurs revient au défaut (la variante au prompt **actif**, pas au premier de la
  liste), les réglages valides sont conservés.
- **R22** — redémarrer avec un formulaire restauré et n'appuyer sur rien → aucun dossier créé
  sous `data/experiences/`.

## Non-goals

- Ne pas écrire de statut dans les fichiers `.md` des tickets, ni modifier leur contenu.
- Ne pas supprimer d'entrée du fichier des statuts depuis l'interface.
- Ne pas ajouter de champ (date, auteur) au fichier des statuts : git porte l'historique.
- Ne pas déplacer le catalogue des cibles `make` ailleurs ; il disparaît de l'interface.
- Ne pas toucher au registre de jobs ni au mécanisme de lancement / arrêt.
- Ne pas gérer d'authentification ni d'accès concurrent entre plusieurs utilisateurs.
- Ne pas afficher les exécutions en pause ou épuisées dans la tuile de la vue d'ensemble : elles
  restent dans l'onglet Expériences, où l'on peut les reprendre.
- Ne pas valider les deux saisies qui désignent un chemin **côté conteneur** : « Dossier
  d'exécution à rejouer », et le champ « Population » libre qui n'apparaît qu'en l'absence de
  population scellée sur le disque. Le tableau de bord ne peut pas les résoudre — ils sont
  interprétés dans le conteneur — et R29 ne couvre que le nom d'expérience, dont le tableau de
  bord fait lui-même un dossier de l'hôte.

## Sécurité

- Application locale, mono-utilisateur, sans authentification — inchangé.
- La seule écriture nouvelle est le fichier des statuts de tickets. Le statut vient d'un
  sélecteur à vocabulaire fermé ; la note est du texte libre écrit comme scalaire YAML par la
  bibliothèque, jamais interprétée : pas d'injection YAML possible par construction.
- La saisie qui devient un chemin **sur l'hôte** est validée (R29) : le nom d'expérience construit
  `data/experiences/<nom>/`, et `../../` y écrirait ailleurs dans le dépôt. Les deux saisies qui
  désignent un chemin côté conteneur traversent sans validation, c'est un non-goal assumé ci-dessus.
  Les variables passées à `make` partent en liste d'arguments, jamais dans un shell.
- Les fichiers `progression.json`, `etat.json` et les manifestes de jeux sont écrits par le
  conteneur : entrées non fiables. Leurs valeurs sont affichées, bornées, jamais exécutées ni
  utilisées pour construire un chemin ou une commande.
- Rien de ce qui est affiché ne contient de secret ; les journaux de jobs restent dans
  `experiments/.dashboard/`, ignoré par git.

## Questions ouvertes

Aucune : les quatre questions ont été tranchées par le GO du 2026-09-06, chacune sur le défaut
proposé.

1. Libellé de l'onglet : « 📟 Activités en cours ». **Tranché.**
2. Catalogue `make` : code de l'onglet Commandes supprimé, pas replié ailleurs. **Tranché.**
3. La note est éditable en même temps que le statut. **Tranché.**
4. L'onglet Activités en cours montre aussi les exécutions et jeux lus sur disque. **Tranché.**
