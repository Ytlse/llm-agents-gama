# Ticket 049 — L'itinéraire mixte n'existe pas : publier la limite, et dire dans quel sens elle penche

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-12, **rien n'est écrit**.
>
> **Ce ticket rédige une limite, il ne corrige rien.** Aucun code, aucune ressource, aucun
> cache, aucun run. Il porte le **lot 5** du
> [ticket 022](ticket_022_rabattement_mode_principal.md), clos le même jour : le lot 1 (la
> hiérarchie des modes) est livré, les lots 2 à 4 (table d'atteignabilité, trait
> `rabattement_plausible`, bande de rendu) sont **classés sans suite**, mesure à l'appui — et
> c'est ce classement qui devient la seconde moitié de ce qu'il faut écrire.
>
> **Touche l'article** : l'écriture dans `docs/paper/article/` passe par la skill
> `article-verrou`, diff présenté et accord explicite. Ce ticket ne s'en dispense pas.

## Le fait

OTP est interrogé **mode par mode**. Le jeu d'options présenté à l'agent ne contient donc
aucun itinéraire mixte : ni « voiture jusqu'au parking-relais puis métro », ni « vélo jusqu'à la
gare puis TER ». L'enquête EMC², elle, en compte : un déplacement qui mêle plusieurs modes reçoit
un mode principal, et la hiérarchie nationale le range presque toujours en transports collectifs
(760 des 770 déplacements voiture + TC, et **les 58** déplacements vélo + TC).

Une part de la cible « transports collectifs » est donc **hors d'atteinte par construction** : la
simulation ne peut pas produire les déplacements que la cible compte en TC *parce qu'ils sont
mixtes*.

## L'amplitude, par strate

Mesurée sur les microdonnées EMC² 2023, pondérée `COEP`, sur les déplacements internes au
périmètre. Globalement 1,41 point de part modale — **et ce chiffre global masque l'essentiel** :

| Couronne de résidence | Cible TC | dont rabattement | TC atteignable | Part de la cible perdue |
|---|---:|---:|---:|---:|
| Toulouse | 21 % | 0,70 pt | 20,3 % | 3 % |
| 1ʳᵉ couronne | 8 % | 1,73 pt | 6,3 % | **22 %** |
| 2ᵉ couronne | 7 % | 2,19 pt | 4,8 % | **31 %** |
| 3ᵉ couronne | 6 % | 1,67 pt | 4,3 % | **28 %** |

| Tranche de distance | Cible TC | dont rabattement | TC atteignable | Part de la cible perdue |
|---|---:|---:|---:|---:|
| 0-1 km | 3 % | 0,00 pt | 3,0 % | 0 % |
| 1-2 km | 9 % | 0,05 pt | 9,0 % | 1 % |
| 2-5 km | 15 % | 0,46 pt | 14,5 % | 3 % |
| 5-10 km | 22 % | 2,83 pt | 19,2 % | 13 % |
| 10-20 km | 16 % | 6,25 pt | 9,8 % | **39 %** |
| 20-50 km | 13 % | 7,70 pt | 5,3 % | **59 %** |
| plus de 50 km | 12 % | 7,72 pt | 4,3 % | **64 %** |

Profil des déplacements concernés : médiane **11,1 km** contre 1,9 km pour l'ensemble ; motifs
dominés par le retour au domicile (42 %) et le travail fixe (14 %) ; **3,1 %** des personnes
mobiles en font au moins un la veille.

## Le sens de la limite, mesuré le 2026-09-12

C'est la moitié neuve, et elle renverse la lecture que le ticket 022 en faisait.

Le 022 supposait que cette limite **pénalise** le modèle : jugé contre une cible qu'il ne peut
pas atteindre, il en serait « corrigé » d'autant. Son critère d'acceptation l'écrivait noir sur
blanc — « ⚠ le score va s'améliorer, et il faut le justifier ligne par ligne ». La prémisse a été
vérifiée plutôt que supposée, sur **17 exécutions archivées** (≈ 50 000 déplacements, trace
[`2026-09-12_10-10_sens_limite_rabattement`](../traces/2026-09-12_10-10_sens_limite_rabattement/README.md)).

**La simulation sur-produit les transports collectifs sur les longues distances**, précisément là
où la cible était la plus inatteignable :

| Tranche | Cible EMC² | gemini-38-f | gemini-31-fl | gemini-35-fl | MNL | RF |
|---|---:|---:|---:|---:|---:|---:|
| 10-20 km | 16 % | 28 % | 35 % | 27 % | 22 % | 17 % |
| 20-50 km | 13 % | **36 %** | 33 % | 27 % | 17 % | 13 % |
| plus de 50 km | 12 % | **47 %** | 42 % | 43 % | 46 % | 37 % |

L'intervalle `[cible − rabattement ; cible]` ne s'étend que **vers le bas**. Quand la valeur
simulée est déjà au-dessus de la borne haute, l'écart à l'intervalle est identique à l'écart au
point : effet **nul**. Gain de la neutralisation, en points de % moyennés sur les déplacements du
bras :

| Bras | Gain |
|---|---:|
| `durmin` (plus rapide), `majvoiture` (tout voiture) | **+2,17 à +2,19 pt** |
| Oracles statistiques (`klr`, `rf`, `lgbm`, `mnl`) | 0,00 à 0,17 pt |
| **Les trois bras LLM** | **0,000 pt** |

