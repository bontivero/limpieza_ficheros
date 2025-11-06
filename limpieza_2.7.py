#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para eliminar archivos antiguos basado en un archivo de configuración.

Compatibilidad: Python 2.7 y 3.x
"""

import os
import sys
import time
import datetime
import logging
import ftplib
import json

# Compatibilidad entre Python 2 y 3
try:
    # Python 2
    from urllib.parse import urlparse
except ImportError:
    # Python 3
    from urlparse import urlparse

try:
    # Python 2
    from io import open
except ImportError:
    # Python 3
    pass

# Intentar importar paramiko, pero no fallar si no está disponible
PARAMIKO_DISPONIBLE = False
try:
    import paramiko
    PARAMIKO_DISPONIBLE = True
except ImportError:
    pass

def configurar_logging():
    """
    Configura el sistema de logging para el script.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(script_dir, "logs")
    
    # Crear directorio logs si no existe
    if not os.path.exists(logs_dir):
        try:
            os.makedirs(logs_dir)
        except OSError:
            print("Error: No se pudo crear el directorio logs")
            return ""
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = "limpieza_{0}.log".format(timestamp)
    log_path = os.path.join(logs_dir, log_filename)
    
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return log_path

def cargar_configuracion(config_file):
    """
    Carga la configuración desde un archivo JSON.
    """
    try:
        # Usar codecs para mejor manejo de encoding en Python 2.7
        if sys.version_info[0] < 3:
            import codecs
            with codecs.open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            with open(config_file, 'r', encoding='utf-8') as f:
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
    """
    if credenciales_file is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ubicaciones = [
            os.path.join(script_dir, "credenciales.json"),
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
        # Manejo de encoding para Python 2.7
        if sys.version_info[0] < 3:
            import codecs
            with codecs.open(credenciales_file, 'r', encoding='utf-8') as f:
                credenciales = json.load(f)
        else:
            with open(credenciales_file, 'r', encoding='utf-8') as f:
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
    """
    conexiones_combinadas = {}
    conexiones_config = config.get('conexiones', {})

    if not conexiones_config:
        logging.error("No se encontraron conexiones en la configuración")
        return {}
    
    for alias, conexion_config in conexiones_config.items():
        # Para Python 2.7, asegurar que alias es string
        alias_str = alias.encode('utf-8') if isinstance(alias, unicode) else str(alias)
        
        if conexion_config.get('tipo') == 'local':
            conexiones_combinadas[alias_str] = conexion_config
            conexiones_combinadas[alias_str]['alias'] = alias_str
            continue
            
        if alias_str not in credenciales:
            logging.error("No se encontraron credenciales para el alias: %s", alias_str)
            continue
            
        # Combinar configuración
        conexion_combinada = {}
        conexion_combinada.update(credenciales[alias_str])
        conexion_combinada.update(conexion_config)
        conexion_combinada['alias'] = alias_str
        conexiones_combinadas[alias_str] = conexion_combinada
        
        # Validar campos requeridos
        campos_requeridos = ['tipo', 'host', 'usuario', 'contraseña']
        for campo in campos_requeridos:
            if campo not in conexion_combinada:
                logging.error("Falta campo requerido '%s' en conexión: %s", campo, alias_str)
                break
    
    return conexiones_combinadas

def verificar_dependencias(conexiones):
    """
    Verifica que las dependencias necesarias estén disponibles.
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
    """
    try:
        stdin, stdout, stderr = cliente_ssh.exec_command(comando)
        exit_status = stdout.channel.recv_exit_status()
        salida = stdout.read().decode('utf-8').strip()
        errores = stderr.read().decode('utf-8').strip()
        
        if exit_status != 0:
            logging.warning("Comando '%s' falló (estado %d): %s", descripcion, exit_status, errores)
        else:
            logging.debug("Comando '%s' ejecutado exitosamente", descripcion)
            
        return salida, errores, exit_status
        
    except Exception as e:
        logging.error("Error ejecutando comando '%s': %s", descripcion, str(e))
        return "", str(e), 1

