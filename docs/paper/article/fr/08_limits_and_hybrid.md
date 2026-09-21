# 8. Limites

<!-- Dernière mise à jour : 2026-09-21 -->

**Document :** brouillon français du chapitre.
**Statut :** `brouillon v0.3` (21 septembre 2026) — le § 8.6 est ajouté au titre du [ticket 074](../../../tickets/ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md) : le dispositif s'exécute en anglais, ce que le § 4.1 justifie, et le biais occidental-centré que l'anglais induit n'a reçu aucune contre-mesure, le renforcement du cadrage territorial ayant été écarté pour ne changer qu'une variable. La limite est déclarée et la part d'écart qui lui revient n'est pas chiffrée. Une référence entre au chapitre, Soegeng et al. (2026).
**Statut antérieur :** `brouillon v0.2` (21 septembre 2026) — le § 8.5 est ajouté au titre du ticket 051 : les deux registres de la mémoire partagent un index unique, le décideur qu'on évalue tient lui-même le registre sémantique, et le critère d'aiguillage que la figure 8.1 laisse vide est rapporté à la mesure de l'habitude. Aucune référence bibliographique n'est ajoutée : l'ancrage de la distinction automatisme / délibération vit dans `docs/arch/memory-stm-ltm.md`, sa notice n'étant pas recoupée.
**Statut antérieur :** `brouillon v0.1` (17 septembre 2026) — première rédaction. Le texte antérieur, extrait du § 6 du manuscrit de septembre, exposait une cascade hybride et un tableau comparatif dont trois cellules sur cinq restaient à mesurer et dont deux chiffres ont depuis été retirés du chapitre 9 faute de source ; il est remplacé, et le tableau ne revient pas. Les limites que le chapitre publie viennent des tickets 049 et 057, le coût d'inférence d'une mesure du 17 septembre 2026. La figure 8.1 porte la cascade ; ses deux parts de flux sont des emplacements **[xx]**, à remplir quand un critère d'aiguillage aura été défini et mesuré.
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

Les quatre méthodes tabulaires ont lu 39 203 déplacements réels de l'enquête locale, et l'agent n'en a lu aucun. Le protocole de comparaison déclare ce déséquilibre au lieu de revendiquer une parité d'information : la parité porte sur la description du déplacement courant, et l'agent reçoit en plus son agenda et la météo des tranches à venir. Ce que le dispositif établit est qu'un agent fait quelque chose qu'un classifieur trajet par trajet ne peut pas faire, et non qu'il fasse mieux à information égale.
<!-- source: docs/tickets/ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation.md, arbitrage du 2026-09-17 ; § 4.3, règle 1 -->

La renormalisation de la distribution tabulaire sur les seuls itinéraires viables repose enfin sur l'hypothèse d'indépendance des alternatives non pertinentes. Retirer un mode physiquement indisponible et recalculer la masse sur les modes restants suppose que le rapport des probabilités entre deux modes conservés ne dépend pas du mode retiré, ce que le logit multinomial vérifie par construction et que les trois autres méthodes ne garantissent pas.

## 8.3 Ce que coûte une journée simulée