**La neutralisation n'aurait profité qu'aux deux baselines dégénérés** — elle aurait rapproché le
modèle sous test de ses hommes de paille. C'est la raison pour laquelle les lots 2 à 4 du ticket
022 sont classés, et cette raison fait partie de ce qu'il faut publier : une limite d'instrument
qui ne mord pas dans le sens attendu se dit, elle ne se tait pas.

⚠ Le composite ne compare pas des parts par tranche mais des **profils EMD** le long de l'axe
(`emd_ordinal_dim_measured`). Dans cette lecture le verdict est encore plus net : retirer le
rabattement de la cible rend le profil TC de référence *plus court en distance*, donc **plus
éloigné** d'une simulation déjà trop ferroviaire. Ni gain, ni neutralité : une dégradation.

## Ce qu'il faut faire

1. **Écrire la limite dans l'article**, chapitre
   [`08_limits_and_hybrid.md`](../paper/article/fr/08_limits_and_hybrid.md) (et sa version `en/`) :
   le jeu d'options ne contient aucun itinéraire mixte, l'amplitude par strate va jusqu'à 64 % de
   la cible TC, et la mesure du 2026-09-12 montre que cette limite **ne flatte pas le modèle
   aujourd'hui** — elle flatterait les baselines dégénérés si on la neutralisait. Deux paragraphes,
   pas un chapitre. **Passe par le verrou de l'article.**
2. **Consigner le classement des lots 2 à 4** dans
   [`docs/arch/perimetre-population.md`](../arch/perimetre-population.md), § A7, qui annonce
   aujourd'hui le trait `rabattement_plausible` et la neutralisation comme à venir. Remplacer
   l'annonce par le constat et son chiffre.
3. **Dire à quelle occasion re-mesurer.** Le résultat est daté, pas définitif : il dépend de la
   distribution des tranches de distance du corpus. Le script de la trace se rejoue tel quel.
4. **Ne pas transporter le raisonnement au ticket 021.** Là-bas la correction dégrade le score et
   c'est le critère de réussite ; ici il n'y a rien à corriger. Les deux tickets sortent du même
   audit, c'est le seul lien.

## Ce qui rouvrirait le dossier

- **Le ticket 025 / le périmètre à 453 communes.** Des domiciles de 3ᵉ couronne à 60-100 km
  déplacent la masse vers les tranches longues ; le signe de l'écart peut basculer. Re-mesurer
  **avant** de conclure, jamais par analogie.
- **Un changement d'offre.** Le plafond `max_trip_candidates = 6`, le groupe ferroviaire séparé ou
  une entrée de nouvelles lignes dans le graphe OTP changent la part TC offerte, donc la part TC
  choisie.
- **La production d'itinéraires mixtes.** Elle lèverait la limite au lieu de la publier — et c'est
  un autre ticket, coûteux (parkings-relais localisés, nouveau type d'option, cache de plans **et**
  cache de décisions invalidés).

## Hors périmètre

- **Produire des itinéraires de rabattement** : le vrai remède, ticket distinct (cf. ci-dessus).
- **La sur-production de TC sur les longues distances** (36 % contre 13 % sur 20-50 km). C'est un
  problème en soi, plus gros que celui-ci, et il mérite son propre ticket : plafond d'options,
  groupe ferroviaire, offre OTP mode par mode.
- **La chaîne de véhicule d'un rabattement** (verrou de retour du ticket 008, positions du
  ticket 014).
- **Les lots 2 à 4 du ticket 022** : classés, pas reportés. Les rouvrir demande la mesure du § « Ce
  qui rouvrirait le dossier », pas une décision de rédaction.

## Critères d'acceptation

- [ ] Le chapitre 8 énonce la limite **avec son amplitude par strate** — pas seulement le chiffre
      global de 1,41 pt, qui est trompeusement rassurant.
- [ ] Il dit aussi **dans quel sens elle penche**, chiffres à l'appui. Une limite publiée sans son
      signe laisse croire au lecteur qu'elle pénalise le modèle.
- [ ] Le diff de l'article a été présenté et accepté (skill `article-verrou`), fichiers `fr/` et
      `en/` annoncés ensemble.
- [ ] `docs/arch/perimetre-population.md` § A7 ne promet plus un trait `rabattement_plausible` qui
      n'existera pas.
- [ ] Aucun fichier de code, de ressource gelée ou de configuration n'est modifié.
      `cerema_values.yaml` en particulier reste intact — une borne d'atteignabilité décrit notre
      instrument, pas l'enquête.

## Sources

- [ticket 022](ticket_022_rabattement_mode_principal.md) — le lot 5 dont ce ticket est la suite,
  et les lots 2 à 4 qu'il classe.
- [ticket 020](ticket_020_perimetre_population_cerema.md), axe A7 — le constat d'origine.
- [`docs/traces/2026-09-12_10-10_sens_limite_rabattement/`](../traces/2026-09-12_10-10_sens_limite_rabattement/README.md)
  — la mesure du sens, et son script de rejeu.
- [`docs/traces/2026-09-04_10-17_hierarchie_modes_enquete/`](../traces/2026-09-04_10-17_hierarchie_modes_enquete/README.md)
  — la hiérarchie livrée (lot 1).
- Microdonnées EMC² Toulouse 2023, ProGEDO/ADISP `lil-1750` ; rapport AUAT/CEREMA, annexe p. 53.
