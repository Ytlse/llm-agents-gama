/**
 * Génère `Divers/memoire_agents_mobilite.pptx` — la vie d'un souvenir, en vingt planches.
 *
 * Source de vérité du contenu : docs/arch/memory-stm-ltm.md, partie II, et specs/ticket_071/.
 * Ce script est versionné pour que le deck se régénère au lieu d'être retouché à la main :
 * le jeu qu'il remplace n'avait pas de générateur, et s'est périmé en silence en trois jours.
 *
 *   npm install pptxgenjs && node scripts/slides/memoire_agents_mobilite.js
 *
 * ── Ce que ce deck n'est PAS ─────────────────────────────────────────────────────
 * Le jeu précédent opposait « dispositif actuel » et « dispositif proposé » : il vendait des
 * angles morts et promettait des briques. Les briques sont posées (ticket 071, cinq lots, puis
 * ticket 077), donc l'axe est mort — on ne promet pas ce qui est fait. Ce deck DÉCRIT un
 * dispositif qui existe, en suivant un seul souvenir du mardi soir au vendredi matin.
 *
 * ── D'où viennent les chiffres ───────────────────────────────────────────────────
 * Tous ceux de `CAS` ont été relevés en EXÉCUTANT `llm/gravite.py` le 2026-09-21, pas
 * recalculés à la main. Ils sont réunis en tête du fichier : une constante du code qui bouge
 * se répercute ici en un seul endroit. Les vérifier à nouveau :
 *
 *   services/llm-agents/.venv/bin/python -c "from llm import gravite as g; \
 *     I,_ = g.gravite_deterministe(retard_s=1800, incident_reseau=True); \
 *     print(I, g.force_initiale(I), g.poids_temporel(3, g.force_initiale(I)))"
 *
 * Révisions : 2026-09-21 création (ticket 071, volet planches).
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
pres.title = "La vie d'un souvenir";
const { card, numDot, head, banner } = aides(pres);

// ════════════════════════════════════════════════════════════════════════════════
// LE CAS — un seul exemple traverse les vingt planches.
// Relevé par exécution de llm/gravite.py, valeurs par défaut de settings.py.
// ════════════════════════════════════════════════════════════════════════════════
const CAS = {
  scene: "Mardi, 17 h 10. Ligne A interrompue. Trente minutes perdues.",
  retardS: 1800,
  partRetard: 0.50,          // g.part_de_retard(1800)
  partIncident: 0.20,        // POIDS_INCIDENT_RESEAU
  gravite: 0.70,             // g.gravite_deterministe(1800, incident_reseau=True)
  graviteBanal: 0.00,
  forceChoc: 14.56,          // g.force_initiale(0.70)
  forceBanal: 2.80,          // S0
  forceApresRappel: 15.56,   // +δ, plafonné à 30
  // g.poids_temporel(j, force) × 100
  decroissance: [[1, 93.4, 70.0], [3, 81.4, 34.3], [5, 70.9, 16.8], [7, 61.8, 8.2]],
  // g.part_de_retard(s) — l'asymptote ne confond plus deux retards (ticket 095)
  asymptote: [["30 min", 0.500], ["40 min", 0.613], ["60 min", 0.684], ["90 min", 0.699]],
};

// Réglages cités, tous lus dans services/llm-agents/settings.py
const P = {
  S0: 2.8, k: 6, delta: 1, forceMax: 30, purge: 0.01,
  theta: 0.70, confianceSeuil: 0.50, contreExemples: 3,
  vivierB: 8, vivierC: 5, fenetreAge: 60, episodiques: 3,
};

const N = (v, d) => v.toFixed(d === undefined ? 2 : d).replace(".", ",");

// ── Aides propres à ce deck ─────────────────────────────────────────────────────
function pied(s, txt, couleur) {
  s.addText(txt, { x: M, y: 6.92, w: W - 2 * M, h: 0.32, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 10, italic: true, color: couleur || MUTED, valign: "middle" });
}
function source(s, txt) {
  s.addText(txt, { x: M, y: 6.58, w: W - 2 * M, h: 0.3, isTextBox: true, margin: 0,
    fontFace: MONO, fontSize: 9, color: MUTED, valign: "middle" });
}
/** Bandeau de rappel du cas, discret, en haut à droite : le fil ne se perd jamais. */
function fil(s, etape) {
  s.addText(etape, { x: W - M - 4.2, y: 0.18, w: 4.2, h: 0.28, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 10, color: MUTED, align: "right", valign: "middle" });
}
/** Rangée de n cartes titre + corps, réparties sur la largeur utile. */
function rangee(s, y, h, items, opts) {
  const o = opts || {};
  const n = items.length, g = o.gap === undefined ? 0.28 : o.gap;
  const w = (W - 2 * M - g * (n - 1)) / n;
  items.forEach(([titre, corps, teinte, bord], i) => {
    const x = M + i * (w + g);
    card(s, x, y, w, h, teinte || TINT, bord);
    s.addText(titre, { x: x + 0.22, y: y + 0.16, w: w - 0.44, h: 0.42, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: o.tailleTitre || 15, bold: true, color: o.couleurTitre || INK, valign: "middle" });
    s.addText(corps, { x: x + 0.22, y: y + 0.58, w: w - 0.44, h: h - 0.76, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: o.taille || 12, color: INK_SOFT, lineSpacingMultiple: 1.12, valign: "top" });
  });
}
/** Ligne clé-valeur en colonne, pour les tables de réglages. */
function table(s, x, y, w, lignes, opts) {
  const o = opts || {};
  const hl = o.hauteur || 0.36;
  lignes.forEach(([k, v], i) => {
    const yy = y + i * hl;
    if (i % 2 === 0) {
      s.addShape(pres.shapes.RECTANGLE, { x, y: yy, w, h: hl,
        fill: { color: o.zebre || TINT }, line: { color: o.zebre || TINT, width: 0 } });
    }
    s.addText(k, { x: x + 0.16, y: yy, w: w * 0.62, h: hl, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: o.taille || 12, color: INK_SOFT, valign: "middle" });
    s.addText(v, { x: x + w * 0.62, y: yy, w: w * 0.38 - 0.16, h: hl, isTextBox: true, margin: 0,
      fontFace: MONO, fontSize: o.taille || 12, bold: true, color: o.accent || VIOLET,
      align: "right", valign: "middle" });
  });
}

// ════════════════════════════════════════════════════════ ACTE 0 · LA QUESTION

// ── 1 · TITRE ───────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addText("PROJET LLM-AGENTS GAMA", { x: M, y: 1.5, w: W - 2 * M, h: 0.34, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 12, bold: true, color: AMBER, charSpacing: 3, valign: "middle" });
  s.addText("La vie d'un souvenir", { x: M, y: 2.0, w: W - 2 * M, h: 1.2, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 54, bold: true, color: WHITE, valign: "middle" });
  s.addShape(pres.shapes.RECTANGLE, { x: M, y: 3.32, w: 2.2, h: 0.05,
    fill: { color: AMBER }, line: { color: AMBER, width: 0 } });
  s.addText(
    "Ce qu'un agent retient d'un mardi soir, et ce que cela change à sa décision du vendredi. " +
    "Vingt planches, un seul souvenir, suivi de bout en bout : du trajet qui le crée à la " +
    "décision qu'il infléchit, puis à son effacement.",
    { x: M, y: 3.62, w: 9.4, h: 1.3, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 16, color: MUTED_DARK, lineSpacingMultiple: 1.25, valign: "top" });
  s.addText("Mécanisme en service · ticket 071 (cinq lots) et ticket 077 · septembre 2026",
    { x: M, y: 6.5, w: W - 2 * M, h: 0.34, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 11, color: VIOLET_PALE, valign: "middle" });
}

