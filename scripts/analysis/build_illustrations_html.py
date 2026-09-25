#!/usr/bin/env python3
"""Générateur de la galerie HTML des illustrations candidates (5 catégories).

Version 2 :
- Correction complète des apostrophes et caractères spéciaux dans les appels JS
- Ajout d'une visionneuse modale enrichie (Zoom +, Zoom -, Plein écran, Précédent, Suivant)
- Bouton explicite "Agrandir" sur chaque carte
- Navigation au clavier (Flèches gauche/droite, Echap)
- Fiches de description complètes sous l'image agrandie
"""

import base64
import html
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
FIG_DIR = RACINE / "docs" / "paper" / "figures"
SORTIE_WORKSPACE = RACINE / "docs" / "paper" / "article-court" / "illustrations_candidates.html"
SORTIE_ARTIFACT = Path("/Users/yvesb/.gemini/antigravity/brain/d040e628-7340-487b-ab63-6d13b3f8873b/illustrations_candidates.html")

ITEMS = [
    # Catégorie 1 : Indispensable
    {
        "cat": 1,
        "cat_nom": "1. Indispensable",
        "cat_color": "emerald",
        "titre": "Schéma causal : Le chemin de l'événement dans la mémoire",
        "section": "§ 6.2 & § 6.4 (Contribution C3)",
        "fichier": "schema_chemin_causal_memoire.png",
        "role": "Prouve le mécanisme interne de la thèse (C3)",
        "pourquoi": "La thèse affirme que la délibération verbalisée apporte la prise en compte d'événements non tabulés dont nous traçons le chemin jusqu'à la décision. Ce schéma montre précisément que sur 4 canaux, seul le bloc 'ce qui a changé récemment' a agi (75/376 prompts) et s'est éteint par usure à J+15 avec 0 contradiction de croyance.",
        "arbitrage": "Recommandation majeure : à intégrer directement en sous-panneau de la Figure 5 ou en ouverture de la Section 6 pour transformer une simple courbe empirique en une démonstration d'architecture cognitive."
    },
    {
        "cat": 1,
        "cat_nom": "1. Indispensable",
        "cat_color": "emerald",
        "titre": "Matrice de croisement 2×3 & Disruption du coût d'inférence",
        "section": "§ 5.3 & § 7.1 (Ticket 103, Pivot du papier)",
        "fichier": "matrice_carre_ticket103.png",
        "role": "Prouve que le CoT ne décide pas et révèle le facteur 50× de coût",
        "pourquoi": "Visualise le résultat pivot : le classifieur typé (qui n'écrit aucun texte) atteint la bande des références tabulaires [3.60, 4.09] et surclasse l'heuristique physique, tout en divisant la facture par 50 (1,06 $ contre 49,28 $ pour 23 026 décisions).",
        "arbitrage": "Figure pivot pour remplacer ou enrichir l'actuelle Fig. 2 si l'espace le permet."
    },
    {
        "cat": 1,
        "cat_nom": "1. Indispensable",
        "cat_color": "emerald",
        "titre": "Échelles de cohortes (c1 vs c2) & Dispersion inter-graines",
        "section": "§ 5.1 & § 5.3 (Ticket 103, Contrôle méthodologique)",
        "fichier": "ticket103_hors_echantillon.png",
        "role": "Désamorce l'objection de robustesse inter-graines et de transportabilité",
        "pourquoi": "Montre que chaque cohorte a son échelle propre (bande tabulaire c1 vs c2) et que la dispersion inter-graines (±0,56) reste très inférieure à la résolution de cohorte (±1,3).",
        "arbitrage": "À placer en tête de l'Annexe H (ou en remplacement partiel de la Fig. 2)."
    },

    # Catégorie 2 : Très utile / Fortement recommandé
    {
        "cat": 2,
        "cat_nom": "2. Très utile",
        "cat_color": "blue",
        "titre": "Fonction d'érosion de la mémoire et oubli exponentiel",
        "section": "§ 3.3 (Mémoire épisodique & Consolidation)",
        "fichier": "ch3_oubli.png",
        "role": "Formalisation mathématique de la persistance des souvenirs",
        "pourquoi": "Illustre la demi-vie de 2,8 jours de la mémoire épisodique et la manière dont la gravité d'un incident étire analytiquement sa durée de service à 15,29 jours.",
        "arbitrage": "Forte valeur scientifique pour convaincre un relecteur MAS. Idéal pour l'Annexe C/D ou en petit format 1 colonne au § 3.3."
    },
    {
        "cat": 2,
        "cat_nom": "2. Très utile",
        "cat_color": "blue",
        "titre": "Frontière de Pareto : Score composite vs Erreur L1 globale",
        "section": "§ 5.1 & § 7.1 (Comparatif multi-objectifs)",
        "fichier": "familles_composite_l1_nuage.png",
        "role": "Visualise le compromis fidélité globale vs fidélité stratifiée",
        "pourquoi": "Montre comment les familles de décideurs se positionnent sur les deux métriques d'erreur et révèle les décideurs dominés.",
        "arbitrage": "Excellente figure d'analyse comparative pour l'Annexe sur les familles de modèles."
    },
    {
        "cat": 2,
        "cat_nom": "2. Très utile",
        "cat_color": "blue",
        "titre": "Évolution des opinions déclarées aux 4 jalons",
        "section": "§ 6.3 & § 6.4 (Opinions Likert & Question témoin)",
        "fichier": "tmp_ch7_affinites_tous_modes.png",
        "role": "Preuve de la rationalité perçue et de l'absence de biais global",
        "pourquoi": "Démontre que la perception de sécurité de la voiture chute brutalement de 8 à 3 puis remonte, tandis que le critère d'écologie (question témoin) reste strictement à 3 tout du long.",
        "arbitrage": "À placer impérativement dans l'Annexe E pour blinder la causalité du choc."
    },

    # Catégorie 3 : Utile si place disponible (Annexes)
    {
        "cat": 3,
        "cat_nom": "3. Utile (Annexes)",
        "cat_color": "indigo",
        "titre": "Dynamique de confiance de la croyance voiture",
        "section": "§ 6.2 & § 6.4 (Extinction par usure)",
        "fichier": "tmp_ch7_croyances_voiture.png",
        "role": "Explication de l'extinction sans contradiction",
        "pourquoi": "Documente la trajectoire de confiance de la croyance voiture et confirme qu'aucune contradiction formelle n'a été enregistrée (l'extinction s'est faite par disparition du souvenir du prompt).",
        "arbitrage": "Matériel supplémentaire / Annexe Adaptation."
    },
    {
        "cat": 3,
        "cat_nom": "3. Utile (Annexes)",
        "cat_color": "indigo",
        "titre": "Audit unitaire selon la distance du déplacement",
        "section": "§ 5.4 (Désaccord unitaire)",
        "fichier": "ch6_audit_distance.png",
        "role": "Complément de l'audit unitaire modal",
        "pourquoi": "Ventile l'exactitude et l'entropie croisée par tranche kilométrique, montrant où les modèles peinent le plus.",
        "arbitrage": "Annexe Audit unitaire."
    },
    {
        "cat": 3,
        "cat_nom": "3. Utile (Annexes)",
        "cat_color": "indigo",
        "titre": "Décomposition modale par tranche de distance",
        "section": "§ 5.2 (Strates physiques)",
        "fichier": "ch99_modes_distance.png",
        "role": "Validation de la reconstruction de la pente modale",
        "pourquoi": "Affiche les 4 modes observés et prédits le long du continuum 0-50+ km.",
        "arbitrage": "Annexe F (Résultats par strate)."
    },
    {
        "cat": 3,
        "cat_nom": "3. Utile (Annexes)",
        "cat_color": "indigo",
        "titre": "Décomposition modale par motif d'activité",
        "section": "§ 5.2 (Strates d'activité)",
        "fichier": "ch99_modes_motif.png",
        "role": "Analyse comportementale par motif (travail, achats, loisirs)",
        "pourquoi": "Montre comment les contraintes d'activité modulent le choix modal.",
        "arbitrage": "Annexe F (Résultats par strate)."
    },
    {
        "cat": 3,
        "cat_nom": "3. Utile (Annexes)",
        "cat_color": "indigo",
        "titre": "Décomposition modale par catégorie socio-professionnelle",
        "section": "§ 5.2 (Strates démographiques)",
        "fichier": "ch99_modes_occupation.png",
        "role": "Diagnostic de la strate résistante (15–19 ans / scolaires)",
        "pourquoi": "Visualise précisément le pic TC des 15–19 ans (47,4 % dans l'enquête) qu'aucun modèle ne parvient à reproduire fidèlement.",
        "arbitrage": "Annexe F (Résultats par strate)."
    },

    # Catégorie 4 : Peu prioritaire
    {
        "cat": 4,
        "cat_nom": "4. Peu prioritaire",
        "cat_color": "amber",
        "titre": "Histogrammes comparatifs Composite vs L1",
        "section": "§ 5.1 (Performances globales)",
        "fichier": "familles_composite_l1_barres.png",
        "role": "Répétition graphique du Tableau 1",
        "pourquoi": "Consomme un espace vertical important pour présenter des barres d'erreurs déjà parfaitement résumées dans le Tableau 1 et la Figure 2.",
        "arbitrage": "Non recommandé dans le corps de l'article court ; tableau textuel préférable."
    },
    {
        "cat": 4,
        "cat_nom": "4. Peu prioritaire",
        "cat_color": "amber",
        "titre": "Nombre brut de trajets en voiture par jour",
        "section": "§ 6.4 (Volume de déplacements)",
        "fichier": "tmp_ch7_voiture_par_jour.png",
        "role": "Volume brut de trajets",
        "pourquoi": "Très bruité par les variations de calendrier hebdomadaire de l'agent. Moins informatif et moins rigoureux que la propension quotidienne de la Fig. 5.",
        "arbitrage": "À écarter au profit de la Fig. 5."
    },
    {
        "cat": 4,
        "cat_nom": "4. Peu prioritaire",
        "cat_color": "amber",
        "titre": "Comparaison chronologique inter-campagnes",
        "section": "Méthodologie interne",
        "fichier": "comparaison_experiences.png",
        "role": "Suivi des versions d'expériences",
        "pourquoi": "Outil de débogage et de suivi d'avancement interne (v1 à v6), sans intérêt pour les relecteurs d'AAMAS.",
        "arbitrage": "À conserver uniquement dans les archives de développement."
    },

    # Catégorie 5 : Presque inutile / Déconseillé
    {
        "cat": 5,
        "cat_nom": "5. Presque inutile",
        "cat_color": "rose",
        "titre": "Carte géographique SIG du réseau de transport toulousain",
        "section": "Contexte territorial",
        "fichier": "toulouse_transport_system.png",
        "role": "Illustration géographique du terrain d'étude",
        "pourquoi": "Figure de confort typique des thèses ou rapports territoriaux. Ne porte aucun message scientifique pour une conférence d'IA multi-agents et consommerait 1/2 page.",
        "arbitrage": "À proscrire du manuscrit pour respecter la limite des 8 pages."
    },
    {
        "cat": 5,
        "cat_nom": "5. Presque inutile",
        "cat_color": "rose",
        "titre": "Grille d'analyse des 20 signes pour l'expérience presse",
        "section": "§ 6.4 & § 7.3 (Campagne de presse en cours)",
        "fichier": "ch7_grille_signes.png",
        "role": "Protocole de mesure sémantique d'articles de presse",
        "pourquoi": "L'expérience est explicitement déclarée comme en cours, sans résultats consolidés. Publier un protocole sans résultats empiriques incite les reviewers à sanctionner l'inachèvement.",
        "arbitrage": "À écarter tant que la campagne n'a pas rendu ses scores."
    },
    {
        "cat": 5,
        "cat_nom": "5. Presque inutile",
        "cat_color": "rose",
        "titre": "Analyse multidimensionnelle des résidus statistiques",
        "section": "§ 5.1 (Calibration statistique)",
        "fichier": "ch6_residu.png",
        "role": "Diagnostic fin des résidus de modélisation",
        "pourquoi": "Graphique complexe et dense, difficile à interpréter sans un long développement textuel impossible dans 8 pages.",
        "arbitrage": "À réserver à une note méthodologique séparée."
    },
    {
        "cat": 5,
        "cat_nom": "5. Presque inutile",
        "cat_color": "rose",
        "titre": "Ingénierie des mutations du prompt expert",
        "section": "§ 4.4 (Protocole d'itération)",
        "fichier": "ch6_ingenierie.png",
        "role": "Trajectoire d'optimisation réflexive du texte",
        "pourquoi": "Relève de l'ingénierie de prompt. Le texte du § 4.4 et le prompt intégral en Annexe D suffisent amplement.",
        "arbitrage": "Superflu dans l'article de synthèse."
    }
]

