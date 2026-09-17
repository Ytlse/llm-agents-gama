# Ticket 085 — Une contrainte de run ne doit pas vivre dans un fichier global à la pile

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert le 2026-09-16. Contrat de tests à écrire avant le code, dans `specs/ticket_085/tests.md`.
>
> **Objet.** Rendre la restriction de routage du ticket 084 **propre à chaque run**, faire
> échouer en une seconde au lieu de deux minutes une contradiction de configuration, et cesser
> d'annoncer « aucune instance ne sert ce modèle » quand le motif réel est « quota pas encore
> renouvelé ».

---

## 1. L'incident du 2026-09-16

`make experience-reprendre EXP=exp_gemini-35-fl_proexp08_…` reprend correctement à 2533/3161
(80,1 %) puis n'avance plus d'une décision. La commande n'est pas figée : elle tourne et échoue en
boucle, muette du point de vue du terminal.

| Heure | Ce qui se passe |
|---|---|
| 09:41:35 | Reprise, premier lot soumis à la passerelle |
| 09:41:38 | Le worker lève `RestrictionInstances` et meurt sans écrire de résultat |
| 09:43:35 | Le client expire à 120 s → `passerelle_occupee: Timeout expiré` |
| 09:45:40 | `[ALARME] Disjoncteur gateway LLM OUVERT` après 10 échecs consécutifs |
| 09:48:50 | Pause automatique : « 420 s sans avancée » |

Bilan : trois heures perdues, 26 appels tous en gemini 3.1, zéro en gemini 3.5 — alors que les
deux clés gemini 3.5 étaient saines dans `/health`.

---

## 2. La cause racine

Une ligne de `services/llm-agents/config/config.yaml`, posée par le ticket 084 pour protéger le
run de soixante jours :

```yaml
llm:
  instances_admises: [google_gemini31_key1, google_gemini31_key2]
```

`llm_agent.py:1187` lit `settings.llm.instances_admises` à **chaque** décision du processus et la
colle au *payload*, tandis que `force_provider` arrive par un autre chemin. Une expérience en
gemini 3.5, qui épingle `google_gemini35_key1`, se retrouve donc à porter les deux contraintes à
la fois. Le routeur refuse :

```
fournisseur forcé 'google_gemini35_key1' hors des instances admises
['google_gemini31_key1', 'google_gemini31_key2'] — contraintes contradictoires,
aucune n'est arbitrée en silence.
```

**Et il a raison de refuser.** La règle du ticket 084 — une restriction fausse n'est jamais
« aucune restriction » — n'est pas en cause et n'est pas touchée ici. Ce qui est faux, c'est
qu'un choix *par run* soit logé dans un fichier *global à la pile*, lu par tout processus lancé
depuis le conteneur `controller`.

C'est un défaut de portée, pas un défaut de règle.

---

## 3. Deux chemins de lancement disjoints

Le point que toute correction doit intégrer, sous peine d'en casser une autre.

| | `experiences lancer` | `make run` |
|---|---|---|
| Processus | éphémère, un par expérience | service `controller`, permanent |
| Réglages | **imposés en mémoire** par `cmd_lancer` (`experiences/cli.py:461-505`) | **lus dans `config.yaml`** à l'import |
| Verrou par clé API | pris (`_jeu_de_cles_experience`) | jamais pris |
| Mode | sans simulateur uniquement | seul chemin avec GAMA |

`cmd_lancer` refuse explicitement le mode simulateur et renvoie vers `make run`. Le run de
soixante jours du ticket 084 passe donc par `make run`, pour qui `config.yaml` **est** le seul
véhicule.

**Conséquence dure : le fichier ne peut pas repasser à vide tant que `make run` n'a pas
d'équivalent.** Le vider ne déplacerait pas la restriction, il la supprimerait, et précisément
pour le run qui l'avait motivée — sans qu'aucune ligne ne le dise. C'est exactement le mode de
panne que le ticket 084 prétendait interdire. L'ordre des lots ci-dessous en découle.

---

## 4. Lot A — l'échec devient immédiat (prioritaire, indépendant)

### Le défaut

