# Ticket 014 — Annexe : transformation de prompts réels vers l'option 2 (prompt-journée)

Démonstration construite le 2026-08-19 à partir du run `experiments/current`
(sim du 2026-03-16). Agent retenu : **514467 — « Marthe, 35 ans »** (travail à
plein temps, famille de 2, revenu faible ; conductrice, voiture toujours dispo,
abonnée TC, vélo classique), l'agent le plus actif du run côté LLM.

## Matériau d'origine (l'« avant »)

Sa journée réelle compte **11 trajets** (moves.csv) :

| Départ (sim) | Trajet | Mode choisi | Méthode | Contrainte chaîne |
|---|---|---|---|---|
| 08:04 | domicile → leisure | Vélo | cache | |
| 08:40 | leisure → leisure | Vélo | cache | sortie_bloquee |
| 09:24 | leisure → domicile | Vélo | mono-option | retour_force |
| 10:23 | domicile → achats | Marche | cache | |
| 11:16 | achats → domicile | Marche | cache | sortie_bloquee |
| 12:09 | domicile → leisure | Voiture | **LLM** | |
| 14:22 | leisure → leisure | Voiture | **LLM** | sortie_bloquee |
| 15:07 | leisure → other | Voiture | **LLM** | sortie_bloquee |
| 15:54 | other → domicile | Voiture | mono-option | retour_force |
| 16:27 | domicile → other | Vélo | **LLM** | |
| 17:26 | other → domicile | Vélo | **LLM** | sortie_bloquee |

Les 5 décisions LLM ont coûté **5 appels distincts**, étalés de 12:09 à 17:26
(sim). Chaque appel était un **batch de 8 personas** (7 autres agents dans le
même prompt), avec le persona de Marthe et ses options recopiés à chaque fois.
Extraction brute : `llm_exchanges.jsonl`, catégorie `itinary_multi_agent`.

Constat sur ce matériau réel, avant toute transformation :

- 6 trajets sur 11 n'ont **pas** touché le LLM (cache de décisions + mono-option) ;
- les jeux d'options de chaque prompt sont **déjà conditionnés par la chaîne
  exécutée** : à 14:22 le vélo n'apparaît pas (resté au domicile), à 15:54 la
  seule option est la voiture (verrou de retour) ;
- la journée contient **deux boucles** distinctes depuis le domicile :
  boucle voiture (12:09→15:54) puis boucle vélo (16:27→17:26).

## L'« après » : prompt-journée fusionné (option 2)

Périmètre : la chaîne de l'après-midi (6 tronçons, domicile → … → domicile),
celle couverte par les 5 prompts réels. Les options sont recopiées **verbatim**
des prompts loggés ; voir les réserves en fin d'annexe.

### Prompt système transformé

```
Tu vas incarner une personne vivant à Toulouse et planifier D'UN SEUL TENANT
tous ses déplacements de la journée. Ta tâche est de sélectionner une chaîne de
modes de déplacement cohérente sur l'ensemble des tronçons. L'évaluation doit
être purement algorithmique et s'effectuer en 5 étapes :
1) Filtrage strict : Définis les lignes rouges non négociables du persona pour
éliminer d'emblée les options invalides.
2) Cohérence de chaîne : Un véhicule personnel (voiture, vélo) est un LIEU : il
reste garé là où la personne l'a laissé. Une option voiture ou vélo n'est
utilisable sur un tronçon que si la chaîne des tronçons précédents a amené ce
véhicule au point de départ du tronçon. Tout véhicule sorti dans la journée
doit être ramené au domicile par la chaîne.
3) Matrice de coût : Calcule le véritable coût d'opportunité de chaque option en
pondérant les variables suivantes exclusivement selon les attributs du profil
(âge, revenus, santé) :
- Gain de temps VS confort.
- Friction d'accès brute (temps d'approche, stationnement, correspondances).
- Filtre de sécurité : Élimine les options présentant des risques.
- Filtre de réalité : Distingue un mode théoriquement utile d'un mode réellement
  légitime selon le contexte immédiat et les contraintes du persona.
- Filtre de confort : Prends en compte les préférences de confort du persona.
4) Soutenabilité : Applique la règle des 48 heures à L'ÉCHELLE DE LA JOURNÉE
ENTIÈRE : l'effort cumulé des tronçons (km de vélo, minutes de marche) doit
rester soutenable s'il est répété deux jours de suite.
5) Anticipation : Le choix du premier tronçon engage la journée. Pèse chaque
option du matin à la lumière des tronçons suivants (distances, horaires,
retour au domicile).

[Instructions de sortie]
1) Analyse le profil et la journée via ce prisme.
2) Construis 2 à 4 CHAÎNES CANDIDATES cohérentes (une option par tronçon,
respectant la règle 2), et attribue à chaque chaîne la probabilité en % que ce
persona la retienne — les probabilités somment à 100.
3) Réponds avec l'objet JSON final : pour chaque chaîne, la liste des index
d'option par tronçon (dans l'ordre), sa probabilité, et une justification en
une phrase. Une chaîne incohérente (véhicule utilisé là où il n'est pas) est
interdite, quelle que soit son attractivité.
```

