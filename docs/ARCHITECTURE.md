# 🏗️ Arquitectura del Sistema

## Patrón de Diseño: Facade (Fachada)

El sistema utiliza una arquitectura modular basada en el patrón **Facade**. `main.py` actúa como un orquestador (Cliente) que coordina subsistemas complejos, manteniendo el código limpio y desacoplado.

### Módulos Principales

1.  **`SecurityManager` (Criptografía & Compresión):**
    * Abstrae el uso de `7-Zip` via `subprocess`.
    * Maneja la derivación de claves (PBKDF2HMAC) y encriptación de metadatos (Fernet).
    * Implementa la lógica de "aplanado" de directorios al descomprimir.

2.  **`CloudManager` (Infraestructura & Red):**
    * Wrapper inteligente sobre `Rclone`.
    * Implementa la lógica de **Smart Upload** y parsers de salida (TQDM).
    * Decide dinámicamente entre `copy` (carpetas) y `copyto` (archivos exactos).

3.  **`InventoryManager` (Datos & Persistencia):**
    * Gestiona el estado del sistema usando `Pandas`.
    * Asegura la integridad referencial (evita duplicados).
    * Maneja la concurrencia de lectura/escritura del CSV local.

---

## 🔄 Flujo de Datos: Subida (Upload Pipeline)

1.  **Ingesta:** El usuario selecciona una ruta. El sistema escanea recursivamente buscando prefijos válidos (`VALID_PREFIXES`).
2.  **Preparación:** Se calculan hashes MD5 y se generan metadatos JSON.
3.  **Encriptación (Local):** Se genera un archivo `.7z` temporal usando AES-256 en modo `Store` (`-mx=0`). *Decisión de diseño: Se prioriza I/O sobre CPU, ya que el contenido multimedia no comprime bien.*
4.  **Smart Upload (Nube):** Se inicia la transferencia monitoreada. Si la velocidad es inestable, se reinicia el socket.
5.  **Commit (Transacción):**
    * Si la subida es `OK` -> Se registra en el `InventoryManager`.
    * Si la subida `FALLA` -> Se descarta el registro y se limpia el temporal.
6.  **Sincronización:** Al finalizar el lote, se sube el índice actualizado a `backup/index/`.

---

## 📂 Estrategia de Carpetas (Flattening)

Para evitar la anidación profunda común en compresiones (ej: `Restore/Juego/Juego/Archivo.exe`), el sistema implementa una lógica de aplanado durante la restauración:

1.  El archivo encriptado se baja a `temp/`.
2.  Se extrae en un directorio temporal único (`uuid`).
3.  Se elimina el archivo `metadatos.json` (información interna).
4.  El sistema detecta si hay una carpeta contenedora redundante. Si existe, mueve su *contenido* a la raíz de destino; si son archivos sueltos, los mueve directamente.
5.  Resultado: Una estructura de carpetas limpia y lista para usar.