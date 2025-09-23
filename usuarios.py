import bcrypt
import sqlite3
import time
from db import db
from functools import wraps
from getpass import getpass
from utiles import pedir_entero, pedir_confirmacion

USUARIO_ACTUAL = "Observador"
NIVEL_ACCESO_ACTUAL = 0
SESION_ACTIVA = False 
ULTIMA_AUTENTICACION = 0
DURACION_SESION = {
    0: 0,        # Observador (no requiere sesión)
    1: 300,      # Operario -> 5 minutos
    2: 300,      # Gerente -> 5 minutos
    3: 300       # Administrador -> 5 minutos
}

def login(usuario, contraseña):
    """Verifica las credenciales y establece la sesión."""
    global USUARIO_ACTUAL, NIVEL_ACCESO_ACTUAL, SESION_ACTIVA, ULTIMA_AUTENTICACION

    usuario_en_db = db.obtener_uno("SELECT CONTRASEÑA_HASH, NIVEL_DE_ACCESO FROM USUARIOS WHERE USUARIO=?", (usuario,))

    if usuario_en_db:
        contraseña_hash = usuario_en_db["CONTRASEÑA_HASH"]
        nivel_de_acceso = usuario_en_db["NIVEL_DE_ACCESO"]

        if bcrypt.checkpw(contraseña.encode('utf-8'), contraseña_hash.encode('utf-8')):
            USUARIO_ACTUAL = usuario
            NIVEL_ACCESO_ACTUAL = nivel_de_acceso
            SESION_ACTIVA = True
            ULTIMA_AUTENTICACION = time.time()
            print(f"\n✔ Inicio de sesión exitoso. Bienvenido, {USUARIO_ACTUAL}.")
            return True

    print("\n❌ Usuario o contraseña incorrectos.")
    return False

def login_interactivo():
    """Solicita credenciales al usuario e invoca login()."""
    usuario = input("👤 Ingresa el nombre de usuario ó (0) para cancelar: ").strip()
    if usuario == "0":
        return False
    contraseña = getpass("🔑 Ingresa la contraseña: ")
    return login(usuario, contraseña)

def logout():
    """Cierra la sesión del usuario actual."""
    global USUARIO_ACTUAL, NIVEL_ACCESO_ACTUAL, SESION_ACTIVA, ULTIMA_AUTENTICACION
    USUARIO_ACTUAL = "Observador"
    NIVEL_ACCESO_ACTUAL = 0
    SESION_ACTIVA = False
    ULTIMA_AUTENTICACION = None
    print("\n👋 Sesión cerrada.")

