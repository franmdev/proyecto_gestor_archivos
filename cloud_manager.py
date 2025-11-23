# cloud_manager.py
import os
import subprocess
import shutil
import re
import time
import sys
import signal
from pathlib import Path
from typing import List, Dict, Optional, Union
from tqdm import tqdm  # Importamos la librería para la barra de progreso

# Configuración
# AGREGADO: Importamos RCLONE_REMOTE_PATH y configuraciones Smart
from config import (
    logger, RCLONE_REMOTE, RCLONE_REMOTE_PATH, VALID_PREFIXES, DATA_DIR,
    # Variables Smart Upload
    SMART_MAX_RETRIES,
    SMART_T1_MIN, SMART_T1_MAX, SMART_T1_LIMIT,
    SMART_T2_MIN, SMART_T2_MAX, SMART_T2_LIMIT,
    SMART_T3_MIN, SMART_T3_MAX, SMART_T3_LIMIT,
    # Variables Download Optimization
    DL_TRANSFERS, DL_CHECKERS, DL_MULTI_THREAD_STREAMS, 
    DL_MULTI_THREAD_CUTOFF, DL_BUFFER_SIZE, DL_WRITE_BUFFER_SIZE,
    DL_DISABLE_HTTP2
)

class CloudManager:
    """
    FACHADA DE INFRAESTRUCTURA
    Responsabilidad: Operaciones con Rclone (Nube) y Sistema de Archivos Local.
    """

    def __init__(self):
        self.remote = RCLONE_REMOTE
        self.base_path = RCLONE_REMOTE_PATH # La carpeta base del .env
        self.rclone_path_env = os.getenv("RCLONE_PATH") 
        self.rclone_exe = self._find_rclone()

    def _find_rclone(self) -> str:
        """Busca el ejecutable rclone.exe."""
        
        # 1. Verificar ruta configurada en .env
        if self.rclone_path_env:
            path_obj = Path(self.rclone_path_env)
            
            # Si es directorio, buscar rclone.exe dentro
            if path_obj.is_dir():
                candidate = path_obj / "rclone.exe"
                if candidate.exists():
                    return str(candidate)
            
            # Si apunta directo al archivo
            if path_obj.is_file() and path_obj.exists():
                return str(path_obj)

        # 2. Intentar buscar en PATH global
        path_global = shutil.which("rclone")
        if path_global:
            return path_global
        
        # Fallback ciego
        return "rclone"

    def _build_remote_path(self, subpath: str) -> str:
        """
        MEJORA: Construye la ruta completa incluyendo la carpeta base del .env.
        Ej: Si base="backup" y subpath="DOC/file.7z" -> "remote:backup/DOC/file.7z"
        """
        # Normalizar slashes para rclone (siempre /)
        subpath = subpath.replace("\\", "/")
        
        if self.base_path:
            # Asegurar que no haya slash duplicado
            base = self.base_path.strip("/")
            clean_sub = subpath.strip("/")
            
            # Si el subpath está vacío (ej: subiendo a la raíz del backup), no agregar slash
            if not clean_sub:
                return f"{self.remote}:{base}"
                
            return f"{self.remote}:{base}/{clean_sub}"
        else:
            # Comportamiento original (Raíz)
            return f"{self.remote}:/{subpath}"

    def _parse_speed(self, line: str) -> float:
        """
        Extrae la velocidad en MB/s de una línea de log de rclone.
        Ejemplo: "Transferred: 200 MiB / 2.991 GiB, 7%, 18.182 MiB/s, ETA 2m37s"
        """
        # Regex para capturar valor y unidad (ej: 18.182 MiB)
        match = re.search(r'(\d+\.?\d*)\s+([kKMGT]?i?B)/s', line)
        if not match:
            return 0.0
        
        value = float(match.group(1))
        unit = match.group(2).upper()
        
        # Normalizar a MB/s (Megabytes por segundo, base 10 aprox para simplificar comparacion)
        if 'K' in unit: return value / 1024
        if 'M' in unit: return value
        if 'G' in unit: return value * 1024
        return 0.0

    def _parse_progress(self, line: str) -> tuple[int, int]:
        """
        Extrae bytes transferidos y total para actualizar la barra tqdm.
        Retorna (bytes_actuales, bytes_totales)
        """
        # Regex para capturar "Transferred: 200 MiB / 2.991 GiB"
        match = re.search(r'Transferred:\s+(\d+\.?\d*)\s+([kKMGT]?i?B)\s+/\s+(\d+\.?\d*)\s+([kKMGT]?i?B)', line)
        
        if not match:
            return 0, 0

        def to_bytes(val, unit):
            val = float(val)
            unit = unit.upper()
            if 'K' in unit: return int(val * 1024)
            if 'M' in unit: return int(val * 1024 * 1024)
            if 'G' in unit: return int(val * 1024 * 1024 * 1024)
            return int(val)

        current = to_bytes(match.group(1), match.group(2))
        total = to_bytes(match.group(3), match.group(4))
        return current, total

    def _get_download_flags(self) -> List[str]:
        """
        Construye la lista de flags optimizados para descarga desde config.
        Permite inyectar parámetros avanzados de Rclone.
        """
        flags = [
            f"--transfers={DL_TRANSFERS}",
            f"--checkers={DL_CHECKERS}",
            f"--multi-thread-streams={DL_MULTI_THREAD_STREAMS}",
            f"--multi-thread-cutoff={DL_MULTI_THREAD_CUTOFF}",
            f"--buffer-size={DL_BUFFER_SIZE}",
            f"--multi-thread-write-buffer-size={DL_WRITE_BUFFER_SIZE}",
        ]
        if DL_DISABLE_HTTP2:
            flags.append("--disable-http2")
        return flags

    def _run_rclone(self, args: List[str], timeout: int = 3600, show_progress: bool = False) -> bool:
        """
        Ejecuta un comando rclone genérico.
        MEJORA: 'show_progress=True' permite que rclone muestre su barra nativa en consola.
        """
        cmd = [self.rclone_exe] + args
        try:
            if show_progress:
                # NUEVO: Si queremos ver progreso, NO capturamos el output, dejamos que salga a consola
                # Usamos run normal heredando stdout/stderr
                logger.debug(f"Ejecutando Rclone (Visible): {' '.join(cmd)}")
                result = subprocess.run(cmd, timeout=timeout)
                return result.returncode == 0
            else:
                # Comportamiento original (Silencioso / Capturado)
                logger.debug(f"Ejecutando Rclone (Oculto): {' '.join(cmd)}")
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

    def _smart_upload(self, local_path: str, remote_full_path: str) -> bool:
        """
        Lógica de subida inteligente para evitar routing subóptimo (BGP).
        Evalúa velocidad a los 10s, 20s y 30s. Si es baja, reinicia la conexión.
        Implementa barra de progreso TQDM.
        """
        # COMANDO OPTIMIZADO (Solicitud Usuario)
        base_cmd = [
            self.rclone_exe, "copy", local_path, remote_full_path,
            "--transfers", "1",
            "--checkers", "1",
            "--onedrive-chunk-size", "200M",
            "--buffer-size", "200M",
            "--progress",
            "--stats", "1s", # Actualizar stats cada segundo para monitoreo real
            "-v" # Verbose para ver detalles si falla
        ]

        # MEJORA: Leer intentos máximos desde Config
        max_retries = SMART_MAX_RETRIES
        
        # Obtener tamaño total del archivo para la barra inicial
        try:
            total_size = os.path.getsize(local_path)
        except:
            total_size = 0

        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                logger.info(f"🔄 Reintentando subida (Intento {attempt}/{max_retries}) por baja velocidad...")
            
            # Usamos Popen para leer stdout en tiempo real
            process = subprocess.Popen(
                base_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Rclone manda stats a stderr a veces, combinamos
                text=True,
                encoding='utf-8',
                bufsize=1
            )

            start_time = time.time()
            killed = False
            
            # Inicializar barra TQDM
            # MEJORA: Agregamos [Avg] a la descripción para aclarar
            pbar = tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024, desc=f"Subiendo (Intento {attempt}) [Avg]", leave=False)
            last_bytes = 0

            try:
                while True:
                    # Leer línea por línea
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    
                    if line:
                        # Si encontramos datos de progreso, actualizamos la barra
                        if "Transferred:" in line and "%" in line:
                            curr_bytes, tot_bytes = self._parse_progress(line)
                            if tot_bytes > 0:
                                # TQDM update es incremental, calculamos el delta
                                delta = curr_bytes - last_bytes
                                if delta > 0:
                                    pbar.update(delta)
                                    last_bytes = curr_bytes
                        
                        # ANÁLISIS DE VELOCIDAD EN TIEMPO REAL
                        elapsed = time.time() - start_time
                        
                        # Solo analizamos si estamos en los hitos de tiempo críticos
                        if "KiB/s" in line or "MiB/s" in line or "GiB/s" in line:
                            speed = self._parse_speed(line)
                            
                            # MEJORA: Actualizar descripción con velocidad instantanea ("Speed")
                            pbar.set_postfix(Speed=f"{speed:.2f} MB/s")

                            # CONFIGURACIÓN DE PUNTOS DE CHEQUEO
                            # Tupla: (min_t, max_t, limit_speed, message, is_forced_on_last_try)
                            # MEJORA: El último booleano indica si se debe forzar el chequeo incluso en el último intento
                            check_points = [
                                (SMART_T1_MIN, SMART_T1_MAX, SMART_T1_LIMIT, "Velocidad baja", False),
                                (SMART_T2_MIN, SMART_T2_MAX, SMART_T2_LIMIT, "Velocidad baja", False),
                                (SMART_T3_MIN, SMART_T3_MAX, SMART_T3_LIMIT, "Velocidad insuficiente", True) # Corte mandatorio T3
                            ]

                            for (t_min, t_max, min_speed, msg, force_check) in check_points:
                                # Lógica: Chequeamos si NO es el último intento, O si es un chequeo forzoso (T3)
                                should_check = (attempt < max_retries) or force_check
                                
                                if should_check and (t_min <= elapsed <= t_max) and (speed < min_speed):
                                    # Cerramos barra limpiamente antes de loguear
                                    pbar.close()
                                    logger.warning(f"⚠️ {msg} ({speed:.2f} MB/s) a los {t_min}s. Reiniciando routing...")
                                    process.terminate()
                                    killed = True
                                    break
                            
                            if killed: break

            except Exception as e:
                pbar.close()
                logger.error(f"Error monitoreando proceso: {e}")
                process.terminate()
                killed = True
            
            pbar.close() # Asegurar cierre de barra al terminar el while

            # Esperar a que cierre
            if killed:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill() # Forzar cierre si no responde
                
                time.sleep(2) # Esperar un poco antes de reintentar para que el socket se libere
                continue # Vamos al siguiente intento del for
            else:
                # Si salimos del while sin killed, el proceso terminó (éxito o error natural)
                if process.returncode == 0:
                    return True
                else:
                    logger.error("❌ Rclone terminó con error (no relacionado a velocidad).")
                    # Si falló por otra cosa (auth, red), reintentamos también
                    time.sleep(2)
                    continue

        logger.error("❌ Se agotaron los intentos de subida inteligente.")
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
        # Probamos listar la raíz del remote, independiente de la carpeta base
        return self._run_rclone(["lsd", f"{self.remote}:/"], timeout=10)

    def upload_file(self, local_path: Path, remote_path: str) -> bool:
        """
        Sube un archivo específico con barra de progreso.
        MEJORA: Si el archivo es grande (>500MB), usa lógica Smart Upload.
        IMPORTANTE: 'remote_path' debe ser el DESTINO (carpeta o archivo).
        """
        local_path = Path(local_path)
        # MEJORA: Usar constructor de ruta inteligente
        full_dest = self._build_remote_path(remote_path)
        
        # Verificar tamaño para decidir estrategia
        try:
            size_mb = local_path.stat().st_size / (1024 * 1024)
        except:
            size_mb = 0

        # UMBRAL: 500 MB para activar Smart Upload
        if size_mb > 500:
            logger.info(f"⚡ Archivo grande ({size_mb:.2f} MB). Usando Smart Upload (Routing Fix)...")
            # Pasamos rutas como string para el comando Popen
            return self._smart_upload(str(local_path), full_dest)
        else:
            # Subida normal para archivos pequeños
            return self._run_rclone([
                "copy", 
                str(local_path), 
                full_dest,
                "--progress",       # Barra de progreso visual
                "--stats-one-line"  # Formato limpio
            ], show_progress=True)

    def download_file(self, remote_path: str, local_dest: Path, silent: bool = False) -> bool:
        """
        Descarga un archivo específico.
        MEJORA: Inyecta flags optimizados definidos en .env.
        """
        # Asegurar directorio destino
        local_dest.parent.mkdir(parents=True, exist_ok=True)
        
        # MEJORA: Usar constructor de ruta inteligente
        full_src = self._build_remote_path(remote_path)
        
        # Obtener flags optimizados
        opt_flags = self._get_download_flags()

        cmd = [
            "copyto", # copyto permite renombrar/definir destino exacto
            full_src,
            str(local_dest),
            "--progress",
            "--stats-one-line"
        ] + opt_flags # <-- Añadimos los flags extra aquí
        
        return self._run_rclone(cmd, show_progress=not silent)

    def sync_up(self, local_dir: Path, remote_dir: str) -> bool:
        """Sincroniza una carpeta local hacia la nube (Unidireccional)."""
        # MEJORA: Usar constructor de ruta inteligente
        full_dest = self._build_remote_path(remote_dir)
        
        return self._run_rclone([
            "sync",
            str(local_dir),
            full_dest,
            "--progress",
            "--create-empty-src-dirs"
        ], show_progress=True)