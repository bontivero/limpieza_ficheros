#!/usr/bin/env python3
"""
Script de diagnóstico completo para todos los tipos de acceso:
Local, SSH, SFTP y FTP.

Analiza la configuración y verifica conectividad, rutas, permisos y más.
"""

import json
import logging
import os
import posixpath
import sys
import time
import paramiko
import ftplib
from pathlib import Path

# Configuración básica de logging para diagnóstico
logging.basicConfig(level=logging.INFO, format='%(message)s')

def cargar_configuracion_y_credenciales(config_path=None, credenciales_path=None):
    """
    Carga configuración y credenciales.
    
    Args:
        config_path: Ruta al archivo config.json (None = buscar automáticamente)
        credenciales_path: Ruta al archivo credenciales.json (None = buscar automáticamente)
    
    Returns:
        tuple: (config, credenciales)
    """
    script_dir = Path(__file__).parent
    
    # Buscar config.json
    if config_path is None:
        posibles_configs = [
            script_dir / "config.json",
            script_dir / "config.test.json",
            script_dir / "config.example.json"
        ]
        for config_file in posibles_configs:
            if config_file.exists():
                config_path = config_file
                break
    
    # Buscar credenciales.json
    if credenciales_path is None:
        posibles_credenciales = [
            script_dir / "credenciales.json",
            script_dir / "credenciales.test.json",
            script_dir / "credenciales.example.json"
        ]
        for cred_file in posibles_credenciales:
            if cred_file.exists():
                credenciales_path = cred_file
                break
    
    try:
        if config_path and config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logging.info(f"✅ Configuración cargada: {config_path}")
        else:
            logging.error(f"❌ No se encontró archivo de configuración")
            config = {"conexiones": {}}
        
        if credenciales_path and credenciales_path.exists():
            with open(credenciales_path, 'r', encoding='utf-8') as f:
                credenciales = json.load(f)
            logging.info(f"✅ Credenciales cargadas: {credenciales_path}")
        else:
            logging.warning(f"⚠️ No se encontró archivo de credenciales")
            credenciales = {}
        
        return config, credenciales
    
    except json.JSONDecodeError as e:
        logging.error(f"❌ Error en formato JSON: {e}")
        return {}, {}
    except Exception as e:
        logging.error(f"❌ Error cargando archivos: {e}")
        return {}, {}

def obtener_rutas_para_diagnostico(conexion):
    """
    Obtiene las rutas para diagnóstico desde la configuración de la conexión.
    """
    rutas_diagnostico = set()
    
    # Rutas base que siempre verificamos
    rutas_base = ['/', '/home', '/tmp', '/var', '/backup', '/opt', '/usr/local']
    
    for ruta in rutas_base:
        rutas_diagnostico.add(ruta)
    
    # Agregar todas las rutas de la conexión
    if 'rutas' in conexion:
        for ruta_config in conexion['rutas']:
            ruta = ruta_config.get('ruta', '')
            if ruta:
                rutas_diagnostico.add(ruta)
                
                # Agregar componentes de la ruta para diagnóstico completo
                partes = ruta.split('/')
                camino_parcial = ''
                for parte in partes:
                    if parte:
                        camino_parcial = posixpath.join(camino_parcial, parte)
                        if camino_parcial and camino_parcial not in rutas_diagnostico:
                            rutas_diagnostico.add('/' + camino_parcial if not camino_parcial.startswith('/') else camino_parcial)
    
    # Agregar directorio home del usuario si SSH/SFTP
    if 'usuario' in conexion:
        rutas_diagnostico.add(f"/home/{conexion['usuario']}")
        rutas_diagnostico.add(f"/Users/{conexion['usuario']}")  # Para macOS
    
    return sorted(list(rutas_diagnostico))

