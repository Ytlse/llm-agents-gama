# Ticket 035 — questions ouvertes (document vivant)

> Une question figure ici tant que ni le code ni l'utilisateur n'y ont répondu. Quand elle est
> tranchée, elle passe dans « Décisions prises » (une ligne, la date) et l'hypothèse **[H]** du
> design devient une règle. Chaque question ouverte est écrite avec un **exemple concret** : c'est
> ce que la relecture du 2026-09-06 a demandé (« c'est quoi ? », « pas compris »).

## Questions ouvertes

*Aucune au 2026-09-06 (second tour).* Reste **à faire**, pas à trancher : lancer
`make jeu-verifier-jours` sur un jeu réel de la population v5 (il faut OTP pour préparer le jeu).

**Ouverte au 2026-09-08 — `gabarit.variante` entre dans la signature d'une expérience qui ne lit
pas de prompt.** `construire_experience` écrit toujours la variante choisie au formulaire, et
`nommage.signature()` prend le sha256 de la définition entière : deux expériences LightGBM qui ne
diffèrent que par ce prompt inerte portent le **même nom calculé** (N5 le retire) mais des
signatures différentes, donc reçoivent un indice `_2` — deux identités pour une seule expérience
réelle. Même effet dans l'archive : `empreintes.gabarit` d'un run LightGBM porte le sha d'un texte
jamais envoyé (`prompts.yaml:minimal_persona` dans `exp_lgbm_jtir_nosim`), et `jetons_mesures`
filtre les archives sur cette empreinte — sans conséquence pratique, un run LightGBM n'ayant
aucun jeton à médianiser. Le corriger (écrire `variante: null` hors passerelle) changerait la
signature des expériences déjà sur disque. **Rien n'est fait par défaut** ; l'affichage, lui, ne
prête plus la variante à ces décideurs (`_prompt_affiche`, cf. changelog du 2026-09-08).

## Décisions prises (2026-09-06)

| # | Décision | Effet dans le code |
|---|---|---|
| 4 | Reprise à chaud au **début de la journée en cours** | `make run CONT=1` rejoue la journée ; décisions archivées resservies |
| 5 | Rien n'est perdu : décisions acquises, positions des véhicules (rejouées depuis les décisions), mémoire (LTM du workdir) ; seules les sollicitations en vol à l'instant de la pause sont redemandées | `runner.py` (rejeu de la chaîne à la reprise) |
| 7 | Réplications = exécutions **indépendantes**, listées sous l'expérience | `Execution.creer` ne réécrit jamais ; registre |
| 10 | Horizon > 1 jour sans simulateur : **refusé** | `refuser_si_impossible` (S3) |
| 12 | Registre : **un maximum d'information**, `moves.csv` enrichi | colonnes « Source des propositions », « Écartées (motifs) », « Identifiant lot » ; synthèse avec méthodes, sources, écartées, fournisseurs |
| 13 (révisée 2026-09-08) | **Deux régimes, l'attente par défaut.** Épuisement confirmé → on **attend la fenêtre en process** (état `en_attente_quota`, réveil à l'heure annoncée par le fournisseur, à défaut minuit dans son fuseau) ; `--ne-pas-attendre-fenetre` restaure l'arrêt en `epuisee` + reprise à chaud. L'attente est devenue le défaut le 2026-09-08, la réouverture étant désormais connue et bornée. Dans les deux cas, aucune substitution ni décision par défaut | R4 ; `runner._attendre_fenetre_quota` ; `experience-lancer` |
| 10 bis / Q10 (révisée 2026-09-07) | **`attente_max_s` = seuil d'alarme, pas borne** (décision a). Une erreur transitoire est réessayée sans limite (pause croissante plafonnée 60 s, interruptible) : **aucun déplacement n'est sauté** (R1) ; au-delà de `attente_max_s`, `[ALARME]` sur front montant | `runner.executer` ; `erreurs.jsonl` + `execution.log` + `experiences erreurs` (R2/R3) ; cf. spec 05 Q10 |
| 14 | Événements : **prévoir l'évolution**, description chargée par GAMA | modèle `Evenement` figé (type, jour, heures, cible, description, source) ; accepté et archivé, exécution refusée tant que GAMA ne le joue pas |
| 15 | `batch_<id>_<n>` archivé tel quel (identifiant du lot de la passerelle) : sert à reconstituer la taille des lots et à chercher un effet de position dans le lot ; aucune modification de la passerelle | trace `identifiant_lot`, colonne « Identifiant lot » |
| 16 | `zone` : donnerait au modèle le type de quartier de destination (« habitat rural dispersé sur la commune de … ») ; **non utilisée aujourd'hui**, on ne l'ajoute pas (changer le texte présenté changerait l'empreinte du gabarit et la comparabilité avec les runs passés) | aucun |
| 17 | Généraliser la recréation du contrôleur : le gain est que `make run CACHE=0` prenne enfin effet (un contrôleur déjà lancé ne relit pas `config.yaml`) | `make run` recrée le contrôleur dès que `config.yaml` diffère de la copie appliquée (`.config.yaml.applique`) |
| 18 | **Le mardi joue l'offre TC du mardi** ; les week-ends sont ignorés | tout autre jour que celui du jeu recalcule transit/rail (`recalculee:offre_jour`), marche/vélo/voiture servis ; sauf jour déclaré équivalent après mesure (`EQUIVALENCES.yaml`, cf. question 9) ; sans simulateur, une date non équivalente est refusée |
| 1 | **Une question par déplacement.** Une question par personne-journée ferait recalculer 100 % de la population à minuit dans la simulation, avec la mémoire en jeu ; on préfère lisser | comportement actuel confirmé ; `regime_applique.unite_sollicitation = deplacement` |
| 2 | **L'empreinte suffit** : le jeu est un objet régénérable identifié par le sha256 de son contenu, cité dans chaque résultat ; pas de dossier de sceau | `empreintes.jeu.sha256` dans `execution.yaml` ; péremption = avertissement + `--accepter-perime` |
| 6 | Regroupement hors de la règle de comparabilité : **un seul modèle** servira aux mesures | E13 inchangée ; régime archivé |
| 9 + 18 | **Le mardi joue l'offre du mardi — sans tout recalculer.** On lit dans le GTFS si chaque course proposée (ligne, arrêt de montée, heure de départ) existe le jour visé : déplacement valide → servi du jeu ; course absente → ses TC seulement sont recalculés ; jour jamais vérifié → TC recalculés (on ne suppose rien). Ce que la lecture ne voit pas : une course **nouvelle** ce jour-là ; la méthode « moteurs » (échantillon OTP) reste pour cela | `experiences/offre_jour.py`, `make jeu-verifier-jours NOM=… JOUR=… [METHODE=gtfs\|moteurs] DECLARER=1`, `EQUIVALENCES.yaml` à côté du MANIFEST (intact) ; **mesure sur la population v5 encore à faire** (il faut un jeu réel, donc OTP) |
| 11 | Heure de référence = **départ programmé** | inchangé, déclaré dans le MANIFEST |
| 15, 16 | On reste comme maintenant | — |
| 3 | Déplacements sans aucune proposition des moteurs (85 sur 5 257 au dernier run : trajets longs depuis des lieux sans TC) : **à exclure**, inexploitables, mais **remontés en WARNING** | trace `inexploitable`, exclus des attendus (couverture = décidés / exploitables, exclus affichés), WARNING à la préparation du jeu et à l'exécution |
| 8 | Le retard de départ des agents est un sujet GAMA préexistant, traité séparément (ou jamais) ; les tolérances proposées restent (marche/vélo insensibles, voiture à l'heure pleine, TC 10 min) | inchangé ; modifiables dans `experience.yaml` / `config.yaml` |
| 18 (précisée) | Vérifier qu'une course existe **ne suffit pas** : une course ajoutée ailleurs peut donner un meilleur itinéraire. Règle sûre : offre identique ⇔ **grille horaire identique** (toutes les courses, tous les arrêts). Sinon un déplacement n'est servi du jeu que si **aucun passage différent ne tombe dans sa fenêtre temporelle** (départ → départ + 4 h, borne rigoureuse dans le temps, sans hypothèse spatiale) ; tout autre déplacement recalcule ses TC | `experiences/offre_jour.py` : différence des grilles (les identifiants distincts qui décrivent le même passage s'annulent), validité par fenêtre, `--fenetre-h` ; résultat par déplacement dans `EQUIVALENCES.yaml` |
