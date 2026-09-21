/**
 * Génère `Divers/architecture_proposée.pptx` — la spécification mémoire en huit slides.
 *
 * Source de vérité du contenu : docs/arch/memory-stm-ltm.md, partie III.
 * Ce script est versionné pour que le deck se régénère au lieu d'être retouché à la main.
 *
 *   npm install pptxgenjs && node scripts/slides/architecture_memoire.js
 *
 * Révisions : 2026-09-11 création ; 2026-09-14 suite à l'expertise externe (ticket 071)
 * — le hachage devient un panier, le plancher temporel disparaît, les concepts ne
 * s'oublient plus à l'horloge.
 */
const pptxgen = require("pptxgenjs");
const {
  INK, INK_SOFT, VIOLET, VIOLET_PALE, AMBER, BRICK,
  WHITE, TINT, TINT_DEEP, MUTED, MUTED_DARK,
  HEAD, BODY, MONO, W, M, aides, sortie,
} = require("./_charte");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "Projet LLM-Agents GAMA";
pres.title = "Architecture memoire proposee";
const { card, numDot, head, banner } = aides(pres);

// ======================================================== 1 · TITRE
const s1 = pres.addSlide();
s1.background = { color: INK };
[[9.3,1.55,.5,AMBER,95],[10.55,2.05,.26,VIOLET_PALE,45],[11.55,1.42,.34,VIOLET,70],
 [9.95,2.95,.2,VIOLET_PALE,35],[10.9,3.3,.62,VIOLET,78],[12.05,2.72,.24,AMBER,60],
 [9.2,3.85,.3,VIOLET_PALE,40],[11.7,4.2,.44,AMBER,85],[10.3,4.85,.22,VIOLET_PALE,30],
 [12.3,3.62,.18,VIOLET_PALE,30],[9.75,5.55,.36,VIOLET,55],[11.2,5.4,.22,VIOLET_PALE,35]
].forEach(([x, y, d, c, op]) => s1.addShape(pres.shapes.OVAL, {
  x, y, w: d, h: d, fill: { color: c, transparency: 100 - op }, line: { color: c, width: 0 } }));
s1.addText("Projet LLM-Agents GAMA", { x: M, y: 1.55, w: 8.2, h: 0.3, isTextBox: true, margin: 0,
  fontFace: BODY, fontSize: 12, bold: true, color: AMBER, charSpacing: 2 });
s1.addText("Architecture mémoire", { x: M, y: 2.05, w: 8.4, h: 0.95, isTextBox: true, margin: 0,
  fontFace: HEAD, fontSize: 50, bold: true, color: WHITE, valign: "middle" });
s1.addText("Spécification", { x: M, y: 2.98, w: 8.4, h: 0.8, isTextBox: true, margin: 0,
  fontFace: HEAD, fontSize: 44, italic: true, color: VIOLET_PALE, valign: "middle" });
s1.addText("Comment un souvenir est qualifié, consolidé, oublié et rappelé dans une population " +
  "d'agents pilotés par un modèle de langue.",
  { x: M, y: 4.15, w: 8.0, h: 1.0, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 16, color: MUTED_DARK, lineSpacing: 24 });
s1.addText("Simulation multimodale · Aire métropolitaine toulousaine · 14 septembre 2026",
  { x: M, y: 6.55, w: 9.0, h: 0.35, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11, color: VIOLET_PALE });
s1.addNotes("Huit slides : les trois règles, ce que porte un souvenir, comment on l'écrit, comment " +
  "on le consolide, comment on l'oublie, comment on le rappelle, et ce que le modèle voit au moment " +
  "de décider. Version révisée après une expertise externe : trois points de conception ont changé, " +
  "ils sont signalés sur les slides concernées.");

