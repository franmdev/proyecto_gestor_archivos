# 🔐 Gestor de Archivos Encriptados (Secure Cloud Vault) v2.2

> **Sistema de preservación digital de "Defensa en Profundidad" utilizando arquitectura Facade, encriptación AES-256 multinivel y sincronización cloud vía Rclone.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Security](https://img.shields.io/badge/Encryption-AES256%20%2B%207z-red)

---

## 📋 Descripción General

Este proyecto es una solución robusta para la gestión, encriptación y respaldo de archivos sensibles en la nube. A diferencia de las soluciones comerciales, este sistema garantiza **Privacidad Cero-Conocimiento** (Zero-Knowledge Privacy) mediante un esquema de doble autenticación y ofuscación total de metadatos.

El sistema actúa como un orquestador inteligente entre el sistema de archivos local, el motor de compresión 7-Zip y el gestor de transferencia Rclone.

### 🚀 Características Principales

* **Arquitectura Facade:** Código modular y mantenible dividido en Managers (Security, Cloud, Inventory).
* **Seguridad de Grado Militar:**
    * Encriptación de contenido: AES-256 (vía 7z).
    * Encriptación de nombres: Fernet (Simétrica).
    * Ofuscación: Nombres de archivo hash SHA-256 deterministas.
* **Doble Factor de Autenticación Lógica:** Contraseña separada para archivos (Master) y para el índice (CSV).
* **Gestión de Inventario Inteligente:** Base de datos local (CSV) con prevención de duplicados y manejo de metadatos.
* **Sincronización Cloud Agnostica:** Compatible con cualquier proveedor soportado por Rclone (Drive, S3, OneDrive, Dropbox, etc.).
* **Resiliencia:** Recuperación ante desastres (lectura de metadatos inyectados) y manejo de errores de sistema de archivos (WinError 5).

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

Crea un archivo `.env` en la raíz basado en el siguiente esquema:

```ini
# Ruta a la carpeta donde reside el ejecutable de rclone (opcional si está en PATH)
RCLONE_PATH=C:\_rclone

# Nombre del remote configurado en 'rclone config'
RCLONE_REMOTE_NAME=mi_remote_seguro

# Ruta base en la nube
RCLONE_REMOTE_PATH=/

# Ruta a la carpeta donde reside 7z.exe o 7za.exe
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

- **Login:** Ingrese su Contraseña Maestra y Contraseña CSV.
- **Modo Subida:** Arrastre carpetas. El sistema detectará prefijos válidos (DOC, FIN, etc.), encriptará y subirá solo si no existen duplicados.
- **Modo Descarga:** Navegue jerárquicamente (Prefijo -> Lista -> Selección) para recuperar archivos.
- **Mantenimiento:** Verifique la conexión con la nube y limpie temporales.

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

Desarrollado con ❤️ y Paranoia para la Preservación Digital.
