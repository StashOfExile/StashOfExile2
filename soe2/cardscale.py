"""Owner (Price Checks' item card fits the window): one scale for the whole item card - its fonts, rows, boxes and
gaps - worked out from the room the card has (the page's height). Price Checks' full window: WIDE when it fits (a
bit bigger than the Drawer's 1), smaller (down to KMIN) until it does; a smaller window than that gets a scroll bar.
The Drawer: 1, it scrolls. Bulk Pricing's picked item: BULK (about 10% smaller than the Drawer's card), never
smaller. Owner (round 2): text never below MIN_PT - the app's normal small size.

The card is drawn for its scale (app._detail_card_draw reads cv._k); nothing here touches a widget."""

KMIN = 0.9           # the smallest scale; below that the scroll bar shows (owner: 0.75 was unreadable)
STEP = 0.05          # scales go in steps (fewer redraws while a window is resized)
WIDE = 1.1           # Price Checks' full window: its card and listings a bit bigger than the Drawer's
BULK = 0.9           # Bulk Pricing's picked item, against the Drawer's card
MIN_PT = 9           # no text smaller than this (the app's normal small size)


def font_size(size, k):
    """A font size (points) at scale k, rounded, never below MIN_PT (a size already below stays as it is)."""
    return max(min(size, MIN_PT), int(size * k + 0.5))


def snap(k):
    """k down to a step."""
    return round(int(k / STEP + 1e-6) * STEP, 2)


def fit(draw, avail, base=1.0, tries=4):
    """Draw the card at the scale that fits: draw(k) builds it at scale k and returns its height (px). First at
    base; then the step the height says should fit, then a step smaller while it still doesn't, down to the
    smallest. -> (k, height). avail 0 (not laid out yet): base."""
    lo = min(base, KMIN)                 # (rows never shrink past what the text can: MIN_PT)
    k = base
    h = draw(k)
    if avail <= 0 or h <= avail:
        return k, h
    for _ in range(tries):
        if k <= lo:
            break
        nk = max(lo, min(round(k - STEP, 2), snap(k * avail / max(1, h))))
        k = nk
        h = draw(k)
        if h <= avail:
            break
    if h <= avail and k < base and h * (k + STEP) / k <= avail:     # (the guess went a step too far: one up)
        k2 = round(k + STEP, 2)
        h2 = draw(k2)
        if h2 <= avail:
            return k2, h2
        h = draw(k)
    return k, h
