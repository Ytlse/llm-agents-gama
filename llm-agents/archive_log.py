"""
archive_log.py - Script d'archivage des logs.

Ce script est destiné à être exécuté une seule fois au démarrage du stack de services
pour archiver le fichier de log existant avant que les nouveaux logs ne soient écrits.

Il lit la configuration depuis la variable d'environnement APP_CONFIG_PATH pour
trouver le chemin du fichier de log.
"""
import os
from datetime import datetime
from settings import settings

if hasattr(settings, 'app') and hasattr(settings.app, 'log_file') and settings.app.log_file:
    log_file_path = str(settings.app.log_file)
    if os.path.exists(log_file_path):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = f"{log_file_path}.{timestamp}.bak"
        try:
            os.rename(log_file_path, archive_path)
            print(f"INFO: Archived existing log file to {archive_path}")
        except OSError as e:
            print(f"ERROR: Failed to archive log file '{log_file_path}': {e}")