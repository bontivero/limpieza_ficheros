#!/usr/bin/env python
"""
Script de Diagnóstico de Acceso - Compatible con Python 2.x
Diagnóstico completo para conexiones Local, SSH, SFTP y FTP

Uso:
    python diagnostico_acceso.py [opciones]

Opciones:
    --config FILE      Archivo de configuración (default: config.json)
    --credenciales FILE Archivo de credenciales (default: credenciales.json)
    --tipo TIPO        Tipo de conexión a diagnosticar (local, ssh, sftp, ftp, all)
    --alias ALIAS      Diagnosticar solo una conexión específica
    --verbose, -v      Mostrar información detallada
    --help, -h         Mostrar esta ayuda

Ejemplos:
    python diagnostico_acceso.py
    python diagnostico_acceso.py --tipo ssh
    python diagnostico_acceso.py --alias mi_servidor --verbose
"""

import os
import sys
import time
import json
import logging

# Detectar versión de Python
PYTHON3 = sys.version_info[0] >= 3

# Configurar logging básico para Python 2.x
if PYTHON3:
    logging.basicConfig(level=logging.INFO, format='%(message)s')
else:
    # Configuración manual para Python 2.x
    logging.getLogger().setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger().addHandler(handler)

# Importaciones condicionales para compatibilidad
try:
    import paramiko
    PARAMIKO_DISPONIBLE = True
except ImportError:
    PARAMIKO_DISPONIBLE = False

try:
    import ftplib
    FTPLIB_DISPONIBLE = True
except ImportError:
    FTPLIB_DISPONIBLE = False

try:
    if PYTHON3:
        from urllib.parse import urlparse
    else:
        from urlparse import urlparse
except ImportError:
    pass

# Función de compatibilidad para print
def print_compatible(*args, **kwargs):
    """Función de print compatible con Python 2.x y 3.x"""
    if PYTHON3:
        print(*args, **kwargs)
    else:
        # En Python 2.x, print es una declaración
        # Usamos sys.stdout.write para mayor control
        sep = kwargs.get('sep', ' ')
        end = kwargs.get('end', '\n')
        sys.stdout.write(sep.join(str(arg) for arg in args) + end)

