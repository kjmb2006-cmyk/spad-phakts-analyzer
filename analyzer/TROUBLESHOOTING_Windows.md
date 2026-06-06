# 🚨 SPAD Analyzer — Dépannage Windows

## Étape 1 : Diagnostic automatique

**Double-cliquez sur `diagnose.bat`** pour identifier automatiquement le problème.

## Étape 2 : Solutions selon le problème

### ❌ "Python n'est pas trouvé"

**Cause :** Python n'est pas installé ou pas dans le PATH.

**Solutions :**
1. Téléchargez Python depuis : https://www.python.org/downloads/
2. Lors de l'installation :
   - ✅ Cochez **"Add Python to PATH"**
   - ✅ Cochez **"Install for all users"** (recommandé)
3. Redémarrez votre ordinateur
4. Relancez `start.bat`

### ❌ "Impossible de créer l'environnement virtuel"

**Cause :** Droits insuffisants ou antivirus.

**Solutions :**
1. **Exécutez en tant qu'administrateur :**
   - Clic droit sur `start.bat` → "Exécuter en tant qu'administrateur"

2. **Désactivez temporairement l'antivirus :**
   - Ajoutez une exception pour ce dossier
   - Ou désactivez l'antivirus pendant l'installation

3. **Vérifiez l'espace disque :**
   - Au moins 500MB d'espace libre

### ❌ "Impossible d'installer les dépendances"

**Cause :** Connexion internet ou proxy.

**Solutions :**
1. **Vérifiez votre connexion internet**
2. **Désactivez le VPN/proxy temporairement**
3. **Installez manuellement :**
   ```cmd
   venv\Scripts\activate
   pip install -r requirements.txt --verbose
   ```

### ❌ "Environnement virtuel corrompu"

**Solutions :**
1. Supprimez le dossier `venv`
2. Relancez `start.bat`

## Étape 3 : Installation manuelle (si tout échoue)

Ouvrez l'**Invite de commandes** (recherchez "cmd") dans ce dossier :

```cmd
# Vérifiez Python
python --version
# Si ça ne marche pas, essayez :
py --version
# Ou :
python3 --version

# Créez l'environnement virtuel
python -m venv venv

# Activez-le
venv\Scripts\activate

# Installez les dépendances
pip install -r requirements.txt

# Lancez l'application
python run.py
```

## Étape 4 : Vérifications finales

- ✅ **Port 5050 libre :** Fermez autres applications utilisant ce port
- ✅ **Navigateur à jour :** Chrome, Firefox, Edge recommandé
- ✅ **Windows 10/11 :** Version récente
- ✅ **Espace disque :** Au moins 1GB libre

## 🚑 Support supplémentaire

Si rien ne marche :

1. **Exécutez `diagnose.bat`** et copiez la sortie
2. **Vérifiez les logs d'erreur** dans la fenêtre de commande
3. **Essayez sur un autre ordinateur** pour isoler le problème

## 📞 Contact

En cas de problème persistant, fournissez :
- La sortie de `diagnose.bat`
- Votre version de Windows (`winver` dans l'invite de commande)
- Les messages d'erreur exacts

---
**Dernière mise à jour :** Mai 2026