def diagnosticar_conexion_local(conexion):
    """
    Diagnóstico para conexiones locales.
    """
    print(f"\n📁 Diagnóstico LOCAL para: {conexion.get('alias', 'sin alias')}")
    print("-" * 50)
    
    if 'rutas' not in conexion or not conexion['rutas']:
        print("❌ No hay rutas configuradas")
        return
    
    for ruta_config in conexion['rutas']:
        ruta = ruta_config.get('ruta', '')
        dias = ruta_config.get('dias', 0)
        mascara = ruta_config.get('mascara')
        
        print(f"\n  🔍 Ruta: {ruta}")
        print(f"    📅 Días configurados: {dias}")
        if mascara:
            print(f"    🎭 Máscara configurada: '{mascara}'")
        
        # Verificar si la ruta existe
        if os.path.exists(ruta):
            print(f"    ✅ La ruta existe")
            
            # Verificar si es directorio
            if os.path.isdir(ruta):
                print(f"    📂 Es un directorio")
                
                # Contar archivos
                try:
                    total_archivos = 0
                    archivos_antiguos = 0
                    limite_tiempo = time.time() - (dias * 86400) if dias > 0 else 0
                    
                    for root, dirs, files in os.walk(ruta):
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
                                except:
                                    pass
                    
                    print(f"    📊 Total archivos: {total_archivos}")
                    if dias > 0:
                        print(f"    ⏳ Archivos antiguos ({dias}+ días): {archivos_antiguos}")
                    
                except Exception as e:
                    print(f"    ⚠️ Error contando archivos: {e}")
                
                # Verificar permisos
                if os.access(ruta, os.W_OK):
                    print(f"    ✅ Permisos de escritura: Sí")
                else:
                    print(f"    ❌ Permisos de escritura: No")
                    
            elif os.path.isfile(ruta):
                print(f"    📄 Es un archivo (no un directorio)")
            else:
                print(f"    ⚠️ Existe pero no es directorio ni archivo")
        else:
            print(f"    ❌ La ruta NO existe")
            
            # Intentar encontrar rutas similares
            parent_dir = os.path.dirname(ruta)
            if parent_dir and os.path.exists(parent_dir):
                print(f"    💡 El directorio padre existe: {parent_dir}")
                try:
                    contenido = os.listdir(parent_dir)[:5]
                    print(f"    📋 Contenido del directorio padre (primeros 5):")
                    for item in contenido:
                        print(f"        - {item}")
                except:
                    pass

