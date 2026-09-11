# 6. Régimes non tabulés : hystérésis et presse locale (brouillon)

<!-- Dernière mise à jour : 2026-09-10 -->

**Document :** brouillon français du chapitre, extrait de `MANUSCRIT_DETAILLE_2026.md` `v1.6` (3 septembre 2026), § 5, Étape 3 — « Étape 3 : La Valeur Ajoutée du LLM (Événements Réels & Dynamique Temporelle) ». Le manuscrit entier est figé dans [`../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md`](../../archive/MANUSCRIT_DETAILLE_2026_v1.6.md).
**Statut :** `brouillon v0` — texte **antérieur** à la réécriture de l'introduction (dont la v0.1 date du 8 septembre 2026). Trois choses à reprendre avant d'en faire un chapitre : le vocabulaire « Tier 1 / 2 / 3 », que les chapitres rédigés remplacent par *exploratory / robust / transferable* (étapes de certification de SILICA) ; les chiffres, à recouper depuis leur source dans le dépôt et non recopiés d'ici ; les renvois de section, qui suivent l'ancienne numérotation du manuscrit. Ni maître anglais ni rendu LaTeX à ce stade.
**Place dans l'article :** section du même numéro dans le plan annoncé en 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). État d'avancement : [`../README.md`](../README.md).

---

### 5.1 Étape 3a : Adaptation aux Situations Exceptionnelles & Hystérésis Temporelle (5 Jours)
Là où les modèles tabulaires (LightGBM, MNL) sont amnésiques et reprennent instantanément leur prédiction nominale dès la fin d'un incident physique, l'agent LLM dispose d'un **registre de mémoire court-terme $\mathcal{M}_t$** :
$$\mathcal{M}_t = \left\{ e_k = \left( t_k, \text{mode}_k, \Delta t_{\text{retard}, k}, \text{ressenti}_k \right) \mid t - t_k \le \Delta T_{\text{horizon}} \right\}$$
La confiance envers le mode perturbé $m$ évolue selon :
$$w_m(t) = 1 - \sum_{\substack{e_k \in \mathcal{M}_t \\ \text{mode}_k = m}} \gamma \cdot \frac{\Delta t_{\text{retard}, k}}{\Delta t_{\text{ref}}} \cdot \exp\left(-\lambda (t - t_k)\right)$$

```
       J1 : Nominal            J2 : Choc (17h)           J3 : Réseau réparé       J4-J5 : Résorption
 ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
 │ Métro fluide         │  │ Panne majeure Ligne A│  │ Métro 100% rétabli   │  │ Métro toujours stable│
 │ Taux Choix : 80 %    │  │ Retard subi +45 min  │  │ LIGHTGBM : 80 %      │  │ LIGHTGBM : 80 %      │
 │ (État nominal base)  │  │ Mémoire négative MT  │  │ (Amnésie complète)   │  │ (Statique)           │
 └──────────────────────┘  └──────────────────────┘  ├──────────────────────┤  ├──────────────────────┤
                                                     │ LLM + MÉMOIRE : 35 % │  │ LLM + MÉMOIRE :      │
                                                     │ (Évitement/Churn J+1)│  │ 60 % (J4) ──► 78 % (J5)
                                                     └──────────────────────┘  └──────────────────────┘
```

### 5.2 Étape 3b : Évaluation Écologique sur Événements Réels Sourcés (Presse Locale)
Pour apporter une validité écologique forte, nous injectons des articles de presse locale réels de la métropole toulousaine :

1. **Événement Culturel Majeur (Minotaure - La Machine)** : « Hyper-centre piétonnisé, boulevards fermés, métros renforcés ».  
   *Réaction LLM :* Éviction totale de la voiture au profit du Métro et de la marche.  
   *Modèle ML Tabulaire :* Aveugle à l'événement textuel brut, maintient la voiture.
2. **Événement Régulatoire & Environnement (Pic d'Ozone & Canicule)** : « Transports collectifs à tarif réduit, circulation différenciée Crit'Air ».  
   *Réaction LLM :* Report préférentiel vers les TC climatisés.
3. **Perturbation d'Infrastructure (Coupure Rocade Empalot)** : « Rocade coupée, +1h de bouchon ».  
   *Réaction LLM :* Report d'urgence vers le train TER / Métro.

### 5.3 Plan Expérimental à Cinq Conditions et Prédictions Pré-Enregistrées

Comparer « agent avec article » à « oracle sans article » ne prouve rien : l'oracle n'est pas *aveugle*, il n'est pas *informé*. Le plan est donc porté à **cinq conditions** par événement, sur une cohorte de $1\,000$ déplacements :

| # | Condition | Ce que le modèle reçoit | L'objection qu'elle ferme |
|---|---|---|---|
| 1 | Agent, régime nominal | Aucun article | Référence interne du bras |
| 2 | Agent + article brut | Le texte de presse tel quel | — (mesure de l'effet total) |
| 3 | **Agent + paraphrase sans indice modal** | Le même fait, réécrit sans aucune mention de mode (« métros renforcés » retiré) | *« Le modèle ne raisonne pas, il obéit »* : l'article contient souvent la réponse |
| 4 | **Agent + article placebo** | Un article réel classé « éliminer », sans effet modal attendu | *« Le modèle réagit à n'importe quel texte »* — contrôle de spécificité |
| 5 | **Oracle + événement encodé** | L'événement traduit en variables : liens coupés dans OTP, fréquences dégradées, météo | *« Votre oracle est muet parce que vous ne lui avez rien donné »* |

La condition 5 sert deux fois : elle rend la comparaison honnête, **et** elle rétablit la cohérence physique du bras textuel — si l'article ferme des rues que le calculateur d'itinéraires ignore, l'agent raisonne contre les durées qu'on lui montre, et le résultat devient ininterprétable dans les deux sens. Le contexte textuel et le contexte physique doivent être **le même événement déclaré deux fois**, une fois en langue et une fois en graphe.

**Prédictions pré-enregistrées.** La grille d'expertise comportementale des 30 articles (impacts modaux notés de 0 à 3, échelle spatiale, classe de crédibilité) a été établie **avant tout appel au modèle**. Gelée par empreinte git et datée, elle constitue un jeu de $4 \times 30 = 120$ **prédictions directionnelles signées**. L'évaluation rapporte le taux de signe correct et un $\kappa$ pondéré (l'intensité prédite étant ordinale), et publie la grille intégrale en annexe.

**Précautions méthodologiques d'ordonnancement (Baronchelli, 2026).** Pour neutraliser tout biais d'amorçage ou de saillance positionnelle (*shared cues* / biais de primauté), l'ordre de présentation des options d'itinéraires et des modes est systématiquement randomisé de manière indépendante pour chaque requête d'agent.

**Critères de réfutation de H3.** L'hypothèse tombe si : (i) l'agent sans registre montre la même inertie à J+1 ; (ii) diviser la vitesse d'oubli $\lambda$ par trois ne déplace pas la courbe ; (iii) un article placebo produit le même report modal que l'article pertinent.

---
