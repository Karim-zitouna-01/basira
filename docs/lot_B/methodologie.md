# Méthodologie et décisions d'intégration

Ce document explicite les ambiguïtés des spécifications. Il ne remplace pas le
contrat original. Les limites ci-dessous doivent être examinées avec A et C lors
de l'intégration; aucun fichier de A n'est corrigé en silence.

## Temps et absence de fuite du futur

- `mois=M` désigne une photographie à la **fin du mois M**. Une déclaration de
  période M est généralement déposée en M+1; les comparaisons fiscales utilisent
  donc la dernière période échue, M-1. Les imports de changement et de référence
  douanière peuvent utiliser M, car ils sont déjà enregistrés.
- Une déclaration n'est utilisable que si `date_depot <= fin(M)`, même si le CSV
  contient déjà sa valeur finale. Les périodes manquantes restent absentes :
  elles ne deviennent pas un CA nul. Les comparaisons fiscales à douze mois
  nécessitent douze dépôts disponibles; sinon le signal est neutralisé.
- TVA import : le dictionnaire indique que la TVA douanière de t est déduite en
  t+1. Les douze périodes de TVA déclarée sont comparées aux douze périodes
  douanières **décalées d'un mois**, pour éviter une fausse alerte de croissance.
- Annexes I, II, V : exercice N utilisable à partir de N+1-03. En janvier/février
  2026, l'exercice retenu est 2024, pas 2025. Ne pas remplacer un exercice absent
  par un exercice ultérieur. Les paiements annuels sont comparés au CA TTC du
  même exercice. Une couverture fiscale de seulement septembre-décembre 2023
  ne justifie pas une comparaison avec les douze mois de paiements 2023.
- Les nouvelles relations locales sont celles dont `premiere_annee_relation`
  égale le dernier exercice publié; aucun mois de transaction locale n'est inventé.
  Les fournisseurs étrangers et chapitres SH sont nouveaux au sens de la
  **première observation dans les données disponibles**, sur les trois derniers mois.
- Les métriques réseau mensuelles sont une entrée de confiance de A, selon §2.14.
  B sélectionne exactement M, sans propagation d'un mois futur. Pour les preuves
  de proximité, B reconstruit des chemins d'au plus trois liens avec les lignes
  annuelles disponibles et les imports enregistrés; seuls les résultats notifiés
  avant la fin de M peuvent être cités. Les arêtes agrégées sur toute l'histoire
  ne sont pas utilisées.
- Le registre et les références sont supposés stables, comme dans le dictionnaire.
  Des modifications réelles d'effectif, d'activité, de prix de référence ou des
  corrections d'annexe exigeraient des versions datées supplémentaires que le
  schéma fourni ne contient pas. Les calculs de pairs n'utilisent pas les valeurs
  d'une entreprise avant sa création.

Le décalage de disponibilité peut décaler une trajectoire illustrée dans les
mocks. Il ne faut pas introduire une fuite temporelle pour forcer 28 → 52 → 76.

## Statistiques et bornes

- EWMA du niveau courant : α=0,3, `adjust=False`. Référence : les dix valeurs de
  [t-12,t-3], donc parmi les douze mois précédents, sans t-2 et t-1. Au moins six
  observations de référence et une observation courante sont exigées.
- Écart-type échantillonnal, plancher max(5 % de la moyenne absolue, 1 TND).
  Une série constante ne provoque pas de division par zéro. Le CA prend la valeur
  absolue du z; imports et TVA locale ne retiennent que la hausse.
- Normalisation z : `clip((z-1)/3,0,1)`. Pour les autres signaux, les formules du
  catalogue s'appliquent. Un ratio 0/0 vaut 0; positif/0 vaut 10 (sentinelle finie
  saturant la normalisation). Une croissance depuis zéro vaut +1 000 points de
  pourcentage, et 0 → 0 vaut 0. Ces conventions évitent NaN et infinis sans cacher
  la reprise d'une entreprise dormante.
- La marge apparente et le ratio imports/CA sont indéfinis si CA=0; CA/salarié si
  effectif=0; TVA déductible/collectée si collectée=0. Ils sont exclus des statistiques
  correspondantes. Les fichiers `pairs_stats` donnent le nombre de valeurs valides.
- PAI_MARGE : z négatif autour de la médiane, échelle MAD × 1,4826, plancher max
  (5 % de la médiane absolue, 1 point de marge); minimum trois pairs exploitables.
- Mahalanobis : centrage médian, échelle MAD, winsorisation à ±4 pour estimer la
  covariance; régularisation `0,9 covariance + 0,1 I`, pseudo-inverse. La distance
  porte sur les observations non tronquées. Minimum cinq observations complètes.
  La variable dominante maximise la valeur absolue de la contribution
  `z_j × (precision × z)_j`. Aucune cible ni modèle entraîné n'intervient.
