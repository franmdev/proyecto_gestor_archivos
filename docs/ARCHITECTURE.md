### 2. `docs/ARCHITECTURE.md` (Actualizado con Smart Upload)
*Explica la lógica de red y la decisión de usar compresión Store.*

```markdown
# 🏗️ Arquitectura del Sistema

## Patrón de Diseño: Facade (Fachada)

El sistema utiliza un patrón **Facade** dividiendo la complejidad en 4 Managers principales, coordinados por un `AppOrchestrator`.

### Componentes Principales

1.  **`AppOrchestrator` (`main.py`)**: Interfaz de usuario (CLI) y control de flujo. Gestiona la interacción visual y los menús.
2.  **`SecurityManager`**: Encargado de la criptografía (Fernet, PBKDF2) y la compresión (7-Zip).
3.  **`InventoryManager`**: Gestiona el estado (Pandas/CSV), validación de duplicados y compatibilidad con Excel.
4.  **`CloudManager`**: Gestiona la comunicación con Rclone, incluyendo la lógica de optimización de red.

---

## 🔄 Lógica "Smart Upload" (Routing Fix)

Uno de los desafíos principales al usar nubes públicas (OneDrive, GDrive) es el **Routing BGP Subóptimo**, donde una conexión puede quedar atrapada en una ruta lenta (ej: 2 MB/s) aunque el ancho de banda disponible sea mayor (ej: 20 MB/s).

El sistema implementa una estrategia de mitigación activa en `CloudManager._smart_upload`:

1.  **Detección:** Se analiza el flujo de datos de Rclone en tiempo real (lectura de `stdout` línea por línea).
2.  **Evaluación Temprana:**
    * **T=10s y T=20s:** Si la velocidad es < **8 MB/s**, se asume una mala ruta.
    * **T=30s:** Si la velocidad es < **15 MB/s**, se considera subóptima.
3.  **Acción:** Si se cumplen las condiciones de baja velocidad, el sistema **mata el proceso de rclone** y reintenta la conexión (hasta 3 veces). Esto fuerza al ISP a negociar una nueva ruta BGP.
4.  **Comandos Optimizados:** Se inyectan flags específicos (`--onedrive-chunk-size 200M`, `--buffer-size 200M`) para maximizar el throughput en archivos grandes.

---

## 📦 Estrategia de Compresión y Almacenamiento

### Modo "Store" (-mx=0)
Se ha cambiado la estrategia de compresión de Ultra (`-mx=9`) a Store (`-mx=0`).
* **Razón:** La mayoría de los archivos multimedia (fotos, videos) ya están comprimidos. Intentar recomprimirlos consume mucha CPU y tiempo sin ganancia real.
* **Beneficio:** La "encriptación" se vuelve instantánea, limitada solo por la velocidad de disco I/O, permitiendo que el cuello de botella sea la red (donde actúa el Smart Upload).
* **Seguridad:** El flag `-mhe=on` (Header Encryption) se mantiene, garantizando que la estructura interna y los nombres de archivo sean invisibles.

### Estructura Plana en Nube
Para evitar redundancia de carpetas, el sistema sube los archivos directamente bajo su prefijo en la carpeta base definida en `.env`.
* **Antes:** `remote:/DOC/archivo_hash.7z/archivo_hash.7z`
* **Ahora:** `remote:backup/DOC/archivo_hash.7z`