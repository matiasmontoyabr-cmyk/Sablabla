import bcrypt
import sqlite3
import time
from db import db
from functools import wraps
from getpass import getpass
from utiles import pedir_entero, pedir_confirmacion, opcion_menu

class SesionActiva:
    def __init__(self):
        self.usuario = "Observador"
        self.nivel_acceso = 0
        self.sesion_activa = False
        self.ultima_autenticacion = 0
        self.duracion_sesion = {
            0: 0,
            1: 300,
            2: 300,
            3: 300
        }
    
    def verificar_acceso(self, nivel_requerido):
        # Verifica si el usuario tiene permiso y si la sesión temporal sigue activa.
        
        # Verifica si el usuario tiene permiso
        if self.nivel_acceso < nivel_requerido:
            return False, "permiso"
        
        # Si el nivel requerido es 0, no necesita sesión activa
        if nivel_requerido == 0:
            return True, None
        
        # Si tiene el permiso, verifica si la sesión está activa
        if not self.sesion_activa:
            return False, "inactiva"
        
        # Finalmente, verifica si la sesión temporal ha expirado
        duracion = self.duracion_sesion.get(self.nivel_acceso, 300)
        if time.time() - self.ultima_autenticacion > duracion > 0:
            self.cerrar()
            return False, "expirada"
        
        return True, None
    
    def iniciar(self, usuario, nivel_acceso):
        # Inicializa la sesión
        self.usuario = usuario
        self.nivel_acceso = nivel_acceso
        self.sesion_activa = True
        self.ultima_autenticacion = time.time()
    
    def cerrar(self):
        """Limpia el estado de la sesión."""
        self.usuario = "Observador"
        self.nivel_acceso = 0
        self.sesion_activa = False
        self.ultima_autenticacion = 0
        print("\n👋 Sesión cerrada.")
    
    def refrescar(self):
        """Actualiza el tiempo de la última autenticación."""
        if self.sesion_activa:
            self.ultima_autenticacion = time.time()

sesion = SesionActiva()

def login(usuario, contraseña):
    # Verifica las credenciales y establece la sesión.
    try:
        usuario_en_db = db.obtener_uno("SELECT CONTRASEÑA_HASH, NIVEL_DE_ACCESO FROM USUARIOS WHERE USUARIO=?", (usuario,))
    except sqlite3.Error as e:
        print(f"\n❌ Error de Base de Datos al intentar iniciar sesión: {e}")
        # Si la consulta falla, el programa termina aquí si no hay más código de menú
        # o devuelve False para no intentar continuar con la lógica de login.
        return False
    except AttributeError as e:
        print(f"\n❌ Error: La conexión a la base de datos no está activa o el cursor no está inicializado. Detalle: {e}")
        return False
    except Exception as e:
        # Esto captura otros errores, como que el módulo 'db' no se pudo inicializar
        print(f"\n❌ Error inesperado al intentar obtener usuario: {e}")
        return False

    if usuario_en_db:
        contraseña_hash = usuario_en_db["CONTRASEÑA_HASH"]
        nivel_de_acceso = usuario_en_db["NIVEL_DE_ACCESO"]

        if contraseña_hash and bcrypt.checkpw(contraseña.encode('utf-8'), contraseña_hash):
            sesion.iniciar(usuario, nivel_de_acceso)
            print(f"\n✔ Inicio de sesión exitoso. Bienvenido, {sesion.usuario}.")
            return True

    print("\n❌ Usuario o contraseña incorrectos.")
    return False

def login_interactivo():
    #Solicita credenciales al usuario e invoca login().
    usuario = input("👤 Ingresá el nombre de usuario ó (0) para cancelar: ").strip()
    if usuario == "0":
        return False
    contraseña = getpass("🔑 Ingresá la contraseña: ")
    return login(usuario, contraseña)

def logout():
    """Cierra la sesión del usuario actual."""
    sesion.cerrar()

def requiere_acceso(nivel_requerido):
    # Decorador que asegura que la función solo se ejecute si hay una sesión válida
    # con el nivel requerido y no expirada.
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ok, motivo = sesion.verificar_acceso(nivel_requerido)
            if not ok:
                # Acá se manejan todos los casos donde el acceso NO es OK
                # Si el usuario no tiene permisos
                if motivo == "permiso":
                    # Si el usuario NO es un observador, se le deniega el acceso sin ofrecer login
                    if sesion.nivel_acceso > 0:
                        print("\n❌ No tenés permisos suficientes para esta acción.")
                        return
                    print("\n⚠️  Esta tarea no puede ejecutarla un observador, tenés que iniciar sesión.")
                # Si la sesión está inactiva
                if motivo == "inactiva":
                    print("\n⚠️  Para esta tarea, tenés que iniciar sesión.")
                # Si la sesión está expirada
                if motivo == "expirada":
                    print("\n⚠️  ⏰Tu sesión expiró, volvé a iniciar sesión.")
                # Se solicita login
                if not login_interactivo():
                    print("\n❌ No se pudo iniciar sesión.")
                    return
                # volver a verificar después del login
                ok, motivo = sesion.verificar_acceso(nivel_requerido)
                if not ok:
                    print("\n❌ Este usuario no cuenta con los permisos requeridos para esta acción.")
                    return
            # si pasó todas las verificaciones → ejecutar la función real
            sesion.refrescar()
            return func(*args, **kwargs)
        return wrapper
    return decorador

