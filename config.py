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

# Ruta base en la nube (ej: "backup")
RCLONE_REMOTE_PATH = os.getenv("RCLONE_REMOTE_PATH", "")

# Ruta al ejecutable 7-Zip
SEVEN_ZIP_PATH = os.getenv("SEVEN_ZIP_PATH", "7za.exe" if os.name == 'nt' else "7z")

# --- NUEVO: CONFIGURACIÓN SMART UPLOAD (Routing Fix) ---
# Cantidad máxima de intentos de subida antes de rendirse
SMART_MAX_RETRIES = int(os.getenv("SMART_MAX_RETRIES", 3))

# Tiempos de chequeo (segundos) y límites de velocidad (MB/s)
# Estos valores se leen del .env y se usan en el bucle de cloud_manager
SMART_T1_MIN = int(os.getenv("SMART_T1_MIN", 10))
SMART_T1_MAX = int(os.getenv("SMART_T1_MAX", 12))
SMART_T1_LIMIT = float(os.getenv("SMART_T1_LIMIT", 8.0))

SMART_T2_MIN = int(os.getenv("SMART_T2_MIN", 20))
SMART_T2_MAX = int(os.getenv("SMART_T2_MAX", 22))
SMART_T2_LIMIT = float(os.getenv("SMART_T2_LIMIT", 8.0))

SMART_T3_MIN = int(os.getenv("SMART_T3_MIN", 30))
SMART_T3_MAX = int(os.getenv("SMART_T3_MAX", 32))
SMART_T3_LIMIT = float(os.getenv("SMART_T3_LIMIT", 15.0))

# --- NUEVO: CONFIGURACIÓN OPTIMIZADA DE DESCARGA (RCLONE) ---
# Flags para maximizar ancho de banda
DL_TRANSFERS = os.getenv("DL_TRANSFERS", "8")
DL_CHECKERS = os.getenv("DL_CHECKERS", "16")
DL_MULTI_THREAD_STREAMS = os.getenv("DL_MULTI_THREAD_STREAMS", "8")
DL_MULTI_THREAD_CUTOFF = os.getenv("DL_MULTI_THREAD_CUTOFF", "200M")
DL_BUFFER_SIZE = os.getenv("DL_BUFFER_SIZE", "200M")
DL_WRITE_BUFFER_SIZE = os.getenv("DL_WRITE_BUFFER_SIZE", "1Mi")

# Flags Booleanos (Enable/Disable)
_http2_env = os.getenv("DL_DISABLE_HTTP2", "true").lower()
DL_DISABLE_HTTP2 = _http2_env in ("true", "1", "yes", "on")

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