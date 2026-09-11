# Ticket 035 — Spécifications testables (index)

> Dérivé de [`docs/tickets/ticket_035_plateforme_gestion_experiences_decouplage_spec_fonctionnelle.md`](../../docs/tickets/ticket_035_plateforme_gestion_experiences_decouplage_spec_fonctionnelle.md).
> Le ticket dit **ce que l'utilisateur doit pouvoir faire** ; ces specs disent **ce qui est vrai
> ou faux d'une exécution**, règle par règle, chacune vérifiable par un test qui porte son numéro.
> Aucun module, aucun format, aucune technologie n'y est fixé : le design vient après leur
> validation, dans un document séparé.

## Pourquoi six specs et pas une

Le ticket compte 45 exigences et 12 critères. Une spec au-delà de deux pages est trop large pour
être tenue par des tests ; le périmètre est donc découpé en six specs autonomes, chacune avec ses
règles, ses critères, ses non-goals et ses questions ouvertes. Les numéros de règles sont
**préfixés par spec** (J, D, S, G, Q, E) pour qu'un nom de test désigne une règle et une seule.

| Spec | Périmètre | Exigences couvertes | Critères couverts |
|---|---|---|---|
| [01 — Jeu de déplacements enregistré](01-jeu-deplacements-enregistre.md) (`J`) | Préparer, consulter, transporter, périmer, reprendre | EF-10 → EF-16, U1 | CAF-7 |
| [02 — Une seule manière de décider](02-decision-unique-eligibilite.md) (`D`) | Éligibilité, chaîne des véhicules, traçabilité du filtre, ordre | EF-20 → EF-23, RG-1, RG-7 | CAF-2, CAF-11 |
| [03 — Exécution sans simulateur](03-execution-sans-simulateur.md) (`S`) | Journée complète d'une cohorte sans GAMA, regroupement, avancement | EF-30 → EF-33, U2 | CAF-2 (volet run) |
| [04 — Simulation sur jeu enregistré](04-simulation-sur-jeu-enregistre.md) (`G`) | GAMA consomme le jeu ; recalcul sous conditions ; mémoire, événements ; pause à chaud ; chemin habituel | EF-40 → EF-48, U3, U6 | CAF-4, CAF-5, CAF-6 |
| [05 — Ressources, interruption, reprise](05-ressources-interruption-reprise.md) (`Q`) | Quotas, arrêt propre, aucune substitution, reprise sans double dépense | EF-60 → EF-63, RG-2, RG-6, U4 | CAF-3, CAF-12 |
| [06 — Expérience, registre, restitution](06-experience-registre-restitution.md) (`E`) | Configuration, empreintes, estimation, refus, calendrier, archive, registre, comparaison, couverture, référentiel | EF-01 → EF-06, EF-50 → EF-52, EF-70 → EF-77, RG-3, RG-4, RG-5, U5 | CAF-1, CAF-8, CAF-9, CAF-10 |

## Ce que l'existant impose de contredire

Quatre comportements actuels sont incompatibles avec le ticket. Les specs les nomment pour que
personne ne les prenne pour des acquis :

1. **Le filtre véhicule s'applique avant le routage.** Aujourd'hui `include_car`/`include_bike`
   entrent dans la requête OTP et dans la clé du cache de routage, et le nombre de candidats est
   plafonné à 6. Le jeu enregistré doit être calculé **sans** ce filtre et **sans** ce plafond
   (EF-12), le filtre s'appliquant à la décision (spec 02).
2. **La reprise repose sur le cache sémantique.** `make run CONT=1` rejoue la journée depuis t0
   et compte sur le cache pour ne pas repayer — un cache désactivé dans le dernier run
   (`cache.enabled: false` dans `experiments/current/static_config.yaml`), alors que la valeur par
   défaut du code le laisse actif.
   La reprise doit s'appuyer sur les **décisions archivées de l'exécution** (spec 05), pas sur une
   mémoire technique dont l'utilisateur n'a pas à connaître l'existence (EF-11).
3. **La passerelle cascade d'un fournisseur à l'autre.** Un provider épuisé est écarté et le lot
   part sur un autre modèle. Pour une expérience, c'est une substitution silencieuse (EF-62) : le
   décideur est épinglé (spec 05).
4. **La maquette porte des valeurs de référence inexistantes.** Ses 51,2 / 18,4 / 22,8 / 7,6 %
   n'apparaissent nulle part ; la source de vérité `scripts/data/population/cerema_values.yaml`
   dit 55 / 12 / 26 / 4. Aucune valeur de référence n'entre dans la plateforme (spec 06, EF-77).

## Dépendances entre specs

- 02 ne dépend de rien : la logique de décision unique se vérifie sur le code actuel.
- 01 dépend de 02 pour définir ce qu'est une proposition « brute » (avant filtre).
- 03 et 04 consomment 01 et 02 ; 04 dépend de plus de 05 pour la pause.
- 06 archive ce que 03 et 04 produisent ; 05 s'applique aux deux.

## Points à trancher avant de coder

La méthode est stricte : **une question ouverte non tranchée, et l'on ne code pas la spec qui la
porte.** Les sept points du ticket (§7) sont répartis ainsi, complétés de ceux que la rédaction a
fait apparaître :

| Point | Spec | Bloque |
|---|---|---|
| 1. Unité de sollicitation du décideur (par déplacement / par personne-journée) | 03, 06 | l'estimation de coût, la comparabilité, le format des réponses archivées |
| 2. Statut du jeu (artefact scellé / objet régénérable) | 01 | la règle de péremption, ce qui est cité dans les résultats |
| 3. Que faire d'un jeu incomplet | 01, 03 | le refus ou l'acceptation au lancement, la couverture affichée |
| 4. Granularité de la reprise à chaud | 04 | ce qui est sauvegardé à la pause |
| 5. Ce que « à chaud » recouvre | 04, 05 | idem, plus ce qu'on accepte de perdre |
| 6. Regroupement figé pour comparer deux décideurs | 03, 06 | la règle de comparabilité |
| 7. Réplication (n exécutions d'une même expérience) | 06 | le modèle du registre |
| 8. *(nouveau)* Seuils de tolérance horaire par mode pour le recalcul | 04 | la règle EF-44 |
| 9. *(nouveau)* Un jeu enregistré porte-t-il aussi les propositions des déplacements du lendemain que la simulation pré-calcule ? | 01, 04 | la couverture d'un jeu, le régime « zéro recalcul » |
| 10. *(nouveau)* Horizon > 1 jour sans simulateur : refusé, ou D journées indépendantes ? | 03 | le refus EF-06 |