Une journée de semaine sur 1 000 personas produit 3 299 déplacements, dont 3 161 exploitables et 3 154 décidés. Les 702 déplacements qui n'offrent qu'un itinéraire ne donnent lieu à aucune sollicitation du modèle, et la journée de référence en demande 2 108, une exécution sans réemploi d'une journée antérieure en demandant de l'ordre de 2 500. La passerelle en groupe huit par requête, et la journée tient en quelque 270 requêtes. Une décision porte de 620 à 840 tokens d'entrée selon le modèle et la variante de consigne : la personne, la météo, les contraintes de chaîne et le détail de six itinéraires au plus, le préambule commun étant amorti sur tout le lot. La sortie va de 190 à 790 tokens, l'écart tenant à la trace de raisonnement, facturée hors du plafond de complétion pour les modèles qui en produisent une. La journée de référence consomme ainsi 3 millions de tokens.
<!-- source: docs/traces/2026-09-21_13-10_cout_jev_vs_gemini/ — erratum de la trace du 2026-09-17 11:26, qui agrégeait par requête HTTP et non par décision ; compteurs.json de exp_gemini-35-fl_proexp05_…_t0 exécution 2026-09-15_07_02_03 pour les 2 108 sollicitations ; jetons par décision agrégés sur les journaux llm_exchanges.jsonl depuis le 2026-09-14, le nombre d'agents étant lu dans chaque réponse : gemini-3.5-flash-lite expert 646 en entrée et 790 en sortie, gemini-3.1-flash-lite 839 et 204, mistral-large-3 695 et 191 ; lot moyen de 7,9 agents par requête pour gemini-3.5, 4,0 pour gemini-3.1, 5,9 pour mistral-large-3. Mesure directe sur un bras complet, sans produit : 2 442 décisions, 309 requêtes, 3,40 M de tokens -->

Les expériences d'ablation tournent mémoire désactivée, et ce budget ne couvre donc aucune consolidation. Une consolidation courte demande 1 292 tokens d'entrée et 388 de sortie, une auto-réflexion multi-jours 2 313 et 335. Sur les runs qui activent la mémoire, un agent en déclenche 1,25 et 0,27 par jour simulé. Rapporté aux 894 personas mobiles de la cohorte, une journée à mémoire active ajouterait environ 2,5 millions de tokens.
<!-- source: idem, jetons par consolidation et non par requête, les lots valant en moyenne 3,28 et 1,37 ; fréquences mesurées sur experiments/archive/2026-09-16_15_58, 5 personas et 11 jours simulés ; 894 mobiles : MANIFEST.yaml, 106 immobiles sur 1 000. Une consolidation se déclenche pour tout agent qui a vécu la journée, d'où les 894 mobiles et non les 868 personnes que le § 6 et l'annexe comptent : ces 868 portent au moins une décision retenue, les 26 autres n'ayant que des déplacements à origine et destination confondues. Vérifié sur decisions.jsonl de l'exécution 2026-09-15_07_02_03 : 894 personnes présentes, 868 avec une décision retenue. -->

Le passage au périmètre d'enquête change d'ordre de grandeur. Les 453 communes comptent 1 320 000 habitants de 5 ans et plus, soit 4,36 millions de déplacements quotidiens au taux de 3,30 déplacements par personne mesuré sur la cohorte. Au rapport d'une sollicitation pour 1,5 décision observé ici, une journée simulée demanderait 2,9 millions de sollicitations, soit quelque 370 000 requêtes, et de 2,6 à 4,2 milliards de tokens selon que le décideur produit ou non une trace de raisonnement. Les quotas par minute et par jour des passerelles commerciales dictent déjà la durée d'exécution sur 1 000 personas, comme le rapporte le chapitre 9.
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

## 8.5 Les deux registres de la mémoire partagent un seul magasin

La mémoire longue distingue les traces vécues des concepts par leur régime d'oubli et non par leur magasin. Les deux registres vivent dans le même index vectoriel par agent, avec le même plongement et le même chemin de rappel ; ce qui les sépare est un attribut de l'entrée, qui commande la composante temporelle du score de rappel : une décroissance depuis le dernier rappel pour une trace, une confiance issue du compte des confirmations et des contre-exemples pour un concept. Un magasin sémantique propre, indexé pour lui-même et tenu par inférence sur les observations plutôt que par une horloge, est une autre architecture, et le dispositif évalué ici ne la met pas à l'épreuve.
<!-- source: services/llm-agents/llm/longterm.py, branche est_episodique du score temporel ; llm/concepts.py, confiance() ; collection ChromaDB unique « memory_collection » -->

