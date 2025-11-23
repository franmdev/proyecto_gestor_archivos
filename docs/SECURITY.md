# 🛡️ Modelo de Seguridad y Criptografía

## 1. Protocolo de "Archivos Testigo" (Witness Files)
Para evitar el escenario catastrófico donde un usuario encripta y sube datos con una contraseña mal escrita (haciéndolos irrecuperables), implementamos un protocolo de validación previo.

* **Ubicación:** `backup/keys/` en la nube.
* **Funcionamiento:** Al inicio, el sistema descarga `witness_master.7z` y `witness_csv.7z`. Intenta abrirlos con las claves ingresadas. Si falla, el programa se detiene inmediatamente.
* **Seguridad:** Estos archivos contienen datos dummy ("VALID"), no información real.

## 2. Criptografía de Datos (Data at Rest)
Utilizamos **AES-256** nativo de 7-Zip para el contenido.
* **Modo:** `-mhe=on` (Header Encryption). Esto es crucial porque oculta no solo el contenido de los archivos, sino también sus **nombres originales** y la estructura de carpetas interna. Un atacante solo ve un archivo `.7z` opaco.

## 3. Privacidad de Metadatos
El índice local (`index_main.csv`) contiene los nombres reales de los archivos. Para proteger esto:
* El índice se encripta con una contraseña diferente a la de los archivos (Separación de Responsabilidades).
* El nombre original dentro del CSV se tokeniza adicionalmente usando **Fernet** (Implementación simétrica de criptografía.io), asegurando que incluso si se filtra el CSV plano, los nombres sensibles no son legibles sin la clave de aplicación derivada.

## 4. Estructura de Carpetas en Nube
Para evitar el análisis de tráfico o deducción por estructura de directorios, el sistema "aplana" el almacenamiento.
* **Nube:** `backup/PREFIJO/HASH_ALEATORIO.7z`
* No se replican las carpetas locales en la nube. La relación lógica se reconstruye solo al descargar y desencriptar localmente.