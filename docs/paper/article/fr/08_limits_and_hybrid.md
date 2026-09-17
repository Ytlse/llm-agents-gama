# 8. Limites

<!-- Dernière mise à jour : 2026-09-17 -->

**Document :** brouillon français du chapitre.
**Statut :** `brouillon v0.1` (17 septembre 2026) — première rédaction. Le texte antérieur, extrait du § 6 du manuscrit de septembre, exposait une cascade hybride et un tableau comparatif dont trois cellules sur cinq restaient à mesurer et dont deux chiffres ont depuis été retirés du chapitre 9 faute de source ; il est remplacé, et le tableau ne revient pas. Les limites que le chapitre publie viennent des tickets 049 et 057, le coût d'inférence d'une mesure du 17 septembre 2026. La figure 8.1 porte la cascade ; ses deux parts de flux sont des emplacements **[xx]**, à remplir quand un critère d'aiguillage aura été défini et mesuré.
**Place dans l'article :** section du même numéro dans le plan annoncé en 1.4 de [`../en/01_introduction.md`](../en/01_introduction.md). État d'avancement : [`../README.md`](../README.md).

---

## 8.1 L'offre d'itinéraires ne contient aucun trajet combiné

OpenTripPlanner est interrogé mode par mode, et le jeu d'options soumis à l'agent ne contient donc aucun itinéraire mixte : ni voiture jusqu'à un parc-relais puis métro, ni vélo jusqu'à une gare puis train régional. L'enquête, elle, en compte, et la hiérarchie nationale des modes les range presque tous en transports collectifs : 760 des 770 déplacements qui mêlent voiture et transport collectif, et les 58 déplacements qui mêlent vélo et transport collectif. Une part de la cible est ainsi hors d'atteinte par construction.
<!-- source: docs/tickets/ticket_049_itineraire_mixte_limite_a_publier.md, § Le fait ; microdonnées EMC² 2023, pondération COEP, déplacements internes au périmètre -->

L'amplitude de cette part se lit par strate, et non globalement. Sur l'ensemble du bassin, le rabattement pèse 1,41 point de part modale. Rapportée à la cible des transports collectifs de chaque couronne, la fraction inatteignable est de 3 % à Toulouse, 22 % en première couronne, 31 % en deuxième et 28 % en troisième. Par tranche de distance, elle atteint 39 % entre 10 et 20 km, 59 % entre 20 et 50 km et 64 % au-delà. Les déplacements concernés ont une médiane de 11,1 km contre 1,9 km pour l'ensemble, relèvent du retour au domicile pour 42 % et du travail fixe pour 14 %, et 3,1 % des personnes mobiles en déclarent au moins un.
<!-- source: idem, § L'amplitude, par strate -->

Le sens dans lequel cette limite joue a été mesuré sur dix-sept exécutions archivées, soit environ 50 000 déplacements. La simulation sur-produit les transports collectifs là où la cible est la plus inatteignable : entre 20 et 50 km, les trois modèles de langue placent 27 à 36 % de la masse de probabilité en transports collectifs pour une cible de 13 %, et au-delà de 50 km, 42 à 47 % pour une cible de 12 %. Neutraliser la borne de rabattement dans le score ne rapporte rien aux trois modèles de langue, à 0,000 point, quand elle rapporte 2,17 à 2,19 points aux planchers de durée minimale et de tout-voiture, et de 0,00 à 0,17 point aux quatre méthodes tabulaires.
<!-- source: docs/traces/2026-09-12_10-10_sens_limite_rabattement/ ; parts par tranche : gemini-38-f 36 % et 47 %, gemini-31-fl 33 % et 42 %, gemini-35-fl 27 % et 43 % -->

Le composite ne compare pas des parts par tranche mais des profils de distance. Dans cette lecture, retirer le rabattement de la cible raccourcit le profil de référence des transports collectifs et l'éloigne d'une simulation déjà trop ferroviaire : la correction dégraderait le score des modèles de langue au lieu de le laisser inchangé. La limite décrite ici ne pèse aujourd'hui sur aucune des conclusions du chapitre 6, et sa neutralisation rapprocherait les décideurs évalués de leurs planchers.

