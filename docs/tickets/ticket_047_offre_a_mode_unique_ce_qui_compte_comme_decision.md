# Ticket 047 — Une offre à mode unique n'est pas une décision : où la compter, où l'exclure

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-11 à la demande de l'auteur, **rien n'est lancé**.
>
> **Ce ticket tranche une convention de mesure, il ne corrige pas un défaut.** Le mécanisme qui
> produit ces situations — la cohérence de chaîne des véhicules — est voulu et reste en place.
>
> Sorti du [ticket 045](ticket_045_substrat_unique_v5_et_reconstruction_des_experiences.md), où il
> était l'alerte A5, pour être traité à part. **Bloque** la publication des parts modales par bras
> tant que la convention n'est pas écrite.

## Le fait

Quand un seul itinéraire est proposé, le décideur n'est pas interrogé : le mode est celui de
l'unique option. Le modèle de langue, l'oracle et le tirage au sort produisent alors **le même
résultat**, sans qu'aucune préférence n'ait été exprimée.

Deux grandeurs traitent ces lignes différemment, et aucune des deux n'a tort :

| Grandeur | Traitement actuel | Raison |
|---|---|---|
| Parts modales publiées par la plateforme | **comptées** | un déplacement contraint est un déplacement de la journée ; une journée réelle en comporte |
| Termes d'accord du score à deux oracles | **écartées et comptées** | mesurer un accord là où personne n'a décidé fait *baisser* la perte sans rien mesurer |

Le problème n'est donc pas le traitement, c'est qu'il n'est **écrit nulle part** et qu'il diffère
d'une grandeur à l'autre sans que le lecteur en soit averti.

## Ce qui rend la question non triviale

**Le compte dépend du décideur.** Ces situations naissent des choix antérieurs de la journée :
prendre la voiture le matin impose de rentrer en voiture le soir. Mesuré sur les exécutions
complètes du 11 septembre, à population et jeu identiques, le nombre de décisions à itinéraire
unique va de **[xx]** (tirage uniforme) à **[xx]** (plus rapide), soit **[xx] %** à **[xx] %** de
la journée selon le bras.

Deux conséquences :

- une part de l'écart entre bras vient de la divergence des offres, non des règles de décision ;
- ces lignes, identiques pour tous, **compriment** les écarts qu'on cherche à mesurer.

**Et c'est le motif récurrent du dépôt.** L'absence de mesure y produit le score parfait : une offre
à mode unique, une strate vide, une marge non mesurable, un repli compté comme une décision. Une
métrique qui ne se protège pas de ce cas mesure sa propre vacuité.

## Ce qu'il faut faire

1. **Inventorier** toutes les grandeurs publiées — parts modales, erreur L1, composite, exactitude
   unitaire, rappel par mode, termes d'accord — et, pour chacune, dire si une offre à mode unique y
   entre, et pourquoi. Une ligne par grandeur, pas de cas laissé implicite.
2. **Trancher la convention** et l'écrire dans [`docs/arch/score-synthesis.md`](../arch/score-synthesis.md).
   Proposition à l'ouverture : les grandeurs qui décrivent **ce qui a eu lieu** (parts modales)
   comptent ces lignes ; les grandeurs qui décrivent **ce qui a été décidé** (accord, exactitude
   attribuée au décideur) les écartent.
3. **Publier les deux lectures** des parts modales — toutes décisions, et hors itinéraire unique —
   et le **compte par bras** à côté du chiffre. Sans le compte, les deux lectures ne se raccordent
   pas.
4. **Le dire dans l'article**, en une ou deux phrases au chapitre 4, sans y installer le raisonnement
   complet : le chapitre annonce la convention, ce ticket la porte.

## Hors périmètre

- La contrainte de chaîne elle-même : c'est le cadre de la simulation, et le 2×2 chaîne / sans
  chaîne du [ticket 045](ticket_045_substrat_unique_v5_et_reconstruction_des_experiences.md).
- L'asymétrie d'information entre agent et modèle tabulaire :
  [ticket 046](ticket_046_asymetrie_informationnelle_du_contrat_d_evaluation.md).
- Le filtre d'éligibilité des modes et son ablation : [ticket 040](ticket_040_ablation_filtre_eligibilite_modes.md).

## Questions ouvertes

1. L'exactitude unitaire d'un bras doit-elle exclure ces lignes ? Les compter gonfle l'exactitude de
   tous les décideurs du même montant, mais pas dans les mêmes proportions selon le bras.
2. La couverture publiée doit-elle être rapportée aux déplacements du périmètre ou aux seules
   décisions réellement prises ? Les deux dénominateurs circulent aujourd'hui.
