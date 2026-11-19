"""2.102.0 Stash scan (beta) - where each stack sits in the fixed-slot stash tabs.

Coordinates are pixels of the stash panel's inside at a 1440-pixel-high game (PANEL x PANEL, top-left = the panel's
corner); every other size scales them by game height / 1440. A slot is (x, y, w, h) of its dark inside (70 x 70).
No pictures of anyone's stash ship with the app: only these numbers and the digit shapes (stashread.GLYPHS).

To add a tab:
  1. A screenshot of the tab's inside at 1440p, cropped to the panel (like the four already done), with every slot
     filled if possible (an empty slot still works: it reads 0).
  2. Each slot's item name (Ctrl+C), left to right, top to bottom - and which slots are wildcards (any item: skip).
  3. Run tools/stash_slots.py on the screenshot: it prints the slot boxes; paste them below in reading order.
  4. Add the tab to TABS and ORDER. Sub-pages (Breach: Catalysts | Wombgifts) are their own entry; say in "page"
     which button must be lit.
3.0.6: the Socketables tab's five pages are in (each one its own entry, like Breach's)."""

from .names import SOCKETABLES_PAGES

PANEL = 847            # the panel's inside at 1440p (it's square)
S = 70                 # a normal slot's inside


def _row(y, xs, names):
    return [(n, (x, y, S, S)) for x, n in zip(xs, names) if n]


_T = ("Orb of Transmutation", "Orb of Augmentation", "Regal Orb", "Exalted Orb", "Chaos Orb")


def _tiers(base):
    return [base, "Greater " + base, "Perfect " + base]


CURRENCY = []
for _i, _b in enumerate(_T):
    CURRENCY += _row(38 + 90 * _i, (29, 110, 191), _tiers(_b))
CURRENCY += _row(38, (299, 389, 479), ("Orb of Alchemy", "Vaal Orb", "Orb of Annulment"))
CURRENCY += _row(128, (299, 389, 479), ("Orb of Chance", "Fracturing Orb", "Divine Orb"))
CURRENCY += _row(218, (344, 434), ("Mirror of Kalandra", "Hinekora's Lock"))
CURRENCY += _row(38, (584, 664, 749), ("Lesser Jeweller's Orb", "Greater Jeweller's Orb", "Perfect Jeweller's Orb"))
CURRENCY += _row(128, (749,), ("Artificer's Orb",))
CURRENCY += _row(245, (569, 659, 749), ("Arcanist's Etcher", "Armourer's Scrap", "Blacksmith's Whetstone"))
CURRENCY += _row(335, (659, 749), ("Glassblower's Bauble", "Gemcutter's Prism"))
CURRENCY += _row(452, (749,), ("Scroll of Wisdom",))
# 3.0.6 (owner's scan: the shard row was missed - all four are on the Currency Exchange). Not read: the crafting
# hole (370, 321)
CURRENCY += _row(571, (255, 345, 435, 525), ("Transmutation Shard", "Regal Shard", "Chance Shard", "Artificer's Shard"))
# 2.114.3: the 2 x 7 wildcard slots - anything can go there; stashread tells what by its picture
CURRENCY_WILD = [(x, y, S, S) for y in (668, 749) for x in (146, 227, 308, 389, 470, 551, 632)]

ABYSS = []
ABYSS += _row(82, (391,), ("Kulemak's Invitation",))
ABYSS += _row(213, (391,), ("Preserved Cranium",))
ABYSS += _row(301, (303, 391, 479), ("Gnawed Jawbone", "Preserved Jawbone", "Ancient Jawbone"))
ABYSS += _row(389, (259, 347, 435, 523), ("Gnawed Collarbone", "Preserved Collarbone", "Ancient Collarbone",
                                          "Altered Collarbone"))
ABYSS += _row(477, (303, 391, 479), ("Gnawed Rib", "Preserved Rib", "Ancient Rib"))
ABYSS += _row(566, (391,), ("Preserved Vertebrae",))
ABYSS += _row(697, (83, 171, 259, 347, 436, 524, 612, 700),
              ("Omen of Abyssal Echoes", "Omen of the Sovereign", "Omen of the Liege", "Omen of the Blackblooded",
               "Omen of Putrefaction", "Omen of Light", "Omen of Sinistral Necromancy", "Omen of Dextral Necromancy"))


def _liq(prefix, names):
    return [(prefix + n).strip() for n in names]


