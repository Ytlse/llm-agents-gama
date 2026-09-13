# Ticket 035 — Spécification fonctionnelle : gestion des expériences, déplacements enregistrés, conduite de la simulation

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
>
> **Ce document dit ce que l'utilisateur doit pouvoir faire, et rien d'autre.** Pas de modules,
> pas de formats, pas de technologies, pas de découpage en lots : le design vient après, et
> dans un document séparé. Il remplace la partie « expression du besoin » d'une première version
> de ce ticket, non conservée, qui était partie trop vite dans la solution — et qui, ce faisant,
> avait recopié des valeurs de référence et des seuils d'acceptation qui n'appartiennent pas à
> cette plateforme.
>
> **Specs testables dérivées de ce ticket** : [`specs/ticket_035/00-index.md`](../../specs/ticket_035/00-index.md)
> (six specs, 86 règles numérotées, chacune avec son critère d'acceptation ; les points à trancher du
> §7 y sont repris et complétés — rien ne se code tant qu'ils sont ouverts).

---

## 1. Le constat

Lancer une expérience, aujourd'hui, c'est lancer **un run**. On choisit une population, on
démarre la chaîne, et le calcul des itinéraires se fait **au fil de la journée simulée** :
pour chaque déplacement, les moteurs de routage produisent les options, le décideur en retient
une, l'agent se déplace, et le déplacement suivant repart de là. Trois conséquences.

**Le calcul d'itinéraires est refait à chaque expérience alors qu'il ne dépend pas de ce qu'on
teste.** Changer de modèle, changer de gabarit de prompt, rejouer le même jour : les options
proposées sont pourtant les mêmes. Le coût est payé une fois par expérience au lieu d'une fois
par population.

**Ce qui dépend vraiment de la décision précédente, c'est un filtre, pas un calcul.** Une
personne ne prend sa voiture que si sa voiture est là où elle est ; son vélo de même. Cette
contrainte élimine des options — elle n'en crée aucune. Elle peut donc s'appliquer *après*,
sur un catalogue préparé à l'avance, au lieu d'imposer que le catalogue soit produit en vol.

**Le simulateur n'est pas toujours nécessaire.** Il l'est quand l'expérience porte sur la
mémoire des agents, sur un incident vécu, sur les effets de trajectoire — et il le sera quand
les agents se parleront. Il ne l'est pas quand la question tient dans « quelles options a-t-on
proposées, et qu'a répondu le décideur ». Une part des expériences n'a besoin que de la chaîne
de propositions et des réponses.

À cela s'ajoute ce qui manque en propre : on ne sait pas retrouver ce qui a été lancé, on ne
sait pas comparer deux exécutions qui ne diffèrent que par le modèle, et on ne sait pas
s'arrêter puis reprendre — ni quand le quota d'un fournisseur est épuisé, ni parce qu'on a
décidé de faire autre chose de sa machine.

---

## 2. Vocabulaire

Ces termes sont employés au sens strict dans tout le document.

| Terme | Sens retenu |
|---|---|
| **Population** | Un ensemble de personnes avec leurs attributs et leur agenda d'activités de la journée. Une population *scellée* est une population qui porte en plus une empreinte et un rapport de conformité ; ce n'est pas une catégorie à part, c'est une population avec un sceau. |
| **Déplacement** | Un trajet d'une personne entre deux activités : une origine, une destination, une heure programmée. |
| **Proposition** | Une manière concrète d'effectuer un déplacement : un mode, un itinéraire, une durée, et ce qui la décrit au décideur. |
| **Jeu de déplacements enregistré** | L'ensemble des propositions préparées à l'avance pour tous les déplacements d'une population. Un objet **nommé, daté, transportable** — pas un cache technique (cf. EF-11). |
| **Décideur** | Ce qui choisit une proposition : un modèle de langage distant ou local, un modèle supervisé, ou une heuristique. |
| **Gabarit de prompt** | Le texte qui met en forme la question posée au décideur, lorsque le décideur est un modèle de langage. |
| **Mode d'exécution** | *Sans simulateur* ou *avec simulateur*. |
| **Expérience** | Une configuration complète et nommée : population, jeu de déplacements, gabarit, décideur, mode, calendrier, horizon, options de mémoire et d'événements. |
| **Exécution** | Le fait de dérouler une expérience une fois. Une expérience peut avoir plusieurs exécutions (reprise, réplication). |
| **Résultat** | Ce que produit une exécution : les décisions prises, ce qui les a précédées, et de quoi les relire. |
| **Registre** | La liste de toutes les expériences, de leur état et de leurs résultats. |

---

## 3. Ce que l'utilisateur doit pouvoir faire

Six situations, dans l'ordre où elles se présentent.

**U1 — Préparer une population.** Je choisis une population et je demande que tous les
scénarios de déplacement de sa journée soient calculés à l'avance, une bonne fois. Le calcul
peut durer longtemps ; il tourne sans moi. À l'arrivée j'obtiens un jeu de déplacements
enregistré que je peux consulter, garder, déplacer sur une autre machine, et réutiliser
d'une expérience à l'autre.

**U2 — Comparer deux décideurs sans simulateur.** Je choisis une population et son jeu de
déplacements, un gabarit, un décideur, une journée. Je lance. Je vois l'avancement. À la fin,
les résultats sont rangés et j'obtiens une page de restitution. Je relance exactement la même
expérience **en ne changeant que le décideur**, et je compare les deux.

**U3 — Faire tourner la simulation.** Même population, même jeu de déplacements, mais cette
fois avec le simulateur, sur plusieurs jours, avec la mémoire des agents activée, et
éventuellement un incident de réseau à un jour donné. C'est le seul mode qui répond aux
questions de mémoire et de trajectoire.

**U4 — M'arrêter et reprendre.** Je mets en pause parce que je veux ma machine, ou l'exécution
s'arrête d'elle-même parce qu'un quota est épuisé. Dans les deux cas, ce qui a été acquis est
conservé, et je reprends plus tard — sans refaire ce qui a déjà été fait, sans repayer les
décisions déjà obtenues.

**U5 — Retrouver et comparer.** J'ouvre le registre. Je vois toutes mes expériences, leur état,
leurs résultats principaux, et je peux trier, filtrer, ouvrir le détail de l'une d'elles
jusqu'à la décision unitaire : ce qui a été proposé à cette personne, pour ce déplacement, et
pourquoi elle a répondu cela.

**U6 — Lancer par le chemin habituel.** Je ne passe pas par la plateforme : je démarre la
simulation comme je le fais aujourd'hui, mais en désignant une population **dont les
déplacements ont déjà été enregistrés**. La simulation les consomme. La préparation à l'avance
ne doit pas être réservée à la nouvelle interface.

---

## 4. Exigences fonctionnelles

### A. Définir et identifier une expérience

- **EF-01 — Configuration complète.** L'utilisateur définit une expérience par : la population,
  le jeu de déplacements enregistré, le gabarit de prompt, le décideur, le mode d'exécution, la
  politique de calendrier, l'horizon en jours, l'activation de la mémoire, et les événements
  éventuels (incident de réseau, information extérieure portée aux agents).
- **EF-02 — Toute population est admissible.** Rien ne restreint le choix à une population
  particulière. Une population qui porte un sceau est acceptée avec son sceau ; une population
  qui n'en porte pas est acceptée aussi, et le résultat dit laquelle des deux situations
  s'appliquait.
- **EF-03 — Tout élément désigné porte son empreinte.** Population, jeu de déplacements et
  gabarit de prompt sont désignés par un nom **et** par une empreinte de leur contenu. Deux
  expériences ne peuvent être déclarées comparables que si les empreintes de ce qu'elles
  partagent sont identiques. *Les noms de gabarits cités dans les discussions autour de ce
  ticket sont des exemples : c'est l'empreinte qui identifie, pas le nom.*
- **EF-04 — Réplication.** L'utilisateur peut dupliquer une expérience existante et n'en changer
  qu'un élément, sans avoir à ressaisir le reste.
- **EF-05 — Estimation avant lancement.** Avant de valider, l'utilisateur voit ce que
  l'exécution va coûter : nombre de sollicitations du décideur, volume attendu, durée
  prévisionnelle, et part des quotas disponibles que cela représente. L'estimation est
  **dérivée des mesures du dépôt et des limites réellement configurées**, jamais d'une valeur
  fixée à la main dans la plateforme.
- **EF-06 — Refus explicite.** Une configuration impossible (jeu de déplacements ne
  correspondant pas à la population, décideur indisponible, horizon incompatible avec le mode)
  est refusée avant lancement, avec la raison et ce qu'il faudrait faire.

### B. Jeux de déplacements enregistrés

- **EF-10 — Préparation hors expérience.** L'utilisateur peut demander, pour une population
  donnée, le calcul à l'avance de toutes les propositions de tous les déplacements de la
  journée, indépendamment de toute expérience et longtemps avant elle.
- **EF-11 — Un objet, pas un cache.** Le jeu produit est un objet de premier rang : nommé,
  daté, rattaché à une population par empreinte, consultable, copiable d'une machine à l'autre,
  et réutilisable tel quel. Il ne se confond pas avec les mémoires techniques internes, dont
  l'utilisateur n'a pas à connaître l'existence.
- **EF-12 — Superset assumé.** Le jeu contient **plus** de propositions que ce qui sera présenté
  au décideur : toutes celles que les moteurs savent produire pour ce déplacement, tous modes
  confondus, sans appliquer les restrictions liées à la personne ni le plafond d'options. La
  réduction se fait au moment de l'expérience, pas au moment de l'enregistrement — c'est ce qui
  rend le jeu réutilisable par des expériences qui n'ont pas les mêmes réglages.
- **EF-13 — Consultation.** L'utilisateur peut parcourir un jeu enregistré avant de lancer quoi
  que ce soit : choisir une personne, voir ses déplacements de la journée et, pour chacun, les
  propositions retenues. C'est aussi le moyen de vérifier qu'un jeu est exploitable.
- **EF-14 — Complétude visible.** Un jeu enregistré dit combien de déplacements il couvre, pour
  combien de personnes, et lesquels sont restés sans proposition. Un jeu incomplet est
  utilisable, mais il ne peut pas se faire passer pour complet.
- **EF-15 — Péremption.** Le jeu dit de quoi il dépend (données de réseau, version des règles de
  routage, période couverte). Lorsqu'un de ces éléments a changé depuis, l'utilisateur en est
  averti avant de lancer une expérience dessus — et décide.
- **EF-16 — Reprise de la préparation.** La préparation d'un jeu peut être interrompue et
  reprise ; ce qui a été calculé n'est pas recalculé.

### C. Éligibilité des propositions

- **EF-20 — Filtrage à la décision.** Au moment de décider, le décideur ne voit que les
  propositions effectivement praticables pour cette personne, à cet instant, compte tenu de ce
  qu'elle possède, de ce qu'elle a le droit de conduire, et de l'endroit où se trouvent ses
  véhicules. Cette règle vaut **à l'identique dans les deux modes d'exécution**.
- **EF-21 — Chaîne de la journée.** L'endroit où se trouvent les véhicules d'une personne
  découle de ses décisions précédentes de la même journée. La décision d'un déplacement dépend
  donc des précédentes, et cette dépendance est la seule qui subsiste une fois les propositions
  enregistrées.
- **EF-22 — Traçabilité du filtre.** Pour toute décision, l'utilisateur peut savoir quelles
  propositions ont été écartées et pour quel motif. Une option absente doit être explicable.
- **EF-23 — Ordre de présentation.** L'ordre dans lequel les propositions sont présentées au
  décideur est maîtrisé et reproductible, de sorte qu'il ne devienne pas un facteur d'influence
  involontaire.

### D. Exécution sans simulateur

- **EF-30 — Journée complète sans simulateur.** L'utilisateur peut faire décider toute une
  cohorte sur sa journée sans démarrer le simulateur : les propositions viennent du jeu
  enregistré, le filtre d'éligibilité s'applique, le décideur répond, la chaîne des véhicules
  avance.
- **EF-31 — Regroupement libre.** Dans ce mode, rien n'impose de traiter les personnes une par
  une : le système est libre de regrouper et de paralléliser les décisions comme il le juge
  efficace, sous deux réserves — le résultat doit être indiscernable d'une exécution décision
  par décision, et le régime de regroupement effectivement appliqué doit être enregistré dans
  le résultat (il fait partie des conditions de l'expérience, donc de sa comparabilité).
- **EF-32 — Avancement visible.** Pendant l'exécution, l'utilisateur voit où on en est : part
  effectuée, temps écoulé, temps restant estimé, sollicitations du décideur, erreurs.
- **EF-33 — Ce mode ne prétend pas à tout.** Sans simulateur, il n'y a ni déplacement physique,
  ni congestion, ni incident vécu, ni mémoire d'expérience. Les questions qui portent sur ces
  éléments relèvent du mode simulateur, et le système doit le dire au moment où l'utilisateur
  configure une expérience qui les mobilise.

### E. Exécution avec simulateur — changements attendus

- **EF-40 — Consommer un jeu enregistré.** La simulation doit pouvoir démarrer sur une
  population **dont les déplacements ont déjà été enregistrés**, et servir ses propositions
  depuis ce jeu au lieu de les calculer en vol.
- **EF-41 — Disponible par le chemin de lancement actuel.** Cette capacité n'est pas réservée à
  la nouvelle interface : la manière habituelle de démarrer la simulation doit permettre de
  désigner une population et son jeu enregistré. La plateforme est un confort, pas un passage
  obligé.
- **EF-42 — Régime nominal sans recalcul.** Lorsqu'un jeu enregistré couvre la journée, la
  simulation n'appelle plus les moteurs d'itinéraires. C'est un comportement observable :
  l'exécution doit pouvoir en rendre compte.
- **EF-43 — Recalcul sous conditions, et seulement là.** Un calcul d'itinéraires en cours de
  simulation n'est légitime que dans deux cas : l'offre de transport a changé (incident,
  fermeture, dégradation), ou l'heure réelle de départ s'est écartée de l'heure programmée au
  point que les propositions enregistrées ne valent plus.
- **EF-44 — Ce qui ne justifie pas un recalcul doit être identifié.** Le système doit rendre
  explicite la règle qui distingue les écarts sans effet de ceux qui en ont, et cette règle doit
  tenir compte du fait que **tous les modes ne sont pas sensibles à l'heure de la même façon** :
  certains ne le sont pas du tout, d'autres à l'heure près, d'autres au quart d'heure. Un
  recalcul qui rend la proposition qu'on avait déjà est un coût sans contrepartie, et un
  déclencheur qui ne déclenche jamais rien est une fonction fantôme.
- **EF-45 — Mémoire.** L'expérience choisit si les agents mémorisent leurs déplacements. Quand
  la mémoire est active, ce qui a été vécu un jour influence les jours suivants, et le résultat
  doit permettre de relire cette influence.
- **EF-46 — Événements.** L'expérience peut porter un incident de réseau ou une information
  extérieure, à un jour donné, et le résultat doit permettre de distinguer ce qui s'est passé
  avant, pendant et après.
- **EF-47 — Pause et reprise à chaud.** L'utilisateur peut suspendre une simulation en cours et
  la reprendre plus tard **sans rejouer ce qui a déjà été joué** : les agents restent où ils
  sont, leur mémoire est conservée, les décisions acquises ne sont pas repayées. La granularité
  acceptable de cette reprise est un point à trancher (§7).
- **EF-48 — Arrêt propre.** L'utilisateur peut arrêter définitivement une exécution ; ce qui a
  été produit reste exploitable et le registre le dit clairement.

### F. Temps et calendrier

- **EF-50 — Horizon.** L'utilisateur choisit le nombre de jours de l'expérience.
- **EF-51 — Trois politiques de date.** Une date commune à toute la population, qui avance
  ensemble ; une date propre à chaque personne, qui avance individuellement ; ou un tirage
  aléatoire d'un jour représentatif. La première est nécessaire dès qu'un événement doit être
  vécu simultanément ; la dernière convient aux expériences d'une seule journée sans mémoire.
- **EF-52 — Cohérence avec les données disponibles.** Une date choisie hors de la période
  couverte par les données de transport doit être refusée ou signalée, jamais silencieusement
  décalée.

### G. Ressources et interruption

- **EF-60 — Surveillance.** Pendant l'exécution, l'utilisateur voit la consommation des quotas
  des décideurs sollicités et leur marge restante.
- **EF-61 — Arrêt propre sur épuisement.** Lorsqu'une ressource nécessaire est épuisée,
  l'exécution s'interrompt proprement, conserve ce qui est acquis, et dit pourquoi elle s'est
  arrêtée et à partir de quand elle pourra reprendre.
- **EF-62 — Aucune substitution silencieuse.** Le système ne remplace jamais de lui-même le
  décideur demandé par un autre, ne réduit jamais de lui-même ce qui est présenté, et ne
  dégrade jamais de lui-même la manière de décider pour finir malgré la pénurie. Il attend, ou
  il s'arrête, et il le dit.
- **EF-63 — Reprise sans double dépense.** À la reprise, les décisions déjà obtenues ne sont pas
  redemandées.

### H. Résultats, registre, restitution

- **EF-70 — Archivage systématique.** Toute exécution, terminée ou interrompue, produit un
  ensemble rangé et daté contenant : sa configuration complète et les empreintes de ce qu'elle a
  consommé, les décisions prises, ce qui a été présenté avant chaque décision, et ce que le
  décideur a répondu.
- **EF-71 — Relecture ultérieure.** Ces éléments doivent rester exploitables plus tard, pour des
  analyses qui n'existaient pas au moment de l'exécution. Ce qui a été présenté au décideur en
  fait partie : sans cela, une décision n'est pas relisable.
- **EF-72 — Registre.** L'utilisateur dispose d'une vue d'ensemble de ses expériences : ce qui a
  été lancé, dans quel état, avec quels résultats principaux, triable et filtrable.
- **EF-73 — Comparaison.** Deux expériences comparables se comparent côte à côte, et le système
  refuse ou signale la comparaison de deux expériences dont les éléments partagés diffèrent.
- **EF-74 — Détail au clic.** Depuis le registre, l'utilisateur descend jusqu'à la décision
  unitaire : cette personne, ce déplacement, ces propositions, cette réponse, ce motif.
- **EF-75 — Restitution.** Chaque résultat donne lieu à une page de synthèse consultable, et les
  chiffres qu'elle porte peuvent être repris ailleurs sans ressaisie.
- **EF-76 — Couverture affichée.** Tout résultat affiche, à côté de ses chiffres, la part des
  déplacements attendus qu'il couvre effectivement. Un résultat partiel ne peut jamais être
  présenté comme un résultat complet — a fortiori dans un classement.
- **EF-77 — Référentiel non recopié.** La plateforme ne détient aucune valeur de référence en
  propre. Lorsqu'elle compare un résultat à des valeurs d'enquête, elle les lit dans la source
  de vérité du dépôt et cite laquelle. *L'exigence naît d'un incident : la version précédente de
  ce ticket portait quatre valeurs de référence qui n'existaient nulle part.*

---

## 5. Règles de gestion

Ces règles priment sur les exigences : une solution qui satisfait une exigence en violant une
règle n'est pas recevable.

- **RG-1 — Une seule manière de décider.** Le mode sans simulateur et le mode simulateur ne
  proposent pas deux logiques de décision comparables : ils en partagent **une**. Toute
  divergence est un défaut, et l'égalité doit être vérifiable, pas postulée.
- **RG-2 — Aucune dégradation scientifique.** Rien n'est assoupli pour qu'une exécution
  aboutisse. En cas de pénurie, on attend ou on s'arrête.
- **RG-3 — L'absence de mesure n'est pas une réussite.** Aucun affichage, aucun classement,
  aucune synthèse ne peut faire apparaître un résultat vide ou partiel comme bon. La couverture
  accompagne toujours le chiffre.
- **RG-4 — Rien n'est réputé identique sans empreinte.** Deux exécutions ne sont déclarées
  comparables que sur la foi d'empreintes, jamais sur la foi de noms de fichiers ou de dates.
- **RG-5 — Reproductibilité.** Une exécution relancée dans les mêmes conditions redonne le même
  résultat ; à défaut, l'expérience déclare explicitement d'où vient sa part d'aléa.
- **RG-6 — Ce qui a été payé n'est pas jeté.** Une interruption, quelle qu'en soit la cause,
  laisse un état exploitable et reprenable.
- **RG-7 — Une décision est toujours explicable.** Pour toute décision archivée, on doit pouvoir
  reconstituer ce qui a été présenté, ce qui a été écarté, et pourquoi.

---

## 6. Hors périmètre

- **Le design.** Découpage, formats, interfaces, technologies : autre document, après validation
  de celui-ci.
- **Les valeurs de référence et les seuils scientifiques.** Ils appartiennent au protocole
  scientifique et à la source de vérité du dépôt. La plateforme les lit, ne les fixe pas, et ne
  se prononce pas sur ce qu'est un bon score.
- **Le plan d'expériences lui-même.** Ce que l'on cherche à mesurer relève du plan expérimental ;
  ce document ne décrit que l'outil qui permet de le dérouler.
- **La discussion entre agents.** Évoquée comme perspective, elle ne fait partie d'aucune
  exigence ici — mais elle est la raison pour laquelle le mode simulateur ne peut pas être
  considéré comme une étape transitoire.
- **La qualité des propositions.** Ce que les moteurs de routage savent produire, et à quel
  point c'est fidèle, est un sujet distinct et déjà traité ailleurs.

---

## 7. Points à trancher

Aucun de ces points ne peut être décidé depuis le code ; ils changent tous ce qu'il faut
construire.

1. **L'unité de sollicitation du décideur.** Une question par déplacement, ou une question par
   personne couvrant sa journée ? Le plan expérimental et le comportement actuel ne disent pas
   la même chose, et le coût comme la comparabilité en dépendent.
2. **Le statut du jeu de déplacements enregistré.** Artefact scellé, versionné et cité dans les
   résultats au même titre que la population — ou objet régénérable dont seule l'empreinte
   compte ? Cela décide de ce qui se passe quand les règles de routage évoluent.
3. **Que faire d'un jeu incomplet.** Une expérience peut-elle tourner sur un jeu qui ne couvre
   pas tous les déplacements — et si oui, comment le résultat le porte-t-il ?
4. **La granularité de la reprise à chaud.** Reprendre à l'instant exact de l'interruption, ou
   au début de la journée en cours ? La seconde est nettement moins coûteuse et suffit peut-être
   à l'usage réel ; la première est ce que dit le besoin.
5. **Ce que « à chaud » recouvre.** Position des agents, mémoire, décisions déjà obtenues,
   demandes en cours : jusqu'où va-t-on, et qu'accepte-t-on de perdre ?
6. **Le regroupement des décisions comme condition d'expérience.** En mode sans simulateur, le
   regroupement est libre (EF-31) ; mais si deux décideurs comparés ne le supportent pas de la
   même façon, faut-il le geler à une valeur commune pour que la comparaison reste propre ?
7. **La réplication.** Combien d'exécutions d'une même expérience, et la plateforme doit-elle
   les gérer comme un ensemble ou comme des exécutions indépendantes ?

---

## 8. Critères d'acceptation fonctionnels

Observables, vérifiables, et volontairement muets sur les valeurs scientifiques.

- [ ] **CAF-1 — Reproductibilité.** Une expérience relancée à l'identique produit le même
      résultat, ou déclare explicitement sa part d'aléa.
- [ ] **CAF-2 — Égalité des modes.** Une même configuration, exécutée avec et sans simulateur,
      mémoire désactivée, produit les mêmes décisions.
- [ ] **CAF-3 — Reprise fidèle.** Une exécution interrompue à mi-parcours puis reprise donne le
      même résultat final qu'une exécution ininterrompue, sans redemander les décisions acquises.
- [ ] **CAF-4 — Régime nominal sans recalcul.** Une exécution sur un jeu enregistré complet ne
      sollicite aucun moteur d'itinéraires, et le prouve dans son compte rendu.
- [ ] **CAF-5 — Recalcul justifié.** Tout recalcul survenu en cours de simulation est rattaché à
      l'une des deux conditions admises, et cette attribution est lisible après coup.
- [ ] **CAF-6 — Chemin habituel.** La simulation peut être lancée par le chemin de lancement
      actuel sur une population dont les déplacements ont été enregistrés.
- [ ] **CAF-7 — Portabilité du jeu.** Un jeu de déplacements enregistré sur une machine est
      utilisable sur une autre sans rejouer aucun calcul.
- [ ] **CAF-8 — Couverture.** Aucun affichage ne présente un chiffre de résultat sans la
      couverture qui lui correspond.
- [ ] **CAF-9 — Aucun référentiel embarqué.** La plateforme ne contient aucune valeur d'enquête
      en propre ; toute comparaison cite sa source.
- [ ] **CAF-10 — Populations ouvertes.** Une population quelconque est acceptée ; un refus, s'il
      y en a un, est motivé et actionnable.
- [ ] **CAF-11 — Explicabilité.** Pour n'importe quelle décision archivée, on retrouve les
      propositions présentées, celles qui ont été écartées et le motif de leur écartement.
- [ ] **CAF-12 — Interruption non destructrice.** Une interruption, choisie ou subie, laisse une
      exécution reprenable et un résultat partiel exploitable et identifié comme tel.
