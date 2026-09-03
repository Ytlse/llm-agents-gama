# Report marche → transports collectifs : dix prompts, un sous-jeu, dix pages

Mesure de l'effet d'un ajout de prompt sur les décisions où le modèle a **retenu un
transport collectif alors que la marche lui était proposée**. Le run n'est pas rejoué :
seules ces décisions-là sont redemandées au modèle, sur le texte exact qu'elles avaient
reçu, puis réinjectées dans le run pour recalculer la page du volet 1.

**Régénérer :**

```bash
make alt-prompt-subset          # sélection seule, aucun appel LLM
make alt-prompt-replay DRY_RUN=1  # plan d'appels chiffré
make alt-prompt-replay          # ~620 appels Gemini free tier, ~25 min
make alt-prompt-pages           # les dix pages, aucun appel LLM
make alt-prompt-figure VARIANT=1  # la figure PNG d'un bras, aucun appel LLM
make alt-prompt-figure VARIANT=1 SCOPE=both  # …avec l'étage du sous-jeu
```

Sorties : `docs/synthesis/detail_simulation_26_08_alternative<1..10>.html` (une page par
variante, de la même forme que
[`detail_simulation.html`](score-synthesis.md)) et
`docs/traces/2026-08-26_report_marche_tc/` (une trace JSON par bras, plus `subset.json`).
Les traces sont la source des pages : `make alt-prompt-pages` ne rappelle jamais le
modèle, et un bras déjà payé est repris sans appel par `make alt-prompt-replay`.

---

## 1. Le constat de départ

Sur le run épinglé (`experiments/archive/2026-08-24_17_34`, jour simulé 2026-03-16,
2 911 décisions après les trois coupes du périmètre commun), les parts modales produites
s'écartent de l'enquête EMC² 2023 dans deux directions liées : **marche 11,9 % contre
26,8 %** attendus, **transports collectifs 17,2 % contre 12,4 %**. Le déficit de marche et
l'excédent de collectif ne sont pas deux défauts indépendants — le second absorbe une
partie du premier.

## 2. Le sous-jeu : trois conditions, aucune approximation

Sont retenues les décisions qui remplissent les trois conditions suivantes :

| Condition | Effectif |
|---|---:|
| Décisions du run après les trois coupes du périmètre commun | 2 911 |
| … dont le **mode tiré** est un transport collectif **et** la marche figurait dans « Modes proposés au LLM » | **497** |
| … dont le lot d'origine est retrouvé dans `llm_exchanges.jsonl`, sans ambiguïté | **495** |

Les 2 décisions perdues sont **ambiguës**, pas absentes : deux blocs persona du même agent
tombent dans la fenêtre d'appariement avec le même jeu d'options. Elles sont écartées et
comptées plutôt que rattachées au petit bonheur — un rattachement faux rejouerait le
prompt d'un autre trajet sous l'étiquette de celui-ci.

### L'appariement, et le piège qu'il contient

`moves.csv` et `llm_exchanges.jsonl` n'ont **aucune clé commune**. La jointure se fait sur
(`ID Personne`, `Heure de calcul`) avec une tolérance de 5 secondes — le journal horodate
la fin du lot, la ligne de trajet sa propre écriture — puis elle est **vérifiée** en
comparant le jeu d'options des deux côtés.

⚠ Deux clés naturelles ne marchent pas, et l'une échoue silencieusement :

- **L'heure de départ** : `moves.csv` l'écrit en UTC, le prompt la rend en heure locale
  (décalage d'une heure en mars). Pire, pour un trajet en transport collectif les deux
  divergent au-delà du décalage — la ligne porte l'heure de départ effective, le prompt
  l'heure planifiée. Sur les 497 décisions du sous-jeu, cette clé n'en apparie que 24.
- **Le couple (personne, activité) sans le jour simulé** : le journal déborde du jour
  retenu (bootstrap, horizon glissant de planification) et le même couple y réapparaît le
  lendemain. Indexer sans couper au premier jour garde la ligne du **jour 2**, dont
  l'« Heure de calcul » appartient à un autre lot : 211 décisions du sous-jeu passaient
  alors pour « sans lot retrouvé » alors que leur lot existe. `latest_attempts` ne les
  sépare pas — sa clé porte le jour, c'est précisément ce qui distingue une reprise à
  chaud d'une répétition.

## 3. Les dix variantes

Elles ne sortent pas d'une intuition mais du **dépouillement des 494 justifications** que
le modèle a lui-même écrites sur ces décisions (colonne `Raisonnement`). Cinq arguments
reviennent, chacun visé par une ou plusieurs variantes :

| Argument invoqué par le modèle | occur. | Variantes |
|---|---:|---|
| « le bus / le métro est plus rapide » | 135 | V1, V2, V6, V10 |
| « la marche est trop longue » | 232 | V3, V4, V6 |
| « il/elle est abonné·e au réseau » | 88 | V5 |
| « la marche fatigue, vu l'âge » | 39 | V7, V8 |
| « il fait froid » | 10 | V9 |
| attente et correspondances comptées | 27 | V2, V10 (à contrario) |

Chaque variante est un bloc **ajouté** au prompt système de production, inséré comme
section « 4) » **après les critères d'évaluation et avant les instructions de sortie** :
placé après le schéma JSON, il se lirait comme une consigne de format. Rien n'est retiré —
le prompt du run est contenu mot pour mot dans celui de la variante, et chaque page
l'affiche en entier avec l'ajout surligné. Le point d'insertion est vérifié : s'il manque,
le rejeu **refuse** de tourner plutôt que de concaténer en fin de prompt.

