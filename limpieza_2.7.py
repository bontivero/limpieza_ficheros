#!/usr/bin/env python
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

try:
    from urlparse import urlparse  # Python 2
except ImportError:
    from urllib.parse import urlparse  # Python 3

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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(script_dir, "logs")
    
    if not os.path.exists(logs_dir):
        try:
            os.makedirs(logs_dir)
        except OSError as e:
            logging.error(f"Error creando directorio de logs: {e}")
            # Usar directorio actual si no se puede crear logs
            logs_dir = script_dir
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = "limpieza_{}.log".format(timestamp)
    log_path = os.path.join(logs_dir, log_filename)
    
    # Configurar logging para Python 2.x
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Eliminar handlers existentes
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Formato del log
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', 
                                  datefmt='%Y-%m-%d %H:%M:%S')
    
    # Handler para archivo
    try:
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print("Error creando archivo de log: {}".format(e))
    
    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return log_path

def cargar_configuracion(config_file):
    """
    Carga la configuración desde un archivo JSON.
    
    Args:
        config_file (str): Ruta al archivo de configuración JSON
        
    Returns:
        dict: Configuración cargada
    """
    try:
        # Python 2.x necesita abrir el archivo sin encoding específico
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        logging.info("Configuración cargada desde: {}".format(config_file))
        return config
        
    except IOError:
        logging.error("Archivo de configuración no encontrado: {}".format(config_file))
        raise
    except ValueError as e:  # JSONDecodeError en Python 2 es ValueError
        logging.error("Error parseando archivo de configuración: {}".format(e))
        raise
    except Exception as e:
        logging.error("Error cargando configuración: {}".format(e))
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
        # Obtener directorio del script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        ubicaciones = [
            os.path.join(script_dir, "credenciales.json"),
            "/etc/limpieza/credenciales.json",
            os.path.join(os.path.expanduser("~"), ".limpieza_credenciales.json")
        ]
        
        for ubicacion in ubicaciones:
            if os.path.exists(ubicacion):
                credenciales_file = ubicacion
                break
        else:
            logging.warning("No se encontró archivo de credenciales")
            return {}
    
    try:
        with open(credenciales_file, 'r') as f:
            credenciales = json.load(f)
        
        logging.info("Credenciales cargadas desde: {}".format(credenciales_file))
        return credenciales
        
    except IOError:
        logging.error("Archivo de credenciales no encontrado: {}".format(credenciales_file))
        return {}
    except ValueError as e:
        logging.error("Error parseando archivo de credenciales: {}".format(e))
        return {}
    except Exception as e:
        logging.error("Error cargando credenciales: {}".format(e))
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
            conexiones_combinadas[alias] = conexion_config.copy()
            conexiones_combinadas[alias]['alias'] = alias
            continue
            
        if alias not in credenciales:
            logging.error("No se encontraron credenciales para el alias: {}".format(alias))
            continue
        
        # Python 2.x: combinar diccionarios manualmente
        conexion_combinada = conexion_config.copy()
        if alias in credenciales:
            conexion_combinada.update(credenciales[alias])
        conexion_combinada['alias'] = alias
        conexiones_combinadas[alias] = conexion_combinada
        
        campos_requeridos = ['tipo', 'host', 'usuario', 'contrasena']
        for campo in campos_requeridos:
            if campo not in conexion_combinada:
                logging.error("Falta campo requerido '{}' en conexión: {}".format(campo, alias))
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
                            logging.info("ELIMINADO (local): {}".format(ruta_completa))
                        except OSError as e:
                            archivos_con_error += 1
                            logging.error("ERROR eliminando {}: {}".format(ruta_completa, str(e)))
                except OSError as e:
                    archivos_con_error += 1
                    logging.error("ERROR accediendo a {}: {}".format(ruta_completa, str(e)))
        
        if mascara:
            logging.info("Resumen LOCAL {} (máscara: '{}'): {} procesados, {} eliminados, {} errores".format(
                ruta_base, mascara, archivos_procesados, archivos_eliminados, archivos_con_error))
        else:
            logging.info("Resumen LOCAL {}: {} procesados, {} eliminados, {} errores".format(
                ruta_base, archivos_procesados, archivos_eliminados, archivos_con_error))
        
    except Exception as e:
        logging.error("ERROR procesando ruta local {}: {}".format(ruta_base, str(e)))
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
            logging.warning("Comando '{}' falló (estado {}): {}".format(descripcion, exit_status, errores))
        else:
            logging.debug("Comando '{}' ejecutado exitosamente".format(descripcion))
            
        return salida, errores, exit_status
        
    except Exception as e:
        logging.error("Error ejecutando comando '{}': {}".format(descripcion, str(e)))
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
        
        logging.info("Conectando SSH a {}:{} (alias: {})".format(
            conexion['host'], conexion.get('puerto', 22), conexion['alias']))
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
                logging.info("  Procesando ruta SSH: {} - {} días - máscara: '{}'".format(ruta, dias, mascara))
            else:
                logging.info("  Procesando ruta SSH: {} - {} días".format(ruta, dias))
            
            comando_test = "{}ls {}".format(comando_sudo, ruta)
            salida, errores, estado = ejecutar_comando_ssh(cliente_ssh, comando_test, "verificar ruta {}".format(ruta))
            
            if estado != 0:
                logging.error("No se puede acceder a la ruta {}: {}".format(ruta, errores))
                archivos_con_error_totales += 1
                continue
            
            if mascara:
                comando_find = "{}find {} -type f -name '{}' -mtime +{} -print".format(comando_sudo, ruta, mascara, dias)
            else:
                comando_find = "{}find {} -type f -mtime +{} -print".format(comando_sudo, ruta, dias)
                
            salida, errores, estado = ejecutar_comando_ssh(cliente_ssh, comando_find, "buscar archivos en {}".format(ruta))
            
            if estado != 0 and "No such file or directory" not in errores:
                logging.error("Error buscando archivos en {}: {}".format(ruta, errores))
            
            archivos_a_eliminar = [archivo for archivo in salida.split('\n') if archivo.strip()]
            
            if not archivos_a_eliminar:
                if mascara:
                    logging.info("No se encontraron archivos con máscara '{}' para eliminar en {} (más antiguos de {} días)".format(mascara, ruta, dias))
                else:
                    logging.info("No se encontraron archivos para eliminar en {} (más antiguos de {} días)".format(ruta, dias))
                continue
            
            logging.info("Encontrados {} archivos para eliminar en {}".format(len(archivos_a_eliminar), ruta))
            
            archivos_eliminados_ruta = 0
            archivos_con_error_ruta = 0
            
            for archivo in archivos_a_eliminar:
                archivo = archivo.strip()
                if not archivo:
                    continue
                    
                try:
                    comando_eliminar = "{}rm -f '{}'".format(comando_sudo, archivo)
                    salida, errores, estado = ejecutar_comando_ssh(cliente_ssh, comando_eliminar, "eliminar {}".format(archivo))
                    
                    if estado == 0:
                        archivos_eliminados_ruta += 1
                        archivos_eliminados_totales += 1
                        logging.info("ELIMINADO (SSH): {}".format(archivo))
                    else:
                        archivos_con_error_ruta += 1
                        archivos_con_error_totales += 1
                        logging.error("ERROR eliminando {}: {}".format(archivo, errores))
                        
                except Exception as e:
                    archivos_con_error_ruta += 1
                    archivos_con_error_totales += 1
                    logging.error("ERROR procesando {}: {}".format(archivo, str(e)))
            
            if mascara:
                logging.info("  Resumen ruta {} (máscara: '{}'): {} eliminados, {} errores".format(
                    ruta, mascara, archivos_eliminados_ruta, archivos_con_error_ruta))
            else:
                logging.info("  Resumen ruta {}: {} eliminados, {} errores".format(
                    ruta, archivos_eliminados_ruta, archivos_con_error_ruta))
        
        cliente_ssh.close()
        
    except paramiko.AuthenticationException:
        logging.error("ERROR SSH: Autenticación fallida para {}@{}".format(
            conexion['usuario'], conexion['host']))
        archivos_con_error_totales += len(conexion['rutas'])
    except paramiko.SSHException as e:
        logging.error("ERROR SSH: {}".format(str(e)))
        archivos_con_error_totales += len(conexion['rutas'])
    except Exception as e:
        logging.error("ERROR conexión SSH a {}:{}: {}".format(
            conexion['host'], conexion.get('puerto', 22), str(e)))
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
        logging.info("Conectado SFTP a {}:{} (alias: {})".format(
            conexion['host'], conexion.get('puerto', 22), conexion['alias']))
        
        # Usar listas para simular "nonlocal" en Python 2
        contadores = [archivos_eliminados_totales, archivos_con_error_totales]
        
        def procesar_directorio_sftp(ruta_remota, dias, mascara=None):
            """
            Función interna para procesar recursivamente un directorio SFTP.
            """
            limite_tiempo = time.time() - (dias * 86400)
            
            try:
                for atributo in sftp.listdir_attr(ruta_remota):
                    ruta_completa = "{}/{}".format(ruta_remota, atributo.filename).replace('//', '/')
                    
                    if atributo.filename in ['.', '..']:
                        continue
                    
                    try:
                        sftp.listdir(ruta_completa)
                        procesar_directorio_sftp(ruta_completa, dias, mascara)
                    except:
                        if mascara:
                            if not fnmatch.fnmatch(atributo.filename, mascara):
                                continue
                                
                        try:
                            mtime = atributo.st_mtime
                            
                            if mtime < limite_tiempo:
                                sftp.remove(ruta_completa)
                                contadores[0] += 1
                                logging.info("ELIMINADO (SFTP): {}".format(ruta_completa))
                            else:
                                logging.debug("Conservado (SFTP): {}".format(ruta_completa))
                        except Exception as e:
                            contadores[1] += 1
                            logging.error("ERROR procesando {} (SFTP): {}".format(ruta_completa, str(e)))
                            
            except Exception as e:
                contadores[1] += 1
                logging.error("ERROR en directorio {} (SFTP): {}".format(ruta_remota, str(e)))
        
        for ruta_config in conexion['rutas']:
            ruta = ruta_config['ruta']
            dias = ruta_config['dias']
            mascara = ruta_config.get('mascara')
            
            if mascara:
                logging.info("  Procesando ruta SFTP: {} - {} días - máscara: '{}'".format(ruta, dias, mascara))
            else:
                logging.info("  Procesando ruta SFTP: {} - {} días".format(ruta, dias))
            
            try:
                sftp.listdir(ruta)
                logging.info("  Ruta verificada: {}".format(ruta))
                
                archivos_antes = contadores[0]
                errores_antes = contadores[1]
                
                procesar_directorio_sftp(ruta, dias, mascara)
                
                eliminados_ruta = contadores[0] - archivos_antes
                errores_ruta = contadores[1] - errores_antes
                
                if mascara:
                    logging.info("  Resumen ruta {} (máscara: '{}'): {} eliminados, {} errores".format(
                        ruta, mascara, eliminados_ruta, errores_ruta))
                else:
                    logging.info("  Resumen ruta {}: {} eliminados, {} errores".format(
                        ruta, eliminados_ruta, errores_ruta))
                
            except Exception as e:
                logging.error("La ruta no existe o no es accesible: {} - Error: {}".format(ruta, e))
                contadores[1] += 1
        
        archivos_eliminados_totales = contadores[0]
        archivos_con_error_totales = contadores[1]
        
        sftp.close()
        transporte.close()
        
    except paramiko.AuthenticationException:
        logging.error("ERROR SFTP: Autenticación fallida para {}@{}".format(
            conexion['usuario'], conexion['host']))
        archivos_con_error_totales += len(conexion['rutas'])
    except Exception as e:
        logging.error("ERROR conexión SFTP a {}:{}: {}".format(
            conexion['host'], conexion.get('puerto', 22), str(e)))
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
        logging.info("Conectando FTP a {}:{} (alias: {})".format(
            conexion['host'], conexion.get('puerto', 21), conexion['alias']))
        ftp = ftplib.FTP()
        ftp.connect(conexion['host'], conexion.get('puerto', 21), timeout=30)
        ftp.login(conexion['usuario'], conexion['contrasena'])
        
        # Usar listas para simular "nonlocal" en Python 2
        contadores = [archivos_eliminados_totales, archivos_con_error_totales]
        
        def procesar_directorio_ftp(path, dias, mascara=None):
            """
            Función interna para procesar recursivamente un directorio FTP.
            """
            limite_tiempo = time.time() - (dias * 86400)
            
            try:
                archivos = []
                ftp.retrlines('LIST {}'.format(path), archivos.append)
                
                for linea in archivos:
                    partes = linea.split()
                    if len(partes) < 9:
                        continue
                    
                    nombre = ' '.join(partes[8:])
                    if nombre in ['.', '..']:
                        continue
                    
                    ruta_completa = "{}/{}".format(path, nombre) if path else nombre
                    
                    if linea.startswith('d'):
                        procesar_directorio_ftp(ruta_completa, dias, mascara)
                    else:
                        if mascara:
                            if not fnmatch.fnmatch(nombre, mascara):
                                continue
                                
                        try:
                            resp = ftp.sendcmd("MDTM {}".format(ruta_completa))
                            if resp.startswith('213'):
                                mtime_str = resp[4:].strip()
                                mtime = time.mktime(time.strptime(mtime_str, '%Y%m%d%H%M%S'))
                                
                                if mtime < limite_tiempo:
                                    ftp.delete(ruta_completa)
                                    contadores[0] += 1
                                    logging.info("ELIMINADO (FTP): {}".format(ruta_completa))
                        except ftplib.error_perm as e:
                            logging.warning("No se pudo obtener fecha de {} (FTP): {}".format(ruta_completa, e))
                        except Exception as e:
                            contadores[1] += 1
                            logging.error("ERROR procesando {} (FTP): {}".format(ruta_completa, str(e)))
                            
            except Exception as e:
                contadores[1] += 1
                logging.error("ERROR en directorio {} (FTP): {}".format(path, str(e)))
        
        for ruta_config in conexion['rutas']:
            ruta = ruta_config['ruta']
            dias = ruta_config['dias']
            mascara = ruta_config.get('mascara')
            
            if mascara:
                logging.info("  Procesando ruta FTP: {} - {} días - máscara: '{}'".format(ruta, dias, mascara))
            else:
                logging.info("  Procesando ruta FTP: {} - {} días".format(ruta, dias))
            
            try:
                ftp.cwd(ruta)
                archivos_antes = contadores[0]
                errores_antes = contadores[1]
                
                procesar_directorio_ftp('', dias, mascara)
                
                eliminados_ruta = contadores[0] - archivos_antes
                errores_ruta = contadores[1] - errores_antes
                
                if mascara:
                    logging.info("  Resumen ruta {} (máscara: '{}'): {} eliminados, {} errores".format(
                        ruta, mascara, eliminados_ruta, errores_ruta))
                else:
                    logging.info("  Resumen ruta {}: {} eliminados, {} errores".format(
                        ruta, eliminados_ruta, errores_ruta))
                
            except Exception as e:
                logging.error("La ruta no existe o no es accesible: {} - Error: {}".format(ruta, e))
                contadores[1] += 1
        
        archivos_eliminados_totales = contadores[0]
        archivos_con_error_totales = contadores[1]
        
        ftp.quit()
        
    except ftplib.all_errors as e:
        logging.error("ERROR FTP: {}".format(str(e)))
        archivos_con_error_totales += len(conexion['rutas'])
    except Exception as e:
        logging.error("ERROR conexión FTP a {}:{}: {}".format(
            conexion['host'], conexion.get('puerto', 21), str(e)))
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
    logging.info("Procesando conexión: {} ({})".format(alias, conexion['tipo'].upper()))
    
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
                    logging.info("  Ruta: {} - {} días - máscara: '{}'".format(ruta, dias, mascara))
                else:
                    logging.info("  Ruta: {} - {} días".format(ruta, dias))
                    
                eliminados, errores = eliminar_archivos_locales(ruta, dias, mascara)
                archivos_eliminados_totales += eliminados
                archivos_con_error_totales += errores
                
                if mascara:
                    logging.info("  Resumen ruta (máscara: '{}'): {} eliminados, {} errores".format(
                        mascara, eliminados, errores))
                else:
                    logging.info("  Resumen ruta: {} eliminados, {} errores".format(eliminados, errores))
                
            return archivos_eliminados_totales, archivos_con_error_totales
            
        elif conexion['tipo'] == 'ssh':
            return eliminar_archivos_ssh(conexion)
            
        elif conexion['tipo'] == 'sftp':
            return eliminar_archivos_sftp(conexion)
            
        elif conexion['tipo'] == 'ftp':
            return eliminar_archivos_ftp(conexion)
            
        else:
            logging.error("Tipo de conexión desconocido: {}".format(conexion['tipo']))
            return 0, len(conexion['rutas'])
            
    except Exception as e:
        logging.error("ERROR procesando conexión {}: {}".format(alias, str(e)))
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
    logging.info("Log guardado en: {}".format(log_path))
    
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
        
        logging.info("Total de conexiones a procesar: {}".format(len(conexiones)))
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
            logging.info("Resumen conexión {}: {} eliminados, {} errores - Tiempo: {:.2f}s".format(
                alias, eliminados, errores, tiempo_procesamiento))
        
        tiempo_total = time.time() - tiempo_inicio_total
        logging.info("=" * 60)
        logging.info("RESUMEN FINAL:")
        logging.info("Archivos eliminados: {}".format(archivos_eliminados_totales))
        logging.info("Archivos con error: {}".format(archivos_con_error_totales))
        logging.info("Tiempo total de ejecución: {:.2f} segundos".format(tiempo_total))
        logging.info("FIN del proceso de eliminación de archivos antiguos")
        logging.info("=" * 60)
        
    except Exception as e:
        logging.error("ERROR CRÍTICO en el proceso: {}".format(str(e)))
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
        logging.error("Error inesperado: {}".format(str(e)))
        sys.exit(1)

if __name__ == "__main__":
    main()