# Article court — reprise de l'article AAMAS 2027 pour la clarté et la lisibilité

Ce dossier porte la refonte de l'article en vue de la soumission AAMAS 2027.
Il est **hors du verrou** de `docs/paper/article/` : on y travaille librement.
`docs/paper/article/` reste la source et n'est pas modifié tant que la refonte
n'est pas validée.

## Pourquoi ce dossier existe

Retour du tuteur, septembre 2026, sur la première version compilée :

> *This first version is sadly really hard to follow and understand.*
> *The sentences seem very brut and sometimes the ideas are not properly structured.*

La relecture détaillée a établi trois causes, dans cet ordre d'importance.

1. **Le format est dépassé d'un facteur trois.** 20 603 mots dans `overleaf/chapters/`
   pour 8 pages maximum, figures et tableaux compris. Un texte trois fois trop long
   qu'on n'a pas encore coupé se lit comme une suite de verdicts : les transitions
   sautent en premier.
2. **L'introduction promet un papier que le corps n'écrit pas.** Le § 1.6 annonce une
   panne de métro sur cinq jours, trois bras et cinq conditions presse ; le chapitre 7
   livre une panne de voiture sur un agent, deux bras et trois conditions.
3. **L'anglais est un décalque phrase à phrase du français.** Le registre d'essai
   français, fait de parataxe, de clivées et d'aphorismes, ne survit pas au passage.
4. **Le PDF relu n'est pas l'article édité.** Cinq des sept `.tex` sont en retard sur leur
   master, de cinq jours pour quatre d'entre eux. L'hypothèse H0, retirée du § 1.3 français
   le 22 septembre, est toujours imprimée dans le PDF. Une partie des remarques du tuteur
   peut donc porter sur du texte déjà corrigé.

## Ordre de travail

La forme d'abord, le fond ensuite. Une réécriture de fond sur un texte dont le style
n'est pas arrêté se refait deux fois.

| Étape | Livrable | État |
|---|---|---|
| 0 | Régénérer les `.tex` depuis leurs masters : le PDF relu est périmé (R18) | **à faire d'abord** |
| 1 | [`CONSIGNES_FORME.md`](CONSIGNES_FORME.md) — dix-huit consignes, chacune avec son test | fait |
| 2 | `verifier_forme.py` — contrôle mécanique de ce qui est automatisable | fait |
| 3 | [`PLAN.md`](PLAN.md) — thèse, trois contributions, sept sections détaillées au niveau 3-4, budget par section, inventaire figures/tableaux/annexes | fait, sous hypothèse du ticket 103 scénario 1 |
| 3 bis | [Ticket 103](../../tickets/ticket_103_carre_jev_gemini_hors_echantillon_et_graines.md) — carré Jev × Gemini hors échantillon sur la seconde cohorte, trois graines par décideur clé | à lancer : 19 exécutions, temps machine |
| 3 ter | [`RELECTURE_V1.md`](RELECTURE_V1.md) (FR, référence) et [`RELECTURE_V1.en.md`](RELECTURE_V1.en.md) (EN) — relecture des huit sections rédigées : 13/20, 30 corrections ordonnées, budget et ordre des coupes | fait ; à appliquer par l'agent |
| 4 | Rédaction section par section, **en anglais d'abord**, par l'agent `article-writer` sous ses vingt règles ; dépôt dans [`sections/`](sections/) | à faire |
| 5 | Rendu français de chaque section validée, par le même agent | à faire |

## Qui écrit

L'agent `.claude/agents/article-writer.md`, réécrit le 2026-09-22 en anglais pour ne pas
mélanger les langues. Il lit le plan, les consignes de forme et les sections déjà écrites,
rédige sous vingt règles de livraison (budget à ±15 %, squelette d'abord, rien deux fois, aucun
terme sans définition amont, aucun nom du dépôt dans le corps, aucun chiffre sans source), se
contrôle avec `verifier_forme.py`, et rend un brouillon avec un bloc de compte-rendu fixe. Il
n'écrit jamais dans `docs/paper/article/`. Il ne se valide pas lui-même.

Invocation : « écris la section 5 », « rédige le § 4.2 selon le plan », « fais le rendu
français de la section 3 ».

## Le contrôle

```bash
python3 docs/paper/article-court/verifier_forme.py docs/paper/article/en/03_Architecture.md
```

Le squelette d'une section, c'est-à-dire la première phrase de chacun de ses
paragraphes mise bout à bout, se lit ainsi :

```bash
python3 docs/paper/article-court/verifier_forme.py --squelette docs/paper/article/en/03_Architecture.md
```

Si ce squelette ne raconte pas la section à lui seul, les paragraphes n'ont pas de
phrase-sujet. C'est le test le plus utile du lot et il ne coûte rien.

## Articulation avec la charte anti-IA

`article-verrou` proscrit quatre familles de marqueurs de rédaction assistée. Trois
d'entre elles poussent vers le défaut que le tuteur signale. L'arbitrage retenu, avec
son détail au § 0 des consignes : **la lisibilité prime, et trois interdictions de la
charte sont levées** — le balisage de section, les connecteurs logiques et la
hiérarchie visuelle. Les autres tiennent.

## Voir aussi

- [`../article/`](../article/) — l'article actuel, verrouillé, qui sert de source.
- [`../article/SOUMISSION_AAMAS_2027.md`](../article/SOUMISSION_AAMAS_2027.md) — contraintes de soumission, dont les 8 pages.
- `.claude/skills/article-verrou` — la charte de style et la procédure de verrou.
