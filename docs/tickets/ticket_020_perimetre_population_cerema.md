# Ticket 020 — La même base ? Périmètre et définitions de population entre EMC²/CEREMA et la simulation

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source
> de vérité.
>
> ✅ **INSTRUIT ET RENDU le 2026-08-24.** Résultats :
> [`docs/arch/perimetre-population.md`](../arch/perimetre-population.md) · rapport grand
> public et traces : [`docs/traces/2026-08-24_perimetre_population/`](../traces/2026-08-24_perimetre_population/README.md).
> Outils livrés : `make communes-couronnes`, `make audit-perimetre`.
> Les deux verdicts « à corriger » (A2 couronnes, A4 hors périmètre) sont exécutés par le
> [ticket 021](ticket_021_couronne_residence_post_traitement.md), par post-traitement de la
> population — sans invalider de cache. L'axe A7 (mode principal) est repris par le
> [ticket 022](ticket_022_rabattement_mode_principal.md), qui le remesure par strate et le
> trouve **plus grave que son chiffre global**. La moitié corrigeable de l'axe A5 (la fenêtre
> de tirage de la météo des jeux gelés) est reprise par le
> [ticket 023](ticket_023_fenetre_meteo_jeux_geles.md), à mener selon le
> [protocole de paramètre exogène](../arch/protocole-parametre-exogene.md).
>
> **Nature du ticket** : *travaux d'instruction*, pas de correction. Il produit un
> **inventaire chiffré des écarts de base** entre la population interrogée par l'enquête
> et la population simulée, et tranche pour chacun : écart à corriger, écart à
> neutraliser dans le scoring, ou écart à publier comme limite. Aucun résultat de
> simulation n'est réputé lisible avant qu'il soit rendu.

## Pourquoi maintenant

Toute la chaîne de mesure du dépôt compare des parts modales simulées aux cibles de
[`cerema_values.yaml`](../../scripts/data/population/cerema_values.yaml) — globalement et
dans **huit sous-catégories** (lieu de résidence, genre, âge, occupation, type de logement,
motif, distance). Le score composite, la calibration de prompt, les campagnes génétiques et
la page de synthèse en dépendent tous.

Cette comparaison n'a de sens que si les deux côtés parlent de la **même population** et du
**même objet compté**. Ce n'est aujourd'hui pas établi : c'est supposé. Or les tickets
[015](ticket_015_acces_velo_progedo.md), [016](ticket_016_abonnement_tc_progedo.md),
[017](ticket_017_permis_progedo.md) et [019](ticket_019_habitat_taille_menage.md) ont tous
montré le même motif — un coefficient appris sur une variable, appliqué à une autre, et
l'écart invisible dans les agrégats. Le périmètre de population est le dernier maillon de
cette famille à n'avoir jamais été vérifié, et c'est le plus en amont : un biais de
périmètre déplace **toutes** les cibles à la fois.

Décision de priorité du 2026-08-24 : ce ticket passe **avant** de remettre du travail dans
la calibration de prompt (tickets [004](ticket_004_prompt_calibration_industrialisation.md)
et [009](ticket_009_calibration_genetique.md), mis en veille). Calibrer un prompt contre une
cible mal cadrée revient à calibrer l'instrument sur le biais.

---

## Trois constats déjà établis (lecture du dépôt, 2026-08-24)

Ces trois-là n'attendent pas la mesure : ils sont lisibles dans le code et les données.

### C1 — Les caractéristiques de la population enquêtée existent, et sont inertes

[`population_emc2_2023.yaml`](../../scripts/data/population/population_emc2_2023.yaml)
documente précisément le périmètre de l'enquête : 453 communes, 5 400 km², 1,4 M
d'habitants dont **1,32 M de 5 ans et plus** (la population cible), 674 000 ménages, taille
moyenne 2,08, découpage concentrique en 1 / 68 / 109 / 275 communes, variables de
redressement, populations exclues, périodes.

Deux problèmes :

1. **Aucun code ne lit ce fichier.** Une recherche sur tout le dépôt ne le trouve
   mentionné que dans un tableau de [`docs/setup/quickstart.md`](../setup/quickstart.md).
   Il n'alimente aucun contrôle, aucune cible, aucun test.