// ── 2 · LA QUESTION ─────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "La question", "Que reste-t-il du mardi, le vendredi ?");
  card(s, M, 1.52, W - 2 * M, 1.12, TINT_DEEP, VIOLET_PALE);
  s.addText(CAS.scene, { x: M + 0.34, y: 1.52, w: W - 2 * M - 0.68, h: 1.12, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 22, bold: true, color: INK, valign: "middle" });

  rangee(s, 2.96, 1.72, [
    ["Mardi 17 h 10", "L'agent subit le retard. La simulation le mesure : mode, lieu, créneau, motif, météo, minutes perdues."],
    ["Mardi 22 h", "La consolidation du soir relit sa journée et peut en tirer un concept — une phrase générale sur le métro aux heures de pointe."],
    ["Vendredi 8 h", "Il décide de son trajet. Le souvenir du mardi remonte-t-il ? Et si oui, pourquoi lui plutôt qu'un autre ?"],
  ]);

  banner(s, 5.0, "Trois rouages répondent : ce qui QUALIFIE un souvenir, ce qui le fait DURER, et ce qui le fait REMONTER. Les vingt planches les ouvrent dans cet ordre.", VIOLET, WHITE);

  s.addText(
    "Le dispositif ne stocke pas des décisions, il stocke du vécu. C'est la distinction qui " +
    "porte tout le reste : un agent qui se rappellerait ses choix se citerait lui-même ; " +
    "un agent qui se rappelle ce qu'il a subi peut changer d'avis.",
    { x: M, y: 6.02, w: W - 2 * M, h: 0.5, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, italic: true, color: INK_SOFT, valign: "middle" });
}

// ════════════════════════════════════════════════════════ ACTE 1 · LE FAIT ENTRE

// ── 3 · CE QUE LA SIMULATION MESURE ─────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 1 · le fait entre", "Ce que la simulation sait, et à quel instant");
  fil(s, "Mardi 17 h 10");

  s.addText(
    "Le souvenir s'écrit à l'ARRIVÉE, et nulle part ailleurs. C'est le seul instant où le mode " +
    "réellement emprunté et le retard réellement subi sont connus ensemble — au départ, le mode " +
    "n'est qu'une intention, et le retard n'existe pas encore.",
    { x: M, y: 1.46, w: W - 2 * M, h: 0.68, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 13, color: INK_SOFT, lineSpacingMultiple: 1.15, valign: "top" });

  rangee(s, 2.26, 1.5, [
    ["Mode", "Métro — normalisé à l'écriture par la hiérarchie AUAT/CEREMA, pas par une sixième liste littérale."],
    ["Lieu", "Zone de destination."],
    ["Créneau", "Pointe du soir."],
  ]);
  rangee(s, 3.94, 1.5, [
    ["Motif", "Retour au domicile."],
    ["Météo", "Le cinquième axe — le seul des cinq qui ne soit pas déjà un critère de rappel."],
    ["Retard subi", `${CAS.retardS} s, soit trente minutes. Mesuré, pas déclaré.`],
  ]);

  banner(s, 5.66, "Normaliser à l'ÉCRITURE et non à la lecture : un axe mal orthographié une fois le reste pour toujours, et le rappel s'appuie dessus des semaines plus tard.", AMBER, INK);
  source(s, "services/llm-agents/llm/axes.py · MoveLogger, journal des trajets alimenté à l'arrivée");
}

// ── 4 · CE QUE PORTE UN SOUVENIR ────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 1 · le fait entre", "Vingt-trois champs, dont cinq pour les concepts");
  fil(s, "Mardi 17 h 10");

  table(s, M, 1.5, 5.85, [
    ["texte", "le vécu"],
    ["mode · lieu · créneau · motif · météo", "5 axes"],
    ["gravité déterministe", "0,00 – 1,00"],
    ["niveau nommé", "5 échelons"],
    ["force (durée de vie)", "jours"],
    ["timestamp", "heure du fait"],
    ["dernier_rappel", "invisible"],
  ]);
  table(s, M + 6.25, 1.5, 5.85, [
    ["panier (mode, motif)", "schéma v2"],
    ["observations", "compteur"],
    ["contre_exemples", "compteur"],
    ["derniere_observation", "≠ timestamp"],
    ["depasse_le", "mise à l'écart"],
  ], { accent: BRICK, hauteur: 0.42 });

  s.addText("les 5 propres au concept", { x: M + 6.25, y: 4.06, w: 5.85, h: 0.28, isTextBox: true,
    margin: 0, fontFace: BODY, fontSize: 10, italic: true, color: MUTED, align: "right", valign: "middle" });
  s.addText("7 des 17 champs communs", { x: M, y: 4.06, w: 5.85, h: 0.28, isTextBox: true,
    margin: 0, fontFace: BODY, fontSize: 10, italic: true, color: MUTED, valign: "middle" });

  card(s, M, 4.3, W - 2 * M, 1.5, TINT_DEEP, VIOLET_PALE);
  s.addText("Deux horodatages, et c'est voulu", { x: M + 0.3, y: 4.44, w: W - 2 * M - 0.6, h: 0.36,
    isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 16, bold: true, color: INK, valign: "middle" });
  s.addText(
    "« timestamp » est l'heure de l'ÉVÉNEMENT, et elle s'affiche dans le prompt : l'agent lit " +
    "« mardi soir », pas « il y a trois jours ». « dernier_rappel » est invisible du modèle et " +
    "sert uniquement à l'oubli. Les confondre revenait à rajeunir un souvenir en le montrant — " +
    "c'est le premier défaut que la consolidation a fait apparaître, corrigé avant le code.",
    { x: M + 0.3, y: 4.82, w: W - 2 * M - 0.6, h: 0.9, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, color: INK_SOFT, lineSpacingMultiple: 1.14, valign: "top" });

  pied(s, "La spécification cible annonçait 15 + 3. L'arbitrage du lot 2 (cinquième axe, météo) et le lot 3 ont porté le compte à 17 + 5, plus schema_version. La relecture reste tolérante dans les deux sens.");
  source(s, "services/llm-agents/llm/memory.py · MemoryEntry, 23 champs · schémas v2 (météo) et v3 (opérations)");
}

