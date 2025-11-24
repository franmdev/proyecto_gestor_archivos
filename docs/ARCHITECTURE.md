# 🏗️ Arquitectura del Sistema

## 📐 Patrón de Diseño: Facade (Fachada)

Para gestionar la complejidad de interactuar con sistemas de archivos locales, procesos de encriptación externos y transmisiones de red asíncronas, el proyecto utiliza el patrón arquitectónico **Facade**.

* **El Cliente:** `main.py` (AppOrchestrator). No conoce los detalles de cómo se encripta un byte o cómo se negocia una conexión TCP. Solo invoca comandos de alto nivel (`upload_file`, `decrypt`).
* **Los Subsistemas:** `CloudManager`, `SecurityManager`, `InventoryManager`. Cada uno encapsula una complejidad específica.

### Diagrama de Componentes

```mermaid
graph TD
    User[Usuario] -->|CLI Input| Main[AppOrchestrator (main.py)]
    
    Main -->|Gestiona| Inv[InventoryManager]
    Main -->|Coordina| Sec[SecurityManager]
    Main -->|Ordena| Cloud[CloudManager]
    
    Inv -->|Persistencia| CSV[(Index CSV)]
    Sec -->|Subprocess| 7z[7-Zip CLI]
    Cloud -->|Subprocess| Rclone[Rclone CLI]
    
    Rclone -->|API| CloudProvider[OneDrive/GDrive]
```

---

## 🧩 Módulos Principales

### 1. CloudManager (Capa de Transporte)

Actúa como un wrapper inteligente sobre Rclone.

* **Responsabilidad:** Abstraer la complejidad de los comandos de CLI de Rclone y añadir lógica de negocio que la herramienta nativa no tiene.
* **Innovación:** Implementa el algoritmo "Smart Upload". Intercepta el stdout de Rclone en tiempo real, parsea la velocidad con expresiones regulares y toma decisiones de interrupción (`process.terminate()`) si la métrica de calidad de servicio (QoS) cae por debajo de los umbrales definidos en `.env` (T10, T20, T30).

### 2. SecurityManager (Capa de Protección)

Encargada de la confidencialidad e integridad.

* **Responsabilidad:** Transformar datos legibles en datos ofuscados y viceversa.
* **Estrategia de "Aplanado" (Flattening):** Al descomprimir, este módulo no se limita a extraer. Analiza la estructura resultante en un entorno temporal (`temp/`) y elimina carpetas contenedoras redundantes (ej: `GAM/GAM/juego.exe -> juego.exe`), entregando una estructura limpia al usuario.

### 3. InventoryManager (Capa de Datos)

Gestiona el estado del sistema.

* **Responsabilidad:** Mantener una base de datos local (pandas DataFrame) sincronizada con la realidad de la nube.
* **Lógica de Categorías:** Implementa la abstracción de "Categorías" (Subfijos) de manera lógica. Físicamente en la nube todo es plano (`backup/PREFIJO/`), pero el InventoryManager agrupa lógicamente los datos (PREFIJO -> CATEGORÍA -> ARCHIVO) para la experiencia de usuario.

---

## 🔄 Flujos de Datos (Pipelines)

### Pipeline de Subida (Transaccional)

Para garantizar la consistencia, el sistema sigue un modelo de Commit de Dos Fases (simulado):

* **Scan & Detect:** Se identifica la estructura local (Carpeta -> Prefijo -> Categoría).
* **Lock & Encrypt:** Se genera el archivo `.7z` cifrado localmente con metadatos embebidos.
* **Transfer (Try):** Se intenta subir el archivo usando Smart Upload.
* **Commit/Rollback:**
    * **Éxito:** Se escribe el registro en el CSV local (commit).
    * **Fallo:** Se elimina el archivo temporal cifrado y no se toca la base de datos (rollback), evitando "registros fantasma".

### Pipeline de Descarga (Restauración Lógica)

* **Fetch Index:** Descarga atómica del índice (`index/index_main.7z`) a memoria.
* **Query:** El usuario filtra por Prefijo y Categoría.
* **Retrieve:** Descarga del blob cifrado (copyto para evitar carpetas anidadas).