2. **L'essentiel est en commentaire.** Méthodologie, échantillon, territoire, totaux de
   population, équipement vélo, stationnement au domicile : commentés. Ne sont actifs que
   la répartition par âge, par occupation, et l'équipement voiture.

C'est un cas de la famille « vacuité » déjà tracée dans le projet : la donnée de cadrage
est là, elle a l'air d'être utilisée, elle ne l'est pas.

### C2 — Les couronnes ne sont pas définies comme celles de l'enquête

[`geo_reference.py:138-146`](../../llm_module/core/geo_reference.py:138) classe un point par
**distance à l'hypercentre** — moins de 8 km = `Toulouse`, moins de 20 km = `1ere couronne`,
moins de 40 km = `2eme couronne`, au-delà = `3eme couronne` — et son commentaire annonce que
« ce sont les modalités de `lieu_residence` de la référence EMC² ».

L'enquête, elle, découpe par **liste de communes** : Toulouse = 1 commune, 1ʳᵉ couronne =
68, 2ᵉ = 109, 3ᵉ = 275. Une couronne administrative n'est pas un anneau métrique. La commune
de Toulouse fait environ 118 km² — un disque de 8 km de rayon depuis l'hypercentre en sort
largement et mord sur Blagnac, Balma, Ramonville ou Colomiers, qui sont de 1ʳᵉ couronne dans
l'enquête.

