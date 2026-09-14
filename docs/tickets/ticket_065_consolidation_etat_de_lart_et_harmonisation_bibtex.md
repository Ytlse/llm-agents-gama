# Ticket 065 — Consolidation de l'état de l'art (5 thèmes) et harmonisation BibTeX pour AAMAS

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ce ticket cadre la consolidation bibliographique pour la soumission AAMAS 2027 (Tâches 45 à 49 de `docs/paper/suivi_actions_publication.md`).
> **Porte préalable obligatoire :** avant d'engager du temps de recherche bibliographique sur un thème, confirmer explicitement si son approfondissement est toujours indispensable pour l'article ou si l'existant suffit.

---

## 1. Porte de Validation Préalable (Sanity Check)

Avant toute recherche active ou ajout de notices, procéder à un **audit d'utilité stricte** thème par thème :
- Vérifier si les citations actuelles dans [`docs/paper/article/CITATIONS.md`](../paper/article/CITATIONS.md) et [`docs/paper/sources/references.bib`](../paper/sources/references.bib) couvrent déjà le besoin argumentatif.
- Ne lancer une recherche bibliographique complémentaire que sur les thèmes où une lacune critique fragiliserait la défense du papier face aux relecteurs d'AAMAS.
- Les thèmes jugés non indispensables ou déjà suffisamment étayés seront classés sans suite pour concentrer l'effort sur le cœur de l'article.

---

## 2. Spécification Détaillée des 5 Thèmes

### Thème 1 — Formation et persistance des habitudes de mobilité (Tâche 45)
- **Rôle dans l'article :** Appui théorique du Chapitre 7 (Étape 3a, § 7.1 / [Ticket 041](ticket_041_etape_3a_hysteresis_longitudinale.md)) sur l'apprentissage et l'inertie décisionnelle quotidienne.
- **Périmètre ciblé :**
  - Psychologie cognitive de l'habitude : mécanismes de renforcement et de déclenchement contextuel (*Wood & Neal, 2009* ; *Verplanken & Aarts, 1999*).
  - Persistance post-perturbation : report modal durable après rupture temporaire (*Larcom et al., 2017* sur la grève du métro londonien montrant $\approx 5\,\%$ de reports permanents).
- **Contrôle préalable :** Confirmer si la citation de Larcom (2017) et de Wood & Neal suffit à cadrer l'ordre de grandeur de la demi-vie et du report résiduel.

### Thème 2 — Chocs de transport réels et élasticités observées (Tâche 46)
- **Rôle dans l'article :** Validation écologique du Chapitre 7 (§ 7.1 & 7.2) pour comparer la réaction des agents à des chocs réels documentés.
- **Périmètre ciblé :**
  - Études empiriques de perturbations aiguës de réseaux urbains (pannes de métro, fermetures d'infrastructures, crues).
  - Ordres de grandeur des élasticités croisées de report modal (voiture, marche, vélo, transports en commun).
- **Contrôle préalable :** Confirmer si un cadrage macro d'ordre de grandeur est nécessaire ou si l'argumentation comparative interne (bras M vs bras A vs bras O) se suffit à elle-même.

### Thème 3 — Optimisation discrète de prompts et Green AI (Tâche 47)
- **Rôle dans l'article :** Soutien du Chapitre 4.5 (§ 4.5 / [Ticket 054](ticket_054_sobriete_computationnelle_prompt_calibration.md)) sur la calibration et le refus des algorithmes génétiques gloutons.
- **Périmètre ciblé :**
  - Méthodes d'optimisation automatique de prompts : OPRO (*Yang et al., 2023*), DSPy (*Khattab et al., 2023*).
  - Éthique et sobriété computationnelle : principes du *Green AI* (*Schwartz et al., 2020*), justification de l'arrêt raisonné face aux coûts écologiques et financiers des recherches exhaustives.
- **Contrôle préalable :** Vérifier si le texte du Chapitre 4.5 est déjà suffisant avec ses références actuelles.

### Thème 4 — Benchmark SILICA, alignement multi-agents et benchmark GTA (Tâche 48)
- **Rôle dans l'article :** Ancrage dans la littérature de pointe AAMAS / ACM pour l'Introduction, le Chapitre 2 et la Conclusion.
- **Périmètre ciblé :**
  - Benchmark SILICA (*Bin Tareaf, 2026*) : taxonomie des trois niveaux de stress-test (*Tier 1 exploratory, Tier 2 robust, Tier 3 transferable*).
  - Dynamique collective et biais des populations de LLMs (*Flint Ashery & Baronchelli, 2025/2026*).
  - Benchmark GTA (*Lämmer, Colley & Ebel, 2026*) : confrontation d'agents LLM aux enquêtes de mobilité nationales (entrée A33 de `CITATIONS.md`).
- **Contrôle préalable :** Valider l'adéquation des notices et des versions (préprint vs publication officielle).

### Thème 5 — Nettoyage et harmonisation du fichier BibTeX (Tâche 49)
- **Rôle dans l'article :** Rigueur formelle et standard de soumission AAMAS 2027.
- **Périmètre ciblé :**
  - Audit complet de `docs/paper/sources/references.bib` face aux 34 notices de `docs/paper/article/CITATIONS.md`.
  - Harmonisation des clés, résolution des doublons et variantes d'orthographe (ex. patronyme *Flint Ashery*).
  - Renseignement exhaustif et systématique des DOI, volumes, pages et éditeurs (les relecteurs AAMAS rejetant d'emblée les références tronquées ou fantômes).
- **Contrôle préalable :** Tâche formelle à exécuter impérativement avant la compilation finale LaTeX.

---

## 3. Livrables

1. Tableau d'arbitrage préalable (statut de chaque thème : *maintenu*, *allégé* ou *écarté*).
2. Fichier `docs/paper/sources/references.bib` nettoyé, harmonisé et conforme aux standards Overleaf / AAMAS.
3. Cases à cocher mises à jour dans `docs/paper/article/CITATIONS.md`.
