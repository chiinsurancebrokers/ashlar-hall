"""
CHI Insurance Quote Engine — Presentation Themes
=================================================
10 professional themes. Each theme overrides the base C color dict
from config.py so all slides (cover, overview, comparison, analysis,
closing) adopt the selected palette consistently.

Theme dict keys (match config.C):
  primary      → main header/bar         (was navy)
  primary_dark → footer / darkest bg     (was navyDark)
  accent       → highlighted text, tags  (was teal)
  accent2      → star / callout / warm   (was gold)
  bg           → slide background        (was offWhite)
  text_dark    → body text               (was textDark)
  white        → text on dark fills      (always near-white)
  green        → positive indicators     (stay semantic)
  orange       → warnings                (stay semantic)
  red          → negative / critical     (stay semantic)

Extra keys (theme-specific metadata):
  name         → display label
  emoji        → selector emoji
  description  → one-line tagline
  cover_accent → large color block on cover slide
  tag_rec      → background of RECOMMENDED badge
  row_even     → table row even fill
  row_odd      → table row odd fill
"""

from pptx.dml.color import RGBColor


def _rgb(r, g, b) -> RGBColor:
    return RGBColor(r, g, b)


# ─── THEME DEFINITIONS ───────────────────────────────────────────────

THEMES = {

    # 1 ── Ocean Blue (default — current look) ────────────────────────
    "ocean": {
        "name":         "Ocean Blue",
        "emoji":        "🌊",
        "description":  "Κλασικό navy & teal — επαγγελματικό και αξιόπιστο",
        "preview":      ["#1C3F5E", "#00B4D8", "#F59E0B", "#F4F9FF"],
        # Core colors
        "primary":      _rgb(0x1C, 0x3F, 0x5E),
        "primary_dark": _rgb(0x0F, 0x26, 0x38),
        "accent":       _rgb(0x00, 0xB4, 0xD8),
        "accent2":      _rgb(0xF5, 0x9E, 0x0B),
        "bg":           _rgb(0xF4, 0xF9, 0xFF),
        "text_dark":    _rgb(0x1A, 0x2B, 0x3C),
        "white":        _rgb(0xFF, 0xFF, 0xFF),
        "cover_accent": _rgb(0x00, 0xB4, 0xD8),
        "tag_rec":      _rgb(0xF5, 0x9E, 0x0B),
        "row_even":     _rgb(0xE8, 0xF4, 0xFF),
        "row_odd":      _rgb(0xF4, 0xF9, 0xFF),
        # Semantic (unchanged across themes)
        "green":        _rgb(0x27, 0xAE, 0x60),
        "orange":       _rgb(0xE6, 0x7E, 0x22),
        "red":          _rgb(0xE7, 0x4C, 0x3C),
    },

    # 2 ── Midnight Gold ──────────────────────────────────────────────
    "midnight": {
        "name":         "Midnight Gold",
        "emoji":        "✨",
        "description":  "Πολυτελές σκούρο φόντο με χρυσές λεπτομέρειες",
        "preview":      ["#0D1B2A", "#C9A84C", "#F0E6CC", "#F5F1E8"],
        "primary":      _rgb(0x0D, 0x1B, 0x2A),
        "primary_dark": _rgb(0x05, 0x0D, 0x15),
        "accent":       _rgb(0xC9, 0xA8, 0x4C),
        "accent2":      _rgb(0xE8, 0xD5, 0x9A),
        "bg":           _rgb(0xF5, 0xF1, 0xE8),
        "text_dark":    _rgb(0x0D, 0x1B, 0x2A),
        "white":        _rgb(0xFF, 0xFC, 0xF0),
        "cover_accent": _rgb(0xC9, 0xA8, 0x4C),
        "tag_rec":      _rgb(0xC9, 0xA8, 0x4C),
        "row_even":     _rgb(0xFA, 0xF5, 0xE4),
        "row_odd":      _rgb(0xF5, 0xF1, 0xE8),
        "green":        _rgb(0x2E, 0xCC, 0x71),
        "orange":       _rgb(0xE6, 0x7E, 0x22),
        "red":          _rgb(0xE7, 0x4C, 0x3C),
    },

    # 3 ── Forest & Trust ─────────────────────────────────────────────
    "forest": {
        "name":         "Forest & Trust",
        "emoji":        "🌿",
        "description":  "Βαθύ πράσινο — φυσικό, αξιόπιστο, ήρεμο",
        "preview":      ["#1B4332", "#52B788", "#D8F3DC", "#F0FFF4"],
        "primary":      _rgb(0x1B, 0x43, 0x32),
        "primary_dark": _rgb(0x0A, 0x24, 0x1B),
        "accent":       _rgb(0x52, 0xB7, 0x88),
        "accent2":      _rgb(0xD4, 0xA0, 0x17),
        "bg":           _rgb(0xF0, 0xFF, 0xF4),
        "text_dark":    _rgb(0x1B, 0x43, 0x32),
        "white":        _rgb(0xFF, 0xFF, 0xFF),
        "cover_accent": _rgb(0x52, 0xB7, 0x88),
        "tag_rec":      _rgb(0xD4, 0xA0, 0x17),
        "row_even":     _rgb(0xD8, 0xF3, 0xDC),
        "row_odd":      _rgb(0xF0, 0xFF, 0xF4),
        "green":        _rgb(0x52, 0xB7, 0x88),
        "orange":       _rgb(0xE6, 0x7E, 0x22),
        "red":          _rgb(0xE7, 0x4C, 0x3C),
    },

    # 4 ── Bordeaux ───────────────────────────────────────────────────
    "bordeaux": {
        "name":         "Bordeaux",
        "emoji":        "🍷",
        "description":  "Βαθύ μπορντό — κύρος, εμπειρία, αριστοκρατική αισθητική",
        "preview":      ["#6B1A2A", "#C0392B", "#F9E4E7", "#FFF5F6"],
        "primary":      _rgb(0x6B, 0x1A, 0x2A),
        "primary_dark": _rgb(0x3D, 0x08, 0x12),
        "accent":       _rgb(0xC0, 0x39, 0x2B),
        "accent2":      _rgb(0xE8, 0xC0, 0x7D),
        "bg":           _rgb(0xFF, 0xF5, 0xF6),
        "text_dark":    _rgb(0x3D, 0x08, 0x12),
        "white":        _rgb(0xFF, 0xFF, 0xFF),
        "cover_accent": _rgb(0xC0, 0x39, 0x2B),
        "tag_rec":      _rgb(0xBD, 0x93, 0x00),
        "row_even":     _rgb(0xF9, 0xE4, 0xE7),
        "row_odd":      _rgb(0xFF, 0xF5, 0xF6),
        "green":        _rgb(0x27, 0xAE, 0x60),
        "orange":       _rgb(0xE6, 0x7E, 0x22),
        "red":          _rgb(0xC0, 0x39, 0x2B),
    },

    # 5 ── Charcoal Pro ───────────────────────────────────────────────
    "charcoal": {
        "name":         "Charcoal Pro",
        "emoji":        "🖤",
        "description":  "Ουδέτερο ανθρακί — minimal, σύγχρονο, εταιρικό",
        "preview":      ["#2D3436", "#636E72", "#00CEC9", "#F8F9FA"],
        "primary":      _rgb(0x2D, 0x34, 0x36),
        "primary_dark": _rgb(0x12, 0x16, 0x17),
        "accent":       _rgb(0x00, 0xCE, 0xC9),
        "accent2":      _rgb(0xFD, 0xCB, 0x6E),
        "bg":           _rgb(0xF8, 0xF9, 0xFA),
        "text_dark":    _rgb(0x2D, 0x34, 0x36),
        "white":        _rgb(0xFF, 0xFF, 0xFF),
        "cover_accent": _rgb(0x00, 0xCE, 0xC9),
        "tag_rec":      _rgb(0xFD, 0xCB, 0x6E),
        "row_even":     _rgb(0xEE, 0xF0, 0xF1),
        "row_odd":      _rgb(0xF8, 0xF9, 0xFA),
        "green":        _rgb(0x00, 0xB8, 0x94),
        "orange":       _rgb(0xE6, 0x7E, 0x22),
        "red":          _rgb(0xD6, 0x3B, 0x31),
    },

    # 6 ── Royal Purple ───────────────────────────────────────────────
    "royal": {
        "name":         "Royal Purple",
        "emoji":        "👑",
        "description":  "Βαθύ μοβ με χρυσό — premium αίσθηση, διαφορετικό",
        "preview":      ["#2E1760", "#7C3AED", "#F5C542", "#F8F5FF"],
        "primary":      _rgb(0x2E, 0x17, 0x60),
        "primary_dark": _rgb(0x16, 0x09, 0x33),
        "accent":       _rgb(0x7C, 0x3A, 0xED),
        "accent2":      _rgb(0xF5, 0xC5, 0x42),
        "bg":           _rgb(0xF8, 0xF5, 0xFF),
        "text_dark":    _rgb(0x1E, 0x0D, 0x45),
        "white":        _rgb(0xFF, 0xFF, 0xFF),
        "cover_accent": _rgb(0x7C, 0x3A, 0xED),
        "tag_rec":      _rgb(0xF5, 0xC5, 0x42),
        "row_even":     _rgb(0xED, 0xE7, 0xFF),
        "row_odd":      _rgb(0xF8, 0xF5, 0xFF),
        "green":        _rgb(0x27, 0xAE, 0x60),
        "orange":       _rgb(0xE6, 0x7E, 0x22),
        "red":          _rgb(0xE7, 0x4C, 0x3C),
    },

    # 7 ── Terracotta ─────────────────────────────────────────────────
    "terracotta": {
        "name":         "Terracotta",
        "emoji":        "🏺",
        "description":  "Ζεστά χρώματα — προσιτό, ανθρώπινο, Μεσογειακό",
        "preview":      ["#7C2D12", "#EA580C", "#FED7AA", "#FFFAF5"],
        "primary":      _rgb(0x7C, 0x2D, 0x12),
        "primary_dark": _rgb(0x43, 0x14, 0x07),
        "accent":       _rgb(0xEA, 0x58, 0x0C),
        "accent2":      _rgb(0xCA, 0x8A, 0x04),
        "bg":           _rgb(0xFF, 0xFA, 0xF5),
        "text_dark":    _rgb(0x43, 0x14, 0x07),
        "white":        _rgb(0xFF, 0xFE, 0xFC),
        "cover_accent": _rgb(0xEA, 0x58, 0x0C),
        "tag_rec":      _rgb(0xCA, 0x8A, 0x04),
        "row_even":     _rgb(0xFE, 0xD7, 0xAA),
        "row_odd":      _rgb(0xFF, 0xFA, 0xF5),
        "green":        _rgb(0x16, 0xA3, 0x4A),
        "orange":       _rgb(0xEA, 0x58, 0x0C),
        "red":          _rgb(0xDC, 0x26, 0x26),
    },

    # 8 ── Arctic ─────────────────────────────────────────────────────
    "arctic": {
        "name":         "Arctic",
        "emoji":        "❄️",
        "description":  "Καθαρό λευκό & παγωμένο μπλε — minimal και φρέσκο",
        "preview":      ["#0C4A6E", "#0EA5E9", "#E0F2FE", "#FFFFFF"],
        "primary":      _rgb(0x0C, 0x4A, 0x6E),
        "primary_dark": _rgb(0x07, 0x2D, 0x44),
        "accent":       _rgb(0x0E, 0xA5, 0xE9),
        "accent2":      _rgb(0xF5, 0x9E, 0x0B),
        "bg":           _rgb(0xFF, 0xFF, 0xFF),
        "text_dark":    _rgb(0x0C, 0x4A, 0x6E),
        "white":        _rgb(0xFF, 0xFF, 0xFF),
        "cover_accent": _rgb(0x0E, 0xA5, 0xE9),
        "tag_rec":      _rgb(0xF5, 0x9E, 0x0B),
        "row_even":     _rgb(0xE0, 0xF2, 0xFE),
        "row_odd":      _rgb(0xF0, 0xF9, 0xFF),
        "green":        _rgb(0x05, 0x96, 0x69),
        "orange":       _rgb(0xD9, 0x77, 0x06),
        "red":          _rgb(0xDC, 0x26, 0x26),
    },

    # 9 ── Slate & Copper ─────────────────────────────────────────────
    "slate": {
        "name":         "Slate & Copper",
        "emoji":        "🔷",
        "description":  "Σκούρο slate με χάλκινο accent — industrial chic",
        "preview":      ["#1E293B", "#B45309", "#FCD34D", "#F8FAFC"],
        "primary":      _rgb(0x1E, 0x29, 0x3B),
        "primary_dark": _rgb(0x0F, 0x17, 0x24),
        "accent":       _rgb(0xB4, 0x53, 0x09),
        "accent2":      _rgb(0xFC, 0xD3, 0x4D),
        "bg":           _rgb(0xF8, 0xFA, 0xFC),
        "text_dark":    _rgb(0x1E, 0x29, 0x3B),
        "white":        _rgb(0xFF, 0xFF, 0xFF),
        "cover_accent": _rgb(0xB4, 0x53, 0x09),
        "tag_rec":      _rgb(0xFC, 0xD3, 0x4D),
        "row_even":     _rgb(0xE2, 0xE8, 0xF0),
        "row_odd":      _rgb(0xF8, 0xFA, 0xFC),
        "green":        _rgb(0x16, 0xA3, 0x4A),
        "orange":       _rgb(0xB4, 0x53, 0x09),
        "red":          _rgb(0xDC, 0x26, 0x26),
    },

    # 10 ── Aegean ────────────────────────────────────────────────────
    "aegean": {
        "name":         "Aegean",
        "emoji":        "🏛️",
        "description":  "Ελληνικό μπλε & λευκό — ταυτότητα, ζεστασιά, τοπική αίσθηση",
        "preview":      ["#003087", "#0057B7", "#FFD700", "#F0F5FF"],
        "primary":      _rgb(0x00, 0x30, 0x87),
        "primary_dark": _rgb(0x00, 0x18, 0x4D),
        "accent":       _rgb(0x00, 0x57, 0xB7),
        "accent2":      _rgb(0xFF, 0xD7, 0x00),
        "bg":           _rgb(0xF0, 0xF5, 0xFF),
        "text_dark":    _rgb(0x00, 0x18, 0x4D),
        "white":        _rgb(0xFF, 0xFF, 0xFF),
        "cover_accent": _rgb(0x00, 0x57, 0xB7),
        "tag_rec":      _rgb(0xFF, 0xD7, 0x00),
        "row_even":     _rgb(0xD6, 0xE4, 0xFF),
        "row_odd":      _rgb(0xF0, 0xF5, 0xFF),
        "green":        _rgb(0x27, 0xAE, 0x60),
        "orange":       _rgb(0xE6, 0x7E, 0x22),
        "red":          _rgb(0xE7, 0x4C, 0x3C),
    },
}


