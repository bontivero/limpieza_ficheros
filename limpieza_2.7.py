#!/usr/bin/env python2
"""
Script para eliminar archivos antiguos basado en un archivo de configuración.

Este script lee un archivo de configuración que especifica rutas (locales, SSH, SFTP o FTP) y tiempos
en días para eliminar archivos recursivamente. Las credenciales se almacenan en un archivo separado.

Formato del archivo de configuración:
LOCAL: /ruta/directorio/|dias
SSH: ssh://alias_servidor/ruta|dias
SFTP: sftp://alias_servidor/ruta|dias
FTP: ftp://alias_servidor/ruta|dias

config.json -> Rutas y configuración
credenciales.json -> Credenciales de acceso
"""

import os
import sys
import time
import datetime
import logging
import ftplib
import json

PARAMIKO_DISPONIBLE = False
try:
    import paramiko
    PARAMIKO_DISPONIBLE = True
except ImportError:
    pass

# Compatibilidad con Python 2.7
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

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
        except OSError:
            pass
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = "limpieza_{}.log".format(timestamp)
    log_path = os.path.join(logs_dir, log_filename)
    
    # Configurar logging para Python 2.7
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Eliminar handlers existentes
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Formateador
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', 
                                  datefmt='%Y-%m-%d %H:%M:%S')
    
    # Handler de archivo
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Handler de consola
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
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        logging.info("Configuración cargada desde: %s", config_file)
        return config
        
    except IOError:
        logging.error("Archivo de configuración no encontrado: %s", config_file)
        raise
    except ValueError as e:
        logging.error("Error parseando archivo de configuración: %s", e)
        raise
    except Exception as e:
        logging.error("Error cargando configuración: %s", e)
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
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "credenciales.json"),
            "/etc/limpieza/credenciales.json",
            os.path.expanduser("~/.limpieza_credenciales.json")
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
        
        logging.info("Credenciales cargadas desde: %s", credenciales_file)
        return credenciales
        
    except IOError:
        logging.error("Archivo de credenciales no encontrado: %s", credenciales_file)
        return {}
    except ValueError as e:
        logging.error("Error parseando archivo de credenciales: %s", e)
        return {}
    except Exception as e:
        logging.error("Error cargando credenciales: %s", e)
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
            logging.error("No se encontraron credenciales para el alias: %s", alias)
            continue
            
        conexion_combinada = conexion_config.copy()
        conexion_combinada.update(credenciales[alias])
        conexion_combinada['alias'] = alias
        conexiones_combinadas[alias] = conexion_combinada
        
        campos_requeridos = ['tipo', 'host', 'usuario', 'contrasena']
        for campo in campos_requeridos:
            if campo not in conexion_combinada:
                logging.error("Falta campo requerido '%s' en conexión: %s", campo, alias)
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