// ======================================================== 2 · TROIS RÈGLES
const s2 = pres.addSlide();
s2.background = { color: WHITE };
head(s2, "Fondations", "Trois règles, et tout en découle");
[["Un souvenir est qualifié, pas seulement daté",
  "Il porte une gravité. Cette gravité décide de sa durée de vie et de son poids au moment où l'agent décide. Un incident et un trajet banal cessent d'être interchangeables."],
 ["Un concept se corrige au lieu de s'empiler",
  "Une connaissance sur le monde est un objet unique, qui se confirme, se précise ou se voit contredire, avec un compteur d'observations derrière lui."],
 ["Au rappel, rien ne filtre, tout pondère",
  "Hors identité de l'agent et fenêtre d'âge, aucun critère n'exclut un souvenir. Un critère qui ne correspond pas n'ajoute rien, mais il n'enlève rien non plus."],
].forEach(([t, d], i) => {
  const x = M + i * 4.1;
  card(s2, x, 1.55, 3.9, 3.2);
  numDot(s2, x + 0.3, 1.9, i + 1, VIOLET, WHITE, 0.5);
  s2.addText(t, { x: x + 0.3, y: 2.55, w: 3.3, h: 0.85, isTextBox: true, margin: 0, valign: "top",
    fontFace: HEAD, fontSize: 16, bold: true, color: INK, lineSpacing: 21 });
  s2.addText(d, { x: x + 0.3, y: 3.5, w: 3.3, h: 1.15, isTextBox: true, margin: 0, valign: "top",
    fontFace: BODY, fontSize: 11.5, color: MUTED, lineSpacing: 16 });
});
banner(s2, 5.3, "Contrainte transverse : aucun appel supplémentaire au modèle. Tout ce qu'il produit " +
  "ici est demandé à l'intérieur des réflexions qui ont déjà lieu.", INK, AMBER);
s2.addNotes("La troisième règle est la moins intuitive et la plus importante. La tentation est de " +
  "filtrer les souvenirs sur le contexte, pour gagner en pertinence. Mais un filtre exclut, et ce " +
  "qu'on veut observer, ce sont les reports d'un contexte sur un autre : une chute à vélo le matin " +
  "doit peser sur le vélo du soir.");

// ======================================================== 3 · LE SOUVENIR
const s3 = pres.addSlide();
s3.background = { color: WHITE };
head(s3, "Structure de données", "Ce que porte un souvenir");
card(s3, M, 1.55, 7.5, 3.75);
s3.addText("Contexte · quatre axes", { x: M + 0.35, y: 1.85, w: 6.8, h: 0.38, isTextBox: true, margin: 0,
  fontFace: HEAD, fontSize: 16, bold: true, color: VIOLET, valign: "middle" });
[["objet", "le mode ou l'objet de réseau concerné : vélo, métro A, bus 401."],
 ["lieu", "arrêt, ligne ou quartier, résolu vers un identifiant réseau."],
 ["créneau", "nuit, matin, midi, soir, comme les tranches déjà utilisées pour la météo."],
 ["motif", "le motif du déplacement : travail, école, loisir."],
].forEach(([k, v], j) => {
  const x = M + 0.35 + (j % 2) * 3.6, y = 2.45 + Math.floor(j / 2) * 1.3;
  s3.addText(k, { x, y, w: 3.4, h: 0.28, isTextBox: true, margin: 0,
    fontFace: MONO, fontSize: 12, bold: true, color: INK, valign: "middle" });
  s3.addText(v, { x, y: y + 0.3, w: 3.4, h: 0.8, isTextBox: true, margin: 0, valign: "top",
    fontFace: BODY, fontSize: 11, color: MUTED, lineSpacing: 15 });
});
[["Gravité", AMBER, 1.55, [["importance", "de 0 à 1. Décide de la durée de vie et du poids au rappel."],
                           ["valence", "négative, neutre ou positive."]]],
 ["Dynamique", BRICK, 3.5, [["force", "constante de temps de l'oubli, en jours. Registre épisodique seul."],
                            ["rappels", "nombre de fois où le souvenir a été servi au modèle."]]],
].forEach(([t, c, cy, rows]) => {
  card(s3, 8.4, cy, 4.3, 1.8);
  s3.addText(t, { x: 8.7, y: cy + 0.16, w: 3.7, h: 0.34, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 15, bold: true, color: c, valign: "middle" });
  rows.forEach(([k, v], j) => {
    const y = cy + 0.6 + j * 0.58;
    s3.addText(k, { x: 8.7, y, w: 3.7, h: 0.24, isTextBox: true, margin: 0,
      fontFace: MONO, fontSize: 10.5, bold: true, color: INK, valign: "middle" });
    s3.addText(v, { x: 8.7, y: y + 0.25, w: 3.7, h: 0.35, isTextBox: true, margin: 0, valign: "top",
      fontFace: BODY, fontSize: 10, color: MUTED, lineSpacing: 12 });
  });
});
s3.addText("Les axes sont normalisés à l'écriture, jamais à la lecture : sans cela, deux graphies de " +
  "la même ligne de bus ne se rencontrent jamais. Un axe non résolu vaut « absent », ce qui ne " +
  "correspond à rien plutôt qu'à tout.",
  { x: M, y: 5.55, w: W - 2 * M, h: 0.8, isTextBox: true, margin: 0, valign: "top",
    fontFace: BODY, fontSize: 12, italic: true, color: MUTED, lineSpacing: 17 });
