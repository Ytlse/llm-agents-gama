# Chocs déclarés (ticket 079)

Un choc, c'est **un retard chiffré** plus **une phrase vécue**, posés sur des agents désignés à
des jours désignés. Il ne coupe aucune ligne et ne dégrade aucune offre : l'agent décide en voyant
l'offre nominale, puis encaisse. C'est le **régime subi**.

## Lancer un run avec un choc

```bash
make run OFFLINE=1 CACHE=0 CHOC=c3_panne_reseau
```

Le cache est coupé volontairement : sa clé ne porte aucune durée, une décision prise avant le choc
pourrait être resservie pendant. Une `[ALARME]` se lève si on l'oublie.

## Pourquoi les textes sont en anglais

Le dispositif entier est passé à l'anglais (ticket 074) : prompts, gabarits, couche de rendu. Une
phrase française dans un prompt anglais réintroduirait exactement le facteur que la bascule a
supprimé. Le format n'impose aucune langue ; ces exemples si.

## Ce qu'un `vecu` peut dire, et ce qu'il ne peut pas

Il **raconte** ce que l'agent a vécu. Il ne lui **dicte** rien.

| Admis | Refusé au chargement |
|---|---|
| « I was stuck for an hour on the ring road » | « avoid the ring road tomorrow » |
| « Flat tyre, hands covered in grease » | « you should take the metro instead » |

Le refus est franc, pas un avertissement : un avertissement au milieu d'un journal de run n'alerte
personne, et une consigne qui passe ne biaise pas un peu — elle fabrique exactement le résultat
qu'on prétend mesurer.

Depuis le 2026-09-19, il ne **conclut** pas davantage. Un verdict sur un mode (« I no longer trust
this car », « this bus line is unreliable ») et une intention pour demain (« I am thinking about
not using this car anymore », « from now on I will take the metro ») sont refusés au même titre.
La croyance est ce que la réflexion de l'agent doit produire ; l'écrire ici revient à mesurer sa
propre consigne. Un doute reste admis — « I am starting to wonder whether this is worth it » — et
un fait passé aussi, même modal : « I had to sort out another way of getting around ».

## Combien de fois par jour

`cadence: trajet` (défaut) — chaque trajet éligible subit le choc : un bouchon dure toute la
journée. `cadence: jour` — seul le premier : une panne réparée ne se reproduit pas à l'identique
trois heures plus tard. Le défaut est journalisé au chargement, une valeur inconnue est refusée.

## Les valeurs sont un scénario déclaré

Retards et durées ne sont pas mesurés sur une source : ce sont des hypothèses assumées, avec la
référence en regard quand elle existe. Elles se discutent ; elles ne se présentent pas comme des
faits.

## Limite connue

`c2_crevaison` déclare au jour suivant que le vélo est immobilisé, mais **le vélo reste
disponible** dans le filtre d'éligibilité : seul le souvenir porte l'indisponibilité. Rendre un
mode réellement indisponible touche la décision partagée avec la plateforme, et sort de ce lot.
