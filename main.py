# main.py
import sys
import getpass
import time
import os
import pandas as pd
from pathlib import Path
from colorama import init, Fore, Style
from tabulate import tabulate

# Importamos Managers
from config import init_directories, logger, VALID_PREFIXES, DATA_DIR
from security_manager import SecurityManager
from cloud_manager import CloudManager
from inventory_manager import InventoryManager

# Inicializar colores para la consola
init(autoreset=True)

class AppOrchestrator:
    def __init__(self):
        self.security: SecurityManager = None
        self.cloud: CloudManager = None
        self.inventory: InventoryManager = None

    # --- UI HELPERS ---
    
    def print_header(self, text):
        print(f"\n{Fore.CYAN}{'='*60}")
        print(f"{Style.BRIGHT}{text.center(60)}")
        print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")

    def print_success(self, text):
        print(f"{Fore.GREEN}✅ {text}{Style.RESET_ALL}")

    def print_error(self, text):
        print(f"{Fore.RED}❌ {text}{Style.RESET_ALL}")

    def print_info(self, text):
        print(f"{Fore.YELLOW}ℹ️  {text}{Style.RESET_ALL}")

    # --- UTILIDADES INTERNAS ---

    def safe_delete(self, path: Path):
        """
        Intenta borrar un archivo con reintentos y espera progresiva.
        """
        if not path.exists(): return
        
        max_retries = 10 
        for i in range(max_retries):
            try:
                time.sleep(0.5 + (i * 0.2)) 
                path.unlink()
                return
            except PermissionError:
                if i == max_retries - 1: 
                    self.print_info(f"⚠️ No se pudo borrar temporal inmediatamente: {path.name} (bloqueado). Se limpiará después.")
                continue
            except Exception as e:
                self.print_error(f"Error borrando {path.name}: {e}")
                return

    def _validate_and_sync_key(self, key_type: str, password: str):
        """
        Valida la contraseña contra un archivo testigo en la nube.
        Usa la carpeta remota 'keys/' para mantener orden.
        """
        witness_name = f"witness_{key_type}.7z"
        local_witness = DATA_DIR / "temp" / witness_name
        # Ruta dedicada para keys
        remote_witness_path = f"keys/{witness_name}"
        
        self.print_info(f"Validando clave {key_type} con la nube...")

        if self.cloud.download_file(remote_witness_path, local_witness, silent=True):
            is_valid = self.security.verify_password_with_witness(local_witness, password)
            # No borramos inmediatamente para evitar bloqueo
            
            if is_valid:
                self.print_success(f"Clave {key_type} VERIFICADA.")
                return True
            else:
                self.print_error(f"CLAVE {key_type.upper()} INCORRECTA.")
                return False
        else:
            self.print_info(f"Creando testigo de seguridad para {key_type}...")
            if self.security.create_password_witness(local_witness, password):
                # Subir a la carpeta keys/
                if self.cloud.upload_file(local_witness, remote_witness_path):
                    self.print_success(f"Testigo {key_type} creado en carpeta 'keys/'.")
                    self.safe_delete(local_witness)
                    return True
            return False

    # --- INICIALIZACIÓN ---

    def start(self):
        """Arranque de la aplicación."""
        init_directories()
        self.print_header("GESTOR DE ARCHIVOS ENCRIPTADOS v2.5")

        # 1. Autenticación
        try:
            print(f"{Fore.YELLOW}🔐 Paso 1: Autenticación{Style.RESET_ALL}")
            
            while True:
                m_pass = getpass.getpass("   🔑 Contraseña MAESTRA (Archivos): ")
                if not m_pass: continue
                m_pass_conf = getpass.getpass("   🔑 Confirme MAESTRA: ")
                if m_pass == m_pass_conf: break
                self.print_error("No coinciden.")
            
            while True:
                c_pass = getpass.getpass("   🔑 Contraseña CSV (Índice): ")
                if not c_pass: continue
                c_pass_conf = getpass.getpass("   🔑 Confirme CSV: ")
                if c_pass == c_pass_conf: break
                self.print_error("No coinciden.")

            self.security = SecurityManager(m_pass)
            self.cloud = CloudManager()
            self.inventory = InventoryManager(c_pass) 
            
            if not self._validate_and_sync_key('master', m_pass): sys.exit(1)
            if not self._validate_and_sync_key('csv', c_pass): sys.exit(1)

            # Limpieza de testigos
            self.print_info("Limpiando testigos en 5 segundos...")
            time.sleep(5)
            self.safe_delete(DATA_DIR / "temp" / "witness_master.7z")
            self.safe_delete(DATA_DIR / "temp" / "witness_csv.7z")

            self.print_success("Sistemas inicializados.")
            
            # --- NUEVO: VALIDACIÓN DE ATOMICIDAD (SYNC CHECK) ---
            self.print_info("Verificando integridad del índice con la nube...")
            local_idx_check = DATA_DIR / "temp" / "index_atomic_check.7z"
            
            if self.cloud.download_file("index/index_main.7z", local_idx_check, silent=True):
                status = self.inventory.compare_local_vs_cloud_backup(self.security, local_idx_check)
                self.safe_delete(local_idx_check)
                
                if status == 'LOCAL_NEWER':
                    print(f"{Fore.YELLOW}⚠️  ATENCIÓN: Tu índice LOCAL tiene más datos que la NUBE.{Style.RESET_ALL}")
                    if input("¿Deseas actualizar la nube ahora? (s/n): ").lower() == 's':
                        encrypted = self.inventory.save_encrypted_backup(self.security, prefix="SYNC_FIX")
                        if encrypted and self.cloud.upload_file(encrypted, "index/index_main.7z"):
                            self.print_success("Nube actualizada correctamente.")
                elif status == 'CLOUD_NEWER':
                    print(f"{Fore.YELLOW}⚠️  ATENCIÓN: La NUBE tiene más datos que tu local.{Style.RESET_ALL}")
                    self.print_info("Se recomienda usar la opción '2. Descarga' para sincronizar o revisar.")
                elif status == 'EQUAL':
                    self.print_success("Índices sincronizados.")
            else:
                self.print_info("No existe índice en nube aún (o error de conexión).")

        except Exception as e:
            self.print_error(f"Error de inicio: {e}")
            sys.exit(1)

        while True:
            self.show_menu()

    def show_menu(self):
        print(f"\n{Fore.BLUE}--- MENÚ PRINCIPAL ---{Style.RESET_ALL}")
        print("1. 📤 MODO SUBIDA (Smart Upload + Validado)")
        print("2. 📥 MODO DESCARGA (Explorador Visual)")
        print("3. 🔍 CONSULTAR ÍNDICE")
        print("4. 🔧 MANTENIMIENTO Y ESTADO")
        print("0. 🚪 SALIR")
        
        opcion = input("\n👉 Seleccione opción: ")

        if opcion == "1": self.run_upload_mode()
        elif opcion == "2": self.run_download_mode()
        elif opcion == "3": self.run_query_mode()
        elif opcion == "4": self.run_maintenance_mode()
        elif opcion == "0": sys.exit(0)
        else: self.print_error("Opción inválida.")

    # --- MODOS DE OPERACIÓN ---

    def run_upload_mode(self):
        self.print_header("MODO SUBIDA")
        path_str = input("📁 Carpeta PADRE a procesar: ").strip().replace('"', '')
        source_path = Path(path_str)
        
        if not source_path.exists():
            return self.print_error("La ruta no existe.")

        # Llamada al escáner que ahora soporta categorías
        items_encontrados = self.cloud.scan_local_folders(source_path)
        if not items_encontrados:
            return self.print_error("No se encontraron subcarpetas con prefijos válidos.")

        # items_encontrados es una lista de dicts: {'path', 'prefix', 'category'}
        
        confirm = input(f"¿Procesar {len(items_encontrados)} carpetas? (s/n): ")
        if confirm.lower() != 's': return

        processed_count = 0
        skipped_count = 0
        total_files = len(items_encontrados)

        print(f"\n{Fore.CYAN}🚀 Iniciando lote...{Style.RESET_ALL}")

        for idx, item_data in enumerate(items_encontrados, 1):
            carpeta = item_data['path']
            prefijo = item_data['prefix']
            categoria = item_data['category']
            
            try:
                # VALIDACIÓN DUPLICADOS (Ahora considerando Categoría implícitamente por nombre)
                if self.inventory.check_exists(prefijo, carpeta.name):
                    print(f"{Fore.YELLOW}⚠️  [{idx}/{total_files}] Saltando duplicado: {carpeta.name}{Style.RESET_ALL}")
                    skipped_count += 1
                    continue

                size_mb = self.security.get_size_mb(carpeta)
                print(f"\n{Fore.BLUE}────────────────────────────────────────────────────────────{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}📤 Procesando: {carpeta.name} ({size_mb:.2f} MB) - ({idx}/{total_files}){Style.RESET_ALL}")
                print(f"   📂 Prefijo: {prefijo} | Categoría: {categoria}")

                next_global, next_prefix = self.inventory.get_next_ids(prefijo)
                hash_nombre = self.security.generate_filename_hash(carpeta.name)
                nombre_orig_encrypted = self.security.encrypt_text(carpeta.name)
                md5_hash = self.security.calculate_md5(carpeta)
                fecha_fmt = time.strftime("%d-%m-%Y %H:%M:%S")

                metadata_json = {
                    "original_name_token": nombre_orig_encrypted,
                    "hash_filename": hash_nombre,
                    "md5": md5_hash,
                    "processed_date": fecha_fmt,
                    "category": categoria # Guardamos categoría en metadatos también
                }

                print(f"{Fore.CYAN}📦 Encriptando...{Style.RESET_ALL}")
                filename_7z = f"{hash_nombre}.7z"
                dest_7z = source_path / filename_7z 
                
                if self.security.compress_encrypt_7z(carpeta, dest_7z, metadata=metadata_json):
                    print(f"{Fore.GREEN}   ✅ Encriptado.{Style.RESET_ALL}")

                    # REGISTRO CON CATEGORÍA (Estrategia A: No guardar aun)
                    record = {
                        'id_global': next_global, 'id_prefix': next_prefix, 'prefijo': prefijo,
                        'categoria': categoria, # NUEVO CAMPO
                        'nombre_original': carpeta.name, 'nombre_original_encrypted': nombre_orig_encrypted,
                        'nombre_encriptado': hash_nombre, 'ruta_relativa': f"{prefijo}/",
                        'carpeta_hija': filename_7z, 'tamaño_mb': size_mb,
                        'hash_md5': md5_hash, 'fecha_procesado': fecha_fmt, 'notas': "Auto Upload"
                    }
                    
                    print(f"{Fore.CYAN}⬆️  Subiendo a la nube...{Style.RESET_ALL}")
                    
                    # Subida a carpeta PREFIJO (Plana en la nube)
                    if self.cloud.upload_file(dest_7z, prefijo):
                        print(f"{Fore.GREEN}   ✅ Subida OK.{Style.RESET_ALL}")
                        
                        # SUBIDA OK -> REGISTRAMOS
                        self.inventory.add_record(record)
                        self.inventory.save_local()
                        processed_count += 1
                    else:
                        self.print_error("Fallo subida. No se registrará en índice.")
                        self.safe_delete(dest_7z)
                
            except Exception as e:
                self.print_error(f"Error procesando {carpeta.name}: {e}")

        print(f"\n{Fore.GREEN}✨ Lote completado.{Style.RESET_ALL}")
        print(f"🏁 Resumen: {processed_count} subidos, {skipped_count} duplicados omitidos.")

        if processed_count > 0:
            self.print_info("Sincronizando índice en la nube...")
            encrypted_index_path = self.inventory.save_encrypted_backup(self.security, prefix="UPLOAD")
            if encrypted_index_path:
                # Subir índice a carpeta 'index/'
                if self.cloud.upload_file(encrypted_index_path, "index/index_main.7z"):
                    self.print_success("Índice actualizado en 'index/'.")
                else:
                    self.print_error("No se pudo subir índice.")
            
        print(f"\n✅ Proceso finalizado.")

    def run_download_mode(self):
        self.print_header("MODO DESCARGA EXPLORADOR")
        
        self.print_info("Sincronizando índice...")
        local_idx_enc = Path("data/temp/index_main_download.7z")
        
        # Descargar desde 'index/'
        if self.cloud.download_file("index/index_main.7z", local_idx_enc, silent=True):
            if self.inventory.load_from_encrypted(self.security, local_idx_enc, temp_only=True):
                self.print_success("Índice actualizado.")
        else:
            self.print_info("Usando índice local.")

        # 1. MENU PREFIJOS
        summary = self.inventory.get_prefixes_summary()
        if summary.empty: 
            self.print_error("Índice vacío.")
            self.safe_delete(local_idx_enc)
            return

        print(f"\n{Fore.CYAN}📂 PREFIJOS DISPONIBLES:{Style.RESET_ALL}")
        summary = summary.reset_index(drop=True)
        summary.index = summary.index + 1 
        summary_view = summary.rename(columns={'prefijo': 'Prefijo', 'count': 'Cant. Archivos'})
        print(tabulate(summary_view, headers='keys', tablefmt='simple'))

        sel_idx = input("\n👉 Seleccione el NÚMERO (#) del Prefijo (o 0 para Salir): ").strip()
        
        if not sel_idx.isdigit() or int(sel_idx) == 0: 
            self.safe_delete(local_idx_enc)
            return

        try:
            sel_prefix = summary.iloc[int(sel_idx)-1]['prefijo']
        except IndexError:
            self.print_error("Número inválido.")
            self.safe_delete(local_idx_enc)
            return

        # 2. MENU CATEGORÍAS (NUEVO)
        categories = self.inventory.get_categories_by_prefix(sel_prefix)
        
        sel_category = 'TODO' # Por defecto
        if not categories.empty:
            print(f"\n{Fore.CYAN}📂 SUB-CATEGORÍAS EN '{sel_prefix}':{Style.RESET_ALL}")
            categories = categories.reset_index(drop=True)
            categories.index = categories.index + 1
            cat_view = categories.rename(columns={'categoria': 'Subfijo', 'count': 'Cant.'})
            print(tabulate(cat_view, headers='keys', tablefmt='simple'))
            
            sel_cat_idx = input("\n👉 Seleccione el NÚMERO (#) del Subfijo (o 0 para Todo): ").strip()
            
            if sel_cat_idx.isdigit() and int(sel_cat_idx) > 0:
                try:
                    sel_category = categories.iloc[int(sel_cat_idx)-1]['categoria']
                except IndexError:
                    self.print_error("Número inválido, mostrando todo.")

        # 3. LISTADO ARCHIVOS
        files_df = self.inventory.get_files_by_category(sel_prefix, sel_category)
        if files_df.empty: 
            self.print_error("Carpeta vacía.")
            self.safe_delete(local_idx_enc)
            return

        print(f"\n{Fore.CYAN}📄 ARCHIVOS EN '{sel_prefix}' > '{sel_category}':{Style.RESET_ALL}")
        # Mostrar id_prefix como ID
        view_df = files_df[['id_prefix', 'nombre_original', 'nombre_encriptado', 'tamaño_mb']].rename(columns={'id_prefix': 'ID'})
        print(tabulate(view_df, headers=['ID', 'Nombre Real', 'Nombre 7z', 'MB'], tablefmt='simple', showindex=False))

        selection = input("\n👉 Ingrese IDs a descargar (ej: 3,4,5) o 'TODO' (0 Cancelar): ").strip()
        
        if selection == '0':
            self.safe_delete(local_idx_enc)
            return

        to_download = pd.DataFrame()
        if selection.upper() == 'TODO':
            to_download = files_df
        else:
            try:
                ids = [int(x.strip()) for x in selection.split(',')]
                to_download = files_df[files_df['id_prefix'].isin(ids)]
            except ValueError:
                self.print_error("Formato inválido.")
                self.safe_delete(local_idx_enc)
                return

        if to_download.empty: 
            self.print_error("Ningún archivo seleccionado.")
            self.safe_delete(local_idx_enc)
            return

        total_items = len(to_download)
        self.print_info(f"Iniciando descarga de {total_items} archivos...")

        for i, (idx, row) in enumerate(to_download.iterrows(), 1):
            nombre_real = row['nombre_original']
            cat_archivo = row['categoria']
            size_mb = row['tamaño_mb']
            
            remote_path = f"{row['ruta_relativa']}{row['nombre_encriptado']}.7z"
            local_7z = Path(f"data/descargas/{row['nombre_encriptado']}.7z")
            
            # MEJORA: Destino organizado por Categoría
            # data/desencriptados/Categoria/NombreReal
            local_dest_folder = Path(f"data/desencriptados/{cat_archivo}/{nombre_real}")

            print(f"\n{Fore.BLUE}────────────────────────────────────────────────────────────{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}📥 Bajando: {nombre_real} (Size: {size_mb} MB) - ({i} de {total_items}){Style.RESET_ALL}")
            
            if self.cloud.download_file(remote_path, local_7z, silent=False):
                print(f"{Fore.YELLOW}📦 Desencriptando y descomprimiendo...{Style.RESET_ALL}")
                # security_manager maneja el aplanado
                if self.security.decrypt_extract_7z(local_7z, local_dest_folder):
                    print(f"{Fore.GREEN}   ✅ Restaurado en: {local_dest_folder}{Style.RESET_ALL}")
                    self.safe_delete(local_7z)
                else:
                    self.print_error("Fallo en descompresión.")
            else:
                self.print_error("Fallo en descarga desde la nube.")
        
        self.safe_delete(local_idx_enc) 
        print(f"\n{Fore.GREEN}✨ Lote completado.{Style.RESET_ALL}")

    def run_query_mode(self):
        self.print_header("CONSULTA")
        print(self.inventory.get_stats())
        print("\nÚltimos 10 registros:")
        print(tabulate(self.inventory.df.tail(10)[['id_global', 'prefijo', 'categoria', 'nombre_original']], headers='keys'))
        input("\nPresione Enter para volver...")

    def run_maintenance_mode(self):
        self.print_header("MANTENIMIENTO")
        print("1. Verificar conexión a Nube")
        print("2. Limpiar temporales")
        op = input("Opción: ")
        if op == "1":
            if self.cloud.check_connection(): self.print_success("Conexión Rclone OK")
            else: self.print_error("Fallo conexión Rclone")
        elif op == "2":
            self.cloud.clean_temp()
            self.print_success("Temporales limpios.")

if __name__ == "__main__":
    app = AppOrchestrator()
    app.start()