## 8.2 La chaîne des véhicules, l'horizon de décision et le parc du ménage

Le suivi de la position des véhicules personnels pose deux verrous de nature différente. Le verrou de retour impose de rentrer avec le véhicule sorti le matin, et il reproduit une régularité du terrain : dans l'enquête, 98,5 % des retours au domicile d'une chaîne automobile commencée le matin se font en voiture, et 93,8 % pour le vélo. Ces retours contraints pèsent 18,2 % des déplacements dans l'enquête et 18,0 % dans la journée simulée, sans qu'aucun réglage ait visé cette valeur.
<!-- source: docs/tickets/ticket_057_audit_et_reflexion_double_lecture_tabulaire.md, § 2.3 -->

Le verrou de sortie retire l'option de conduire à un déplacement qui part d'un lieu où le véhicule n'est pas garé, et il joue quatre fois plus souvent que dans la réalité. Cette situation touche 4,2 % des déplacements de conducteur dans l'enquête. Sur une seule et même cohorte, elle en touche 13,8 à 15,4 % sous prompt expert, 17,7 à 18,0 % pour les quatre méthodes tabulaires, 18,7 à 18,9 % sous prompt minimal et 30,9 % au plancher aléatoire. Le taux s'ordonne selon le décideur seul, ce qu'un défaut de la règle ou de la population synthétique ne produirait pas : il mesure le coût de décider un déplacement sans regarder la suite de la journée, et la consigne calibrée le paie moins que les modèles ajustés sur l'enquête. Aucun décideur ne rejoint le niveau du terrain.
<!-- source: idem, § 2.3, tableau par décideur -->

La disponibilité du parc automobile du ménage est approchée par une règle qui attribue un véhicule à tout adulte motorisé titulaire du permis, sans tenir le compte des voitures déclarées par le foyer. Sur les 499 ménages de la cohorte scellée, 90 comptent plus de conducteurs que de véhicules, ce qui rend 268 personas éligibles à une circulation concurrente. Le remplacement de leurs décisions par celles prises sous offre complète déplace la part de voiture de 52,0 à 53,2 % pour une cible de 55,9 %, dégrade la stratification, et coûte 0,073 point de composite. Cette valeur se situe dix-huit fois sous la résolution de l'instrument, qui est de 1,3 point par décideur.
<!-- source: idem, § 6 et § 7 ; résolution : § 4.1 -->

Les quatre méthodes tabulaires ont lu 39 203 déplacements réels de l'enquête locale, et l'agent n'en a lu aucun. Le contrat d'évaluation déclare ce déséquilibre au lieu de revendiquer une parité d'information : la parité porte sur la description du déplacement courant, et l'agent reçoit en plus son agenda et la météo des tranches à venir. Ce que le dispositif établit est qu'un agent fait quelque chose qu'un classifieur trajet par trajet ne peut pas faire, et non qu'il fasse mieux à information égale.
<!-- source: docs/tickets/ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation.md, arbitrage du 2026-09-17 ; § 4.3, règle 1 -->

La renormalisation de la distribution tabulaire sur les seuls itinéraires viables repose enfin sur l'hypothèse d'indépendance des alternatives non pertinentes. Retirer un mode physiquement indisponible et recalculer la masse sur les modes restants suppose que le rapport des probabilités entre deux modes conservés ne dépend pas du mode retiré, ce que le logit multinomial vérifie par construction et que les trois autres méthodes ne garantissent pas.

## 8.3 Ce que coûte une journée simulée

