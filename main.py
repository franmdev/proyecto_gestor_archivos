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

    # --- UTILIDADES INTERNAS ---

    def safe_delete(self, path: Path):
        """
        MEJORA: Intenta borrar un archivo con reintentos y espera.
        Soluciona el [WinError 5] Access is denied.
        """
        if not path.exists(): return
        
        for i in range(3): # 3 intentos
            try:
                time.sleep(0.5) # Esperar a que el sistema libere el archivo
                path.unlink()
                return
            except PermissionError:
                if i == 2: # En el último intento, solo avisar
                    self.print_info(f"No se pudo borrar temporal inmediatamente: {path.name} (bloqueado)")
                continue
            except Exception as e:
                self.print_error(f"Error borrando {path.name}: {e}")
                return

    # --- INICIALIZACIÓN ---

    def start(self):
        """Arranque de la aplicación."""
        init_directories()
        self.print_header("GESTOR DE ARCHIVOS ENCRIPTADOS v2.2")

        # 1. Autenticación DOBLE
        try:
            print(f"{Fore.YELLOW}🔐 Paso 1: Autenticación{Style.RESET_ALL}")
            
            # A. Password Maestra (Archivos)
            master_pass = getpass.getpass("   🔑 Ingrese Contraseña MAESTRA (para archivos): ")
            if not master_pass: raise ValueError("La contraseña maestra no puede estar vacía.")
            
            # B. Password CSV (Índice)
            csv_pass = getpass.getpass("   🔑 Ingrese Contraseña CSV (para índice): ")
            if not csv_pass: raise ValueError("La contraseña CSV no puede estar vacía.")

            if master_pass == csv_pass:
                print(f"{Fore.RED}⚠️  ADVERTENCIA: Se recomienda usar contraseñas diferentes.{Style.RESET_ALL}")
            
            # Inicializamos los Managers
            self.security = SecurityManager(master_pass)
            self.cloud = CloudManager()
            self.inventory = InventoryManager(csv_pass) # Pasamos la clave CSV aquí
            
            self.print_success("Sistemas inicializados correctamente.")
            
        except Exception as e:
            self.print_error(f"Error de inicio: {e}")
            sys.exit(1)

        # 2. Bucle Principal
        while True:
            self.show_menu()

    def show_menu(self):
        print(f"\n{Fore.BLUE}--- MENÚ PRINCIPAL ---{Style.RESET_ALL}")
        print("1. 📤 MODO SUBIDA (Detecta Duplicados)")
        print("2. 📥 MODO DESCARGA (Explorador Prefijos)")
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
        skipped_count = 0

        # 3. Procesamiento (Bucle Principal)
        for carpeta in carpetas_validas:
            try:
                prefijo = carpeta.name.split('_')[0] if '_' in carpeta.name else carpeta.name[:3].upper()
                if prefijo not in self.inventory.df['prefijo'].unique():
                     pass

                # MEJORA: VALIDACIÓN DE DUPLICADOS
                if self.inventory.check_exists(prefijo, carpeta.name):
                    print(f"{Fore.YELLOW}⚠️  Saltando duplicado: {prefijo}/{carpeta.name} ya existe en el índice.{Style.RESET_ALL}")
                    skipped_count += 1
                    continue

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

                # MEJORA: Fecha formato dd-mm-yyyy hh:mm:ss
                fecha_fmt = time.strftime("%d-%m-%Y %H:%M:%S")

                # B. Preparar Metadatos para inyectar en el 7z
                metadata_json = {
                    "original_name_token": nombre_orig_encrypted,
                    "hash_filename": hash_nombre,
                    "md5": md5_hash,
                    "processed_date": fecha_fmt
                }

                # C. Comprimir y Encriptar (Security Manager - Usa Password Maestra)
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
                        'fecha_procesado': fecha_fmt,
                        'notas': "Subida Automática"
                    }
                    self.inventory.add_record(record)
                    
                    # E. Subir a la Nube (Cloud Manager)
                    cloud_path = f"{prefijo}/{hash_nombre}.7z"
                    if self.cloud.upload_file(dest_7z, cloud_path):
                        self.print_success(f"Subido: {carpeta.name} -> {cloud_path}")
                        
                        # F. LIMPIEZA AUTOMÁTICA MEJORADA (Usa safe_delete)
                        self.safe_delete(dest_7z)
                        self.print_info("🧹 Archivo comprimido local eliminado.")
                            
                        processed_count += 1
                    else:
                        self.print_error(f"Fallo al subir {carpeta.name}")
                
            except Exception as e:
                self.print_error(f"Error procesando {carpeta.name}: {e}")

        # Resumen
        print(f"\n🏁 Resumen: {processed_count} procesados, {skipped_count} duplicados omitidos.")

        # 4. Finalización: Guardar y Subir Índice (Usando Password CSV)
        if processed_count > 0:
            self.print_info("Guardando índice encriptado (Usando Clave CSV)...")
            encrypted_index_path = self.inventory.save_encrypted_backup(self.security, prefix="UPLOAD")
            
            if encrypted_index_path:
                if self.cloud.upload_file(encrypted_index_path, "index_main.7z"):
                    self.print_success("Índice sincronizado con la nube.")
                else:
                    self.print_error("No se pudo subir el índice a la nube.")
            
        print(f"\n✅ Proceso finalizado.")

    def run_download_mode(self):
        """
        MEJORA: Nuevo flujo jerárquico de descarga.
        1. Sincronizar índice.
        2. Mostrar Prefijos.
        3. Mostrar Archivos.
        4. Seleccionar IDs (ej: 3,4,5).
        """
        self.print_header("MODO DESCARGA EXPLORADOR")
        
        # 1. Intentar sincronizar índice primero
        self.print_info("Sincronizando índice...")
        local_idx_enc = Path("data/temp/index_main_download.7z")
        if self.cloud.download_file("index_main.7z", local_idx_enc):
            # Desencriptar índice con Clave CSV
            if self.inventory.load_from_encrypted(self.security, local_idx_enc):
                self.print_success("Índice actualizado.")
            self.safe_delete(local_idx_enc) # MEJORA: Borrado seguro
        else:
            self.print_info("No se pudo descargar índice remoto. Usando local.")

        # 2. Mostrar Prefijos Disponibles
        summary = self.inventory.get_prefixes_summary()
        if summary.empty: return self.print_error("Índice vacío.")

        print(f"\n{Fore.CYAN}📂 PREFIJOS DISPONIBLES:{Style.RESET_ALL}")
        # Ajuste visual de columnas para tabulate
        summary.columns = ['Prefijo', 'Cant. Archivos']
        print(tabulate(summary, headers='keys', tablefmt='simple', showindex=False))

        # 3. Seleccionar Prefijo
        sel_prefix = input("\n👉 Escriba el Prefijo a explorar (o 'SALIR'): ").upper().strip()
        if sel_prefix == 'SALIR' or not sel_prefix: return

        # 4. Mostrar Archivos del Prefijo
        files_df = self.inventory.get_files_by_prefix(sel_prefix)
        if files_df.empty: return self.print_error("Prefijo no existe o está vacío.")

        print(f"\n{Fore.CYAN}📄 ARCHIVOS EN '{sel_prefix}':{Style.RESET_ALL}")
        # Mostramos ID, Nombre y Nombre 7z como pediste
        view_df = files_df[['id_global', 'nombre_original', 'nombre_encriptado', 'tamaño_mb']]
        print(tabulate(view_df, headers=['ID', 'Nombre Real', 'Nombre 7z', 'MB'], tablefmt='simple', showindex=False))

        # 5. Selección de Archivos (Múltiple 3,4,5)
        selection = input("\n👉 Ingrese IDs a descargar (ej: 3,4,5) o 'TODO': ").strip()
        if not selection: return

        to_download = pd.DataFrame()
        if selection.upper() == 'TODO':
            to_download = files_df
        else:
            # Parsear lista de IDs
            try:
                ids = [int(x.strip()) for x in selection.split(',')]
                # Filtrar DataFrame por los IDs seleccionados
                to_download = files_df[files_df['id_global'].isin(ids)]
            except ValueError:
                return self.print_error("Formato inválido. Use números separados por coma (ej: 1,3,5).")

        if to_download.empty: return self.print_error("Ningún archivo seleccionado o IDs no encontrados.")

        # 6. Ejecutar Descarga
        self.print_info(f"Iniciando descarga de {len(to_download)} archivos...")

        for _, row in to_download.iterrows():
            remote_path = f"{row['ruta_relativa']}{row['nombre_encriptado']}.7z"
            local_7z = Path(f"data/descargas/{row['nombre_encriptado']}.7z")
            local_dest_folder = Path(f"data/desencriptados/{row['nombre_original']}")

            self.print_info(f"⬇️ Bajando: {row['nombre_original']}...")
            
            if self.cloud.download_file(remote_path, local_7z):
                self.print_info("Desencriptando y descomprimiendo...")
                
                # Desencriptar contenido con Password Maestra
                if self.security.decrypt_extract_7z(local_7z, local_dest_folder):
                    self.print_success(f"Archivo listo en: {local_dest_folder}")
                    
                    # Limpieza automática del .7z descargado (Segura)
                    self.safe_delete(local_7z)
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