// ── 5 · LA GRAVITÉ, SUR LE CAS ──────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 1 · le fait entre", "D'où vient la gravité, calculée sur ce mardi");
  fil(s, "Mardi 17 h 10");

  const comps = [
    ["Retard subi", N(CAS.partRetard), "30 min, au point de référence", VIOLET, true],
    ["Incident réseau", N(CAS.partIncident), "ligne interrompue", VIOLET, true],
    ["Correspondance ratée", "0,00", "poids 0,20 — inactif ici", MUTED, false],
    ["Mode contraint", "0,00", "poids 0,10 — inactif ici", MUTED, false],
  ];
  const wc = (W - 2 * M - 0.84) / 4;
  comps.forEach(([lab, val, note, col, actif], i) => {
    const x = M + i * (wc + 0.28);
    card(s, x, 1.5, wc, 1.66, actif ? TINT_DEEP : TINT, actif ? VIOLET_PALE : TINT_DEEP);
    s.addText(lab, { x: x + 0.2, y: 1.62, w: wc - 0.4, h: 0.34, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, bold: true, color: actif ? INK : MUTED, valign: "middle" });
    s.addText(val, { x: x + 0.2, y: 1.96, w: wc - 0.4, h: 0.62, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: 32, bold: true, color: col, valign: "middle" });
    s.addText(note, { x: x + 0.2, y: 2.58, w: wc - 0.4, h: 0.46, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 10, color: MUTED, valign: "top" });
  });

  card(s, M, 3.34, W - 2 * M, 1.0, INK, INK);
  s.addText("Gravité de ce souvenir", { x: M + 0.34, y: 3.34, w: 6.0, h: 1.0, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 19, bold: true, color: WHITE, valign: "middle" });
  s.addText(`${N(CAS.partRetard)}  +  ${N(CAS.partIncident)}  =  ${N(CAS.gravite)}`,
    { x: W - M - 6.2, y: 3.34, w: 5.86, h: 1.0, isTextBox: true, margin: 0,
      fontFace: MONO, fontSize: 26, bold: true, color: AMBER, align: "right", valign: "middle" });

  banner(s, 4.52, `Seuil de rupture Θ = ${N(P.theta)} · franchi tout juste. Au-delà, le souvenir est servi SANS condition de contexte.`, BRICK, WHITE);

  s.addText(
    "⚠ La composante « incident réseau » n'est alimentée par aucun événement GAMA à ce jour : " +
    "elle est déclarée comme telle, et c'est le catalogue des chocs qui la pose. Le dire vaut " +
    "mieux que la laisser croire mesurée.",
    { x: M, y: 5.6, w: W - 2 * M, h: 0.62, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, italic: true, color: BRICK, lineSpacingMultiple: 1.14, valign: "top" });
  source(s, "llm/gravite.py · POIDS_RETARD 0,50 · POIDS_INCIDENT_RESEAU 0,20 · memoire__theta_gravite_cumulee 0,7");
}

// ── 6 · LES CINQ ÉCHELONS ───────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 1 · le fait entre", "Cinq échelons, ancrés par une conséquence");
  fil(s, "Mardi 17 h 10");

  const ech = [
    ["anodin", "0,10", "Everything went as I had planned."],
    ["notable", "0,30", "A noticeable deviation, with no consequence for the rest of my day."],
    ["gênant", "0,50", "It cost me time, or forced me to shift a schedule."],
    ["grave", "0,75", "It made me miss something, or put me in difficulty."],
    ["marquant", "1,00", "I will remember this in a month; it changes how I travel."],
  ];
  ech.forEach(([nom, val, ancre], i) => {
    const y = 1.5 + i * 0.72;
    const vif = nom === "grave";
    card(s, M, y, W - 2 * M, 0.62, vif ? TINT_DEEP : TINT, vif ? VIOLET_PALE : TINT_DEEP);
    numDot(s, M + 0.18, y + 0.1, i + 1, vif ? VIOLET : VIOLET_PALE, WHITE);
    s.addText(nom, { x: M + 0.78, y, w: 1.7, h: 0.62, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: 16, bold: true, color: INK, valign: "middle" });
    s.addText(val, { x: M + 2.5, y, w: 0.9, h: 0.62, isTextBox: true, margin: 0,
      fontFace: MONO, fontSize: 15, bold: true, color: VIOLET, valign: "middle" });
    s.addText(ancre, { x: M + 3.6, y, w: W - 2 * M - 3.8, h: 0.62, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, italic: true, color: INK_SOFT, valign: "middle" });
  });

  banner(s, 5.2, "RÈGLE DU MAXIMUM, non négociable : entre la gravité calculée et celle que le modèle juge, on retient la plus forte. Un modèle qui minimise ne peut pas effacer un fait mesuré.", INK, WHITE);

  s.addText(
    "Les ancres sont en anglais parce que le dispositif s'adresse au modèle en anglais ; le " +
    "vocabulaire canonique reste français, et les deux sont acceptés en entrée. Chaque échelon " +
    "est ancré par une CONSÉQUENCE OBSERVABLE et non par une intensité ressentie : c'est ce qui " +
    "rend la valeur comparable d'un agent et d'un jour à l'autre, là où un rang ne l'est pas.",
    { x: M, y: 6.14, w: W - 2 * M, h: 0.74, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 11.5, color: INK_SOFT, lineSpacingMultiple: 1.14, valign: "top" });
}

// ════════════════════════════════════════════════════════ ACTE 2 · LE SOUVENIR DURE

// ── 7 · LA DURÉE DE VIE ─────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 2 · le souvenir dure", "Ce que la gravité achète : des jours");
  fil(s, "Mardi soir → vendredi");

  s.addText(`force  =  min( S0 × (1 + k · I) , ${P.forceMax} )      avec  S0 = ${N(P.S0, 1)} j   et   k = ${P.k}`,
    { x: M, y: 1.46, w: W - 2 * M, h: 0.48, isTextBox: true, margin: 0,
      fontFace: MONO, fontSize: 16, bold: true, color: VIOLET, valign: "middle" });

  rangee(s, 2.06, 1.24, [
    ["Trajet banal · I = 0,00", `force = ${N(CAS.forceBanal, 1)} jours`, TINT, TINT_DEEP],
    [`Ce choc · I = ${N(CAS.gravite)}`, `force = ${N(CAS.forceChoc)} jours`, TINT_DEEP, VIOLET_PALE],
  ], { tailleTitre: 15, taille: 18 });

  s.addText("Ce qu'il en reste, jour après jour", { x: M, y: 3.5, w: W - 2 * M, h: 0.36, isTextBox: true,
    margin: 0, fontFace: HEAD, fontSize: 16, bold: true, color: INK, valign: "middle" });

  const wj = (W - 2 * M - 0.84) / 4;
  CAS.decroissance.forEach(([j, choc, banal], i) => {
    const x = M + i * (wj + 0.28);
    card(s, x, 3.94, wj, 1.5);
    s.addText(`J+${j}`, { x: x + 0.2, y: 4.04, w: wj - 0.4, h: 0.32, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 11, bold: true, color: MUTED, charSpacing: 1, valign: "middle" });
    s.addText(`${N(choc, 1)} %`, { x: x + 0.2, y: 4.36, w: wj - 0.4, h: 0.52, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: 26, bold: true, color: VIOLET, valign: "middle" });
    s.addText(`le choc`, { x: x + 0.2, y: 4.86, w: wj - 0.4, h: 0.26, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 10, color: MUTED, valign: "middle" });
    s.addText(`${N(banal, 1)} %  ·  trajet banal`, { x: x + 0.2, y: 5.12, w: wj - 0.4, h: 0.26,
      isTextBox: true, margin: 0, fontFace: BODY, fontSize: 11, color: MUTED, valign: "middle" });
  });

  banner(s, 5.62, `Trois jours après, le choc pèse encore ${N(CAS.decroissance[1][1], 1)} % quand le trajet banal est tombé à ${N(CAS.decroissance[1][2], 1)} %. L'oubli à l'horloge n'explique donc AUCUN retour au métro dans la fenêtre de l'expérience.`, VIOLET, WHITE);
  source(s, "llm/gravite.py · force_initiale, poids_temporel · long_term_retrieval__force_base_jours 2.8 · memoire__force_k_importance 6.0");
}

