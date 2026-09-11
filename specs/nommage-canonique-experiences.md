# Le nom d'une expérience se calcule, il ne se saisit plus

## Intention

Le nom d'une expérience **est** son identité : il devient le dossier
`data/experiences/<nom>/`, la clé de dédoublonnage de la file FIFO et la cible de
`pause` / `arreter`. Tant qu'il était tapé à la main, rien ne garantissait qu'il dise les
paramètres : le 2026-09-07, trois exécutions de `Prompt_Minimaliste` ont mesuré gemini,
gpt-oss et mistral sous une seule identité, et `experience.yaml` n'a gardé que le dernier
décideur. Le 2026-09-08, `Prompt_Minimaliste_qwen3.6-27b` et
`Prompt_Minimaliste_qwen_qwen3.6-27b` portaient deux noms pour un jeu de paramètres
strictement identique, et `Prompt_Minimaliste_GPT-OSS-120b` annonçait un modèle
(`gpt-oss-120b`) que son fichier ne servait pas (`mistral-small-latest`).

Le nom est donc désormais **dérivé** des paramètres. Deux expériences qui diffèrent d'un
paramètre nommé portent deux noms ; deux expériences qui ne diffèrent d'aucun paramètre
sont *la même expérience*, avec deux exécutions.

## Règles

- **N1** — Le nom n'est plus saisi. Le formulaire l'affiche, calculé, et ne le laisse pas
  modifier. Le champ texte disparaît, avec sa validation et sa proposition de correction.
- **N2** — Grammaire, segments séparés par `_`, ordre fixe :
  `exp_<décideur>[_<prompt>][_<calendrier>][_<écarts>][_t<T>]_<mode>`.
- **N3** — Le **décideur** est toujours nommé : `passerelle` → le slug de son modèle (N4) ;
  `antigravity` → `agy-<slug-du-modele>` ; `aleatoire` → `alea` ; `duree_minimale` → `durmin` ;
  `majoritaire_voiture` → `majvoiture` ; `modele` → `lgbm` ; `rejeu` → `rejeu`. Un artefact LightGBM
  autre que celui du dépôt ajoute son nom de fichier (`lgbm-<stem>`) ; un rejeu ajoute l'horodatage
  compacté de l'exécution rejouée (`rejeu-260907-2209`).
- **N4** — **Slug du modèle**, algorithmique (aucune table à tenir à jour) : minuscules,
  préfixe fournisseur avant `/` retiré s'il répète la famille, mots de bruit jetés
  (`latest`, `preview`, `instruct`, `chat`, `hf`, `awq`, `gguf`), points supprimés, mots
  joints par `-`. Au-delà de **12 caractères**, les mots sans chiffre placés après le
  premier tombent à leur initiale ; si c'est encore trop long, on tronque.
  `gemini-3.1-flash-lite-preview` → `gemini-31-fl` · `mistral-small-latest` → `mistral-s` ·
  `qwen/qwen3.6-27b` → `qwen36-27b` · `gpt-oss-120b` → `gpt-oss-120b`.
- **N5** — Le **prompt** est nommé si et seulement si le décideur est `passerelle` ou `antigravity` :
  ailleurs la variante n'a aucun effet sur la décision, et la nommer ferait croire à un prompt
  (`Light_GBM` portait `minimal_persona`). Abréviation = trois premières lettres de chaque
  mot, dix caractères au plus : `minimal_persona` → `minper`, `b_min` → `bmin`,
  `expert_chaine` → `expcha`. Variante absente (= prompt **actif** de la passerelle) →
  `actif`, parce que « le prompt du jour » n'est pas un paramètre reproductible.
- **N6** — Le **calendrier** n'est nommé que s'il s'écarte du cas simple : `aleatoire` →
  `jtir`, `propre` → `jpers` ; `commune` reste muette quand sa date est le jour du jeu, et
  donne `j<MMJJ>` sinon.
- **N7** — **Écarts** : tout paramètre égal à sa valeur de référence
  (`nommage.DEFAUTS_NOMMAGE`) est muet ; sinon il ajoute son segment, dans un ordre fixe :
  `pop-<slug>`, `jeu-<slug>`, `h<N>j`, `mem`, `ev<N>`, `p<N>`, `c<N>`, `a<N>`, `go<N>`,
  `gt<N>`, `gc<N>`, `gd<N>`, `tol-<4 hex>`.