@requiere_acceso(3)
def crear_usuario():
    while True:
        usuario = input("👤 Ingresa el nombre de usuario ó (0) para salir: ").strip()
        if usuario == "0":
            print("\n❌ Operación cancelada.")
            return
        else:
            break
    contraseña = getpass("🔑 Ingresa la contraseña: ")
    while True:
        nivel_de_acceso = int(pedir_entero("Nivel de acceso (0, 1, 2): ", minimo=0, maximo=2))
        if nivel_de_acceso in [0, 1, 2]:
            # Encriptar la contraseña
            contraseña_hash = bcrypt.hashpw(contraseña.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            try:
                db.ejecutar("INSERT INTO USUARIOS (USUARIO, CONTRASEÑA_HASH, NIVEL_DE_ACCESO) VALUES (?, ?, ?)", 
                            (usuario, contraseña_hash, nivel_de_acceso))
                print(f"\n✔ Usuario '{usuario}' de nivel de acceso {nivel_de_acceso} creado exitosamente.")
                break
            except sqlite3.IntegrityError:
                print(f"\n⚠️  Error: El usuario '{usuario}' ya existe.")
        else:
            print("\n⚠️  Nivel de acceso no válido. Debe ser 0, 1 o 2.")

@requiere_acceso(3)
def mostrar_usuarios():
    #Muestra la lista de usuarios para que el Superusuario los gestione.
    lista_usuarios = db.obtener_todos("SELECT USUARIO, NIVEL_DE_ACCESO FROM USUARIOS")

    print("\n--- Usuarios del sistema ---")
    for u in lista_usuarios:
        usuario = u["USUARIO"]
        nivel = u["NIVEL_DE_ACCESO"]
        print(f"  - Usuario: {usuario} | Nivel: {nivel}")
    print("----------------------------")
    input("\nPresiona enter para continuar...")

@requiere_acceso(3)
def editar_usuario():
    while True:
        usuario = input("👤 Ingresa el nombre de usuario a editar, (*) para buscar ó (0) para cancelar: ").strip()
        if usuario == "0":
            print("\n❌ Operación cancelada.")
            return
        elif usuario == "*":
            mostrar_usuarios()
            continue
        elif not usuario:
            print("\n⚠️  El nombre de usuario no puede estar vacío.")
            continue
        usuario_db = db.obtener_uno("SELECT USUARIO FROM USUARIOS WHERE USUARIO = ?", (usuario,))
        if usuario_db is None:
            print(f"\n⚠️  Error: El usuario '{usuario}' no existe.")
            continue # Vuelve a pedir el nombre de usuario
        leyenda = "¿Qué querés editar? (1) La contraseña, (2) el nivel de acceso, (3) el nombre ó (0) para cancelar: "
        while True:
            opcion_editar = opcion_menu(leyenda, cero=True, minimo=1, maximo=3)
            if opcion_editar == 0:
                print("\n❌ Operación cancelada.")
                return
            if opcion_editar == 1:
                contraseña = getpass("Ingresa la nueva contraseña: ")
                try:
                    contraseña_hash = bcrypt.hashpw(contraseña.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    db.ejecutar("UPDATE USUARIOS SET CONTRASEÑA_HASH=? WHERE USUARIO=?", (contraseña_hash, usuario))
                    print(f"\n✔ Contraseña de '{usuario}' modificada.")
                except Exception as e:
                    print(f"\n❌ Error al modificar la contraseña de '{usuario}': {e}")
                return
            elif opcion_editar == 2:
                nuevo_nivel = pedir_entero("Ingresa el nuevo nivel de acceso (0, 1, 2): ", minimo=0, maximo=2)
                try:
                    db.ejecutar("UPDATE USUARIOS SET NIVEL_DE_ACCESO=? WHERE USUARIO=?", (nuevo_nivel, usuario))
                    print(f"\n✔ Nivel de acceso de '{usuario}' modificado a {nuevo_nivel}.")
                except Exception as e:
                    print(f"\n❌ Error al modificar el nivel de acceso de '{usuario}': {e}")
                return
            elif opcion_editar == 3:
                while True:
                    nuevo_nombre = input("Ingresa el nuevo nombre de usuario: ").strip()
                    if not nuevo_nombre:
                        print("\n⚠️  El nombre de usuario no puede estar vacío.")
                        continue
                    else:
                        try:
                            db.ejecutar("UPDATE USUARIOS SET USUARIO=? WHERE USUARIO=?", (nuevo_nombre, usuario))
                            print(f"\n✔ Nombre de usuario de '{usuario}' modificado a {nuevo_nombre}.")
                        except Exception as e:
                            print(f"\n❌ Error al modificar el nombre de usuario de '{usuario}': {e}")
                        break
                return

@requiere_acceso(3)
def eliminar_usuario():
    while True:
        usuario = input("👤 Ingresa el nombre de usuario a eliminar, (*) para buscar ó (0) para cancelar: ").strip()
        if usuario == "0":
            print("\n❌ Eliminación cancelada.")
            return
        elif usuario == "*":
            mostrar_usuarios()
            continue
        usuario_db = db.obtener_uno("SELECT USUARIO FROM USUARIOS WHERE USUARIO = ?", (usuario,))
        if usuario_db is None:
            print(f"\n❌ Error: El usuario '{usuario}' no existe.")
            continue # Vuelve a pedir el nombre de usuario
        confirmacion = pedir_confirmacion(f"\n⚠️¿Estás seguro de que querés eliminar a '{usuario}'? (si/no): ")
        if confirmacion == "si":
            # Elimina un usuario de la base de datos.
            try:
                db.ejecutar("DELETE FROM USUARIOS WHERE USUARIO=?", (usuario,))
                print(f"\n✔ Usuario '{usuario}' eliminado.")
            except Exception as e:
                print(f"\n❌ Error al eliminar el usuario '{usuario}': {e}")
        else:
            print("\n❌ Operación cancelada.")
        return