def diagnosticar_conexion_ssh(conexion):
    """
    Diagnóstico para conexiones SSH.
    """
    print(f"\n🔐 Diagnóstico SSH para: {conexion.get('alias', 'sin alias')}")
    print("-" * 50)
    
    host = conexion.get('host', '')
    puerto = conexion.get('puerto', 22)
    usuario = conexion.get('usuario', '')
    contrasena = conexion.get('contrasena', '')
    necesita_sudo = conexion.get('necesita_sudo', False)
    
    if not host or not usuario:
        print("❌ Configuración incompleta (falta host o usuario)")
        return
    
    print(f"  🌐 Host: {host}:{puerto}")
    print(f"  👤 Usuario: {usuario}")
    print(f"  ⚡ Sudo requerido: {'Sí' if necesita_sudo else 'No'}")
    
    try:
        # Verificar paramiko disponible
        import paramiko
        
        # Conectar al servidor
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
            print(f"  ✅ Conexión SSH exitosa")
            
            # Ejecutar comando básico para verificar
            stdin, stdout, stderr = cliente_ssh.exec_command("whoami && uname -a")
            salida = stdout.read().decode().strip()
            errores = stderr.read().decode().strip()
            
            if salida:
                print(f"  🖥️  Sistema: {salida}")
            
            # Verificar rutas configuradas
            if 'rutas' in conexion and conexion['rutas']:
                print(f"\n  🔍 Verificando rutas configuradas:")
                
                for ruta_config in conexion['rutas']:
                    ruta = ruta_config.get('ruta', '')
                    dias = ruta_config.get('dias', 0)
                    mascara = ruta_config.get('mascara')
                    
                    print(f"\n    📂 Ruta: {ruta}")
                    print(f"      📅 Días: {dias}")
                    if mascara:
                        print(f"      🎭 Máscara: '{mascara}'")
                    
                    # Verificar si la ruta existe
                    comando = f"{'sudo ' if necesita_sudo else ''}ls -ld \"{ruta}\" 2>/dev/null || echo 'NO_EXISTE'"
                    stdin, stdout, stderr = cliente_ssh.exec_command(comando)
                    resultado = stdout.read().decode().strip()
                    
                    if "NO_EXISTE" in resultado or "No such file or directory" in resultado:
                        print(f"      ❌ La ruta NO existe en el servidor")
                    else:
                        print(f"      ✅ La ruta existe")
                        
                        # Verificar permisos
                        comando_perm = f"{'sudo ' if necesita_sudo else ''}test -w \"{ruta}\" && echo 'WRITABLE' || echo 'NOT_WRITABLE'"
                        stdin, stdout, stderr = cliente_ssh.exec_command(comando_perm)
                        perm_result = stdout.read().decode().strip()
                        
                        if "WRITABLE" in perm_result:
                            print(f"      ✅ Permisos de escritura: Sí")
                        else:
                            print(f"      ❌ Permisos de escritura: No")
                        
                        # Contar archivos (aproximado)
                        if dias > 0:
                            comando_find = f"{'sudo ' if necesita_sudo else ''}find \"{ruta}\" -type f "
                            if mascara:
                                comando_find += f"-name '{mascara}' "
                            comando_find += f"-mtime +{dias} 2>/dev/null | wc -l"
                            
                            stdin, stdout, stderr = cliente_ssh.exec_command(comando_find)
                            archivos_antiguos = stdout.read().decode().strip()
                            
                            if archivos_antiguos.isdigit():
                                print(f"      📊 Archivos antiguos encontrados: {archivos_antiguos}")
            
            # Verificar configuración sudo si es necesario
            if necesita_sudo:
                print(f"\n  🔧 Verificando configuración sudo:")
                comando_sudo = f"sudo -n ls / >/dev/null 2>&1 && echo 'SUDO_OK' || echo 'SUDO_FAIL'"
                stdin, stdout, stderr = cliente_ssh.exec_command(comando_sudo)
                sudo_result = stdout.read().decode().strip()
                
                if "SUDO_OK" in sudo_result:
                    print(f"      ✅ Sudo configurado correctamente")
                else:
                    print(f"      ❌ Problemas con sudo (puede pedir contraseña)")
            
            cliente_ssh.close()
            
        except paramiko.AuthenticationException:
            print(f"  ❌ Error de autenticación (credenciales incorrectas)")
        except paramiko.SSHException as e:
            print(f"  ❌ Error SSH: {e}")
        except Exception as e:
            print(f"  ❌ Error de conexión: {e}")
            
    except ImportError:
        print(f"  ❌ Paramiko no está instalado")
        print(f"  💡 Instala con: pip install paramiko")

