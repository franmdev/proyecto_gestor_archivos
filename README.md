# 🔐 Gestor de Archivos Encriptados (Secure Cloud Vault) v2.5

> **Sistema de preservación digital con arquitectura Facade, encriptación AES-256 Zero-Knowledge y optimización de red "Smart Upload" para nubes públicas.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Security](https://img.shields.io/badge/Encryption-AES256%20%2B%207z-red)
![Network](https://img.shields.io/badge/Network-Smart%20Routing%20Fix-orange)

---

## 📚 Documentación Técnica Detallada

Para comprender la profundidad del sistema, consulte los siguientes documentos en la carpeta `docs/`:

* **[🏗️ Arquitectura del Sistema](docs/ARCHITECTURE.md):** Explica el patrón Facade, el flujo "Smart Upload" y la gestión de datos.
* **[🛡️ Modelo de Seguridad](docs/SECURITY.md):** Detalles sobre criptografía, testigos de validación (Witness Files) y doble autenticación.
* **[🔧 Solución de Problemas](docs/TROUBLESHOOTING.md):** Guía para errores comunes (WinError 5, Excel, Red).

---

## 📋 Descripción General

Este proyecto es una solución robusta para la gestión y respaldo de archivos sensibles en la nube. A diferencia de las soluciones comerciales, garantiza **Privacidad Cero-Conocimiento** mediante un esquema de doble autenticación y nombres de archivo ofuscados.

Integra una lógica de **"Smart Upload"** diseñada específicamente para combatir el *routing subóptimo* (BGP) común en servicios como OneDrive o Google Drive, garantizando velocidades de transferencia óptimas.

### 🚀 Características Principales

* **Smart Upload (Routing Fix):** Monitoreo en tiempo real de la velocidad de subida. Si detecta una ruta lenta (<8 MB/s), reinicia la conexión automáticamente para buscar una mejor ruta de red.
* **Modo "Store" Ultrarrápido:** Utiliza compresión `-mx=0` (solo almacenamiento) con encriptación AES-256 `-mhe=on`. Prioriza la velocidad de cifrado para grandes volúmenes de datos.
* **Seguridad de Grado Militar:** Encriptación AES-256 multinivel (Contenido + Nombres + Índice).
* **Validación Remota (Witness):** Verifica las contraseñas contra archivos testigo en la nube antes de iniciar operaciones, evitando corrupción de datos por claves erróneas.
* **Gestión de Inventario:** Base de datos local (CSV) compatible con Excel (`utf-8-sig`), detección de duplicados y recuperación ante desastres.
* **Descarga Jerárquica:** Explorador visual de archivos por prefijos en la terminal.

---

## 🛠️ Requisitos del Sistema

1. **Python 3.9+**
2. **Rclone:** Configurado y accesible en el sistema o en ruta portable.
3. **7-Zip:** Instalado o en versión portable (`7za.exe`).
4. **Entorno:** Windows (probado en 10/11), Linux o macOS.

---

## 📦 Instalación y Configuración

### 1. Clonar el Repositorio

```bash
git clone https://github.com/TU_USUARIO/gestor-archivos-secure.git
cd gestor-archivos-secure
```

### 2. Preparar Entorno Virtual

```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 4. Configuración de Variables (.env)

Crea un archivo `.env` en la raíz. Nota: RCLONE_REMOTE_PATH define la carpeta contenedora en la nube.

```ini
# Ruta a la carpeta de rclone (opcional si está en PATH)
RCLONE_PATH=C:\_rclone

# Nombre del remote configurado en 'rclone config'
RCLONE_REMOTE_NAME=mi_remote_seguro

# Carpeta base en la nube (El sistema la creará automáticamente)
# Ejemplo: Los archivos irán a mi_remote_seguro:backup/DOC/...
RCLONE_REMOTE_PATH=backup

# Ruta a la carpeta de 7z (portable o instalada)
SEVEN_ZIP_PATH=C:\_rclone\_7z\x64

# Configuración General
MIN_PASSWORD_LENGTH=12
DEBUG=false
```

---

## 💻 Uso

Ejecuta el orquestador principal:

```bash
python main.py
```

### Flujo de Trabajo

- **Login:** Ingrese y confirme su Contraseña Maestra y Contraseña CSV. El sistema validará contra la nube.
- **Modo Subida:** Arrastre carpetas. El sistema detectará prefijos, validará duplicados y aplicará "Smart Upload" si el archivo es grande (>500MB).
- **Modo Descarga:** Seleccione un Prefijo numéricamente -> Vea la lista -> Seleccione IDs para descargar.
- **Mantenimiento:** Verifique la conexión y limpie temporales.

---

## 📂 Estructura del Proyecto

```
GESTOR/
├── config.py              # Configuración central y Logging
├── main.py                # Orquestador (UI y Flujo)
├── cloud_manager.py       # Fachada para Rclone y FS Local
├── security_manager.py    # Fachada para Criptografía y 7-Zip
├── inventory_manager.py   # Fachada para Pandas/CSV
├── requirements.txt       # Dependencias
├── .env                   # Variables de entorno (No subir a git)
└── data/                  # Almacenamiento local de índices y logs
```

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulte el archivo LICENSE para más detalles.

Desarrollado con ❤️, Paranoia y Optimización de Red.