def eliminar_archivos_locales(ruta_base, dias):
    """
    Elimina archivos locales más antiguos que los días especificados.
    
    Args:
        ruta_base (str): Ruta local del directorio
        dias (int): Días de antigüedad máxima
        
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
                ruta_completa = os.path.join(root, file)
                archivos_procesados += 1

                try:
                    mtime = os.path.getmtime(ruta_completa)

                    if mtime < limite_tiempo:
                        try:
                            os.remove(ruta_completa)
                            archivos_eliminados += 1
                            logging.info("ELIMINADO (local): %s", ruta_completa)
                        except OSError as e:
                            archivos_con_error += 1
                            logging.error("ERROR eliminando %s: %s", ruta_completa, str(e))
                except OSError as e:
                    archivos_con_error += 1
                    logging.error("ERROR accediendo a %s: %s", ruta_completa, str(e))

        logging.info("Resumen LOCAL %s: %d procesados, %d eliminados, %d errores", 
                    ruta_base, archivos_procesados, archivos_eliminados, archivos_con_error)
        
    except Exception as e:
        logging.error("ERROR procesando ruta local %s: %s", ruta_base, str(e))
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
        salida = stdout.read().strip()
        errores = stderr.read().strip()
        
        if exit_status != 0:
            logging.warning("Comando '%s' falló (estado %d): %s", descripcion, exit_status, errores)
        else:
            logging.debug("Comando '%s' ejecutado exitosamente", descripcion)
            
        return salida, errores, exit_status
        
    except Exception as e:
        logging.error("Error ejecutando comando '%s': %s", descripcion, str(e))
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
        # Conectar al servidor SSH (una sola vez)
        cliente_ssh = paramiko.SSHClient()
        cliente_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        logging.info("Conectando SSH a %s:%d (alias: %s)", 
                    conexion['host'], conexion.get('puerto', 22), conexion['alias'])
        cliente_ssh.connect(
            hostname=conexion['host'],
            port=conexion.get('puerto', 22),
            username=conexion['usuario'],
            password=conexion['contrasena'],
            timeout=30
        )
        
        # Procesar todas las rutas con la misma conexión
        for ruta_config in conexion['rutas']:
            ruta = ruta_config['ruta']
            dias = ruta_config['dias']
            
            logging.info("  Procesando ruta SSH: %s - %d días", ruta, dias)
            
            # Verificar si la ruta existe
            comando_test = "{}ls {}".format(comando_sudo, ruta)
            salida, errores, estado = ejecutar_comando_ssh(cliente_ssh, comando_test, "verificar ruta {}".format(ruta))
            
            if estado != 0:
                logging.error("No se puede acceder a la ruta %s: %s", ruta, errores)
                archivos_con_error_totales += 1
                continue
            
            # Buscar archivos antiguos
            comando_find = "{}find {} -type f -mtime +{} -print".format(comando_sudo, ruta, dias)
            salida, errores, estado = ejecutar_comando_ssh(cliente_ssh, comando_find, "buscar archivos en {}".format(ruta))
            
            if estado != 0 and "No such file or directory" not in errores:
                logging.error("Error buscando archivos en %s: %s", ruta, errores)
            
            archivos_a_eliminar = [archivo for archivo in salida.split('\n') if archivo.strip()]
            
            if not archivos_a_eliminar:
                logging.info("No se encontraron archivos para eliminar en %s (más antiguos de %d días)", ruta, dias)
                continue
            
            logging.info("Encontrados %d archivos para eliminar en %s", len(archivos_a_eliminar), ruta)
            
            # Eliminar archivos encontrados
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
                        logging.info("ELIMINADO (SSH): %s", archivo)
                    else:
                        archivos_con_error_ruta += 1
                        archivos_con_error_totales += 1
                        logging.error("ERROR eliminando %s: %s", archivo, errores)
                        
                except Exception as e:
                    archivos_con_error_ruta += 1
                    archivos_con_error_totales += 1
                    logging.error("ERROR procesando %s: %s", archivo, str(e))
            
            logging.info("  Resumen ruta %s: %d eliminados, %d errores", ruta, archivos_eliminados_ruta, archivos_con_error_ruta)
        
        # Cerrar conexión al final
        cliente_ssh.close()
        
    except paramiko.AuthenticationException:
        logging.error("ERROR SSH: Autenticación fallida para %s@%s", conexion['usuario'], conexion['host'])
        archivos_con_error_totales += len(conexion['rutas'])
    except paramiko.SSHException as e:
        logging.error("ERROR SSH: %s", str(e))
        archivos_con_error_totales += len(conexion['rutas'])
    except Exception as e:
        logging.error("ERROR conexión SSH a %s:%d: %s", 
                     conexion['host'], conexion.get('puerto', 22), str(e))
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
        logging.info("Conectado SFTP a %s:%d (alias: %s)", 
                    conexion['host'], conexion.get('puerto', 22), conexion['alias'])
        
        def procesar_directorio_sftp(ruta_remota, dias):
            """
            Función interna para procesar recursivamente un directorio SFTP.
            """
            nonlocal archivos_eliminados_totales, archivos_con_error_totales
            limite_tiempo = time.time() - (dias * 86400)
            
            try:
                for atributo in sftp.listdir_attr(ruta_remota):
                    ruta_completa = "{}/{}".format(ruta_remota, atributo.filename).replace('//', '/')
                    
                    if atributo.filename in ['.', '..']:
                        continue
                    
                    # Si es directorio, procesar recursivamente
                    try:
                        sftp.listdir(ruta_completa)
                        procesar_directorio_sftp(ruta_completa, dias)
                    except:
                        # Es archivo - verificar si es antiguo
                        try:
                            mtime = atributo.st_mtime
                            
                            if mtime < limite_tiempo:
                                sftp.remove(ruta_completa)
                                archivos_eliminados_totales += 1
                                logging.info("ELIMINADO (SFTP): %s", ruta_completa)
                            else:
                                logging.debug("Conservado (SFTP): %s", ruta_completa)
                        except Exception as e:
                            archivos_con_error_totales += 1
                            logging.error("ERROR procesando %s (SFTP): %s", ruta_completa, str(e))
                            
            except Exception as e:
                archivos_con_error_totales += 1
                logging.error("ERROR en directorio %s (SFTP): %s", ruta_remota, str(e))
        
        # Procesar todas las rutas con la misma conexión SFTP
        for ruta_config in conexion['rutas']:
            ruta = ruta_config['ruta']
            dias = ruta_config['dias']
            
            logging.info("  Procesando ruta SFTP: %s - %d días", ruta, dias)
            
            # Verificar si la ruta existe
            try:
                sftp.listdir(ruta)
                logging.info("  Ruta verificada: %s", ruta)
                
                # Procesar directorio recursivamente
                archivos_antes = archivos_eliminados_totales
                errores_antes = archivos_con_error_totales
                
                procesar_directorio_sftp(ruta, dias)
                
                eliminados_ruta = archivos_eliminados_totales - archivos_antes
                errores_ruta = archivos_con_error_totales - errores_antes
                
                logging.info("  Resumen ruta %s: %d eliminados, %d errores", ruta, eliminados_ruta, errores_ruta)
                
            except Exception as e:
                logging.error("La ruta no existe o no es accesible: %s - Error: %s", ruta, e)
                archivos_con_error_totales += 1
        
        # Cerrar conexión al final
        sftp.close()
        transporte.close()
        
    except paramiko.AuthenticationException:
        logging.error("ERROR SFTP: Autenticación fallida para %s@%s", conexion['usuario'], conexion['host'])
        archivos_con_error_totales += len(conexion['rutas'])
    except Exception as e:
        logging.error("ERROR conexión SFTP a %s:%d: %s", 
                     conexion['host'], conexion.get('puerto', 22), str(e))
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
        # Conectar al servidor FTP (una sola vez)
        logging.info("Conectando FTP a %s:%d (alias: %s)", 
                    conexion['host'], conexion.get('puerto', 21), conexion['alias'])
        ftp = ftplib.FTP()
        ftp.connect(conexion['host'], conexion.get('puerto', 21))
        ftp.login(conexion['usuario'], conexion['contrasena'])
        
        def procesar_directorio_ftp(path, dias):
            """
            Función interna para procesar recursivamente un directorio FTP.
            """
            nonlocal archivos_eliminados_totales, archivos_con_error_totales
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
                        procesar_directorio_ftp(ruta_completa, dias)
                    else:
                        try:
                            resp = ftp.sendcmd("MDTM {}".format(ruta_completa))
                            if resp.startswith('213'):
                                mtime_str = resp[4:].strip()
                                mtime = time.mktime(time.strptime(mtime_str, '%Y%m%d%H%M%S'))
                                
                                if mtime < limite_tiempo:
                                    ftp.delete(ruta_completa)
                                    archivos_eliminados_totales += 1
                                    logging.info("ELIMINADO (FTP): %s", ruta_completa)
                        except ftplib.error_perm as e:
                            logging.warning("No se pudo obtener fecha de %s (FTP): %s", ruta_completa, e)
                        except Exception as e:
                            archivos_con_error_totales += 1
                            logging.error("ERROR procesando %s (FTP): %s", ruta_completa, str(e))
                            
            except Exception as e:
                archivos_con_error_totales += 1
                logging.error("ERROR en directorio %s (FTP): %s", path, str(e))
        
        # Procesar todas las rutas con la misma conexión FTP
        for ruta_config in conexion['rutas']:
            ruta = ruta_config['ruta']
            dias = ruta_config['dias']
            
            logging.info("  Procesando ruta FTP: %s - %d días", ruta, dias)
            
            try:
                ftp.cwd(ruta)
                archivos_antes = archivos_eliminados_totales
                errores_antes = archivos_con_error_totales
                
                procesar_directorio_ftp('', dias)
                
                eliminados_ruta = archivos_eliminados_totales - archivos_antes
                errores_ruta = archivos_con_error_totales - errores_antes
                
                logging.info("  Resumen ruta %s: %d eliminados, %d errores", ruta, eliminados_ruta, errores_ruta)
                
            except Exception as e:
                logging.error("La ruta no existe o no es accesible: %s - Error: %s", ruta, e)
                archivos_con_error_totales += 1
        
        # Cerrar conexión al final
        ftp.quit()
        
    except ftplib.all_errors as e:
        logging.error("ERROR FTP: %s", str(e))
        archivos_con_error_totales += len(conexion['rutas'])
    except Exception as e:
        logging.error("ERROR conexión FTP a %s:%d: %s", 
                     conexion['host'], conexion.get('puerto', 21), str(e))
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
    logging.info("Procesando conexión: %s (%s)", alias, conexion['tipo'].upper())
    
    try:
        if conexion['tipo'] == 'local':
            # Para local, procesamos cada ruta individualmente
            archivos_eliminados_totales = 0
            archivos_con_error_totales = 0
            
            for ruta_config in conexion['rutas']:
                logging.info("  Ruta: %s - %d días", ruta_config['ruta'], ruta_config['dias'])
                eliminados, errores = eliminar_archivos_locales(ruta_config['ruta'], ruta_config['dias'])
                archivos_eliminados_totales += eliminados
                archivos_con_error_totales += errores
                logging.info("  Resumen ruta: %d eliminados, %d errores", eliminados, errores)
                
            return archivos_eliminados_totales, archivos_con_error_totales
            
        elif conexion['tipo'] == 'ssh':
            # Una sola conexión SSH para todas las rutas
            return eliminar_archivos_ssh(conexion)
            
        elif conexion['tipo'] == 'sftp':
            # Una sola conexión SFTP para todas las rutas
            return eliminar_archivos_sftp(conexion)
            
        elif conexion['tipo'] == 'ftp':
            # Una sola conexión FTP para todas las rutas
            return eliminar_archivos_ftp(conexion)
            
        else:
            logging.error("Tipo de conexión desconocido: %s", conexion['tipo'])
            return 0, len(conexion['rutas'])
            
    except Exception as e:
        logging.error("ERROR procesando conexión %s: %s", alias, str(e))
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
    logging.info("Log guardado en: %s", log_path)
    
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
        
        logging.info("Total de conexiones a procesar: %d", len(conexiones))
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
            logging.info("Resumen conexión %s: %d eliminados, %d errores - Tiempo: %.2fs", 
                        alias, eliminados, errores, tiempo_procesamiento)
        
        tiempo_total = time.time() - tiempo_inicio_total
        logging.info("=" * 60)
        logging.info("RESUMEN FINAL:")
        logging.info("Archivos eliminados: %d", archivos_eliminados_totales)
        logging.info("Archivos con error: %d", archivos_con_error_totales)
        logging.info("Tiempo total de ejecución: %.2f segundos", tiempo_total)
        logging.info("FIN del proceso de eliminación de archivos antiguos")
        logging.info("=" * 60)
        
    except Exception as e:
        logging.error("ERROR CRÍTICO en el proceso: %s", str(e))
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
        logging.error("Error inesperado: %s", str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()