// ── 8 · LE RENFORCEMENT ─────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 2 · le souvenir dure", "Se rappeler d'un souvenir le prolonge");
  fil(s, "À chaque rappel");

  rangee(s, 1.5, 1.6, [
    ["Renforcement", `+ ${P.delta} jour à chaque rappel. Additif, jamais multiplicatif : un souvenir souvent servi ne devient pas éternel.`],
    ["Plafond", `${P.forceMax} jours, appliqué dès l'écriture. Un souvenir très grave ne peut pas naître immortel.`],
    ["Purge", `Sous ${N(P.purge * 100, 0)} % de son poids, le souvenir épisodique est retiré. Les CONCEPTS ne sont jamais purgés.`],
  ]);

  card(s, M, 3.34, W - 2 * M, 1.0, INK, INK);
  s.addText("Ce choc, après un rappel", { x: M + 0.34, y: 3.34, w: 6.0, h: 1.0, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 19, bold: true, color: WHITE, valign: "middle" });
  s.addText(`${N(CAS.forceChoc)} j   →   ${N(CAS.forceApresRappel)} j`,
    { x: W - M - 6.2, y: 3.34, w: 5.86, h: 1.0, isTextBox: true, margin: 0,
      fontFace: MONO, fontSize: 26, bold: true, color: AMBER, align: "right", valign: "middle" });

  banner(s, 4.52, "Le renforcement est limité au top-K SERVI, pas au top-K calculé. Un souvenir classé puis écarté n'a pas été rappelé — le prolonger reviendrait à récompenser un candidat malheureux.", AMBER, INK);

  s.addText(
    "La décroissance court depuis le DERNIER RAPPEL, pas depuis l'écriture. Un souvenir jamais " +
    "reconvoqué s'efface à son rythme ; un souvenir qui ressort régulièrement reste disponible. " +
    "C'est la récence au sens de Park et al., et non l'âge.",
    { x: M, y: 5.6, w: W - 2 * M, h: 0.7, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12.5, color: INK_SOFT, lineSpacingMultiple: 1.16, valign: "top" });
  source(s, "memoire__force_delta_rappel_jours 1.0 · memoire__force_max_jours 30.0 · memoire__purge_seuil_poids 0.01");
}

// ── 9 · LES DEUX RÉGIMES ────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 2 · le souvenir dure", "Ce que le temps efface, et ce qu'il n'efface pas");
  fil(s, "La planche centrale");

  const wc = (W - 2 * M - 0.4) / 2;
  card(s, M, 1.5, wc, 2.5, TINT, TINT_DEEP);
  s.addText("ÉPISODIQUE", { x: M + 0.3, y: 1.64, w: wc - 0.6, h: 0.34, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 11, bold: true, color: VIOLET, charSpacing: 2, valign: "middle" });
  s.addText("Le mardi soir, tel qu'il a été vécu", { x: M + 0.3, y: 1.98, w: wc - 0.6, h: 0.4,
    isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 17, bold: true, color: INK, valign: "middle" });
  s.addText(
    "S'efface à l'horloge. Sa force décroît depuis le dernier rappel, et il est purgé sous un " +
    "pour cent. C'est un fait daté : il n'a pas vocation à survivre indéfiniment.",
    { x: M + 0.3, y: 2.44, w: wc - 0.6, h: 1.4, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12.5, color: INK_SOFT, lineSpacingMultiple: 1.16, valign: "top" });

  card(s, M + wc + 0.4, 1.5, wc, 2.5, TINT_DEEP, BRICK);
  s.addText("SÉMANTIQUE", { x: M + wc + 0.7, y: 1.64, w: wc - 0.6, h: 0.34, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 11, bold: true, color: BRICK, charSpacing: 2, valign: "middle" });
  s.addText("« Le métro est incertain aux heures de pointe »", { x: M + wc + 0.7, y: 1.98, w: wc - 0.6,
    h: 0.4, isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 17, bold: true, color: INK, valign: "middle" });
  s.addText(
    "Ne s'efface JAMAIS à l'horloge. Seule une contradiction l'éteint. Une connaissance ne " +
    "devient pas fausse parce qu'elle a vieilli — elle devient fausse quand on observe le " +
    "contraire.",
    { x: M + wc + 0.7, y: 2.44, w: wc - 0.6, h: 1.4, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12.5, color: INK_SOFT, lineSpacingMultiple: 1.16, valign: "top" });

  card(s, M, 4.2, W - 2 * M, 1.62, INK, INK);
  s.addText("Ce que ce partage a corrigé", { x: M + 0.34, y: 4.34, w: W - 2 * M - 0.68, h: 0.38,
    isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 17, bold: true, color: AMBER, valign: "middle" });
  s.addText(
    "Avant ce partage, un concept de dix jours tombait de 1,00 à 0,028 sans qu'aucune " +
    "observation ne l'ait infirmé. L'agent oubliait ce qu'il savait au seul motif que le temps " +
    "passait — et le réapprenait à l'identique. C'est le point le plus fort du dispositif, et " +
    "celui qui se transporte le plus directement à l'article.",
    { x: M + 0.34, y: 4.74, w: W - 2 * M - 0.68, h: 0.98, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12.5, color: MUTED_DARK, lineSpacingMultiple: 1.18, valign: "top" });

  pied(s, "La rétention tient au POIDS et non au type : c'est le poids qui décide, et le sémantique n'en perd pas à l'horloge.");
}

