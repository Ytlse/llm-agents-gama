# Une cohorte disjointe tirée du même vivier

## Problème

L'axe 2 du [ticket 073](../docs/tickets/ticket_073_reproductibilite_prompt_calibre_multi_graines_multi_populations.md)
demande au moins une cohorte supplémentaire pour mesurer si le prompt calibré est sur-appris sur
`population_1000_AAMAS_v6`. Le scelleur ne sait pas en produire : l'ordre d'entrée des ménages
vient de `sha256("aamas_seal_v4:" + household_id)`, un sel écrit en dur, si bien que rejouer la
sélection sur le même vivier redonne exactement la même cohorte. Rien ne permet aujourd'hui
d'obtenir une seconde cohorte, ni de garantir qu'elle ne recouvre pas la première.

**Décision de l'auteur du 2026-09-22 : une seule cohorte supplémentaire**, disjointe de la v6.

## Utilisateurs

L'auteur de l'article, depuis la ligne de commande, sur sa machine. Aucun autre appelant : le
scellement produit un artefact de référence cité par les jeux gelés et par le chapitre 6, il ne
tourne pas dans un service.

## Ce que cette cohorte permet, et ce qu'elle ne permet pas

À écrire avant les règles, parce que ça borne l'usage du livrable.

Elle permet de **constater un écart** entre la cohorte de référence et une cohorte indépendante
tirée du même territoire : le prompt calibré donne-t-il un composite du même ordre sur des gens
qu'il n'a jamais vus ?

Elle ne permet pas de **décomposer la variance**. L'ANOVA à deux facteurs de la section 3 du
ticket 073 exige plusieurs cohortes ; avec une seule, il n'y a ni écart-type inter-cohortes ni
η². Elle ne permet pas non plus de conclure sur le critère `Δ_gen < 1,0 point` tel que le ticket
l'écrit : chaque cohorte mesure son composite à ±1,3 point près, les deux mesures ne sont pas
appariables — ce sont des gens différents —, donc l'incertitude sur leur différence est de
l'ordre de ±1,8 point. Un Δ_gen observé sous 1,8 ne se distinguera pas de zéro, et un Δ_gen
au-dessus dira qu'il se passe quelque chose sans dire quoi.

C'est un constat, pas une objection : un écart unique et honnêtement borné vaut mieux qu'une
dispersion inventée sur deux points.

## Règles métier

- **R1** — Le tirage accepte une liste de cohortes déjà scellées ; les ménages qu'elles retiennent
  sont retirés du vivier avant toute sélection.
- **R2** — La disjonction porte sur le **ménage** (`household.id`), pas sur la personne. Un ménage
  retenu par une cohorte antérieure est exclu en entier, y compris les membres qu'elle n'a pas
  retenus.
- **R3** — La cohorte produite n'a aucun `person_id` ni aucun `household.id` en commun avec les
  cohortes exclues.
- **R4** — Le `MANIFEST.yaml` nomme les cohortes exclues et le sha256 de chacune. Un manifeste qui
  ne dit pas de quoi la cohorte est disjointe ne vaut rien : la disjonction n'est pas relisible
  sur le fichier de population.
- **R5** — La règle de sélection se déclare `aamas_seal_v5_disjoint` quand le vivier est amputé.
  `aamas_seal_v5` reste réservé à une sélection sur vivier entier : deux cohortes tirées sur des
  viviers différents ne peuvent pas porter la même étiquette de méthode.
- **R6** — Le contrôle territorial s'applique inchangé : mêmes marges, même borne TOST (± 1,0 pt),
  mêmes seuils `n_min` (30) et `n_min_cellule` (50). Un verdict « à corriger » refuse le
  scellement, comme aujourd'hui. Le vivier réduit n'achète aucune indulgence, et l'échec est un
  échec — on ne relâche rien, on ne recouvre rien.
- **R7** *(déduite)* — Un déficit de cellule causé par l'exclusion se signale comme tel, et se
  distingue d'un déficit du vivier entier. Les deux ont la même conséquence — alarme et code de
  sortie 1 — mais pas le même remède : le premier dit que l'exclusion est de trop, le second que
  le vivier ne couvre pas la cible.
- **R8** *(déduite)* — L'ordre d'entrée des ménages reste celui du hachage existant. Le sel ne
  change pas : c'est l'exclusion qui produit une cohorte différente, et elle suffit. Changer le
  sel *et* exclure rendrait impossible de dire lequel des deux a produit l'écart observé.
