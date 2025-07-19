import shutil
from datetime import datetime
import os

def backup_configs():
    backup_name = f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    os.makedirs(backup_name, exist_ok=True)
    for file in ['.env', 'config.py']:
        if os.path.exists(file):
            shutil.copy(file, backup_name)
