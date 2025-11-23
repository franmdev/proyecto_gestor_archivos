# 🔧 Desafíos de Ingeniería y Soluciones (Engineering Journal)

Durante el desarrollo de este gestor de archivos, enfrentamos varios desafíos técnicos relacionados con la interacción con el sistema operativo (Windows) y la inestabilidad de las redes. Aquí se documentan las soluciones implementadas.

## 1. El Problema del "Muro de Texto" en Consola
**Desafío:** Al leer la salida estándar (`stdout`) de Rclone para monitorear la velocidad, la consola se llenaba de miles de líneas, haciendo imposible leer los logs de error o el estado.
**Solución:** Implementación de **TQDM** con parseo en tiempo real.
* Interceptamos el `stdout` de Rclone línea por línea.
* Usamos expresiones regulares (`Regex`) para extraer `%` y `Velocidad`.
* Alimentamos una barra de progreso TQDM manual que se actualiza en la misma línea (`\r`), manteniendo la consola limpia y profesional.

## 2. Bloqueo de Archivos en Windows (`[WinError 5] Access is denied`)
**Desafío:** Al intentar borrar archivos temporales (`witness.7z`, índices) inmediatamente después de usarlos, Windows arrojaba errores de permiso porque el proceso (Python o el antivirus) aún tenía el "handle" del archivo abierto.
**Solución:**
1.  Implementación de función `safe_delete` con **Backoff Exponencial**: Intenta borrar 10 veces con pausas crecientes (0.5s, 0.7s...).
2.  **Limpieza Diferida:** En el arranque (`main.py`), los testigos no se borran inmediatamente tras la validación. Se introdujo un `time.sleep(5)` estratégico para dar tiempo al SO a liberar los recursos antes de la limpieza.

## 3. Rclone: `copy` vs `copyto` (El bug de las carpetas anidadas)
**Desafío:** Al descargar archivos específicos (como las llaves o el índice), Rclone creaba una carpeta con el nombre del archivo en lugar de descargar el archivo en sí (ej: `data/temp/index.7z/index.7z`). Esto rompía la lógica de borrado, ya que `unlink()` falla en directorios.
**Análisis:** El comando `rclone copy` asume que el destino es siempre un directorio.
**Solución:** Se migró la lógica crítica a `rclone copyto`. Este comando es explícito: si el destino es una ruta de archivo, escribe el archivo ahí, garantizando una estructura plana y predecible.

## 4. Routing BGP Subóptimo (Velocidades de 2MB/s en fibra óptica)
**Desafío:** Al subir archivos grandes a nubes públicas, la conexión a veces se negociaba a través de rutas congestionadas, limitando la velocidad a <5 MB/s a pesar de tener 600 MB/s disponibles.
**Solución:** Algoritmo **"Smart Upload"**.
* El sistema muestrea la velocidad en T=10s, T=20s y T=30s.
* Si la velocidad está por debajo del umbral configurado en `.env`, el sistema mata proactivamente el proceso de subida y reintenta.
* Esto fuerza una nueva negociación TCP/IP y BGP, logrando frecuentemente saltar a una ruta de alta velocidad en el segundo intento.

## 5. Integridad del Índice (Registros Fantasma)
**Desafío:** Si una subida fallaba en el último intento, el archivo ya se había registrado en el CSV en memoria. Al guardar el CSV, quedaba un registro de un archivo que no existía en la nube.
**Solución:** Implementación de **Registro Transaccional (Commit)**.
* Se invirtió la lógica en `main.py`.
* Ahora: `Encriptar` -> `Intentar Subir` -> `¿Éxito?` -> `Registrar en CSV`.
* Si falla la subida, el registro nunca ocurre, manteniendo la integridad total entre el índice local y la realidad en la nube.