def eliminar_archivos_ssh(conexion, ruta_config):
    """
    Elimina archivos remotos vía SSH más antiguos que los días especificados.
    """
    if not PARAMIKO_DISPONIBLE:
        logging.error("No se puede procesar configuración SSH: paramiko no está instalado")
        return 0, 1

    archivos_eliminados = 0
    archivos_con_error = 0
    ruta = ruta_config['ruta']
    dias = ruta_config['dias']
    necesita_sudo = conexion.get('necesita_sudo', False)
    comando_sudo = "sudo " if necesita_sudo else ""

    try:
        cliente_ssh = paramiko.SSHClient()
        cliente_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        puerto = conexion.get('puerto', 22)
        logging.info("Conectando SSH a %s:%d (alias: %s)", conexion['host'], puerto, conexion['alias'])
        
        cliente_ssh.connect(
            hostname=conexion['host'],
            port=puerto,
            username=conexion['usuario'],
            password=conexion['contraseña'],
            timeout=30
        )
        
        comando_test = "{0}ls {1}".format(comando_sudo, ruta)
        salida, errores, estado = ejecutar_comando_ssh(cliente_ssh, comando_test, "verificar ruta")
        
        if estado != 0:
            logging.error("No se puede acceder a la ruta %s: %s", ruta, errores)
            cliente_ssh.close()
            return 0, 1
        
        comando_find = "{0}find {1} -type f -mtime +{2} -print".format(comando_sudo, ruta, dias)
        salida, errores, estado = ejecutar_comando_ssh(cliente_ssh, comando_find, "buscar archivos antiguos")
        
        if estado != 0 and "No such file or directory" not in errores:
            logging.error("Error buscando archivos: %s", errores)
        
        archivos_a_eliminar = [archivo for archivo in salida.split('\n') if archivo.strip()]
        
        if not archivos_a_eliminar:
            logging.info("No se encontraron archivos para eliminar en %s (más antiguos de %d días)", ruta, dias)
            cliente_ssh.close()
            return 0, 0
        
        logging.info("Encontrados %d archivos para eliminar en %s", len(archivos_a_eliminar), ruta)
        
        for i, archivo in enumerate(archivos_a_eliminar[:3]):
            logging.debug("Archivo a eliminar %d: %s", i+1, archivo)
        if len(archivos_a_eliminar) > 3:
            logging.debug("... y %d archivos más", len(archivos_a_eliminar) - 3)
        
        for archivo in archivos_a_eliminar:
            archivo = archivo.strip()
            if not archivo:
                continue
                
            try:
                comando_eliminar = "{0}rm -f '{1}'".format(comando_sudo, archivo)
                salida, errores, estado = ejecutar_comando_ssh(cliente_ssh, comando_eliminar, "eliminar {0}".format(archivo))
                
                if estado == 0:
                    archivos_eliminados += 1
                    logging.info("ELIMINADO (SSH): %s", archivo)
                else:
                    archivos_con_error += 1
                    logging.error("ERROR eliminando %s: %s", archivo, errores)
                    
            except Exception as e:
                archivos_con_error += 1
                logging.error("ERROR procesando %s: %s", archivo, str(e))
        
        cliente_ssh.close()
        logging.info("Resumen SSH %s: %d archivos encontrados, %d eliminados, %d errores", 
                    ruta, len(archivos_a_eliminar), archivos_eliminados, archivos_con_error)
        
    except paramiko.AuthenticationException:
        logging.error("ERROR SSH: Autenticación fallida para %s@%s", conexion['usuario'], conexion['host'])
        archivos_con_error += 1
    except paramiko.SSHException as e:
        logging.error("ERROR SSH: %s", str(e))
        archivos_con_error += 1
    except Exception as e:
        puerto = conexion.get('puerto', 22)
        logging.error("ERROR conexión SSH a %s:%d: %s", conexion['host'], puerto, str(e))
        archivos_con_error += 1

    return archivos_eliminados, archivos_con_error

def eliminar_archivos_sftp(conexion, ruta_config):
    """
    Elimina archivos remotos vía SFTP más antiguos que los días especificados.
    """
    if not PARAMIKO_DISPONIBLE:
        logging.error("No se puede procesar configuración SFTP: paramiko no está instalado")
        return 0, 1

    limite_tiempo = time.time() - (ruta_config['dias'] * 86400)
    archivos_eliminados = 0
    archivos_con_error = 0

    try:
        puerto = conexion.get('puerto', 22)
        transporte = paramiko.Transport((conexion['host'], puerto))
        transporte.connect(username=conexion['usuario'], password=conexion['contraseña'])
        
        sftp = paramiko.SFTPClient.from_transport(transporte)
        logging.info("Conectado SFTP a %s:%d (alias: %s)", conexion['host'], puerto, conexion['alias'])
        
        # Usar lista para variables no locales (workaround para Python 2.7)
        stats = [archivos_eliminados, archivos_con_error]
        
        def procesar_directorio_sftp(ruta_remota):
            try:
                for atributo in sftp.listdir_attr(ruta_remota):
                    ruta_completa = "{0}/{1}".format(ruta_remota, atributo.filename).replace('//', '/')
                    
                    if atributo.filename in ['.', '..']:
                        continue
                    
                    try:
                        sftp.listdir(ruta_completa)
                        procesar_directorio_sftp(ruta_completa)
                    except:
                        try:
                            mtime = atributo.st_mtime
                            
                            if mtime < limite_tiempo:
                                sftp.remove(ruta_completa)
                                stats[0] += 1
                                logging.info("ELIMINADO (SFTP): %s", ruta_completa)
                            else:
                                logging.debug("Conservado (SFTP): %s", ruta_completa)
                        except Exception as e:
                            stats[1] += 1
                            logging.error("ERROR procesando %s (SFTP): %s", ruta_completa, str(e))
                            
            except Exception as e:
                stats[1] += 1
                logging.error("ERROR en directorio %s (SFTP): %s", ruta_remota, str(e))
        
        procesar_directorio_sftp(ruta_config['ruta'])
        
        archivos_eliminados, archivos_con_error = stats[0], stats[1]
        sftp.close()
        transporte.close()
        
    except paramiko.AuthenticationException:
        logging.error("ERROR SFTP: Autenticación fallida para %s@%s", conexion['usuario'], conexion['host'])
        archivos_con_error += 1
    except Exception as e:
        puerto = conexion.get('puerto', 22)
        logging.error("ERROR conexión SFTP a %s:%d: %s", conexion['host'], puerto, str(e))
        archivos_con_error += 1

    return archivos_eliminados, archivos_con_error

