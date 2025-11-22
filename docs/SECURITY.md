# 🛡️ Modelo de Seguridad

Este documento detalla las medidas implementadas para garantizar la confidencialidad, integridad y disponibilidad de los datos.

## 1. Validación de Identidad (Witness Files)

El sistema implementa un mecanismo de **"Archivos Testigo"** para validar que las contraseñas ingresadas son correctas *antes* de intentar desencriptar datos críticos o corromper el índice.

### Flujo de Validación
1.  Al iniciar, el sistema busca `witness_master.7z` y `witness_csv.7z` en la carpeta temporal de la nube.
2.  **Si existen:** Se descargan y se intenta una operación de "Test" (`7z t`) con la contraseña ingresada.
    * Si falla: Se alerta al usuario y se detiene el programa.
    * Si éxito: Se permite el acceso.
3.  **Si no existen:** El sistema crea archivos pequeños encriptados con las contraseñas actuales y los sube a la nube para futuras validaciones.

Este mecanismo previene el error común de subir archivos encriptados con una contraseña errónea (typo), lo que los haría irrecuperables.

## 2. Criptografía

### Derivación de Claves
* **Algoritmo:** PBKDF2HMAC (SHA-256).
* **Iteraciones:** 100,000 (Estándar NIST).
* **Salt:** Fijo por aplicación para permitir determinismo en la recuperación de nombres.

### Encriptación de Contenido (Data at Rest)
* **Herramienta:** 7-Zip (AES-256).
* **Modo:** Store (`-mx=0`) + Header Encryption (`-mhe=on`).
* **Protección:** Oculta contenido, nombres de archivos originales y estructura de directorios.

### Encriptación de Metadatos
* **Algoritmo:** Fernet (AES-128 CBC + HMAC).
* **Uso:** Encriptación del nombre original del archivo almacenado en el CSV y en el `metadatos.json` inyectado.

## 3. Doble Factor Lógico

* **Contraseña Maestra:** Protege los archivos de datos (`.7z`).
* **Contraseña CSV:** Protege exclusivamente el índice (`index_main.csv`).
* **Beneficio:** Compromiso compartimentado. Acceder al índice no da acceso a los archivos, y viceversa.