s3.addNotes("Sept champs nouveaux. Les six premiers sont écrits une fois, force et rappels évoluent. " +
  "Depuis la révision, la constante de temps ne concerne que le registre épisodique : les concepts " +
  "ne s'oublient pas à l'horloge, voir la slide « Oublier ».");

// ======================================================== 4 · ÉCRIRE
const s4 = pres.addSlide();
s4.background = { color: WHITE };
head(s4, "Écrire", "D'où vient la gravité d'un souvenir");
card(s4, M, 1.55, 5.85, 3.9);
s4.addText("Ce que la simulation mesure", { x: M + 0.32, y: 1.85, w: 5.2, h: 0.4, isTextBox: true, margin: 0,
  fontFace: HEAD, fontSize: 17, bold: true, color: INK, valign: "middle" });
s4.addText("Pour les entrées brutes. Objectif, gratuit, sans modèle.", { x: M + 0.32, y: 2.26, w: 5.2, h: 0.3,
  isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11.5, color: MUTED });
s4.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M + 0.32, y: 2.68, w: 5.2, h: 1.55, rectRadius: 0.05,
  fill: { color: WHITE }, line: { color: TINT_DEEP, width: 0.75 } });
s4.addText("I = 0,50 × retard subi, plafonné à 30 min\n  + 0,20 × correspondance ratée\n" +
  "  + 0,20 × incident réseau\n  + 0,10 × changement de mode contraint",
  { x: M + 0.5, y: 2.68, w: 4.9, h: 1.55, isTextBox: true, margin: 0, valign: "middle",
    fontFace: MONO, fontSize: 10.5, color: INK, lineSpacing: 17 });
s4.addText("Le résultat est borné entre 0 et 1.", { x: M + 0.32, y: 4.35, w: 5.2, h: 0.3, isTextBox: true,
  margin: 0, fontFace: BODY, fontSize: 11, italic: true, color: MUTED });

card(s4, 6.85, 1.55, 5.85, 3.9);
s4.addText("Ce que le modèle juge", { x: 7.17, y: 1.85, w: 5.2, h: 0.4, isTextBox: true, margin: 0,
  fontFace: HEAD, fontSize: 17, bold: true, color: INK, valign: "middle" });
s4.addText("Pour les concepts, dans l'appel qui a déjà lieu. Un niveau nommé, jamais un chiffre.",
  { x: 7.17, y: 2.26, w: 5.2, h: 0.34, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11.5, color: MUTED });