// ── 10 · LE MUR SUPPRIMÉ ────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 2 · le souvenir dure", "Deux retards différents ne se valent plus");
  fil(s, "Ticket 095");

  s.addText(
    "Le retard de référence vaut trente minutes : à ce point, la composante rend exactement " +
    "0,50. Au-delà, elle suivait un PALIER — soixante minutes et quatre-vingt-dix minutes " +
    "rendaient la même valeur, et deux journées incomparables recevaient la même gravité. " +
    "Elle suit désormais une asymptote calée pour que la pente reste continue au point d'ancrage.",
    { x: M, y: 1.46, w: W - 2 * M, h: 0.9, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 13, color: INK_SOFT, lineSpacingMultiple: 1.16, valign: "top" });

  const wa = (W - 2 * M - 0.84) / 4;
  CAS.asymptote.forEach(([lab, val], i) => {
    const x = M + i * (wa + 0.28);
    const ancre = i === 0;
    card(s, x, 2.5, wa, 1.5, ancre ? TINT_DEEP : TINT, ancre ? VIOLET_PALE : TINT_DEEP);
    s.addText(lab, { x: x + 0.2, y: 2.64, w: wa - 0.4, h: 0.34, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, bold: true, color: MUTED, valign: "middle" });
    s.addText(N(val, 3), { x: x + 0.2, y: 2.98, w: wa - 0.4, h: 0.62, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: 28, bold: true, color: ancre ? VIOLET : INK, valign: "middle" });
    s.addText(ancre ? "point d'ancrage" : "distinct du précédent", { x: x + 0.2, y: 3.6, w: wa - 0.4,
      h: 0.3, isTextBox: true, margin: 0, fontFace: BODY, fontSize: 10, color: MUTED, valign: "middle" });
  });

  banner(s, 4.2, "Retirer le palier sans changer de forme ne supprime pas le mur : il le DÉPLACE. Une composante linéaire non bornée vaudrait 1,0 dès soixante minutes, et les trois autres composantes cesseraient de peser.", BRICK, WHITE);

  card(s, M, 5.2, W - 2 * M, 1.2, TINT, TINT_DEEP);
  s.addText(
    "⚠ Le retard de référence n'a pas encore de règle de conception écrite. Trente minutes est " +
    "une demi-heure ronde, pas une grandeur mesurée — et c'est elle qui décide quelles journées " +
    "franchissent Θ. La règle est à rattacher à la distribution des durées de déplacement de la " +
    "cohorte ; elle est portée par le lot F5 du ticket 095.",
    { x: M + 0.3, y: 5.32, w: W - 2 * M - 0.6, h: 0.98, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, color: BRICK, lineSpacingMultiple: 1.14, valign: "top" });
  source(s, "memoire__retard_ref_s 1800 · memoire__retard_saturation « asymptote » · memoire__retard_gravite_max 0.70");
}

// ════════════════════════════════════════════════════════ ACTE 3 · LE SOIR CONSOLIDE

// ── 11 · LES TROIS CONDITIONS ───────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 3 · le soir consolide", "Trois conditions déclenchent une réflexion");
  fil(s, "Mardi 22 h");

  rangee(s, 1.5, 2.0, [
    ["1 · Le plancher journalier", "Une réflexion à la fin de chaque jour simulé, à 22 h, indépendamment du remplissage. C'est le RÉGIME : une journée sans réflexion serait une journée sans apprentissage."],
    ["2 · Le remplissage", "Le seuil volumétrique historique. Il subsiste, mais il n'est plus la condition principale — il déclenchait des réflexions au milieu de rien."],
    [`3 · La rupture · Θ = ${N(P.theta)}`, "Une gravité cumulée qui franchit le seuil déclenche une consolidation SANS attendre le soir. C'est l'EXCEPTION, réservée aux journées qui sortent de l'ordinaire."],
  ]);

  card(s, M, 3.78, W - 2 * M, 1.02, TINT_DEEP, VIOLET_PALE);
  s.addText("Ce mardi", { x: M + 0.34, y: 3.78, w: 3.0, h: 1.02, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 18, bold: true, color: INK, valign: "middle" });
  s.addText(`gravité ${N(CAS.gravite)}  ≥  Θ ${N(P.theta)}  →  la rupture est franchie, tout juste`,
    { x: M + 3.2, y: 3.78, w: W - 2 * M - 3.5, h: 1.02, isTextBox: true, margin: 0,
      fontFace: MONO, fontSize: 15, bold: true, color: BRICK, align: "right", valign: "middle" });

  banner(s, 4.98, "Trois motifs de déclenchement, comptés SÉPARÉMENT, avec une alarme de rareté. C'est la mesure qui manquait pour valider Θ sur autre chose qu'une intuition.", VIOLET, WHITE);

  s.addText(
    "La réflexion par déplacement a été évaluée puis abandonnée : le plancher journalier coûte " +
    "0,69 à 0,96 appel mémoire par déplacement, contre 1,05 pour une réflexion à chaque trajet. " +
    "Le régime retenu est le moins cher des deux qui tiennent.",
    { x: M, y: 5.94, w: W - 2 * M, h: 0.6, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, italic: true, color: INK_SOFT, lineSpacingMultiple: 1.14, valign: "top" });
}

// ── 12 · LE PANIER ──────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 3 · le soir consolide", "Un panier de candidats, pas une identité");
  fil(s, "Mardi 22 h");

  s.addText(
    "Le couple (mode, motif) — ici « métro, retour au domicile » — désigne un ENSEMBLE de " +
    "concepts candidats, et non un concept unique.",
    { x: M, y: 1.46, w: W - 2 * M, h: 0.5, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 14, color: INK_SOFT, valign: "top" });

  const wc = (W - 2 * M - 0.4) / 2;
  card(s, M, 2.08, wc, 2.2, TINT, BRICK);
  s.addText("Si le couple était une IDENTITÉ", { x: M + 0.3, y: 2.22, w: wc - 0.6, h: 0.38,
    isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 16, bold: true, color: BRICK, valign: "middle" });
  s.addText(
    "L'agent n'aurait droit qu'à UNE SEULE pensée par mode et par motif. « Le métro est " +
    "incertain le soir » et « le métro me fait gagner du temps le matin » ne pourraient pas " +
    "coexister : la seconde écraserait la première.",
    { x: M + 0.3, y: 2.64, w: wc - 0.6, h: 1.44, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12.5, color: INK_SOFT, lineSpacingMultiple: 1.16, valign: "top" });

  card(s, M + wc + 0.4, 2.08, wc, 2.2, TINT_DEEP, VIOLET_PALE);
  s.addText("Le panier, tel qu'il est implémenté", { x: M + wc + 0.7, y: 2.22, w: wc - 0.6, h: 0.38,
    isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 16, bold: true, color: VIOLET, valign: "middle" });
  s.addText(
    "Le couple ouvre un panier. Le modèle y lit les candidats et désigne celui qu'il corrige, " +
    "confirme ou contredit — ou décide qu'aucun ne convient et en crée un. Plusieurs pensées " +
    "sur le même mode cohabitent, et se corrigent séparément.",
    { x: M + wc + 0.7, y: 2.64, w: wc - 0.6, h: 1.44, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12.5, color: INK_SOFT, lineSpacingMultiple: 1.16, valign: "top" });

  banner(s, 4.5, `Le panier est borné : ${P.vivierB} concepts par mode. Au-delà, les moins confiants sortent du service — et c'est leur sortie qui date leur mise à l'écart.`, VIOLET, WHITE);

  s.addText(
    "Le champ « mode » sur le concept (schéma v2) est ce qui rend le panier atteignable : sans " +
    "lui, la mémoire longue ne contient que des réflexions et des concepts sans axe, et le " +
    "vivier sémantique ne trouverait rien.",
    { x: M, y: 5.5, w: W - 2 * M, h: 0.68, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, color: INK_SOFT, lineSpacingMultiple: 1.14, valign: "top" });
  source(s, "services/llm-agents/llm/concepts.py · memoire__vivier_b_par_mode 8 · schéma v2");
}

