# Ticket 095 — Ce que la campagne du 2026-09-21 établit

> **Observations brutes** (hors git, doctrine du 2026-09-02) :
> `docs/traces/2026-09-21_ticket095_plancher_et_choc_861500/`, avec `EMPREINTES.json`
> (sha256 de chaque fichier + révision du code `2baf55b7ada5`).
> **Ce document se versionne** : il dit ce que la campagne établit, pas comment on l'a mesuré.
> Les mesures dérivées se recalculent depuis les observations — elles ne sont pas figées ici.

Persona **861500 (Capucine Boulay)**, 58 ans, temps plein, permis, deux voitures. Trois bras,
horizon 42 jours, ancre lundi 16 mars 2026, cache coupé, température 0.

| Bras | Archive | Choc | Décisions |
|---|---|---|---:|
| témoin 42 j | `2026-09-21_11_11` | aucun | 201 |
| témoin 1 semaine | `2026-09-21_14_28` | aucun | 31 |
| traité | `2026-09-21_15_13` | C6, jours 15-16 | 197 |

Modèles : **`gemini-3.1-flash-lite`** pour la décision et l'auto-réflexion, **`gemini-3.5-flash-lite`**
pour la réflexion du soir et l'enquête. 471 appels sur le bras témoin, **aucun repli vers une
autre famille** alors que onze autres instances étaient chargées.

---

## 1. La durée d'un effet se déduit de la gravité de l'événement

**C'est la thèse du ticket, et elle est établie.** Le choc déclaré vaut une gravité de **0,700**
(retard saturé 0,50 + incident réseau 0,20), mesurée et journalisée, donc une durée de service de
`14,56 × ln(1/0,35) = 15,29 jours`. La prédiction était écrite dans `tests.md` **avant** le run.

```
[noyau] 861500 : le souvenir de choc du 2026-03-30 est sorti du bloc « ce qui a changé
récemment » (durée 15.29 j dérivée d'une gravité de 0.70 (force 14.56 j, durée calculée 15.29 j))
```

Avant ce ticket, cette date se lisait dans `settings.py`.

## 2. L'hystérésis, et le retour au moment de la sortie

Part de la voiture, sur les seules décisions prises par le modèle :

| | avant choc | après choc | après sortie de fenêtre |
|---|---:|---:|---:|
| Témoin | 57 % (n=49) | 57 % (n=72) | 55 % (n=73) |
| **Traité** | 60 % (n=57) | **15 %** (n=67) | **54 %** (n=65) |

Le témoin est plat de bout en bout. Le traité s'effondre puis revient, et le retour coïncide avec
la sortie du souvenir.

## 3. L'agent a changé d'avis, pas seulement d'itinéraire

Perceptions déclarées de la voiture, échelle 0-10 :

| critère | J12 *(avant)* | J17 *(après choc)* | J31 *(après sortie)* | J40 |
|---|---:|---:|---:|---:|
| rapidité | 9 | 8 | 9 | 9 |
| praticité | 9 | 6 | 9 | 9 |
| confort | 8 | 5 | 8 | 8 |
| **sécurité** | 8 | **3** | 8 | 8 |
| coût | 6 | 5 | 6 | 6 |
| **écologie** *(témoin)* | **3** | **3** | **3** | **3** |

**La question témoin tient** : l'écologie ne bouge d'aucun point aux quatre jalons. L'agent n'a
pas exprimé une humeur globale, il a noté des critères. Sans cette garde, les cinq autres colonnes
ne s'interpréteraient pas.

Le plancher de bruit de la voiture est **nul** — zéro variation sur les quatre jalons du témoin,
et zéro écart entre les deux runs au jalon d'avant le choc. La chute de 8 à 3 en sécurité est donc
attribuable au choc sans discussion.

**L'effet est entièrement réversible ici.** Les six valeurs reviennent à l'identique. La campagne
de septembre sur Corinne laissait au contraire une trace permanente (80 % contre 95 % au témoin).
Deux personas, deux résultats : **ne rien généraliser avant un troisième.**

---

## 4. Ce que cette campagne NE permet PAS d'affirmer

**Le plancher de bruit des décisions n'est pas nul : 1 écart de mode sur 31 décisions appariées
(3,2 %).** Température 0, graines identiques, cache coupé — c'est le modèle qui ne rend pas deux
fois la même distribution. L'attendu « 0 écart » est démenti, et le « 0 sur 44 » du ticket 077 se
lit comme un tirage chanceux. Deux témoins ne disent pas si 3,2 % est le taux ou un accident :
mesure sérieuse reportée (§ 7 bis du ticket).

**Le bloc n'est pas alimenté par le seul choc déclaré.** Le témoin, sans aucun choc, produit
**trois** souvenirs de gravité ≥ 0,70 : la réflexion du soir juge d'elle-même certains vécus
graves. Deux d'entre eux existent dans les deux bras, donc l'attribution reste saine — mais la
phrase « le bloc porte le choc » serait fausse.

**Le second jour de choc n'a pas pesé sur le bloc** : 20 minutes de retard valent 0,533, sous le
seuil de 0,70. Il reste un souvenir ordinaire.

**Le choc déclaré tombe exactement sur le seuil** (0,50 + 0,20 = 0,70, comparaison `>=`). Toute
modification d'une pondération le ferait basculer sous le seuil, et l'effet disparaîtrait sans
qu'aucune ligne ne le dise.

**Le plafond de 30 jours a mordu**, en situation : deux souvenirs ont vu leur force croître de
14,56 à 30 à force d'être rappelés, et leur durée de 31,49 j a été ramenée à 30. Le plafond ne
mord jamais par la gravité — seulement par le renforcement au rappel.

**Un seul persona.** Dix agents ne représentent rien, un encore moins. La référence de l'article
reste `population_1000_AAMAS_v6`.
