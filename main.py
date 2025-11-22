# main.py
import sys
import getpass
import time
import os  # Necesario para unlink en safe_delete
import pandas as pd # Necesario para manejo de selecciones
from pathlib import Path
from colorama import init, Fore, Style
from tabulate import tabulate

# Importamos nuestros Managers (Fachadas)
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
        MEJORA: Intenta borrar un archivo con reintentos y espera progresiva.
        Soluciona el [WinError 5] Access is denied (archivo bloqueado por antivirus/sistema).
        """
        if not path.exists(): return
        
        max_retries = 10 # Aumentamos a 10 intentos para seguridad
        for i in range(max_retries):
            try:
                # Espera progresiva: 0.5s, 0.7s, 0.9s...
                time.sleep(0.5 + (i * 0.2)) 
                path.unlink()
                return
            except PermissionError:
                if i == max_retries - 1: # En el último intento, solo avisar
                    self.print_info(f"⚠️ No se pudo borrar temporal inmediatamente: {path.name} (bloqueado). Se limpiará después.")
                continue
            except Exception as e:
                self.print_error(f"Error borrando {path.name}: {e}")
                return

    def _validate_and_sync_key(self, key_type: str, password: str):
        """
        Valida la contraseña contra un archivo testigo en la nube.
        Si no existe, lo crea.
        key_type: 'master' o 'csv'
        """
        witness_name = f"witness_{key_type}.7z"
        local_witness = DATA_DIR / "temp" / witness_name
        
        self.print_info(f"Validando clave {key_type} con la nube...")

        # 1. Intentar bajar el testigo
        if self.cloud.download_file(witness_name, local_witness, silent=True):
            # 2. Si existe, validar
            is_valid = self.security.verify_password_with_witness(local_witness, password)
            self.safe_delete(local_witness)
            
            if is_valid:
                self.print_success(f"Clave {key_type} VERIFICADA correctamente.")
                return True
            else:
                self.print_error(f"CLAVE {key_type.upper()} INCORRECTA. No coincide con la nube.")
                return False
        else:
            # 3. Si no existe, crear y subir (Primera vez)
            self.print_info(f"Creando testigo de seguridad para {key_type}...")
            if self.security.create_password_witness(local_witness, password):
                if self.cloud.upload_file(local_witness, witness_name):
                    self.print_success(f"Testigo {key_type} creado y subido.")
                    self.safe_delete(local_witness)
                    return True
            return False

    # --- INICIALIZACIÓN ---

    def start(self):
        """Arranque de la aplicación."""
        init_directories()
        self.print_header("GESTOR DE ARCHIVOS ENCRIPTADOS v2.5")

        # 1. Autenticación DOBLE con REINTENTO
        try:
            print(f"{Fore.YELLOW}🔐 Paso 1: Autenticación{Style.RESET_ALL}")
            
            # A. Password Maestra (Archivos)
            while True:
                m_pass = getpass.getpass("   🔑 Contraseña MAESTRA (Archivos): ")
                if not m_pass: continue
                m_pass_conf = getpass.getpass("   🔑 Confirme MAESTRA: ")
                if m_pass == m_pass_conf: break
                self.print_error("Las contraseñas no coinciden.")
            
            # B. Password CSV (Índice)
            while True:
                c_pass = getpass.getpass("   🔑 Contraseña CSV (Índice): ")
                if not c_pass: continue
                c_pass_conf = getpass.getpass("   🔑 Confirme CSV: ")
                if c_pass == c_pass_conf: break
                self.print_error("Las contraseñas no coinciden.")

            if m_pass == c_pass:
                print(f"{Fore.RED}⚠️  ADVERTENCIA: Se recomienda usar contraseñas diferentes.{Style.RESET_ALL}")
            
            # Inicializamos Managers
            self.security = SecurityManager(m_pass)
            self.cloud = CloudManager()
            self.inventory = InventoryManager(c_pass) 
            
            # VALIDACIÓN REMOTA (Seguridad Extra)
            if not self._validate_and_sync_key('master', m_pass): sys.exit(1)
            if not self._validate_and_sync_key('csv', c_pass): sys.exit(1)

            self.print_success("Sistemas inicializados y validados.")
            
        except Exception as e:
            self.print_error(f"Error de inicio: {e}")
            sys.exit(1)

        # 2. Bucle Principal
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
        elif opcion == "0": 
            self.print_info("Saliendo...")
            sys.exit(0)
        else:
            self.print_error("Opción inválida.")

    # --- MODOS DE OPERACIÓN ---

    def run_upload_mode(self):
        """
        MODO SUBIDA MEJORADO (Visualización profesional + Lógica Smart)
        """
        self.print_header("MODO SUBIDA")
        
        path_str = input("📁 Carpeta PADRE a procesar: ").strip().replace('"', '')
        source_path = Path(path_str)
        
        if not source_path.exists():
            return self.print_error("La ruta no existe.")

        carpetas_validas = self.cloud.scan_local_folders(source_path)
        if not carpetas_validas:
            return self.print_error("No se encontraron subcarpetas con prefijos válidos.")

        confirm = input(f"¿Procesar {len(carpetas_validas)} carpetas? (s/n): ")
        if confirm.lower() != 's': return

        processed_count = 0
        skipped_count = 0
        total_files = len(carpetas_validas)

        print(f"\n{Fore.CYAN}🚀 Iniciando lote de {total_files} carpetas...{Style.RESET_ALL}")

        for idx, carpeta in enumerate(carpetas_validas, 1):
            try:
                prefijo = carpeta.name.split('_')[0] if '_' in carpeta.name else carpeta.name[:3].upper()
                
                # VALIDACIÓN DE DUPLICADOS
                if self.inventory.check_exists(prefijo, carpeta.name):
                    print(f"{Fore.YELLOW}⚠️  [{idx}/{total_files}] Saltando duplicado: {carpeta.name}{Style.RESET_ALL}")
                    skipped_count += 1
                    continue

                # Preparación de datos
                size_mb = self.security.get_size_mb(carpeta)
                
                # FEEDBACK VISUAL MEJORADO
                print(f"\n{Fore.BLUE}────────────────────────────────────────────────────────────{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}📤 Procesando: {carpeta.name} (Size: {size_mb:.2f} MB) - ({idx} de {total_files}){Style.RESET_ALL}")

                next_global, next_prefix = self.inventory.get_next_ids(prefijo)
                hash_nombre = self.security.generate_filename_hash(carpeta.name)
                nombre_orig_encrypted = self.security.encrypt_text(carpeta.name)
                md5_hash = self.security.calculate_md5(carpeta)
                fecha_fmt = time.strftime("%d-%m-%Y %H:%M:%S")

                metadata_json = {
                    "original_name_token": nombre_orig_encrypted,
                    "hash_filename": hash_nombre,
                    "md5": md5_hash,
                    "processed_date": fecha_fmt
                }

                # B. Compresión (STORE - Rápida)
                print(f"{Fore.CYAN}📦 Encriptando (Modo Store)...{Style.RESET_ALL}")
                start_compress = time.time()
                
                filename_7z = f"{hash_nombre}.7z"
                dest_7z = source_path / filename_7z # Local temporal
                
                success = self.security.compress_encrypt_7z(carpeta, dest_7z, metadata=metadata_json)
                
                if success:
                    comp_time = time.time() - start_compress
                    print(f"{Fore.GREEN}   ✅ Listo ({comp_time:.1f}s).{Style.RESET_ALL}")

                    # C. Registro en Inventario
                    record = {
                        'id_global': next_global, 'id_prefix': next_prefix, 'prefijo': prefijo,
                        'nombre_original': carpeta.name, 'nombre_original_encrypted': nombre_orig_encrypted,
                        'nombre_encriptado': hash_nombre, 'ruta_relativa': f"{prefijo}/",
                        'carpeta_hija': filename_7z, 'tamaño_mb': size_mb,
                        'hash_md5': md5_hash, 'fecha_procesado': fecha_fmt, 'notas': "Auto Upload"
                    }
                    self.inventory.add_record(record)
                    
                    # D. Subida a la Nube (Estructura PLANA + Smart Upload)
                    # Ahora subimos a: PREFIJO/hash.7z directamente
                    cloud_path = f"{prefijo}/{filename_7z}"
                    
                    print(f"{Fore.CYAN}⬆️  Iniciando transferencia...{Style.RESET_ALL}")
                    start_upload = time.time()
                    
                    # CloudManager.upload_file maneja internamente la lógica Smart/BGP
                    if self.cloud.upload_file(dest_7z, cloud_path):
                        upl_time = time.time() - start_upload
                        print(f"{Fore.GREEN}   ✅ Subida finalizada en {upl_time:.1f}s.{Style.RESET_ALL}")
                        
                        # E. Limpieza
                        self.safe_delete(dest_7z)
                        processed_count += 1
                    else:
                        self.print_error(f"Fallo al subir {carpeta.name}")
                
            except Exception as e:
                self.print_error(f"Error procesando {carpeta.name}: {e}")

        # Resumen Final
        print(f"\n{Fore.GREEN}✨ Lote completado.{Style.RESET_ALL}")
        print(f"🏁 Resumen: {processed_count} subidos, {skipped_count} duplicados omitidos.")

        # 4. Actualización de Índice
        if processed_count > 0:
            self.print_info("Sincronizando índice en la nube...")
            encrypted_index_path = self.inventory.save_encrypted_backup(self.security, prefix="UPLOAD")
            
            if encrypted_index_path:
                if self.cloud.upload_file(encrypted_index_path, "index_main.7z"):
                    self.print_success("Índice actualizado correctamente.")
                else:
                    self.print_error("No se pudo subir el índice a la nube.")
            
        print(f"\n✅ Proceso finalizado.")

    def run_download_mode(self):
        """
        MODO DESCARGA EXPLORADOR (Igual funcionalidad)
        """
        self.print_header("MODO DESCARGA EXPLORADOR")
        
        # 1. Intentar sincronizar índice primero
        self.print_info("Sincronizando índice...")
        local_idx_enc = Path("data/temp/index_main_download.7z")
        if self.cloud.download_file("index_main.7z", local_idx_enc, silent=True):
            if self.inventory.load_from_encrypted(self.security, local_idx_enc):
                self.print_success("Índice actualizado.")
            self.safe_delete(local_idx_enc)
        else:
            self.print_info("Usando índice local.")

        # 2. Mostrar Prefijos Disponibles
        summary = self.inventory.get_prefixes_summary()
        if summary.empty: return self.print_error("Índice vacío.")

        print(f"\n{Fore.CYAN}📂 PREFIJOS DISPONIBLES:{Style.RESET_ALL}")
        summary = summary.reset_index(drop=True)
        summary.index = summary.index + 1 
        summary_view = summary.rename(columns={'prefijo': 'Prefijo', 'count': 'Cant. Archivos'})
        print(tabulate(summary_view, headers='keys', tablefmt='simple'))

        # 3. Seleccionar Prefijo
        sel_idx = input("\n👉 Seleccione el NÚMERO (#) del Prefijo (o 0 para Salir): ").strip()
        if not sel_idx.isdigit() or int(sel_idx) == 0: return

        try:
            sel_prefix = summary.iloc[int(sel_idx)-1]['prefijo']
        except IndexError:
            return self.print_error("Número inválido.")

        # 4. Mostrar Archivos
        files_df = self.inventory.get_files_by_prefix(sel_prefix)
        if files_df.empty: return self.print_error("Carpeta vacía.")

        print(f"\n{Fore.CYAN}📄 ARCHIVOS EN '{sel_prefix}':{Style.RESET_ALL}")
        view_df = files_df[['id_global', 'nombre_original', 'nombre_encriptado', 'tamaño_mb']]
        print(tabulate(view_df, headers=['ID', 'Nombre Real', 'Nombre 7z', 'MB'], tablefmt='simple', showindex=False))

        # 5. Selección de Archivos
        selection = input("\n👉 Ingrese IDs a descargar (ej: 3,4,5) o 'TODO': ").strip()
        if not selection: return

        to_download = pd.DataFrame()
        if selection.upper() == 'TODO':
            to_download = files_df
        else:
            try:
                ids = [int(x.strip()) for x in selection.split(',')]
                to_download = files_df[files_df['id_global'].isin(ids)]
            except ValueError:
                return self.print_error("Formato inválido. Use números separados por coma.")

        if to_download.empty: return self.print_error("Ningún archivo seleccionado.")

        # 6. Ejecutar Descarga
        total_items = len(to_download)
        self.print_info(f"Iniciando descarga de {total_items} archivos...")

        for i, (idx, row) in enumerate(to_download.iterrows(), 1):
            nombre_real = row['nombre_original']
            size_mb = row['tamaño_mb']
            
            # Ruta remota PLANA: PREFIJO/hash.7z
            remote_path = f"{row['ruta_relativa']}{row['nombre_encriptado']}.7z"
            local_7z = Path(f"data/descargas/{row['nombre_encriptado']}.7z")
            local_dest_folder = Path(f"data/desencriptados/{nombre_real}")

            print(f"\n{Fore.BLUE}────────────────────────────────────────────────────────────{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}📥 Bajando: {nombre_real} (Size: {size_mb} MB) - ({i} de {total_items}){Style.RESET_ALL}")
            
            start_dl = time.time()
            if self.cloud.download_file(remote_path, local_7z, silent=False):
                duration = time.time() - start_dl
                print(f"{Fore.GREEN}   ✅ Descarga completada en {duration:.1f}s.{Style.RESET_ALL}")

                print(f"{Fore.YELLOW}📦 Desencriptando y descomprimiendo...{Style.RESET_ALL}")
                if self.security.decrypt_extract_7z(local_7z, local_dest_folder):
                    self.print_success(f"Archivo restaurado en: {local_dest_folder}")
                    self.safe_delete(local_7z)
                else:
                    self.print_error("Fallo en descompresión (contraseña incorrecta?).")
            else:
                self.print_error("Fallo en descarga desde la nube.")
        
        print(f"\n{Fore.GREEN}✨ Lote completado.{Style.RESET_ALL}")

    def run_query_mode(self):
        self.print_header("CONSULTA")
        print(self.inventory.get_stats())
        print("\nÚltimos 10 registros:")
        print(tabulate(self.inventory.df.tail(10)[['id_global', 'prefijo', 'nombre_original', 'fecha_procesado']], headers='keys'))
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