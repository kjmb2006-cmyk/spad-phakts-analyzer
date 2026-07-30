import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# When launched by Electron in packaged mode, the bundle may sit in a
# read-only location, so the launcher passes a user-writable directory.
# In dev / standalone runs we fall back to <BASE_DIR>/static/.
USER_DATA_DIR = os.environ.get('SPAD_USER_DATA_DIR') or os.path.join(BASE_DIR, 'static')


class Config:
    # En local, une valeur par défaut suffit (le seul verrou d'accès est déjà
    # le système d'exploitation). Dès que l'app est exposée publiquement
    # (ex. Render), SECRET_KEY doit être définie via une variable d'environnement
    # réellement aléatoire — sinon les sessions (dont l'authentification, voir
    # app.py) peuvent être falsifiées par quiconque connaît la valeur par défaut
    # codée ici, qui est visible dans le dépôt Git.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'spad-analyzer-2024-secret')
    UPLOAD_FOLDER = os.path.join(USER_DATA_DIR, 'uploads')
    REPORTS_FOLDER = os.path.join(USER_DATA_DIR, 'reports')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB
    ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
    TEMP_FILE_TTL = 24 * 3600
    SESSION_TYPE = 'filesystem'