print("Encodage des images en base64 pour autonomie complète...")
for idx, item in enumerate(ITEMS):
    item["id"] = idx
    p = FIG_DIR / item["fichier"]
    if p.exists():
        data = base64.b64encode(p.read_bytes()).decode("utf-8")
        item["b64"] = f"data:image/png;base64,{data}"
        item["taille_kb"] = round(p.stat().st_size / 1024, 1)
    else:
        print(f"ATTENTION: {p} non trouvé")
        item["b64"] = ""
        item["taille_kb"] = 0

html_content = """<!DOCTYPE html>
<html lang="fr" class="h-full">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Galerie des Illustrations Candidates — Article Court AAMAS 2027</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: {
              50: '#f0fdf4',
              500: '#16a34a',
              600: '#15803d',
              700: '#166534',
            }
          }
        }
      }
    }
  </script>
  <style>
    .modal-active { overflow: hidden; }
    .zoom-img { transition: transform 0.2s ease-out; }
  </style>
</head>
<body class="bg-slate-50 dark:bg-slate-950 text-slate-800 dark:text-slate-100 min-h-full font-sans antialiased">

  <!-- Header -->
  <header class="sticky top-0 z-30 bg-white/95 dark:bg-slate-900/95 backdrop-blur border-b border-slate-200 dark:border-slate-800 px-6 py-4 shadow-sm">
    <div class="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center md:justify-between gap-4">
      <div>
        <div class="flex items-center gap-2">
          <span class="px-2 py-0.5 text-xs font-bold uppercase tracking-wider rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">Arbitrage Visuel</span>
          <h1 class="text-xl font-bold tracking-tight">Article Court AAMAS 2027 : Galerie des Illustrations Candidates</h1>
        </div>
        <p class="text-xs text-slate-500 dark:text-slate-400 mt-1">
          Triées selon les 5 catégories de priorité — Les 5 figures déjà insérées sont exclues — Budget contraint : 8 pages max
        </p>
      </div>

      <!-- Filtres par catégorie -->
      <div class="flex flex-wrap items-center gap-1.5" id="filter-buttons">
        <button onclick="filterCat('all')" id="btn-all" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-sm transition">
          Toutes (18)
        </button>
        <button onclick="filterCat(1)" id="btn-1" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-emerald-50 dark:hover:bg-emerald-950 text-slate-700 dark:text-slate-300 transition border border-transparent hover:border-emerald-300">
          1. Indispensable (3)
        </button>
        <button onclick="filterCat(2)" id="btn-2" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-blue-50 dark:hover:bg-blue-950 text-slate-700 dark:text-slate-300 transition border border-transparent hover:border-blue-300">
          2. Très utile (3)
        </button>
        <button onclick="filterCat(3)" id="btn-3" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-indigo-50 dark:hover:bg-indigo-950 text-slate-700 dark:text-slate-300 transition border border-transparent hover:border-indigo-300">
          3. Utile / Annexes (5)
        </button>
        <button onclick="filterCat(4)" id="btn-4" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-amber-50 dark:hover:bg-amber-950 text-slate-700 dark:text-slate-300 transition border border-transparent hover:border-amber-300">
          4. Peu prioritaire (3)
        </button>
        <button onclick="filterCat(5)" id="btn-5" class="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-rose-50 dark:hover:bg-rose-950 text-slate-700 dark:text-slate-300 transition border border-transparent hover:border-rose-300">
          5. Presque inutile (4)
        </button>
      </div>
    </div>
  </header>

  <!-- Bannière rappel d'arbitrage -->
  <section class="max-w-7xl mx-auto px-6 pt-6">
    <div class="bg-gradient-to-r from-slate-900 to-indigo-950 text-white rounded-2xl p-5 shadow-md flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
      <div class="space-y-1">
        <div class="flex items-center gap-2">
          <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span class="text-xs font-bold uppercase tracking-wider text-emerald-300">Rappel Contrainte 8 Pages</span>
        </div>
        <h2 class="text-base font-semibold">5 figures sont déjà insérées dans le texte compilé</h2>
        <p class="text-xs text-slate-300 max-w-3xl">
          Fig. 1 (Architecture), Fig. 2 (Échelle composite), Fig. 3 (Pente distance), Fig. 4 (Audit unitaire) et Fig. 5 (Propension choc) saturent déjà le quota visuel. Toute image ci-dessous ne peut être intégrée qu'en <strong>substitution</strong>, en <strong>sous-panneau intégré</strong> (ex: Schéma causal sous la Fig. 5), ou en <strong>Annexe</strong>.
        </p>
      </div>
      <div class="flex items-center gap-3 shrink-0">
        <button onclick="filterCat(1)" class="px-3 py-2 bg-emerald-500 hover:bg-emerald-600 text-white text-xs font-bold rounded-lg shadow transition">
          Voir les candidates Catégorie 1
        </button>
      </div>
    </div>
  </section>

  <!-- Grille des cartes -->
  <main class="max-w-7xl mx-auto px-6 py-8 space-y-12">
"""

