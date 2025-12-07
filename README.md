# Script de Limpieza de Archivos Antiguos

Script automatizado para eliminar archivos antiguos en sistemas locales y remotos (SSH, SFTP, FTP) con configuración flexible, filtrado por máscara de archivos, logging detallado y diagnóstico avanzado. Compatible con Python 2.x y 3.x.

## Características

- ✅ **Múltiples protocolos**: Local, SSH, SFTP y FTP
- ✅ **Filtrado por máscara**: Soporte para patrones fnmatch (ej: `ldr_*`, `*.log`, `*backup*`)
- ✅ **Python 2.x/3.x compatible**: Funciona en versiones antiguas y modernas de Python
- ✅ Diagnóstico avanzado: Verificación preventiva de todos los accesos
- ✅ **Configuración JSON**: Estructura organizada y fácil de mantener
- ✅ **Credenciales separadas**: Mayor seguridad separando rutas y credenciales
- ✅ **Logging completo**: Registros detallados con timestamps y estadísticas
- ✅ **Soporte para sudo**: Para operaciones que requieren elevación de permisos
- ✅ **Manejo de errores robusto**: Continúa ejecución aunque falle una ruta
- ✅ **Ejecución programada**: Compatible con crontab y task schedulers

## Configuración

### Estructura de archivos

limpieza-archivos/
├── limpieza.py                 # Script principal (Python 2/3 compatible)
├── config.json                 # Configuración de RUTAS (NO SUBIR AL GIT)
├── config.json.example         # Ejemplo de configuración con máscaras
├── credenciales.json           # CREDENCIALES (NO SUBIR AL GIT)
├── credenciales.json.example   # Ejemplo de credenciales 
├── diagnostico_acceso.py       # Script de diagnóstico de acceso (Python 2/3 compatible)
├── logs/                       # Directorio de logs automáticos
├── examples/                   # Ejemplos adicionales
│   ├── config_con_mascaras.json
│   └── mascaras_comunes.txt
└── README.md                # Este archivo


### Archivo de configuración (config.json)

Crear `config.json` con la siguiente estructura (SOLO rutas):

```json
{
    "conexiones": {
        "servidor_ssh": {
            "tipo": "ssh",
            "necesita_sudo": true,
            "rutas": [
                {"ruta": "/home/usuario/backups/carpeta1", "dias": 10, "mascara": "app_*.log"},
                {"ruta": "/home/usuario/backups/carpeta2", "dias": 14, "mascara": "backup_*.tar.gz"}
            ]
        },
        "local_backups": {
            "tipo": "local",
            "rutas": [
                {"ruta": "/var/backups/aplicacion", "dias": 30}
            ]
        }
    }
}
```

## 📊 Filtrado por Máscara (Nueva Función)

La nueva funcionalidad de **máscara** permite filtrar archivos por nombre usando patrones tipo shell:

| Patrón | Descripción | Ejemplos |
|--------|-------------|----------|
| `ldr_*` | Archivos que comienzan con "ldr_" | `ldr_report.pdf`, `ldr_data.csv` |
| `*.log` | Archivos con extensión .log | `app.log`, `error.log` |
| `*backup*` | Archivos que contienen "backup" | `daily_backup.zip`, `backup_2024.tar` |
| `data_???` | "data_" + exactamente 3 caracteres | `data_001.csv`, `data_xyz.txt` |
| `[0-9]*.csv` | Archivos CSV que comienzan con dígitos | `001_data.csv`, `2024_report.csv` |


## Instalación

### Requisitos

- Python 2.7 o Python 3.6+ (compatible con ambas versiones)
- Para SSH/SFTP: paramiko (opcional, solo si se usan conexiones SSH/SFTP)

### Instalación de dependencias

# Para Python 3
pip install paramiko

# Para Python 2.7
pip install paramiko

# Verificar instalación
python -c "import paramiko; print('Paramiko instalado correctamente')"

### Configuración rápida

1. **Clonar o descargar el repositorio**:
```bash
git clone https://github.com/bontivero/limpieza_ficheros.git
cd limpieza-archivos
```

2. **Configurar los archivos:
```bash
cp config.json.example config.json
cp credenciales.json.example credenciales.json
```

3. **Editar la configuración:

- Editar config.json con tus rutas, días y máscaras (opcional)
- Editar credenciales.json con tus credenciales de acceso

4. **Establecer permisos seguros:
```bash
chmod 600 credenciales.json
chmod 755 limpieza.py
```

## Ejecución Manual

```bash
# Uso básico
python limpieza.py config.json

# Especificar archivo de credenciales
python limpieza.py config.json credenciales.json

# Con Python 2.7
python2 limpieza.py config.json

# Diagnóstico completo (todos los protocolos)
python diagnostico_acceso.py

# Con archivos específicos
python diagnostico_acceso.py --config mi_config.json --credenciales mis_credenciales.json

# Solo un tipo específico
python diagnostico_acceso.py --tipo ssh

# Solo una conexión específica
python diagnostico_acceso.py --alias mi_servidor_ftp

# Modo verbose
python diagnostico_acceso.py --verbose

# Ayuda completa
python diagnostico_acceso.py --help
```

## Ejecución programada con Crontab