Une journée de semaine sur 1 000 personas produit 3 299 déplacements, dont 3 161 exploitables et 3 154 décidés. Les 702 déplacements qui n'offrent qu'un itinéraire ne donnent lieu à aucun appel, et la journée de référence en demande 2 108, une exécution sans réemploi d'une journée antérieure en demandant de l'ordre de 2 500. Un appel de décision porte de 4 100 à 5 200 tokens d'entrée selon le modèle et la variante de consigne : la personne, la météo, les contraintes de chaîne et le détail de six itinéraires au plus. La sortie va de 1 100 à 6 000 tokens, l'écart tenant à la trace de raisonnement, facturée hors du plafond de complétion pour les modèles qui en produisent une. La journée de référence consomme ainsi 23 millions de tokens.
<!-- source: docs/traces/2026-09-17_11-26_cout_inference_chapitre8/ — compteurs.json de exp_gemini-35-fl_proexp05_…_t0 exécution 2026-09-15_07_02_03 ; coût par appel agrégé sur 142 journaux llm_exchanges.jsonl : gemini-3.5-flash-lite expert 4 907 en entrée et 5 952 en sortie, gemini-3.1-flash-lite 4 189 et 1 192, mistral-large-3 4 124 et 1 134 -->

Les expériences d'ablation tournent mémoire désactivée, et ce budget ne couvre donc aucune consolidation. Une consolidation courte demande 4 383 tokens d'entrée et 1 341 de sortie, une auto-réflexion multi-jours 3 177 et 469. Sur les runs qui activent la mémoire, un agent en déclenche 1,25 et 0,27 par jour simulé. Rapporté aux 894 personas mobiles de la cohorte, une journée à mémoire active ajouterait environ 7 millions de tokens.
<!-- source: idem ; fréquences mesurées sur experiments/archive/2026-09-16_15_58, 5 personas et 11 jours simulés ; 894 mobiles : MANIFEST.yaml, 106 immobiles sur 1 000. Une consolidation se déclenche pour tout agent qui a vécu la journée, d'où les 894 mobiles et non les 868 personnes que le § 6 et l'annexe comptent : ces 868 portent au moins une décision retenue, les 26 autres n'ayant que des déplacements à origine et destination confondues. Vérifié sur decisions.jsonl de l'exécution 2026-09-15_07_02_03 : 894 personnes présentes, 868 avec une décision retenue. -->

Le passage au périmètre d'enquête change d'ordre de grandeur. Les 453 communes comptent 1 320 000 habitants de 5 ans et plus, soit 4,36 millions de déplacements quotidiens au taux de 3,30 déplacements par personne mesuré sur la cohorte. Au rapport d'un appel pour 1,5 décision observé ici, une journée simulée demanderait 2,9 millions d'appels, et de 15 à 32 milliards de tokens selon que le décideur produit ou non une trace de raisonnement. Les quotas par minute et par jour des passerelles commerciales dictent déjà la durée d'exécution sur 1 000 personas, comme le rapporte le chapitre 9.
<!-- source: 1 320 000 habitants : docs/arch/perimetre-population.md ; 3,30 déplacements : MANIFEST.yaml ; le détail du calcul est dans la trace du 2026-09-17 11:26 -->

Ce coût commande de réserver la délibération en langue aux situations où elle apporte quelque chose de mesuré. Le chapitre 5 écarte pour la même raison l'optimisation combinatoire de la consigne, qui aurait demandé 80 000 inférences pour un gain marginal, et le chapitre 7 délimite les deux régimes où la délibération produit un comportement qu'aucune variable tabulée ne porte.

## 8.4 Ce que ces limites impliquent pour une architecture en cascade

Les mesures du chapitre 6 et le coût du § 8.3 mènent à une division du travail plutôt qu'à la substitution d'un paradigme à l'autre. Un premier étage déterministe élague les alternatives physiquement ou légalement impossibles, absence de permis, véhicule garé ailleurs, absence d'offre. Un second étage tabulaire traite les déplacements de routine en régime nominal, à coût nul en tokens et avec l'alignement que le § 4.4 mesure. Un troisième étage n'appelle le modèle de langue que sur rupture : incident non répertorié, information textuelle locale, retard remettant en cause l'activité suivante.