// ── 13 · LES QUATRE OPÉRATIONS ──────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 3 · le soir consolide", "Quatre opérations, désignées par le modèle");
  fil(s, "Mardi 22 h");

  const ops = [
    ["créer", "Aucun candidat ne convient : une pensée neuve entre au panier, à 0,50 de confiance."],
    ["confirmer", "Le vécu va dans le sens du concept : une observation de plus."],
    ["préciser", "Le concept est vrai mais trop large : son énoncé se resserre."],
    ["contredire", "Le vécu l'infirme : un contre-exemple, et la confiance chute."],
  ];
  const wo = (W - 2 * M - 0.84) / 4;
  ops.forEach(([nom, desc], i) => {
    const x = M + i * (wo + 0.28);
    const rouge = nom === "contredire";
    card(s, x, 1.5, wo, 2.0, rouge ? TINT_DEEP : TINT, rouge ? BRICK : TINT_DEEP);
    numDot(s, x + 0.2, 1.64, i + 1, rouge ? BRICK : VIOLET, WHITE);
    s.addText(nom, { x: x + 0.72, y: 1.62, w: wo - 0.9, h: 0.46, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: 18, bold: true, color: rouge ? BRICK : INK, valign: "middle" });
    s.addText(desc, { x: x + 0.2, y: 2.18, w: wo - 0.4, h: 1.2, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, color: INK_SOFT, lineSpacingMultiple: 1.16, valign: "top" });
  });

  card(s, M, 3.72, W - 2 * M, 1.5, INK, INK);
  s.addText("Coût marginal : zéro", { x: M + 0.34, y: 3.86, w: W - 2 * M - 0.68, h: 0.38,
    isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 18, bold: true, color: AMBER, valign: "middle" });
  s.addText(
    "L'opération est désignée dans l'appel de consolidation qui a DÉJÀ lieu. Aucune inférence " +
    "supplémentaire, et surtout aucun seuil de similarité à calibrer : c'est le modèle qui dit " +
    "si le vécu confirme ou contredit, là où un seuil numérique aurait demandé un réglage " +
    "arbitraire, invérifiable, et différent pour chaque mode.",
    { x: M + 0.34, y: 4.26, w: W - 2 * M - 0.68, h: 0.86, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12.5, color: MUTED_DARK, lineSpacingMultiple: 1.18, valign: "top" });

  banner(s, 5.42, "Un compteur par opération, et une alarme « le modèle confirme tout » : un modèle qui ne contredit jamais rend le dispositif inerte sans rien casser de visible.", AMBER, INK);
  source(s, "llm/concepts.py · OPERATIONS = (creer, confirmer, preciser, contredire) · schéma v3");
}

// ── 14 · LA CONFIANCE ───────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 3 · le soir consolide", "La confiance, et la mise à l'écart");
  fil(s, "Mardi 22 h");

  s.addText("confiance  =  ( obs + 1 )  /  ( obs + contre-exemples + 2 )",
    { x: M, y: 1.44, w: 8.6, h: 0.42, isTextBox: true, margin: 0,
      fontFace: MONO, fontSize: 13.5, bold: true, color: VIOLET, valign: "middle" });
  s.addText("règle de succession de Laplace", { x: M + 8.7, y: 1.44, w: W - 2 * M - 8.7, h: 0.42,
    isTextBox: true, margin: 0, fontFace: BODY, fontSize: 12, italic: true, color: MUTED,
    align: "right", valign: "middle" });

  const etats = [
    ["Concept neuf", "0 obs · 0 contre", "0,50", VIOLET, "Naît exactement au seuil de service — il n'a encore rien prouvé."],
    ["Une contradiction", "0 obs · 1 contre", "0,33", BRICK, "Passe sous le seuil : HORS SERVICE, et daté."],
    ["Bien établi", "6 obs · 1 contre", "0,78", VIOLET, "Une contradiction isolée ne renverse pas six observations."],
  ];
  const we = (W - 2 * M - 0.56) / 3;
  etats.forEach(([lab, compte, val, col, note], i) => {
    const x = M + i * (we + 0.28);
    card(s, x, 2.02, we, 2.1, i === 1 ? TINT_DEEP : TINT, i === 1 ? BRICK : TINT_DEEP);
    s.addText(lab, { x: x + 0.2, y: 2.14, w: we - 0.4, h: 0.34, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: 15, bold: true, color: INK, valign: "middle" });
    s.addText(compte, { x: x + 0.2, y: 2.48, w: we - 0.4, h: 0.28, isTextBox: true, margin: 0,
      fontFace: MONO, fontSize: 11, color: MUTED, valign: "middle" });
    s.addText(val, { x: x + 0.2, y: 2.8, w: we - 0.4, h: 0.6, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: 30, bold: true, color: col, valign: "middle" });
    s.addText(note, { x: x + 0.2, y: 3.42, w: we - 0.4, h: 0.6, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 11.5, color: INK_SOFT, lineSpacingMultiple: 1.14, valign: "top" });
  });

  card(s, M, 4.34, W - 2 * M, 1.72, TINT, TINT_DEEP);
  s.addText("Jamais supprimé — seulement daté", { x: M + 0.3, y: 4.46, w: W - 2 * M - 0.6, h: 0.38,
    isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 17, bold: true, color: INK, valign: "middle" });
  s.addText(
    "Un concept sous le seuil sort du service, mais reste en mémoire avec sa date : c'est " +
    "l'observable que l'expérience cherche — QUAND une croyance a cessé de tenir. La date se " +
    "pose à la CESSATION DE SERVICE, et non aux trois contre-exemples : un concept peu observé " +
    "sort du panier dès qu'il n'est plus servi, donc n'est plus montré, donc ne peut plus être " +
    "contredit — il n'atteignait jamais les trois. Défaut trouvé en EXÉCUTANT les tests, pas en " +
    "les lisant.",
    { x: M + 0.3, y: 4.86, w: W - 2 * M - 0.6, h: 1.1, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, color: INK_SOFT, lineSpacingMultiple: 1.16, valign: "top" });

  pied(s, `Effet de bord assumé et testé : le nombre de contradictions qu'un concept peut recevoir est borné par sa sortie du panier. Seuil de service ${N(P.confianceSeuil)} · ${P.contreExemples} contre-exemples.`);
}

// ════════════════════════════════════════════════════════ ACTE 4 · LE RAPPEL

