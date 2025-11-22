### 2. Documentación Técnica: `docs/ARCHITECTURE.md`
Este archivo es para desarrolladores. Explica el *porqué* de las decisiones técnicas.

```markdown
# 🏗️ Arquitectura del Sistema

## Patrón de Diseño: Facade (Fachada)

El proyecto ha migrado de una arquitectura de servicios dispersos a un patrón **Facade**. Esto se decidió para reducir la complejidad cognitiva y el acoplamiento entre componentes.

### Componentes Principales (Managers)

El sistema se divide en 4 módulos de alto nivel, cada uno responsable de un dominio específico:

1.  **`AppOrchestrator` (`main.py`)**:
    * **Rol:** Controlador y Vista.
    * **Responsabilidad:** Gestiona la interacción con el usuario (CLI), captura inputs y coordina a los managers. No contiene lógica de negocio profunda, solo lógica de flujo.

2.  **`SecurityManager` (`security_manager.py`)**:
    * **Rol:** Caja Fuerte.
    * **Responsabilidad:** Abstrae la complejidad de las librerías criptográficas.
    * **Funciones Clave:**
        * Wrapper de `subprocess` para 7-Zip.
        * Generación de claves PBKDF2HMAC.
        * Encriptación simétrica Fernet.
        * Hashing SHA-256 determinista para nombres de archivo.

3.  **`InventoryManager` (`inventory_manager.py`)**:
    * **Rol:** Cerebro de Datos.
    * **Responsabilidad:** Gestión del estado del sistema mediante Pandas.
    * **Funciones Clave:**
        * CRUD sobre el índice CSV.
        * Validación de duplicados (`check_exists`).
        * Generación de IDs autoincrementales.
        * Persistencia segura (guardado y carga de índice encriptado).

4.  **`CloudManager` (`cloud_manager.py`)**:
    * **Rol:** Brazo Ejecutor.
    * **Responsabilidad:** Interfaz con el sistema de archivos y la nube.
    * **Funciones Clave:**
        * Wrapper de `rclone` via `subprocess`.
        * Escaneo inteligente de carpetas locales.
        * Gestión de transferencias (Upload/Download).

## Flujo de Datos (Data Flow)

### Proceso de Subida (Upload)
1.  `CloudManager` escanea disco local -> Lista de `Path`.
2.  `InventoryManager` verifica existencia -> Filtra duplicados.
3.  `SecurityManager` genera metadatos (Hash, Nombre Encriptado).
4.  `SecurityManager` comprime y encripta a `.7z` temporal.
5.  `CloudManager` sube el `.7z` a Rclone.
6.  `InventoryManager` registra la transacción en memoria.
7.  `InventoryManager` genera backup encriptado del índice.
8.  `CloudManager` sube el índice actualizado.

### Manejo de Errores y Resiliencia
* **WinError 5 (Access Denied):** Implementado `safe_delete` con lógica de reintento y espera (`time.sleep`) para manejar el bloqueo de archivos por parte del SO/Antivirus tras operaciones de 7-Zip.
* **Codificación:** Uso estricto de `utf-8-sig` para garantizar compatibilidad total con Microsoft Excel en la lectura de logs y CSVs.