# Faire tourner la calibration de prompt sur le cloud Google — guide pas à pas

Ce guide s'adresse à quelqu'un qui **n'a jamais utilisé Google Cloud**. On installe la
campagne de calibration sur une **petite machine gratuite** qui tourne toute seule, jour
après jour, jusqu'à ce que la campagne soit finie.

**Combien ça coûte ?** → **0 €.** La machine est dans l'offre « Always Free » de Google
Cloud, et l'API Gemini est utilisée dans son offre gratuite (500 requêtes/jour). Il faut
juste créer un compte Google Cloud (une carte bancaire est demandée pour vérifier
l'identité, mais rien n'est débité tant qu'on reste dans le gratuit).

**Combien de temps ça prend à installer ?** → ~30 minutes la première fois.

---

## Comment ça marche (en une image)

```
  Ton PC                          La VM gratuite chez Google (tourne 24h/24)
 ┌────────┐   1x upload données  ┌───────────────────────────────────────────┐
 │ .tar.gz├─────────────────────>│  git clone du projet                      │
 │  clé   │                      │  chaque nuit à 3h : run_daily.sh           │
 └────────┘                      │    → consomme les 500 requêtes Gemini      │
                                 │    → s'arrête, reprend le lendemain        │
                                 │  résultats dans calibration.db (SQLite)    │
                                 └───────────────────────────────────────────┘
```

- La campagne complète (50 itérations) **ne tient pas** dans 500 requêtes/jour : elle
  s'étale sur **plusieurs jours**. Ce n'est pas un problème : le programme **sait
  reprendre** exactement où il s'est arrêté. Un réveil automatique chaque nuit suffit.
- Tu n'as **rien à surveiller**. Tu reviens au bout de quelques jours récupérer le
  résultat.

---

## Ce dont tu as besoin avant de commencer

1. Un **compte Google Cloud** : https://console.cloud.google.com (crée un projet, le nom
   n'a pas d'importance).
2. Une **clé API Gemini** (gratuite) : https://aistudio.google.com/apikey → bouton
   « Create API key » → copie la longue chaîne de caractères, garde-la de côté.
3. Le fichier **`data_to_upload.tar.gz`** (il est déjà prêt, dans le dossier `cloud/`
   à côté de ce README). Ce sont les jeux de données de calibration — ils ne sont pas
   dans le dépôt Git, donc il faut les envoyer à la main.

> ℹ️ **Pourquoi uploader des données alors qu'on clone le projet ?**
> Le clone Git apporte le **code**, le prompt de départ et la référence EMC². Mais les
> **jeux gelés** (`train/val/test`) sont volontairement hors Git (ils se régénèrent depuis
> un run de simulation). Comme la VM n'a pas ce run, on lui envoie directement le paquet.

---

## Étape 1 — Installer l'outil `gcloud` sur ton PC (une fois)

`gcloud` est le programme qui permet de piloter Google Cloud depuis ton terminal.

