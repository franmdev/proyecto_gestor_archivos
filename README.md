# 🔐 Secure Cloud Vault v3.5: Enterprise-Grade Cloud Archiver

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Rclone](https://img.shields.io/badge/Backend-Rclone-blueviolet?style=for-the-badge&logo=rclone&logoColor=white)](https://rclone.org/)
[![Security](https://img.shields.io/badge/Encryption-AES256%20%2B%20Fernet-red?style=for-the-badge&logo=lock&logoColor=white)](https://cryptography.io/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

> **Sistema de preservación digital Zero-Knowledge con optimización activa de enrutamiento de red ("Smart Upload"), integridad transaccional ACID-like y arquitectura modular basada en Facade.**

---

## 📖 Visión del Proyecto

**Secure Cloud Vault** no es un simple script de backup. Es una solución de ingeniería diseñada para resolver los tres "cuellos de botella" críticos que enfrentan los desarrolladores y empresas al usar almacenamiento en nube pública (OneDrive, Google Drive, AWS S3):

1. **Privacidad (Data Privacy):** Los proveedores de nube escanean los datos. Este sistema garantiza que **nada** salga de la máquina local sin estar encriptado y ofuscado.
2. **Rendimiento de Red (Network Throttling):** Las conexiones a menudo se estancan o se enrutan por nodos congestionados. Este sistema detecta y corrige esto activamente.
3. **Integridad de Datos (Data Consistency):** Evitar archivos corruptos o índices desincronizados ante fallos de energía o red.

Este proyecto demuestra la implementación de patrones de diseño robustos, manejo avanzado de subprocesos (`subprocess`) y manipulación de flujos de datos en tiempo real.

---

## 🚀 Características de Ingeniería (Core Features)

### 1. ⚡ Smart Upload & BGP Routing Fix

El sistema implementa un algoritmo heurístico para maximizar el ancho de banda, rechazando conexiones subóptimas.

* **El Problema:** A veces, una subida a la nube comienza a 2 MB/s en una conexión de fibra de 600 Mbps debido a una mala negociación de ruta BGP o saturación del nodo de entrada del proveedor.
* **La Solución:** El módulo `CloudManager` monitorea el flujo de bytes en tiempo real (T=10s, T=20s, T=30s).
* **Algoritmo:**
    * Si `Speed < Umbral` (ej: 15 MB/s) en puntos críticos, el sistema **mata el socket TCP** y fuerza una reconexión inmediata.
    * Esto obliga al proveedor de servicios de internet (ISP) y al Cloud Provider a renegociar la ruta, logrando frecuentemente saltar de **2 MB/s a +40 MB/s** automáticamente.

### 2. 🛡️ Arquitectura Zero-Knowledge

* **Seguridad en Capas:**
    * **Capa 1 (Contenido):** AES-256 con encriptación de cabeceras (`-mhe=on`). Nadie puede ver la estructura de carpetas interna.
    * **Capa 2 (Metadatos):** El índice local (`CSV`) se encripta con una clave secundaria antes de subir.
    * **Capa 3 (Ofuscación):** Los nombres de archivos en la nube son hashes SHA-256 truncados (ej: `a9966c...7z`). No hay rastro semántico del contenido.
* **Protocolo de Testigos (Witness Protocol):** El sistema valida criptográficamente las llaves contra archivos testigo en la nube (`backup/keys/`) al inicio. Si las llaves no coinciden, el sistema se bloquea para prevenir la corrupción de datos o la creación de backups irrecuperables.

### 3. 💾 Integridad Transaccional

El sistema opera bajo principios de atomicidad.

* **Commit-Logic:** Un archivo solo se registra en la base de datos local **después** de recibir la confirmación de integridad (`exit_code=0`) del proceso de subida.
* **Rollback Automático:** Si una subida falla o se cancela, se eliminan los temporales locales y no se ensucia el índice.
* **Sync Check:** Al iniciar, el sistema descarga el índice remoto, lo compara con el local y ofrece sincronización si detecta discrepancias (ej: si se subió desde otro PC).

---

## 🔧 Under the Hood: Optimización de Rclone

Este proyecto utiliza **Rclone** como motor de transporte, pero lo envuelve en una capa de lógica de negocio. A continuación, se detallan los parámetros de *Tuning* implementados para maximizar el throughput:

| Flag Rclone | Función Técnica | Por qué lo usamos |
| :--- | :--- | :--- |
| `--transfers 8` | Paralelismo de Archivos | Permite subir/bajar 8 archivos simultáneamente, saturando el ancho de banda en archivos pequeños. |
| `--checkers 16` | Paralelismo de Verificación | Acelera la comparación de estados entre local y nube antes de transferir. |
| `--multi-thread-streams 8` | Hilos por Archivo | Divide un **único** archivo grande en 8 partes y las transfiere en paralelo. Crucial para archivos > 1GB. |
| `--multi-thread-cutoff 200M` | Umbral de Hilos | Solo activa el multi-hilo si el archivo supera los 200MB, evitando overhead en archivos pequeños. |
| `--buffer-size 200M` | Memoria Intermedia | Asigna 200MB de RAM por hilo para suavizar picos de latencia de disco o red. |
| `--disable-http2` | Protocolo de Red | En ciertas condiciones de latencia alta, HTTP/1.1 ha demostrado ser más estable y rápido que HTTP/2 para transferencias de bloques grandes. |
| `copy` vs `copyto` | Gestión de Rutas | El código selecciona dinámicamente entre `copy` (para carpetas) y `copyto` (para archivos atómicos como índices), evitando la creación errónea de carpetas anidadas. |

---

## 🏗️ Estructura del Proyecto

El diseño sigue una arquitectura limpia, separando responsabilidades en Managers especializados:

```text
proyecto/
├── config.py              # Singleton de configuración y carga de entorno.
├── main.py                # Orquestador (Facade) y UI de consola.
├── cloud_manager.py       # Lógica de red, Smart Upload y Wrapper de Rclone.
├── security_manager.py    # Lógica de cifrado (Fernet/AES) y aplanado de carpetas.
├── inventory_manager.py   # Gestión de base de datos (Pandas) y lógica de negocio.
├── .env                   # Secretos y parámetros de tuning (No versionado).
├── data/                  # Directorio de trabajo (Ignorado por Git).
│   ├── backups/           # Backups automáticos del índice.
│   ├── descargas/         # Archivos bajados (temporales).
│   ├── desencriptados/    # Salida final para el usuario.
│   ├── index/             # Base de datos local (CSV + Encriptado).
│   ├── logs/              # Auditoría de operaciones.
│   └── temp/              # Zona de transito para encriptación/descompresión.
```

---

## 📦 Instalación y Despliegue

### Prerrequisitos

* Python 3.10+
* Rclone: Debe estar instalado y configurado (o su ejecutable en la ruta del proyecto).
* 7-Zip: Debe estar instalado o usar la versión portable (`7za.exe`).

### Pasos

#### 1. Clonar el Repositorio

```bash
git clone https://github.com/tu-usuario/secure-cloud-vault.git
cd secure-cloud-vault
```

#### 2. Preparar Entorno Virtual

```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

#### 3. Instalar Dependencias

```bash
pip install -r requirements.txt
```

#### 4. Configurar Variables de Entorno (.env)

Crea un archivo `.env` en la raíz. Este archivo actúa como el panel de control de rendimiento del sistema.

```ini
# --- INFRAESTRUCTURA ---
RCLONE_REMOTE_NAME=mi_drive_personal
RCLONE_REMOTE_PATH=backup_seguro
# Opcional: Rutas absolutas si no están en PATH
# SEVEN_ZIP_PATH="C:\Program Files\7-Zip"

# --- TUNING SMART UPLOAD ---
SMART_MAX_RETRIES=3       # Intentos máximos críticos
SMART_T3_LIMIT=15.0       # Si a los 30s la velocidad es < 15MB/s, REINICIAR.

# --- TUNING RCLONE DOWNLOAD ---
DL_TRANSFERS=8
DL_MULTI_THREAD_STREAMS=8
DL_BUFFER_SIZE=200M
```

---

## 💻 Guía de Uso

### 1. Inicio y Autenticación

Al ejecutar `python main.py`, el sistema realiza un Handshake de Seguridad:

* Solicita Clave Maestra (Archivos) y Clave CSV (Índice).
* Descarga los "Testigos" desde la nube.
* Verifica criptográficamente las claves.
* Verifica si el índice local está sincronizado con la nube.

### 2. Modo Subida (Upload)

* El usuario ingresa una carpeta raíz.
* El sistema escanea recursivamente.
* **Detección Inteligente:** Si la carpeta seleccionada es un contenedor conocido (ej: GAM para Juegos), el sistema entra y procesa cada subcarpeta como un ítem independiente.
* Se asigna una Categoría lógica automáticamente.
* Se encripta, se aplica Smart Upload y se registra.

### 3. Modo Descarga (Download)

El sistema ofrece una experiencia de navegación jerárquica que no existe físicamente en la nube:

* **Seleccionar Prefijo:** (Ej: DOC, GAM).
* **Seleccionar Categoría:** (Ej: Universidad, Trabajo).
* **Seleccionar Archivos:** El usuario ve nombres reales, no hashes.
* **Restauración:** El sistema descarga el hash, lo desencripta y lo coloca en `data/desencriptados/Categoría/NombreReal`, reconstruyendo la estructura original.

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Siéntase libre de usarlo, modificarlo y distribuirlo, manteniendo la atribución al autor original.

<div align="center">
  <sub>Desarrollado con énfasis en <b>Seguridad Ofensiva</b> y <b>Optimización de Redes</b>.</sub>
</div>