- **R9** *(déduite)* — Une cohorte ne peut pas s'exclure elle-même, ni exclure une cohorte dont le
  sha256 ne correspond plus au fichier qu'elle désigne. Les deux cas sont des erreurs explicites
  avant tout calcul.
- **R10** *(déduite)* — L'exclusion est vérifiée *après* sélection, sur le résultat, et pas
  seulement appliquée en entrée. Un filtre en entrée qui se tromperait de clé produirait une
  cohorte recouvrante sans que rien ne le dise, et l'axe 2 serait publié sur du sable.

## Critères d'acceptation

- **R1** — Tirer en excluant `population_1000_AAMAS_v6` → le vivier passe de 5 652 à 5 153 ménages
  (499 exclus), et le journal l'écrit.
- **R2** — Un ménage de 4 personnes dont la v6 n'a retenu que 3 membres → les 4 sont hors du
  vivier réduit.
- **R3** — Intersection des `person_id` et des `household.id` entre la cohorte produite et la v6 :
  vides toutes les deux.
- **R4** — Le `MANIFEST.yaml` porte le nom et le sha256 de chaque cohorte exclue ; retirer ce champ
  fait échouer le test.
- **R5** — Le manifeste d'une cohorte tirée sur vivier réduit porte `aamas_seal_v5_disjoint`, et
  jamais `aamas_seal_v5`.
- **R6** — Une cohorte dont une marge sort de la borne TOST n'est pas scellée : rien n'est écrit,
  le fichier candidat reste en place, le rapport dit laquelle.
- **R7** — Exclusions telles qu'une cellule ne se remplit plus → message nommant la cellule,
  l'effectif disponible et l'effectif requis, code de sortie 1.
- **R8** — À exclusion vide, le tirage redonne exactement la cohorte v6, au sha256 près
  (`412efada…31db6`).
- **R9** — Exclure une cohorte dont le `population.json` a été modifié depuis son scellement →
  erreur avant tout calcul, citant le sha256 attendu et le sha256 lu.
- **R10** — Injecter artificiellement un ménage déjà pris dans le résultat de la sélection → la
  vérification finale échoue et rien n'est scellé.

## Non-goals

- **Préparer le jeu gelé** de cette cohorte (offre d'itinéraires OTP, météo). C'est l'étape
  suivante, elle a son propre outil (`experiences preparer-jeu`) et son propre coût.
- **Définir ou lancer l'expérience** de l'axe 2.
- **Changer la règle de sélection elle-même** : l'allocation par sous-cellule, la descente sur
  marges et les cibles restent ce qu'elles sont. Seul le vivier d'entrée change.
- **Produire plusieurs cohortes.** Décision de l'auteur du 2026-09-22. Le mécanisme d'exclusion
  accepte une liste, donc une seconde cohorte reste possible plus tard sans retoucher le
  dispositif — mais rien n'est fait ni testé pour l'enchaînement de plusieurs tirages.
- **Rendre le tirage reproductible depuis un autre vivier.** Le vivier est identifié par son
  sha256 ; un autre vivier est un autre chantier.

## Sécurité

Aucune entrée réseau, aucun contenu produit par un LLM. Les entrées sont des fichiers du dépôt,
sous le contrôle de l'auteur. Le seul risque d'écrasement est déjà couvert : un dossier scellé ne
se modifie pas, et le scelleur refuse d'écrire dans un `--out-dir` existant. Les données sont des
personas synthétiques — aucune donnée personnelle réelle, malgré les noms générés.

La fragilité réelle est ailleurs : une cohorte qui recouvre silencieusement la v6 invaliderait
l'axe 2 sans qu'aucun message ne le signale, et le résultat serait publié. D'où R3 et R10, qui
vérifient le résultat au lieu de faire confiance au filtre.

## Questions ouvertes

Aucune. **Taille tranchée le 2026-09-22 : 1 000 personas**, comme `population_1000_AAMAS_v6` —
comparaison directe avec le composite publié au § 6.1, contrôle territorial conforme, ≈ 930
requêtes au fournisseur.

Écarté au passage, et consigné parce que le chiffre resservira : à N = 100, huit cellules sur
douze tombent sous le seuil de mesurabilité de 30 (« 2nd ring × une voiture » vaut 4, « 1st ring
× sans voiture » vaut 2), la cohorte n'est pas scellable sous R6, et son composite porte un
intervalle de l'ordre de ±4 points — quatre fois l'écart cherché. Le plancher de conformité est
≈ 770 personas.
