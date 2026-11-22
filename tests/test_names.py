from crowd.names import make_normaliser, split_composite


def test_normalise_casefolds_punctuation_and_abbreviations():
    norm = make_normaliser({"bdr": "border", "sec": "sector"})
    assert norm("Kalindi Kunj Bdr") == "kalindi kunj border"
    assert norm("ROHINI  Sec-22, Terminal") == "rohini sector 22 terminal"


def test_composite_names_are_split():
    norm = make_normaliser({})
    assert split_composite(norm("Nhai / District Court / Ig Hospital")) == ["nhai", "district court", "ig hospital"]
    assert split_composite("single stop") == ["single stop"]