_L3 = ("Diluted Liquid Ire", "Diluted Liquid Guilt", "Diluted Liquid Greed")
_R3 = ("Liquid Disgust", "Liquid Despair", "Concentrated Liquid Fear")
_L2 = ("Liquid Paranoia", "Liquid Envy")
_R2 = ("Concentrated Liquid Suffering", "Concentrated Liquid Isolation")
DELIRIUM = []
DELIRIUM += _row(79, (339, 447), ("Simulacrum Splinter", "Simulacrum"))
DELIRIUM += _row(170, (391,), ("Raven's Reflection",))
for _y, _p in ((268, ""), (470, "Ancient ")):
    DELIRIUM += _row(_y, (94, 184, 274, 508, 598, 688), _liq(_p, _L3 + _R3))
    DELIRIUM += _row(_y + 90, (139, 229, 553, 643), _liq(_p, _L2 + _R2))
DELIRIUM += _row(678, (112, 205, 298, 481, 574, 667),
                 ("Potent Liquid Melancholy", "Potent Liquid Ferocity", "Potent Liquid Contempt",
                  "Ancient Potent Liquid Melancholy", "Ancient Potent Liquid Ferocity",
                  "Ancient Potent Liquid Contempt"))
# not read: the 3 wildcard slots down the middle (x 391)

_CAT = ("Flesh", "Neural", "Adaptive", "Uul-Netol's", "Xoph's", "Tul's", "Esh's", "Chayula's", "Carapace", "Reaver",
        "Sibilant", "Skittering", "Necrotic")
BREACH = []
BREACH += _row(140, (348, 438), ("Breach Splinter", "Breachstone"))
BREACH += [("Breachlord Sac", (358, 231, 136, 136))]     # (2.114.2: the game's name - was "Breachlord's Sac")
for _y, _p in ((416, ""), (623, "Refined ")):
    BREACH += _row(_y, (168, 258, 348, 438, 528, 618), [f"{_p}{c} Catalyst" for c in _CAT[:6]])
    BREACH += _row(_y + 90, (123, 213, 303, 393, 483, 573, 663), [f"{_p}{c} Catalyst" for c in _CAT[6:]])
# Wombgifts page: not read (user's call)

# 2.114.2 (the user's Expedition tab, every slot named): Aldur's Saga's slot (74, 255) is left out - it's out of
# the game for now. The two big slots: Shattered Triskelion and The Triskelion Reforged.
_ALLOY = ("Runic", "Adaptive", "Protective", "Expansive", "Swift", "Cyclonic", "Prismatic", "Mystic", "Sovereign",
          "Celestial", "Transcendent")
EXPEDITION = []
EXPEDITION += _row(74, (165, 345, 435, 525, 615),
                   ("Expedition Logbook", "Medved's Saga", "Vorana's Saga", "Uhtred's Saga", "Olroth's Saga"))
EXPEDITION += [("Shattered Triskelion", (274, 202, 140, 140)), ("The Triskelion Reforged", (435, 202, 140, 140))]
EXPEDITION += _row(371, (255, 345, 525), ("Verisium", "Exceptional Verisium", "Liquid Verisium"))
EXPEDITION += _row(461, (255, 345, 435, 525), ("Medved's Crest of the Circle", "Vorana's Crest of the Scythe",
                                               "Uhtred's Crest of the Chalice", "Olroth's Crest of the Sun"))
EXPEDITION += _row(560, (120, 210, 300, 390, 480, 570, 660), [a + " Alloy" for a in _ALLOY[:7]])
EXPEDITION += _row(650, (165, 255, 345, 435, 525, 615), [a + " Alloy" for a in _ALLOY[7:]]
                   + ["The Runebinder's Alloy", "The Runefather's Alloy"])
EXPEDITION += _row(749, (255, 345, 435, 525), ("Blazing Flux", "Chilling Flux", "Crackling Flux", "Void Flux"))

# 2.114.2 (the user's Ritual tab, every slot named): the two empty slots (250, 173) and (165, 372) held items that
# are out of the game - left out. Head of the King's slot is double wide.
_O = "Omen of "
RITUAL = []
RITUAL += [("An Audience with the King", (251, 40, 70, 70)), ("Head of the King", (350, 40, 140, 70)),
           ("Call of the Shadows", (520, 40, 70, 70))]
RITUAL += _row(174, (445, 526), (_O + "Gambling", _O + "Bartering"))
RITUAL += _row(291, (125, 206, 287, 404, 485, 566),
               [_O + n for n in ("Sinistral Exaltation", "Dextral Exaltation", "Greater Exaltation",
                                 "Sinistral Erasure", "Dextral Erasure", "Whittling")])
RITUAL += _row(372, (246, 404, 485, 566, 647),
               [_O + n for n in ("Catalysing Exaltation", "Chaotic Rarity", "Chaotic Quantity", "Chaotic Monsters",
                                 "Chaotic Effectiveness")])