def cargar_configuracion_y_credenciales(config_path=None, credenciales_path=None):
    """
    Carga configuración y credenciales.
    
    Args:
        config_path: Ruta al archivo config.json
        credenciales_path: Ruta al archivo credenciales.json
    
    Returns:
        tuple: (config, credenciales)
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Buscar config.json
    if config_path is None:
        posibles_configs = [
            os.path.join(script_dir, "config.json"),
            os.path.join(script_dir, "config.test.json"),
            os.path.join(script_dir, "config.example.json")
        ]
        for config_file in posibles_configs:
            if os.path.exists(config_file):
                config_path = config_file
                break
    
    # Buscar credenciales.json
    if credenciales_path is None:
        posibles_credenciales = [
            os.path.join(script_dir, "credenciales.json"),
            os.path.join(script_dir, "credenciales.test.json"),
            os.path.join(script_dir, "credenciales.example.json")
        ]
        for cred_file in posibles_credenciales:
            if os.path.exists(cred_file):
                credenciales_path = cred_file
                break
    
    try:
        config = {"conexiones": {}}
        credenciales = {}
        
        if config_path and os.path.exists(config_path):
            # Python 2.x necesita abrir archivos sin encoding específico
            with open(config_path, 'r') as f:
                config = json.load(f)
            logging.info("Configuracion cargada: {}".format(config_path))
        else:
            logging.error("No se encontro archivo de configuracion")
        
        if credenciales_path and os.path.exists(credenciales_path):
            with open(credenciales_path, 'r') as f:
                credenciales = json.load(f)
            logging.info("Credenciales cargadas: {}".format(credenciales_path))
        else:
            logging.warning("No se encontro archivo de credenciales")
        
        return config, credenciales
    
    except ValueError as e:  # JSONDecodeError en Python 2 es ValueError
        logging.error("Error en formato JSON: {}".format(e))
        return {"conexiones": {}}, {}
    except Exception as e:
        logging.error("Error cargando archivos: {}".format(e))
        return {"conexiones": {}}, {}

def verificar_paramiko():
    """Verifica si paramiko está disponible."""
    if not PARAMIKO_DISPONIBLE:
        print_compatible("⚠️  Paramiko no está instalado")
        print_compatible("💡 Instala con: pip install 'paramiko<3.0.0'")
        return False
    return True

def verificar_ftplib():
    """Verifica si ftplib está disponible."""
    if not FTPLIB_DISPONIBLE:
        print_compatible("⚠️  FTPLIB no disponible")
        return False
    return True

def diagnosticar_conexion_local(conexion, verbose=False):
    """
    Diagnóstico para conexiones locales.
    
    Args:
        conexion (dict): Configuración de la conexión
        verbose (bool): Modo detallado
    """
    print_compatible("\n" + "=" * 50)
    print_compatible("📁 DIAGNOSTICO LOCAL: {}".format(conexion.get('alias', 'sin alias')))
    print_compatible("=" * 50)
    
    if 'rutas' not in conexion or not conexion['rutas']:
        print_compatible("❌ No hay rutas configuradas")
        return
    
    rutas_verificadas = 0
    rutas_con_problemas = 0
    
    for idx, ruta_config in enumerate(conexion['rutas'], 1):
        ruta = ruta_config.get('ruta', '')
        dias = ruta_config.get('dias', 0)
        mascara = ruta_config.get('mascara')
        
        print_compatible("\n  [{}/{}] 📂 Ruta: {}".format(idx, len(conexion['rutas']), ruta))
        print_compatible("     📅 Días configurados: {}".format(dias))
        if mascara:
            print_compatible("     🎭 Máscara configurada: '{}'".format(mascara))
        
        # Verificar si la ruta existe
        if os.path.exists(ruta):
            print_compatible("     ✅ La ruta existe")
            rutas_verificadas += 1
            
            # Verificar si es directorio
            if os.path.isdir(ruta):
                print_compatible("     📂 Es un directorio")
                
                try:
                    total_archivos = 0
                    archivos_antiguos = 0
                    limite_tiempo = time.time() - (dias * 86400) if dias > 0 else 0
                    
                    # Recorrer directorio (compatible Python 2.x)
                    for root, dirs, files in os.walk(unicode(ruta) if not PYTHON3 else ruta):
                        for file in files:
                            total_archivos += 1
                            
                            # Verificar máscara si está configurada
                            if mascara:
                                import fnmatch
                                if not fnmatch.fnmatch(file, mascara):
                                    continue
                            
                            # Verificar antigüedad si hay días configurados
                            if dias > 0:
                                try:
                                    filepath = os.path.join(root, file)
                                    mtime = os.path.getmtime(filepath)
                                    if mtime < limite_tiempo:
                                        archivos_antiguos += 1
                                except Exception:
                                    pass
                    
                    print_compatible("     📊 Total archivos: {}".format(total_archivos))
                    if dias > 0:
                        print_compatible("     ⏳ Archivos antiguos ({}+ días): {}".format(dias, archivos_antiguos))
                    
                except Exception as e:
                    print_compatible("     ⚠️ Error contando archivos: {}".format(e))
                
                # Verificar permisos
                if os.access(ruta, os.W_OK):
                    print_compatible("     ✅ Permisos de escritura: Sí")
                else:
                    print_compatible("     ❌ Permisos de escritura: No")
                    rutas_con_problemas += 1
                    
            elif os.path.isfile(ruta):
                print_compatible("     📄 Es un archivo (no un directorio)")
                rutas_con_problemas += 1
            else:
                print_compatible("     ⚠️ Existe pero no es directorio ni archivo")
                rutas_con_problemas += 1
        else:
            print_compatible("     ❌ La ruta NO existe")
            rutas_con_problemas += 1
            
            # Intentar encontrar rutas similares
            parent_dir = os.path.dirname(ruta)
            if parent_dir and os.path.exists(parent_dir):
                print_compatible("     💡 El directorio padre existe: {}".format(parent_dir))
                if verbose:
                    try:
                        contenido = os.listdir(parent_dir)[:5]
                        print_compatible("     📋 Contenido del directorio padre (primeros 5):")
                        for item in contenido:
                            print_compatible("         - {}".format(item))
                    except Exception:
                        pass
    
    # Resumen
    print_compatible("\n" + "-" * 40)
    print_compatible("📊 RESUMEN LOCAL:")
    print_compatible("  ✅ Rutas verificadas: {}".format(rutas_verificadas))
    print_compatible("  ❌ Rutas con problemas: {}".format(rutas_con_problemas))
    if rutas_con_problemas == 0:
        print_compatible("  🎉 Todas las rutas están listas para limpieza")

def diagnosticar_conexion_ssh(conexion, verbose=False):
    """
    Diagnóstico para conexiones SSH.
    
    Args:
        conexion (dict): Configuración de la conexión
        verbose (bool): Modo detallado
    """
    print_compatible("\n" + "=" * 50)
    print_compatible("🔐 DIAGNOSTICO SSH: {}".format(conexion.get('alias', 'sin alias')))
    print_compatible("=" * 50)
    
    if not verificar_paramiko():
        print_compatible("❌ Paramiko no disponible")
        return
    
    host = conexion.get('host', '')
    puerto = conexion.get('puerto', 22)
    usuario = conexion.get('usuario', '')
    contrasena = conexion.get('contrasena', '')
    necesita_sudo = conexion.get('necesita_sudo', False)
    
    if not host or not usuario:
        print_compatible("❌ Configuración incompleta (falta host o usuario)")
        return
    
    print_compatible("  🌐 Host: {}:{}".format(host, puerto))
    print_compatible("  👤 Usuario: {}".format(usuario))
    print_compatible("  ⚡ Sudo requerido: {}".format("Sí" if necesita_sudo else "No"))
    
    try:
        cliente_ssh = paramiko.SSHClient()
        cliente_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            cliente_ssh.connect(
                hostname=host,
                port=puerto,
                username=usuario,
                password=contrasena,
                timeout=10
            )
            print_compatible("  ✅ Conexión SSH exitosa")
            
            # Ejecutar comando básico para verificar
            stdin, stdout, stderr = cliente_ssh.exec_command("whoami && uname -a")
            salida = stdout.read().decode('utf-8').strip()
            errores = stderr.read().decode('utf-8').strip()
            
            if salida:
                print_compatible("  🖥️  Sistema: {}".format(salida.split('\n')[0]))
            
            # Verificar rutas configuradas
            if 'rutas' in conexion and conexion['rutas']:
                print_compatible("\n  🔍 Verificando rutas configuradas:")
                
                for idx, ruta_config in enumerate(conexion['rutas'], 1):
                    ruta = ruta_config.get('ruta', '')
                    dias = ruta_config.get('dias', 0)
                    mascara = ruta_config.get('mascara')
                    
                    print_compatible("\n    [{}/{}] 📂 Ruta: {}".format(
                        idx, len(conexion['rutas']), ruta))
                    print_compatible("       📅 Días: {}".format(dias))
                    if mascara:
                        print_compatible("       🎭 Máscara: '{}'".format(mascara))
                    
                    # Verificar si la ruta existe
                    comando = "{}ls -ld \"{}\" 2>/dev/null || echo 'NO_EXISTE'".format(
                        "sudo " if necesita_sudo else "", ruta)
                    stdin, stdout, stderr = cliente_ssh.exec_command(comando)
                    resultado = stdout.read().decode('utf-8').strip()
                    
                    if "NO_EXISTE" in resultado or "No such file or directory" in resultado:
                        print_compatible("       ❌ La ruta NO existe en el servidor")
                    else:
                        print_compatible("       ✅ La ruta existe")
                        
                        # Verificar permisos
                        comando_perm = "{}test -w \"{}\" && echo 'WRITABLE' || echo 'NOT_WRITABLE'".format(
                            "sudo " if necesita_sudo else "", ruta)
                        stdin, stdout, stderr = cliente_ssh.exec_command(comando_perm)
                        perm_result = stdout.read().decode('utf-8').strip()
                        
                        if "WRITABLE" in perm_result:
                            print_compatible("       ✅ Permisos de escritura: Sí")
                        else:
                            print_compatible("       ❌ Permisos de escritura: No")
                        
                        # Contar archivos (aproximado) si verbose
                        if verbose and dias > 0:
                            comando_find = "{}find \"{}\" -type f ".format(
                                "sudo " if necesita_sudo else "", ruta)
                            if mascara:
                                comando_find += "-name '{}' ".format(mascara)
                            comando_find += "-mtime +{} 2>/dev/null | wc -l".format(dias)
                            
                            stdin, stdout, stderr = cliente_ssh.exec_command(comando_find)
                            archivos_antiguos = stdout.read().decode('utf-8').strip()
                            
                            if archivos_antiguos.isdigit():
                                print_compatible("       📊 Archivos antiguos encontrados: {}".format(archivos_antiguos))
            
            # Verificar configuración sudo si es necesario
            if necesita_sudo:
                print_compatible("\n  🔧 Verificando configuración sudo:")
                comando_sudo = "sudo -n ls / >/dev/null 2>&1 && echo 'SUDO_OK' || echo 'SUDO_FAIL'"
                stdin, stdout, stderr = cliente_ssh.exec_command(comando_sudo)
                sudo_result = stdout.read().decode('utf-8').strip()
                
                if "SUDO_OK" in sudo_result:
                    print_compatible("      ✅ Sudo configurado correctamente")
                else:
                    print_compatible("      ❌ Problemas con sudo (puede pedir contraseña)")
            
            cliente_ssh.close()
            
        except paramiko.AuthenticationException:
            print_compatible("  ❌ Error de autenticación (credenciales incorrectas)")
        except paramiko.SSHException as e:
            print_compatible("  ❌ Error SSH: {}".format(str(e)))
        except Exception as e:
            print_compatible("  ❌ Error de conexión: {}".format(str(e)))
            
    except Exception as e:
        print_compatible("  ❌ Error general SSH: {}".format(str(e)))

def diagnosticar_conexion_sftp(conexion, verbose=False):
    """
    Diagnóstico para conexiones SFTP.
    
    Args:
        conexion (dict): Configuración de la conexión
        verbose (bool): Modo detallado
    """
    print_compatible("\n" + "=" * 50)
    print_compatible("📡 DIAGNOSTICO SFTP: {}".format(conexion.get('alias', 'sin alias')))
    print_compatible("=" * 50)
    
    if not verificar_paramiko():
        print_compatible("❌ Paramiko no disponible")
        return
    
    host = conexion.get('host', '')
    puerto = conexion.get('puerto', 22)
    usuario = conexion.get('usuario', '')
    contrasena = conexion.get('contrasena', '')
    
    if not host or not usuario:
        print_compatible("❌ Configuración incompleta (falta host o usuario)")
        return
    
    print_compatible("  🌐 Host: {}:{}".format(host, puerto))
    print_compatible("  👤 Usuario: {}".format(usuario))
    
    try:
        # Conectar al servidor SFTP
        transporte = paramiko.Transport((host, puerto))
        transporte.connect(username=usuario, password=contrasena)
        sftp = paramiko.SFTPClient.from_transport(transporte)
        
        print_compatible("  ✅ Conexión SFTP exitosa")
        
        # Obtener directorio actual
        try:
            directorio_actual = sftp.normalize('.')
            print_compatible("  📂 Directorio actual: {}".format(directorio_actual))
        except Exception as e:
            print_compatible("  ⚠️ No se pudo obtener directorio actual: {}".format(e))
        
        # Listar contenido del directorio actual si verbose
        if verbose:
            print_compatible("\n  📋 Contenido del directorio actual (primeros 10):")
            try:
                contenido = sftp.listdir('.')
                for item in contenido[:10]:
                    print_compatible("      📄 {}".format(item))
                if len(contenido) > 10:
                    print_compatible("      ... y {} elementos más".format(len(contenido) - 10))
            except Exception as e:
                print_compatible("      ❌ Error listando directorio: {}".format(e))
        
        # Verificar rutas configuradas
        if 'rutas' in conexion and conexion['rutas']:
            print_compatible("\n  🔍 Verificando rutas configuradas:")
            
            for idx, ruta_config in enumerate(conexion['rutas'], 1):
                ruta = ruta_config.get('ruta', '')
                dias = ruta_config.get('dias', 0)
                mascara = ruta_config.get('mascara')
                
                print_compatible("\n    [{}/{}] 📂 Ruta: {}".format(
                    idx, len(conexion['rutas']), ruta))
                print_compatible("       📅 Días: {}".format(dias))
                if mascara:
                    print_compatible("       🎭 Máscara: '{}'".format(mascara))
                
                try:
                    contenido = sftp.listdir(ruta)
                    print_compatible("       ✅ La ruta existe ({} elementos)".format(len(contenido)))
                    
                    # Verificar permisos de escritura
                    try:
                        test_file = "{}/test_permisos_diag.tmp".format(ruta.rstrip('/'))
                        with sftp.file(test_file, 'w') as f:
                            f.write("test")
                        sftp.remove(test_file)
                        print_compatible("       ✅ Permisos de escritura: Sí")
                    except Exception as e:
                        print_compatible("       ❌ Permisos de escritura: No ({})".format(e))
                    
                except Exception as e:
                    print_compatible("       ❌ La ruta NO existe o no es accesible: {}".format(e))
        
        sftp.close()
        transporte.close()
        
    except paramiko.AuthenticationException:
        print_compatible("  ❌ Error de autenticación (credenciales incorrectas)")
    except Exception as e:
        print_compatible("  ❌ Error de conexión SFTP: {}".format(str(e)))

def diagnosticar_conexion_ftp(conexion, verbose=False):
    """
    Diagnóstico para conexiones FTP.
    
    Args:
        conexion (dict): Configuración de la conexión
        verbose (bool): Modo detallado
    """
    print_compatible("\n" + "=" * 50)
    print_compatible("📁 DIAGNOSTICO FTP: {}".format(conexion.get('alias', 'sin alias')))
    print_compatible("=" * 50)
    
    if not verificar_ftplib():
        print_compatible("❌ ftplib no disponible")
        return
    
    host = conexion.get('host', '')
    puerto = conexion.get('puerto', 21)
    usuario = conexion.get('usuario', '')
    contrasena = conexion.get('contrasena', '')
    
    if not host or not usuario:
        print_compatible("❌ Configuración incompleta (falta host o usuario)")
        return
    
    print_compatible("  🌐 Host: {}:{}".format(host, puerto))
    print_compatible("  👤 Usuario: {}".format(usuario))
    
    try:
        ftp = ftplib.FTP()
        ftp.connect(host, puerto, timeout=10)
        ftp.login(usuario, contrasena)
        
        # Obtener mensaje de bienvenida
        welcome_msg = ftp.getwelcome()
        if isinstance(welcome_msg, bytes):  # Python 3
            welcome_msg = welcome_msg.decode('utf-8', errors='ignore')
        
        print_compatible("  ✅ Conexión FTP exitosa")
        if welcome_msg:
            print_compatible("  🖥️  Servidor: {}".format(welcome_msg.split('\n')[0]))
        
        # Obtener directorio actual
        try:
            directorio_actual = ftp.pwd()
            print_compatible("  📂 Directorio actual: {}".format(directorio_actual))
        except Exception:
            print_compatible("  ⚠️ No se pudo obtener directorio actual")
        
        # Listar contenido del directorio actual si verbose
        if verbose:
            print_compatible("\n  📋 Contenido del directorio actual (primeros 10):")
            try:
                contenido = []
                ftp.retrlines('LIST', contenido.append)
                for item in contenido[:10]:
                    print_compatible("      📄 {}".format(item))
                if len(contenido) > 10:
                    print_compatible("      ... y {} elementos más".format(len(contenido) - 10))
            except Exception as e:
                print_compatible("      ❌ Error listando directorio: {}".format(e))
        
        # Verificar rutas configuradas
        if 'rutas' in conexion and conexion['rutas']:
            print_compatible("\n  🔍 Verificando rutas configuradas:")
            
            for idx, ruta_config in enumerate(conexion['rutas'], 1):
                ruta = ruta_config.get('ruta', '')
                dias = ruta_config.get('dias', 0)
                mascara = ruta_config.get('mascara')
                
                print_compatible("\n    [{}/{}] 📂 Ruta: {}".format(
                    idx, len(conexion['rutas']), ruta))
                print_compatible("       📅 Días: {}".format(dias))
                if mascara:
                    print_compatible("       🎭 Máscara: '{}'".format(mascara))
                
                try:
                    ftp.cwd(ruta)
                    print_compatible("       ✅ La ruta existe y es accesible")
                    
                    # Volver al directorio anterior
                    ftp.cwd('..')
                        
                except Exception as e:
                    print_compatible("       ❌ La ruta NO existe o no es accesible: {}".format(e))
        
        ftp.quit()
        
    except Exception as e:
        print_compatible("  ❌ Error de conexión FTP: {}".format(str(e)))

def ejecutar_diagnostico_completo(config_file=None, credenciales_file=None, 
                                 tipo_filtro='all', alias_filtro=None, verbose=False):
    """
    Ejecuta diagnóstico completo para todas las conexiones.
    
    Args:
        config_file (str): Ruta al archivo de configuración
        credenciales_file (str): Ruta al archivo de credenciales
        tipo_filtro (str): Filtrar por tipo (local, ssh, sftp, ftp, all)
        alias_filtro (str): Filtrar por alias específico
        verbose (bool): Modo detallado
    """
    print_compatible("=" * 70)
    print_compatible("🔍 DIAGNOSTICO DE ACCESO - Python {}.{}".format(
        sys.version_info[0], sys.version_info[1]))
    print_compatible("=" * 70)
    print_compatible("Fecha: {}".format(time.strftime("%Y-%m-%d %H:%M:%S")))
    
    # Cargar configuración y credenciales
    config, credenciales = cargar_configuracion_y_credenciales(config_file, credenciales_file)
    
    if not config.get('conexiones'):
        print_compatible("\n❌ No se encontraron conexiones en la configuracion")
        return
    
    # Filtrar conexiones
    conexiones_filtradas = {}
    for alias, conexion_config in config['conexiones'].items():
        # Filtrar por alias
        if alias_filtro and alias != alias_filtro:
            continue
        
        # Filtrar por tipo
        tipo = conexion_config.get('tipo', '').lower()
        if tipo_filtro != 'all' and tipo != tipo_filtro:
            continue
        
        conexiones_filtradas[alias] = conexion_config
    
    if not conexiones_filtradas:
        print_compatible("\n❌ No hay conexiones que coincidan con los filtros:")
        if tipo_filtro != 'all':
            print_compatible("   Tipo: {}".format(tipo_filtro))
        if alias_filtro:
            print_compatible("   Alias: {}".format(alias_filtro))
        return
    
    print_compatible("\n📋 Conexiones a diagnosticar: {}".format(len(conexiones_filtradas)))
    
    # Diagnosticar cada conexión
    for alias, conexion_config in conexiones_filtradas.items():
        # Combinar configuración con credenciales
        conexion = conexion_config.copy()
        conexion['alias'] = alias
        
        if alias in credenciales:
            conexion.update(credenciales[alias])
        else:
            print_compatible("\n⚠️ No se encontraron credenciales para '{}'".format(alias))
        
        tipo = conexion.get('tipo', '').lower()
        
        # Ejecutar diagnóstico según el tipo
        if tipo == 'local':
            diagnosticar_conexion_local(conexion, verbose)
        elif tipo == 'ssh':
            diagnosticar_conexion_ssh(conexion, verbose)
        elif tipo == 'sftp':
            diagnosticar_conexion_sftp(conexion, verbose)
        elif tipo == 'ftp':
            diagnosticar_conexion_ftp(conexion, verbose)
        else:
            print_compatible("\n❌ Tipo de conexion desconocido: {}".format(tipo))
    
    print_compatible("\n" + "=" * 70)
    print_compatible("✅ DIAGNOSTICO COMPLETADO")
    print_compatible("=" * 70)
    
    # Mostrar recomendaciones
    mostrar_recomendaciones()

def mostrar_recomendaciones():
    """Muestra recomendaciones basadas en hallazgos comunes."""
    print_compatible("\n💡 RECOMENDACIONES GENERALES:")
    print_compatible("  1. ✅ Verifica que todas las rutas configuradas existan")
    print_compatible("  2. 🔐 Confirma los permisos de escritura en cada ruta")
    print_compatible("  3. 🔑 Asegurate de que las credenciales sean correctas")
    print_compatible("  4. 🌐 Valida que los servidores remotos esten accesibles")
    print_compatible("  5. 🎭 Revisa que las mascaras de archivos sean correctas")
    print_compatible("  6. 📁 Para SSH/SFTP: instala paramiko: pip install 'paramiko<3.0.0'")

def mostrar_ayuda():
    """Muestra mensaje de ayuda."""
    print_compatible(__doc__)

def main():
    """
    Función principal del script de diagnóstico.
    Compatible con Python 2.x y 3.x.
    """
    # Argumentos simples para Python 2.x (sin argparse si no está disponible)
    config_file = None
    credenciales_file = None
    tipo_filtro = 'all'
    alias_filtro = None
    verbose = False
    
    # Parsear argumentos manualmente para compatibilidad
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        
        if arg in ['--help', '-h']:
            mostrar_ayuda()
            return
        elif arg in ['--verbose', '-v']:
            verbose = True
        elif arg == '--config' and i + 1 < len(args):
            config_file = args[i + 1]
            i += 1
        elif arg == '--credenciales' and i + 1 < len(args):
            credenciales_file = args[i + 1]
            i += 1
        elif arg == '--tipo' and i + 1 < len(args):
            tipo_filtro = args[i + 1].lower()
            i += 1
        elif arg == '--alias' and i + 1 < len(args):
            alias_filtro = args[i + 1]
            i += 1
        else:
            print_compatible("⚠️  Argumento desconocido: {}".format(arg))
            print_compatible("💡 Usa --help para ver las opciones disponibles")
        
        i += 1
    
    # Ejecutar diagnóstico
    ejecutar_diagnostico_completo(
        config_file=config_file,
        credenciales_file=credenciales_file,
        tipo_filtro=tipo_filtro,
        alias_filtro=alias_filtro,
        verbose=verbose
    )

if __name__ == "__main__":
    main()