categories_def = [
    (1, "Catégorie 1 — Indispensable (si substitution ou intégration compacte)", "emerald", "Portent directement le cœur de la thèse (C2 ou C3). À privilégier en intégration sous-panneau ou remplacement."),
    (2, "Catégorie 2 — Très utile / Fortement recommandé", "blue", "Apportent une forte valeur ajoutée explicative. Candidates idéales pour l'Annexe prioritaire ou en colonne."),
    (3, "Catégorie 3 — Utile si place disponible (Destination : Annexes)", "indigo", "Excellents compléments scientifiques, mais qui surchargeraient le corps des 8 pages. À déporter en matériel supplémentaire."),
    (4, "Catégorie 4 — Peu prioritaire", "amber", "Informations déjà synthétisées par un tableau compact ou du texte. Coût spatial supérieur au gain."),
    (5, "Catégorie 5 — Presque inutile / Déconseillé", "rose", "Décoratif, inachevé ou déconseillé dans un article court (gaspillage d'espace précieux ou risque de critique des reviewers).")
]

for cat_num, cat_titre, cat_color, cat_desc in categories_def:
    cat_items = [it for it in ITEMS if it["cat"] == cat_num]
    if not cat_items:
        continue

    html_content += f"""
    <!-- Catégorie {cat_num} -->
    <section id="cat-{cat_num}" class="category-block space-y-4" data-category="{cat_num}">
      <div class="border-b border-slate-200 dark:border-slate-800 pb-3 flex flex-col md:flex-row md:items-end justify-between gap-2">
        <div>
          <div class="flex items-center gap-2">
            <span class="w-3 h-3 rounded-full bg-{cat_color}-500"></span>
            <h2 class="text-lg font-bold text-slate-900 dark:text-white">{cat_titre}</h2>
          </div>
          <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{cat_desc}</p>
        </div>
        <span class="text-xs font-semibold px-2.5 py-1 rounded-full bg-{cat_color}-100 dark:bg-{cat_color}-950 text-{cat_color}-800 dark:text-{cat_color}-300 self-start md:self-auto">
          {len(cat_items)} illustration{'s' if len(cat_items) > 1 else ''}
        </span>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
    """

    for item in cat_items:
        titre_escaped = html.escape(item['titre'])
        section_escaped = html.escape(item['section'])
        pourquoi_escaped = html.escape(item['pourquoi'])
        arbitrage_escaped = html.escape(item['arbitrage'])

        html_content += f"""
        <!-- Carte ID {item['id']} -->
        <div class="image-card bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden flex flex-col transition hover:shadow-md hover:border-{cat_color}-400 dark:hover:border-{cat_color}-700" data-cat="{item['cat']}">
          <!-- Image thumbnail cliquable -->
          <div class="relative bg-slate-100 dark:bg-slate-950 p-2 border-b border-slate-200 dark:border-slate-800 aspect-video flex items-center justify-center overflow-hidden group cursor-pointer" onclick="openModalById({item['id']})">
            <img src="{item['b64']}" alt="{titre_escaped}" class="max-h-full max-w-full object-contain transition duration-200 group-hover:scale-105" loading="lazy">
            <div class="absolute inset-0 bg-slate-900/40 opacity-0 group-hover:opacity-100 transition flex items-center justify-center gap-2 text-white font-medium text-xs">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7"></path></svg>
              Cliquer pour agrandir
            </div>
            <span class="absolute top-2 right-2 text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/60 text-white backdrop-blur">
              {item['taille_kb']} KB
            </span>
          </div>

          <!-- Métadonnées & Description -->
          <div class="p-4 flex-1 flex flex-col justify-between space-y-3">
            <div class="space-y-1.5">
              <div class="flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
                <span class="font-medium text-{cat_color}-600 dark:text-{cat_color}-400">{section_escaped}</span>
                <span class="font-mono text-[10px]">{item['fichier']}</span>
              </div>
              <h3 class="text-sm font-bold text-slate-900 dark:text-white leading-snug cursor-pointer hover:underline" onclick="openModalById({item['id']})">{titre_escaped}</h3>
              <p class="text-xs text-slate-600 dark:text-slate-300 line-clamp-3 leading-relaxed" title="{pourquoi_escaped}">
                {pourquoi_escaped}
              </p>
            </div>

            <!-- Box d'arbitrage -->
            <div class="bg-slate-50 dark:bg-slate-950/60 rounded-lg p-2.5 border border-slate-200/80 dark:border-slate-800 text-[11px] space-y-1">
              <div class="font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                <svg class="w-3.5 h-3.5 text-{cat_color}-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                Arbitrage & Recommandation
              </div>
              <p class="text-slate-500 dark:text-slate-400 leading-normal">
                {arbitrage_escaped}
              </p>
            </div>

            <!-- Bouton d'action direct -->
            <button onclick="openModalById({item['id']})" class="w-full py-1.5 px-3 rounded-lg text-xs font-semibold bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 transition flex items-center justify-center gap-1.5 border border-slate-200 dark:border-slate-700">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg>
              Agrandir l'image
            </button>
          </div>
        </div>
        """

    html_content += """
      </div>
    </section>
    """

