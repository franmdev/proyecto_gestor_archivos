# cloud_manager.py
import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Union

# Configuración
from config import logger, RCLONE_REMOTE, VALID_PREFIXES, DATA_DIR

class CloudManager:
    """
    FACHADA DE INFRAESTRUCTURA
    Responsabilidad: Operaciones con Rclone (Nube) y Sistema de Archivos Local.
    """

    def __init__(self):
        self.remote = RCLONE_REMOTE
        self.rclone_exe = self._find_rclone()

    def _find_rclone(self) -> str:
        """Busca rclone en el sistema."""
        # Intentar buscar en PATH
        path = shutil.which("rclone")
        if path:
            return path
        
        # Fallback común en Windows
        if os.name == 'nt':
            common = Path(r"C:\rclone\rclone.exe")
            if common.exists():
                return str(common)
        
        # Si no lo encuentra, asumimos que 'rclone' comando funciona o fallará luego
        return "rclone"

    def _run_rclone(self, args: List[str], timeout: int = 3600) -> bool:
        """Ejecuta un comando rclone genérico."""
        cmd = [self.rclone_exe] + args
        try:
            logger.debug(f"Ejecutando Rclone: {' '.join(cmd)}")
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                timeout=timeout
            )
            
            if result.returncode != 0:
                # Filtramos errores que no son críticos (ej: avisos de 'directory not found' al listar)
                if "directory not found" not in result.stderr.lower():
                    logger.error(f"❌ Error Rclone: {result.stderr.strip()}")
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error("❌ Rclone excedió el tiempo límite.")
            return False
        except Exception as e:
            logger.error(f"❌ Excepción Rclone: {e}")
            return False

    # --- OPERACIONES LOCALES ---

    def scan_local_folders(self, parent_path: Path) -> List[Path]:
        """
        Escanea una ruta local y devuelve las subcarpetas que tienen
        un prefijo válido (DOC, FIN, etc).
        """
        parent_path = Path(parent_path)
        if not parent_path.exists():
            logger.error(f"Ruta no existe: {parent_path}")
            return []

        valid_folders = []
        logger.info(f"Explorando: {parent_path}")

        for item in parent_path.iterdir():
            if item.is_dir():
                # Verificar si el nombre empieza con algún prefijo válido (case insensitive)
                if any(item.name.upper().startswith(p) for p in VALID_PREFIXES):
                    valid_folders.append(item)
                else:
                    logger.debug(f"Saltando carpeta sin prefijo válido: {item.name}")
        
        logger.info(f"✅ Encontradas {len(valid_folders)} carpetas para procesar.")
        return sorted(valid_folders)

    def clean_temp(self):
        """Limpia la carpeta temporal."""
        temp_dir = DATA_DIR / "temp"
        for item in temp_dir.glob("*"):
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception:
                pass

    # --- OPERACIONES EN LA NUBE (RCLONE) ---

    def check_connection(self) -> bool:
        """Verifica si rclone puede ver el remoto."""
        return self._run_rclone(["lsd", f"{self.remote}:/"], timeout=10)

    def upload_file(self, local_path: Path, remote_path: str) -> bool:
        """Sube un archivo específico."""
        return self._run_rclone([
            "copy", 
            str(local_path), 
            f"{self.remote}:/{remote_path}",
            "--progress"
        ])

    def download_file(self, remote_path: str, local_dest: Path) -> bool:
        """Descarga un archivo específico."""
        # Asegurar directorio destino
        local_dest.parent.mkdir(parents=True, exist_ok=True)
        return self._run_rclone([
            "copyto", # copyto permite renombrar/definir destino exacto
            f"{self.remote}:/{remote_path}",
            str(local_dest),
            "--progress"
        ])

    def sync_up(self, local_dir: Path, remote_dir: str) -> bool:
        """Sincroniza una carpeta local hacia la nube (Unidireccional)."""
        return self._run_rclone([
            "sync",
            str(local_dir),
            f"{self.remote}:/{remote_dir}",
            "--progress",
            "--create-empty-src-dirs"
        ])