Aucune variante ne dit « choisis la marche ». Une consigne de ce genre produirait une part
de marche réglable à volonté — un thermostat, pas une correction. Chaque variante fournit
un **élément de calcul** que le modèle ignorait (l'attente, l'aléa du réseau, la marche de
rabattement déjà contenue dans l'option, le coût porte-à-porte) et le laisse conclure.

Le texte complet des dix vit dans
[`scripts/synthesis/alt_prompt_variants.py`](../../scripts/synthesis/alt_prompt_variants.py),
en données et non en dur dans le code du rejeu : en ajouter une onzième ne demande pas de
toucher au moteur.

## 4. Le régime de mesure

| | |
|---|---|
| Modèle | `gemini-3.5-flash-lite`, température 0 |
| Fournisseurs | `google2_35` et `google_gemini35` — **deux clés, un seul modèle** |
| Lots | 8 personas (même valeur que `common_set_eval` : à 15, le modèle rend un JSON valide mais amputé de personas) |
| Appels | 62 lots × 10 bras = 620 |
| Débit | 15 req/min et par clé, les deux clés en parallèle |

Les deux clés ne sont pas un changement de modèle : le quota gratuit vaut 500 requêtes par
jour **par projet et par modèle**, et une seule clé plafonnerait sous les 620 appels
demandés. Même nom de modèle, même version, même température des deux côtés.

### Le quota journalier borne la campagne, et il faut le prévoir

620 appels pour 1 000 de quota théorique : la marge est mince, et elle a été franchie dès
la première exécution — la clé 1 était déjà entamée par d'autres mesures du jour. Deux
conséquences portées dans le code, l'une et l'autre apprises de cet incident :

- **Un quota journalier ne se retente pas.** `classify_quota_error` distingue un 429
  « par minute » d'un 429 « par jour » ; le second abandonne le bras sur-le-champ. Sans
  cette distinction, la boucle de retry du moteur dormait jusqu'à 5 minutes par tentative,
  5 fois — une demi-heure par lot, pour rien. `max_retry_wait` est ramené à 30 s pour la
  même raison.
- **Les bras ne sont pas affectés aux clés à l'avance.** Une file commune, un fil par clé :
  la clé qui s'épuise sort de la rotation et rend ses bras à la file. Avec l'affectation
  statique du premier dispositif, l'épuisement de la clé 1 condamnait les cinq bras qui
  lui étaient attribués **alors que la clé 2 avait encore du quota**.
- **Un bras interrompu ne laisse aucune trace.** Une trace partielle serait relue plus tard
  comme une mesure, et la reprise la servirait sans jamais la compléter.

Relancer la même commande après le reset (minuit heure du Pacifique) reprend là où la
campagne s'est arrêtée : les bras déjà payés sont servis depuis leur trace, sans appel.

## 5. Ce que ces pages ne permettent pas de conclure

Quatre réserves, écrites en tête de chaque page parce qu'elles en bornent la lecture.

**Aucun bras témoin** (décision du 2026-08-26). Le run a tourné sur quatre fournisseurs —
`google2` (1 687 décisions), `google2_35` (1 560), `groq_openai_120` (87),
`groq_qwen_qwen3_6_27b` (35) — quand les variantes tournent sur un seul modèle. L'écart
publié mélange donc l'effet du prompt et celui du changement de modèle. Le séparer
demanderait un onzième bras rejouant le prompt **inchangé** dans ces mêmes conditions,
soit +62 appels : c'est le dispositif que `prompt_calibration/ab_meteo.py` applique déjà
sous le nom de « plancher de bruit », et il reste à payer ici.

**Le sous-jeu est sélectionné sur un tirage.** Le critère est le mode *tiré*, pas la masse.
Sur les 495 décisions retenues, la masse de transport collectif valait déjà 75,4 % en
moyenne — mais 97 d'entre elles avaient la **voiture** en tête de distribution et 21 la
marche : c'est le tirage qui a sorti le collectif. Sélectionner sur un aléa puis remplacer
la masse introduit un effet de sélection qui gonfle l'écart apparent. Le critère
alternatif — masse TC > masse marche — retiendrait 883 décisions et n'a pas cet effet.

**Neuf leviers sur dix sont des leviers de NIVEAU, pas de PENTE.** Le défaut chiffré du
modèle est une élasticité à la distance quasi nulle : la part voiture produite est plate
(42,7 → 49,1 %) quand la réelle va de 18 à 77 %
(cf. [`prompt_calibration/TODO.md`](../../prompt_calibration/TODO.md)). Un ajout qui
déplace la masse à toutes les distances peut améliorer l'agrégat en dégradant les tranches
longues — le « gaming de la distribution » mesuré sur la campagne `ref1`. Seule V4 est
explicitement conditionnée à la distance. C'est le **détail par tranche de distance** de
chaque page, et non ses tuiles, qui départage.

**La simulation n'est pas rejouée.** Le jeu d'itinéraires OTP et la chaîne de véhicules du
jour sont gelés dans le texte. On mesure l'effet du prompt sur la **décision**, pas ce que
la ville aurait fait ensuite d'un agent qui marche : autres horaires d'arrivée, autre
chaîne de véhicules, autre état de mémoire.

## 6. Comment la page est recomposée

Les 495 lignes rejouées voient leur **masse de probabilité** remplacée ; les
2 416 autres décisions du run restent intactes. Le mode **tiré** des lignes remplacées est
re-tiré dans la nouvelle distribution, avec une graine dérivée de (variante, clé de
ligne) : sans cela, la lecture « tiré » de la page continuerait d'afficher le tirage de
l'ancienne masse et les deux lectures de la même page se contrediraient.

Le sous-chapitre « Détail par sous-catégorie » est produit par le **même**
`render._dimension_blocks()` que `detail_simulation.html`, et le score par le même
`frames.Scorer` — donc par la loss importée de
`prompt_calibration/calibration/metrics.py`. Aucun chiffre n'est recopié d'une page à
l'autre, et une page d'alternative ne peut pas diverger de la page dont elle dérive.

**Vérification faite** avant tout appel : en substituant aux 495 décisions leur **propre**
masse d'origine (trace identité), la page reproduit le composite du run au centième
(18,23) et la part de marche du sous-jeu à la décimale (6,7 %). Le chemin de recomposition
n'introduit donc aucun écart de son cru.

## 7. La figure : deux camemberts, un périmètre nommé

`make alt-prompt-figure VARIANT=<n>` écrit
`docs/synthesis/figures/prompt_parts_modales_v<n>.png` — la lecture visuelle de ce que
l'ajout déplace : deux anneaux côte à côte, le run sous son prompt de production puis le
même run dont 495 décisions ont été rejouées.

**Le périmètre est un choix, et il change tout.** `SCOPE=global` (le défaut) dessine les
parts modales de la **population entière** : c'est le chiffre qui se compare à EMC² 2023,
et l'ajout n'y déplace que 1,7 point au maximum sur V1. `SCOPE=subset` dessine les
**495 décisions rejouées** seules, là où l'ajout s'applique : le transport collectif y perd
9,9 points. `SCOPE=both` empile les deux étages. Les trois disent la même mesure — l'effet
propre de l'ajout est dilué d'un facteur six dans l'agrégat, parce qu'il ne touche que
495 décisions sur 2 911.

La figure ne porte pas de titre — elle est faite pour un document qui pose lui-même ce
qu'elle montre — mais elle nomme toujours **deux choses** : la variante, en tête, sans quoi
deux figures de la campagne seraient indiscernables ; et le périmètre, en marge de chaque
étage, avec son effectif. Une phrase de lecture dit en pied **ce que la version choisie
cache** : sans elle, la figure globale se lirait « le prompt ne fait rien » et celle du
sous-jeu « le prompt refait la ville ». Un camembert de sous-jeu pris pour une part modale
de ville est un contresens, pas une simplification.

Les chiffres sont **lus dans la page** de la variante, colonnes comprises — y compris les
Δ, qui ne sont pas recalculés depuis les valeurs arrondies : 6,7 → 8,3 donnerait +1,6 là où
la page publie +1,7, et deux documents du même dossier se contrediraient d'un dixième. Une
page régénérée se répercute donc dans la figure d'une seule commande, et une figure ne peut
pas diverger de la page dont elle dérive. Les réserves du § 5 sont portées en pied de figure.

Un bras non rejoué n'est pas dessiné : le script s'arrête en nommant la commande qui
produirait la page manquante, plutôt que de rendre un PNG vide.

## Voir aussi

- [`score-synthesis.md`](score-synthesis.md) — la page dont ces alternatives dérivent
- [`prompt_calibration.md`](prompt_calibration.md) — le moteur dont viennent la loss, les
  records et les adaptateurs LLM
- [`protocole-parametre-exogene.md`](protocole-parametre-exogene.md) — le protocole d'A/B
  apparié dont ce dispositif emprunte la forme sans en payer le bras témoin
