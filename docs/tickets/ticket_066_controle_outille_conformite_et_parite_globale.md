# Ticket 066 — Contrôle outillé de conformité et de parité globale (make paper-parite)

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ce ticket formalise la procédure et les règles de validation outillée de conformité globale de l'article pour AAMAS 2027 (Tâche 54 de `docs/paper/suivi_actions_publication.md`).

---

## 1. Contexte & Enjeux (Règle Parité Tri-Arbres)

L'article AAMAS 2027 est maintenu en miroir sur trois arbres documentaires distincts dans `docs/paper/article/` :
1. `fr/` : version de travail et d'arbitrage scientifique en français.
2. `en/` : maître officiel de soumission en anglais.
3. `overleaf/` : gabarit typographique officiel LaTeX AAMAS (`aamas.cls`).

Cette structure nécessite un garde-fou automatisé strict pour interdire toute divergence silencieuse de contenu, de numérotation ou de version entre les trois représentations.

---

## 2. Dispositif Outillé de Vérification

Le contrôle repose sur la cible du Makefile :
```bash
make paper-parite
# Exécute : python3 scripts/paper/verifier_parite.py
```

### Règles de conformité contrôlées :
1. **Concordance des slugs et numéros de chapitres :** chaque chapitre `NN_slug` doit posséder le même identifiant technique sur `fr/`, `en/` et `overleaf/`.
2. **Parité stricte des versions déclarées :** les versions `vX.Y` indiquées dans les en-têtes doivent être strictement identiques.
3. **Alignement avec le plan directeur :** correspondance bidirectionnelle exacte avec `docs/paper/article/plan/PLAN.md` (aucun chapitre orphelin, aucune section du plan non instanciée).
4. **Gestion des brouillons :** tolérance explicite pour les chapitres encore au statut `brouillon` documentés en français.

---

## 3. Critères d'Acceptation (Porte Finale)

- [ ] La commande `make paper-parite` s'exécute sans erreur (code retour `0`).
- [ ] Tous les chapitres finalisés présentent un statut `conforme` sur les trois arbres (`en`, `fr`, `tex`).
- [ ] Le rapport final affiche `SUCCÈS : tous les chapitres rédigés sont à parité sur les trois arbres`.
