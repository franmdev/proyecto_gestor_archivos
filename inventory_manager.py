# inventory_manager.py
import pandas as pd
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Configuración
from config import logger, CSV_COLUMNS, INDEX_DIR, BACKUP_DIR

class InventoryManager:
    """
    FACHADA DE DATOS
    Responsabilidad: Gestionar el índice (CSV/Pandas), búsquedas y persistencia.
    """

    def __init__(self):
        self.csv_path = INDEX_DIR / "index_main.csv"
        self.df = self._load_or_create_db()

    def _load_or_create_db(self) -> pd.DataFrame:
        """Carga el CSV local o crea uno vacío si no existe."""
        if self.csv_path.exists():
            try:
                df = pd.read_csv(self.csv_path)
                # Validar columnas mínimas
                missing = [col for col in CSV_COLUMNS if col not in df.columns]
                if missing:
                    logger.warning(f"⚠️ CSV corrupto o antiguo. Faltan columnas: {missing}. Se recrearán.")
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

    def add_record(self, record: Dict):
        """Añade un registro al DataFrame en memoria (no guarda a disco aún)."""
        new_row = pd.DataFrame([record])
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

    def find_file(self, criteria: str, value: str) -> pd.DataFrame:
        """
        Busca archivos. 
        criteria: 'prefijo', 'nombre_original', 'nombre_encriptado'
        """
        if criteria not in self.df.columns:
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

    # --- PERSISTENCIA Y SEGURIDAD ---

    def save_local(self):
        """Guarda el DataFrame a CSV plano localmente."""
        self.df.to_csv(self.csv_path, index=False)
        logger.info(f"💾 Índice guardado localmente: {len(self.df)} registros.")

    def save_encrypted_backup(self, security_manager, prefix="AUTO"):
        """
        Crea un backup encriptado del CSV usando SecurityManager.
        Guarda en data/backups y sobreescribe data/index/index_main.7z (para subir).
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

        # 4. Comprimir y Encriptar (Usando SecurityManager)
        success = security_manager.compress_encrypt_7z(
            source_path=self.csv_path,
            dest_path=backup_path,
            metadata=metadata
        )

        if success:
            # 5. Copiar el backup recién creado a index_main.7z (el archivo oficial para la nube)
            shutil.copy2(backup_path, main_encrypted_path)
            logger.info(f"🔐 Backup encriptado creado: {backup_name}")
            return main_encrypted_path
        else:
            logger.error("❌ Fallo al encriptar el índice CSV.")
            return None

    def load_from_encrypted(self, security_manager, archive_path: Path) -> bool:
        """
        Restaura el CSV desde un .7z encriptado.
        Útil para sincronización inicial o recuperación.
        """
        temp_extract = Path("data/temp/csv_restore")
        temp_extract.mkdir(parents=True, exist_ok=True)

        if security_manager.decrypt_extract_7z(archive_path, temp_extract):
            restored_csv = temp_extract / "index_main.csv"
            if restored_csv.exists():
                # Reemplazar actual
                shutil.move(str(restored_csv), str(self.csv_path))
                self.df = self._load_or_create_db() # Recargar en memoria
                logger.info("✅ Índice restaurado desde backup encriptado.")
                shutil.rmtree(temp_extract)
                return True
        
        return False