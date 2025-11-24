# inventory_manager.py
import pandas as pd
import shutil
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Configuración
from config import logger, CSV_COLUMNS, INDEX_DIR, BACKUP_DIR, TEMP_DIR

class InventoryManager:
    """
    FACHADA DE DATOS
    Responsabilidad: Gestionar el índice (CSV/Pandas), búsquedas y persistencia.
    Maneja su propia contraseña para proteger el archivo de índice.
    """

    def __init__(self, csv_password: str):
        self.csv_path = INDEX_DIR / "index_main.csv"
        self.csv_password = csv_password  # Clave específica para el CSV
        self.df = self._load_or_create_db()

    def _load_or_create_db(self) -> pd.DataFrame:
        """Carga el CSV local o crea uno vacío si no existe."""
        if self.csv_path.exists():
            try:
                # MEJORA: utf-8-sig para compatibilidad con Excel (Ñ/Tildes)
                df = pd.read_csv(self.csv_path, encoding='utf-8-sig')
                # Validar columnas mínimas
                missing = [col for col in CSV_COLUMNS if col not in df.columns]
                if missing:
                    logger.warning(f"⚠️ CSV antiguo. Faltan columnas: {missing}. Se recrearán.")
                    return self._create_empty_db()
                return df
            except Exception as e:
                logger.error(f"Error leyendo CSV: {e}. Creando uno nuevo.")
                return self._create_empty_db()
        else:
            return self._create_empty_db()

    def _create_empty_db(self) -> pd.DataFrame:
        return pd.DataFrame(columns=CSV_COLUMNS)

    # --- GESTIÓN DE REGISTROS ---

    def check_exists(self, prefijo: str, nombre_original: str) -> bool:
        """
        MEJORA: Verifica si ya existe un archivo con el mismo nombre original dentro del mismo prefijo.
        Evita duplicados en la subida.
        """
        if self.df.empty:
            return False
        
        # Filtramos por prefijo y nombre original exacto
        exists = not self.df[
            (self.df['prefijo'] == prefijo) & 
            (self.df['nombre_original'] == nombre_original)
        ].empty
        return exists

    def add_record(self, record: Dict):
        """Añade un registro al DataFrame en memoria (no guarda a disco aún)."""
        new_row = pd.DataFrame([record])
        
        # CORRECCIÓN PANDAS WARNING:
        # Eliminamos columnas totalmente vacías/NA antes de concatenar
        new_row = new_row.dropna(how='all', axis=1)
        
        if self.df.empty:
            self.df = new_row
        else:
            self.df = pd.concat([self.df, new_row], ignore_index=True)

    def get_next_ids(self, prefix: str) -> tuple[int, int]:
        """
        Calcula el siguiente ID Global y el siguiente ID para un Prefijo.
        Returns: (next_global_id, next_prefix_id)
        """
        # ID Global
        if self.df.empty:
            next_global = 1
        else:
            # Convertir a numérico forzosamente para evitar errores de string
            next_global = pd.to_numeric(self.df['id_global'], errors='coerce').max()
            next_global = 1 if pd.isna(next_global) else int(next_global) + 1

        # ID Prefijo
        prefix_df = self.df[self.df['prefijo'] == prefix]
        if prefix_df.empty:
            next_prefix = 1
        else:
            next_prefix = pd.to_numeric(prefix_df['id_prefix'], errors='coerce').max()
            next_prefix = 1 if pd.isna(next_prefix) else int(next_prefix) + 1

        return next_global, next_prefix

    # --- CONSULTAS PARA NUEVO FLUJO DE DESCARGA ---

    def get_prefixes_summary(self) -> pd.DataFrame:
        """Retorna un DataFrame con el conteo de archivos por prefijo."""
        if self.df.empty:
            return pd.DataFrame(columns=['prefijo', 'count'])
        # Cuenta cuántos archivos hay por cada prefijo
        return self.df['prefijo'].value_counts().reset_index()

    def get_files_by_prefix(self, prefix: str) -> pd.DataFrame:
        """Retorna todos los archivos de un prefijo específico."""
        return self.df[self.df['prefijo'] == prefix]

    # --- NUEVOS MÉTODOS PARA CATEGORÍAS ---

    def get_categories_by_prefix(self, prefix: str) -> pd.DataFrame:
        """Retorna las categorías únicas dentro de un prefijo con su conteo."""
        if self.df.empty:
            return pd.DataFrame(columns=['categoria', 'count'])
        
        prefix_df = self.df[self.df['prefijo'] == prefix]
        if prefix_df.empty:
            return pd.DataFrame(columns=['categoria', 'count'])
            
        # Llenar NaN con 'General' para archivos viejos sin categoría
        prefix_df['categoria'] = prefix_df['categoria'].fillna('General')
        
        return prefix_df['categoria'].value_counts().reset_index()

    def get_files_by_category(self, prefix: str, category: str) -> pd.DataFrame:
        """Retorna archivos filtrados por Prefijo Y Categoría."""
        # Tratamiento de nulos para compatibilidad
        temp_df = self.df.copy()
        temp_df['categoria'] = temp_df['categoria'].fillna('General')
        
        if category == 'TODO':
            return temp_df[temp_df['prefijo'] == prefix]
        
        return temp_df[
            (temp_df['prefijo'] == prefix) & 
            (temp_df['categoria'] == category)
        ]

    def find_file(self, criteria: str, value: str) -> pd.DataFrame:
        """
        Busca archivos. 
        criteria: 'prefijo', 'nombre_original', 'nombre_encriptado'
        """
        if criteria not in self.df.columns or self.df.empty:
            return pd.DataFrame()
        
        # Búsqueda exacta para prefijo o encriptado, parcial para nombre original
        if criteria == 'nombre_original':
            return self.df[self.df[criteria].astype(str).str.contains(value, case=False, na=False)]
        else:
            return self.df[self.df[criteria].astype(str) == value]

    def get_stats(self) -> str:
        """Retorna un resumen de estadísticas."""
        if self.df.empty:
            return "La base de datos está vacía."
        
        total_size = pd.to_numeric(self.df['tamaño_mb'], errors='coerce').sum()
        count = len(self.df)
        return f"Total Archivos: {count} | Tamaño Total: {total_size:.2f} MB"

    # --- PERSISTENCIA Y SEGURIDAD (CON CLAVE CSV) ---

    def save_local(self):
        """Guarda el DataFrame a CSV plano localmente."""
        # MEJORA: utf-8-sig para Excel
        self.df.to_csv(self.csv_path, index=False, encoding='utf-8-sig')
        logger.info(f"💾 Índice guardado localmente: {len(self.df)} registros.")

    def save_encrypted_backup(self, security_manager, prefix="AUTO"):
        """
        Crea un backup encriptado del CSV usando SecurityManager.
        IMPORTANTE: Usa self.csv_password para encriptar este archivo.
        """
        # 1. Asegurar que está guardado en plano primero
        self.save_local()

        # 2. Definir rutas
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"index_backup_{prefix}_{timestamp}.7z"
        backup_path = BACKUP_DIR / "auto" / backup_name
        
        main_encrypted_path = INDEX_DIR / "index_main.7z"

        # 3. Crear Metadatos del Backup
        metadata = {
            "timestamp": timestamp,
            "total_records": len(self.df),
            "type": "CSV_INDEX_BACKUP"
        }

        # 4. Comprimir y Encriptar (Usando SecurityManager + Password CSV)
        success = security_manager.compress_encrypt_7z(
            source_path=self.csv_path,
            dest_path=backup_path,
            metadata=metadata,
            password=self.csv_password # <--- Usa la clave CSV aquí
        )

        if success:
            # 5. Copiar el backup recién creado a index_main.7z (el archivo oficial para la nube)
            shutil.copy2(backup_path, main_encrypted_path)
            logger.info(f"🔐 Backup encriptado (Clave CSV) creado: {backup_name}")
            return main_encrypted_path
        else:
            logger.error("❌ Fallo al encriptar el índice CSV.")
            return None

    def load_from_encrypted(self, security_manager, archive_path: Path, temp_only: bool = False) -> bool:
        """
        Restaura el CSV desde un .7z encriptado.
        Usa la clave CSV para desencriptar.
        MEJORA: 'temp_only=True' carga en memoria sin bloquear el archivo local.
        """
        import uuid
        # Carpeta única para evitar colisiones
        temp_extract = TEMP_DIR / f"csv_restore_{uuid.uuid4().hex[:6]}"
        temp_extract.mkdir(parents=True, exist_ok=True)

        # Usamos clave CSV para desencriptar
        if security_manager.decrypt_extract_7z(archive_path, temp_extract, password=self.csv_password):
            restored_csv = temp_extract / "index_main.csv"
            
            if restored_csv.exists():
                try:
                    loaded_df = pd.read_csv(restored_csv, encoding='utf-8-sig')
                    
                    if temp_only:
                        self.df = loaded_df
                        logger.info("✅ Índice cargado en memoria (Modo Solo Lectura).")
                    else:
                        # Modo restauración: Sobreescribimos
                        time.sleep(0.5) # Pausa de seguridad
                        try:
                            shutil.move(str(restored_csv), str(self.csv_path))
                        except PermissionError:
                            shutil.copy2(str(restored_csv), str(self.csv_path))
                        
                        self.df = loaded_df # Recargar en memoria
                        logger.info("✅ Índice restaurado en disco local.")
                    
                    return True
                except Exception as e:
                    logger.error(f"Error cargando CSV restaurado: {e}")
                    return False
                finally:
                    try: shutil.rmtree(temp_extract, ignore_errors=True)
                    except: pass
        
        try: shutil.rmtree(temp_extract, ignore_errors=True)
        except: pass
        return False

    def compare_local_vs_cloud_backup(self, security_manager, cloud_backup_path: Path) -> str:
        """
        Compara el índice local actual contra un backup descargado de la nube.
        Retorna: 'LOCAL_NEWER', 'CLOUD_NEWER', 'EQUAL', 'ERROR'
        """
        import uuid
        temp_extract = TEMP_DIR / f"compare_{uuid.uuid4().hex[:6]}"
        temp_extract.mkdir(parents=True, exist_ok=True)

        try:
            # Desencriptar en temporal
            if security_manager.decrypt_extract_7z(cloud_backup_path, temp_extract, password=self.csv_password):
                cloud_csv = temp_extract / "index_main.csv"
                if cloud_csv.exists():
                    cloud_df = pd.read_csv(cloud_csv, encoding='utf-8-sig')
                    
                    count_local = len(self.df)
                    count_cloud = len(cloud_df)
                    
                    # Criterio simple: Cantidad de registros
                    if count_local > count_cloud:
                        return 'LOCAL_NEWER'
                    elif count_cloud > count_local:
                        return 'CLOUD_NEWER'
                    else:
                        return 'EQUAL'
            return 'ERROR'
        except Exception as e:
            logger.error(f"Error comparando índices: {e}")
            return 'ERROR'
        finally:
            try: shutil.rmtree(temp_extract, ignore_errors=True)
            except: pass