### Prompt utilisateur transformé

```
--- agent_id=514467 | Planification de la journée du lundi | 6 tronçons ---
**Contexte du jour :** Météo : 12–13°C, Ciel dégagé/Ensoleillé toute la journée.
Pas de précipitations prévues.
Marthe, 35 ans, Travail à plein temps (famille de 2 pers., revenu faible)
Mobilité : conducteur·trice, voiture toujours dispo | abonné·e TC | possède un
vélo classique. Contraintes : None
**État initial :** au domicile ; voiture et vélo garés au domicile.

**Agenda de la journée** (6 tronçons, indices A à F) :
- [A] 13:09 domicile → leisure (≈10,7 km)
- [B] 15:22 leisure → leisure (≈6,4 km)
- [C] 16:07 leisure → other (≈4,8 km)
- [D] 16:54 other → domicile (≈1,3 km)
- [E] 17:27 domicile → other (≈1 km)
- [F] 18:26 other → domicile (≈1,1 km)

**Tronçon [A] — 13:09, domicile → leisure** (6 options, indices 0 à 5) :
- [0] foot,bus,foot,metro,foot: Temps de trajet : 57 minutes, dont 31 minutes de marche.
    · Marche jusqu'à 'Sausse' : 21 minutes.
    · Bus '42' vers 'Borderouge' : 23 minutes.
    · [correspondance] Metro 'B' vers 'Trois Cocus' : 1 minute.
    · Marche jusqu'à 'leisure' : 7 minutes.
- [1] foot: Durée estimée : 1 hour, 46 minutes. Distance : 8.5 km.
- [2] bicycle: Temps de trajet : 35 minutes, dont 2 minutes d'accès et d'attache. Distance : 8.7 km.
    · Déverrouiller le vélo : 1 minute.
    · Trajet à vélo : 33 minutes.
    · Attacher le vélo à 'leisure' : 1 minute.
- [3] foot,bus,foot: Temps de trajet : 1 hour, 1 minute, dont 38 minutes de marche.
    · Marche jusqu'à 'Sausse' : 21 minutes.
    · Bus '42' vers 'Borderouge' : 23 minutes.
    · Marche jusqu'à 'leisure' : 17 minutes.
- [4] car: Temps de trajet : 23 minutes, dont 9 minutes d'accès et de stationnement. Distance : 10.7 km.
    · Rejoindre la voiture : 2 minutes.
    · Conduite : 14 minutes.
    · Stationnement et marche jusqu'à 'leisure' : 7 minutes.
- [5] foot,bus,foot,metro,foot,metro,foot: Temps de trajet : 52 minutes, dont 16 minutes de marche.
    · Marche jusqu'à 'Gare SNCF Montrabé' : 4 minutes.
    · Bus '20' vers 'Balma-Gramont' : 13 minutes.
    · [correspondance] Metro 'A' vers 'Jean Jaurès' : 6 minutes.
    · [correspondance] Metro 'B' vers 'Trois Cocus' : 9 minutes.
    · Marche jusqu'à 'leisure' : 7 minutes.

**Tronçon [B] — 15:22, leisure → leisure** (5 options, indices 0 à 4) :
⚠ Le vélo n'est utilisable ici que si le tronçon [A] l'a amené (option [A][2]).
- [0] foot,bus,foot: Temps de trajet : 47 minutes, dont 40 minutes de marche.
    · Marche jusqu'à 'Borderouge' : 16 minutes.
    · Bus '33' vers 'Vasseur' : 7 minutes.
    · Marche jusqu'à 'leisure' : 23 minutes.
- [1] foot: Temps de trajet : 1 hour, 1 minute, dont 1 hour, 1 minute de marche.
    · Marche jusqu'à 'leisure' : 1 hour, 1 minute.
- [2] foot: Durée estimée : 56 minutes. Distance : 4.6 km.
- [3] foot,bus,foot: Temps de trajet : 48 minutes, dont 42 minutes de marche.
    · Marche jusqu'à 'Lanusse' : 12 minutes.
    · Bus '19' vers 'Nicol' : 6 minutes.
    · Marche jusqu'à 'leisure' : 29 minutes.
- [4] car: Temps de trajet : 17 minutes, dont 10 minutes d'accès et de stationnement. Distance : 6.4 km.
    · Rejoindre la voiture : 3 minutes.
    · Conduite : 7 minutes.
    · Stationnement et marche jusqu'à 'leisure' : 7 minutes.
    ⚠ Utilisable seulement si la voiture est ici (option [A][4] choisie).

**Tronçon [C] — 16:07, leisure → other** (5 options, indices 0 à 4) :
- [0] foot: Temps de trajet : 1 hour, 5 minutes, dont 1 hour, 5 minutes de marche.
    · Marche jusqu'à 'other' : 1 hour, 5 minutes.
- [1] car: Temps de trajet : 16 minutes, dont 7 minutes d'accès et de stationnement. Distance : 4.8 km.
    · Rejoindre la voiture : 3 minutes.
    · Conduite : 9 minutes.
    · Stationnement et marche jusqu'à 'other' : 4 minutes.
    ⚠ Utilisable seulement si la chaîne [A]-[B] a amené la voiture ici.
- [2] foot,bus,foot: Temps de trajet : 40 minutes, dont 21 minutes de marche.
    · Marche jusqu'à 'ZI Montredon' : 20 minutes.
    · Bus '20' vers 'Collège Montrabé' : 19 minutes.
    · Marche jusqu'à 'other' : 43 seconds.
- [3] foot,bus,foot: Temps de trajet : 38 minutes, dont 27 minutes de marche.
    · Marche jusqu'à 'Balma-Gramont' : 25 minutes.
    · Bus '101' vers 'Collège Montrabé' : 11 minutes.
    · Marche jusqu'à 'other' : 1 minute.
- [4] foot: Durée estimée : 1 hour, 4 minutes. Distance : 5.2 km.

**Tronçon [D] — 16:54, other → domicile** (1 option, indice 0) :
- [0] car: Temps de trajet : ≈8 minutes. Distance : 1.3 km.
    ⚠ Retour du véhicule : si la voiture est ici, elle doit rentrer au domicile
    par ce tronçon ou un tronçon ultérieur de la chaîne.

**Tronçon [E] — 17:27, domicile → other** (6 options, indices 0 à 5) :
- [0] car: Temps de trajet : 12 minutes, dont 9 minutes d'accès et de stationnement. Distance : 827 m.
    · Rejoindre la voiture : 2 minutes.
    · Conduite : 3 minutes.
    · Stationnement et marche jusqu'à 'other' : 7 minutes.
- [1] foot: Temps de trajet : 11 minutes, dont 11 minutes de marche.
    · Marche jusqu'à 'other' : 11 minutes.
- [2] bicycle: Temps de trajet : 6 minutes, dont 2 minutes d'accès et d'attache. Distance : 1.1 km.
    · Déverrouiller le vélo : 1 minute.
    · Trajet à vélo : 4 minutes.
    · Attacher le vélo à 'other' : 1 minute.
- [3] foot,bus,foot: Temps de trajet : 11 minutes, dont 6 minutes de marche.
    · Marche jusqu'à 'Gare SNCF Montrabé' : 4 minutes.
    · Bus '20' vers 'Mont Pin' : 5 minutes.
    · Marche jusqu'à 'other' : 2 minutes.
- [4] foot: Durée estimée : 12 minutes. Distance : 950 m.
- [5] foot,bus,foot: Temps de trajet : 15 minutes, dont 14 minutes de marche.
    · Marche jusqu'à 'Mont Pin' : 9 minutes.
    · Bus '20' vers 'Vignobles' : 1 minute.
    · Marche jusqu'à 'other' : 5 minutes.

**Tronçon [F] — 18:26, other → domicile** (6 options, indices 0 à 5) :
- [0] foot,bus,foot: Temps de trajet : 11 minutes, dont 6 minutes de marche.
    · Marche jusqu'à 'Mont Pin' : 2 minutes.
    · Bus '20' vers 'Gare SNCF Montrabé' : 5 minutes.
    · Marche jusqu'à 'home' : 3 minutes.
- [1] foot,bus,foot: Temps de trajet : 18 minutes, dont 17 minutes de marche.
    · Marche jusqu'à 'Belle Fontaine' : 8 minutes.
    · Bus '20' vers 'Vignobles' : 1 minute.
    · Marche jusqu'à 'home' : 9 minutes.
- [2] foot: Temps de trajet : 11 minutes, dont 11 minutes de marche.
    · Marche jusqu'à 'home' : 11 minutes.
- [3] foot: Durée estimée : 12 minutes. Distance : 950 m.
- [4] bicycle: Temps de trajet : 6 minutes, dont 2 minutes d'accès et d'attache. Distance : 1.1 km.
    · Déverrouiller le vélo : 1 minute.
    · Trajet à vélo : 4 minutes.
    · Attacher le vélo à 'home' : 1 minute.
    ⚠ Utilisable seulement si le tronçon [E] a amené le vélo ici ([E][2]).
- [5] foot,bus,foot: Temps de trajet : 14 minutes, dont 14 minutes de marche.
    · Marche jusqu'à 'Vignobles' : 5 minutes.
    · Bus '20' vers 'Mont Pin' : 0 seconds.
    · Marche jusqu'à 'home' : 9 minutes.

Réponds avec l'objet JSON final contenant 2 à 4 chaînes candidates pour la
journée. Chaque chaîne : `chain` (liste de 6 index d'option, un par tronçon A→F,
dans l'ordre), `probability` (les probabilités somment à 100), `reason` (une
phrase). Recopie `agent_id` exactement tel que fourni. Une chaîne qui utilise
un véhicule là où la chaîne ne l'a pas amené, ou qui laisse un véhicule hors du
domicile en fin de journée, est invalide et ne doit pas apparaître.
```