L'enjeu est direct : la cible `voiture` vaut **31 %** à Toulouse et **64 %** en 1ʳᵉ
couronne. Un agent mal classé n'est pas comparé à une cible un peu décalée, il est comparé à
une cible qui diffère de plus de 30 points. Et depuis le
[ticket 013](ticket_013_temps_terminal_itineraires.md), ce même classement **facture** le
temps terminal (accès à l'origine, stationnement à destination) : l'erreur ne fausse pas
seulement la lecture, elle agit sur la simulation.

### C3 — L'enquête est d'automne-hiver, la simulation tire sa météo dans l'année

Période d'enquête : **20 septembre 2022 – 18 février 2023, hors vacances scolaires**.
Toutes les parts modales de `cerema_values.yaml` sont donc des parts d'automne et d'hiver,
en semaine, hors congés.

Les jeux gelés `v2` du [ticket 008](ticket_008_run_24h_mesures_synthese.md) tirent au
contraire la **météo dans l'année entière**. Comparer une simulation dont la météo peut être
un jour de juin à une cible mesurée entre septembre et février est un écart de base, et il
porte précisément sur le mode le plus sensible à la météo — le vélo, dont les mouvements de
4 à 5 points ont déjà arbitré plusieurs décisions du projet (tickets 013 et 014).

---

## Les axes à instruire

Pour chacun : mesurer l'écart entre la population simulée et la population enquêtée, puis
trancher (corriger / neutraliser dans le scoring / publier comme limite).

| # | Axe | Ce que dit l'enquête | À vérifier côté simulation |
|---|---|---|---|
| A1 | **Âge minimum** | Population cible = **5 ans et plus** (1,32 M sur 1,4 M) ; les classes de parts modales commencent à `5-9` | Des agents de moins de 5 ans existent-ils dans la population générée ? Sont-ils exclus du scoring, ou dilués dans la première classe ? |
| A2 | **Couronnes** (cf. C2) | Découpage par communes : 1 / 68 / 109 / 275 | Combien d'agents changent de couronne entre le classement métrique actuel et le classement communal ? Effet sur les parts modales par zone **et** sur le temps terminal facturé |
| A3 | **Pondération** | Redressement CEREMA (non-réponse + RP2019) sur taille de ménage, motorisation, âge, occupation, sexe ; poids `COE0` (ménages) et `COEP` (déplacements) | Les parts simulées sont-elles des comptes bruts ? Le [ticket 019](ticket_019_habitat_taille_menage.md) a déjà basculé la loi du logement en pondération ménages — le même raisonnement s'applique-t-il ailleurs ? |
| A4 | **Populations exclues** | Touristes et visiteurs, populations spécifiques (EHPAD…), flux de marchandises | La population synthétique contient-elle des équivalents ? Le bassin d'emploi importe-t-il des déplacements que l'enquête ne compte pas ? |
| A5 | **Période et saison** (cf. C3) | 20/09/2022 – 18/02/2023, hors vacances scolaires | Distribution de météo et de jour-type des jeux gelés. Faut-il restreindre le tirage à la fenêtre d'enquête pour la mesure, tout en gardant l'année pleine pour la simulation ? |
| A6 | **Jour de semaine** | Méthode EMC² : déplacements de la veille, en semaine | Les runs comparés sont-ils bien des jours de semaine ? Le report week-end→lundi existant (`compute_next_move`) n'introduit-il pas de jours atypiques dans le scoring ? |
| A7 | **Objet compté : le déplacement** | Un déplacement, un **mode principal** — la marche d'accès à un bus n'est pas un déplacement à pied | Depuis le [ticket 013](ticket_013_temps_terminal_itineraires.md), accès et diffusion sont portés par des **jambes nommées** : ces jambes sont-elles comptées comme déplacements dans `moves.csv` ? Si oui, la marche est surestimée par construction |
| A8 | **Structure de ménage** | Taille moyenne 2,08 ; 674 000 ménages ; 19 % sans voiture, 1,25 voiture/ménage | Écarts sur la population générée. Les 118 grappes incomplètes et 8 collisions d'adresse documentées par le [ticket 015](ticket_015_acces_velo_progedo.md) faussent-elles la comparaison ? |
| A9 | **Représentativité spatiale de l'échantillon** | 70 % des habitants de 5 ans et plus en Toulouse + 1ʳᵉ couronne | Le `toulouse_population_1000.json` respecte-t-il cette concentration ? Un excès de Toulouse tire la part voiture vers le bas de plus de 30 points sans qu'aucun modèle soit en cause |

---

## Lots

1. **Lot 1 — Rendre le cadrage opposable.** Décommenter et valider
   `population_emc2_2023.yaml` (ce qui est vérifiable dans les publications CEREMA ; ce qui
   ne l'est pas est supprimé, pas laissé en commentaire), lui donner un chargeur validant
   dans `llm_module/core/`, et le brancher sur un contrôle exécutable — sur le modèle de
   `make housing-type` du ticket 019, dont le bloc de validation interne s'exécute à chaque
   génération. Une valeur de cadrage sans lecteur est une valeur fausse en attente.

2. **Lot 2 — Mesurer les neuf axes.** Un script d'audit
   (`scripts/data/population/audit_perimetre.py`, `make audit-perimetre`) qui prend une
   population générée et un run, et publie un tableau écart par écart : valeur enquête,
   valeur simulée, écart, et le verdict retenu. Sortie archivée dans `docs/traces/`, jamais
   dans un dossier volatil.

3. **Lot 3 — Trancher C2.** Substituer au classement métrique un classement **par commune**
   (la liste des 453 communes et leur couronne est la donnée manquante), ou démontrer par la
   mesure que l'écart de classement est négligeable — et l'écrire. Attention : ce classement
   facture le temps terminal, donc tout changement demande un bump de `version` dans
   [`terminal_time.yaml`](../../llm-agents/config/terminal_time.yaml) et invalide trois
   caches. À coordonner avec la correction de calibre en attente du ticket 013.

4. **Lot 4 — Trancher A5/A7.** Deux décisions de protocole, pas de code : la fenêtre de
   météo utilisée **pour la mesure**, et le statut des jambes d'accès dans le comptage des
   déplacements. Chacune est soit corrigée, soit inscrite aux limites de la publication.

---

## Critères d'acceptation

- [x] Les neuf axes ont **chacun** une valeur enquête, une valeur simulée et un verdict
      écrit. Aucun axe n'est laissé « non mesuré » : un axe non mesuré est un axe qui
      passe, et c'est exactement le motif de vacuité que le projet traque.
      → 2 conformes (A1, A6), 2 à corriger (A2, A4), 5 à publier (A3, A5, A7, A8, A9).
      `make audit-perimetre` sort **3** si un axe devient non mesurable.
- [x] `population_emc2_2023.yaml` est chargé par du code et vérifié par un test ; plus
      aucun bloc de cadrage ne dort en commentaire.
      → `llm_module/core/population_reference.py` + 17 tests. Chaque valeur est en outre
      **recalculée depuis les microdonnées** (`--recompute`), ce qui a corrigé 54 785 →
      54 585 déplacements et 68/109 → 69/108 communes. Les blocs vélo, stationnement et
      télétravail sont supprimés, non rétablis.
- [x] Le classement en couronnes est **identique** entre `geo_reference.py` et les modalités
      `lieu_residence` de `cerema_values.yaml`, ou l'écart résiduel est mesuré et publié.
      → **Écart mesuré et publié**, pas corrigé : 249/1 021 personas (24,4 %) changent de
      couronne ; L1 par zone 47,8 pt sous le classement publié contre 50,7 sous le
      classement correct. La bascule invalide trois caches et ouvre son propre ticket.
      Le référentiel nécessaire est livré (`make communes-couronnes`).
- [x] La fenêtre saisonnière de la mesure est explicite, et cohérente avec la période
      d'enquête ou justifiée de ne pas l'être.
      → Explicite, et **révisé le 2026-08-24** après vérification de la période de
      référence de l'enquête (méthodologie CEREMA + dates de référence des microdonnées) :
      l'enquête porte bien sur la fenêtre — déplacements de la veille, aucune observation
      de mars à août — mais elle **publie « un jour moyen de semaine »**. L'écart n'est
      donc pas saisonnier, il est de **moyennage**, et il se sépare : biais **thermique**
      de +5,3 °C sur le tirage des jeux gelés (corrigeable en le restreignant à la
      fenêtre), et **variance** d'un run de 5 jours face à une moyenne de 152 (non
      corrigeable — 27,7 % des séquences de 5 jours de la période d'enquête sont
      elles-mêmes sèches, et les jours simulés sont thermiquement au 56ᵉ–81ᵉ centile de
      la fenêtre). Publié comme limite de variance.
- [x] Le comptage des déplacements simulés répond à la définition EMC² du déplacement à
      mode principal, ou l'écart est chiffré (part de marche imputable aux jambes d'accès).
      → **Part de marche imputable aux jambes d'accès : zéro.** Les jambes terminales
      portent `is_transfer=True` et l'enquête ne code aucun trajet à pied dans un
      déplacement voiture ou TC (0 sur 39 743). En revanche la **hiérarchie est inversée**
      (voiture avant TC ; l'enquête code 760/770 mixtes en TC) : latent aujourd'hui,
      1,41 pt de la cible TC hors d'atteinte. ⚠ La mesure PAR STRATE faite pour le
      [ticket 022](ticket_022_rabattement_mode_principal.md) montre que ce chiffre global
      était trompeur : jusqu'à **59 % de la cible TC** est perdue sur la tranche 20-50 km,
      et 31 % en 2ᵉ couronne.
- [x] Les écarts non corrigés figurent dans les limites de la publication, avec leur
      amplitude — jamais en tant que « supposé négligeable ».
      → Cinq limites chiffrées, § « Limites à publier » de
      [`docs/arch/perimetre-population.md`](../arch/perimetre-population.md).
- [x] Aucun écart n'est réputé nul faute de mesure.
      → Le code de sortie **3** de `make audit-perimetre` existe pour ça, et A1 est
      documenté « conforme par héritage, garanti par aucune assertion » plutôt que
      « conforme ».

## Hors périmètre

- **Corriger les écarts trouvés.** Ce ticket les établit et les qualifie ; les corrections
  qui dépassent un ajustement de mesure ouvrent leurs propres tickets.
- **Le millésime des données d'appariement** (ENTD 2008) : c'est la cause identifiée des
  tickets 016 et 017, traitée là-bas.
- **Le choix du nouveau jeu de test** : décidé hors de ce ticket, mais ce ticket en fixe
  les contraintes de périmètre.

## Sources

- [`scripts/data/population/population_emc2_2023.yaml`](../../scripts/data/population/population_emc2_2023.yaml)
  — caractéristiques de la population interrogée, EMC² CEREMA 2023, bassin de vie toulousain.
- [`scripts/data/population/cerema_values.yaml`](../../scripts/data/population/cerema_values.yaml)
  — parts modales cibles, huit dimensions.
- [`llm_module/core/geo_reference.py`](../../llm_module/core/geo_reference.py) — classement
  en couronnes (`COURONNE_BOUNDS_KM`, `residence_zone`).
- [`docs/arch/score-synthesis.md`](../arch/score-synthesis.md) — usage des cibles dans le
  score composite.
- Microdonnées **EMC² Toulouse 2023**, ProGEDO/ADISP `lil-1750` — pondérations `COE0`,
  `COEP`, pour toute vérification que les publications ne permettent pas.
