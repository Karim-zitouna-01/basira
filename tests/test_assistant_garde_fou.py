from api.assistant import _extraire_sources, nombres_non_fondes, outils_evidents


class _FauxFront:
    def _reseau(self, mf, max_contreparties=40):
        return [{"id": "FE00231", "label": "Shenzhen Tools Co."}, {"id": "1001", "label": "Société Jaziri Home Center SARL"},
                {"id": "1002", "label": "Sfax"}], {}, {}


def test_outils_evidents():
    f = _FauxFront()
    for q in ("Qui d'autre travaille avec Shenzhen Tools Co. ?", "Et Shenzhen Tools ?"):  # forme juridique ignorée
        assert outils_evidents(f, "X", q) == [("get_liens_contrepartie", {"contrepartie": "Shenzhen Tools Co."})]
    assert outils_evidents(f, "X", "Quelles entreprises sont à Sfax ?") == []  # nom trop court : le modèle choisit
    assert outils_evidents(f, "X", "Pourquoi Jaziri Home Center est signalée ?") == [("get_liens_contrepartie", {"contrepartie": "Société Jaziri Home Center SARL"})]
    assert outils_evidents(f, "X", "Est-elle reliée à une entreprise redressée ?") == [("get_chemin_redresse", {})]
    assert outils_evidents(f, "X", "Pourquoi ce score ?") == []
    assert outils_evidents(None, "X", "Trace le chemin") == []


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