- **Mac** : `brew install --cask google-cloud-sdk`
  (ou suivre https://cloud.google.com/sdk/docs/install)
- Puis connecte-toi : `gcloud auth login` (ça ouvre le navigateur)
- Choisis ton projet : `gcloud config set project TON_ID_DE_PROJET`
  (l'ID de projet est visible en haut de la console Google Cloud)

> 💡 **Tu préfères éviter d'installer `gcloud` ?** Tu peux tout faire depuis le navigateur
> avec **Cloud Shell** (icône `>_` en haut à droite de la console). Dans ce cas, saute les
> commandes `gcloud` de ton PC et tape-les dans Cloud Shell ; pour envoyer le `.tar.gz`,
> utilise le bouton « Upload » (menu ⋮) de Cloud Shell.

---

## Étape 2 — Créer la machine gratuite

Une seule commande (copie-colle, remplace juste rien) :

```bash
gcloud compute instances create calib-vm \
  --zone=us-central1-a \
  --machine-type=e2-micro \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB
```

**Points importants pour rester gratuit :**
- `--machine-type=e2-micro` : le seul type inclus dans « Always Free ». Ne le change pas.
- `--zone` : doit être **`us-central1-a`**, `us-west1-*` ou `us-east1-*` (seules régions
  gratuites). On prend `us-central1-a`.
- `--boot-disk-size=30GB` : la limite gratuite est 30 Go. Ne dépasse pas.

Attends ~30 secondes que la machine démarre.

---

## Étape 3 — Se connecter à la machine

```bash
gcloud compute ssh calib-vm --zone=us-central1-a
```

La première fois, ça crée une clé SSH (laisse la phrase de passe vide en appuyant sur
Entrée). Tu te retrouves avec un terminal **sur la VM** (le nom de la machine apparaît dans
l'invite). Toutes les commandes des étapes 4 à 7 se tapent **dans cette fenêtre**.

---

## Étape 4 — Installer le projet (script automatique)

Sur la VM, récupère juste le script d'installation et lance-le :

```bash
curl -O https://raw.githubusercontent.com/Ytlse/llm-agents-gama/main/scripts/prompt_calibration/cloud/setup_vm.sh
bash setup_vm.sh
```

Le script installe git + Python, clone le projet et prépare l'environnement. Ça prend
quelques minutes. À la fin, il affiche les 2 dernières étapes manuelles (ci-dessous).

> 🔒 **Si le dépôt est privé**, le `git clone` demandera un identifiant. Le plus simple :
> crée un « Personal Access Token » GitHub (Settings → Developer settings → Tokens) et
> utilise-le comme mot de passe. Ou rends le dépôt public le temps de l'installation.

---

## Étape 5 — Envoyer les données et la clé

**5a. Les données** — reviens sur **le terminal de ton PC** (nouvelle fenêtre, ou tape
`exit` puis reconnecte-toi ensuite). Place-toi dans le dossier `cloud/` du projet sur ton
PC, puis :

```bash
gcloud compute scp data_to_upload.tar.gz calib-vm:~ --zone=us-central1-a
```

Puis, **de retour sur la VM**, décompresse au bon endroit :

```bash
tar xzf ~/data_to_upload.tar.gz -C ~/llm-agents-gama/scripts/prompt_calibration/
```

**5b. La clé Gemini** — toujours sur la VM :

```bash
cp ~/llm-agents-gama/scripts/prompt_calibration/cloud/env.example ~/calib.env
nano ~/calib.env
```

Dans l'éditeur, remplace `colle_ta_cle_ici` par ta clé Gemini. Enregistre avec
`Ctrl+O` puis `Entrée`, quitte avec `Ctrl+X`. Puis protège le fichier :

```bash
chmod 600 ~/calib.env
```

---

## Étape 6 — Test : un premier lancement à la main

```bash
bash ~/llm-agents-gama/scripts/prompt_calibration/cloud/run_daily.sh
```

Ça démarre la campagne. Laisse tourner 1–2 minutes puis regarde le journal en direct
(ouvre une 2ᵉ connexion SSH, ou `Ctrl+C` pour rendre la main — **la reprise fait qu'on ne
perd rien**) :

```bash
tail -f ~/calib-logs/$(date +%F).log
```

Tu dois voir des lignes d'itération défiler (mutations, scores). Si tu vois une erreur de
**clé** (`invalid api key`), reprends l'étape 5b. Si tu vois `429`/`quota`, c'est **normal**
en fin de journée : le quota du jour est atteint.

---

## Étape 7 — Automatiser le réveil quotidien (cron)

On demande à la VM de relancer la campagne **chaque nuit à 3h** (le quota Gemini se
réinitialise chaque jour). Sur la VM :

```bash
crontab -e
```

(Choisis `nano` si on te demande l'éditeur.) Ajoute cette **unique ligne** à la fin :

```
0 3 * * *  bash $HOME/llm-agents-gama/scripts/prompt_calibration/cloud/run_daily.sh
```

Enregistre (`Ctrl+O`, `Entrée`) et quitte (`Ctrl+X`). **C'est tout.** La campagne
progressera toute seule, un peu chaque nuit.

> La VM `e2-micro` gratuite reste allumée en permanence : le cron se déclenchera donc bien
> chaque nuit sans que tu aies à te connecter.

---

## Suivre l'avancement (quand tu veux)

Reconnecte-toi à la VM (`gcloud compute ssh calib-vm --zone=us-central1-a`), puis :

```bash
cd ~/llm-agents-gama/scripts/prompt_calibration
source ~/calib-venv/bin/activate
python -m calibration.cli status --config config/cloud.yaml
```

Ça affiche le meilleur prompt trouvé, l'itération en cours et le nombre d'évaluations
consommées. Les journaux jour par jour sont dans `~/calib-logs/`.

---

## Récupérer le résultat final

Quand la campagne est terminée (le `status` n'avance plus, itération = 50), tu peux :

**Option A — le bilan chiffré, sur la VM :**
```bash
python -m calibration.cli finalize --config config/cloud.yaml
```
Ça évalue le meilleur prompt sur le jeu de test et affiche la comparaison avant/après.
Ajoute `--write` pour écrire le prompt calibré dans `prompts.yaml` (voir la doc).

**Option B — rapatrier la base sur ton PC** pour l'ouvrir avec le dashboard local :
```bash
# depuis ton PC :
gcloud compute scp \
  calib-vm:~/llm-agents-gama/scripts/prompt_calibration/calibration_results/calibration.db \
  ./calibration.db --zone=us-central1-a
```
Puis, en local, `calibrate dashboard` sur cette base.

---

## Éteindre / supprimer la machine (pour ne rien laisser tourner)

- **Éteindre** (garde tout, ne consomme rien en Always Free) :
  ```bash
  gcloud compute instances stop calib-vm --zone=us-central1-a
  ```
- **Supprimer définitivement** (une fois le résultat récupéré) :
  ```bash
  gcloud compute instances delete calib-vm --zone=us-central1-a
  ```

---

## Si vraiment tu veux aller plus vite (payant, optionnel)

Le facteur qui ralentit, c'est le **quota gratuit de Gemini** (500 requêtes/jour), pas la
machine. Deux leviers, tous deux peu coûteux :

| Levier | Effet | Coût indicatif |
|---|---|---|
| Passer l'API Gemini en **payant** (retirer le plafond 500/jour) | La campagne se termine en **heures** au lieu de jours | `gemini-flash-lite` est très bon marché ; une campagne entière ≈ **quelques dollars** *(à vérifier sur la grille Gemini du moment)* |
| Garder la VM gratuite | inchangé | 0 € |

La machine `e2-micro` gratuite reste suffisante même en payant (le travail est limité par
le réseau, pas par le processeur).

---

## Aide-mémoire des fichiers de ce dossier

| Fichier | Rôle |
|---|---|
| `README_CLOUD.md` | ce guide |
| `setup_vm.sh` | installe le projet sur une VM Ubuntu vierge (étape 4) |
| `run_daily.sh` | lance/reprend la campagne ; appelé par le cron (étape 7) |
| `env.example` | gabarit du fichier de clé API à copier en `~/calib.env` |
| `data_to_upload.tar.gz` | les jeux gelés à envoyer à la VM (étape 5a) |
| `../config/cloud.yaml` | la configuration de la campagne côté cloud |
