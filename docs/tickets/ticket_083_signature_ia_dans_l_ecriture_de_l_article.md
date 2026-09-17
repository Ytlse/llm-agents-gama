# Ticket 083 — L'écriture de l'article ne doit pas porter la signature d'une IA : détecteur calé sur le corpus, contrôle après écriture, et reprise des chapitres 3, 4, 6 et 8

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-15, à la demande de l'auteur.
>
> **Catégorie** : Rédaction & Publication (📄)
>
> **Touche l'article** : OUI pour le lot C, qui réécrit des passages de `docs/paper/article/fr/`
> et `en/`. Chaque écriture passe par la procédure du verrou (skill `article-verrou`) : diff
> présenté, arrêt, accord. Les lots A et B ne touchent pas l'article.

## Le fait

Une évaluation à double insu lit un manuscrit rédigé avec assistance. Les marqueurs d'écriture
générée ne sont pas une question de goût : ils se mesurent, et sur ce corpus ils se concentrent
dans les chapitres les moins retravaillés.

Passe du 2026-09-15 sur les 15 chapitres rédigés (11 FR, 4 EN). Densités calculées sur la prose
seule, après retrait des blocs de code, tableaux, schémas ASCII, cibles de liens, listes de
tickets et lignes d'en-tête éditorial (`**Statut :**`, `**Version antérieure :**`, etc.) :

| Chapitre | mots de prose | cadratins/1k | gras/1k |
|---|---|---|---|
| fr/02_related_work | 1211 | 0,0 | 0,0 |
| fr/01_introduction | 2952 | 0,7 | 6,1 |
| en/02_related_work | 1051 | 0,0 | 0,0 |
| en/01_introduction | 2690 | 0,7 | 7,1 |
| fr/03_architecture | 1771 | 13,0 | 4,5 |
| en/03_architecture | 1845 | 15,2 | 5,4 |
| fr/04_metrics_and_substrate | 1907 | 13,1 | 27,8 |
| fr/05_factual_neutral_prompt | 2996 | 12,0 | 18,0 |
| fr/06_ablation | 1131 | 11,5 | 20,3 |
| fr/07_untabulated_regimes | 519 | 1,9 | 23,1 |
| fr/08_limits_and_hybrid | 332 | 9,0 | 36,1 |
| fr/09_conclusion | 415 | 7,2 | 16,9 |
| fr/99_annexes | 686 | 17,5 | 19,0 |
| fr/00_abstract | 373 | 8,0 | 21,4 |
| en/00_abstract | 333 | 9,0 | 24,0 |

**Le corpus porte sa propre norme.** Les chapitres 1 et 2, les plus relus par l'auteur (l'introduction
compte quinze versions archivées), sont typographiquement nus : 0,0 et 0,7 cadratin pour 1000 mots,
0,0 et 6,1 gras. Les brouillons montent à 17,5 et 36,1. Un facteur 20 sépare `fr/02` de `fr/99`.
Le seuil du détecteur n'a donc pas à être importé : il se lit dans les chapitres déjà validés.

Ce qui a été relevé, par famille.

**A. Trois défauts typographiques.** Une incise fermée par cadratin immédiatement suivi d'une
virgule, séquence incorrecte en français comme en anglais : `fr/03:39` (« niveau de revenu —, la
destination »), `en/03:39` (« income level —, the destination »), `fr/04:58` (« heure de départ —,
six pour la géométrie »).

**B. La glose en cadratin, devenue tic de chapitre.** Un concept posé, puis une énumération
explicative accrochée par cadratin. Onze des trente et un paragraphes de prose de `fr/03` sont
bâtis ainsi (l. 23, 25, 27, 31, 35, 39, 41, 49, 51, 53, 55) ; `en/03` reproduit la série ligne pour
ligne ; `fr/04` la reprend quatorze fois (l. 24, 30, 36, 42, 50, 58, 76, 78, 89, 91, 93, 97, 99, 101).
`fr/03:53` en porte deux dans la même phrase.

**C. Le gras qui porte l'argument à la place de la phrase.** `fr/06:62` met en gras la copule :
« L'écart entre les deux lectures **est** une mesure ». `fr/08:16-22` met en gras quatre résultats
chiffrés (64 %, 59 %, 31 %, +2,2 pt) dans un paragraphe de onze lignes. `fr/00:19` et `en/00:19`
mettent en gras cinq emplacements `[xx]` chacun, gras qui survivra au remplacement par les vraies
valeurs si rien n'est décidé. `fr/06` ajoute sept fragments de proposition en gras (l. 33, 45, 66,
90, 98, 105, 118).

