# 🔐 Secure Cloud Vault (Gestor de Archivos Encriptados) v3.0

> **Sistema de preservación digital Zero-Knowledge con optimización de red activa ("Smart Upload"), integridad transaccional y arquitectura modular.**

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Security](https://img.shields.io/badge/Encryption-AES256%20%2B%20Fernet-red)
![Network](https://img.shields.io/badge/Network-Smart%20BGP%20Routing-orange)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey)

Este proyecto es una solución de ingeniería de software diseñada para resolver tres problemas críticos en el almacenamiento en la nube pública (OneDrive, GDrive, etc.): **Privacidad**, **Velocidad de Transferencia** e **Integridad de Datos**.

A diferencia de clientes de sincronización estándar, este sistema actúa como un orquestador que encripta todo localmente antes de subirlo, gestiona su propio índice de base de datos y **manipula activamente la conexión de red** para evitar rutas saturadas.

---

## 🚀 Características Clave

### 1. ⚡ Smart Upload (Corrección de Routing BGP)

El sistema no acepta pasivamente la velocidad que ofrece el proveedor de nube.

* **Monitoreo Activo:** Analiza el flujo de datos en tiempo real.
* **Lógica de Decisión:** Si la velocidad cae por debajo de umbrales definidos (ej: <8 MB/s en T=10s), el sistema **mata el proceso** y renegocia la conexión.
* **Resultado:** Forza al ISP/Cloud Provider a asignar una nueva ruta de enrutamiento, logrando saltos de velocidad de 2 MB/s a +40 MB/s automáticamente.

### 2. 🛡️ Arquitectura Zero-Knowledge

* **Doble Factor Lógico:** Separación de secretos para Archivos (`.7z`) y Metadatos (`.csv`).
* **Ofuscación Total:** Los nombres de archivo en la nube son hashes aleatorios (ej: `a9966813c2ed.7z`). Nadie, ni el proveedor de la nube, puede saber qué contienen.
* **Witness Files:** Validación de identidad mediante archivos testigo en la nube (`backup/keys/`) antes de permitir cualquier operación local destructiva.

### 3. 💾 Integridad y Atomicidad

* **Base de Datos Distribuida:** El índice (`index_main.csv`) vive encriptado tanto localmente como en la nube (`backup/index/`).
* **Sync Check:** Al iniciar, compara la versión local contra la nube para asegurar la consistencia.
* **Transacciones Seguras:** El registro en la base de datos solo ocurre **después** de una subida exitosa confirmada (Commit-like logic).

---

## 📚 Documentación Técnica

Para profundizar en la ingeniería del proyecto:

* **[🏗️ Arquitectura y Diseño](docs/ARCHITECTURE.md):** Patrones de diseño, flujo de datos y estructura de carpetas.
* **[🛡️ Seguridad Criptográfica](docs/SECURITY.md):** Detalles sobre AES-256, derivación de claves y manejo de temporales.
* **[🔧 Desafíos y Soluciones (Engineering Journal)](docs/TROUBLESHOOTING.md):** *Lectura recomendada.* Documentación de los problemas complejos resueltos durante el desarrollo.

---

## 🛠️ Requisitos del Sistema

1. **Python 3.10+**
2. **Rclone:** Configurado y accesible en el sistema o en ruta portable.
3. **7-Zip:** Instalado o en versión portable (`7za.exe`).
4. **Entorno:** Windows, Linux o macOS.

---

## 📦 Instalación

### 1. Clonar Repositorio

```bash
git clone https://github.com/tu-usuario/secure-cloud-vault.git
cd secure-cloud-vault
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

### 4. Configurar Entorno (.env)

Crea un archivo `.env` en la raíz basado en el siguiente esquema:

```ini
# Configuración de Rclone
RCLONE_REMOTE_NAME=mi_remote_drive
RCLONE_REMOTE_PATH=backup

# Rutas a binarios (Opcional si están en PATH)
# RCLONE_PATH=C:\bin\rclone
# SEVEN_ZIP_PATH=C:\Program Files\7-Zip

# Tuning de Smart Upload (Umbrales de reinicio)
SMART_MAX_RETRIES=3
SMART_T1_LIMIT=8.0  # MB/s

# Optimización de Descarga
DL_TRANSFERS=8
DL_DISABLE_HTTP2=true
```

---

## 💻 Uso

Ejecute el orquestador:

```bash
python main.py
```

### Menú Principal

- **📤 Modo Subida:**
  - Arrastre una carpeta padre. El sistema detectará subcarpetas válidas (ej: GAM, DOC).
  - Si la carpeta es un contenedor (ej: GAM), procesará cada juego/item individualmente.
  - Aplicará compresión "Store" (sin compresión, solo cifrado) para máxima velocidad.

- **📥 Modo Descarga:**
  - Explorador visual de sus archivos en la nube.
  - Seleccione por ID para descargar y restaurar automáticamente.

- **🔍 Consultar Índice:** Estadísticas y últimos movimientos.

- **🔧 Mantenimiento:** Limpieza de temporales y test de conexión.

---

## 📂 Estructura de Nube Generada

El sistema mantiene el orden automáticamente:

```
R:/backup/
├── index/
│   └── index_main.7z       # Base de datos encriptada
├── keys/
│   ├── witness_master.7z   # Testigo validación Master
│   └── witness_csv.7z      # Testigo validación CSV
├── DOC/
│   ├── a4f1...7z           # Documento encriptado
│   └── ...
└── GAM/
    ├── b1c2...7z           # Juego encriptado
    └── ...
```

---

## 📄 Licencia

MIT License. Desarrollado con enfoque en seguridad y performance.