# ─── ACCESSORS ───────────────────────────────────────────────────────

def get_theme(theme_key: str) -> dict:
    """Return theme dict by key. Defaults to 'ocean'."""
    return THEMES.get(theme_key, THEMES["ocean"])


def get_theme_colors(theme_key: str) -> dict:
    """
    Return a color dict compatible with config.C.
    Maps theme keys → C keys so pptx_builder can swap them in.
    """
    t = get_theme(theme_key)
    return {
        "navy":      t["primary"],
        "navyDark":  t["primary_dark"],
        "teal":      t["accent"],
        "gold":      t["accent2"],
        "offWhite":  t["bg"],
        "textDark":  t["text_dark"],
        "white":     t["white"],
        "green":     t["green"],
        "orange":    t["orange"],
        "red":       t["red"],
        # Pass through theme extras for special use in builder
        "_cover_accent": t.get("cover_accent", t["accent"]),
        "_tag_rec":      t.get("tag_rec", t["accent2"]),
        "_row_even":     t.get("row_even",  _rgb(0xE8, 0xF4, 0xFF)),
        "_row_odd":      t.get("row_odd",   _rgb(0xF4, 0xF9, 0xFF)),
        # Keep semantic colors from base config
        "generali":  _rgb(0xCC, 0x00, 0x00),
        "now":       _rgb(0x7B, 0x2D, 0x8B),
        "blue":      _rgb(0x3B, 0x82, 0xF6),
        "axa":       _rgb(0x00, 0x00, 0x8B),
        "allianz":   _rgb(0x00, 0x67, 0xB1),
        "cigna":     _rgb(0x00, 0x61, 0xA0),
        "ethniki":   _rgb(0x00, 0x5B, 0xAA),
        "interlife": _rgb(0xE8, 0x00, 0x00),
        "eurolife":  _rgb(0x00, 0x40, 0x80),
        "groupama":  _rgb(0x00, 0x82, 0x40),
    }


def list_themes() -> list[tuple[str, dict]]:
    """Return list of (key, theme_dict) sorted by display order."""
    order = ["ocean","midnight","forest","bordeaux","charcoal",
             "royal","terracotta","arctic","slate","aegean"]
    return [(k, THEMES[k]) for k in order if k in THEMES]
