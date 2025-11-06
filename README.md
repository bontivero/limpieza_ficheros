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

## Instalación

### Requisitos

- Python 3.6 o superior
- Para SSH/SFTP: `paramiko` (opcional)

### Configuración rápida

1. **Clonar o descargar el repositorio**:
```bash
git clone https://github.com/bontivero/limpieza_ficheros.git
cd limpieza-archivos

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