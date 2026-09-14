# Ticket 059 — Étape 3b : Évaluation écologique sur presse locale, protocole à 5 conditions et validation des prédictions pré-enregistrées

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ce ticket cadre la méthode, les conditions expérimentales et la rédaction de l'Étape 3b pour le Chapitre 7 (`docs/paper/article/fr/07_untabulated_regimes.md`).

---

## 1. Contexte & Enjeu Scientifique (Standard AAMAS)

Dans le régime nominal (Chapitres 5 et 6), les modèles tabulaires supervisés (LightGBM) et économétriques (MNL) dominent les choix de routine grâce à 31 000 trajets d'apprentissage. En revanche, ils souffrent d'une **incompressibilité tabulaire structurelle** face aux perturbations du monde réel : ils sont strictement aveugles à toute information textuelle, sensorielle ou contextuelle non formalisée au préalable dans leur vecteur de 21 variables.

L'**Étape 3b** démontre la valeur ajoutée qualitative et adaptative des agents LLM face à des ruptures aiguës issues de la presse locale réelle de la métropole toulousaine (fermeture de parcs sous vent d'Autan, crise des punaises de lit dans le métro, grève des éboueurs dans les ruelles, marée humaine du Minotaure, vélos partagés électriques sur les coteaux).

---

## 2. Protocole Expérimental à 5 Conditions

Pour répondre aux objections classiques des relecteurs (*« Le LLM obéit juste aux consignes textuelles sans raisonner »*, *« Le LLM réagit à n'importe quel texte injecté »*, *« La comparaison est déloyale car l'oracle n'a rien reçu »*), chaque événement est testé selon **cinq conditions expérimentales rigoureusement contrôlées** sur la cohorte scellée :

| # | Condition | Ce que le modèle reçoit | Objection réfutée |
|---|---|---|---|
| **C1** | **Agent Nominal** | Zéro article (prompt nominal habituel) | Établit la ligne de base de référence du bras. |
| **C2** | **Agent + Article Brut** | Le texte journalistique réel extrait de la presse locale | Mesure de l'effet brut global. |
| **C3** | **Agent + Paraphrase sans indice modal** | Le même événement réécrit en neutralisant toute mention explicite de transport (ex. « métros renforcés » ou « chaussée bloquée » retirés) | Réfute l'objection de *suivisme lexical passif* : prouve que l'agent déduit la physique spatiale par raisonnement de bon sens. |
| **C4** | **Agent + Article Placebo** | Un article réel de presse locale sans pertinence pour les mobilités (ex. annonce culturelle éloignée ou fait divers neutre) | Réfute l'objection de *sensibilité au bruit* (contrôle de spécificité). |
| **C5** | **Oracle + Événement Encodé** | L'événement traduit au mieux sous forme tabulaire (coupure de liens OTP, dégradation d'horaires GTFS, vitesse du vent) | Réfute l'objection de *comparaison asymétrique déloyale*. |

---

## 3. Matrice Pré-enregistrée & Critères de Réfutation

### 3.1 Corpus Pré-enregistré et Gelé
- Le corpus complet de **30 scénarios réels** avec liens sources archivés et sélection du **Top 5 d'expertise comportementale** est pré-enregistré dans :
  [`docs/paper/sources/actualites/RAPPORT_SCENARIOS_QUALITATIFS_TOULOUSE.md`](../paper/sources/actualites/RAPPORT_SCENARIOS_QUALITATIFS_TOULOUSE.md).
- Ce rapport définit a priori la matrice des élasticités quadri-modales attendues (Voiture, Vélo, Marche, TC) cotées de $0$ à $3$ étoiles, gelée avant la campagne de requêtes.

### 3.2 Métriques de Validation Directionnelle
1. **Taux d'accord de signe ($S_{\text{sign}}$)** : pourcentage des reports modaux réels dont la direction ($+$ ou $-$) concorde avec la prédiction pré-enregistrée.
2. **$\kappa$ pondéré (Cohen / Fleiss)** : concordance sur l'intensité ordinale des reports modaux ($0$ à $3$ étoiles).

### 3.3 Critères Formels de Réfutation de l'Hypothèse $H_3$
L'hypothèse $H_3$ (adaptation contextuelle écologique supérieure du LLM) est réfutée si :
1. L'article placebo (C4) produit une perturbation modale d'amplitude comparable à l'article actif (défaut de spécificité).
2. La paraphrase sans indice modal (C3) détruit totalement la réallocation modale (l'agent ne raisonne pas, il exécute un ordre direct).
3. Le taux de signe $S_{\text{sign}}$ ne dépasse pas significativement le hasard ($50\,\%$ sous test binomial).

---

## 4. Livrables & Actions

1. **Section 7.2 & 7.3 du Chapitre 7** : Rédaction définitive intégrant le tableau des 5 conditions et les 5 scénarios majeurs.
2. **Annexe F (Matrice des 30 Scénarios)** : Transcription du rapport de 30 articles en annexe méthodologique du papier.
3. **Planification de la campagne (Tâche 41 & 42)** : Cadrage du script d'injection des articles dans le contrôleur d'expérience sans simulateur.