RITUAL += _row(489, (147, 228, 345, 426, 543, 624),
               [_O + n for n in ("Sinistral Annulment", "Dextral Annulment", "Chance", "the Ancients", "the Blessed",
                                 "Sanctification")])
RITUAL += _row(606, (147, 228), (_O + "Dextral Crystallisation", _O + "Sinistral Crystallisation"))
RITUAL += _row(741, (125, 206, 287, 404, 485, 566, 647),
               [_O + n for n in ("Resurgence", "Amelioration", "Refreshment", "the Hunt", "Answered Prayers",
                                 "Secret Compartments", "Reinforcements")])

# 2.114.2 (the user's Essence tab, every slot named): smaller slots (63 x 63); each line is Lesser, normal, Greater,
# Perfect. The big slot and the four small ones in the middle aren't read (nothing named there).
E = 63
_ESS_L = ("the Body", "the Mind", "Enhancement", "Flames", "Insulation", "Ice", "Thawing", "Electricity", "Grounding",
          "Ruin")
_ESS_R = ("Command", "Abrasion", "Sorcery", "Haste", "Alacrity", "Seeking", "Battle", "the Infinite", "Opulence")
_ESS_MID = (("Essence of Hysteria", "Essence of Horror"), ("Essence of Delirium", "Essence of Insanity"),
            ("Essence of the Abyss", "Essence of the Breach"))


def _ess(n):
    return [f"{t}Essence of {n}" for t in ("Lesser ", "", "Greater ", "Perfect ")]


ESSENCE = []
for _i, _y in enumerate((26, 107, 188, 269, 350, 431, 512, 593, 674, 755)):
    ESSENCE += [(n, (x, _y, E, E)) for x, n in zip((43, 115, 187, 264), _ess(_ESS_L[_i]))]
    if _i >= 7:
        ESSENCE += [(n, (x, _y + 1, E - 1, E - 1)) for x, n in zip((358, 430), _ESS_MID[_i - 7])]
    if _i < len(_ESS_R):
        ESSENCE += [(n, (x, _y, E, E)) for x, n in zip((524, 596, 668, 744), _ess(_ESS_R[_i]))]

# 2.114.2 (the user's Fragments tab › Fragments page, every slot named). Many of these also have a slot in their
# own tab (Breach, Delirium, Abyss, Expedition, Ritual): a scan adds up what each tab holds.
FRAGMENTS = []
FRAGMENTS += _row(148, (306, 387, 468), ("Ancient Crisis Fragment", "Weathered Crisis Fragment", "Faded Crisis Fragment"))
FRAGMENTS += _row(265, (91, 181, 387), ("Breach Splinter", "Breachstone", "Origin Spark"))
FRAGMENTS += [("Shattered Triskelion", (602, 193, 140, 140)), ("Breachlord Sac", (101, 355, 140, 140)),
              ("Origin Cradle", (351, 356, 140, 140)), ("The Triskelion Reforged", (602, 355, 140, 140))]
FRAGMENTS += [("An Audience with the King", (54, 560, 70, 70)), ("Head of the King", (144, 560, 140, 70))]
FRAGMENTS += _row(560, (305, 422, 512, 602, 719), ("Call of the Shadows", "Simulacrum Splinter", "Simulacrum",
                                                  "Raven's Reflection", "Kulemak's Invitation"))
FRAGMENTS += _row(695, (306, 387, 468), ("Deadly Fate", "Cowardly Fate", "Victorious Fate"))

# 3.0.6 the Socketables tab: five pages, one per button along the tab's top (left to right). Every slot named by
# its picture matched with the item art (poe.ninja's, and the Currency Exchange's icons), an empty slot's faint
# picture too, and checked by eye; each item once. The same 70 x 70 slots as the other tabs.
_RUNE_BASES = (("Desert", "Glacial", "Storm"), ("Iron", "Body", "Mind"), ("Rebirth", "Inspiration", "Stone"),
               ("Robust", "Adept", "Resolve"), ("Vision", "Ward", "Charging"))
SOCK_RUNES = []                 # each block of three: Lesser, normal, Greater
for _y, _bases in zip((103, 193, 283, 373, 463), _RUNE_BASES):
    SOCK_RUNES += _row(_y, (30, 111, 192, 309, 390, 471, 588, 669, 750),
                       [f"{t}{b} Rune" for b in _bases for t in ("Lesser ", "", "Greater ")])
