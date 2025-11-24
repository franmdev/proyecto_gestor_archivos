# 🛡️ Modelo de Seguridad y Criptografía

Este proyecto implementa un enfoque de **"Defensa en Profundidad"** para proteger los activos digitales en entornos de nube pública no confiables.

## 1. Principio Zero-Knowledge
El proveedor de la nube (Microsoft, Google, AWS) es tratado como un adversario capaz de leer metadatos y contenido.
* **Datos:** Cifrados con AES-256.
* **Metadatos:** Los nombres de archivo son hashes SHA-256 truncados. No hay forma de saber si un archivo es una "Tesis" o un "Video" mirando la nube.
* **Estructura:** La jerarquía de carpetas se aplana. No se revela la organización del usuario.

## 2. Implementación Criptográfica

### Cifrado de Archivos (Data at Rest)
Utilizamos el estándar industrial **AES-256** en modo CBC implementado nativamente por 7-Zip.
* **Header Encryption (`-mhe=on`):** Crucial. Cifra no solo el contenido de los archivos comprimidos, sino también la lista de archivos interna. Sin la contraseña, el archivo `.7z` es una caja negra indistinguible de ruido aleatorio.
* **Key Derivation:** Las contraseñas de usuario no se usan directamente. Se derivan usando **PBKDF2-HMAC-SHA256** con 100,000 iteraciones y un salt específico, protegiendo contra ataques de diccionario y Rainbow Tables.

### Protección de Identidad (Witness Protocol)
Para mitigar el riesgo de error humano (olvidar la contraseña o escribirla mal al subir), implementamos el protocolo de **Archivos Testigo**.
* **Ubicación:** `backup/keys/`.
* **Funcionamiento:** Al iniciar, el sistema descarga pequeños archivos cifrados (`witness_master.7z`). Intenta desencriptarlos con la contraseña ingresada en memoria.
* **Efecto:** Si la contraseña es incorrecta, el programa **termina inmediatamente** (`sys.exit()`). Esto impide que el usuario encripte nuevos datos con una contraseña errónea, lo que resultaría en pérdida de datos.

## 3. Topología de Aislamiento en Nube

La estructura de carpetas en la nube está diseñada para segregar datos sensibles de datos estructurales:

| Ruta Nube | Contenido | Nivel de Riesgo |
| :--- | :--- | :--- |
| `backup/keys/` | Testigos de validación | Alto (Verificadores de acceso) |
| `backup/index/` | Base de datos (`index_main.7z`) | Crítico (Mapa de todo el sistema) |
| `backup/DOC/` | Bloques de datos ofuscados | Medio (Inutilizables sin índice/clave) |

## 4. Gestión de Temporales
* Todos los procesos criptográficos ocurren en `data/temp/`.
* El sistema implementa una limpieza agresiva (`safe_delete` con reintentos).
* **Sanitización:** Al finalizar una operación (éxito o fallo), los residuos en disco se eliminan para evitar fugas de información en el equipo local.