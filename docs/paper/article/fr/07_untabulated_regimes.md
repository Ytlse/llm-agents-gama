# 7. Régimes non tabulés : hystérésis et presse locale (brouillon)

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

**Critères de réfutation de H3.** L'hypothèse tombe si : (i) l'agent sans registre montre la même inertie à J+1 ; (ii) la reprise des jours 3 à 5 n'est pas monotone ; (iii) un article placebo produit le même report modal que l'article pertinent.

---

### Tickets associés à ce chapitre
- [Ticket 041](../../../tickets/ticket_041_etape_3a_hysteresis_longitudinale.md) — Étape 3a longitudinale : habitudes, choc, récupération (GAMA offline, 5 à 60 jours)
- [Ticket 059](../../../tickets/ticket_059_etape_3b_presse_locale_et_predictions_preenregistrees.md) — Étape 3b : Évaluation écologique sur presse locale, protocole à 5 conditions et validation des prédictions pré-enregistrées
- [Ticket 063](../../../tickets/ticket_063_campagne_experimentale_hysteresis_longitudinale.md) — Campagne expérimentale longitudinale d'hystérésis et d'érosion mémorielle (Étape 3a)
- [Ticket 064](../../../tickets/ticket_064_campagne_experimentale_presse_locale_et_scoring.md) — Campagne expérimentale de presse locale à 5 conditions et scoring de réfutation (Étape 3b)

---

<!-- NOTE DE TRAVAIL — à traiter, ne fait pas partie du texte -->

> **À traiter (2026-09-14, ticket 070).** Deux points sur le § 5.3.
>
> 1. **Le dénominateur de la condition 5.** « Le plan est porté à cinq conditions par
>    événement, sur une cohorte de 1 000 déplacements » vaut pour les conditions 1 à 4, qui
>    sont textuelles et atteignent tous les agents. La condition 5 est physique : une coupure
>    encodée dans le graphe ne touche que les trajets qui l'empruntent. Mesuré le 2026-09-14 :
>    **18,2 % des trajets voiture de 7 h-9 h passent par la rocade, soit ≈ 38 déplacements par
>    journée simulée** à 1 000 agents. L'exigence « le même événement déclaré deux fois » est
>    donc tenue en droit, pas en portée : 100 % des agents en langue, ~18 % en graphe.
>    Trace `2026-09-14_11-20_exposition_rocade_lot0bis`.
> 2. **Un canal d'encodage manque au tableau.** La condition 5 liste « liens coupés dans OTP,
>    fréquences dégradées, météo ». L'accident posé sur une arête en sera un quatrième — le
>    jour où il produira un retard.