def diagnosticar_conexion_sftp(conexion):
    """
    Diagnóstico para conexiones SFTP.
    """
    print(f"\n📡 Diagnóstico SFTP para: {conexion.get('alias', 'sin alias')}")
    print("-" * 50)
    
    host = conexion.get('host', '')
    puerto = conexion.get('puerto', 22)
    usuario = conexion.get('usuario', '')
    contrasena = conexion.get('contrasena', '')
    
    if not host or not usuario:
        print("❌ Configuración incompleta (falta host o usuario)")
        return
    
    print(f"  🌐 Host: {host}:{puerto}")
    print(f"  👤 Usuario: {usuario}")
    
    try:
        import paramiko
        
        # Conectar al servidor SFTP
        transporte = paramiko.Transport((host, puerto))
        transporte.connect(username=usuario, password=contrasena)
        sftp = paramiko.SFTPClient.from_transport(transporte)
        
        print(f"  ✅ Conexión SFTP exitosa")
        
        # Obtener directorio actual
        try:
            directorio_actual = sftp.normalize('.')
            print(f"  📂 Directorio actual: {directorio_actual}")
        except Exception as e:
            print(f"  ⚠️ No se pudo obtener directorio actual: {e}")
        
        # Listar contenido del directorio actual
        print(f"\n  📋 Contenido del directorio actual (primeros 10):")
        try:
            contenido = sftp.listdir('.')
            for item in contenido[:10]:
                print(f"      📄 {item}")
            if len(contenido) > 10:
                print(f"      ... y {len(contenido) - 10} elementos más")
        except Exception as e:
            print(f"      ❌ Error listando directorio: {e}")
        
        # Verificar rutas configuradas
        if 'rutas' in conexion and conexion['rutas']:
            print(f"\n  🔍 Verificando rutas configuradas:")
            
            for ruta_config in conexion['rutas']:
                ruta = ruta_config.get('ruta', '')
                dias = ruta_config.get('dias', 0)
                mascara = ruta_config.get('mascara')
                
                print(f"\n    📂 Ruta: {ruta}")
                print(f"      📅 Días: {dias}")
                if mascara:
                    print(f"      🎭 Máscara: '{mascara}'")
                
                try:
                    contenido = sftp.listdir(ruta)
                    print(f"      ✅ La ruta existe ({len(contenido)} elementos)")
                    
                    # Verificar permisos de escritura
                    try:
                        test_file = posixpath.join(ruta, "test_permisos_diag.tmp")
                        with sftp.file(test_file, 'w') as f:
                            f.write("test")
                        sftp.remove(test_file)
                        print(f"      ✅ Permisos de escritura: Sí")
                    except Exception as e:
                        print(f"      ❌ Permisos de escritura: No ({e})")
                    
                except Exception as e:
                    print(f"      ❌ La ruta NO existe o no es accesible: {e}")
        
        sftp.close()
        transporte.close()
        
    except paramiko.AuthenticationException:
        print(f"  ❌ Error de autenticación (credenciales incorrectas)")
    except Exception as e:
        print(f"  ❌ Error de conexión SFTP: {e}")

def diagnosticar_conexion_ftp(conexion):
    """
    Diagnóstico para conexiones FTP.
    """
    print(f"\n📁 Diagnóstico FTP para: {conexion.get('alias', 'sin alias')}")
    print("-" * 50)
    
    host = conexion.get('host', '')
    puerto = conexion.get('puerto', 21)
    usuario = conexion.get('usuario', '')
    contrasena = conexion.get('contrasena', '')
    
    if not host or not usuario:
        print("❌ Configuración incompleta (falta host o usuario)")
        return
    
    print(f"  🌐 Host: {host}:{puerto}")
    print(f"  👤 Usuario: {usuario}")
    
    try:
        ftp = ftplib.FTP()
        ftp.connect(host, puerto, timeout=10)
        ftp.login(usuario, contrasena)
        
        print(f"  ✅ Conexión FTP exitosa")
        print(f"  🖥️  Servidor: {ftp.getwelcome().split('\n')[0]}")
        
        # Obtener directorio actual
        try:
            directorio_actual = ftp.pwd()
            print(f"  📂 Directorio actual: {directorio_actual}")
        except:
            print(f"  ⚠️ No se pudo obtener directorio actual")
        
        # Listar contenido del directorio actual
        print(f"\n  📋 Contenido del directorio actual (primeros 10):")
        try:
            contenido = []
            ftp.retrlines('LIST', contenido.append)
            for item in contenido[:10]:
                print(f"      📄 {item}")
            if len(contenido) > 10:
                print(f"      ... y {len(contenido) - 10} elementos más")
        except Exception as e:
            print(f"      ❌ Error listando directorio: {e}")
        
        # Verificar rutas configuradas
        if 'rutas' in conexion and conexion['rutas']:
            print(f"\n  🔍 Verificando rutas configuradas:")
            
            for ruta_config in conexion['rutas']:
                ruta = ruta_config.get('ruta', '')
                dias = ruta_config.get('dias', 0)
                mascara = ruta_config.get('mascara')
                
                print(f"\n    📂 Ruta: {ruta}")
                print(f"      📅 Días: {dias}")
                if mascara:
                    print(f"      🎭 Máscara: '{mascara}'")
                
                try:
                    ftp.cwd(ruta)
                    print(f"      ✅ La ruta existe y es accesible")
                    
                    # Verificar que podemos listar contenido
                    try:
                        contenido = []
                        ftp.retrlines('LIST', lambda x: contenido.append(x))
                        print(f"      📊 Elementos en la ruta: {len(contenido)}")
                        
                        # Volver al directorio anterior
                        ftp.cwd('..')
                    except:
                        print(f"      ⚠️ No se pudo listar contenido")
                        
                except Exception as e:
                    print(f"      ❌ La ruta NO existe o no es accesible: {e}")
        
        ftp.quit()
        
    except ftplib.error_perm as e:
        print(f"  ❌ Error de permisos FTP: {e}")
    except ftplib.all_errors as e:
        print(f"  ❌ Error de conexión FTP: {e}")
    except Exception as e:
        print(f"  ❌ Error general FTP: {e}")

