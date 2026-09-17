# Ticket 052 — Documentation et scellement démographique de la cohorte v5 (Chapitre 4 § 4.5)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-13 suite à l'arbitrage de la tâche 5 de [`docs/paper/suivi_actions_publication.md`](../paper/suivi_actions_publication.md).
>
> **Touche l'article** : modification directe de [`docs/paper/article/fr/04_metrics_and_substrate.md`](../paper/article/fr/04_metrics_and_substrate.md) (§ 4.5).

## Contexte & Enjeux

La section 4.5 de l'article AAMAS 2027 présente le substrat d'évaluation empirique : la cohorte scellée de référence v5. Actuellement, la trame méthodologique est posée mais le tableau des 13 marges démographiques et les paramètres clés de mobilité comportent encore des balises `[xx]` à renseigner. 

Toutes les données empiriques ont été produites, vérifiées et scellées le 2026-09-04 sous l'empreinte sha256 `de73532e82c84f62eb72c8a614f3c27767bf5cca1d1574d3574f4a96b65bd8ce`. Ce ticket formalise le renseignement de ces valeurs et la sanctuarisation de la traçabilité.

## Ce que le ticket livre

Renseigner les emplacements dans [`docs/paper/article/fr/04_metrics_and_substrate.md`](../paper/article/fr/04_metrics_and_substrate.md) (§ 4.5) à partir des sources de vérité [`data/population/population_1000_AAMAS_v5/CONTROLE.md`](../../data/population/population_1000_AAMAS_v5/CONTROLE.md) et `MANIFEST.yaml` :

1. **Paramètres de composition et de mobilité de la cohorte :**
   - Nombre de personnes : $1\,000$ personas.
   - Nombre de ménages entiers : $499$ ménages (dont $474$ complets à $95{,}0\,\%$).
   - Chaînes de déplacements cycliques : $3\,299$ déplacements au total ($3{,}30$ déplacements/persona, contre $3{,}53$ dans l'enquête).
   - Part des personnes immobiles : $10{,}6\,\%$ (exactement identique au $10{,}6\,\%$ de l'enquête EMC²).
   - Sceau cryptographique sha256 de la population : `de73532e82c84f62eb72c8a614f3c27767bf5cca1d1574d3574f4a96b65bd8ce`.

2. **Complétion du tableau des 13 marges démographiques (Test d'équivalence TOST $\pm 1{,}0$ pt) :**
   - Renseigner pour chacune des 13 marges l'écart absolu maximal mesuré et confirmer le verdict conforme :
     * `classe_age` (6 classes, personne, AUAT p. 11) : écart max $0{,}50$ pt — **conforme**
     * `occupation` (7 classes, personne, AUAT p. 11) : écart max $0{,}50$ pt — **conforme**
     * `age_quinquennal` (15 classes, personne, microdonnées) : écart max $0{,}46$ pt — **conforme**
     * `motorisation_personne` (3 classes, personne, microdonnées) : écart max $0{,}09$ pt — **conforme**
     * `motorisation_menage` (3 classes, ménage, AUAT p. 21) : écart max $0{,}06$ pt — **conforme**
     * `couronne_residence` (4 couronnes, personne, AUAT p. 10) : écart max $0{,}05$ pt — **conforme**
     * `couronne_x_motorisation` (12 cellules, personne, microdonnées) : écart max $0{,}23$ pt — **conforme**
     * `taille_menage` (5 classes, personne, microdonnées) : écart max $0{,}09$ pt — **conforme**
     * `permis_conduire_18plus` (binaire, personne, microdonnées) : écart max $0{,}05$ pt — **conforme**
     * `abonnement_tc` (binaire, personne, microdonnées) : écart max $0{,}05$ pt — **conforme**
     * `type_logement` (binaire, personne, microdonnées) : écart max $0{,}05$ pt — **conforme**
     * `genre` (binaire, personne, microdonnées) : écart max $0{,}00$ pt — **conforme**
     * `immobiles_veille` (binaire, personne, microdonnées) : écart max $0{,}01$ pt — **conforme**

3. **Renvoi méthodologique :**
   - Maintenir et valider le renvoi vers la note [`docs/paper/methode/JUSTIFICATION_TAILLE_ECHANTILLON.md`](../methode/JUSTIFICATION_TAILLE_ECHANTILLON.md) explicitant le calcul de puissance statistique $N = 1\,000$ et le bootstrap par grappe agent.

## Critères d'acceptation
- [x] Tous les `[xx]` du § 4.5 sont remplacés par leurs valeurs réelles scellées (livré au § 4.1 après restructuration du chapitre).
- [x] Le tableau des 13 marges est intégralement renseigné avec ses écarts maximaux (conforme sur cohorte v6, toutes les marges < 0,50 pt).
- [x] L'empreinte sha256 de `population.json` est tracée (présente dans `MANIFEST.yaml` et métadonnées `<!-- source: ... -->` de l'article, conformément à la règle éditoriale excluant les détails de fabrication du corps du texte).

**Clôture le 2026-09-17** : Livré au § 4.1 de l'article dans les trois arbres (FR, EN, LaTeX Overleaf) sur la cohorte scellée `population_1000_AAMAS_v6` (sha256 `412efada802f79e8a72976ba25e0c7db8c9404adaed7c1f5e3e3d6afa3531db6`).
