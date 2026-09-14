# Ticket 057 — Audit méthodologique et réflexion sur la double lecture tabulaire en chaîne vs hors chaîne (Chapitre 6 § 6.2)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-13 suite à l'arbitrage de la tâche 14 de [`docs/paper/suivi_actions_publication.md`](../paper/suivi_actions_publication.md).
>
> **Nature du ticket** : **Tâche de réflexion critique, d'audit méthodologique et de vérification expérimentale « ceinture et bretelles ».** Avant d'affirmer dans le papier que l'écart entre lecture en chaîne et hors chaîne prouve le coût de l'absence d'anticipation de la journée, il est impératif d'auditer la méthode, de contrôler l'acceptabilité des chiffres et de vérifier qu'aucun biais de mesure n'explique cette dégradation. Les conséquences rédactionnelles ne seront tirées qu'après validation.

---

## 1. Contexte & Questionnements

Les exécutions récentes sur la cohorte scellée v5 font apparaître une dégradation brutale des 4 familles tabulaires lorsqu'elles passent du mode « hors chaîne » au mode « en chaîne » :
- **Hors chaîne** (`nochn_noret_nosim`) : les 4 modèles sont très proches et stables (Composite entre $4{,}18$ et $4{,}45$, Métrique 2 entre $3{,}97$ et $4{,}18$, environ $1{,}4\,\%$ de décisions contraintes).
- **En chaîne** (`nosim`) : la Métrique 2 (distribution des parts) fait un bond spectaculaire vers le haut (LightGBM : $10{,}46$ ; KLR : $9{,}95$ ; MNL : $11{,}15$ ; RF : $10{,}45$), avec plus de $20\,\%$ de décisions contraintes au retour.

Avant d'ériger cet écart en résultat scientifique central dans l'article, nous devons appliquer le principe d'exigence absolue : **« ceinture et bretelles »**. 
- Ces résultats sont-ils acceptables et plausibles ? 
- N'y a-t-il pas un problème dans l'implémentation de la règle de chaîne dans le runner ?
- Le traitement des trajets de retour contraints est-il méthodologiquement irréprochable ou introduit-il une distorsion artificielle ?

---

## 2. Programme d'Audit et de Réflexion Méthodologique

### 2.1 Audit de la chaîne d'application des contraintes dans le code
* **Vérification du runner sans simulateur** :
  - Examiner le mécanisme qui impose le mode au retour dans `services/llm-agents/experiences/runner.py` (ou script équivalent) : comment l'état de localisation du véhicule est-il mis à jour et vérifié ?
  - La proportion de $\approx 20{,}8\,\%$ de décisions contraintes observée en chaîne correspond-elle exactement à la structure réelle des chaînes d'activités des personas, ou y a-t-il des blocages indus ?
* **Examen du dénominateur et de la renormalisation** :
  - Quand un modèle tabulaire est confronté à un retour contraint (ex. obligation de rentrer en voiture car la voiture est au travail), la décision est-elle comptée comme un choix scoré ou comme une exclusion ?
  - La Métrique 2 calcule-t-elle les parts modales sur l'ensemble des trajets ou seulement sur les trajets où une délibération réelle avait lieu ? Vérifier l'impact mathématique exact de cette convention sur le saut de $4{,}01$ à $10{,}46$.

### 2.2 Contrôle qualitatif sur cas d'échantillons
* **Audit unitaire de 30 parcours d'agents** :
  - Extraire 30 chaînes complètes de déplacements d'agents pour chaque famille tabulaire (LGBM, RF, KLR, MNL).
  - Contrôler pas à pas : les décisions prises le matin étaient-elles raisonnables ? Les impasses créées au retour sont-elles des situations urbaines réalistes (ex: navetteur parti en voiture et contraint de rentrer avec) ou des artefacts de code ?

### 2.3 Évaluation de la validité scientifique de la double lecture
* **La comparaison est-elle juste ?**
  - Un modèle tabulaire ajusté sur des microdonnées d'enquête (où les personnes réelles respectaient déjà les chaînes) n'est-il pas intrinsèquement pénalisé deux fois lorsqu'on lui réapplique le filtre ?
  - L'écart mesuré reflète-t-il fidèlement le coût de la myopie temporelle, ou un artefact de sur-contrainte ?

---

## 3. Ce que le ticket livre

1. **Rapport d'audit technique et méthodologique sur la double lecture** : diagnostic tranché sur l'absence de biais dans l'implémentation des contraintes en chaîne.
2. **Recommandations d'interprétation pour le Chapitre 6** :
   - Si les chiffres sont validés sans faille : définir le cadrage honnête et prudent à adopter dans l'article.
   - Si un biais ou un problème de mesure est détecté : corriger le runner et re-mesurer avant toute écriture.

## Critères de clôture
- [ ] Le code appliquant les contraintes de chaîne dans le runner a été audité et validé.
- [ ] L'impact de la part des décisions contraintes (~20 %) sur la Métrique 2 est formellement expliqué et quantifié.
- [ ] L'échantillon de parcours individuels a été inspecté sans déceler d'incohérence.
- [ ] Aucune affirmation péremptoire n'est rédigée dans le texte du chapitre 6 avant la clôture formelle de cet audit.
