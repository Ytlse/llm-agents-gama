"""lancer_experience_rf.py — Joue le témoin random forest comme une expérience, une fois.

**Pourquoi un lanceur ponctuel plutôt qu'un câblage.** Faire du témoin une famille de plein
droit demande deux lignes : une entrée dans `FAMILLES` (`experiences/decideur_modele.py`) et
une dans `POLICY_FORMATS` / `load_policy` (`scripts/synthesis/model_on_common_set.py`). Ces
deux fichiers sont ceux que le **ticket 043** (régression logistique à noyau) modifie en ce
moment, et qui ajoute exactement une entrée aux mêmes tables. Y écrire en parallèle, c'est
écraser l'un des deux travaux.

Ce script contourne l'attente sans rien falsifier : il **remplace `load_policy` dans l'espace
de noms du décideur**, au moment de l'exécution, puis laisse la plateforme faire tout le
reste — chemin de décision, renormalisation sur l'offre OTP, tirage, compteurs, scoring,
`execution.yaml`. L'exécution produite est une vraie exécution, calculée par le code de la
plateforme. Rien n'est recopié à la main : un `scores.json` écrit au clavier ne serait plus
comparable au 6,1734 du logit, puisque l'un sortirait du code de scoring et l'autre de nous.

⚠ **Ce qu'on perd, et qui est assumé (décision du 2026-09-11).** L'expérience produite n'est
**pas rejouable par la CLI** : `python -m experiences lancer --experience exp_rf_jtir_nosim`
échouera sur un format d'artefact inconnu tant que les deux lignes ne sont pas posées. Il
faudra repasser par ce script. Le fait est écrit dans l'`experience.yaml` produit, pour que
personne ne le découvre en essayant.

Usage :
    python -m scripts.progedo_logit.lancer_experience_rf [--vers NOM] [--definir-seulement]

Hors ligne côté modèle (aucun appel LLM, aucun quota) ; l'offre d'itinéraires vient d'OTP
comme pour les autres expériences `sans_simulateur`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE / "services" / "llm-agents") not in sys.path:
    sys.path.insert(0, str(RACINE / "services" / "llm-agents"))

ARTEFACT = "scripts/progedo_logit/rf_mode_choice_policy.json"

#: `exp_mnl_jtir_nosim` désigne la population par son chemin DANS LE CONTENEUR
#: (`/data/eqasim-output/…` ← bind sur `data/population/`). Ce témoin doit tourner sur
#: l'hôte : le conteneur `controller` porte scikit-learn 1.9.0 quand la forêt a été estimée
#: sous 1.8.0, et les deux ne donnent pas la même forêt — mesuré, pas supposé (exactitude
#: +0,000188, CEL +0,0008). Seul ce champ change ; **l'empreinte d'identité de la population
#: est le SHA du fichier**, pas son chemin, donc la comparaison avec les autres familles
#: reste exacte.
POPULATION_CONTENEUR = "/data/eqasim-output/population_1000_AAMAS"
POPULATION_HOTE = "data/population/population_1000_AAMAS"
DERIVE_DE = "exp_mnl_jtir_nosim"
NOM_DEFAUT = "exp_rf_jtir_nosim"

#: Avertissement déposé À CÔTÉ de l'experience.yaml. Une expérience qu'on ne peut pas
#: relancer par la voie normale doit le dire d'elle-même — le découvrir en essayant coûte une
#: demi-heure. Pas *dans* l'`experience.yaml` : son schéma est strict et refuse toute clé hors
#: contrat, ce qui est une bonne chose (une expérience ne doit pas porter de champ libre que
#: personne ne valide). Un fichier voisin se voit en ouvrant le dossier, et ne triche pas avec
#: le schéma.
LISEZ_MOI = """# exp_rf_jtir_nosim — NON REJOUABLE par la CLI

Témoin **random forest** du [ticket 044](../../../docs/tickets/ticket_044_temoin_random_forest.md),
lancé par `scripts/progedo_logit/lancer_experience_rf.py`.

## Pourquoi ce fichier existe

Ce script enregistre la famille `rf` **au moment de l'exécution**, sans l'écrire dans les
tables de la plateforme. Conséquence directe :

```
python -m experiences lancer --experience exp_rf_jtir_nosim     # ÉCHOUE
```

L'exécution échoue sur un format d'artefact inconnu (`rf_mode_choice_policy`). **Pour
relancer, repasser par le script :**

```bash
python -m scripts.progedo_logit.lancer_experience_rf
```

## Ce qu'il faudrait pour la rendre rejouable

Deux lignes, pas davantage :

- `rf_mode_choice_policy: "rf"` dans `FAMILLES` (`services/llm-agents/experiences/decideur_modele.py`)
- `rf_mode_choice_policy` dans `POLICY_FORMATS` et son branchement dans `load_policy`
  (`scripts/synthesis/model_on_common_set.py`)

Elles ont été laissées de côté le 2026-09-11 parce que le **ticket 043** (régression
logistique à noyau) modifiait ces deux fichiers au même moment, et y ajoutait exactement une
entrée aux mêmes tables. Écrire en parallèle aurait écrasé l'un des deux travaux.

## Ce qui n'a PAS été bricolé

L'exécution est une **vraie exécution** : chemin de décision, renormalisation sur l'offre OTP,
tirage, compteurs et scoring sont le code de la plateforme. Aucun `scores.json` n'a été écrit
à la main — un composite tapé au clavier ne serait pas comparable à celui du logit ou du
booster, puisque l'un sortirait du code de scoring et l'autre de nous.

