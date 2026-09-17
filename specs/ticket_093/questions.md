# Ticket 093 — Questions vivantes

Ce que j'ai tranché seul pour avancer, et ce qui reste à confirmer. Rien ici n'est bloquant :
chaque point porte l'hypothèse retenue et ce qu'il faudrait changer si la réponse diffère.

## Tranché avec l'auteur avant l'écriture (2026-09-16)

1. **« Durée de vie médiane par type de souvenir » = médiane du champ `force`**, la constante de
   temps de l'oubli en jours. C'est la seule grandeur du modèle qui soit littéralement une durée
   de vie. L'alternative — l'âge au moment de la purge — ne produirait presque rien : `est_purgeable`
   ne déclenche qu'à ~4,6 × force, donc jamais sur un run de dix jours.
2. **Activation par réglage explicite**, éteint par défaut, allumé par la cible de run mémoire.
   Pas d'activation implicite selon la taille de la population.
3. **La population produite est versionnée**, comme l'est `population_5_memoire_075` : le script
   reste la source, le fichier est le résultat gelé.

## Tranché par l'auteur le 2026-09-16, à la relecture du contrat

4. **Plusieurs trajets d'une même activité le même jour.** Hypothèse retenue (C10) : le mode du
   jour pour cette activité est celui du **premier départ**, et le nombre d'occurrences est écrit
   à côté. Le cas est rare mais il existe ; en prendre le dernier, ou compter chaque occurrence
   comme une observation d'habitude distincte, donnerait des taux légèrement différents. Validé
   par l'auteur ; à rouvrir seulement si le cas se révèle fréquent sur un run réel.

5. **Seuil minimal de jours observés pour une conformité à l'habitude.** Hypothèse retenue : aucun
   seuil dans le CSV — la mesure est écrite dès qu'un jour antérieur existe, et `jours_observes`
   est écrit à côté pour que l'analyse filtre elle-même. Le tableau de bord, lui, n'affiche la
   série qu'à partir de trois observations. Poser un seuil dans le CSV reviendrait à décider à la
   place de l'analyse. Validé par l'auteur.

6. **Fenêtre de l'habitude : 5 jours OBSERVÉS.** Tranché par l'auteur le 2026-09-16. La fenêtre
   porte sur les cinq derniers jours où **cette activité** a été observée, et saute les trous :
   un agent qui ne sort qu'un jour sur trois a la même profondeur d'habitude que les autres,
   simplement étalée sur plus de jours. L'alternative — cinq jours simulés — aurait donné à cet
   agent une fenêtre creuse de une ou deux observations, donc une conformité bruitée qui aurait
   dit son assiduité plutôt que son habitude.

## Ouvert — constaté en produisant la population (2026-09-16)

7. **Le critère sélectionne une population sociologiquement homogène, et il faut le dire.**
   Les dix retenus sont **dix femmes**, dont cinq « Unemployed / job seeker » et aucune
   « Full-time worker » hors `861500`. Ce n'est pas un défaut du code : c'est la conséquence
   directe du critère. Faire beaucoup de trajets, variés, avec un vrai choix de modes, c'est le
   quotidien de qui n'a pas d'horaires fixes — un pendulaire motorisé fait deux trajets et n'a
   pas le choix, ce qui est exactement pourquoi `609` est écarté.

   Deux lectures, et elle est à l'auteur :
   - **On assume.** Ces dix agents ne représentent rien, le MANIFEST le dit déjà, et l'objet est
     d'observer un mécanisme de mémoire, pas une population.
   - **On contraint.** Ajouter au tourniquet une couverture des occupations, comme il couvre
     déjà les modes. Le critère resterait mesurable, la sélection resterait scriptée, et la
     population gagnerait en variété — au prix de retenir des agents moins observables.

   **Tranché par l'auteur le 2026-09-16 : sans importance à ce stade, ces dix agents servent à
   mettre au point l'instrumentation.** Le tourniquet ne couvre donc que les modes. À rouvrir si
   cette population devait un jour porter autre chose qu'une mise au point.

## Deux défauts trouvés en mesurant, hors périmètre du ticket (2026-09-16)

8. **Le rejeu d'une reprise écrase les points de reprise des journées déjà vécues.**
   Mesuré sur `2026-09-16_15_58` : les points `jour_002` à `jour_009` portent tous exactement le
   même contenu — 101 entrées, mêmes compteurs par agent — écrits entre 17 h 42 et 18 h 20 en
   temps réel, c'est-à-dire pendant le rejeu, mémoire gelée. L'historique d'évolution de la
   mémoire sur les huit premières journées est **perdu pour ce run**, et c'est précisément la
   courbe que le ticket veut produire (« 11 candidats au jour 1, 26 au jour 10 »).

   Parade posée ici : une mesure d'état écrite une fois n'est jamais réécrite, donc les runs à
   venir gardent ce qu'ils ont vu au moment où ils l'ont vu. Cela ne répare pas le passé, et cela
   ne corrige pas la cause — `_ecrire_point_de_reprise` devrait refuser d'écraser un point
   existant pendant un gel. **Ticket à ouvrir**, il touche le 075/091 et pas celui-ci.

9. **Rien ne relie un choc au souvenir qu'il produit, et l'appariement par texte échoue.**
   Le vécu injecté — « The engine made a grinding noise and the car stalled twice » — n'est jamais
   recopié tel quel : il passe en mémoire courte, puis la réflexion le REFORMULE (« my car started
   making a terrible grinding noise »). Chercher le texte littéral ne rend aucun identifiant.
   `scripts/analysis/memoire/choc.py` a le même angle mort depuis le ticket 079 : sa figure
   « le souvenir du choc a-t-il été servi » ne peut pas répondre.

   Parade posée ici : quand aucun souvenir n'est appariable, la colonne est **vide** et jamais
   `faux` — écrire « non servi » ferait lire « le souvenir du choc n'a jamais pesé sur une
   décision », qui est justement la conclusion que le ticket cherche à établir.

   Le lien doit être posé à la source : un `choc_id` porté par l'entrée de mémoire courte et
   propagé à la réflexion qui la consomme. C'est de la traçabilité, pas une règle de mémoire —
   mais cela touche la chaîne de consolidation, donc **à l'auteur de dire** si cela entre dans ce
   ticket ou dans un ticket propre.
