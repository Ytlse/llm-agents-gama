# Le bulletin météo seul, à pleine masse — ticket 023bis

Mesure du **2026-08-26** (campagne montée le 25/08, exécutée le 26 après renouvellement du
quota). Substrat `v9`, tiré du run de référence `2026-08-24_17_34`. **Trois bras**, mêmes
personas, même prompt `expert_chaine`, modèle d'éval épinglé `gemini-3.5-flash-lite` (T = 0),
clé `google2_35`. 437 appels LLM.

**Verdict : aucun effet distinguable.** Le bulletin enrichi — la seule des trois corrections
du ticket 023 réellement livrée en production — déplace le composite de **+0,19** contre un
plancher de bruit de **−1,07** : cinq fois et demie plus petit que ce qu'un simple re-tirage
produit tout seul. Il reste en production comme un choix de CONTENU, et cette mesure ne le
soutient pas davantage qu'elle ne le condamne.

**Et un second résultat, sur l'instrument :** à pleine masse, le plancher de bruit se resserre
de moitié. C'est la première fois qu'une mesure de cette campagne dispose d'un instrument
assez fin pour que son non-résultat veuille dire quelque chose.

## Pourquoi cette mesure existe, alors que le 023 avait déjà conclu

L'A/B du ticket 023 mesurait le bulletin **par-dessus la fenêtre d'enquête** (`v10b − v10`).
Or la production ne joue pas la fenêtre : elle tire sur l'année entière. La combinaison
réellement livrée — **année + bulletin** — n'avait donc jamais été contrastée directement.
`v9b` la mesure : tirage de `v9` reproduit à l'identique, seule la forme de la phrase change.

## Les trois bras

| Jeu | Tirage | Phrase météo | Rôle |
|---|---|---|---|
| `v9` | année (365 j), `meteo_v2` | d'origine | la référence — le substrat du run à 18,23 |
| `v9b` | année (365 j), `meteo_v2` — **identique à `v9`** | **enrichie** | **le traitement** — la production telle que livrée |
| `v9n` | année (365 j), `meteo_v3n` | d'origine | **le plancher de bruit** — re-tirage seul |

Le tirage de `v9b` est vérifié **strictement** : les 2 874 phrases du jeu, régénérées avec la
graine `meteo_v2` puis dépouillées de leur cadre, sont identiques aux 2 874 phrases de `v9`
— zéro écart, zéro enregistrement non tirable. `v9b − v9` mesure donc la FORME de la phrase
et rien d'autre : ni jour tiré, ni température, ni agenda.

## Le jeu `all` — et pourquoi la masse était le vrai enjeu

`all` = `train` ∪ `val` de `v9` : **1 810 décisions, 613 personas** (2 726 lignes de décision
après ventilation en masse de probabilité). `test` en est exclu — regard unique du protocole,
§8 ; `screen` n'y figure pas en propre puisque `screen ⊂ train`. C'est le plus grand jeu de
lecture disponible sans jouer un nouveau run.

Ce choix vient du résultat n° 7 de la campagne 023 : `screen` (121 personas) avait fabriqué
deux signaux que `val` (182 personas) n'a pas confirmés, parce qu'un plancher étroit fabrique
des signaux. La réponse n'était pas de changer de jeu, mais d'en prendre un plus gros.

## Le résultat

Composite, ↓ meilleur :

| | `v9` | `v9n` | `v9b` |
|---|---:|---:|---:|
| `all` — 613 personas | 21,73 | 20,66 | **21,92** |

Et les deux contrastes :

| Contraste | `all` | |
|---|---:|---|
| `v9n − v9` | **−1,07** | le témoin nul — **le plancher de bruit** |
| `v9b − v9` | **+0,19** | le bulletin seul, tel que livré — **le traitement** |

## Ce que ces chiffres établissent

**1. Le bulletin n'a pas d'effet mesurable, et c'est maintenant un vrai non-résultat.** +0,19
contre un plancher de −1,07 : le traitement est **5,6 fois plus petit** que le bruit propre de
l'instrument. Sur `val`, le même bulletin donnait +1,72 contre un plancher de +1,98 — un
rapport de 0,87, soit un non-signal si serré qu'il ne prouvait rien. Ici la marge est franche.

**2. Le plancher de bruit se resserre avec la masse, comme il devait.** ±1,98 sur `val`
(516 records) → 1,07 sur `all` (1 810 records). Le rapport des amplitudes (1,85) est proche
de la racine du rapport des effectifs (√3,5 = 1,87) : le bruit décroît comme du bruit de
tirage. C'est la confirmation que l'instrument n'était pas cassé — il était trop petit.

**3. Le signe du témoin nul est arbitraire, et cette mesure le confirme une troisième fois.**
−0,34 sur `screen`, +1,98 sur `val`, −1,07 sur `all` : le même dispositif, qui ne change
AUCUNE distribution, produit les deux signes selon le jeu de lecture. Aucun raisonnement ne
doit reposer sur le signe d'un contraste plus petit que ce plancher.

**4. Le plancher utilisé ici MAJORE le bruit applicable, et c'est un choix prudent.** `v9n`
re-tire la météo (1 799 des 1 810 contextes changent) ; `v9b` ne re-tire rien (tirage
identique, seule la mise en forme bouge). Le bruit du témoin est donc d'une nature plus
agitée que celui auquel `v9b` est exposé. Conclure « sous le plancher » contre un plancher
majoré est plus solide, pas moins.