[["anodin", "0,10", "Tout s'est passé comme prévu.", MUTED],
 ["notable", "0,30", "Un écart perceptible, sans conséquence.", MUTED],
 ["gênant", "0,50", "M'a coûté du temps, ou décalé un horaire.", VIOLET],
 ["grave", "0,75", "M'a fait rater quelque chose.", BRICK],
 ["marquant", "1,00", "Je m'en souviendrai dans un mois.", BRICK],
].forEach(([lab, val, anchor, c], i) => {
  const y = 2.72 + i * 0.4;
  s4.addText(lab, { x: 7.17, y, w: 1.35, h: 0.34, isTextBox: true, margin: 0,
    fontFace: MONO, fontSize: 11, bold: true, color: c, valign: "middle" });
  s4.addText(val, { x: 8.52, y, w: 0.62, h: 0.34, isTextBox: true, margin: 0,
    fontFace: MONO, fontSize: 10.5, color: INK, valign: "middle", align: "right" });
  s4.addText(anchor, { x: 9.3, y, w: 3.07, h: 0.34, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 10.5, color: MUTED, valign: "middle" });
});
s4.addText("Chaque échelon est ancré sur une conséquence observable. Le seuil du choc se lit alors " +
  "en mots : est un choc ce qui est jugé grave ou au-dessus.",
  { x: 7.17, y: 4.78, w: 5.2, h: 0.5, isTextBox: true, margin: 0, valign: "top",
    fontFace: BODY, fontSize: 10.5, italic: true, color: MUTED, lineSpacing: 14 });
banner(s4, 5.75, "Règle de sécurité : la gravité retenue est le maximum des deux. Un modèle qui " +
  "sous-estime un incident de quarante-cinq minutes ne peut pas le dégrader. Le fait mesuré l'emporte " +
  "toujours.", INK, AMBER);
s4.addNotes("Les deux sources ne sont jamais en concurrence, elles s'appliquent à des objets " +
  "différents. Le déterministe note le vécu brut, le modèle note les connaissances qu'il en tire. " +
  "La règle du maximum garantit qu'aucun jugement mal calibré n'efface un fait mesuré.");

// ======================================================== 5 · CONSOLIDER
const s5 = pres.addSlide();
s5.background = { color: WHITE };
head(s5, "Consolider", "Un concept se corrige, il ne s'empile pas");
s5.addText("Le couple objet-motif désigne un PANIER de concepts candidats, pas un concept unique. " +
  "La présélection reste une correspondance exacte sur une métadonnée, sans embedding ni balayage " +
  "de l'index ; la discrimination se fait ensuite à l'intérieur du panier, que le modèle voit dans " +
  "l'appel de réflexion qui a déjà lieu.",
  { x: M, y: 1.4, w: W - 2 * M, h: 0.72, isTextBox: true, margin: 0, valign: "top",
    fontFace: BODY, fontSize: 12.5, color: MUTED, lineSpacing: 17 });
[["créer", VIOLET, "Aucun concept du panier ne correspond. Un concept naît, avec une observation à son compteur."],
 ["confirmer", VIOLET, "Même affirmation. Rien n'est écrit de neuf : le compteur monte, la date se rafraîchit, la confiance s'élève."],
 ["préciser", AMBER, "Affirmation compatible mais plus fine. Le contenu est remplacé, les compteurs et l'historique sont conservés."],
 ["contredire", BRICK, "Affirmation incompatible. Le compteur de contre-exemples monte. Au-delà d'un seuil, l'ancien concept est marqué dépassé."],
].forEach(([t, c, d], i) => {
  const x = M + (i % 2) * 6.25, y = 2.3 + Math.floor(i / 2) * 1.72;
  card(s5, x, y, 5.85, 1.52);
  s5.addShape(pres.shapes.OVAL, { x: x + 0.3, y: y + 0.28, w: 0.2, h: 0.2, fill: { color: c }, line: { color: c, width: 0 } });
  s5.addText(t, { x: x + 0.62, y: y + 0.2, w: 5.0, h: 0.36, isTextBox: true, margin: 0,
    fontFace: MONO, fontSize: 14, bold: true, color: c, valign: "middle" });
  s5.addText(d, { x: x + 0.3, y: y + 0.63, w: 5.3, h: 0.75, isTextBox: true, margin: 0, valign: "top",
    fontFace: BODY, fontSize: 11.5, color: MUTED, lineSpacing: 16 });
});
banner(s5, 5.95, "Un panier, pas une identité : une identité unique par couple objet-motif " +
  "condamnerait l'agent à une seule pensée par mode et par motif, chaque concept nouveau détruisant " +
  "le précédent.", INK, AMBER);
