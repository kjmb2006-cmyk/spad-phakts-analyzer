"""
Génère un fichier Excel de données d'enquête SPAD réaliste.
Usage : python scripts/generate_sample_data.py
"""
import numpy as np
import pandas as pd
import os

np.random.seed(42)
N = 500

# ── Variables sociodémographiques ────────────────────────────────────────────
sexe = np.random.choice(['Masculin', 'Féminin'], N, p=[.52, .48])

age_classes = ['15-24 ans', '25-34 ans', '35-44 ans', '45-54 ans', '55-64 ans', '65 ans et +']
age = np.random.choice(age_classes, N, p=[.18, .22, .20, .18, .13, .09])

regions = ['Dakar', 'Thiès', 'Ziguinchor', 'Diourbel', 'Saint-Louis', 'Louga',
           'Tambacounda', 'Kaolack', 'Fatick', 'Kolda', 'Matam', 'Kaffrine',
           'Kédougou', 'Sédhiou']
region = np.random.choice(regions, N)

milieu = np.where(np.isin(region, ['Dakar', 'Thiès', 'Saint-Louis', 'Ziguinchor']),
                  np.random.choice(['Urbain', 'Rural'], N, p=[.75, .25]),
                  np.random.choice(['Urbain', 'Rural'], N, p=[.30, .70]))

niveaux = ['Sans instruction', 'Primaire', 'Secondaire', 'Supérieur']
niveau_edu = np.random.choice(niveaux, N, p=[.28, .32, .25, .15])

statut_matrimonial = np.random.choice(
    ['Célibataire', 'Marié(e)', 'Veuf/Veuve', 'Divorcé(e)'],
    N, p=[.30, .55, .09, .06])

professions = ['Agriculteur', 'Commerçant', 'Fonctionnaire', 'Salarié privé',
               'Étudiant', 'Sans emploi', 'Artisan', 'Autre']
profession = np.random.choice(professions, N,
                               p=[.22, .18, .12, .14, .10, .13, .07, .04])

taille_menage = np.random.randint(1, 15, N)

# ── Revenus et conditions de vie ─────────────────────────────────────────────
revenu_mensuel = np.random.lognormal(mean=10.5, sigma=0.8, size=N).astype(int)
revenu_mensuel = np.clip(revenu_mensuel, 20000, 2000000)

acces_eau = np.random.choice(['Robinet domicile', 'Borne fontaine', 'Puits', 'Autre'],
                              N, p=[.40, .30, .20, .10])
acces_electricite = np.random.choice(['Oui', 'Non'], N, p=[.65, .35])
type_logement = np.random.choice(['Maison individuelle', 'Appartement', 'Chambre', 'Autre'],
                                  N, p=[.55, .18, .20, .07])

# ── Questions d'enquête (Likert 1-5) ─────────────────────────────────────────
def likert(n, mu=3, sigma=1):
    vals = np.round(np.clip(np.random.normal(mu, sigma, n), 1, 5)).astype(int)
    return vals

q_satisfaction_vie     = likert(N, mu=3.2)
q_satisfaction_service = likert(N, mu=2.8)
q_acces_sante          = likert(N, mu=3.0)
q_qualite_education    = likert(N, mu=3.1)
q_securite             = likert(N, mu=2.7)
q_transport            = likert(N, mu=2.5)
q_emploi               = likert(N, mu=2.6)

# ── Questions binaires ────────────────────────────────────────────────────────
q_assurance_maladie = np.random.choice(['Oui', 'Non'], N, p=[.28, .72])
q_telephone_mobile  = np.random.choice(['Oui', 'Non'], N, p=[.78, .22])
q_internet          = np.random.choice(['Oui', 'Non'], N, p=[.45, .55])
q_compte_bancaire   = np.random.choice(['Oui', 'Non'], N, p=[.32, .68])

# ── Confiance institutionnelle (Likert) ──────────────────────────────────────
conf_gouvernement = likert(N, mu=2.8)
conf_justice      = likert(N, mu=2.6)
conf_police       = likert(N, mu=3.0)
conf_religion     = likert(N, mu=4.1, sigma=0.8)

# ── Variables continues ───────────────────────────────────────────────────────
distance_hopital = np.abs(np.random.normal(15, 12, N)).round(1)   # km
distance_ecole   = np.abs(np.random.normal(3, 4, N)).round(1)     # km
nb_enfants       = np.random.poisson(2.5, N)
nb_enfants       = np.clip(nb_enfants, 0, 12)
annees_scolarite = np.clip(np.random.normal(7, 5, N), 0, 20).round(0).astype(int)

# ── Construction du DataFrame ─────────────────────────────────────────────────
df = pd.DataFrame({
    'ID': range(1, N + 1),
    # Socio-démo
    'Sexe':                 sexe,
    'Classe_age':           age,
    'Region':               region,
    'Milieu':               milieu,
    'Niveau_education':     niveau_edu,
    'Statut_matrimonial':   statut_matrimonial,
    'Profession':           profession,
    'Taille_menage':        taille_menage,
    'Nb_enfants':           nb_enfants,
    'Annees_scolarite':     annees_scolarite,
    # Conditions de vie
    'Revenu_mensuel_FCFA':  revenu_mensuel,
    'Acces_eau_potable':    acces_eau,
    'Electricite':          acces_electricite,
    'Type_logement':        type_logement,
    'Distance_hopital_km':  distance_hopital,
    'Distance_ecole_km':    distance_ecole,
    # Satisfaction (1=Très insatisfait … 5=Très satisfait)
    'Satisfaction_vie':           q_satisfaction_vie,
    'Satisfaction_services_pub':  q_satisfaction_service,
    'Acces_soins_sante':          q_acces_sante,
    'Qualite_education':          q_qualite_education,
    'Securite_quartier':          q_securite,
    'Transport_public':           q_transport,
    'Opportunites_emploi':        q_emploi,
    # Accès services (Oui/Non)
    'Assurance_maladie':    q_assurance_maladie,
    'Telephone_mobile':     q_telephone_mobile,
    'Acces_internet':       q_internet,
    'Compte_bancaire':      q_compte_bancaire,
    # Confiance institutions (1=Pas du tout … 5=Totalement)
    'Confiance_gouvernement': conf_gouvernement,
    'Confiance_justice':      conf_justice,
    'Confiance_police':       conf_police,
    'Confiance_religion':     conf_religion,
})

# Introduce ~5% missing values randomly
mask = np.random.rand(*df.shape) < 0.05
mask[:, 0] = False  # preserve ID
df = df.where(~mask, other=np.nan)

out_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'donnees_enquete_spad.xlsx')
df.to_excel(out_path, index=False, engine='openpyxl')
print(f"✓ Fichier généré : {os.path.abspath(out_path)}")
print(f"  {N} observations × {len(df.columns)} variables")
