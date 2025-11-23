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
    """

    def __init__(self, csv_password: str):
        self.csv_path = INDEX_DIR / "index_main.csv"
        self.csv_password = csv_password
        self.df = self._load_or_create_db()

    def _load_or_create_db(self) -> pd.DataFrame:
        """Carga el CSV local o crea uno vacío si no existe."""
        if self.csv_path.exists():
            try:
                df = pd.read_csv(self.csv_path, encoding='utf-8-sig')
                missing = [col for col in CSV_COLUMNS if col not in df.columns]
                if missing:
                    logger.warning(f"⚠️ CSV antiguo. Faltan: {missing}. Se recrearán.")
                    return self._create_empty_db()
                return df
            except Exception as e:
                logger.error(f"Error leyendo CSV: {e}. Creando nuevo.")
                return self._create_empty_db()
        else:
            return self._create_empty_db()

    def _create_empty_db(self) -> pd.DataFrame:
        return pd.DataFrame(columns=CSV_COLUMNS)

    # --- GESTIÓN DE REGISTROS ---

    def check_exists(self, prefijo: str, nombre_original: str) -> bool:
        if self.df.empty: return False
        exists = not self.df[
            (self.df['prefijo'] == prefijo) & 
            (self.df['nombre_original'] == nombre_original)
        ].empty
        return exists

    def add_record(self, record: Dict):
        new_row = pd.DataFrame([record])
        new_row = new_row.dropna(how='all', axis=1)
        if self.df.empty:
            self.df = new_row
        else:
            self.df = pd.concat([self.df, new_row], ignore_index=True)

    def get_next_ids(self, prefix: str) -> tuple[int, int]:
        if self.df.empty:
            next_global = 1
        else:
            next_global = pd.to_numeric(self.df['id_global'], errors='coerce').max()
            next_global = 1 if pd.isna(next_global) else int(next_global) + 1

        prefix_df = self.df[self.df['prefijo'] == prefix]
        if prefix_df.empty:
            next_prefix = 1
        else:
            next_prefix = pd.to_numeric(prefix_df['id_prefix'], errors='coerce').max()
            next_prefix = 1 if pd.isna(next_prefix) else int(next_prefix) + 1

        return next_global, next_prefix

    # --- CONSULTAS ---

    def get_prefixes_summary(self) -> pd.DataFrame:
        if self.df.empty: return pd.DataFrame(columns=['prefijo', 'count'])
        return self.df['prefijo'].value_counts().reset_index()

    def get_files_by_prefix(self, prefix: str) -> pd.DataFrame:
        return self.df[self.df['prefijo'] == prefix]

    def find_file(self, criteria: str, value: str) -> pd.DataFrame:
        if criteria not in self.df.columns or self.df.empty: return pd.DataFrame()
        if criteria == 'nombre_original':
            return self.df[self.df[criteria].astype(str).str.contains(value, case=False, na=False)]
        else:
            return self.df[self.df[criteria].astype(str) == value]

    def get_stats(self) -> str:
        if self.df.empty: return "Base de datos vacía."
        total_size = pd.to_numeric(self.df['tamaño_mb'], errors='coerce').sum()
        count = len(self.df)
        return f"Total Archivos: {count} | Tamaño Total: {total_size:.2f} MB"

    # --- PERSISTENCIA Y SEGURIDAD ---

    def save_local(self):
        self.df.to_csv(self.csv_path, index=False, encoding='utf-8-sig')
        logger.info(f"💾 Índice guardado localmente: {len(self.df)} registros.")

    def save_encrypted_backup(self, security_manager, prefix="AUTO"):
        self.save_local()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"index_backup_{prefix}_{timestamp}.7z"
        backup_path = BACKUP_DIR / "auto" / backup_name
        
        main_encrypted_path = INDEX_DIR / "index_main.7z"

        metadata = {
            "timestamp": timestamp,
            "total_records": len(self.df),
            "type": "CSV_INDEX_BACKUP"
        }

        success = security_manager.compress_encrypt_7z(
            source_path=self.csv_path,
            dest_path=backup_path,
            metadata=metadata,
            password=self.csv_password
        )

        if success:
            shutil.copy2(backup_path, main_encrypted_path)
            logger.info(f"🔐 Backup encriptado creado: {backup_name}")
            return main_encrypted_path
        else:
            logger.error("❌ Fallo al encriptar índice.")
            return None

    def load_from_encrypted(self, security_manager, archive_path: Path, temp_only: bool = False) -> bool:
        """
        Restaura el CSV desde un .7z encriptado.
        MEJORA: 'temp_only=True' carga el CSV en memoria pero NO lo guarda 
        en la ruta permanente local, evitando bloqueos de archivo abierto.
        """
        import uuid
        temp_extract = TEMP_DIR / f"csv_restore_{uuid.uuid4().hex[:6]}"
        temp_extract.mkdir(parents=True, exist_ok=True)

        if security_manager.decrypt_extract_7z(archive_path, temp_extract, password=self.csv_password):
            restored_csv = temp_extract / "index_main.csv"
            
            if restored_csv.exists():
                try:
                    loaded_df = pd.read_csv(restored_csv, encoding='utf-8-sig')
                    
                    if temp_only:
                        self.df = loaded_df
                        logger.info("✅ Índice cargado en memoria (Modo Solo Lectura).")
                    else:
                        time.sleep(0.5)
                        try:
                            shutil.move(str(restored_csv), str(self.csv_path))
                        except PermissionError:
                            shutil.copy2(str(restored_csv), str(self.csv_path))
                        
                        self.df = loaded_df
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