def ejecutar_diagnostico_completo(config_file=None, credenciales_file=None):
    """
    Ejecuta diagnóstico completo para todas las conexiones.
    """
    print("=" * 70)
    print("🔍 DIAGNÓSTICO COMPLETO - TODOS LOS TIPOS DE ACCESO")
    print("=" * 70)
    
    # Cargar configuración y credenciales
    config, credenciales = cargar_configuracion_y_credenciales(config_file, credenciales_file)
    
    if not config.get('conexiones'):
        print("❌ No se encontraron conexiones en la configuración")
        return
    
    print(f"📋 Conexiones encontradas: {len(config['conexiones'])}")
    
    # Diagnosticar cada conexión
    for alias, conexion_config in config['conexiones'].items():
        print(f"\n{'='*60}")
        print(f"🚀 INICIANDO DIAGNÓSTICO: {alias}")
        print(f"{'='*60}")
        
        # Combinar configuración con credenciales
        conexion = conexion_config.copy()
        conexion['alias'] = alias
        
        if alias in credenciales:
            conexion.update(credenciales[alias])
        else:
            print(f"⚠️ No se encontraron credenciales para '{alias}'")
        
        tipo = conexion.get('tipo', '').lower()
        
        # Ejecutar diagnóstico según el tipo
        if tipo == 'local':
            diagnosticar_conexion_local(conexion)
        elif tipo == 'ssh':
            diagnosticar_conexion_ssh(conexion)
        elif tipo == 'sftp':
            diagnosticar_conexion_sftp(conexion)
        elif tipo == 'ftp':
            diagnosticar_conexion_ftp(conexion)
        else:
            print(f"❌ Tipo de conexión desconocido: {tipo}")
    
    print(f"\n{'='*70}")
    print("✅ DIAGNÓSTICO COMPLETADO")
    print(f"{'='*70}")

def main():
    """
    Función principal del script de diagnóstico.
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Diagnóstico completo para conexiones Local, SSH, SFTP y FTP',
        epilog='Ejemplos:\n'
               '  python diagnostico_completo.py\n'
               '  python diagnostico_completo.py --config mi_config.json\n'
               '  python diagnostico_completo.py --tipo ssh\n'
               '  python diagnostico_completo.py --alias mi_servidor',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--config',
        help='Ruta al archivo de configuración (default: busca config.json en directorio actual)'
    )
    
    parser.add_argument(
        '--credenciales',
        help='Ruta al archivo de credenciales (default: busca credenciales.json en directorio actual)'
    )
    
    parser.add_argument(
        '--tipo',
        choices=['local', 'ssh', 'sftp', 'ftp', 'all'],
        default='all',
        help='Tipo de conexión a diagnosticar (default: all/todos)'
    )
    
    parser.add_argument(
        '--alias',
        help='Diagnosticar solo una conexión específica por su alias'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Mostrar información detallada'
    )
    
    args = parser.parse_args()
    
    print("🛠️  SCRIPT DE DIAGNÓSTICO COMPLETO v2.0")
    print("📅 Fecha: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    print()
    
    # Ejecutar diagnóstico completo
    ejecutar_diagnostico_completo(args.config, args.credenciales)
    
    print("\n💡 RECOMENDACIONES:")
    print("  1. Verifica que todas las rutas configuradas existan")
    print("  2. Confirma los permisos de escritura en cada ruta")
    print("  3. Asegúrate de que las credenciales sean correctas")
    print("  4. Valida que los servidores remotos estén accesibles")
    print("  5. Revisa que las máscaras de archivos sean correctas")

if __name__ == "__main__":
    main()