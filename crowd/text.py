"""Every user-visible string (design/business-logic.md §9). Wording rules:

* always "usually", never "now" or "currently" (the data are historical);
* level names are relative ("Lighter / Busy / Very busy"), never "seats available";
* the sample is stated; no absolute passenger counts in the commuter view.
"""

LEVEL_WORDS = {0: "No estimate", 1: "Lighter", 2: "Busy", 3: "Very busy"}
LEVEL_GLYPHS = {0: "?", 1: "●", 2: "●●", 3: "●●●"}

SAMPLE_SHARE = "about 2.6%"                      # press-figure ratio of the ticket sample to daily riders (unverified)
NO_CALMER = "No clearly calmer option for this trip."
PARTLY_ESTIMATED = "Partly estimated: some stretches have too little data."
NO_SERVICE = "No scheduled service found for this trip at that time."

WEEKDAY_BASIS = "Compared with what typical riders experience on Delhi buses on weekdays."
WEEKEND_BASIS = "Compared with what typical riders experience on Delhi buses at weekends."
SAMPLE_NOTE = (f"Based on {SAMPLE_SHARE} of riders' tickets (digital tickets only). "
               "Seat availability depends on how many riders our tickets represent; see the technical note.")


def usually(period: str) -> str:
    """The standing caveat, naming the period the tickets come from (never hard-coded to a month)."""
    return f"Usually, based on {period} ticket data — not live."


def basis(day_type: str) -> str:
    return WEEKEND_BASIS if day_type == "weekend" else WEEKDAY_BASIS


def breakdown_note(status: str, value: float | None, gamma_max: float) -> str:
    """Tooltip for the robustness value: how much capture error the recommendation can absorb."""
    if status == "finite":
        return f"Holds unless these routes' ticket coverage differs by more than {value:.1f}×."
    if status == "beyond_max":
        return f"Holds even if these routes' ticket coverage differed by more than {gamma_max:g}×."
    if status == "not_applicable":
        return "Robustness value not defined: both options use the same routes."
    return "The advantage is already within the uncertainty."
