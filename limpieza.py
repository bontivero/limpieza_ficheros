#!/usr/bin/env python3
"""
Script para eliminar archivos antiguos basado en un archivo de configuración JSON.

Este script lee un archivo de configuración JSON que especifica rutas (locales, SSH, SFTP o FTP), 
tiempos en días para eliminar archivos recursivamente y máscaras opcionales para filtrar por nombre. 
Las credenciales se almacenan en un archivo separado.

Estructura del archivo de rutas y configuración (config.json) explicado y ejemplificado
en config.json.example

Estructura del archivo de credenciales de acceso (credenciales.json) explicado y ejemplificado
en credenciales.json.example

La máscara permite filtrar archivos por nombre usando patrones fnmatch:
- "ldr_*"    - archivos que comienzan con "ldr_"
- "*.log"    - archivos con extensión .log
- "*backup*" - archivos que contienen "backup"
- "data_???" - archivos que comienzan con "data_" seguido de 3 caracteres
- Si no se especifica máscara, se procesan todos los archivos

Funcionalidades:
- Eliminación recursiva de archivos antiguos en rutas locales
- Conexión SSH para ejecución remota de comandos
- Conexión SFTP para manipulación remota de archivos
- Conexión FTP para servidores FTP tradicionales
- Log detallado con resumen de operaciones
- Manejo de errores con registro de archivos problemáticos
- Soporte para sudo en conexiones SSH
- Una sola conexión por servidor para múltiples rutas

Uso:
    python limpieza.py config.json [credenciales.json]

Nota: Para conexiones SSH/SFTP se requiere la librería paramiko.
"""

import os
import sys
import time
import datetime
import logging
import ftplib
import fnmatch
import json
from pathlib import Path
from urllib.parse import urlparse

PARAMIKO_DISPONIBLE = False
try:
    import paramiko
    PARAMIKO_DISPONIBLE = True
except ImportError:
    pass

def configurar_logging():
    """
    Configura el sistema de logging para el script.
    
    Crea el directorio 'logs' si no existe y configura un archivo de log
    con timestamp en el nombre. El log incluye timestamp, nivel y mensaje.
    
    Returns:
        str: Ruta del archivo de log creado
    """
    script_dir = Path(__file__).parent.absolute()
    logs_dir = script_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"limpieza_{timestamp}.log"
    log_path = logs_dir / log_filename
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return str(log_path)