// ── 15 · LES CINQ AXES ──────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 4 · vendredi, le rappel", "Cinq axes, et l'absence qui ne s'apparie avec rien");
  fil(s, "Vendredi 8 h");

  const axes = [["Mode", "métro"], ["Lieu", "zone de destination"], ["Créneau", "pointe du soir"],
                ["Motif", "retour au domicile"], ["Météo", "pluie"]];
  const wx = (W - 2 * M - 4 * 0.24) / 5;
  axes.forEach(([nom, val], i) => {
    const x = M + i * (wx + 0.24);
    card(s, x, 1.5, wx, 1.2, TINT_DEEP, VIOLET_PALE);
    s.addText(nom, { x: x + 0.16, y: 1.62, w: wx - 0.32, h: 0.4, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: 15, bold: true, color: INK, align: "center", valign: "middle" });
    s.addText(val, { x: x + 0.16, y: 2.02, w: wx - 0.32, h: 0.56, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 11, color: MUTED, align: "center", valign: "top" });
  });

  card(s, M, 2.96, W - 2 * M, 1.5, INK, INK);
  s.addText("Un axe absent ne s'apparie avec RIEN", { x: M + 0.34, y: 3.1, w: W - 2 * M - 0.68, h: 0.4,
    isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 19, bold: true, color: AMBER, valign: "middle" });
  s.addText(
    "Pas même avec un autre axe absent. Deux souvenirs dont on ignore la météo ne se " +
    "ressemblent pas pour autant : les traiter comme concordants ferait remonter n'importe " +
    "quoi dès que la donnée manque, et la rareté d'une information deviendrait un facteur de " +
    "rappel.",
    { x: M + 0.34, y: 3.52, w: W - 2 * M - 0.68, h: 0.84, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12.5, color: MUTED_DARK, lineSpacingMultiple: 1.18, valign: "top" });

  banner(s, 4.64, "La météo est le CINQUIÈME axe, et le seul qui compte dans l'affinité catégorielle : mode, créneau et motif sont déjà des axes, les compter deux fois rendait le score ininterprétable.", VIOLET, WHITE);

  s.addText(
    "Les axes sont normalisés à l'écriture, par la hiérarchie AUAT/CEREMA pour le mode — pas " +
    "par une sixième liste littérale qui aurait divergé des cinq autres à la première retouche.",
    { x: M, y: 5.66, w: W - 2 * M, h: 0.6, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, italic: true, color: INK_SOFT, lineSpacingMultiple: 1.14, valign: "top" });
  source(s, "llm/axes.py · mode_canonique, normaliser_lieu, creneau_de, normaliser_motif, meteo_de");
}

// ── 16 · LES TROIS VIVIERS ──────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 4 · vendredi, le rappel", "Trois viviers, puis un seul classement");
  fil(s, "Vendredi 8 h");

  rangee(s, 1.5, 2.3, [
    ["A · Contexte", "Les souvenirs dont les axes concordent avec la situation du moment. C'est la voie ordinaire : on se rappelle ce qui ressemble à ce qu'on vit."],
    ["B · Sémantique", `Les concepts du mode envisagé, ${P.vivierB} au plus. Lus en RAM, SANS plongement : un concept porte son mode, il n'y a rien à comparer vectoriellement.`],
    ["C · Chocs", `Les souvenirs qui ont franchi Θ, ${P.vivierC} au plus. Ils remontent HORS CONTEXTE — c'est tout l'intérêt : le mardi ressort le vendredi même si rien ne s'y ressemble.`],
  ]);

  banner(s, 4.08, "Les trois viviers sont dédoublonnés avant classement : un souvenir qui appartient à deux viviers ne compte pas deux fois.", VIOLET, WHITE);

  card(s, M, 5.08, W - 2 * M, 1.3, TINT, TINT_DEEP);
  s.addText(
    "Le vivier C est la raison pour laquelle le souvenir du mardi est disponible le vendredi. " +
    "Sans lui, il faudrait que la situation du vendredi ressemble à celle du mardi pour qu'il " +
    "remonte — or une rupture se caractérise précisément par le fait qu'elle déborde son " +
    "contexte d'origine.",
    { x: M + 0.3, y: 5.2, w: W - 2 * M - 0.6, h: 1.06, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12.5, color: INK_SOFT, lineSpacingMultiple: 1.16, valign: "top" });
  source(s, "llm/axes.py · memoire__vivier_b_par_mode 8 · memoire__vivier_c_taille 5");
}

// ── 17 · LE SCORE ───────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 4 · vendredi, le rappel", "Cinq composantes, et pourquoi ce souvenir-là");
  fil(s, "Vendredi 8 h");

  const comp = [
    ["Similarité", 0.30, "le texte ressemble à la situation"],
    ["Lexical", 0.10, "les mots en commun"],
    ["Récence", 0.20, "depuis le dernier rappel"],
    ["Gravité", 0.20, "ce que la journée a coûté"],
    ["Affinité météo", 0.20, "le cinquième axe"],
  ];
  const wp = (W - 2 * M - 4 * 0.24) / 5;
  comp.forEach(([nom, poids, note], i) => {
    const x = M + i * (wp + 0.24);
    const fort = poids >= 0.20;
    card(s, x, 1.5, wp, 1.96, fort ? TINT_DEEP : TINT, fort ? VIOLET_PALE : TINT_DEEP);
    s.addText(nom, { x: x + 0.16, y: 1.62, w: wp - 0.32, h: 0.38, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: 14, bold: true, color: INK, align: "center", valign: "middle" });
    s.addText(N(poids), { x: x + 0.16, y: 2.0, w: wp - 0.32, h: 0.62, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: 28, bold: true, color: fort ? VIOLET : MUTED, align: "center", valign: "middle" });
    s.addText(note, { x: x + 0.16, y: 2.64, w: wp - 0.32, h: 0.68, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 10.5, color: MUTED, align: "center", valign: "top" });
  });

  card(s, M, 3.62, W - 2 * M, 1.22, INK, INK);
  s.addText("Pourquoi le mardi remonte", { x: M + 0.34, y: 3.74, w: W - 2 * M - 0.68, h: 0.36,
    isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 17, bold: true, color: AMBER, valign: "middle" });
  s.addText(
    "Pas parce que son texte ressemble à celui du vendredi — un vendredi matin ensoleillé ne " +
    "ressemble pas à un mardi soir sous la pluie. Il remonte parce qu'il a franchi Θ et vit " +
    "dans le vivier des chocs, et parce que sa gravité pèse 0,20 du score.",
    { x: M + 0.34, y: 4.12, w: W - 2 * M - 0.68, h: 0.64, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12.5, color: MUTED_DARK, lineSpacingMultiple: 1.16, valign: "top" });

  banner(s, 5.06, "Les cinq poids basculent ENSEMBLE, et une invariante vérifie leur somme : passer de trois à cinq composantes en oubliant d'en renormaliser une aurait faussé tous les rappels en silence.", AMBER, INK);

  pied(s, "Poids en service 0,30 / 0,10 / 0,20 / 0,20 / 0,20. Vu et al. publient 0,3 / 0,3 / 0,4 sur trois composantes, la récence portant le poids fort : l'écart est propre à ce dépôt et se dit.");
  source(s, "settings.py · long_term_retrieval__{sim,keyword,time,importance,affinite}_weight");
}