Le décideur **réajuste la forêt** au chargement (~10 s, aucun arbre sérialisé : 1 200 arbres
et 3 740 500 nœuds pèseraient ~150 Mo), puis **vérifie qu'elle reproduit les métriques
publiées** avant de décider quoi que ce soit.

## Pourquoi elle tourne sur l'hôte et non dans le `controller`

Le conteneur porte **scikit-learn 1.9.0**, la forêt a été estimée sous **1.8.0**, et les deux
ne donnent pas la même forêt — mesuré et non supposé : exactitude +0,000188, CEL +0,0008. Le
garde-fou de reproduction refuse donc de démarrer dans le conteneur, ce qui est son travail.

Conséquence sur la définition : `population.chemin` désigne le chemin **hôte**
(`data/population/…`) là où `exp_mnl_jtir_nosim` désigne le chemin conteneur
(`/data/eqasim-output/…`). C'est le même fichier des deux côtés du bind, et l'empreinte
d'identité de la population est **son SHA**, pas son chemin : la comparaison avec les autres
familles reste exacte.

(Le conteneur n'a de toute façon ni `pyarrow` ni `fastparquet` ; c'est pourquoi le rejeu passe
par une matrice `.npz` de 1,4 Mo que numpy seul sait relire, et non par le parquet.)
"""


def enregistrer_famille_rf() -> None:
    """Rend la famille `rf` visible du décideur, pour la durée de ce processus seulement.

    Le décideur importe `load_policy` dans **son** espace de noms
    (`from scripts.synthesis.model_on_common_set import load_policy`) : le remplacer ici ne
    touche ni le module d'origine ni le disque. Le libellé de famille reste **dérivé du
    format** de l'artefact, jamais écrit en dur — c'est ce qui empêche une exécution du RF de
    s'annoncer « lightgbm » dans les traces, et un libellé faux est pire qu'un libellé absent.
    """
    from experiences import decideur_modele
    from scripts.progedo_logit.mode_choice_rf import RF_FORMAT, charger_rf
    from scripts.synthesis.model_on_common_set import load_policy as load_officiel

    decideur_modele.FAMILLES[RF_FORMAT] = "rf"

    def load_policy(path, spec):
        artefact_lu = json.loads(Path(path).read_text(encoding="utf-8"))
        if artefact_lu.get("format") == RF_FORMAT:
            return charger_rf(Path(path), spec)
        return load_officiel(path, spec)

    decideur_modele.load_policy = load_policy
    print(f"[lanceur] famille « rf » enregistrée pour ce processus ({RF_FORMAT})")


def _chemin_population_hote(chemin_yaml: Path) -> None:
    """Ramène le chemin de population du conteneur vers l'hôte, si besoin.

    Une substitution de chemin, rien de plus : le fichier `population.json` est le même des
    deux côtés du bind, et c'est **son SHA** qui sert d'empreinte d'identité. Faite
    explicitement plutôt que subie — l'alternative était de découvrir « population
    introuvable » au lancement.
    """
    contenu = chemin_yaml.read_text(encoding="utf-8")
    if POPULATION_CONTENEUR not in contenu:
        return
    if Path(POPULATION_CONTENEUR).exists():
        return                      # on tourne dans le conteneur : rien à changer
    chemin_yaml.write_text(
        contenu.replace(POPULATION_CONTENEUR, str(RACINE / POPULATION_HOTE)),
        encoding="utf-8")
    print(f"[lanceur] chemin de population ramené sur l'hôte ({POPULATION_HOTE}) — "
          "même fichier, même SHA d'identité")


def definir(vers: str) -> int:
    """Crée l'expérience en dupliquant celle du logit — un seul paramètre change."""
    from experiences import cli

    dossier = RACINE / "data" / "experiences" / vers
    if dossier.exists():
        print(f"[lanceur] {vers} existe déjà — définition inchangée")
        _chemin_population_hote(dossier / "experience.yaml")
        (dossier / "LISEZ-MOI.md").write_text(LISEZ_MOI, encoding="utf-8")
        return 0
    code = cli.main(["dupliquer", "--de", DERIVE_DE, "--vers", vers,
                     "--artefact", ARTEFACT])
    if code != 0:
        return code
    _chemin_population_hote(dossier / "experience.yaml")
    (dossier / "LISEZ-MOI.md").write_text(LISEZ_MOI, encoding="utf-8")
    print(f"[lanceur] {vers} définie depuis {DERIVE_DE}, artefact {ARTEFACT}")
    print(f"[lanceur] avertissement « non rejouable » écrit : {dossier / 'LISEZ-MOI.md'}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vers", default=NOM_DEFAUT, help=f"nom de l'expérience (défaut : {NOM_DEFAUT})")
    parser.add_argument("--definir-seulement", action="store_true",
                        help="crée l'experience.yaml sans lancer l'exécution")
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(line_buffering=True)

    chemin_artefact = RACINE / ARTEFACT
    if not chemin_artefact.exists():
        raise SystemExit(
            f"Artefact du témoin absent : {ARTEFACT}. Produisez-le avec "
            "`make forest FOREST_ARGS=--artefact`.")

    enregistrer_famille_rf()
    code = definir(args.vers)
    if code != 0 or args.definir_seulement:
        return code

    from experiences import cli
    print(f"[lanceur] lancement de {args.vers} — le décideur réajuste la forêt (~10 s), "
          "puis vérifie qu'elle reproduit les métriques publiées")
    return cli.main(["lancer", "--experience", args.vers, "--ne-pas-attendre-fenetre"])


if __name__ == "__main__":
    raise SystemExit(main())