SOCK_RUNES += _row(571, (30, 120, 210, 300, 570, 660, 750),
                   ("Greater Rune of Leadership", "Greater Rune of Tithing", "Greater Rune of Alacrity",
                    "Greater Rune of Nobility", "Farrul's Rune of the Hunt", "Thane Myrk's Rune of Summer",
                    "Lady Hestra's Rune of Winter"))
_X9 = tuple(30 + 90 * _i for _i in range(9))
SOCK_RUNES += _row(661, _X9, ("Thane Leld's Rune of Spring", "Fenumus' Rune of Agony", "Thane Girt's Rune of Wildness",
                              "Hedgewitch Assandra's Rune of Wisdom", "Saqawal's Rune of the Sky",
                              "The Greatwolf's Rune of Willpower", "Craiceann's Rune of Recovery",
                              "Craiceann's Rune of Warding", "Countess Seske's Rune of Archery"))
SOCK_RUNES += _row(751, _X9, ("Saqawal's Rune of Erosion", "Saqawal's Rune of Memory", "The Greatwolf's Rune of Claws",
                              "Courtesan Mannan's Rune of Cruelty", "Thane Grannell's Rune of Mastery",
                              "Fenumus' Rune of Spinning", "Fenumus' Rune of Draining", "Farrul's Rune of Grace",
                              "Farrul's Rune of the Chase"))

_WR = "Warding Rune of "
_AR = "Ancient Rune of "
SOCK_MORE = []
SOCK_MORE += _row(103, (165, 255, 345, 435, 525, 615),
                  [_WR + n for n in ("Reinforcement", "Protection", "Disintegration", "Desperation", "Courage",
                                     "Nourishment")])
SOCK_MORE += _row(193, (165, 255, 345, 435, 525, 615),
                  [_WR + n for n in ("Symbiosis", "Stability", "Glancing", "Heart", "Annihilation", "Salvaging")])
SOCK_MORE += _row(283, (210, 300, 390, 480, 570),
                  [_WR + n for n in ("Armature", "Obsession", "Equinox", "Bodyguards", "Hollowing")])
SOCK_MORE += _row(382, _X9, [_AR + n for n in ("Splinters", "Dueling", "the Titan", "Shattering", "Prowess", "Control",
                                               "Discovery", "Decay", "Witchcraft")])
SOCK_MORE += _row(472, (30, 120, 210, 300, 480, 570, 660, 750),
                  [_AR + n for n in ("the Horde", "Animosity", "Detonation", "Retaliation")]
                  + ["Rune of " + n for n in ("Vitality", "the Hunt", "Acrobatics", "Culmination")])
SOCK_MORE += _row(562, _X9, ["Rune of " + n for n in ("Renown", "Accumulation", "Foundations", "the Prism",
                                                     "the Blossom", "Consistency", "Reach", "Vital Flame",
                                                     "Confrontation")])
SOCK_MORE += _row(661, _X9[1:8], ("Passion of Aldur", "Breath of Aldur", "Ire of Aldur", "Betrayal of Aldur",
                                  "Serle's Triumph", "Cadigan's Epiphany", "Astrid's Creativity"))
SOCK_MORE += _row(751, _X9[:7] + (750,), ("Uhtred's Sidereus", "Kolr's Hunt", "Vorana's Carnage", "Thrud's Might",
                                          "Medved's Tending", "Katla's Gloom", "Masterwork Rune", "Aldur's Legacy"))

_X8 = tuple(75 + 90 * _i for _i in range(8))          # rows of 8, and of 7 between them
_X7 = tuple(120 + 90 * _i for _i in range(7))
_SC = "Soul Core of "
SOCK_CORES = []
SOCK_CORES += _row(117, _X8, [_SC + n for n in ("Topotante", "Tacati", "Opiloti", "Jiquani", "Zalatl", "Citaqualotl",
                                                "Puhuarte", "Tzamoto")])
SOCK_CORES += _row(207, _X7, [_SC + n for n in ("Xopec", "Quipolatl", "Ticaba", "Atmohua", "Cholotl", "Zantipi",
                                                "Azcapa")])
SOCK_CORES += _row(324, _X8, ("Atmohua's Soul Core of Retreat", "Hayoxi's Soul Core of Heatproofing",
                              "Zalatl's Soul Core of Insulation", "Topotante's Soul Core of Dampening",
                              "Cholotl's Soul Core of War", "Quipolatl's Soul Core of Flow",
                              "Tzamoto's Soul Core of Ferocity", "Uromoti's Soul Core of Attenuation"))
