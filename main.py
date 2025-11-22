# main.py
import sys
import getpass
import time
from pathlib import Path
from colorama import init, Fore, Style
from tabulate import tabulate

# Importamos nuestros Managers (Fachadas)
from config import init_directories, logger, VALID_PREFIXES
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

    # --- INICIALIZACIÓN ---

    def start(self):
        """Arranque de la aplicación."""
        init_directories()
        self.print_header("GESTOR DE ARCHIVOS ENCRIPTADOS v2.0 (Facade)")

        # 1. Autenticación
        try:
            master_pass = getpass.getpass(f"{Fore.YELLOW}🔐 Ingrese Contraseña MAESTRA (para archivos): {Style.RESET_ALL}")
            if not master_pass: raise ValueError("La contraseña no puede estar vacía.")
            
            # Inicializamos los Managers
            self.security = SecurityManager(master_pass)
            self.cloud = CloudManager()
            self.inventory = InventoryManager()
            
            self.print_success("Sistemas inicializados correctamente.")
            
        except Exception as e:
            self.print_error(f"Error de inicio: {e}")
            sys.exit(1)

        # 2. Bucle Principal
        while True:
            self.show_menu()

    def show_menu(self):
        print(f"\n{Fore.BLUE}--- MENÚ PRINCIPAL ---{Style.RESET_ALL}")
        print("1. 📤 MODO SUBIDA (Encriptar + Subir)")
        print("2. 📥 MODO DESCARGA (Bajar + Desencriptar)")
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
        self.print_header("MODO SUBIDA")
        
        # 1. Pedir carpeta origen
        path_str = input("📁 Arrastre la carpeta PADRE a procesar: ").strip().replace('"', '')
        source_path = Path(path_str)
        
        if not source_path.exists():
            return self.print_error("La ruta no existe.")

        # 2. Cloud Manager escanea carpetas válidas (DOC, FIN, etc)
        carpetas_validas = self.cloud.scan_local_folders(source_path)
        if not carpetas_validas:
            return self.print_error("No se encontraron subcarpetas con prefijos válidos.")

        confirm = input(f"¿Procesar {len(carpetas_validas)} carpetas? (s/n): ")
        if confirm.lower() != 's': return

        processed_count = 0

        # 3. Procesamiento (Bucle Principal)
        for carpeta in carpetas_validas:
            try:
                prefijo = carpeta.name.split('_')[0] if '_' in carpeta.name else carpeta.name[:3].upper()
                if prefijo not in self.inventory.df['prefijo'].unique():
                     # Fallback simple si el nombre es solo "DOC"
                     pass

                self.print_info(f"Procesando: {carpeta.name}...")

                # A. Generar IDs y Nombres Seguros
                next_global, next_prefix = self.inventory.get_next_ids(prefijo)
                
                # Generamos hash determinista para el nombre del archivo .7z
                hash_nombre = self.security.generate_filename_hash(carpeta.name)
                
                # Encriptamos el nombre original para guardarlo en metadatos
                nombre_orig_encrypted = self.security.encrypt_text(carpeta.name)
                
                # Calculamos MD5 y Tamaño antes de comprimir
                md5_hash = self.security.calculate_md5(carpeta)
                size_mb = self.security.get_size_mb(carpeta)

                # B. Preparar Metadatos para inyectar en el 7z
                metadata_json = {
                    "original_name_token": nombre_orig_encrypted,
                    "hash_filename": hash_nombre,
                    "md5": md5_hash,
                    "processed_date": time.strftime("%Y-%m-%d %H:%M:%S")
                }

                # C. Comprimir y Encriptar (Security Manager)
                dest_7z = source_path / f"{hash_nombre}.7z"
                success = self.security.compress_encrypt_7z(carpeta, dest_7z, metadata=metadata_json)

                if success:
                    # D. Registrar en Inventario (Inventory Manager)
                    record = {
                        'id_global': next_global,
                        'id_prefix': next_prefix,
                        'prefijo': prefijo,
                        'nombre_original': carpeta.name,
                        'nombre_original_encrypted': nombre_orig_encrypted,
                        'nombre_encriptado': hash_nombre,
                        'ruta_relativa': f"{prefijo}/",
                        'carpeta_hija': f"{hash_nombre}.7z",
                        'tamaño_mb': size_mb,
                        'hash_md5': md5_hash,
                        'fecha_procesado': time.strftime("%Y-%m-%dT%H:%M:%S"),
                        'notas': "Subida Automática"
                    }
                    self.inventory.add_record(record)
                    
                    # E. Subir a la Nube (Cloud Manager)
                    # Subimos el .7z a la carpeta del prefijo correspondiente en la nube
                    cloud_path = f"{prefijo}/{hash_nombre}.7z"
                    if self.cloud.upload_file(dest_7z, cloud_path):
                        self.print_success(f"Subido: {carpeta.name} -> {cloud_path}")
                        processed_count += 1
                        # Opcional: Borrar el .7z local después de subir
                        # dest_7z.unlink() 
                    else:
                        self.print_error(f"Fallo al subir {carpeta.name}")
                
            except Exception as e:
                self.print_error(f"Error procesando {carpeta.name}: {e}")

        # 4. Finalización: Guardar y Subir Índice
        if processed_count > 0:
            self.print_info("Guardando índice encriptado...")
            encrypted_index_path = self.inventory.save_encrypted_backup(self.security, prefix="UPLOAD")
            
            if encrypted_index_path:
                if self.cloud.upload_file(encrypted_index_path, "index_main.7z"):
                    self.print_success("Índice sincronizado con la nube.")
                else:
                    self.print_error("No se pudo subir el índice a la nube.")
            
        print(f"\n✅ Proceso finalizado. {processed_count} carpetas procesadas.")

    def run_download_mode(self):
        self.print_header("MODO DESCARGA")
        
        # 1. Intentar sincronizar índice primero
        self.print_info("Intentando descargar índice más reciente...")
        local_idx_enc = Path("data/temp/index_main_download.7z")
        if self.cloud.download_file("index_main.7z", local_idx_enc):
            if self.inventory.load_from_encrypted(self.security, local_idx_enc):
                self.print_success("Índice actualizado.")
            local_idx_enc.unlink(missing_ok=True)
        else:
            self.print_info("No se pudo descargar índice remoto. Usando local.")

        # 2. Buscar archivo
        criterio = input("Buscar por (1) Nombre Original (2) Prefijo: ")
        termino = input("Término de búsqueda: ")
        
        columna = 'nombre_original' if criterio == '1' else 'prefijo'
        resultados = self.inventory.find_file(columna, termino)
        
        if resultados.empty:
            return self.print_error("No se encontraron resultados.")

        # Mostrar tabla
        print(tabulate(resultados[['id_global', 'prefijo', 'nombre_original', 'tamaño_mb']], headers='keys', tablefmt='simple'))
        
        ids = input("\nIngrese ID_GLOBAL a descargar (o 'todas' para descargar la lista): ")
        
        # 3. Descargar
        files_to_download = resultados if ids == 'todas' else results = resultados[resultados['id_global'].astype(str) == ids.strip()]
        
        if files_to_download.empty: return

        for _, row in files_to_download.iterrows():
            remote_path = f"{row['ruta_relativa']}{row['nombre_encriptado']}.7z"
            local_7z = Path(f"data/descargas/{row['nombre_encriptado']}.7z")
            local_dest_folder = Path(f"data/desencriptados/{row['nombre_original']}")

            self.print_info(f"Bajando {row['nombre_original']}...")
            
            if self.cloud.download_file(remote_path, local_7z):
                self.print_info("Desencriptando y descomprimiendo...")
                if self.security.decrypt_extract_7z(local_7z, local_dest_folder):
                    self.print_success(f"Archivo listo en: {local_dest_folder}")
                    # Validar MD5 post-descarga (Opcional pero recomendado)
                    # current_md5 = self.security.calculate_md5(local_dest_folder)
                    # if current_md5 == row['hash_md5']: print("Integridad OK")
                else:
                    self.print_error("Fallo en descompresión (contraseña incorrecta?).")
            else:
                self.print_error("Fallo en descarga.")

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