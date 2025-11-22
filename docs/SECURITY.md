# 🛡️ Modelo de Seguridad

Este documento detalla las medidas criptográficas y de diseño implementadas para garantizar la confidencialidad e integridad de los datos.

## 1. Criptografía

### Derivación de Claves (KDF)
* **Algoritmo:** PBKDF2HMAC (Password-Based Key Derivation Function 2).
* **Hashing:** SHA-256.
* **Iteraciones:** 100,000 (Estándar NIST para resistencia a fuerza bruta).
* **Salt:** Salt fijo de aplicación para garantizar determinismo en la recuperación, combinado con entropía de la contraseña del usuario.

### Encriptación de Contenido (Data at Rest)
* **Herramienta:** 7-Zip (AES-256).
* **Modo:** `-mhe=on` (Encrypt Headers). Esto oculta no solo el contenido de los archivos, sino también sus nombres originales y la estructura de carpetas interna dentro del contenedor `.7z`.

### Encriptación de Metadatos
* **Algoritmo:** Fernet (Implementación simétrica sobre AES-128 en modo CBC con firma HMAC-SHA256).
* **Uso:** Se utiliza para encriptar el "Nombre Original" del archivo dentro del CSV y dentro del `metadatos.json` inyectado en cada archivo.

### Hashing e Integridad
* **MD5:** Verificación de integridad de contenido (detección de corrupción en transferencia).
* **SHA-256:** Generación de nombres de archivo ofuscados (deterministas) para almacenamiento en la nube.

## 2. Estrategia de Doble Autenticación

El sistema implementa una separación de preocupaciones de seguridad:

1.  **Contraseña Maestra (Master Password):**
    * Utilizada para encriptar/desencriptar los contenedores `.7z` de los archivos de datos (`DOC`, `FIN`, etc.).
    * Utilizada para derivar la clave Fernet de los nombres de archivo.

2.  **Contraseña de Índice (CSV Password):**
    * Utilizada **exclusivamente** para encriptar el archivo `index_main.csv` (que se guarda como `index_main.7z`).
    * **Beneficio:** Si el archivo de índice es comprometido, el atacante no puede acceder a los archivos de datos. Si un archivo de datos es comprometido, el atacante no tiene el mapa completo de la información.

## 3. Recuperación de Desastres (Disaster Recovery)

El sistema está diseñado para ser resiliente a la pérdida total de la base de datos local (`index_main.csv`).

**Mecanismo de Inyección de Metadatos:**
Cada archivo `.7z` subido contiene un archivo oculto `metadatos.json` con:
* Hash del nombre.
* Token Fernet del nombre original.
* Timestamp.

**Escenario de Recuperación:**
En caso de pérdida del CSV, un script de recuperación (futura implementación) puede descargar todos los `.7z`, extraer sus `metadatos.json` usando la Contraseña Maestra y reconstruir el índice CSV desde cero.