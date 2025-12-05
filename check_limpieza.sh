#!/bin/bash
# check_limpieza.sh

LOG_FILE="/opt/company/limpieza/logs/latest.log"
ALERT_EMAIL="admin@company.com"

# Verificar uso efectivo de máscaras
MASKS_USED=$(grep -c "máscara:" $LOG_FILE 2>/dev/null || echo "0")
TOTAL_PATHS=$(grep -c "Procesando ruta" $LOG_FILE 2>/dev/null || echo "0")

# Calcular porcentaje de rutas con máscaras
if [ "$TOTAL_PATHS" -gt 0 ]; then
    MASK_PERCENTAGE=$((MASKS_USED * 100 / TOTAL_PATHS))
    
    if [ "$MASK_PERCENTAGE" -lt 50 ]; then
        echo "ALERTA: Solo $MASK_PERCENTAGE% de rutas usan máscaras (recomendado >50%)" | \
            mail -s "Alerta: Bajo uso de máscaras" $ALERT_EMAIL
    fi
fi

# Verificar errores en patrones de máscaras
MASK_ERRORS=$(grep -c "Error en patrón de máscara" $LOG_FILE 2>/dev/null || echo "0")

if [ "$MASK_ERRORS" -gt 0 ]; then
    echo "ALERTA: $MASK_ERRORS errores en patrones de máscaras detectados" | \
        mail -s "Alerta: Errores en máscaras" $ALERT_EMAIL
fi