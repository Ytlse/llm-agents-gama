# Directives et Instructions de Soumission — AAMAS 2027

> **Conférence :** La 26e Conférence internationale sur les agents autonomes et les systèmes multi-agents (AAMAS 2027)  
> **Lien OpenReview :** [https://openreview.net/group?id=ifaamas.org/AAMAS/2027/Conference](https://openreview.net/group?id=ifaamas.org/AAMAS/2027/Conference)

---

## 0. Calendrier officiel

Relevé le 2026-09-21 sur la page de l'appel principal
([warwick.ac.uk](https://warwick.ac.uk/fac/sci/dcs/aamas2027/calls/call-for-main-track/)).
Toutes les échéances tombent en fin de journée, *Anywhere on Earth* (UTC−12).

| Étape | Date |
|---|---|
| Author registration on OpenReview | **17 septembre 2026** |
| Abstract submission | **1er octobre 2026** |
| Paper submission | **8 octobre 2026** |
| Rebuttal period | 20 – 24 novembre 2026 |
| Author notification | 21 décembre 2026 |
| Camera-ready paper | 25 janvier 2027 |
| Conférence | 3 – 7 mai 2027 |

Contact soumission : `aamas2027pcs@gmail.com`.

**L'enregistrement des auteurs sur OpenReview est antérieur à celui du résumé**, et cette
page-ci n'en donnait que la règle relative (« au moins 2 semaines avant »), pas la date. Rien
ne pouvait donc alerter à son approche.

---

## 1. Format et Contraintes Générales

- **Langue :** Les articles doivent être rédigés en anglais.
- **Évaluation :** Évaluation à double insu (*double-blind review*).
- **Format de fichier :** PDF uniquement.
- **Support typographique :** L'utilisation de **LaTeX est obligatoire**.
- **Longueur maximale :**
  - **8 pages** maximum pour le texte principal, les figures et les tableaux.
  - Des **pages supplémentaires illimitées** pour les références bibliographiques uniquement.
- **Mise en page :**
  - Respect strict des fichiers de style et paramètres de mise en page officiels d'AAMAS.
  - Modification des fichiers de style (`.sty`) ou altération des paramètres de mise en page interdites.
  - Tout recours excessif à des astuces de mise en page pour faire tenir le texte sur 8 pages est interdit.

---

## 2. Calendrier & Procédure sur OpenReview

1. **Compte OpenReview :**
   - Chaque auteur doit obligatoirement posséder un compte OpenReview valide.
   - **Date limite de création de compte :** au moins **2 semaines avant** la date limite de soumission du résumé.
2. **Enregistrement du Résumé (Abstract) :**
   - **Obligatoire 1 semaine avant** la date limite de soumission finale.
   - Contenu : Texte brut d'**environ 100 à 300 mots**. Le texte officiel dit « registering an abstract of your paper (of **around** 100-300 words in plain text) » : c'est une fourchette indicative, pas un plafond dur, et elle porte sur le champ texte d'OpenReview. Le résumé composé dans le PDF n'a pas de limite de mots propre — seules les 8 pages du papier le bornent. <!-- source : https://warwick.ac.uk/fac/sci/dcs/aamas2027/calls/instructions/, relevé le 2026-09-21 ; le mot « around » manquait à la transcription antérieure -->
   - Informations complémentaires requises : Sélection des mots-clés caractérisant l'article.
3. **Choix du Domaine (Track) :**
   - L'article doit être rattaché à l'un des domaines officiels de l'AAMAS.
   - Les responsables de domaine (*area chairs*) vérifieront la correspondance du résumé avec le domaine choisi. Si nécessaire, une réattribution sera tentée, mais l'article sera **rejeté d'emblée (*desk reject*)** si aucun domaine approprié ne correspond.
4. **Révisions :**
   - Recommandation de ne pas attendre le dernier moment. Le document peut être révisé et re-soumis autant de fois que souhaité jusqu'à la date limite.
5. **Statut Étudiant :**
   - Si l'auteur principal (premier auteur ou co-premier auteur) est étudiant (doctorat ou autre niveau), cocher la case : *« L'auteur principal est étudiant »*.
   - Cette information reste confidentielle (non transmise aux évaluateurs) et sert exclusivement pour le prix **Pragnesh Jay Modi** du meilleur article étudiant.
6. **Liste des Auteurs :**
   - Aucune modification de la liste ou de l'ordre des auteurs n'est autorisée après l'acceptation de l'article.

---

## 3. Matériel Supplémentaire (*Supplementary Material*)

- **Contenu autorisé/encouragé :** Versions complètes de démonstrations/preuves, informations détaillées sur les expériences, code source, jeux de données, ou tout élément favorisant la reproductibilité des résultats.
- **Format et taille :**
  - Fichier **ZIP unique**.
  - Taille maximale : **25 Mo**.
- **Règles d'évaluation :**
  - Les évaluateurs **ne sont pas tenus** de consulter le matériel supplémentaire.
  - **Toute information essentielle** à la compréhension ou à l'évaluation du papier doit obligatoirement figurer dans les 8 pages de l'article principal (ex. éviter de placer l'essentiel des preuves théoriques uniquement en annexe).
  - Ne pas utiliser le matériel supplémentaire pour soumettre une version étendue ou corrigée de l'article.
- **Anonymat :** Le matériel supplémentaire doit respecter scrupuleusement les consignes de double anonymat.
- **Ce que la convention `lil-1750` interdit dans le ZIP :** les microdonnées EMC² 2023 sont diffusées sous convention nominative par Quetelet-Progedo-Diffusion, qui engage à **ne pas céder les données sous quelque forme que ce soit**. Conséquence directe sur le matériel supplémentaire : ni les fichiers d'enquête, ni le jeu de test scellé de 13 045 trajets, ni aucun fichier qui en reproduirait le contenu n'entrent dans le ZIP, ni dans l'archive Zenodo/GitHub de la version publiée. Le statut des **ressources dérivées** (lois agrégées, découpages de zones fines) n'est pas tranché : à vérifier avant de constituer l'archive. Engagements complets : [`../sources/ENGAGEMENT_DONNEES_EMC2.md`](../sources/ENGAGEMENT_DONNEES_EMC2.md).
- **Garantie de reproductibilité (Action pour le papier) :** Si un relecteur ne peut pas rejouer les expériences parce que les microdonnées d'enquête sont sous embargo / convention nominative, le code d'inférence/évaluation et la cohorte synthétique scellée (v5, $N = 1\,000$, $3\,299$ déplacements) doivent être intégralement décrits et rendus reproductibles dans le Supplementary Material (ZIP anonyme de 25 Mo). Voir [`actions.md`](actions.md) § 1 et [`ameliorations.md`](ameliorations.md) § 5.
- **Ce que la même convention oblige :** citer la source selon le modèle annexé à la convention (Annexe G du chapitre 99), et **informer le diffuseur** de la soumission en lui envoyant les références — y compris si l'article n'est pas retenu. Le journal des envois est tenu dans le même fichier.
- **Publication & Archivage Open Access :**
  - L'IFAAMAS ne publiera pas directement les fichiers zip supplémentaires.
  - En cas d'acceptation, les lecteurs de la version finale publiée auront accès aux mêmes informations que les relecteurs.
  - Les auteurs doivent rendre le matériel supplémentaire accessible publiquement sous forme d'archives au moment de la publication (ex. **Zenodo** ou **GitHub** pour le code/données, **arXiv** pour les annexes techniques et preuves). La version finale de l'article devra inclure une référence vers ces archives.

---

## 4. Politique relative aux Technologies d'Assistance à l'IA

*(LLMs, Chatbots, Générateurs d'images)*

- **Authorship :** Les outils d'IA ne peuvent pas être crédités comme auteurs ou co-auteurs.
- **Usages autorisés :**
  - Mise en forme et perfectionnement du style/texte.
  - Génération de code et de scripts pour preuves de concept, démonstrations ou expériences.
- **Transparence et méthodologie :**
  - Si l'IA est utilisée pour la formulation d'hypothèses, la méthodologie ou la conception expérimentale, des détails complets doivent être fournis dans le texte ou les annexes (notamment le **prompt exact**, l'**outil d'IA** et sa **version**).
- **Responsabilité des auteurs :**
  - Les auteurs restent entièrement responsables de l'exactitude, de l'absence de plagiat, de la vérabilité des citations et de la prévention des biais introduits par les outils.
  - Les articles comportant des citations erronées ou un usage inapproprié de l'IA risquent un **refus d'emblée**.
  - Les évaluateurs ont l'interdiction d'utiliser des outils d'IA pour rédiger leurs rapports d'évaluation.
- **Éléments multimédias et images générées par IA :**
  - Autorisés **uniquement** si l'IA générative est le sujet même de la recherche et que ces éléments constituent une preuve qualitative des résultats.

---

## 5. Politique relative aux Doubles Soumissions et "Thin Slicing"

- **Interdiction de double soumission :** Interdiction de soumettre simultanément un travail substantiellement similaire à AAMAS 2027 et à une autre instance d'archivage, ou de le soumettre ailleurs pendant son évaluation à AAMAS 2027.
- **Exceptions non archivantes :** Les serveurs de prépublication (ex. arXiv) et les ateliers sans actes officiels (*non-archival workshops*) ne sont pas considérés comme des instances d'archivage.
- **Soumissions fractionnées ("Thin Slicing") :** Les soumissions constituant un découpage trop fin ou dont la publication rendrait une autre soumission similaire trop incrémentale peuvent être refusées.
- **Sanction :** Le non-respect de ces rules peut entraîner un **refus d'emblée (*desk reject*)** à n'importe quel stade du processus d'évaluation.
