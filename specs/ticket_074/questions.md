# Ticket 074 — questions vivantes

> Ce que j'ai tranché seul pour avancer, et qui mérite ton arbitrage à la fin.
> Rien ici n'est bloquant : chaque point a été résolu par l'hypothèse la plus conservatrice.

---

## Q1 — Deux anomalies de texte préservées telles quelles dans la traduction

**Contexte.** Une traduction change la langue, pas le contenu. Deux variantes portaient un texte
fautif en français ; je les ai traduites **fautives**, plutôt que de les réparer au passage.

### Q1a — `expert_chaine_m6`, `m7`, `m7.1` : une description de schéma corrompue

Le français dit :

> « Une entrée par option proposée à ce persona, sans exception. La somme des&nbsp;&nbsp;doit
> valoir exactement 100. »

Le mot `` `probability` `` a disparu entre deux espaces restés en place. C'est une corruption
d'édition, pas une tournure. Traduit en :

> "One entry per option offered to this persona, without exception. The sum of the&nbsp;&nbsp;must
> be exactly 100."

**Pourquoi je n'ai pas réparé.** Ces trois variantes ont servi à des exécutions archivées. Réparer
sous couvert de traduire modifierait l'instrument d'une mesure déjà faite, et la retouche
passerait inaperçue dans un diff de 22 variantes.

**Ce que ça coûte si on laisse.** Rien pour la campagne (aucune des 10 expériences ne désigne ces
variantes). Le texte est en revanche **publié en annexe** (ticket 069), où il se lira comme une
négligence.

**Ce que ça coûte si on répare.** Les trois variantes cessent d'être le texte qui a produit les
mesures archivées. Il faudrait le dire dans l'annexe.

→ **Réparer, ou laisser et l'annoter dans l'annexe ?**

### Q1b — `persona_v5` : une phrase contradictoire

Le français dit :

> « Tu vas incarner séquentiellement des personnes vivant à Toulouse, France **qui en suporte pas
> le vélo et la voiture et adore le vélo**. »

Le vélo y est à la fois détesté et adoré, et « en » est mis pour « ne ». C'est la seule chose qui
distingue `persona_v5` de `persona_v4` — donc **toute la variante**. Traduit littéralement,
contradiction comprise.

→ **Même question. Mon avis : laisser.** Une variante dont l'unique apport est une consigne
contradictoire est un résultat expérimental en soi ; la réparer reviendrait à inventer une
variante qui n'a jamais tourné.

---

## Q2 — Les libellés d'occupation ne sont pas traduits, ils sont contournés

B-7 demande de traduire `main_occupation` « à l'affichage uniquement », parce que ses libellés
français sont des clés de jointure (`scripts/synthesis/frames.py:138`, `scripts/progedo_logit/`).

**Ce que j'ai fait** : `_build_profile_narrative` préfère désormais `professional_activity`, qui
porte déjà l'équivalent anglais dans chaque enregistrement. Aucune table de correspondance n'a été
écrite.

**La nuance à connaître** : la correspondance n'est pas bijective. `Scolaire (jusqu'au Bac)` se
répartit entre `Child (under 14)` (132) et `Student` (33) ; `Personne au foyer` entre
`Other Inactive` (40) et `Homemaker` (10). Le prompt dira donc `Child (under 14)` là où il disait
`Scolaire (jusqu'au Bac)` — **plus précis**, pas équivalent.

→ **C'est un changement de contenu, pas seulement de langue.** Il est assumé et documenté, mais
il entame la promesse « une seule variable change ». À dire au chapitre 8 avec le reste.

---

## Q3 — `terminal_time.yaml` bumpé en `tt5` alors qu'aucune valeur n'a changé

Le fichier impose de bumper `version:` à « toute modification des valeurs ». Je l'ai bumpé pour une
modification de **libellés**, ce que la règle ne prévoyait pas.

**Pourquoi**, et c'est mesuré, pas supposé : `osmnx_direct` pose ces libellés dans
`Transit.step_label`, et le cache OTP persistant mémorise les `TravelPlan` sérialisés. J'ai relu un
plan de l'archive : il rend aujourd'hui

    Travel time: 28 minutes, including 20 minutes of access and parking. Distance: 6.5 km.
    - Rejoindre la voiture: 20 minutes.
    - Conduite: 8 minutes.

— en-tête anglais, sous-étapes françaises. Sans bump, le jeu v6 aurait hérité de ça au scellement.

`routing_version` (r3) n'est **pas** bumpée : le cache de routage OSMnx ne mémorise que du temps
réseau. Le recalcul à froid (~2 h) est donc épargné, et le cache OTP était vide de toute façon.

→ **Rien à trancher, mais à savoir** : la règle du fichier mériterait d'être reformulée en
« toute modification de ce qui entre dans un plan mis en cache », libellés compris.

---

## Q4 — 31 tests sont passés en veille avec l'archive froide

Avant le lot A : `888 passed, 2 skipped`. Après : `857 passed, 33 skipped`.

Les 31 nouveaux sauts viennent tous de `data/experiences` et `data/population` désormais vides —
`test_035_10_scoring_cloture`, `test_047_mesure_systematique_choix_forces` (10 tests),
`test_045_02_journee_refermee`, `test_perimetre_chargement`. Ils sautent **en le disant**
(« aucune exécution terminée dans data/experiences (substrat absent) »), ce qui est le bon
comportement.

→ **C'est une perte de couverture réelle et temporaire.** Elle se referme quand la v6 est scellée
et la campagne rejouée. À vérifier explicitement à ce moment-là : le compte doit revenir à 2.

---

## Q5 — Le renommage des prompts : schéma complet à valider

Tu as tranché `expert_baseline_01` → `prompt_expert_01`. J'en déduis le schéma
`prompt_<famille>_<nn>`, sans segment de trait. Proposition pour les 22 :

| Aujourd'hui | Demain | Famille |
|---|---|---|
| `prompt_minimal` | `prompt_minimal_01` | minimale |
| `minimal_persona` | `prompt_expert_01` | experte |
| `b_min` | `prompt_expert_02` | experte |
| `b0_pristine` | `prompt_expert_03` | experte |
| `expert` | `prompt_expert_04` | experte |
| `expert_m1` | `prompt_expert_05` | experte |
| `expert_m4` | `prompt_expert_06` | experte *(ACTIVE)* |
| `expert_chaine_m5` … `m7.1` | `prompt_expert_07` … `10` | experte |
| `expert_gem_3.8_v1` … `v3`, `v2_neutre_justif` | `prompt_expert_11` … `14` | experte |
| `prompt_optimise_v4`, `v5` | `prompt_expert_15`, `16` | experte |
| `persona_v1` … `v5` | `prompt_expert_17` … `21` | experte |

→ **L'ordre de numérotation est arbitraire.** Chronologique ? Par famille de dérivation
(`derive_de`) ? Alphabétique ? Dis-moi, sinon je prends l'ordre de `derive_de`, qui se lit comme
une généalogie.

Chaque entrée gardera `_ancien_nom`, et `PromptManager` continuera de résoudre les anciens noms
**en lecture** (avec un avertissement nommant le nom canonique), pour que les traces archivées
restent relisibles.
