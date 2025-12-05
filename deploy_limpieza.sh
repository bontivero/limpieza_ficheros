#!/bin/bash
# deploy_limpieza.sh

set -e

# Variables
INSTALL_DIR="/opt/company/limpieza"
USER="limpieza-user"
GROUP="limpieza-group"
PYTHON_BIN=$(which python3 || which python2 || which python)

echo "🚀 Iniciando despliegue del sistema de limpieza..."

# Verificar Python
if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Error: Python no encontrado"
    exit 1
fi
echo "✅ Python detectado: $($PYTHON_BIN --version 2>&1)"

# Crear directorios
sudo mkdir -p $INSTALL_DIR
sudo mkdir -p $INSTALL_DIR/logs
sudo mkdir -p $INSTALL_DIR/examples

# Copiar archivos
sudo cp limpieza.py $INSTALL_DIR/
sudo cp config.json.example $INSTALL_DIR/config.json
sudo cp credenciales.json.example $INSTALL_DIR/credenciales.json
sudo cp mascaras_comunes.txt $INSTALL_DIR/examples/

# Crear ejemplo de configuración con máscaras
sudo cat > $INSTALL_DIR/examples/config_con_mascaras.json << 'EOF'
{
    "conexiones": {
        "ejemplo_local": {
            "tipo": "local",
            "rutas": [
                {
                    "ruta": "/tmp",
                    "dias": 7,
                    "mascara": "*.tmp"
                }
            ]
        }
    }
}
EOF

# Establecer permisos
sudo chown $USER:$GROUP $INSTALL_DIR -R
sudo chmod 755 $INSTALL_DIR/limpieza.py
sudo chmod 600 $INSTALL_DIR/credenciales.json
sudo chmod 644 $INSTALL_DIR/config.json

# Configurar crontab
CRON_JOB="0 2 * * * $PYTHON_BIN $INSTALL_DIR/limpieza.py $INSTALL_DIR/config.json"
echo "$CRON_JOB" | sudo tee -a /etc/crontab > /dev/null

echo "✅ Despliegue completado en $INSTALL_DIR"
echo "📝 Ejemplos de máscaras disponibles en: $INSTALL_DIR/examples/mascaras_comunes.txt"