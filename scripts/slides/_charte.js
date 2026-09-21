/**
 * Charte commune aux générateurs de planches — palette, polices, gabarit, aides de tracé.
 *
 * Pourquoi ce fichier existe : deux générateurs qui redéclarent chacun `VIOLET = "6D4E8C"`
 * divergent à la première retouche, et un jeu de planches qui ne ressemble plus à l'autre est
 * le même piège qu'un `.pptx` sans générateur — il se périme en silence. La règle du ticket 071
 * est qu'on modifie le générateur, jamais le `.pptx` ; celle-ci en est la suite : on modifie la
 * charte, jamais la palette d'un deck.
 *
 * ⚠ Toute retouche ici change les DEUX decks. L'épreuve à rejouer après modification est écrite
 * dans `scripts/slides/README.md` : régénérer et diffé le XML des slides.
 *
 * Extrait de `architecture_memoire.js` le 2026-09-21 (ticket 071, volet planches), à valeurs
 * identiques : l'extraction ne devait rien changer au rendu, et ne change rien.
 */

// ── Couleurs ────────────────────────────────────────────────────────────────────
const INK = "2B1B3D", INK_SOFT = "3D2B52";
const VIOLET = "6D4E8C", VIOLET_PALE = "B9A3D0";
const AMBER = "E8A33D", BRICK = "C4453C";
const WHITE = "FFFFFF", TINT = "F3EFF7", TINT_DEEP = "E6DEEF";
const MUTED = "6B6076", MUTED_DARK = "C9BCD6";

// ── Polices ─────────────────────────────────────────────────────────────────────
const HEAD = "Cambria", BODY = "Calibri", MONO = "Courier New";

// ── Gabarit, en pouces : largeur de la planche large et marge latérale ──────────
const W = 13.3, M = 0.6;

/**
 * Les quatre aides de tracé. Elles ont besoin de l'instance `pptxgen` pour lire
 * `pres.shapes`, d'où la fabrique plutôt que quatre exports directs.
 */
function aides(pres) {
  function card(s, x, y, w, h, fill, edge) {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y, w, h, rectRadius: 0.08, fill: { color: fill || TINT },
      line: { color: edge || TINT_DEEP, width: 0.75 },
      shadow: { type: "outer", angle: 90, blur: 8, offset: 0.04, color: INK, opacity: 0.1 },
    });
  }

  function numDot(s, x, y, n, bg, fg, d) {
    const sz = d || 0.42;
    s.addShape(pres.shapes.OVAL, { x, y, w: sz, h: sz, fill: { color: bg }, line: { color: bg, width: 0 } });
    s.addText(String(n), { x, y, w: sz, h: sz, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: sz > 0.45 ? 17 : 15, bold: true, color: fg, align: "center", valign: "middle" });
  }

  function head(s, kick, title, dark) {
    s.addText(kick.toUpperCase(), { x: M, y: 0.16, w: W - 2 * M, h: 0.3, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 11, bold: true, color: dark ? AMBER : VIOLET, charSpacing: 2, valign: "middle" });
    s.addText(title, { x: M, y: 0.5, w: W - 2 * M, h: 0.75, isTextBox: true, margin: 0,
      fontFace: HEAD, fontSize: 34, bold: true, color: dark ? WHITE : INK, valign: "middle" });
  }

  function banner(s, y, txt, fill, color) {
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y, w: W - 2 * M, h: 0.82, rectRadius: 0.06,
      fill: { color: fill }, line: { color: fill, width: 0 } });
    s.addText(txt, { x: M + 0.32, y, w: W - 2 * M - 0.64, h: 0.82, isTextBox: true, margin: 0,
      fontFace: BODY, fontSize: 13, bold: true, color, valign: "middle" });
  }

  return { card, numDot, head, banner };
}

/**
 * Résout le chemin de sortie. Le défaut est `Divers/<nom>`, jamais le répertoire courant :
 * la version précédente écrivait dans le CWD, ce qui déposait un `.pptx` orphelin à la racine
 * du dépôt dès qu'on lançait le générateur depuis ailleurs que `Divers/`.
 */
function sortie(nomParDefaut) {
  const path = require("path");
  if (process.argv[2]) return process.argv[2];
  return path.join(__dirname, "..", "..", "Divers", nomParDefaut);
}

module.exports = {
  INK, INK_SOFT, VIOLET, VIOLET_PALE, AMBER, BRICK,
  WHITE, TINT, TINT_DEEP, MUTED, MUTED_DARK,
  HEAD, BODY, MONO, W, M,
  aides, sortie,
};
