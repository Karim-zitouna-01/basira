from api.assistant import _extraire_sources, nombres_non_fondes


def test_nombres_fondes():
    ctx = '{"score": 76.0, "enjeu": 420000.0, "marge": 0.03, "fait_fr": "Importations ×3,4 ; +240 %"}'
    assert nombres_non_fondes("Le score est de 76, enjeu 420 000 DT, marge 3 %, imports ×3,4 et +240 %.", ctx) == []


def test_nombres_inventes():
    ctx = '{"score": 76.0, "enjeu": 420000.0}'
    assert nombres_non_fondes("Le score est de 76 et l'enjeu de 950 000 DT.", ctx) == [950000.0]


def test_sources():
    corps, cit = _extraire_sources("Réponse.\nSOURCES : COH_IMPORT_VS_CA, douane_articles:2026/401/0034567-001, blabla")
    assert corps == "Réponse."
    assert cit == [{"type": "signal", "ref": "COH_IMPORT_VS_CA"}, {"type": "preuve", "ref": "douane_articles:2026/401/0034567-001"}]
