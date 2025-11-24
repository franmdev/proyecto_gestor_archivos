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
    # Variables Stall Detection
    SMART_STALL_MIN_TIME, SMART_STALL_LIMIT,
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
        Lógica de subida inteligente unificada (archivos grandes y pequeños).
        - Maneja reintentos infinitos para cortes T10/T20.
        - Solo consume intentos reales en T30.
        - Detección de estancamiento (Stall Detection).
        - Cancelación manual con Ctrl+C.
        """
        # COMANDO OPTIMIZADO
        base_cmd = [
            self.rclone_exe, "copy", local_path, remote_full_path,
            "--transfers", "1",
            "--checkers", "1",
            "--onedrive-chunk-size", "200M",
            "--buffer-size", "200M",
            "--progress",
            "--stats", "1s", 
            "-v" 
        ]

        max_critical_retries = SMART_MAX_RETRIES
        critical_failures = 0
        total_attempts = 0
        
        try:
            total_size = os.path.getsize(local_path)
        except:
            total_size = 0

        # BUCLE MANUAL WHILE PARA CONTROL FINO DE INTENTOS
        while critical_failures < max_critical_retries:
            total_attempts += 1
            if total_attempts > 1:
                logger.info(f"🔄 Reintentando subida (Global: {total_attempts} | Críticos: {critical_failures}/{max_critical_retries})...")
            
            process = subprocess.Popen(
                base_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                bufsize=1
            )

            start_time = time.time()
            killed = False
            critical_error = False # Flag para saber si el error cuenta como "vida perdida"
            
            pbar = tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024, desc=f"Subiendo (Intento {total_attempts}) [Avg]", leave=False)
            last_bytes = 0
            
            # Variables para Stall Detection (Promedio)
            accumulated_speed = 0.0
            speed_samples = 0

            try:
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    
                    if line:
                        # Parseo de Progreso
                        if "Transferred:" in line and "%" in line:
                            curr_bytes, tot_bytes = self._parse_progress(line)
                            if tot_bytes > 0:
                                delta = curr_bytes - last_bytes
                                if delta > 0:
                                    pbar.update(delta)
                                    last_bytes = curr_bytes
                        
                        elapsed = time.time() - start_time
                        
                        # Análisis de Velocidad
                        if "KiB/s" in line or "MiB/s" in line or "GiB/s" in line:
                            speed = self._parse_speed(line)
                            pbar.set_postfix(Speed=f"{speed:.2f} MB/s")
                            
                            # Acumular para Stall Detection
                            accumulated_speed += speed
                            speed_samples += 1
                            avg_speed_session = accumulated_speed / speed_samples if speed_samples > 0 else 0

                            # --- 1. DETECCIÓN DE ESTANCAMIENTO (STALL) ---
                            if elapsed > SMART_STALL_MIN_TIME and avg_speed_session < SMART_STALL_LIMIT:
                                pbar.close()
                                logger.warning(f"⚠️ ESTANCAMIENTO DETECTADO (Avg: {avg_speed_session:.2f} MB/s en {elapsed:.0f}s). Reiniciando...")
                                process.terminate()
                                killed = True
                                critical_error = True # Un estancamiento largo cuenta como falla crítica
                                break

                            # --- 2. CORTES TEMPRANOS (GRATUITOS) ---
                            # T10
                            if 10 <= elapsed <= 12 and speed < SMART_T1_LIMIT:
                                pbar.close()
                                logger.warning(f"⚠️ Velocidad baja ({speed:.2f} MB/s) a los 10s. Reinicio RÁPIDO (No consume intento)...")
                                process.terminate()
                                killed = True
                                critical_error = False # No cuenta
                                break
                            
                            # T20
                            if 20 <= elapsed <= 22 and speed < SMART_T2_LIMIT:
                                pbar.close()
                                logger.warning(f"⚠️ Velocidad baja ({speed:.2f} MB/s) a los 20s. Reinicio RÁPIDO (No consume intento)...")
                                process.terminate()
                                killed = True
                                critical_error = False # No cuenta
                                break

                            # --- 3. CORTE TARDÍO (CRÍTICO) ---
                            # T30
                            if 30 <= elapsed <= 32 and speed < SMART_T3_LIMIT:
                                pbar.close()
                                logger.warning(f"⚠️ Velocidad insuficiente ({speed:.2f} MB/s) a los 30s. Falla CRÍTICA...")
                                process.terminate()
                                killed = True
                                critical_error = True # SÍ cuenta
                                break

            except KeyboardInterrupt:
                pbar.close()
                logger.warning("\n🛑 Cancelación manual detectada.")
                process.terminate()
                return False # Abortar todo el archivo

            except Exception as e:
                pbar.close()
                logger.error(f"Error monitoreando proceso: {e}")
                process.terminate()
                killed = True
                critical_error = True
            
            pbar.close()

            if killed:
                try: process.wait(timeout=5)
                except: process.kill()
                
                time.sleep(2)
                
                if critical_error:
                    critical_failures += 1
                
                continue # Reinicia el while
            else:
                # Terminó sin killed
                if process.returncode == 0:
                    return True
                else:
                    logger.error("❌ Rclone terminó con error no controlado.")
                    time.sleep(2)
                    critical_failures += 1 # Error de rclone cuenta como crítico
                    continue

        logger.error(f"❌ Se agotaron los {max_critical_retries} intentos CRÍTICOS de subida.")
        return False

    # --- OPERACIONES LOCALES ---

    def scan_local_folders(self, parent_path: Path) -> List[Dict]:
        """
        MEJORA: Escaneo inteligente de 2 niveles para soportar Categorías.
        Devuelve una lista de diccionarios: {'path': Path, 'prefix': str, 'category': str}
        """
        parent_path = Path(parent_path)
        if not parent_path.exists():
            logger.error(f"Ruta no existe: {parent_path}")
            return []

        valid_items = []
        logger.info(f"Explorando: {parent_path}")

        for item in parent_path.iterdir():
            if item.is_dir():
                # 1. Verificar si el nombre es un Prefijo (Nivel 1: Contenedor de Categorías)
                # Ej: C:/.../DOC
                possible_prefix = item.name.upper()
                
                if possible_prefix in VALID_PREFIXES:
                    # Estamos en una carpeta PREFIJO (DOC). Exploramos sus hijos (Categorías).
                    # Ej: C:/.../DOC/Universidad
                    for subitem in item.iterdir():
                        if subitem.is_dir():
                            category_name = subitem.name # "Universidad"
                            
                            # Ahora exploramos los archivos dentro de la categoría
                            # Ej: C:/.../DOC/Universidad/Tesis
                            for final_item in subitem.iterdir():
                                if final_item.is_dir(): # Solo procesamos carpetas como unidades
                                    valid_items.append({
                                        'path': final_item,
                                        'prefix': possible_prefix,
                                        'category': category_name
                                    })
                else:
                    # 2. Verificar si es una carpeta directa con prefijo (Legacy/Simple)
                    # Ej: C:/.../DOC_Contrato
                    if any(possible_prefix.startswith(p) for p in VALID_PREFIXES):
                        # Intentamos deducir el prefijo
                        prefix_found = next((p for p in VALID_PREFIXES if possible_prefix.startswith(p)), None)
                        if prefix_found:
                            valid_items.append({
                                'path': item,
                                'prefix': prefix_found,
                                'category': 'General' # Categoría por defecto
                            })

        logger.info(f"✅ Encontradas {len(valid_items)} carpetas para procesar.")
        # Ordenamos por prefijo y luego categoría
        return sorted(valid_items, key=lambda x: (x['prefix'], x['category']))

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
        MEJORA: UNIFICACIÓN. Todos los archivos (grandes o chicos) pasan por _smart_upload.
        Esto arregla el error 'is a directory' porque _smart_upload usa 'copy', y nos da robustez siempre.
        """
        local_path = Path(local_path)
        # MEJORA: Usar constructor de ruta inteligente
        full_dest = self._build_remote_path(remote_path)
        
        try:
            size_mb = local_path.stat().st_size / (1024 * 1024)
        except:
            size_mb = 0

        # SIEMPRE USAR SMART UPLOAD (Incluso para archivos chicos)
        # Cambiado umbral > 500 a >= 0
        if size_mb >= 0:
            logger.info(f"⚡ Archivo detectado ({size_mb:.2f} MB). Iniciando transferencia Smart...")
            # Pasamos rutas como string para el comando Popen
            return self._smart_upload(str(local_path), full_dest)
        else:
            # Este bloque técnicamente es inalcanzable ahora, pero se deja por seguridad
            return self._run_rclone([
                "copyto", 
                str(local_path), 
                full_dest,
                "--progress",       
                "--stats-one-line" 
            ], show_progress=True)

    def download_file(self, remote_path: str, local_dest: Path, silent: bool = False) -> bool:
        """
        Descarga un archivo específico.
        MEJORA: Inyecta flags optimizados definidos en .env.
        MEJORA CRÍTICA: Usa 'copyto' para asegurar que el destino sea el archivo exacto.
        """
        # Asegurar directorio destino
        local_dest.parent.mkdir(parents=True, exist_ok=True)
        
        # MEJORA: Usar constructor de ruta inteligente
        full_src = self._build_remote_path(remote_path)
        
        # Obtener flags optimizados
        opt_flags = self._get_download_flags()

        cmd = [
            "copyto", 
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