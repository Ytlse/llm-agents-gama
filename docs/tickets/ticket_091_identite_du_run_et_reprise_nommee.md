# Ticket 091 — On ne réutilise une mémoire que si c'est la même expérience

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de vérité.
> Ouvert et **livré le 2026-09-16**, 16 tests dédiés. Contrat : `specs/ticket_091/tests.md`.

---

## 1. Le trou

Contenu réel d'un point de reprise, avant ce ticket :

```json
{ "jour_simule": 9, "timestamp_simule": 1774321200, "ancre_run": 1773638100,
  "ecrit_le": "2026-09-16T16:37:09", "compteurs": { … } }
```

Ni modèle, ni prompt, ni population, ni choc. **Rien ne relie cette mémoire au run qui l'a
produite.** Et la reprise suivait le lien `experiments/current`, qui a pointé deux fois dans la
même journée sur un run autre que celui qu'on croyait reprendre. Un `make run CONT=1` pouvait donc
restaurer la mémoire d'une autre expérience sans qu'une seule ligne ne le dise.

---

## 2. Le principe

**Par défaut, on ne réutilise rien.** Ni point de mémoire, ni trace de décisions. La réutilisation
se demande en nommant le run :

```bash
make run OFFLINE=1 … REPRISE=2026-09-16_15_58
```

Le workdir est résolu **par ce nom**, pas par le lien `current`. Un `CONT=1` seul est refusé :
« une reprise se nomme ».

---

## 3. Ce qui fait « la même expérience »

Onze champs, comparés un à un : modèle(s) admis, instances admises, variante de prompt,
population, mémoire longue, auto-réflexion, empreinte du choc, les trois graines, état du cache.

L'heure d'écriture et les compteurs **n'en font pas partie** : ils diffèrent toujours et feraient
refuser toutes les reprises.

⚠ **Le modèle est DÉRIVÉ des instances admises**, via leur `default_model`. La première rédaction
lisait `settings.llm.model`, un réglage qui n'existe pas : le champ sortait vide à chaque fois.
Un champ toujours vide ne fait jamais refuser — il donne l'illusion d'une vérification sans en
faire aucune. C'est le motif récurrent de ce dépôt, l'absence de mesure qui passe pour un succès.

---

## 4. Trois refus fermes

**Une identité qui diffère** fait refuser, en nommant **tous** les écarts d'un coup — corriger un
champ pour buter sur le suivant coûterait un lancement par écart.

**Une identité absente** fait refuser : supposer l'égalité faute de preuve est exactement le
défaut corrigé ici. Un run antérieur à ce ticket n'est donc pas reprenable.

**Une identité illisible** fait refuser aussi.

Et une reprise **ne réécrit jamais** l'identité du run repris : c'est la référence contre laquelle
on compare, la réécrire ferait disparaître l'écart qu'on cherche à détecter.

---

## 5. Aucune échappatoire

Décision de l'auteur, le 2026-09-16 : pas de `REPRISE_FORCEE`. Les cas de mise au point se
traitent à la main, hors du code. Un contournement livré dans le produit finirait par servir en
mesure, et c'est précisément ce qu'on cherche à rendre impossible.

Conséquence assumée, vérifiée par un test : déplacer les jours d'un choc change son empreinte,
donc la manœuvre de mise au point du 2026-09-16 — choc déplacé des jours 6-7 aux jours 9-10, puis
reprise — serait désormais refusée. Et elle aurait raison de l'être.

---

## 6. Le cas « Docker redémarré par une autre session »

L'identité voyage avec **chaque point de reprise**, et le point est écrit de façon atomique
(répertoire temporaire puis renommage). Que la machine s'arrête ou qu'une autre session recrée les
conteneurs, on repart du dernier point **valide** — le début d'une journée simulée — et la
vérification a lieu au démarrage du contrôleur, donc avant qu'une seule décision ne soit prise.


---

## Extension du 2026-09-19 (ticket 077, lot K)

L'identité portait onze champs. Elle en porte huit de plus, tous des **réglages d'expérience** :
chaînage des véhicules, verrou de retour au domicile, seuil de troncature du tirage, seuil de choc
en mémoire, fenêtre et plafond du bloc « ce qui a changé récemment », plancher d'entrées avant
réflexion, météo tirée par agent.

**Pourquoi.** Les quatre premiers avaient été posés dans `config/config.yaml` le 18 septembre et
ne figuraient nulle part ailleurs. Trois bras d'expérience aux réglages opposés portaient donc la
**même identité** — le défaut exact que ce ticket corrigeait pour le modèle, le prompt et la
population, reparu par une autre porte.

**Effet de bord assumé :** un run antérieur au 2026-09-19 n'est plus reprenable. Son identité ne
porte pas ces champs, et le refus le dit — « absent du run repris » et non « None au run repris »,
pour que la cause cherchée soit l'âge du run et non un réglage différent. On ne sait pas sous
quelles valeurs ces runs ont tourné ; les reprendre reviendrait à le supposer.