Le registre sémantique est en outre tenu par le décideur qu'on évalue. À chaque consolidation, le modèle voit les concepts voisins du couple mode-motif concerné et désigne celui qu'il crée, confirme, précise ou contredit ; cette désignation remplace un seuil de similarité fixe, dont aucune valeur n'est mesurée sur le plongement employé, mais elle fait dépendre la tenue de la mémoire de la même politique que la décision. Un décideur qui traite mal ces quatre opérations dégrade sa propre mémoire, et rien dans le protocole du chapitre 5 ne sépare les deux effets.
<!-- source: docs/arch/memory-stm-ltm.md, lot 3 ; docs/tickets/ticket_071_evolution_memoire_du_code_actuel_a_l_etat_vise.md, § 2.3 -->

Le critère d'aiguillage que la figure 8.1 laisse vide est celui de l'habitude. Aucune règle n'impose à un agent de reprendre le mode de la veille : la répétition, quand elle apparaît, vient du rappel de ses propres trajets. Son installation est donc une grandeur observable, la décroissance de l'entropie des choix d'un même agent au fil des jours simulés, et les cinq jours du § 7.2 en fournissent la fenêtre. Coder l'automatisme avant de l'avoir mesuré produirait la routine au lieu de l'observer, et priverait le second étage de la cascade du critère qui le déclenche.
<!-- source: docs/tickets/ticket_051_reflexion_architecture_cognitive_memoire.md, § C ; ticket 071 § 2.9, arbitrage de l'auteur des 2026-09-11 et 2026-09-14 -->

## 8.6 Le dispositif s'exécute en anglais sans renforcement du cadrage territorial

Le prompt système, le gabarit de rendu et les traits de la cohorte sont en anglais, et la consigne n'ancre le territoire que par la mention de la ville. Prompter en anglais donne la meilleure performance générale mais induit un biais occidental-centré : la connaissance culturelle est présente dans les représentations en langue locale et mal récupérée depuis l'anglais (Soegeng et al., 2026). Étoffer le cadrage de la consigne, par l'armature urbaine, l'opérateur de transport et des ordres de grandeur locaux, était le levier disponible contre ce biais ; il a été écarté pour que le passage à l'anglais ne change qu'une variable et reste attribuable. La part de l'écart au territoire du chapitre 6 qui revient à ce biais n'est donc pas chiffrée : aucune exécution en français ne porte sur le jeu qui fonde ces mesures.
<!-- source: docs/tickets/ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md, § 3.3 et arbitrage Q3 du 2026-09-14 ; la justification de l'anglais est au § 4.1 -->

---

### Tickets associés à ce chapitre
- [Ticket 046](../../../tickets/ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation.md) — L'agent voit sa journée, le modèle tabulaire non : ce que déclare le protocole
- [Ticket 049](../../../tickets/ticket_049_itineraire_mixte_limite_a_publier.md) — L'itinéraire mixte n'existe pas : publier la limite, et dire dans quel sens elle penche
- [Ticket 051](../../../tickets/ticket_051_reflexion_architecture_cognitive_memoire.md) — Réflexion et audit épistémologique de l'architecture mémoire : le § 8.5 en porte la prospective, et l'habitude s'y mesure au lieu d'être codée
- [Ticket 057](../../../tickets/ticket_057_audit_et_reflexion_double_lecture_tabulaire.md) — Audit de la contrainte de chaîne, verrou de retour et verrou de sortie
- [Ticket 060](../../../tickets/ticket_060_formalisation_architecture_hybride_et_perspectives.md) — Formalisation de l'architecture hybride en cascade et perspectives
- [Ticket 074](../../../tickets/ticket_074_bascule_anglaise_archivage_et_reprise_de_campagne.md) — Bascule du dispositif en anglais : le § 8.6 porte le biais qu'elle induit et l'absence de contre-mesure
- [Ticket 078](../../../tickets/ticket_078_partage_de_concepts_au_sein_du_foyer.md) — Le foyer comme canal : ce qu'un membre apprend