def eliminar_archivos_ftp(conexion, ruta_config):
    """
    Elimina archivos remotos vía FTP más antiguos que los días especificados.
    """
    limite_tiempo = time.time() - (ruta_config['dias'] * 86400)
    archivos_eliminados = 0
    archivos_con_error = 0

    try:
        puerto = conexion.get('puerto', 21)
        logging.info("Conectando FTP a %s:%d (alias: %s)", conexion['host'], puerto, conexion['alias'])
        ftp = ftplib.FTP()
        ftp.connect(conexion['host'], puerto, timeout=30)
        ftp.login(conexion['usuario'], conexion['contraseña'])
        
        ftp.cwd(ruta_config['ruta'])
        
        # Usar lista para variables no locales
        stats = [archivos_eliminados, archivos_con_error]
        
        def procesar_directorio_ftp(path=''):
            try:
                archivos = []
                ftp.retrlines('LIST {0}'.format(path), archivos.append)
                
                for linea in archivos:
                    partes = linea.split()
                    if len(partes) < 9:
                        continue
                    
                    nombre = ' '.join(partes[8:])
                    if nombre in ['.', '..']:
                        continue
                    
                    ruta_completa = "{0}/{1}".format(path, nombre) if path else nombre
                    
                    if linea.startswith('d'):
                        procesar_directorio_ftp(ruta_completa)
                    else:
                        try:
                            resp = ftp.sendcmd("MDTM {0}".format(ruta_completa))
                            if resp.startswith('213'):
                                mtime_str = resp[4:].strip()
                                # Convertir timestamp (formato: YYYYMMDDHHMMSS)
                                mtime = time.mktime(time.strptime(mtime_str, '%Y%m%d%H%M%S'))
                                
                                if mtime < limite_tiempo:
                                    ftp.delete(ruta_completa)
                                    stats[0] += 1
                                    logging.info("ELIMINADO (FTP): %s", ruta_completa)
                        except ftplib.error_perm as e:
                            logging.warning("No se pudo obtener fecha de %s (FTP): %s", ruta_completa, e)
                        except Exception as e:
                            stats[1] += 1
                            logging.error("ERROR procesando %s (FTP): %s", ruta_completa, str(e))
                            
            except Exception as e:
                stats[1] += 1
                logging.error("ERROR en directorio %s (FTP): %s", path, str(e))
        
        procesar_directorio_ftp()
        archivos_eliminados, archivos_con_error = stats[0], stats[1]
        ftp.quit()
        
    except ftplib.all_errors as e:
        logging.error("ERROR FTP: %s", str(e))
        archivos_con_error += 1
    except Exception as e:
        puerto = conexion.get('puerto', 21)
        logging.error("ERROR conexión FTP a %s:%d: %s", conexion['host'], puerto, str(e))
        archivos_con_error += 1

    return archivos_eliminados, archivos_con_error

def procesar_conexion(alias, conexion):
    """
    Procesa una conexión completa con todas sus rutas.
    """
    logging.info("Procesando conexión: %s (%s)", alias, conexion['tipo'].upper())
    
    archivos_eliminados_totales = 0
    archivos_con_error_totales = 0
    
    for ruta_config in conexion['rutas']:
        logging.info("  Ruta: %s - %d días", ruta_config['ruta'], ruta_config['dias'])
        
        try:
            if conexion['tipo'] == 'local':
                eliminados, errores = eliminar_archivos_locales(ruta_config['ruta'], ruta_config['dias'])
            elif conexion['tipo'] == 'ssh':
                eliminados, errores = eliminar_archivos_ssh(conexion, ruta_config)
            elif conexion['tipo'] == 'sftp':
                eliminados, errores = eliminar_archivos_sftp(conexion, ruta_config)
            elif conexion['tipo'] == 'ftp':
                eliminados, errores = eliminar_archivos_ftp(conexion, ruta_config)
            else:
                logging.error("Tipo de conexión desconocido: %s", conexion['tipo'])
                continue
                
            archivos_eliminados_totales += eliminados
            archivos_con_error_totales += errores
            
            logging.info("  Resumen ruta: %d eliminados, %d errores", eliminados, errores)
            
        except Exception as e:
            logging.error("ERROR procesando ruta %s: %s", ruta_config['ruta'], str(e))
            archivos_con_error_totales += 1
    
    return archivos_eliminados_totales, archivos_con_error_totales

def eliminar_archivos_antiguos(config_file, credenciales_file=None):
    """
    Función principal que elimina archivos antiguos basándose en la configuración.
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