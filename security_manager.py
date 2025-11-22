# security_manager.py
import os
import json
import shutil
import hashlib
import base64
import subprocess
from pathlib import Path
from typing import Dict, Tuple, Optional

# Librerías de criptografía (Standard NIST)
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Importamos configuración
from config import logger, SEVEN_ZIP_PATH

class SecurityManager:
    """
    FACHADA DE SEGURIDAD
    Responsabilidad: Encriptación, Hashing y Compresión (7z).
    """

    def __init__(self, master_password: str):
        """Inicializa el motor criptográfico con la contraseña maestra."""
        if len(master_password) < 12:
            logger.warning("⚠️ La contraseña maestra es corta (<12 chars). Se recomienda mayor longitud.")
            
        self.master_password = master_password
        self.key = self._derive_key(master_password)
        self.cipher = Fernet(self.key)
        self.seven_zip_exe = self._find_7z_executable()

    def _derive_key(self, password: str) -> bytes:
        """
        Deriva una clave de 32 bytes segura usando PBKDF2HMAC-SHA256.
        Estándar recomendado por NIST (100,000 iteraciones).
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'gestor_archivos_encriptados_salt_fijo', # Salt fijo para poder regenerar la misma clave
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def _find_7z_executable(self) -> str:
        """Localiza el ejecutable de 7-Zip (7za.exe o 7z.exe)."""
        # 1. Obtener ruta del .env
        env_path = Path(SEVEN_ZIP_PATH) if SEVEN_ZIP_PATH else None

        # Si existe y es un directorio, buscamos el exe dentro
        if env_path and env_path.is_dir():
            # Prioridad: 7za.exe (portable standalone) > 7z.exe (full)
            for exe in ["7za.exe", "7z.exe"]:
                candidate = env_path / exe
                if candidate.exists():
                    return str(candidate)

        # Si el usuario puso la ruta completa al archivo en el .env
        if env_path and env_path.is_file() and env_path.exists():
            return str(env_path)

        # 2. Fallback: Intentar PATH del sistema
        path_in_env = shutil.which("7z") or shutil.which("7za")
        if path_in_env:
            return path_in_env
            
        error_msg = f"❌ No se encuentra 7-Zip en {env_path}. Verifica tu .env"
        logger.critical(error_msg)
        raise FileNotFoundError(error_msg)

    # --- MÉTODOS DE ENCRIPTACIÓN DE DATOS ---

    def encrypt_text(self, plaintext: str) -> str:
        """Encripta texto (ej: nombre original) devolviendo un token Fernet reversible."""
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt_text(self, token: str) -> str:
        """Desencripta un token Fernet para recuperar el texto original."""
        try:
            return self.cipher.decrypt(token.encode()).decode()
        except Exception as e:
            logger.error(f"Error desencriptando token: {e}")
            return "[ERROR_DECRYPT]"

    def generate_filename_hash(self, plaintext: str) -> str:
        """
        Genera un hash determinista corto (12 chars) basado en el nombre y la contraseña.
        Se usa para el nombre del archivo .7z en la nube (ofuscación).
        """
        combined = f"{plaintext}:{self.master_password}"
        full_hash = hashlib.sha256(combined.encode()).hexdigest()
        return full_hash[:12] # Primeros 12 caracteres hexadecimales

    # --- MÉTODOS DE INTEGRIDAD Y HASHING ---

    def calculate_md5(self, path: Path) -> str:
        """Calcula el MD5 de un archivo o carpeta (recursivo)."""
        path = Path(path)
        hasher = hashlib.md5()
        
        if path.is_file():
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
        elif path.is_dir():
            # Para carpetas, hasheamos los hashes de los archivos ordenados alfabéticamente
            for p in sorted(path.rglob("*")):
                if p.is_file():
                    with open(p, "rb") as f:
                        file_hash = hashlib.md5(f.read()).hexdigest()
                    hasher.update(file_hash.encode())
        
        return hasher.hexdigest()

    def get_size_mb(self, path: Path) -> float:
        """Calcula el tamaño en MB."""
        path = Path(path)
        total = 0
        if path.is_file():
            total = path.stat().st_size
        elif path.is_dir():
            total = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        return round(total / (1024 * 1024), 2)

    # --- MÉTODOS DE COMPRESIÓN (7-ZIP) ---

    def compress_encrypt_7z(self, source_path: Path, dest_path: Path, metadata: Dict = None) -> bool:
        """
        Comprime una carpeta/archivo a .7z usando AES-256 y Header Encryption (-mhe=on).
        Opcionalmente inyecta un archivo 'metadatos.json' dentro del 7z para recuperación.
        """
        source_path = Path(source_path)
        dest_path = Path(dest_path)
        
        # Asegurar que destino existe
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Manejo de metadatos temporales
        temp_meta_path = None
        try:
            cmd = [
                self.seven_zip_exe, "a",       # Add (Comprimir)
                f"-p{self.master_password}",   # Password
                "-mhe=on",                     # Encrypt Headers (Oculta nombres de archivo)
                "-mx=9",                       # Compresión Máxima
                "-y",                          # Yes to all
                str(dest_path),                # Archivo destino
                str(source_path)               # Fuente
            ]

            # Si hay metadatos, crear JSON temporal e incluirlo
            if metadata:
                temp_meta_path = source_path.parent / "metadatos.json"
                with open(temp_meta_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
                cmd.append(str(temp_meta_path)) # Agregar el JSON al comando 7z

            # Ejecutar 7z
            logger.debug(f"Ejecutando 7z: {' '.join(cmd).replace(self.master_password, '******')}")
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

            if result.returncode != 0:
                logger.error(f"❌ Error 7z: {result.stderr}")
                return False
            
            logger.info(f"✅ Compresión exitosa: {dest_path.name}")
            return True

        except Exception as e:
            logger.error(f"Excepción en compresión: {e}")
            return False
        finally:
            # Limpieza de archivo temporal
            if temp_meta_path and temp_meta_path.exists():
                temp_meta_path.unlink()

    def decrypt_extract_7z(self, archive_path: Path, dest_folder: Path) -> bool:
        """Desencripta y extrae un archivo .7z."""
        try:
            cmd = [
                self.seven_zip_exe, "x",       # Extract
                f"-p{self.master_password}",   # Password
                f"-o{dest_folder}",            # Output folder
                "-y",                          # Sobreescribir sin preguntar
                str(archive_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode != 0:
                # Error común: Contraseña incorrecta
                if "Wrong password" in result.stderr or "Data Error" in result.stderr:
                    logger.error("❌ Contraseña incorrecta o archivo corrupto.")
                else:
                    logger.error(f"❌ Error extrayendo 7z: {result.stderr}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Excepción en extracción: {e}")
            return False

    def recover_metadata_from_7z(self, archive_path: Path) -> Dict:
        """
        Intenta extraer SOLO el archivo metadatos.json del 7z sin descomprimir todo.
        Útil para reconstrucción de índice.
        """
        import uuid
        temp_extract_dir = Path(f"temp_meta_{uuid.uuid4().hex[:8]}")
        
        try:
            cmd = [
                self.seven_zip_exe, "e",       # Extract (sin directorios)
                f"-p{self.master_password}",
                f"-o{temp_extract_dir}",
                str(archive_path),
                "metadatos.json",              # Solo este archivo
                "-r"                           # Recursivo
            ]
            
            subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            
            meta_file = temp_extract_dir / "metadatos.json"
            if meta_file.exists():
                with open(meta_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
            
        except Exception as e:
            logger.error(f"Error recuperando metadatos: {e}")
            return {}
        finally:
            if temp_extract_dir.exists():
                shutil.rmtree(temp_extract_dir, ignore_errors=True)