```
                         [ Déplacement à décider ]
                                     │
                                     ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ Étage 1 — Filtre déterministe                                        │
 │ Permis, véhicule garé ailleurs, absence d'offre sur le mode          │
 │ ──► retrait des alternatives impossibles                             │
 └───────────────────────────────────┬──────────────────────────────────┘
                                     │ options éligibles
                                     ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ Étage 2 — Moteur tabulaire                    part du flux : [xx] %  │
 │ Déplacement de routine, réseau nominal, aucun texte à interpréter    │
 │ ──► décision immédiate, aucun token consommé                         │
 └───────────────────────────────────┬──────────────────────────────────┘
                                     │ rupture détectée
                                     ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ Étage 3 — Décideur génératif                  part du flux : [xx] %  │
 │ Incident non répertorié, information textuelle locale, retard        │
 │ remettant en cause l'activité suivante                               │
 │ ──► délibération en langue, mise à jour de la mémoire                │
 └──────────────────────────────────────────────────────────────────────┘
```

*Figure 8.1 — Les trois étages de la cascade. Les deux parts de flux sont à construire avec les résultats : elles supposent un critère d'aiguillage explicite entre routine et rupture, et sa mesure sur la cohorte scellée.*

La part du flux que le second étage absorberait n'est pas mesurée à ce jour. Aucun compteur du dispositif ne sépare les décisions de routine des décisions de rupture, et le taux de réemploi des décisions archivées ne répond pas à cette question puisqu'il décrit une reprise d'exécution. Le chiffrage de la réduction d'appels suppose donc le critère d'aiguillage de la figure 8.1, puis son application aux 3 154 décisions de la journée de référence.

La planification à l'échelle de la journée répond au verrou de sortie du § 8.2. L'agent reçoit déjà son agenda, et ce qui lui manque est de s'engager dès le premier départ du matin sur la boucle entière, de sorte que le choix du matin porte la condition du retour. Le taux de blocage mesuré, de 13,8 à 15,4 % sous prompt expert contre 4,2 % sur le terrain, donne la grandeur que cette planification devrait réduire.

Le foyer est le seul groupe social de la simulation qui porte un identifiant stable. Sur les 499 ménages de la cohorte, 287 comptent plusieurs membres présents et 788 personas vivent avec au moins un autre agent simulé. Leurs membres diffèrent par le motif de déplacement dans 223 ménages, par le permis dans 133, par l'abonnement de transport collectif dans 122. L'arbitrage du véhicule partagé, la dépose scolaire et les courses communes relèvent d'une négociation entre personas d'un même foyer, là où le dispositif actuel alloue indépendamment.
<!-- source: docs/tickets/ticket_078_partage_de_concepts_au_sein_du_foyer.md, § 0, mesuré sur data/population/toulouse_population_1000_AAMAS_v6.json -->

La rétroaction des choix modaux sur le réseau physique reste hors du dispositif évalué, qui traite une offre d'itinéraires exogène. La brancher permettrait d'étudier comment la mémoire d'incidents et les reports d'itinéraire se composent en congestion et en occupation des transports collectifs. La distillation des traces de raisonnement vers des modèles compacts exécutables localement lèverait enfin la dépendance aux passerelles distantes que le § 8.3 chiffre, et rendrait compatibles la simulation de mobilité individuelle et le secret statistique attaché à ses données.

---

### Tickets associés à ce chapitre
- [Ticket 046](../../../tickets/ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation.md) — L'agent voit sa journée, le modèle tabulaire non : ce que déclare le contrat
- [Ticket 049](../../../tickets/ticket_049_itineraire_mixte_limite_a_publier.md) — L'itinéraire mixte n'existe pas : publier la limite, et dire dans quel sens elle penche
- [Ticket 057](../../../tickets/ticket_057_audit_et_reflexion_double_lecture_tabulaire.md) — Audit de la contrainte de chaîne, verrou de retour et verrou de sortie
- [Ticket 060](../../../tickets/ticket_060_formalisation_architecture_hybride_et_perspectives.md) — Formalisation de l'architecture hybride en cascade et perspectives
- [Ticket 078](../../../tickets/ticket_078_partage_de_concepts_au_sein_du_foyer.md) — Le foyer comme canal : ce qu'un membre apprend
- [Ticket 087](../../../tickets/ticket_087_attribution_du_nombre_de_voitures_par_menage.md) — Attribution du nombre de voitures par ménage