s5.addNotes("Point de conception corrigé après expertise externe. La version initiale posait une " +
  "identité égale au hachage du couple objet-motif. Un agent pendulaire à vélo qui apprend " +
  "successivement que la piste du canal est protégée, que l'abri à vélos sature à 8 h 30 et que les " +
  "pavés sont glissants par temps de pluie aurait vu chaque concept détruire le précédent. Le panier " +
  "conserve la propriété utile, aucun balayage de l'index, et supprime l'écrasement. Le modèle " +
  "désigne le concept qu'il met à jour plutôt qu'un seuil de similarité qu'il faudrait calibrer.");

// ======================================================== 6 · OUBLIER
const s6 = pres.addSlide();
s6.background = { color: WHITE };
head(s6, "Oublier", "Ce que le temps efface, et ce qu'il n'efface pas");
const days = ["0","1","2","3","4","5","6","7","8","9","10"];
s6.addChart(pres.charts.LINE,
  [{ name: "Épisodique · souvenir marquant", labels: days,
     values: [1,.913,.834,.761,.695,.635,.580,.529,.483,.441,.403] },
   { name: "Épisodique · trajet ordinaire", labels: days,
     values: [1,.700,.490,.343,.240,.168,.118,.082,.058,.041,.029] },
   { name: "Sémantique · concept jamais contredit", labels: days,
     values: [.9,.9,.9,.9,.9,.9,.9,.9,.9,.9,.9] }],
  { x: M, y: 1.5, w: 5.95, h: 4.5, showTitle: true, title: "Poids du souvenir au fil des jours",
    titleFontFace: HEAD, titleFontSize: 14, titleColor: INK,
    chartColors: [BRICK, VIOLET_PALE, AMBER], lineDataSymbol: "none", lineSize: 3,
    showLegend: true, legendPos: "b", legendFontFace: BODY, legendFontSize: 10, legendColor: MUTED,
    catAxisTitle: "Jours écoulés", showCatAxisTitle: true, catAxisTitleFontSize: 10, catAxisTitleColor: MUTED,
    catAxisLabelColor: MUTED, catAxisLabelFontSize: 10, catAxisLabelFontFace: BODY,
    valAxisLabelColor: MUTED, valAxisLabelFontSize: 10, valAxisLabelFontFace: BODY,
    valAxisMinVal: 0, valAxisMaxVal: 1, valAxisMajorUnit: 0.25,
    valGridLine: { color: TINT_DEEP, size: 1 }, catGridLine: { style: "none" } });
[["Deux registres, deux effacements",
  "Un épisode s'efface avec le temps. Un concept ne s'efface que si une observation le contredit. Qu'une ligne sature les jours de pluie ne devient pas faux en dix jours."],
 ["La gravité allonge la durée de vie",
  "La constante de temps d'un épisode croît avec sa gravité : près de trois jours pour un trajet banal, onze pour un souvenir marquant. Le défaut reproduit la décroissance en service."],
 ["Le rappel renforce",
  "Un épisode servi au modèle voit sa force croître, sous un plafond, pour qu'un agent ne se fige pas sur une poignée de souvenirs auto-entretenus."],
].forEach(([t, d], i) => {
  const y = 1.5 + i * 1.6;
  card(s6, 6.9, y, 5.8, 1.45);
  s6.addText(t, { x: 7.2, y: y + 0.18, w: 5.2, h: 0.36, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 15, bold: true, color: INK, valign: "middle" });
  s6.addText(d, { x: 7.2, y: y + 0.6, w: 5.2, h: 0.72, isTextBox: true, margin: 0, valign: "top",
    fontFace: BODY, fontSize: 11, color: MUTED, lineSpacing: 15 });
});
s6.addText("Aucun plancher artificiel : la persistance d'un choc vient de sa constante de temps et " +
  "du vivier des chocs, jamais d'une décroissance qu'on fige.",
  { x: 6.9, y: 6.35, w: 5.8, h: 0.6, isTextBox: true, margin: 0, valign: "top",
    fontFace: BODY, fontSize: 11.5, italic: true, color: BRICK, lineSpacing: 15 });
