"""Every user-visible string (design/business-logic.md §9). Wording rules:

* always "usually", never "now" or "currently" (the data are historical);
* level names are relative ("Lighter / Busy / Very busy"), never "seats available";
* the sample is stated; no absolute passenger counts in the commuter view.
"""

LEVEL_WORDS = {0: "No estimate", 1: "Lighter", 2: "Busy", 3: "Very busy"}
LEVEL_GLYPHS = {0: "?", 1: "●", 2: "●●", 3: "●●●"}

USUALLY = "Usually, based on October ticket data — not live."
NO_CALMER = "No clearly calmer option for this trip."
PARTLY_ESTIMATED = "Partly estimated: some stretches have too little data."
NO_SERVICE = "No scheduled service found for this trip at that time."

WEEKDAY_BASIS = "Compared with what typical riders experience on Delhi buses on weekdays."
WEEKEND_BASIS = "Compared with what typical riders experience on Delhi buses at weekends."
SAMPLE_NOTE = ("Based on about 2.6% of riders' tickets (digital tickets only). "
               "Seat availability depends on how many riders our tickets represent; see the technical note.")


def basis(day_type: str) -> str:
    return WEEKEND_BASIS if day_type == "weekend" else WEEKDAY_BASIS


def breakdown_note(gamma_star: float | None, gamma_max: float) -> str:
    """Tooltip for the robustness value: how much capture error the recommendation can absorb."""
    if gamma_star is None:
        return f"Holds even if these routes' ticket coverage differed by more than {gamma_max:g}×."
    return f"Holds unless these routes' ticket coverage differs by more than {gamma_star:.1f}×."
