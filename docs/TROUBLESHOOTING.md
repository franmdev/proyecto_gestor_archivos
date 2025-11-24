# 🔧 Engineering Journal: Desafíos y Soluciones

Registro técnico de los obstáculos encontrados durante el desarrollo v3.x y las soluciones de ingeniería aplicadas.

## 1. Inestabilidad de Routing BGP (El problema de "1 MB/s")
* **Contexto:** Subiendo archivos grandes (>3GB) a OneDrive, la velocidad se estancaba aleatoriamente en 1-2 MB/s, a pesar de tener una conexión de fibra simétrica de 600 Mbps.
* **Diagnóstico:** El enrutamiento TCP/IP hacia los servidores de ingestión de la nube a veces tomaba saltos congestionados. Rclone nativo no detecta "lentitud", solo cortes.
* **Solución:** Algoritmo **Smart Upload**. Implementamos un monitor de caudal. Si en T=30s la velocidad es < 15 MB/s, el sistema asume una mala ruta, mata el proceso y reintenta. Esto fuerza al sistema operativo y al ISP a negociar una nueva ruta, solucionando el problema en el 90% de los reintentos.

## 2. Corrupción Lógica: "Registros Fantasma"
* **Contexto:** Si una subida se interrumpía manualmente o por error de red en el último intento, el archivo ya aparecía en el CSV local como "Subido".
* **Causa:** El registro en la base de datos ocurría *antes* de la confirmación de la subida.
* **Solución:** Inversión de control (Commit-Logic). El código se refactorizó para que `inventory.add_record()` solo se ejecute si y solo si `cloud.upload_file()` retorna `True`. Esto garantiza integridad referencial estricta.

## 3. Rclone: Ambigüedad de `copy` vs `copyto`
* **Contexto:** Al descargar archivos individuales (como los testigos), Rclone creaba una carpeta con el nombre del archivo (`temp/witness.7z/witness.7z`) en lugar del archivo en sí. Esto hacía fallar la función de borrado `os.unlink`.
* **Diagnóstico:** `rclone copy` trata el destino como un directorio. Si no existe, lo crea.
* **Solución:** Implementación de `rclone copyto` para operaciones de archivo único. Este comando fuerza a Rclone a tratar el destino como una ruta de archivo, evitando la creación de estructuras anidadas erróneas.

## 4. Bloqueo de Archivos en Windows (`Access Denied`)
* **Contexto:** Intentar borrar archivos temporales inmediatamente después de usarlos fallaba aleatoriamente.
* **Causa:** Latencia del sistema de archivos NTFS o escaneo de antivirus manteniendo el *file handle* abierto milisegundos después de que Python lo cerrara.
* **Solución:**
    1.  **Backoff Exponencial:** `safe_delete` reintenta el borrado 10 veces con esperas crecientes.
    2.  **Limpieza Diferida:** En el arranque, introdujimos un `time.sleep(5)` explícito antes de limpiar los testigos, dando tiempo al SO para liberar los recursos.

## 5. Estructura Recursiva al Descomprimir
* **Contexto:** Al comprimir una carpeta "Juego", 7-Zip guarda la carpeta raíz. Al descomprimir en "Juego", terminábamos con `Juego/Juego/archivo.exe`.
* **Solución:** Lógica de "Aplanado" en `SecurityManager`. El sistema extrae en un UUID temporal, inspecciona el contenido, y si detecta una carpeta contenedora única, mueve su contenido hacia arriba, eliminando el nivel redundante automáticamente.

## 6. Estancamiento Silencioso (Stall)
* **Contexto:** A veces la velocidad no era baja, sino cero, pero la conexión no se cortaba (Zombie socket).
* **Solución:** Implementación de **Stall Detection**. Si el tiempo transcurrido es > 120s y el promedio de velocidad es < 1 MB/s, se considera conexión muerta y se fuerza el reinicio del ciclo de subida.