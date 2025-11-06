#!/usr/bin/env python3
"""
Script de diagnóstico para SFTP usando rutas dinámicas de config.json
"""

import json
import logging
import paramiko
import posixpath
from pathlib import Path

def obtener_rutas_para_diagnostico(conexion):
    """
    Obtiene las rutas para diagnóstico desde la configuración de la conexión.
    """
    rutas_diagnostico = set()
    
    # Rutas base que siempre verificamos
    rutas_base = ['/', '/home', '/tmp', '/var', '/backup']
    
    for ruta in rutas_base:
        rutas_diagnostico.add(ruta)
    
    # Agregar todas las rutas de la conexión
    if 'rutas' in conexion:
        for ruta_config in conexion['rutas']:
            ruta = ruta_config['ruta']
            rutas_diagnostico.add(ruta)
            
            # Agregar componentes de la ruta para diagnóstico completo
            partes = ruta.split('/')
            camino_parcial = ''
            for parte in partes:
                if parte:
                    camino_parcial = posixpath.join(camino_parcial, parte)
                    if camino_parcial and camino_parcial not in rutas_diagnostico:
                        rutas_diagnostico.add(camino_parcial)
    
    # Agregar directorio home del usuario
    if 'usuario' in conexion:
        rutas_diagnostico.add(f"/home/{conexion['usuario']}")
    
    return sorted(list(rutas_diagnostico))

def diagnosticar_servidor_sftp(host, puerto, usuario, contraseña, rutas_conexion):
    """Realiza diagnóstico completo del servidor SFTP."""
    
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    
    print("=" * 60)
    print("🔍 DIAGNÓSTICO SERVIDOR SFTP")
    print("=" * 60)
    
    try:
        # Conectar al servidor
        transporte = paramiko.Transport((host, puerto))
        transporte.connect(username=usuario, password=contraseña)
        sftp = paramiko.SFTPClient.from_transport(transporte)
        
        print(f"✅ Conexión exitosa a {host}:{puerto}")
        print(f"👤 Usuario: {usuario}")
        
        # Obtener directorio actual
        try:
            directorio_actual = sftp.normalize('.')
            print(f"📂 Directorio actual: {directorio_actual}")
        except Exception as e:
            print(f"⚠️ No se pudo obtener directorio actual: {e}")
        
        # Listar contenido del directorio actual
        print("\n📋 Contenido del directorio actual:")
        try:
            contenido = sftp.listdir('.')
            for item in contenido[:15]:  # Mostrar primeros 15 elementos
                print(f"   📄 {item}")
            if len(contenido) > 15:
                print(f"   ... y {len(contenido) - 15} elementos más")
        except Exception as e:
            print(f"❌ Error listando directorio: {e}")
        
        # Verificar rutas desde config.json
        print(f"\n🔍 Verificando {len(rutas_conexion)} rutas desde config.json:")
        rutas_existentes = []
        rutas_inexistentes = []
        
        for ruta in rutas_conexion:
            try:
                contenido = sftp.listdir(ruta)
                print(f"   ✅ {ruta} - EXISTE ({len(contenido)} elementos)")
                rutas_existentes.append(ruta)
            except Exception as e:
                print(f"   ❌ {ruta} - NO EXISTE")
                rutas_inexistentes.append(ruta)
        
        # Verificar permisos de escritura
        print("\n🔐 Verificando permisos de escritura:")
        for ruta in rutas_existentes[:3]:  # Verificar solo 3 rutas existentes
            if ruta != '/':
                try:
                    test_file = posixpath.join(ruta, "test_permisos.txt")
                    with sftp.file(test_file, 'w') as f:
                        f.write("test")
                    sftp.remove(test_file)
                    print(f"   ✅ Permisos escritura en: {ruta}")
                except Exception as e:
                    print(f"   ❌ Sin permisos escritura en {ruta}: {e}")
        
        sftp.close()
        transporte.close()
        
        # Resumen
        print("\n" + "=" * 60)
        print("📊 RESUMEN DIAGNÓSTICO:")
        print(f"   ✅ Rutas existentes: {len(rutas_existentes)}")
        print(f"   ❌ Rutas inexistentes: {len(rutas_inexistentes)}")
        
        if rutas_inexistentes:
            print("\n💡 RECOMENDACIONES:")
            print("   Las siguientes rutas configuradas no existen:")
            for ruta in rutas_inexistentes:
                print(f"   - {ruta}")
            
            if rutas_existentes:
                print("\n   Rutas existentes que podrías usar:")
                for ruta in rutas_existentes[:5]:
                    print(f"   - {ruta}")
        
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error de conexión: {e}")

if __name__ == "__main__":
    # Cargar configuración y credenciales
    config_file = Path(__file__).parent / "config.json"
    credenciales_file = Path(__file__).parent / "credenciales.json"
    
    if config_file.exists() and credenciales_file.exists():
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        with open(credenciales_file, 'r') as f:
            credenciales = json.load(f)
        
        for alias, conexion_config in config.get('conexiones', {}).items():
            if conexion_config.get('tipo') == 'sftp' and alias in credenciales:
                print(f"🔍 Diagnosticando servidor: {alias}")
                
                # Combinar configuración
                conexion = {**conexion_config, **credenciales[alias]}
                
                # Obtener rutas para diagnóstico
                rutas_diagnostico = obtener_rutas_para_diagnostico(conexion)
                
                diagnosticar_servidor_sftp(
                    conexion['host'],
                    conexion.get('puerto', 22),
                    conexion['usuario'],
                    conexion['contrasena'],
                    rutas_diagnostico
                )
                break
    else:
        print("❌ No se encontraron archivos config.json y/o credenciales.json")
        print("💡 Asegúrate de que estén en el mismo directorio que este script")