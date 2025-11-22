# 🔧 Solución de Problemas (Troubleshooting)

### 1. Mensaje: "Velocidad baja... Reiniciando routing"
**Síntoma:** La subida se detiene y vuelve a empezar varias veces.
**Causa:** Esta es una **función**, no un error. El sistema ("Smart Upload") detectó que su conexión a la nube era inestable o lenta (< 8-15 MB/s) y está reiniciando la conexión para forzar una mejor ruta de internet.
**Solución:** Deje que el sistema trabaje. Si falla 3 veces, el último intento se dejará correr hasta el final.

### 2. Error: `[WinError 5] Access is denied`
**Síntoma:** Fallo al borrar archivos temporales.
**Causa:** Bloqueo de archivo por Antivirus o el Sistema Operativo.
**Solución:** El sistema incluye la función `safe_delete` que reintenta el borrado hasta 10 veces con pausas progresivas. Si ve este mensaje, es informativo; el sistema limpiará el archivo en la siguiente ejecución.

### 3. Caracteres extraños en Excel (Ã±)
**Síntoma:** Tildes o Ñ mal visualizados en el CSV.
**Solución:** El sistema utiliza codificación `utf-8-sig`. Excel debería abrirlo automáticamente bien. Si no, use "Datos -> Obtener datos -> De Texto/CSV -> UTF-8".

### 4. Rclone no encontrado
**Solución:** Verifique que `RCLONE_PATH` en su archivo `.env` apunte correctamente a la carpeta donde está `rclone.exe`.

### 5. Archivos Duplicados
**Síntoma:** El sistema dice "Saltando duplicado".
**Causa:** El sistema detecta que la combinación de `Prefijo` + `Nombre de Carpeta` ya existe en el índice para evitar redundancia.
**Solución:** Si desea subir una nueva versión, cambie el nombre de la carpeta origen (ej: `Carpeta_v2`).