**D. Les amorces en gras en série.** `**Matière disponible.**` ouvre trois paragraphes de `fr/06`
(l. 55, 116, 130), plus une variante sans point (l. 141). Deux séries `**Règle N — …**` : trois dans
`fr/04` (l. 58, 66, 68), quatre dans `fr/05` (l. 146, 155, 162, 169). L'amorce en gras est une
convention admise en ACM ; c'est sa répétition sous le même libellé qui simule la clarté au lieu
de la produire.

**E. Lexique : rien.** Treize occurrences relevées, treize faux positifs vérifiés un par un.
`robust` et `robustness` (5, dans `en/00` et `en/01`) sont le vocabulaire de certification de
SILICA, cité comme tel ; `paysage de perte` (`fr/99:21`) est *loss landscape* ; `paysage tabulaire`
(`fr/05:275`) est dans une citation en bloc ; `ni … ni … ni` (`fr/02:32`, `fr/05:84`, `fr/99:27`)
est une énumération française ordinaire ; `riche` et `souligne` sont employés au sens propre.
Aucune transition stéréotypée, aucune ouverture en « En résumé » ou « In summary », aucun gabarit
concessif « bien que X, Y offre », aucun triptyque « tout d'abord / ensuite / enfin ».

**F. Puces : rien.** Le taux le plus élevé mesuré, 13,9 % pour `en/03`, venait entièrement de la
section « Tickets attached to this chapter », que le filtre de la passe ne reconnaissait pas, son
titre étant en anglais. Hors listes de tickets, `en/03` ne contient aucune puce et `fr/06` en
contient quatre, toutes des critères de mesure énumérés.

Trace de la passe : `docs/traces/2026-09-15_14-53_ticket083_signature_ia_corpus/` (hors git).

## Ce que le ticket livre

### Lot A — le détecteur et sa cible make

- `scripts/paper/detecter_artefacts_ia.py`, calqué sur `scripts/paper/verifier_parite.py` :
  docstring FR, `argparse`, durée affichée, lignes `SUCCÈS` / `ERREUR`, code de sortie 0 ou 1.
- **Extraction de la prose d'abord.** Le détecteur ne mesure rien avant d'avoir retiré : blocs de
  code, tableaux (lignes `|`), schémas ASCII, commentaires HTML, cibles de liens `](…)`, code
  inline, lignes d'en-tête éditorial (`^\*\*[A-ZÉ][^*:]{2,45} ?:\*\*`) et sections de queue de
  tickets. **Le filtre de queue reconnaît les titres FR et EN** : la passe du 15/09 a raté
  « Tickets attached to this chapter » et a fabriqué un faux positif de 13,9 % de puces.
- **Seuils calés sur le corpus, pas sur une constante arbitraire** : la référence est la densité de
  `fr/01`, `fr/02`, `en/01` et `en/02`. Proposition à l'implémentation, 5 cadratins et 10 gras pour
  1000 mots de prose, avec la valeur et sa justification en tête de fichier.
- **La famille lexicale sort en informatif et ne fait pas échouer le détecteur.** Elle a produit
  13 constats et 0 correction ; la faire échouer imposerait une liste d'exemptions (`robust`,
  `exploratory`, `transferable`, `paysage de perte`) qui vieillirait mal. La famille puces est
  retirée.
- Familles qui font échouer : typographie (densités), structure (ouverture de conclusion,
  triptyque, symétrie mécanique de sections consécutives), lissage (gabarits concessifs,
  « non seulement … mais aussi »).
- Sortie : les constats en `fichier:ligne`, le tableau de densités, puis le verdict.
  `--fichier` pour un seul fichier, sinon `fr/` et `en/` en entier. `overleaf/` et `relecture/`
  sont hors périmètre (le `.tex` demande un autre filtrage ; les notes de relecture n'engagent
  personne).
- Cible `make paper-style [F=…]`, à côté de `paper-parite`.

### Lot B — le contrôle après écriture

- Seconde entrée `PostToolUse` sous le matcher `Write|Edit` de `.claude/settings.json`, à côté de
  la checklist existante. Le hook lit `tool_input.file_path`, ne fait rien hors d'un `.md` de
  `docs/paper/article/`, et sinon lance le détecteur sur ce seul fichier.
- **Fail-open par construction** : `|| true`, `timeout: 15`, jamais de code 2. Un détecteur cassé
  ne bloque jamais une écriture.