```bash
# Editar crontab
crontab -e

# Ejecutar diariamente a las 2 AM
0 2 * * * /usr/bin/python /ruta/limpieza-archivos/limpieza.py /ruta/limpieza-archivos/config.json

# Ejecutar cada 6 horas
0 */6 * * * /usr/bin/python /ruta/limpieza-archivos/limpieza.py /ruta/limpieza-archivos/config.json
```

Windows (Task Scheduler)
- Abrir Task Scheduler
- Crear nueva tarea básica
- Programar ejecución diaria
- Acción: "Start a program"
- Programa: python.exe (o python3.exe)
- Argumentos: "C:\ruta\limpieza-archivos\limpieza.py" "C:\ruta\limpieza-archivos\config.json"
- Configurar carpeta de inicio: C:\ruta\limpieza-archivos

## Configuración de Sudo en servidores remotos

Cuando se usa "necesita_sudo": true en conexiones SSH, es necesario configurar el servidor remoto para permitir ejecución de comandos sudo sin TTY

¿Cuándo usar necesita_sudo?
- false (recomendado): Cuando el usuario tiene permisos de escritura en las rutas
- true: Cuando se necesitan permisos de root para eliminar archivos (ej: /var/log/, /tmp/system/)


## Solución de Problemas

Error: "paramiko no está instalado"
```bash
pip install paramiko
```

Paramiko no está instalado
- pip install paramiko (Python 3) o pip install 'paramiko<3.0.0' (Python 2.7)

Error de permisos en SSH con sudo
- Verificar configuración sudoers en el servidor remoto
- Confirmar que necesita_sudo esté en true
- Probar conexión manualmente: ssh usuario@servidor "sudo ls /ruta"

Error de conexión FTP
- Verificar que el servidor FTP esté activo
- Confirmar puerto (normalmente 21)
- Verificar credenciales

Los logs no se generan
- Verificar que el directorio logs/ exista y tenga permisos de escritura
- Verificar permisos del script: chmod 755 limpieza.py

Error en patrón de máscara
- Verificar sintaxis fnmatch, probar con 
```bash
python -c "import fnmatch; print(fnmatch.fnmatch('test.log', '*.log'))"
```

Script no ejecuta en Python 2.7
- Verificar que paramiko sea compatible: pip install 'paramiko<3.0.0'

Estructura de Logs
Los logs se generan automáticamente en el directorio logs/ con formato YYYYMMDD_HHMMSS:
logs/
├── limpieza_20251115_143022.log
├── limpieza_20251116_020001.log
└── ...

Ejemplo de contenido del log:

2024-01-15 14:30:22 - INFO - INICIO del proceso de eliminación de archivos antiguos
2024-01-15 14:30:25 - INFO - Procesando conexión: servidor_ssh (SSH)
2024-01-15 14:30:26 - INFO -   Procesando ruta SSH: /var/log - 30 días - máscara: 'app_*.log'
2024-01-15 14:30:30 - INFO - Encontrados 15 archivos con máscara 'app_*.log' para eliminar
2024-01-15 14:30:32 - INFO - ELIMINADO (SSH): /var/log/app_20231201.log
2024-01-15 14:30:45 - INFO - Resumen ruta /var/log (máscara: 'app_*.log'): 15 eliminados, 0 errores
2024-01-15 14:31:00 - INFO - RESUMEN FINAL: Archivos eliminados: 42, Archivos con error: 0

Monitoreo de logs

```bash
# Ver últimos logs
tail -f logs/limpieza_*.log

# Buscar errores
grep -i "error" logs/*.log

# Contar archivos eliminados por máscara
grep "máscara:" logs/limpieza_*.log | sort | uniq -c

# Espacio liberado estimado (requiere script adicional)
python -c "
import os, re
total = 0
for line in open('logs/limpieza_20240115_143022.log'):
    if 'ELIMINADO' in line:
        # Extraer ruta y estimar tamaño (ejemplo simplificado)
        pass
print(f'Espacio liberado estimado: {total} bytes')
"
```

## Licencia

Distribuido bajo la Licencia MIT. Consulta `LICENSE` para más información.

---

**Resumen de la licencia MIT:**
- ✅ Puedes usar, copiar y modificar el software libremente
- ✅ Puedes distribuirlo en proyectos privados o comerciales
- ✅ Solo debes incluir el aviso de copyright original
- ❌ No hay garantía - el software se proporciona "tal cual"
- ❌ Los autores no son responsables de ningún daño

Para más detalles, consulta el archivo [LICENSE](LICENSE).

🤝 Contribuir

- Haz fork del repositorio
- Crea una rama para tu feature (git checkout -b feature/NuevaFuncionalidad)
- Commit tus cambios (git commit -am 'Agrega nueva funcionalidad')
- Push a la rama (git push origin feature/NuevaFuncionalidad)
- Abre un Pull Request

📞 Soporte

- Issues: Reportar bugs en GitHub Issues
- Discusiones: Preguntas y ayuda en GitHub Discussions
- Documentación: Consultar este README y ejemplos en /examples/

Nota sobre Python 2.7: Aunque el script es compatible con Python 2.7, esta versión llegó al final de su vida útil en 2020. Se recomienda migrar a Python 3.x cuando sea posible para seguridad y soporte continuo.