# Script de Limpieza de Archivos Antiguos

Script automatizado para eliminar archivos antiguos en sistemas locales y remotos (SSH, SFTP, FTP) con configuración flexible y logging detallado.

## Características

- ✅ **Múltiples protocolos**: Local, SSH, SFTP y FTP
- ✅ **Configuración JSON**: Estructura organizada y fácil de mantener
- ✅ **Credenciales separadas**: Mayor seguridad separando rutas y credenciales
- ✅ **Logging completo**: Registros detallados con timestamps
- ✅ **Soporte para sudo**: Para operaciones que requieren elevación de permisos
- ✅ **Manejo de errores robusto**: Continúa ejecución aunque falle una ruta
- ✅ **Ejecución programada**: Compatible con crontab
- ✅ Compatibilidad multi-Python: Soporte para Python 2.7 y 3.x

## Configuración

### Estructura de archivos

limpieza-archivos/
├── limpieza.py # Script principal
├── config.json # Configuración de RUTAS (NO SUBIR AL GIT)
├── config.json.example # Ejemplo de configuración
├── credenciales.json # CREDENCIALES (NO SUBIR AL GIT)
├── credenciales.json.example # Ejmeplo de credenciales
└── logs/ # Logs automáticos


### Archivo de configuración (config.json)

Crear `config.json` con la siguiente estructura (SOLO rutas):

```json
{
    "conexiones": {
        "servidor_ssh": {
            "tipo": "ssh",
            "necesita_sudo": true,
            "rutas": [
                {"ruta": "/home/usuario/backups/carpeta1", "dias": 10},
                {"ruta": "/home/usuario/backups/carpeta2", "dias": 14}
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

## Instalación

### Requisitos

- Python 3.6 o superior
- Para SSH/SFTP: `paramiko` (opcional)

### Instalación de dependencias

# Para Python 3
pip install paramiko

# Para Python 2.7
pip install paramiko

### Configuración rápida

1. **Clonar o descargar el repositorio**:
```bash
git clone https://github.com/bontivero/limpieza_ficheros.git
cd limpieza-
```

2. **Configurar los archivos:
```bash
cp config.json.example config.json
cp credenciales.json.example credenciales.json
```

3. **Editar la configuración:

- Modificar config.json con tus rutas y días
- Modificar credenciales.json con tus credenciales

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

Estructura de Logs
Los logs se generan automáticamente en el directorio logs/ con formato:
```bash
limpieza_YYYYMMDD_HHMMSS.log
```

Ejemplo de contenido del log:
2024-01-15 14:30:22 - INFO - INICIO del proceso de eliminación de archivos antiguos
2024-01-15 14:30:25 - INFO - Conectando SSH a 192.168.1.100:22 (alias: servidor_ssh)
2024-01-15 14:30:30 - INFO - ELIMINADO (SSH): /home/usuario/backups/archivo_viejo.log
2024-01-15 14:30:35 - INFO - Resumen servidor_ssh: 15 eliminados, 0 errores


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