- Les groupes sont stables : taille au registre d'existence, division NAT × taille,
  repli division puis section si moins de 30 entreprises. **Tous** les membres
  de la division/section alimentent un groupe de repli, y compris ceux qui ont
  leur propre groupe fin. Si la section a moins de 30 membres, elle reste le
  dernier niveau prévu; `nb_pairs` et `nb` rendent cette limite visible.
- `RES_COQUILLE.valeur_brute` est en pourcentage (0,38 devient 38); la
  normalisation utilise la fraction originale `0,38 / 0,3`.
- `COH_ADEB_VS_CA` conserve la normalisation définie du ratio paiements HT / CA.
  L'écart de retenue TVA est calculé et conservé dans l'audit. Le contrat ne donne
  aucune formule pour l'ajouter au ratio : aucun poids supplémentaire n'est inventé.

## Preuves et formulations

Les calculs utilisent **toutes** les lignes admissibles. L'interface n'autorise
que 50 références; elles sont dédupliquées et classées par montant décroissant
puis identifiant pour un résultat stable. Les `fait_fr` décrivent la nature du
signal et citent une valeur exacte sur une pièce affichée. Pour les comparaisons
de cohérence, les totaux sont affichés si toutes leurs lignes tiennent dans les
50 références. Cela évite d'affirmer
qu'un total issu de milliers de lignes serait recalculable à partir des 50 seules
pièces affichées. Les faits de pairs nomment la variable dominante; les statistiques
numériques complètes sont dans `pairs_stats.parquet` et l'audit.

Pour la liquidation douanière, qui n'a pas d'identifiant de ligne unique, la clé
est `douane_liquidation:<id_article>:105`. Pour un contrôle cité sur un chemin :
`historique_controles:<id_controle>`. Ces références utilisent le format général
`table:identifiant`; C doit résoudre ces clés composites au même titre que
`declarations_mensuelles:<mf>:<mois>`.

`audit_signaux.jsonl` garde les agrégats et la taille des ensembles de preuves;
il n'est pas un remplacement des données brutes ni un export de toute la lignée.
Pour reproduire un calcul complet, réexécuter B avec les CSV identifiés par les
SHA-256 du rapport. Une métrique réseau active sans justificatif est signalée
comme incohérence d'entrée; ne pas la présenter comme un constat vérifié.

## Enjeux

- L'annexe V est TTC. Conversion en HT avec le taux effectif observable sur
  l'exercice complet; repli à 19 % si cette information manque. Même convention
  pour le `montant_brut` d'annexe II (hypothèse à confirmer avec A).
- `ca_observe_12m = max(clients_HT_du_dernier_exercice + ADEB_HT_12m,
  imports_CAF_12m × (1 + marge_pairs))`.
- `base_omise = max(observé - déclaré, 0)`.
- `tva_surdeduite = max(TVA_import_déduite - TVA_douane_alignée, 0)
  + TVA_locale_déduite × part_achats_coquilles`.
- `enjeu = base_omise × 0,19 + base_omise × marge_pairs × 0,20
  + tva_surdeduite`. Marge médiane des pairs bornée à [0,1], 0 si inexploitable.
- Confiance : moyenne de `min(mois_deposes/24,1)`, `sources_observees/4` et
  `1 - abs(reconstitution_1-reconstitution_2)/max(reconstitutions)`.
  L'accord vaut 0 si une reconstruction manque. Sources : fiscal, douane,
  paiements clients et ADEB. Intervalle : ±[30 % + 40 % × (1-confiance)].
- La combinaison de recettes annuelles retardées et de flux glissants est une
  approximation prescrite par le contrat. Un payeur public peut aussi apparaître
  en annexe V : sans rapprochement transactionnel, la somme peut compter deux fois
  une recette. La note indique cette limite. Ces estimations ne sont pas un avis
  fiscal ni une somme effectivement recouvrable.
- Le Monte Carlo était explicitement facultatif; la fourchette déterministe,
  reproductible et dépendante de la confiance est celle livrée.

## Autres incohérences documentaires

Le texte annonce 13 caractères pour `mf`, mais les identifiants héros et la
structure 7 chiffres + 3 lettres + 3 chiffres de certaines descriptions ne
coïncident pas avec les exemples à 12 caractères. B conserve exactement les clés
reçues, sans les renuméroter ni imposer une longueur contradictoire.

Un seul nouveau fournisseur donne `1/5=0,2` pour CHG_NOUVEAUX_FOURNISSEURS : il ne
peut donc pas être actif au seuil 0,5, même si une histoire de démo le suggère.
Le jeu jouet d'Alpha comporte trois fournisseurs nouveaux et une hausse plus forte
pour tester un signal actif après latence. Il n'est pas la calibration de A.