**5. Le niveau de `v9` sur `all` (21,73) n'est pas comparable au 18,23 du run.** Trois raisons,
et elles se cumulent : un seul modèle-juge à T0 contre toute la flotte du run (mesuré sur ce
run : 19,01 pour un modèle contre 18,23 pour l'agrégat, par compensation d'erreurs) ; un
sous-ensemble de 1 810 décisions sur 2 911 ; et l'exclusion des replis d'erreur, joués par la
simulation mais hors score. Un jeu gelé sacrifie le niveau pour gagner l'attribution.

## Ce que ces chiffres ne disent pas

- **Rien sur les chaînes de véhicule ni sur l'offre d'options.** Un jeu gelé mesure l'effet
  du narratif soumis au modèle, pas ce que la simulation aurait fait d'un agent trempé. Les
  trajets et les options sont gravés dans le jeu.
- **Rien sur la pluie**, et c'était écrit avant la mesure : son Δ change de signe selon le
  substrat. Cf. [`2026-08-25_premesure_meteo_v9`](../2026-08-25_premesure_meteo_v9/README.md).
- **Rien sur les transports collectifs**, à 24,3 % contre 12,0 attendus, ni sur la marche à
  11,3 % contre 26,0. Le bulletin ne touche pas ces défauts de fond : `v9b` laisse la marche
  à 11,2 % et pousse même les TC à 24,9 %.
- **Rien sur la résolution de 3 h**, qui reste la piste ouverte du ticket 023 — elle voyageait
  en paquet avec l'agenda annoté, et son rejet ne la condamne pas.

## La preuve d'exclusion

Jeton **nommé** `protocol_lock_35.json` (`PROTOCOL_LOCK_FILE`), pris à 09:02 et relâché à
10:37 UTC+2. Le jeton par défaut était détenu par une autre campagne — ticket 024, juge
`gemini-3.1-flash-lite` — dont le store confirme qu'elle n'a jamais appelé
`gemini-3.5-flash-lite` : autre clé, autre modèle, donc **autre compteur de quota**. Les deux
campagnes ne se disputaient rien, d'où deux jetons distincts plutôt qu'une attente inutile.

Pile locale entièrement arrêtée aux deux bouts (aucun service en marche — preuve plus directe
que deux compteurs inchangés). Campagne cloud vérifiée inactive, pas seulement déclarée :
`systemctl is-active calib-ga` → `inactive`, aucun timer armé.

## Le coût réel, et les deux fausses manœuvres

437 appels aboutis pour 363 annoncés. L'écart vient des **74 lots incomplets** : le modèle
rend moins de personas que le lot n'en portait, et les manquants sont re-tirés seuls. Ce
n'est pas une anomalie de cette mesure — c'est le régime normal du batching à 15 personas.

Deux dépenses en pure perte, à consigner :

- **~92 lots perdus le 25/08** : le bras `v9` est mort à 89/121 sur épuisement du quota. Une
  éval interrompue n'est **pas** mise en cache (le cache est par bras complet) : tout le bras
  est à re-payer. C'est le vrai coût d'un quota mal anticipé.
- **5 appels perdus le 26/08 au matin** : un appel de sonde a répondu HTTP 200, d'où la
  conclusion — fausse — que le seau était renouvelé. Il ne restait que ~5 requêtes du
  reliquat de la veille. ⚠ **Un 200 ne prouve pas qu'un quota journalier est renouvelé, il
  prouve qu'il reste au moins une requête.**

⚠ **21 alarmes** pendant la campagne : autant de vecteurs de probabilités à somme nulle,
repliés sur une distribution uniforme, sur 5 430 décisions évaluées (0,4 %). Même motif que
les 4 alarmes de la campagne 023. Trop peu pour déplacer un composite, assez pour être dit.

Une coupure réseau de 46 minutes (09:07 → 09:53) a interrompu les appels sans tuer le
processus : 2 timeouts à 240 s, puis reprise automatique au débit normal. Le coupe-circuit à
3 échecs consécutifs n'a pas eu à se déclencher.

## La porte de décision

**Le bulletin enrichi reste en production, et cette mesure ne change pas ce statut.** Elle le
documente : ce qui était « pas de preuve qu'il dégrade » sur un instrument trop étroit devient
« aucun effet mesurable » sur un instrument dont le bruit est chiffré et deux fois plus fin.
Le choix reste un choix de contenu — l'information qu'il porte (amplitude, soleil, créneaux
pluvieux) est factuellement absente du prompt sans lui — et il est assumé comme tel.

**Ce que la mesure ferme :** l'hypothèse qu'un gain de composite se cachait dans la forme du
bulletin. Elle est close à pleine masse, sur le jeu le plus large disponible.

## Reproduire

```bash
cd prompt_calibration && ../llm-agents/.venv/bin/python rewrite_weather.py --src v9 --variant bulletin_seul --dry-run
```

```bash
make protocol-lock SUBJECT="ticket 023bis" CLOUD_PAUSED=1 PROTOCOL_LOCK_FILE=experiments/protocol_lock_35.json
```

```bash
cd prompt_calibration && ../llm-agents/.venv/bin/python ab_meteo.py --config run_ab_chaine_g2.yaml --dataset all --arms v9,v9n,v9b --dry-run
```

`all.json` porte les chiffres de cette page — aucun n'est recopié à la main. `console.txt`
porte la sortie brute des 437 appels, lots incomplets et alarmes comprises. Le jeu `all` se
reconstruit par `cat calibration_datasets/<v>/train.jsonl calibration_datasets/<v>/val.jsonl`.
L'amendement **A12** du `PROTOCOLE.md` de `prompt_calibration` déclare cette lecture à pleine
masse et le bras `v9b`.