s6.addNotes("Deux points de conception corrigés après expertise externe. D'abord la distinction " +
  "épisodique et sémantique : appliquer une décroissance d'horloge à un concept est un contresens " +
  "cognitif, un concept ne se dément que par contradiction, et sa confiance se lit sur ses compteurs " +
  "d'observations et de contre-exemples. Ensuite la suppression du plancher temporel. Il figeait la " +
  "composante d'ancienneté, ce qui revient à poser que le temps cesse de s'écouler pour un souvenir " +
  "grave, alors qu'une personne sait très bien que l'événement est ancien : ce qui reste élevé, c'est " +
  "son accessibilité, pas sa récence. Et surtout il faisait entrer la gravité trois fois dans le " +
  "score, ce qui rendait l'effet de l'oubli inséparable de l'effet de la gravité dans l'ablation.");

// ======================================================== 7 · RAPPELER
const s7 = pres.addSlide();
s7.background = { color: WHITE };
head(s7, "Rappeler", "Trois viviers, puis un classement");
[["Vivier sémantique", "Les souvenirs dont le texte ressemble à la situation. Un embedding de requête."],
 ["Vivier par objet", "Pour chaque mode offert dans les options, les souvenirs portant sur ce mode, les plus graves et les plus récents d'abord. Aucun embedding."],
 ["Vivier des chocs", "Les souvenirs dont la gravité dépasse le seuil, sans aucune condition de lieu, d'heure ni de motif."],
].forEach(([t, d], i) => {
  const y = 1.5 + i * 1.55;
  card(s7, M, y, 5.85, 1.4);
  numDot(s7, M + 0.28, y + 0.22, i + 1, VIOLET, WHITE);
  s7.addText(t, { x: M + 0.82, y: y + 0.22, w: 4.7, h: 0.42, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 15, bold: true, color: INK, valign: "middle" });
  s7.addText(d, { x: M + 0.28, y: y + 0.7, w: 5.3, h: 0.6, isTextBox: true, margin: 0, valign: "top",
    fontFace: BODY, fontSize: 11, color: MUTED, lineSpacing: 14 });
});
s7.addText("Les trois viviers sont réunis et dédupliqués, puis classés ensemble.",
  { x: M, y: 6.2, w: 5.85, h: 0.3, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11, italic: true, color: MUTED });
s7.addChart(pres.charts.BAR,
  [{ name: "Poids", labels: ["Lexical", "Poids temporel", "Affinité d'axes", "Gravité", "Similarité"],
     values: [0.10, 0.20, 0.20, 0.20, 0.30] }],
  { x: 6.9, y: 1.5, w: 5.8, h: 3.35, barDir: "bar", showTitle: true,
    title: "Les cinq composantes du classement", titleFontFace: HEAD, titleFontSize: 14, titleColor: INK,
    chartColors: [VIOLET], showLegend: false, showValue: true, dataLabelPosition: "outEnd",
    dataLabelFormatCode: "0.00", dataLabelColor: INK, dataLabelFontFace: BODY, dataLabelFontSize: 10,
    catAxisLabelColor: INK, catAxisLabelFontSize: 11, catAxisLabelFontFace: BODY,
    valAxisLabelColor: MUTED, valAxisLabelFontSize: 9, valAxisLabelFontFace: BODY,
    valAxisMinVal: 0, valAxisMaxVal: 0.4, valGridLine: { color: TINT_DEEP, size: 1 },
    catGridLine: { style: "none" }, barGapWidthPct: 45 });
s7.addText("L'affinité d'axes est un bonus, jamais un veto : un axe discordant contribue zéro, et un " +
  "souvenir dont aucun axe ne concorde reste classable sur ses quatre autres composantes.",
  { x: 6.9, y: 5.05, w: 5.8, h: 0.75, isTextBox: true, margin: 0, valign: "top",
    fontFace: BODY, fontSize: 11.5, color: MUTED, lineSpacing: 16 });
s7.addText("Poids de départ, à calibrer. Ce ne sont pas des résultats.",
  { x: 6.9, y: 5.9, w: 5.8, h: 0.3, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11, italic: true, color: MUTED });
