# Ticket 108 — Une injection déclarée qui ne se produit pas doit se voir

> Le statut de ce ticket vit dans `scripts/dashboard/tickets_status.yaml`, seule source de
> vérité. Ouvert le 2026-09-24, à la demande de l'auteur, en relisant le run
> `2026-09-23_20_35` avec le témoin du ticket 106.

---

## 1. La question, en une phrase

Un run peut **déclarer** des jours d'injection et n'en **produire** aucun, ou moins que
déclaré, sans que rien ne le dise — et continuer à mesurer l'effet d'un événement qui n'a pas
eu lieu.

## 2. Ce qui s'est passé, le 2026-09-23

Le run `experiments/archive/2026-09-23_20_35` porte un `evenement.yaml` qui déclare **deux**
jours d'injection pour `c6_voiture_suspecte` :

```yaml
jours:
- jour: 15
  retard_min: 45
  vecu: The engine stalled on the expressway. […]
- jour: 16
  retard_min: 20
  vecu: The warning lights came on again. […]
```

`evenements.jsonl` n'en porte **qu'une** — celle du jour 15. La seconde ne s'est pas produite,
et c'est mécaniquement normal : l'exposition est restreinte au mode `car`
(`exposition.modes: [car]`), et après le choc du jour 15 l'agent ne choisit plus la voiture.
Une injection conditionnée au mode ne peut pas avoir lieu si le mode a disparu — et le choc
lui-même est ce qui l'a fait disparaître.

Rien dans le run ne le signale. Ni alarme, ni ligne de journal, ni section de `make report`.
Le fait a été découvert à la main, en comparant les deux fichiers.

## 3. Pourquoi c'est la même classe de défaut que le ticket 106

Le ticket 106 a été ouvert parce qu'un run avait tourné 2 h 22 en mesurant l'effet d'un
souvenir qui n'avait jamais atteint la mémoire longue. Il pose un témoin **en aval** de
l'injection : le texte est-il ressorti de la consolidation ?

Ce ticket-ci pose la question **en amont** : le texte a-t-il seulement été injecté ? Le témoin
du 106 ne peut pas y répondre — il ne contrôle que ce qui est injecté, et une injection qui
n'a pas lieu ne le réveille jamais. Les deux trous sont côte à côte, et ils produisent la même
conséquence : une mesure qui porte sur rien, et qui ne le dit pas.

## 4. Ce qu'il faut livrer

### 4.1 Le rapprochement déclaré / produit

En **fin de run**, comparer les jours d'injection que la déclaration prévoyait aux lignes
réellement écrites dans `evenements.jsonl`, par agent exposé. Trois comptes suffisent :
déclaré, produit, manquant.

⚠ Le rapprochement n'est pas trivial pour toutes les formes de déclaration. La forme A
(`jours:`) énumère des jours de run et se rapproche directement. La forme B (canal `lu`,
`calendrier:`) tire une date par cible : ce qui est « déclaré » y est un calendrier, pas une
liste, et le rapprochement doit se faire cible par cible. Traiter la forme A d'abord, et dire
explicitement que la forme B ne l'est pas encore plutôt que de rendre un compte faux.

### 4.2 L'alarme, et ce qu'elle doit nommer

Une ligne `[ALARME]` par écart, avec de quoi agir sans rouvrir la session : l'agent,
l'événement, le jour déclaré, et **la raison plausible** quand elle est lisible — le mode
d'exposition n'a pas été choisi ce jour-là, l'agent n'a pas voyagé, le run s'est arrêté avant.
Une alarme qui dit seulement « injection manquante » fera rouvrir les fichiers à la main,
c'est-à-dire exactement ce qu'on veut éviter.

### 4.3 La section de rapport

`make report` rend le rapprochement, **dans les deux sens** : le compte des injections
produites quand tout va bien, pas seulement les manquantes. Un rapport muet quand tout va bien
ne permet pas de distinguer « aucune injection manquante » de « le rapprochement ne tourne
plus ».

### 4.4 Le cas particulier qui a tout déclenché

Une injection conditionnée à un mode que le choc précédent a fait disparaître n'est pas un
bug : c'est un effet de bord du protocole, et il se reproduira à chaque déclaration
multi-jours restreinte par mode. La sortie doit le nommer comme tel, pas comme une panne.
C'est une information de protocole — elle dit à l'auteur que sa déclaration de choc demande
plus que ce que l'expérience peut produire.

## 5. Ce qui ne change pas

- **Aucun run n'est arrêté par ce chemin.** Même geste que le ticket 106 : on constate et on
  alarme. Une injection manquante se découvre en fin de run, quand il n'y a plus rien à
  sauver ; arrêter n'apporterait rien.
- Le protocole d'exposition n'est pas modifié. Ce ticket rend visible ce qui se produit, il ne
  change pas ce qui se produit.
- La déclaration (`evenement.yaml`) n'est pas modifiée non plus.

## 6. Critères d'acceptation

- [ ] Un run dont toutes les injections déclarées ont eu lieu le dit explicitement.
- [ ] Un run auquel il manque une injection lève une `[ALARME]` nommant agent, événement et
      jour déclaré.
- [ ] La raison est nommée quand elle est lisible (mode non choisi, agent immobile, run
      interrompu).
- [ ] `make report` rend le rapprochement dans les deux sens.
- [ ] La forme B (`calendrier:`) est traitée, ou explicitement déclarée hors champ dans la
      sortie — jamais comptée à zéro en silence.
- [ ] Le run `2026-09-23_20_35` est rejoué par l'outil et signale l'injection manquante du
      jour 16.
- [ ] Aucun run n'est arrêté par ce chemin.
- [ ] Suite complète au vert.

## 7. Voir aussi

- Ticket 106 — le témoin en aval : le souvenir injecté atteint-il la mémoire longue.
- Ticket 100 — canal unique d'événement, et la forme de `evenement.yaml`.
- Ticket 105 — arrêt sur replis, d'où vient le geste `[ALARME]` + marqueur.