- **N8** — La **température** et le **mode** sont toujours nommés, même à leur valeur par
  défaut (`t0`, `nosim`) : ce sont les deux réglages qu'on veut lire sans ouvrir le fichier.
  La température ne l'est que pour un décideur qui en a un (`passerelle`, `antigravity`).
- **N9** — Le nom produit satisfait `MOTIF_NOM` par construction (caractères de mot Unicode,
  `-`, `.`, 64 au plus, commence par une lettre ou un chiffre) : il devient un dossier et la
  valeur de `EXP=` développée sans guillemets par `make`. Un générateur qui n'y parviendrait
  pas lève au lieu de rendre un nom douteux.
- **N10** — **Collision.** La *signature* d'une expérience est le sha256 de sa définition
  privée de son identité (`nom`, `derive_de`, `renomme_de`, `executions_connues`). Quand le
  nom calculé est déjà pris :
  - signature **identique** → c'est la même expérience : elle est réutilisée telle quelle,
    sans indice et **sans réécriture** de son fichier ; une exécution s'ajoute à ses archives ;
  - signature **différente** → indice à la façon d'une copie de fichier : `_2`, `_3`… le
    premier libre. Jamais d'écrasure silencieuse.
- **N11** — L'indice ne tombe jamais : si `<base>_2` dépasse 64 caractères, c'est la base
  qui est rognée, pas l'indice.
- **N12** — Le nom d'une expérience **déjà écrite** ne se recalcule jamais : `experience.yaml`
  est autoritaire. Changer la grammaire ne renomme rien. Seule la migration explicite
  (`make experiences-renommer APPLIQUER=1`) renomme, et elle consigne l'ancien nom dans
  `renomme_de` et dans `data/experiences/.renommages.json`.
- **N13** — `experiences definir` refuse un fichier dont le `nom` n'est pas le nom canonique
  de ses paramètres, en affichant le nom attendu. `--accepter-nom` passe outre, pour les
  expériences renommées avant l'existence de la règle.

## Vérifications attendues

- **N2/N3/N8** — un décideur `duree_minimale`, calendrier commun au jour du jeu, tout par
  défaut → `exp_durmin_nosim` ; le même en mode simulateur → `exp_durmin_sim`.
- **N4** — les quatre modèles de la campagne donnent `gemini-31-fl`, `gemini-35-fl`,
  `mistral-s`, `qwen36-27b`, `gpt-oss-120b` ; un modèle inconnu (`acme/foo-bar-9b-latest`)
  donne un slug non vide de 12 caractères au plus.
- **N5** — décideur `modele` avec `variante: minimal_persona` → aucun segment de prompt ;
  décideur `passerelle` avec `variante: null` → `actif`.
- **N6** — `aleatoire` → `jtir` ; `commune` sur le jour du jeu → muet ; `commune` sur un
  autre jour → `j0317`.
- **N7** — parallélisme 16 → `p16` ; mémoire → `mem` ; horizon 5 → `h5j` ; deux événements →
  `ev2` ; tolérances modifiées → `tol-<4 hex>` stable d'un appel à l'autre.
- **N10** — deux définitions identiques à un nom près → le même nom rendu, `reutilise`
  renseigné, aucun dossier créé ; deux définitions différentes qui s'abrègent pareil → la
  seconde reçoit `_2`, la troisième `_3`.
- **N11** — une base de 63 caractères en collision → nom de 64 caractères au plus, terminé
  par `_2`.
- **N13** — un `experience.yaml` nommé à la main → `definir` refuse en citant le nom attendu ;
  avec `--accepter-nom`, il range le fichier.

## Hors du sujet

- Renommer les identifiants du plan AAMAS (`docs/paper/methode/experience_plan/experiments.yaml`) :
  ce sont les identifiants du papier, ordonnés par phase. Le lien avec le disque se fait par
  une clé `nom_runtime:` sur les entrées déjà exécutées.
- Réécrire les entrées passées du changelog qui citent les anciens noms : c'est l'historique.
