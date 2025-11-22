# config.py
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# --- 1. CONFIGURACIÓN DE RUTAS ---
# Base del proyecto (donde está este archivo)
BASE_DIR = Path(__file__).resolve().parent

# Carpetas de datos
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"
TEMP_DIR = DATA_DIR / "temp"
INDEX_DIR = DATA_DIR / "index"
BACKUP_DIR = DATA_DIR / "backups"

# --- 2. CARGA DE VARIABLES DE ENTORNO ---
load_dotenv()  # Carga el archivo .env si existe

# --- 3. CONFIGURACIÓN DE HERRAMIENTAS EXTERNAS ---
# Nombre del remote en rclone (ej: mi_remote)
RCLONE_REMOTE = os.getenv("RCLONE_REMOTE_NAME", "mi_remote")

# NUEVO: Ruta base en la nube (ej: "backup")
# Si no se define en .env, usa vacío (raíz)
RCLONE_REMOTE_PATH = os.getenv("RCLONE_REMOTE_PATH", "")

# Ruta al ejecutable 7-Zip
# Intenta leer del .env, si no, usa valores por defecto según el sistema operativo
SEVEN_ZIP_PATH = os.getenv("SEVEN_ZIP_PATH", "7za.exe" if os.name == 'nt' else "7z")

# --- 4. CONSTANTES DE NEGOCIO ---
# Prefijos permitidos para organizar carpetas
VALID_PREFIXES = [
    'DOC', 'FIN', 'MED', 'IMG', 'BAK', 'COD', 
    'VID', 'ARC', 'PWR', 'DAT', 'EML', 'MIX',
    'GAM'
]

# Estructura del CSV (Columnas)
CSV_COLUMNS = [
    'id_global',                # ID único incremental
    'id_prefix',                # ID incremental por prefijo (DOC_001)
    'prefijo',                  # Categoría (DOC)
    'nombre_original',          # Nombre real (leíble)
    'nombre_original_encrypted',# Token Fernet completo (recuperación)
    'nombre_encriptado',        # Hash determinista 12 chars (nombre de archivo)
    'ruta_relativa',            # Ruta en la nube
    'carpeta_hija',             # Nombre de la carpeta comprimida
    'tamaño_mb',                # Peso del archivo
    'hash_md5',                 # Integridad del contenido
    'fecha_procesado',          # Timestamp ISO
    'notas'                     # Metadatos extra
]

# --- 5. CONFIGURACIÓN DE LOGGING (AUDITORÍA) ---
# Crear carpeta de logs si no existe
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Configurar formato y handlers (Consola y Archivo)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(module)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOGS_DIR / "app.log", encoding='utf-8'), # Persistencia
        logging.StreamHandler(sys.stdout)                           # Ver en terminal
    ]
)

# Logger global para importar en otros módulos
logger = logging.getLogger("GestorArchivos")

def init_directories():
    """Crea la estructura de directorios necesaria si no existe."""
    dirs = [
        DATA_DIR, LOGS_DIR, TEMP_DIR, INDEX_DIR,
        BACKUP_DIR / "auto", BACKUP_DIR / "manual",
        DATA_DIR / "descargas", DATA_DIR / "desencriptados"
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    logger.info("📂 Estructura de directorios verificada.")