À titre de repère, la chaîne effectivement exécutée par la simulation
trajet-par-trajet correspond à `[4, 4, 1, 0, 2, 4]` (voiture ×3, retour voiture,
puis vélo ×2) — une réponse plausible du prompt-journée serait cette chaîne en
candidate dominante, contre une chaîne « tout voiture » `[4, 4, 1, 0, 0, ?]`
(impossible : pas d'option voiture cohérente en [F]) et une chaîne TC/marche.

## Ce que la transformation révèle (constats d'implémentation)

1. **Le batching actuel est orthogonal à l'option 2.** Aujourd'hui, 1 appel =
   8 personas × 1 trajet (le persona de Marthe est recopié dans 5 batches).
   L'option 2 inverse : 1 appel = 1 persona × 6 tronçons. La masse de tokens
   par appel est comparable, mais l'appel ne sert plus qu'un agent — la
   mutualisation inter-agents est perdue, la mutualisation intra-agent
   (persona + météo écrits une fois au lieu de 5) est gagnée.
2. **Les options loggées sont conditionnées par la chaîne exécutée.** Le
   tronçon [B] réel n'avait pas d'option vélo parce que le vélo était resté au
   domicile ; le tronçon [D] n'avait qu'une option parce que le verrou de
   retour avait déjà filtré. Un vrai prompt-journée exige de produire les
   options de chaque tronçon pour **chaque état de véhicule atteignable**
   (OTP/OSMnx par tronçon × scénarios), ou d'annoter les dépendances comme
   ci-dessus (⚠) en laissant la cohérence à la charge du LLM — plus fragile.
3. **Le tirage probabiliste doit remonter au niveau chaîne.** Tirer
   indépendamment dans 6 distributions par tronçon produirait des chaînes
   incohérentes ; la sortie doit être une distribution sur des chaînes
   complètes, tirée une fois (`mode_draw_seed`). Conséquence directe : la
   colonne `P(mode) %` par trajet de moves.csv devient une projection dérivée,
   plus une sortie native.
4. **La moitié de la journée n'aurait jamais dû coûter un appel.** 6 des 11
   trajets réels ont été servis par cache ou mono-option. Dans l'option 2, ils
   rentrent dans le prompt-journée : le cache ne peut plus les servir
   individuellement, et le taux de hit du cache de décisions chute (clé =
   journée entière).
5. **Les horaires des tronçons aval sont spéculatifs.** Les heures affichées
   ([B] 15:22, etc.) sont les heures planifiées ; dans la réalité du run elles
   dérivent avec les retards. Le prompt-journée fige des horaires que
   l'exécution contredira.