// ── 18 · LES TROIS EXCEPTIONS ───────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 4 · vendredi, le rappel", "« Rien ne filtre » — et ses trois exceptions");
  fil(s, "Vendredi 8 h");

  s.addText(
    "Le principe est que rien n'est exclu a priori : tout candidat est classé, et c'est le " +
    "score qui tranche. La phrase se transporte à l'article, donc ses exceptions se disent — " +
    "il y en a trois, et pas une de plus.",
    { x: M, y: 1.46, w: W - 2 * M, h: 0.62, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 13, color: INK_SOFT, lineSpacingMultiple: 1.15, valign: "top" });

  const exc = [
    ["Identité", "Un souvenir ne se rappelle pas lui-même. Le souvenir en cours d'écriture n'entre pas dans son propre classement."],
    ["Âge", `Au-delà de la fenêtre d'âge — l'horizon de l'expérience, ${P.fenetreAge} jours au plus — le souvenir n'est plus candidat. La fenêtre valait 30 jours en dur : un run de soixante jours perdait son second mois en silence.`],
    ["Hors service", "Un concept sous le seuil de confiance n'est plus servi. Il reste en mémoire, daté, mais il ne parle plus."],
  ];
  const wx2 = (W - 2 * M - 0.56) / 3;
  exc.forEach(([nom, desc], i) => {
    const x = M + i * (wx2 + 0.28);
    card(s, x, 2.2, wx2, 2.5, TINT, TINT_DEEP);
    numDot(s, x + 0.22, 2.36, i + 1, VIOLET, WHITE);
    s.addText(nom, { x: x + 0.76, y: 2.34, w: wx2 - 0.98, h: 0.46, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: 17, bold: true, color: INK, valign: "middle" });
    s.addText(desc, { x: x + 0.22, y: 2.92, w: wx2 - 0.44, h: 1.7, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, color: INK_SOFT, lineSpacingMultiple: 1.16, valign: "top" });
  });

  banner(s, 4.94, "Une exception non dite devient un mensonge dès que la phrase quitte le dépôt. C'est pour cela qu'elles sont comptées, et que la troisième a été ajoutée au moment où elle est apparue.", INK, WHITE);

  pied(s, "La fenêtre d'âge est CÂBLÉE sur l'horizon de l'expérience, plafonné à soixante jours : le même jeu de réglages vaut de cinq à soixante jours.");
}

// ════════════════════════════════════════════════════════ ACTE 5 · CE QUE LE MODÈLE VOIT

// ── 19 · LA MÉMOIRE NOYAU ───────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  head(s, "Acte 5 · ce que le modèle voit", "Trois blocs calculés, et deux ou trois souvenirs");
  fil(s, "Vendredi 8 h");

  rangee(s, 1.5, 2.16, [
    ["Mes habitudes", "Ce que l'agent fait d'ordinaire, compté sur son journal de trajets : mode retenu et retard subi, relevés à l'arrivée."],
    ["Ce que je sais", "Les concepts en service, avec leur confiance. Calculé aussi — le lot 3 les a rendus assez structurés pour cela."],
    ["Ce qui a changé récemment", "Les ruptures encore servies, dont le mardi. Un souvenir de choc y reste le temps que sa durée de service lui accorde."],
  ]);

  card(s, M, 3.94, W - 2 * M, 1.0, TINT_DEEP, VIOLET_PALE);
  s.addText(`+ ${P.episodiques} souvenirs épisodiques`, { x: M + 0.34, y: 3.94, w: 5.0, h: 1.0,
    isTextBox: true, margin: 0, fontFace: HEAD, fontSize: 18, bold: true, color: INK, valign: "middle" });
  s.addText("paramètre DISTINCT du top-K : réutiliser le même rendrait toute mesure de sensibilité ambiguë",
    { x: M + 5.2, y: 3.94, w: W - 2 * M - 5.5, h: 1.0, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, color: INK_SOFT, align: "right", valign: "middle" });

  card(s, M, 5.12, W - 2 * M, 1.26, INK, INK);
  s.addText("Les trois blocs sont CALCULÉS, jamais rédigés par le modèle", { x: M + 0.34, y: 5.24,
    w: W - 2 * M - 0.68, h: 0.36, isTextBox: true, margin: 0,
    fontFace: HEAD, fontSize: 17, bold: true, color: AMBER, valign: "middle" });
  s.addText(
    "Un texte réécrit par un modèle dérive et invente. Conséquence : le bloc ne coûte AUCUNE " +
    "inférence. Et un bloc vide est ABSENT, pas titré à vide — un titre sans contenu invite le " +
    "modèle à le combler.",
    { x: M + 0.34, y: 5.62, w: W - 2 * M - 0.68, h: 0.66, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12.5, color: MUTED_DARK, lineSpacingMultiple: 1.16, valign: "top" });

  source(s, "llm/noyau.py · memoire__episodiques_avec_noyau 3 · journal des trajets par agent, persisté");
}

// ── 20 · BILAN ──────────────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: INK };
  s.addText("CE QUE CELA A COÛTÉ", { x: M, y: 0.7, w: W - 2 * M, h: 0.34, isTextBox: true, margin: 0,
    fontFace: BODY, fontSize: 11, bold: true, color: AMBER, charSpacing: 3, valign: "middle" });
  s.addText("Zéro appel supplémentaire au modèle", { x: M, y: 1.1, w: W - 2 * M, h: 0.8, isTextBox: true,
    margin: 0, fontFace: HEAD, fontSize: 36, bold: true, color: WHITE, valign: "middle" });

  const bilan = [
    ["5", "lots livrés", "gravité, rappel, concepts, mémoire noyau, et les constantes qui les tiennent"],
    ["6", "défauts trouvés", "dans la spécification cible, tous AVANT d'écrire la ligne de code correspondante"],
    ["0", "inférence de plus", "les quatre opérations tiennent dans l'appel de consolidation qui a déjà lieu"],
  ];
  const wb = (W - 2 * M - 0.56) / 3;
  bilan.forEach(([n, lab, desc], i) => {
    const x = M + i * (wb + 0.28);
    card(s, x, 2.3, wb, 2.0, INK_SOFT, VIOLET);
    s.addText(n, { x: x + 0.24, y: 2.42, w: wb - 0.48, h: 0.76, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: 44, bold: true, color: AMBER, valign: "middle" });
    s.addText(lab, { x: x + 0.24, y: 3.18, w: wb - 0.48, h: 0.34, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: 15, bold: true, color: WHITE, valign: "middle" });
    s.addText(desc, { x: x + 0.24, y: 3.54, w: wb - 0.48, h: 0.66, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 11.5, color: MUTED_DARK, lineSpacingMultiple: 1.14, valign: "top" });
  });

  s.addText(
    "Chaque lot a eu son contrat de test rédigé AVANT son code. Les six défauts ont été trouvés " +
    "en écrivant ces contrats et en exécutant les tests — pas en relisant la spécification, qui " +
    "les portait sans que personne les voie.",
    { x: M, y: 4.62, w: W - 2 * M, h: 0.74, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 14, color: VIOLET_PALE, lineSpacingMultiple: 1.2, valign: "top" });

  s.addShape(pres.shapes.RECTANGLE, { x: M, y: 5.6, w: 2.2, h: 0.05,
    fill: { color: AMBER }, line: { color: AMBER, width: 0 } });
  s.addText(
    "Ce qui reste ouvert : la règle de conception du retard de référence (lot F5 du ticket 095), " +
    "et le fait que la composante « incident réseau » n'est alimentée par aucun événement GAMA.",
    { x: M, y: 5.8, w: W - 2 * M, h: 0.62, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 12, italic: true, color: MUTED_DARK, lineSpacingMultiple: 1.16, valign: "top" });
  s.addText("docs/arch/memory-stm-ltm.md, partie II · specs/ticket_071/ · scripts/slides/memoire_agents_mobilite.js",
    { x: M, y: 6.6, w: W - 2 * M, h: 0.3, isTextBox: true, margin: 0,
      fontFace: MONO, fontSize: 9.5, color: MUTED, valign: "middle" });
}

pres.writeFile({ fileName: sortie("memoire_agents_mobilite.pptx") })
  .then((f) => console.log("écrit :", f));