# Données JSON propres pour le JS
js_items = []
for it in ITEMS:
    js_items.append({
        "id": it["id"],
        "cat": it["cat"],
        "cat_nom": it["cat_nom"],
        "cat_color": it["cat_color"],
        "titre": it["titre"],
        "section": it["section"],
        "fichier": it["fichier"],
        "pourquoi": it["pourquoi"],
        "arbitrage": it["arbitrage"],
        "b64": it["b64"],
        "taille_kb": it["taille_kb"]
    })

html_content += f"""
  </main>

  <!-- Modal Zoom Avancée -->
  <div id="image-modal" class="fixed inset-0 z-50 bg-black/85 backdrop-blur-md hidden items-center justify-center p-3 sm:p-6" onclick="closeModal()">
    <div class="relative max-w-6xl w-full max-h-[95vh] bg-white dark:bg-slate-900 rounded-2xl overflow-hidden shadow-2xl flex flex-col border border-slate-200 dark:border-slate-800" onclick="event.stopPropagation()">

      <!-- Barre d'outils supérieure du modal -->
      <div class="flex items-center justify-between px-5 py-3.5 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950">
        <div class="flex items-center gap-3 overflow-hidden pr-2">
          <span id="modal-cat-badge" class="px-2 py-0.5 text-xs font-bold rounded shrink-0"></span>
          <div class="truncate">
            <h3 id="modal-title" class="text-sm font-bold text-slate-900 dark:text-white truncate"></h3>
            <p id="modal-meta" class="text-[11px] text-slate-500 font-mono"></p>
          </div>
        </div>

        <div class="flex items-center gap-1.5 shrink-0">
          <!-- Contrôles Zoom -->
          <div class="flex items-center bg-slate-200 dark:bg-slate-800 rounded-lg p-0.5">
            <button onclick="changeZoom(-0.25)" title="Dézoomer" class="p-1.5 hover:bg-white dark:hover:bg-slate-700 rounded text-slate-700 dark:text-slate-200 transition">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4"></path></svg>
            </button>
            <span id="zoom-level" class="text-[11px] font-mono px-2 text-slate-600 dark:text-slate-300">100%</span>
            <button onclick="changeZoom(0.25)" title="Zoomer" class="p-1.5 hover:bg-white dark:hover:bg-slate-700 rounded text-slate-700 dark:text-slate-200 transition">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
            </button>
            <button onclick="resetZoom()" title="Réinitialiser zoom" class="px-2 py-1 text-[11px] hover:bg-white dark:hover:bg-slate-700 rounded text-slate-700 dark:text-slate-200 transition font-medium">
              1:1
            </button>
          </div>

          <!-- Navigation précédent / suivant -->
          <div class="flex items-center bg-slate-200 dark:bg-slate-800 rounded-lg p-0.5 ml-2">
            <button onclick="prevImage()" title="Image précédente (Flèche gauche)" class="p-1.5 hover:bg-white dark:hover:bg-slate-700 rounded text-slate-700 dark:text-slate-200 transition">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
            </button>
            <span id="modal-counter" class="text-[11px] font-mono px-2 text-slate-600 dark:text-slate-300">1 / 18</span>
            <button onclick="nextImage()" title="Image suivante (Flèche droite)" class="p-1.5 hover:bg-white dark:hover:bg-slate-700 rounded text-slate-700 dark:text-slate-200 transition">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path></svg>
            </button>
          </div>

          <!-- Bouton fermer -->
          <button onclick="closeModal()" title="Fermer (Echap)" class="p-2 ml-2 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-800 text-slate-500 hover:text-slate-800 dark:hover:text-slate-100 transition">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          </button>
        </div>
      </div>

      <!-- Zone d'affichage de l'image -->
      <div id="image-container" class="p-4 flex items-center justify-center overflow-auto max-h-[62vh] min-h-[400px] bg-slate-100 dark:bg-black/60 relative select-none">
        <img id="modal-img" src="" alt="" class="zoom-img max-h-full max-w-full object-contain rounded shadow-lg cursor-grab active:cursor-grabbing">
      </div>

      <!-- Barre d'information inférieure du modal -->
      <div class="p-4 border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        <div class="space-y-1">
          <span class="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[10px]">Pourquoi cette illustration ?</span>
          <p id="modal-pourquoi" class="text-slate-600 dark:text-slate-300 leading-relaxed"></p>
        </div>
        <div class="space-y-1 bg-slate-50 dark:bg-slate-950 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800">
          <span class="font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-[10px]">Arbitrage éditorial (Contrainte 8 pages)</span>
          <p id="modal-arbitrage" class="text-slate-500 dark:text-slate-400 leading-relaxed"></p>
        </div>
      </div>

    </div>
  </div>

  <script>
    const itemsData = {json.dumps(js_items)};
    let currentIndex = 0;
    let currentZoom = 1.0;

    function filterCat(cat) {{
      const btns = ['all', '1', '2', '3', '4', '5'];
      btns.forEach(b => {{
        const el = document.getElementById('btn-' + b);
        if (!el) return;
        if (b === String(cat)) {{
          el.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-sm transition';
        }} else {{
          el.className = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 transition';
        }}
      }});

      const sections = document.querySelectorAll('.category-block');
      sections.forEach(sec => {{
        if (cat === 'all' || sec.getAttribute('data-category') === String(cat)) {{
          sec.style.display = 'block';
        }} else {{
          sec.style.display = 'none';
        }}
      }});
    }}

    function openModalById(idx) {{
      if (idx < 0 || idx >= itemsData.length) return;
      currentIndex = idx;
      currentZoom = 1.0;
      updateModalView();

      const modal = document.getElementById('image-modal');
      modal.classList.remove('hidden');
      modal.classList.add('flex');
      document.body.classList.add('modal-active');
    }}

    function updateModalView() {{
      const data = itemsData[currentIndex];
      if (!data) return;

      const img = document.getElementById('modal-img');
      img.src = data.b64;
      img.style.transform = `scale(${{currentZoom}})`;
      document.getElementById('zoom-level').textContent = Math.round(currentZoom * 100) + '%';

      document.getElementById('modal-title').textContent = data.titre;
      document.getElementById('modal-meta').textContent = `${{data.section}} • ${{data.fichier}} (${{data.taille_kb}} KB)`;
      document.getElementById('modal-pourquoi').textContent = data.pourquoi;
      document.getElementById('modal-arbitrage').textContent = data.arbitrage;
      document.getElementById('modal-counter').textContent = `${{currentIndex + 1}} / ${{itemsData.length}}`;

      const badge = document.getElementById('modal-cat-badge');
      badge.textContent = data.cat_nom;
      badge.className = `px-2 py-0.5 text-xs font-bold rounded shrink-0 bg-${{data.cat_color}}-100 dark:bg-${{data.cat_color}}-950 text-${{data.cat_color}}-800 dark:text-${{data.cat_color}}-300 border border-${{data.cat_color}}-300 dark:border-${{data.cat_color}}-800`;
    }}

    function changeZoom(delta) {{
      currentZoom = Math.max(0.5, Math.min(3.0, currentZoom + delta));
      const img = document.getElementById('modal-img');
      img.style.transform = `scale(${{currentZoom}})`;
      document.getElementById('zoom-level').textContent = Math.round(currentZoom * 100) + '%';
    }}

    function resetZoom() {{
      currentZoom = 1.0;
      const img = document.getElementById('modal-img');
      img.style.transform = `scale(1.0)`;
      document.getElementById('zoom-level').textContent = '100%';
    }}

    function prevImage() {{
      currentIndex = (currentIndex - 1 + itemsData.length) % itemsData.length;
      resetZoom();
      updateModalView();
    }}

    function nextImage() {{
      currentIndex = (currentIndex + 1) % itemsData.length;
      resetZoom();
      updateModalView();
    }}

    function closeModal() {{
      const modal = document.getElementById('image-modal');
      modal.classList.add('hidden');
      modal.classList.remove('flex');
      document.body.classList.remove('modal-active');
      resetZoom();
    }}

    document.addEventListener('keydown', (e) => {{
      const modal = document.getElementById('image-modal');
      if (modal.classList.contains('hidden')) return;

      if (e.key === 'Escape') closeModal();
      else if (e.key === 'ArrowLeft') prevImage();
      else if (e.key === 'ArrowRight') nextImage();
      else if (e.key === '+' || e.key === '=') changeZoom(0.25);
      else if (e.key === '-' || e.key === '_') changeZoom(-0.25);
    }});
  </script>
</body>
</html>
"""

print(f"Écriture dans le workspace : {SORTIE_WORKSPACE}")
SORTIE_WORKSPACE.write_text(html_content, encoding="utf-8")

print(f"Écriture dans le dossier artifact : {SORTIE_ARTIFACT}")
SORTIE_ARTIFACT.write_text(html_content, encoding="utf-8")

print("OK: Version 2 du fichier HTML générée avec succès !")
