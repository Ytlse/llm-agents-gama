# Ticket 089 — `make run` arrête le run précédent avant de lancer le suivant

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert et **livré le 2026-09-16**, 4 tests dédiés.
>
> **Objet.** Empêcher que deux simulations s'empilent dans le même processus GAMA.

---

## 1. Ce qui a été mesuré

Quatrième tentative du bras choqué C6, morte au jour 1 :

```
/usr/sbin/gama-headless: line 140: 41 Killed  $java …
GAMA encountered an error and crashed
OOMKilled=true
```

Le conteneur GAMA n'était **pas** redémarré entre deux lancements. Chaque `make run` demandait
donc un `load` au processus GAMA déjà en place, et le journal du conteneur le montre : sur le
dernier segment, `City.gaml model is being compiled` apparaît **deux fois**.

| Lancement | Conteneur GAMA |
|---|---|
| 12:49 | démarré à 12:48 — une simulation chargée |
| 13:11 | **le même**, toujours debout — une deuxième simulation chargée |

Deux `City.gaml` résidents en même temps — 453 communes, réseau de transport complet, graphes
OSM — dans une JVM plafonnée à 12 Go.

**Ce qui pèse est le territoire, pas les agents.** La limite de 12 Go avait été calée en août
pour UNE journée simulée de 1 000 agents. Deux réseaux complets la dépassent même avec cinq
agents, ce qui explique un OOM qui paraissait absurde sur une population de test.

---

## 2. Ce qui est fait

`stop-run` devient la **première** étape de `run`, avant tout geste sur la pile, et pour **tous**
les lancements — reprise à chaud comprise, puisqu'elle charge elle aussi un modèle.

L'arrêt est annoncé à l'écran. Ce n'est pas décoratif : voir § 3.

---

## 3. Ce que cela change, et qu'il faut savoir

⚠ **La garde « un launcher tourne déjà, lancement ignoré » ne se déclenche plus.** Elle
protégeait contre le double lancement : un `make run` tapé par mégarde pendant un run en cours
était refusé. Maintenant il **arrête ce run** puis en démarre un autre. Le message d'arrêt est le
seul avertissement.

C'est le prix du correctif, et il est assumé : empiler deux simulations tue le run à coup sûr et
salit son répertoire, tandis qu'un `make run` tapé par erreur reste un geste délibéré. Si la
protection redevient souhaitable, elle devra prendre la forme d'un refus explicite avec
échappatoire (`FORCE=1`), pas d'un retour au silence.

---

## 4. Défaut signalé, non corrigé

`make stop-run` annonce « ✅ Run arrêté » même quand son `pkill` à l'intérieur du conteneur
échoue — `pkill` n'existe pas dans l'image du contrôleur, et l'erreur est avalée par un
`|| true`. L'arrêt réel passe par les deux gestes côté hôte (`pkill` du launcher et `stop gama`),
qui eux fonctionnent ; le `pkill` en conteneur est redondant. Mais maintenant que `stop-run` est
sur le chemin critique de chaque lancement, ce message trop confiant mérite d'être repris.