SOCK_CORES += _row(414, _X7, ("Opiloti's Soul Core of Assault", "Guatelitzi's Soul Core of Endurance",
                              "Xopec's Soul Core of Power", "Estazunti's Soul Core of Convalescence",
                              "Tacati's Soul Core of Affliction", "Xipocado's Soul Core of Dominion",
                              "Citaqualotl's Soul Core of Foulness"))
_JQ = "Jiquani's Soul Core of "
SOCK_CORES += _row(531, _X7, [_JQ + n for n in ("Automation", "Malediction", "Targeting", "Rallying", "Radiance",
                                                "Severing", "Rippling")])
SOCK_CORES += _row(621, _X8[1:7], [_JQ + n for n in ("Quaking", "Munitions", "Snares", "Abundance", "Squalls",
                                                     "Thundering")])
SOCK_CORES += _row(738, _X8[2:6], ["Atziri's Soul Core of " + n for n in ("Devotion", "Vitality", "Alacrity",
                                                                          "Inoculation")])

SOCK_IDOLS = []
SOCK_IDOLS += _row(135, _X8, [n + " Idol" for n in ("Snake", "Primate", "Owl", "Cat", "Wolf", "Boar", "Bear", "Ox")])
SOCK_IDOLS += _row(243, _X8[1:7], [n + " Idol" for n in ("Stag", "Rabbit", "Fox", "Panther", "Stoat", "Hawk")])
SOCK_IDOLS += _row(396, _X7, ["Idol of " + n for n in ("Sirrius", "Thruldana", "Grold", "Eeshta", "Egrin", "Maxarius",
                                                       "Ralakesh")])
SOCK_IDOLS += _row(549, _X7, ["Idol of " + n for n in ("Greust", "Yeena", "Eramir", "Oak", "Alira", "Kraityn",
                                                       "Silk")])
SOCK_IDOLS += _row(702, _X7[2:5], ("Idol of the Sycophant", "Idol of the Martyr", "Idol of the Pharisee"))

_X4 = (255, 345, 435, 525)
SOCK_OTHERS = []
SOCK_OTHERS += _row(121, _X4, ("Amanamu's Gaze", "Tecrod's Gaze", "Kurgal's Gaze", "Ulaman's Gaze"))
SOCK_OTHERS += _row(274, _X4, ("Guatelitzi's Thesis", "Citaqualotl's Thesis", "Jiquani's Thesis", "Quipolatl's Thesis"))
SOCK_OTHERS += _row(427, (390,), ("Raven-Touched Shard",))
SOCK_OTHERS += _row(580, _X4, ("Emergent Vigour", "Emergent Possibility", "Emergent Protection", "Emergent Instinct"))
SOCK_OTHERS += _row(733, _X4, ("Carved Cunning", "Carved Majesty", "Carved Mischief", "Carved Tenacity"))

# the five page buttons along the top (the same on every page): drawn with the slots when the panel is matched, so a
# page with few slots (Ancient Augments: 17) isn't taken for the Essence tab's dense grid. Not read.
SOCK_BUTTONS = [(227 + 83 * _i, 11, 66, 69) for _i in range(5)]
SOCKETABLES = ("socketables_runes", "socketables_more", "socketables_cores", "socketables_idols", "socketables_others")

TABS = {
    "currency": {"label": "Currency", "slots": CURRENCY, "wild": CURRENCY_WILD},
    "abyss": {"label": "Abyss", "slots": ABYSS},
    "delirium": {"label": "Delirium", "slots": DELIRIUM},
    "breach": {"label": "Breach", "page": "Catalysts", "slots": BREACH},
    "expedition": {"label": "Expedition", "slots": EXPEDITION},
    "ritual": {"label": "Ritual", "slots": RITUAL},
    "essence": {"label": "Essence", "slots": ESSENCE},
    "fragments": {"label": "Fragments", "page": "Fragments", "slots": FRAGMENTS},
}
for _i, (_key, _slots) in enumerate(zip(SOCKETABLES, (SOCK_RUNES, SOCK_MORE, SOCK_CORES, SOCK_IDOLS, SOCK_OTHERS))):
    TABS[_key] = {"label": "Socketables", "page": SOCKETABLES_PAGES[_i], "button": (_i + 1, len(SOCKETABLES)),
                  "slots": _slots, "marks": SOCK_BUTTONS}
ORDER = ("currency", "abyss", "delirium", "breach", "expedition", "ritual", "essence", "fragments") + SOCKETABLES


def tab_title(tab):
    """3.0.6: a tab's name in the scan's notes and check list - "Socketables › Idols" for a page of a tab with many
    (one label, five pages), else the tab's label."""
    t = TABS[tab]
    return f"{t['label']} › {t['page']}" if t.get("button") else t["label"]
