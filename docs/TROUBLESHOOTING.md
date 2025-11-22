# 🔧 Solución de Problemas (Troubleshooting)

### 1. Error: `[WinError 5] Access is denied`
**Síntoma:** El programa falla al intentar borrar un archivo temporal `.7z` después de subirlo o descargarlo.
**Causa:** Windows o el Antivirus mantienen el archivo "tomado" o escaneándolo milisegundos después de que 7-Zip lo cierra.
**Solución:** El sistema ya incluye una función `safe_delete` que reintenta el borrado 3 veces con pausas. Si persiste, verifique que su antivirus no esté bloqueando la carpeta `data/temp`.

### 2. Caracteres extraños en Excel (Ã±)
**Síntoma:** Al abrir `index_main.csv` en Excel, las tildes y la 'ñ' se ven mal.
**Solución:** El sistema guarda los CSV usando `utf-8-sig`. Asegúrese de abrir el archivo directamente. Si persiste, use la opción de Excel "Datos -> Obtener datos -> De texto/CSV" y seleccione "Origen de archivo: 65001: Unicode (UTF-8)".

### 3. Rclone no encontrado
**Síntoma:** Error `FileNotFoundError` al iniciar.
**Solución:**
1.  Verifique que la ruta en `.env` bajo `RCLONE_PATH` sea correcta.
2.  Si `RCLONE_PATH` apunta a una carpeta, asegúrese de que `rclone.exe` esté dentro.

### 4. Advertencia de Pandas "FutureWarning"
**Síntoma:** Texto rojo en la consola sobre `DataFrame concatenation`.
**Solución:** Este proyecto ya implementa la corrección (`dropna(how='all')`) en `InventoryManager`. Asegúrese de tener la última versión del código.

### 5. Duplicados no detectados
**Síntoma:** Se sube un archivo que ya existía.
**Causa:** El sistema valida duplicados basándose en la combinación exacta de `Prefijo` + `Nombre Original`.
**Solución:** Si cambió el nombre de la carpeta origen localmente (ej: `DOC/Factura` a `DOC/Factura_Final`), el sistema lo tratará como un archivo nuevo. Esto es comportamiento esperado.