- Le hook ne voit pas les écritures passées par `Bash` (`sed -i`, heredoc, `>`), exactement la
  brèche que `article-verrou` documente déjà. D'où la règle écrite : `make paper-style F=…` est
  lancé quel que soit le chemin d'écriture, et les constats sont rendus dans la réponse.
- Section « Style » dans la skill `article-verrou` plutôt qu'une skill de plus : elle est déjà
  chargée avant toute écriture sur l'article, le coût en contexte est nul. Elle porte les quatre
  familles comme consignes de rédaction, pas seulement de détection. Renvoi de trois lignes dans
  `.claude/agents/article-writer.md`, qui écrit sans passer par la skill.
- Le détecteur est un signal, pas une autorité : un passage signalé peut être conservé, mais la
  décision est énoncée.

### Lot C — la reprise du corpus (sous verrou)

Par ordre de priorité, chaque écriture soumise à accord préalable.

- **C1, les trois défauts de A.** Sans débat : fermer l'incise par une virgule seule ou passer aux
  parenthèses. `fr/03:39`, `en/03:39`, `fr/04:58`.
- **C2, les chapitres 3 FR et EN.** Ne garder le cadratin que là où l'incise coupe réellement la
  phrase ; passer le reste en deux-points, en parenthèses ou en phrase suivante. Cible, 4 à 5 pour
  1000 mots, soit 8 cadratins au lieu de 23. Les deux versions se corrigent ensemble, la parité
  étant vérifiée par `make paper-parite`.
- **C3, le chapitre 4.** Même traitement sur les quatorze gloses, et arbitrage du gras à 27,8 pour
  1000 mots.
- **C4, le gras des chapitres 6 et 8.** Réécrire `fr/06:62` plutôt que dégraisser la copule.
  Dégraisser les quatre chiffres de `fr/08:16-22`. Trancher le gras des cinq `[xx]` des deux
  abstracts maintenant : l'abstract FR passe de 21,4 à 8,0 pour 1000 mots.
- **C5, les amorces répétées.** Fusionner ou tourner en phrase les trois `**Matière disponible.**`
  de `fr/06`. Les séries `**Règle N —**` de `fr/04` et `fr/05` sont proposées à la conservation :
  elles numérotent des règles réellement distinctes et le lecteur y revient.

## Tests attendus

- Le détecteur sort en 0 sur `fr/01`, `fr/02`, `en/01` et `en/02` sans exemption d'aucune sorte.
- Il sort en 1 sur `fr/03`, `fr/04` et `fr/08` dans leur état du 2026-09-15, et nomme les lignes
  listées au paragraphe « Le fait ».
- Un chapitre dont la seule densité de gras vient des lignes d'en-tête éditorial sort en 0 : le
  filtre de prose fait son travail (`fr/02` porte 15 gras de métadonnées et 0 en prose).
- La section de queue de tickets est exclue dans les deux langues : `en/03` ne compte aucune puce.
- Le hook, détecteur absent ou en erreur, laisse l'écriture aboutir et n'écrit rien de bloquant.
- Après le lot C, `make paper-parite` reste vert sur les chapitres 3.

## Critères d'acceptation

- [ ] `make paper-style` existe, documenté dans `docs/paper/README.md` à côté de `paper-parite`.
- [ ] Les seuils sont justifiés en tête de script par les densités mesurées de `fr/01` et `fr/02`,
      et non posés arbitrairement.
- [ ] Le hook `PostToolUse` est fail-open et le vérifie par un test : détecteur renommé, l'écriture
      aboutit.
- [ ] `article-verrou` porte la section « Style » et les quatre familles.
- [ ] C1 livré : aucune occurrence de `—,` dans `fr/` et `en/`.
- [ ] C2 à C5 livrés ou explicitement reportés, chacun avec l'accord qui l'a autorisé.
- [ ] Après C2 et C3, `fr/03`, `en/03` et `fr/04` passent sous le seuil de cadratins sans que le
      détecteur ait été desserré pour eux.
- [ ] Entrée au changelog à la livraison.

## Liens

- [Ticket 080](ticket_080_idee_directrice_du_chapitre_6_et_impact_sur_le_papier.md) — idée directrice du chapitre 6 ; le lot C4 touche des passages que le 080 réécrira, à séquencer.
- [Ticket 074](ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md) — bascule anglaise ; `en/` est la version maîtresse à terme, le détecteur doit y tourner d'emblée.
- `.claude/skills/article-verrou/SKILL.md` — procédure d'accord pour le lot C.
- `scripts/paper/verifier_parite.py` — modèle de forme pour le détecteur.