Dans `packages/llm_gateway/src/llm_gateway/worker/task_worker.py:97`, la boucle d'attente
n'intercepte que `RuntimeError`. `RestrictionInstances` est un `ValueError` : elle traverse la
tâche **avant** le `rt.queue.pop`. Les tâches ne sont donc pas seulement laissées sans réponse,
elles **restent dans la file** — chaque dispatch suivant les reprend et échoue à l'identique.

Ce n'est pas un échec qui coûte 120 s une fois, c'est un échec qui se réarme tout seul. C'est ce
qui produit les dix échecs consécutifs jusqu'au disjoncteur.

### Ce qui est fait

Le worker rattrape `RestrictionInstances`, vide la file du lot (`pop` **et**
`clear_scheduled` — sinon le drapeau de dispatch tient jusqu'à son TTL), marque chaque tâche en
échec avec **les deux contraintes nommées** (la liste admise et le fournisseur épinglé), et ne
réessaie pas : l'erreur est déterministe, un rejeu ne peut que la reproduire.

Aucun slot RPM n'est à restituer : la sélection a échoué avant toute réservation.

### La règle

**Un refus déterministe se dit une fois, tout de suite, et ne se réessaie jamais.** Le client
reçoit le vrai motif en moins d'une seconde au lieu de `Timeout expiré` à 120 s, et le disjoncteur
ne s'ouvre plus sur une faute de configuration.

Corollaire : cet échec ne doit pas être classé `passerelle_occupee`. Une contradiction de
configuration rangée dans le seau « passerelle débordée » envoie chercher un quota là où il n'y a
qu'une ligne de YAML à corriger — c'est ce qui a coûté les trois heures.

### Cas de test

- **A1** — `RestrictionInstances` levée à la sélection : les tâches du lot sortent de la file, sont
  marquées en échec, et aucun rejeu Celery n'est planifié.
- **A2** — le motif rendu au client nomme la liste admise **et** le fournisseur épinglé.
- **A3** — le drapeau de dispatch du lot est levé (`clear_scheduled`), sinon le lot suivant attend
  le TTL pour rien.
- **A4** — l'échec n'est pas typé `passerelle_occupee`.
- **A5** — une saturation ordinaire (`RuntimeError`) conserve **exactement** le comportement
  d'attente et de rejeu actuel : le lot A ne touche pas à ce chemin.

---

## 5. Lot B — la restriction suit l'expérience

### Ce qui est fait

Au lancement, `experiences lancer` dérive `instances_admises` du modèle de l'expérience courante
(`instances_pour_modele(exp.decideur.modele, providers, exp.decideur.portee)`) et l'impose aux
réglages du processus — **au même endroit et de la même façon** que `appliquer_fenetre_age` règle
déjà la fenêtre mémoire (`experiences/cli.py:461-505`). Chaque expérience porte alors sa propre
restriction et deux familles de modèles cohabitent sans se voir.

La liste retenue est journalisée au lancement et consignée dans `execution.yaml` : une mesure
archivée dira sous quelle restriction elle a été prise.

Dériver du modèle plutôt que de recopier une liste à la main est le bon invariant : il reste vrai
quand une clé est ajoutée aux fournisseurs, et il est cohérent par construction avec l'instance
épinglée, qui sert ce même modèle.

### Ce que le lot B ne fait PAS

**Il ne vide pas `config.yaml`.** Le fichier reste la source du seul chemin `make run` (§ 3).
Quand `experiences lancer` impose sa propre liste par-dessus une valeur non vide du fichier, il
**le journalise explicitement** : un écrasement muet de contrainte scientifique est le défaut
qu'on est en train de corriger, pas un moyen acceptable de le corriger.

Vider le fichier suppose d'abord de donner à `make run` son injection par run — il réécrit déjà
`config.yaml` pour `CACHE` et `MEM` (`make/gama.mk:63-70`), le geste est connu. Hors périmètre
ici, mais c'est la condition pour clore vraiment le sujet.

### Cas de test

- **B1** — une expérience en gemini 3.5 lancée avec `config.yaml` portant les clés gemini 3.1
  s'exécute sous **ses** instances : la valeur du fichier n'atteint pas ses requêtes.
- **B2** — la liste retenue est celle des instances servant le modèle, filtrée par `portee`.
- **B3** — l'écrasement d'une valeur non vide du fichier est journalisé, avec l'ancienne et la
  nouvelle liste.
- **B4** — la liste retenue apparaît dans `execution.yaml`.
- **B5** — un décideur qui n'est pas `passerelle` n'impose aucune restriction (liste vide).
- **B6** — `config.yaml` non vide et `experiences lancer` absent : le chemin `make run` conserve
  la restriction du fichier, à l'identique.

---

## 6. Lot C — le refus dit le bon motif

### Le défaut

Dans `experiences/cli.py:384-390`, la variable `instances` porte d'abord « les instances qui
servent ce modèle », puis est **écrasée** par `moniteur.instances_disponibles()`, c'est-à-dire
« celles qui ont encore du quota » :

```python
instances = instances_pour_modele(exp.decideur.modele or "", providers, exp.decideur.portee)
moniteur = MoniteurRessources(instances, providers)
moniteur.rafraichir()
instances = moniteur.instances_disponibles() if moniteur.joignable else instances
```

Le refus de `experiences/experience.py:690` lit la seconde et annonce la première : « aucune
instance de passerelle ne sert le modèle `gemini-3.5-flash-lite` » — juste après avoir listé ce
modèle parmi les modèles servis. Le motif réel, ce matin-là, était que le quota journalier n'était
pas encore renouvelé (fenêtre `America/Los_Angeles`, remise à zéro à 09:00 CEST).

Une seule variable pour deux sens, et le message ment de bonne foi.

### Ce qui est fait

Les deux ensembles sont séparés et nommés. Le refus distingue « aucune instance ne sert ce
modèle » de « les instances qui le servent sont momentanément épuisées », ce second cas rendant le
détail des quotas par `MoniteurRessources.raison_epuisement()` — la fonction existe déjà
(`experiences/ressources.py:309`) et produit exactement ce texte.

### Cas de test

- **C1** — modèle servi par personne : message inchangé.
- **C2** — modèle servi mais toutes les instances épuisées : le refus dit l'épuisement et rend le
  compte requêtes/jour par instance.
- **C3** — le mot « épuisée » ne peut pas apparaître quand aucune instance ne sert le modèle, et
  réciproquement.

---

## 7. Constat annexe — le verrou par clé ne couvre pas `make run`

Le verrou par clé API (`experiences/cles.py`, via `_jeu_de_cles_experience`) n'est pris que par
`cmd_lancer`. Le run gemini 3.1 passant par `make run`, il ne tenait aucune clé : il n'y avait
rien derrière quoi mettre la reprise en file, alors que les deux expériences partagent les mêmes
clés API Google.

La même asymétrie explique donc la contradiction de configuration **et** le verrou qui n'a pas
joué. Le chemin `make run` est invisible à toute la coordination inter-expériences. Constaté ici,
**non traité** : cela dépasse le périmètre de ces trois correctifs et mérite son propre ticket.

---

## 8. La leçon, plus large que ce ticket

`config.yaml` est traité comme un état *par run* alors que c'est un état *partagé, mutable et non
versionné* de toute la pile — `make run` le réécrit en place pendant qu'une autre expérience le
lit. `instances_admises` est le cas qui a fait mal le 2026-09-16 ; `cache.enabled` et
`cache_dir` ont rigoureusement la même forme et attendent leur incident.

---

## 9. Question à trancher pendant l'implémentation

Quand le client reçoit le refus déterministe du lot A, faut-il **arrêter le run** plutôt que
laisser chaque décision échouer jusqu'au disjoncteur ? Une faute de configuration ne se répare pas
en réessayant, et dix échecs rapides valent mieux que dix échecs lents mais restent dix échecs.

Hypothèse retenue faute d'arbitrage : on **ne change pas** le comportement du client dans ce
ticket — le lot A rend le motif juste et rapide, le détecteur d'immobilité fait déjà le reste. À
consigner dans `specs/ticket_085/questions.md` et à poser en fin de lot.

---

## 10. Portée

Passerelle (`packages/llm_gateway`) pour le lot A, plateforme d'expériences
(`services/llm-agents/experiences`) pour les lots B et C. Tests des deux côtés. Mise à jour de
`docs/arch/llm-inference.md` et entrée de changelog à la livraison.

**Ordre imposé :** A d'abord — il est indépendant et transforme trois heures en une seconde quelle
que soit la suite. C ensuite, qui ne touche que du texte. B en dernier : c'est le seul qui déplace
une garantie scientifique, et il porte la dépendance du § 3.