def cargar_configuracion(config_file):
    """
    Carga la configuración desde un archivo JSON.
    
    Args:
        config_file (str): Ruta al archivo de configuración JSON
        
    Returns:
        dict: Configuración cargada
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        logging.info(f"Configuración cargada desde: {config_file}")
        return config
        
    except FileNotFoundError:
        logging.error(f"Archivo de configuración no encontrado: {config_file}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Error parseando archivo de configuración: {e}")
        raise
    except Exception as e:
        logging.error(f"Error cargando configuración: {e}")
        raise

def cargar_credenciales(credenciales_file=None):
    """
    Carga las credenciales desde un archivo JSON.
    
    Args:
        credenciales_file (str): Ruta al archivo de credenciales
        
    Returns:
        dict: Diccionario con las credenciales cargadas o vacío si hay error
    """
    if credenciales_file is None:
        ubicaciones = [
            Path(__file__).parent / "credenciales.json",
            Path("/etc/limpieza/credenciales.json"),
            Path.home() / ".limpieza_credenciales.json"
        ]
        
        for ubicacion in ubicaciones:
            if ubicacion.exists():
                credenciales_file = ubicacion
                break
        else:
            logging.warning("No se encontró archivo de credenciales")
            return {}
    
    try:
        with open(credenciales_file, 'r', encoding='utf-8') as f:
            credenciales = json.load(f)
        
        logging.info(f"Credenciales cargadas desde: {credenciales_file}")
        return credenciales
        
    except FileNotFoundError:
        logging.error(f"Archivo de credenciales no encontrado: {credenciales_file}")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"Error parseando archivo de credenciales: {e}")
        return {}
    except Exception as e:
        logging.error(f"Error cargando credenciales: {e}")
        return {}

def combinar_configuracion(config, credenciales):
    """
    Combina la configuración con las credenciales.
    
    Args:
        config (dict): Configuración de rutas
        credenciales (dict): Credenciales de acceso
        
    Returns:
        dict: Configuración combinada
    """
    conexiones_combinadas = {}
    conexiones_config = config.get('conexiones', {})

    if not conexiones_config:
        logging.error("No se encontraron conexiones en la configuración")
        return {}
    
    for alias, conexion_config in conexiones_config.items():
        if conexion_config.get('tipo') == 'local':
            conexiones_combinadas[alias] = conexion_config
            conexiones_combinadas[alias]['alias'] = alias
            continue
            
        if alias not in credenciales:
            logging.error(f"No se encontraron credenciales para el alias: {alias}")
            continue
            
        conexion_combinada = {**conexion_config, **credenciales[alias]}
        conexion_combinada['alias'] = alias
        conexiones_combinadas[alias] = conexion_combinada
        
        campos_requeridos = ['tipo', 'host', 'usuario', 'contrasena']
        for campo in campos_requeridos:
            if campo not in conexion_combinada:
                logging.error(f"Falta campo requerido '{campo}' en conexión: {alias}")
                break
    
    return conexiones_combinadas

def verificar_dependencias(conexiones):
    """
    Verifica que las dependencias necesarias estén disponibles según la configuración.
    
    Args:
        conexiones (dict): Diccionario de configuraciones a procesar
        
    Returns:
        bool: True si todas las dependencias están disponibles, False si faltan
    """
    necesita_paramiko = any(
        conexion['tipo'] in ['ssh', 'sftp'] 
        for conexion in conexiones.values()
        )
    
    if necesita_paramiko and not PARAMIKO_DISPONIBLE:
        logging.error("Se requieren conexiones SSH/SFTP pero paramiko no está instalado")
        logging.error("Instale paramiko con: pip install paramiko")
        logging.error("O elimine las configuraciones SSH del archivo de configuración")
        return False
    
    return True

def eliminar_archivos_locales(ruta_base, dias, mascara=None):
    """
    Elimina archivos locales más antiguos que los días especificados.
    
    Args:
        ruta_base (str): Ruta local del directorio
        dias (int): Días de antigüedad máxima
        mascara (str, opcional): Patrón para filtrar nombres de archivo
        
    Returns:
        tuple: (archivos_eliminados, archivos_con_error)
    """
    limite_tiempo = time.time() - (dias * 86400)
    archivos_eliminados = 0
    archivos_con_error = 0
    archivos_procesados = 0

    try:
        for root, dirs, files in os.walk(ruta_base):
            for file in files:
                
                if mascara and not fnmatch.fnmatch(file, mascara):
                    continue
                
                ruta_completa = os.path.join(root, file)
                archivos_procesados += 1

                try:
                    mtime = os.path.getmtime(ruta_completa)

                    if mtime < limite_tiempo:
                        try:
                            os.remove(ruta_completa)
                            archivos_eliminados += 1
                            logging.info(f"ELIMINADO (local): {ruta_completa}")
                        except OSError as e:
                            archivos_con_error += 1
                            logging.error(f"ERROR eliminando {ruta_completa}: {str(e)}")
                except OSError as e:
                    archivos_con_error += 1
                    logging.error(f"ERROR accediendo a {ruta_completa}: {str(e)}")
        
        if mascara:
            logging.info(f"Resumen LOCAL {ruta_base} (máscara: '{mascara}'): {archivos_procesados} procesados, {archivos_eliminados} eliminados, {archivos_con_error} errores")
        else:
            logging.info(f"Resumen LOCAL {ruta_base}: {archivos_procesados} procesados, {archivos_eliminados} eliminados, {archivos_con_error} errores")
        
    except Exception as e:
        logging.error(f"ERROR procesando ruta local {ruta_base}: {str(e)}")
        archivos_con_error += 1

    return archivos_eliminados, archivos_con_error

def ejecutar_comando_ssh(cliente_ssh, comando, descripcion):
    """
    Ejecuta un comando SSH y retorna la salida y el estado.
    
    Args:
        cliente_ssh: Cliente SSH de Paramiko
        comando (str): Comando a ejecutar
        descripcion (str): Descripción para logging
        
    Returns:
        tuple: (salida, errores, exit_status)
    """
    try:
        stdin, stdout, stderr = cliente_ssh.exec_command(comando)
        exit_status = stdout.channel.recv_exit_status()
        salida = stdout.read().decode('utf-8').strip()
        errores = stderr.read().decode('utf-8').strip()
        
        if exit_status != 0:
            logging.warning(f"Comando '{descripcion}' falló (estado {exit_status}): {errores}")
        else:
            logging.debug(f"Comando '{descripcion}' ejecutado exitosamente")
            
        return salida, errores, exit_status
        
    except Exception as e:
        logging.error(f"Error ejecutando comando '{descripcion}': {str(e)}")
        return "", str(e), 1

def eliminar_archivos_ssh(conexion):
    """
    Elimina archivos remotos vía SSH más antiguos que los días especificados.
    Usa una sola conexión para todas las rutas del servidor.
    
    Args:
        conexion (dict): Configuración de conexión SSH
        
    Returns:
        tuple: (archivos_eliminados_totales, archivos_con_error_totales)
    """
    if not PARAMIKO_DISPONIBLE:
        logging.error("No se puede procesar configuración SSH: paramiko no está instalado")
        return 0, 1

    archivos_eliminados_totales = 0
    archivos_con_error_totales = 0
    necesita_sudo = conexion.get('necesita_sudo', False)
    comando_sudo = "sudo " if necesita_sudo else ""

    try:
        cliente_ssh = paramiko.SSHClient()
        cliente_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        logging.info(f"Conectando SSH a {conexion['host']}:{conexion.get('puerto', 22)} (alias: {conexion['alias']})")
        cliente_ssh.connect(
            hostname=conexion['host'],
            port=conexion.get('puerto', 22),
            username=conexion['usuario'],
            password=conexion['contrasena'],
            timeout=30
        )
        
        for ruta_config in conexion['rutas']:
            ruta = ruta_config['ruta']
            dias = ruta_config['dias']
            mascara = ruta_config.get('mascara')
            
            if mascara:
                logging.info(f"  Procesando ruta SSH: {ruta} - {dias} días - máscara: '{mascara}'")
            else:
                logging.info(f"  Procesando ruta SSH: {ruta} - {dias} días")
            
            comando_test = f"{comando_sudo}ls {ruta}"
            salida, errores, estado = ejecutar_comando_ssh(cliente_ssh, comando_test, f"verificar ruta {ruta}")
            
            if estado != 0:
                logging.error(f"No se puede acceder a la ruta {ruta}: {errores}")
                archivos_con_error_totales += 1
                continue
            
            if mascara:
                comando_find = f"{comando_sudo}find {ruta} -type f -name '{mascara}' -mtime +{dias} -print"
            else:
                comando_find = f"{comando_sudo}find {ruta} -type f -mtime +{dias} -print"
                
            salida, errores, estado = ejecutar_comando_ssh(cliente_ssh, comando_find, f"buscar archivos en {ruta}")
            
            if estado != 0 and "No such file or directory" not in errores:
                logging.error(f"Error buscando archivos en {ruta}: {errores}")
            
            archivos_a_eliminar = [archivo for archivo in salida.split('\n') if archivo.strip()]
            
            if not archivos_a_eliminar:
                if mascara:
                    logging.info(f"No se encontraron archivos con máscara '{mascara}' para eliminar en {ruta} (más antiguos de {dias} días)")
                else:
                    logging.info(f"No se encontraron archivos para eliminar en {ruta} (más antiguos de {dias} días)")
                continue
            
            logging.info(f"Encontrados {len(archivos_a_eliminar)} archivos para eliminar en {ruta}")
            
            archivos_eliminados_ruta = 0
            archivos_con_error_ruta = 0
            
            for archivo in archivos_a_eliminar:
                archivo = archivo.strip()
                if not archivo:
                    continue
                    
                try:
                    comando_eliminar = f"{comando_sudo}rm -f '{archivo}'"
                    salida, errores, estado = ejecutar_comando_ssh(cliente_ssh, comando_eliminar, f"eliminar {archivo}")
                    
                    if estado == 0:
                        archivos_eliminados_ruta += 1
                        archivos_eliminados_totales += 1
                        logging.info(f"ELIMINADO (SSH): {archivo}")
                    else:
                        archivos_con_error_ruta += 1
                        archivos_con_error_totales += 1
                        logging.error(f"ERROR eliminando {archivo}: {errores}")
                        
                except Exception as e:
                    archivos_con_error_ruta += 1
                    archivos_con_error_totales += 1
                    logging.error(f"ERROR procesando {archivo}: {str(e)}")
            
            if mascara:
                logging.info(f"  Resumen ruta {ruta} (máscara: '{mascara}'): {archivos_eliminados_ruta} eliminados, {archivos_con_error_ruta} errores")
            else:
                logging.info(f"  Resumen ruta {ruta}: {archivos_eliminados_ruta} eliminados, {archivos_con_error_ruta} errores")
        
        cliente_ssh.close()
        
    except paramiko.AuthenticationException:
        logging.error(f"ERROR SSH: Autenticación fallida para {conexion['usuario']}@{conexion['host']}")
        archivos_con_error_totales += len(conexion['rutas'])
    except paramiko.SSHException as e:
        logging.error(f"ERROR SSH: {str(e)}")
        archivos_con_error_totales += len(conexion['rutas'])
    except Exception as e:
        logging.error(f"ERROR conexión SSH a {conexion['host']}:{conexion.get('puerto', 22)}: {str(e)}")
        archivos_con_error_totales += len(conexion['rutas'])

    return archivos_eliminados_totales, archivos_con_error_totales

def eliminar_archivos_sftp(conexion):
    """
    Elimina archivos remotos vía SFTP más antiguos que los días especificados.
    Usa una sola conexión para todas las rutas del servidor.
    
    Args:
        conexion (dict): Configuración de conexión SFTP
        
    Returns:
        tuple: (archivos_eliminados_totales, archivos_con_error_totales)
    """
    if not PARAMIKO_DISPONIBLE:
        logging.error("No se puede procesar configuración SFTP: paramiko no está instalado")
        return 0, 1

    archivos_eliminados_totales = 0
    archivos_con_error_totales = 0

    try:
        # Conectar al servidor SFTP (una sola vez)
        transporte = paramiko.Transport((conexion['host'], conexion.get('puerto', 22)))
        transporte.connect(username=conexion['usuario'], password=conexion['contrasena'])
        
        sftp = paramiko.SFTPClient.from_transport(transporte)
        logging.info(f"Conectado SFTP a {conexion['host']}:{conexion.get('puerto', 22)} (alias: {conexion['alias']})")
        
        def procesar_directorio_sftp(ruta_remota, dias, mascara=None):
            """
            Función interna para procesar recursivamente un directorio SFTP.
            """
            nonlocal archivos_eliminados_totales, archivos_con_error_totales
            limite_tiempo = time.time() - (dias * 86400)
            
            try:
                for atributo in sftp.listdir_attr(ruta_remota):
                    ruta_completa = f"{ruta_remota}/{atributo.filename}".replace('//', '/')
                    
                    if atributo.filename in ['.', '..']:
                        continue
                    
                    try:
                        sftp.listdir(ruta_completa)
                        procesar_directorio_sftp(ruta_completa, dias, mascara)
                    except:
                        if mascara:
                            import fnmatch
                            if not fnmatch.fnmatch(atributo.filename, mascara):
                                continue
                                
                        try:
                            mtime = atributo.st_mtime
                            
                            if mtime < limite_tiempo:
                                sftp.remove(ruta_completa)
                                archivos_eliminados_totales += 1
                                logging.info(f"ELIMINADO (SFTP): {ruta_completa}")
                            else:
                                logging.debug(f"Conservado (SFTP): {ruta_completa}")
                        except Exception as e:
                            archivos_con_error_totales += 1
                            logging.error(f"ERROR procesando {ruta_completa} (SFTP): {str(e)}")
                            
            except Exception as e:
                archivos_con_error_totales += 1
                logging.error(f"ERROR en directorio {ruta_remota} (SFTP): {str(e)}")
        
        for ruta_config in conexion['rutas']:
            ruta = ruta_config['ruta']
            dias = ruta_config['dias']
            mascara = ruta_config.get('mascara')
            
            if mascara:
                logging.info(f"  Procesando ruta SFTP: {ruta} - {dias} días - máscara: '{mascara}'")
            else:
                logging.info(f"  Procesando ruta SFTP: {ruta} - {dias} días")
            
            try:
                sftp.listdir(ruta)
                logging.info(f"  Ruta verificada: {ruta}")
                
                archivos_antes = archivos_eliminados_totales
                errores_antes = archivos_con_error_totales
                
                procesar_directorio_sftp(ruta, dias, mascara)
                
                eliminados_ruta = archivos_eliminados_totales - archivos_antes
                errores_ruta = archivos_con_error_totales - errores_antes
                
                if mascara:
                    logging.info(f"  Resumen ruta {ruta} (máscara: '{mascara}'): {eliminados_ruta} eliminados, {errores_ruta} errores")
                else:
                    logging.info(f"  Resumen ruta {ruta}: {eliminados_ruta} eliminados, {errores_ruta} errores")
                
            except Exception as e:
                logging.error(f"La ruta no existe o no es accesible: {ruta} - Error: {e}")
                archivos_con_error_totales += 1
        
        sftp.close()
        transporte.close()
        
    except paramiko.AuthenticationException:
        logging.error(f"ERROR SFTP: Autenticación fallida para {conexion['usuario']}@{conexion['host']}")
        archivos_con_error_totales += len(conexion['rutas'])
    except Exception as e:
        logging.error(f"ERROR conexión SFTP a {conexion['host']}:{conexion.get('puerto', 22)}: {str(e)}")
        archivos_con_error_totales += len(conexion['rutas'])

    return archivos_eliminados_totales, archivos_con_error_totales

def eliminar_archivos_ftp(conexion):
    """
    Elimina archivos remotos vía FTP más antiguos que los días especificados.
    Usa una sola conexión para todas las rutas del servidor.
    
    Args:
        conexion (dict): Configuración de conexión FTP
        
    Returns:
        tuple: (archivos_eliminados_totales, archivos_con_error_totales)
    """
    archivos_eliminados_totales = 0
    archivos_con_error_totales = 0

    try:
        logging.info(f"Conectando FTP a {conexion['host']}:{conexion.get('puerto', 21)} (alias: {conexion['alias']})")
        ftp = ftplib.FTP()
        ftp.connect(conexion['host'], conexion.get('puerto', 21), timeout=30)
        ftp.login(conexion['usuario'], conexion['contrasena'])
        
        def procesar_directorio_ftp(path, dias, mascara=None):
            """
            Función interna para procesar recursivamente un directorio FTP.
            """
            nonlocal archivos_eliminados_totales, archivos_con_error_totales
            limite_tiempo = time.time() - (dias * 86400)
            
            try:
                archivos = []
                ftp.retrlines(f'LIST {path}', archivos.append)
                
                for linea in archivos:
                    partes = linea.split()
                    if len(partes) < 9:
                        continue
                    
                    nombre = ' '.join(partes[8:])
                    if nombre in ['.', '..']:
                        continue
                    
                    ruta_completa = f"{path}/{nombre}" if path else nombre
                    
                    if linea.startswith('d'):
                        procesar_directorio_ftp(ruta_completa, dias, mascara)
                    else:
                        if mascara:
                            import fnmatch
                            if not fnmatch.fnmatch(nombre, mascara):
                                continue
                                
                        try:
                            resp = ftp.sendcmd(f"MDTM {ruta_completa}")
                            if resp.startswith('213'):
                                mtime_str = resp[4:].strip()
                                mtime = time.mktime(time.strptime(mtime_str, '%Y%m%d%H%M%S'))
                                
                                if mtime < limite_tiempo:
                                    ftp.delete(ruta_completa)
                                    archivos_eliminados_totales += 1
                                    logging.info(f"ELIMINADO (FTP): {ruta_completa}")
                        except ftplib.error_perm as e:
                            logging.warning(f"No se pudo obtener fecha de {ruta_completa} (FTP): {e}")
                        except Exception as e:
                            archivos_con_error_totales += 1
                            logging.error(f"ERROR procesando {ruta_completa} (FTP): {str(e)}")
                            
            except Exception as e:
                archivos_con_error_totales += 1
                logging.error(f"ERROR en directorio {path} (FTP): {str(e)}")
        
        for ruta_config in conexion['rutas']:
            ruta = ruta_config['ruta']
            dias = ruta_config['dias']
            mascara = ruta_config.get('mascara')
            
            if mascara:
                logging.info(f"  Procesando ruta FTP: {ruta} - {dias} días - máscara: '{mascara}'")
            else:
                logging.info(f"  Procesando ruta FTP: {ruta} - {dias} días")
            
            try:
                ftp.cwd(ruta)
                archivos_antes = archivos_eliminados_totales
                errores_antes = archivos_con_error_totales
                
                procesar_directorio_ftp('', dias, mascara)
                
                eliminados_ruta = archivos_eliminados_totales - archivos_antes
                errores_ruta = archivos_con_error_totales - errores_antes
                
                if mascara:
                    logging.info(f"  Resumen ruta {ruta} (máscara: '{mascara}'): {eliminados_ruta} eliminados, {errores_ruta} errores")
                else:
                    logging.info(f"  Resumen ruta {ruta}: {eliminados_ruta} eliminados, {errores_ruta} errores")
                
            except Exception as e:
                logging.error(f"La ruta no existe o no es accesible: {ruta} - Error: {e}")
                archivos_con_error_totales += 1
        
        ftp.quit()
        
    except ftplib.all_errors as e:
        logging.error(f"ERROR FTP: {str(e)}")
        archivos_con_error_totales += len(conexion['rutas'])
    except Exception as e:
        logging.error(f"ERROR conexión FTP a {conexion['host']}:{conexion.get('puerto', 21)}: {str(e)}")
        archivos_con_error_totales += len(conexion['rutas'])

    return archivos_eliminados_totales, archivos_con_error_totales

def procesar_conexion(alias, conexion):
    """
    Procesa una conexión completa con todas sus rutas usando una sola conexión.
    
    Args:
        alias (str): Alias de la conexión
        conexion (dict): Configuración completa de la conexión
        
    Returns:
        tuple: (archivos_eliminados, archivos_con_error)
    """
    logging.info(f"Procesando conexión: {alias} ({conexion['tipo'].upper()})")
    
    try:
        if conexion['tipo'] == 'local':
            # Para local, procesamos cada ruta individualmente
            archivos_eliminados_totales = 0
            archivos_con_error_totales = 0
            
            for ruta_config in conexion['rutas']:
                ruta = ruta_config['ruta']
                dias = ruta_config['dias']
                mascara = ruta_config.get('mascara')
                
                if mascara:
                    logging.info(f"  Ruta: {ruta} - {dias} días - máscara: '{mascara}'")
                else:
                    logging.info(f"  Ruta: {ruta} - {dias} días")
                    
                eliminados, errores = eliminar_archivos_locales(ruta, dias, mascara)
                archivos_eliminados_totales += eliminados
                archivos_con_error_totales += errores
                
                if mascara:
                    logging.info(f"  Resumen ruta (máscara: '{mascara}'): {eliminados} eliminados, {errores} errores")
                else:
                    logging.info(f"  Resumen ruta: {eliminados} eliminados, {errores} errores")
                
            return archivos_eliminados_totales, archivos_con_error_totales
            
        elif conexion['tipo'] == 'ssh':
            return eliminar_archivos_ssh(conexion)
            
        elif conexion['tipo'] == 'sftp':
            return eliminar_archivos_sftp(conexion)
            
        elif conexion['tipo'] == 'ftp':
            return eliminar_archivos_ftp(conexion)
            
        else:
            logging.error(f"Tipo de conexión desconocido: {conexion['tipo']}")
            return 0, len(conexion['rutas'])
            
    except Exception as e:
        logging.error(f"ERROR procesando conexión {alias}: {str(e)}")
        return 0, len(conexion['rutas'])

def eliminar_archivos_antiguos(config_file, credenciales_file=None):
    """
    Función principal que elimina archivos antiguos basándose en la configuración.
    
    Args:
        config_file (str): Ruta al archivo de configuración
        credenciales_file (str): Ruta al archivo de credenciales (opcional)
    """
    log_path = configurar_logging()
    logging.info("=" * 60)
    logging.info("INICIO del proceso de eliminación de archivos antiguos")
    logging.info(f"Log guardado en: {log_path}")
    
    try:
        # Cargar configuración y credenciales
        config = cargar_configuracion(config_file)
        credenciales = cargar_credenciales(credenciales_file)
        
        # Combinar configuración con credenciales
        conexiones = combinar_configuracion(config, credenciales)
        
        if not conexiones:
            logging.error("No hay conexiones válidas para procesar")
            return
        
        # Informar sobre disponibilidad de funcionalidades
        if PARAMIKO_DISPONIBLE:
            logging.info("SSH/SFTP: Disponible (paramiko instalado)")
        else:
            logging.info("SSH/SFTP: No disponible (paramiko no instalado)")
        
        logging.info(f"Total de conexiones a procesar: {len(conexiones)}")
        logging.info("=" * 60)
        
        # Verificar dependencias necesarias
        if not verificar_dependencias(conexiones):
            logging.error("Faltan dependencias necesarias. Abortando ejecución.")
            return
        
        archivos_eliminados_totales = 0
        archivos_con_error_totales = 0
        tiempo_inicio_total = time.time()
        
        for alias, conexion in conexiones.items():
            tiempo_inicio = time.time()
            
            eliminados, errores = procesar_conexion(alias, conexion)
            archivos_eliminados_totales += eliminados
            archivos_con_error_totales += errores
            
            tiempo_procesamiento = time.time() - tiempo_inicio
            logging.info(f"Resumen conexión {alias}: {eliminados} eliminados, {errores} errores - Tiempo: {tiempo_procesamiento:.2f}s")
        
        tiempo_total = time.time() - tiempo_inicio_total
        logging.info("=" * 60)
        logging.info("RESUMEN FINAL:")
        logging.info(f"Archivos eliminados: {archivos_eliminados_totales}")
        logging.info(f"Archivos con error: {archivos_con_error_totales}")
        logging.info(f"Tiempo total de ejecución: {tiempo_total:.2f} segundos")
        logging.info("FIN del proceso de eliminación de archivos antiguos")
        logging.info("=" * 60)
        
    except Exception as e:
        logging.error(f"ERROR CRÍTICO en el proceso: {str(e)}")
        raise

def main():
    """
    Función principal que maneja la ejecución del script.
    """
    if len(sys.argv) < 2:
        print("Uso: python limpieza.py <ruta_al_archivo_configuracion> [ruta_al_archivo_credenciales]")
        print("\nEjemplos:")
        print("  python limpieza.py config.json")
        print("  python limpieza.py config.json credenciales.json")
        print("\nEl archivo config.json contiene las rutas y configuración.")
        print("El archivo credenciales.json contiene las credenciales de acceso.")
        sys.exit(1)
    
    config_file = sys.argv[1]
    credenciales_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        eliminar_archivos_antiguos(config_file, credenciales_file)
    except Exception as e:
        logging.error(f"Error inesperado: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()