def requiere_acceso(nivel_requerido):
    """
    Decorador que asegura que la función solo se ejecute si hay una sesión válida
    con el nivel requerido y no expirada.
    """
    def decorador(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ok, motivo = verificar_sesion_activa(nivel_requerido)
            if not ok:
                if motivo in ("expirada", "inactiva"):
                    if motivo == "inactiva":
                        print("\n⚠️  Para esta tarea, tenés que iniciar sesión.")
                    if motivo == "expirada":
                        print("\n⚠️  ⏰Tu sesión expiró, volvé a iniciar sesión.")

                    if not login_interactivo():
                        print("\n❌ No se pudo iniciar sesión.")
                        return
                    # volver a verificar después del login
                    ok, motivo = verificar_sesion_activa(nivel_requerido)
                    if not ok:
                        print("\n❌ No tenés permisos suficientes para esta acción.")
                        return
                elif motivo == "permiso":
                    print("\n❌ No tenés permisos suficientes para esta acción.")
                    return
            # si pasó todas las verificaciones → ejecutar la función real
            return func(*args, **kwargs)
        return wrapper
    return decorador

def verificar_sesion_activa(nivel_requerido):
    """ Verifica si el usuario tiene permiso y si la sesión temporal sigue activa.
    Si la sesión expiró, solicita la contraseña nuevamente.
    """

    # Verificar sesión activa
    if NIVEL_ACCESO_ACTUAL == 0 or ULTIMA_AUTENTICACION is None:
        return False, "inactiva"

    # Verificar nivel de acceso
    if NIVEL_ACCESO_ACTUAL >= nivel_requerido:
        # Verificar si la sesión temporal ha expirado
        duracion = DURACION_SESION.get(NIVEL_ACCESO_ACTUAL, 300)
        if duracion > 0 and time.time() - ULTIMA_AUTENTICACION > duracion:
            # Expirada → limpiar sesión
            logout()
            return False, "expirada"
        return True, None

    return False, "permiso"

def refrescar_sesion():
    global ULTIMA_AUTENTICACION
    if SESION_ACTIVA:
        ULTIMA_AUTENTICACION = time.time()

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
        nivel_de_acceso = int(input("Nivel de acceso (0, 1, 2): "))
        if nivel_de_acceso in [0, 1, 2]:
            # Encriptar la contraseña
            contraseña_hash = bcrypt.hashpw(contraseña.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            try:
                db.iniciar()
                db.ejecutar("INSERT INTO USUARIOS (USUARIO, CONTRASEÑA_HASH, NIVEL_DE_ACCESO) VALUES (?, ?, ?)", 
                            (usuario, contraseña_hash, nivel_de_acceso))
                db.confirmar()
                print(f"\n✔ Usuario '{usuario}' de nivel de acceso {nivel_de_acceso} creado exitosamente.")
                break
            except sqlite3.IntegrityError:
                db.revertir()
                print(f"\n⚠️  Error: El usuario '{usuario}' ya existe.")
        else:
            print("\n⚠️  Nivel de acceso no válido. Debe ser 0, 1 o 2.")

@requiere_acceso(3)
def mostrar_usuarios():
    """Muestra la lista de usuarios para que el Superusuario los gestione."""
    lista_usuarios = db.obtener_todos("SELECT USUARIO, NIVEL_DE_ACCESO FROM USUARIOS")

    print("\n--- Usuarios del sistema ---")
    for usuario, nivel in lista_usuarios:
        print(f"  - Usuario: {usuario} | Nivel: {nivel}")
    print("----------------------------")

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
        else:
            opcion_editar = input("¿Qué desea editar? La contraseña (1) o el nivel de acceso (2) ó el nombre (3): ").strip()
            if opcion_editar == "1":
                contraseña = getpass("Ingresa la nueva contraseña: ")
                try:
                    db.iniciar()
                    contraseña_hash = bcrypt.hashpw(contraseña.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    db.ejecutar("UPDATE USUARIOS SET CONTRASEÑA_HASH=? WHERE USUARIO=?", (contraseña_hash, usuario))
                    db.confirmar()
                    print(f"\n✔ Contraseña de '{usuario}' modificada.")
                except Exception as e:
                    db.revertir()
                    print(f"\n❌ Error al modificar la contraseña de '{usuario}': {e}")
                return
            elif opcion_editar == "2":
                nuevo_nivel = pedir_entero("Ingresa el nuevo nivel de acceso (0, 1, 2): ", minimo=0, maximo=2)
                try:
                    db.iniciar()
                    db.ejecutar("UPDATE USUARIOS SET NIVEL_DE_ACCESO=? WHERE USUARIO=?", (nuevo_nivel, usuario))
                    db.confirmar()
                    print(f"\n✔ Nivel de acceso de '{usuario}' modificado a {nuevo_nivel}.")
                except Exception as e:
                    db.revertir()
                    print(f"\n❌ Error al modificar el nivel de acceso de '{usuario}': {e}")
                return
            elif opcion_editar == "3":
                while True:
                    nuevo_nombre = input("Ingresa el nuevo nombre de usuario: ").strip()
                    if not nuevo_nombre:
                        print("\n⚠️  El nombre de usuario no puede estar vacío.")
                        continue
                    else:
                        try:
                            db.iniciar()
                            db.ejecutar("UPDATE USUARIOS SET USUARIO=? WHERE USUARIO=?", (nuevo_nombre, usuario))
                            db.confirmar()
                            print(f"\n✔ Nombre de usuario de '{usuario}' modificado a {nuevo_nombre}.")
                        except Exception as e:
                            db.revertir()
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
        else:
            confirmacion = pedir_confirmacion(f"\n⚠️¿Estás seguro de que quieres eliminar a '{usuario}'? (si/no): ")
            if confirmacion == "si":
                """Elimina un usuario de la base de datos."""
                try:
                    db.iniciar()
                    db.ejecutar("DELETE FROM USUARIOS WHERE USUARIO=?", (usuario,))
                    db.confirmar()
                    print(f"\n✔ Usuario '{usuario}' eliminado.")
                except Exception as e:
                    db.revertir()
                    print(f"\n❌ Error al eliminar el usuario '{usuario}': {e}")
            else:
                print("\n❌ Operación cancelada.")