# SPAD Analyzer — Guide de démarrage

## Installation (une seule fois)

```bash
cd "spad_analyzer"
pip3 install -r requirements.txt
```

## Générer les données d'exemple

```bash
python3 scripts/generate_sample_data.py
```

Crée `data/donnees_enquete_spad.xlsx` — 500 observations × 32 variables.

## Lancer l'application

```bash
python3 run.py
```

Puis ouvrir le navigateur : **http://localhost:5050**

---

## Structure du projet

```
spad_analyzer/
├── app.py                    # Application Flask principale
├── run.py                    # Script de démarrage
├── requirements.txt          # Dépendances Python
├── config.py                 # Configuration
├── modules/
│   ├── data_loader.py        # Chargement Excel, types de variables
│   ├── descriptive.py        # Tris à plat, stats continues
│   ├── crosstabs.py          # Tableaux croisés, khi-deux
│   ├── multivariate.py       # ACP, ACM, AFC, K-Means
│   └── report_generator.py   # Génération PDF automatique
├── templates/                # Pages HTML (Bootstrap 5)
├── static/                   # CSS, JS, fichiers uploadés
├── data/                     # Données d'exemple
└── scripts/                  # Scripts utilitaires
```

## Fonctionnalités

| Module | Fonctions |
|--------|-----------|
| **Import** | Excel .xlsx / .xls, détection automatique des types |
| **Descriptif** | Tris à plat, fréquences, moyennes, médianes, histogrammes |
| **Tableaux croisés** | χ², V de Cramér, résidus standardisés, profils lignes/colonnes |
| **ACP** | Valeurs propres, cercle des corrélations, biplot, scree plot |
| **ACM** | Plan factoriel individus + modalités |
| **AFC** | Plan de correspondance entre deux variables catégorielles |
| **K-Means** | Segmentation, méthode du coude, silhouette, profils radar |
| **Rapport PDF** | Export automatique avec tableaux et graphiques |

## Formats de données acceptés

- Première ligne = noms de variables
- Une ligne = une observation (individu enquêté)
- Variables catégorielles : texte ou codes numériques (≤ 15 valeurs uniques)
- Variables continues : valeurs numériques (> 15 valeurs uniques)
- Valeurs manquantes : cellules vides
