"""What each Ritual altar type gives and what to watch out for - the facts Game Search lists under Ritual Altars
(tools/build_gamedb.py reads TYPES into gamedb.json). (3.0.6: the Ritual Identifier that used this to name an altar you
hovered is gone - it couldn't be automated under GGG policy; the facts stay.)

The dangers follow the game's own danger lines (in our words); Tainted's loot (rare belts, charms, flasks) and Queen's
(10 more omens in the first Favours, a Corrupted Idol from the Queen - 0.5.2 patch notes) from community guides."""

# key: (name, what it gives - "" for nothing extra, danger)
TYPES = {
    "tainted": ("Tainted", "Rare belts, charms, flasks ↑", "Boils explode when touched"),
    "queens": ("Queen's", "+10 omens in first Favours, Corrupted Idol", "Queen in the Mists boss"),
    "smothered": ("Smothered", "", "Plants drop explosive pods"),
    "infested": ("Infested", "", "Rat tornadoes chase you"),
    "sapping": ("Sapping", "", "Slows you, lowers your res"),
    "contaminated": ("Contaminated", "", "Blood waves knock you back"),
    "prowling": ("Prowling", "", "Crimson Wolves"),
    "fractured": ("Fractured", "", "Exploding corpses"),
    "plagued": ("Plagued", "", "Locust swarms"),
    "croaking": ("Croaking", "", "Plague toads"),
}