s7.addNotes("Le vivier par objet fait remonter la chute à vélo du matin dès lors que le vélo figure " +
  "parmi les options du soir : ni le lieu, ni l'heure, ni le motif ne coïncident, c'est l'objet qui " +
  "les relie. Le vivier des chocs garantit qu'un souvenir grave n'est jamais perdu par accident de " +
  "classement. Techniquement c'est une génération de candidats multi-viviers, technique classique de " +
  "recherche d'information : une version antérieure la présentait comme une inversion d'HippoRAG, " +
  "ce qui était un contresens, HippoRAG ne restreignant rien. Les composantes entrent en valeur " +
  "absolue, sans normalisation relative au lot, sinon le paramètre d'oubli devient inopérant.");

// ======================================================== 8 · MÉMOIRE NOYAU
const s8 = pres.addSlide();
s8.background = { color: INK };
head(s8, "Ce que le modèle voit", "La mémoire noyau", true);
s8.addText("Un bloc permanent, court et structuré, complété de deux ou trois souvenirs épisodiques " +
  "rappelés pour la décision en cours.",
  { x: M, y: 1.35, w: W - 2 * M, h: 0.4, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 13, color: MUTED_DARK });
s8.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 1.85, w: 7.95, h: 3.15, rectRadius: 0.06,
  fill: { color: INK_SOFT }, line: { color: VIOLET, width: 1 } });
s8.addText(
  "Mes habitudes\n" +
  "- Domicile vers travail, jours ouvrés 07h45 : bus 401 puis 5 min\n" +
  "  de marche, 24 min porte à porte. Tenu 9 fois sur 11.\n" +
  "- Retour 18h00, même trajet. Deux retards de plus de 10 min.\n\n" +
  "Ce que je sais\n" +
  "- Le bus 401 est fiable, sauf par temps de pluie.      (12 obs.)\n" +
  "- La marche jusqu'à l'arrêt fait toujours 5 minutes.   (18 obs.)\n\n" +
  "Ce qui a changé récemment\n" +
  "- 14 mars, panne ligne A, 45 min perdues. Je n'ai pas repris\n" +
  "  la ligne A depuis.",
  { x: M + 0.3, y: 2.12, w: 7.4, h: 2.8, isTextBox: true, margin: 0, valign: "top",
    fontFace: MONO, fontSize: 10.5, color: WHITE, lineSpacing: 15 });
[["Les habitudes viennent du journal des trajets", AMBER, 1.85,
  "Pas du modèle. Un texte réécrit périodiquement par un modèle dérive et invente. Seul le bloc de connaissances lui est confié, et chaque énoncé y porte son compteur."],
 ["Le dernier bloc porte la dynamique", VIOLET_PALE, 3.75,
  "C'est là que l'inertie après une perturbation devient lisible dans le prompt lui-même, et non plus seulement dans les statistiques de sortie."],
].forEach(([t, c, y, d]) => {
  const lines = t.length > 34 ? 2 : 1;
  s8.addText(t, { x: 8.85, y, w: 3.85, h: lines * 0.34, isTextBox: true, margin: 0, valign: "top",
    fontFace: HEAD, fontSize: 15, bold: true, color: c, lineSpacing: 19 });
  s8.addText(d, { x: 8.85, y: y + lines * 0.34 + 0.12, w: 3.85, h: 1.35, isTextBox: true, margin: 0,
    valign: "top", fontFace: BODY, fontSize: 11.5, color: MUTED_DARK, lineSpacing: 16 });
});
s8.addText("Aucune métadonnée sur le bloc lui-même : ni date de mise à jour, ni nombre de jours de " +
  "vécu. Cela ne change aucune décision, et une personne ne pense pas à la fraîcheur de sa propre mémoire.",
  { x: M, y: 5.3, w: 7.95, h: 0.75, isTextBox: true, margin: 0, valign: "top",
    fontFace: BODY, fontSize: 11.5, italic: true, color: VIOLET_PALE });
s8.addNotes("C'est la sortie visible de tout ce qui précède. Les compteurs d'observations viennent de " +
  "la consolidation des concepts, le dernier bloc vient de la gravité, et le choix des souvenirs " +
  "épisodiques qui complètent le bloc vient des trois viviers.");

pres.writeFile({ fileName: sortie("architecture_proposée.pptx") })
  .then(f => console.log("écrit :", f));
