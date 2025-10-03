#TODO: Análisis de archivos y errores .br@gmail

#Que permita cancelar al pedir la fecha y demás.

#Aumentar el tamaño de la fuente desde propiedades de la consola

#Por qué algunos iconos necesitan doble espacio, porque sino se pegan demaciado al texto y cómo solucionarlo?

#Muestreo de coretsías en generar_reportes, con opción diario, semanal, mensual, histórico. Requiere mínimo lvl 2.

#Estructurar Logs en JSON para facilitar su lectura y análisis
#Verificar el muestreo de registros para que no se muestren todos los registros de una vez
#Verificar el muestreo de Logs (principalmente aquel de consumos eliminados, ya que no tiene sentido que muestre todo)

#Normalización de nombres y apellidos guardando en DB en formato Title Case.

import bcrypt
import sqlite3
import traceback
from consumos import agregar_consumo, ver_consumos, eliminar_consumos, registrar_pago, consumo_cortesia
from db import db
from huespedes import nuevo_huesped, realizar_checkout, buscar_huesped, ver_registro, cambiar_estado, editar_huesped, eliminar_huesped, realizar_checkin
from inventario import abrir_inventario, ingresar_compra, editar_inventario
from productos import nuevo_producto, buscar_producto, listado_productos, editar_producto, eliminar_producto
from reportes import reporte_diario, reporte_abiertos, reporte_cerrados, reporte_pronto_checkin, reporte_inventario, reporte_ocupacion, ver_logs
from usuarios import crear_usuario, mostrar_usuarios, editar_usuario, eliminar_usuario, logout, requiere_acceso
from utiles import pedir_confirmacion, opcion_menu

### FUNCIONES ###

def usuarios_existe():
    try:
        db.ejecutar('''
            CREATE TABLE IF NOT EXISTS USUARIOS (
                ID INTEGER PRIMARY KEY,
                USUARIO TEXT NOT NULL UNIQUE,
                CONTRASEÑA_HASH TEXT NOT NULL,
                NIVEL_DE_ACCESO INTEGER NOT NULL
            )
        ''')
    except Exception as e:
        print(f"❌ Error al crear la tabla USUARIOS: {e}")

    num_usuarios = db.obtener_uno("SELECT COUNT(*) AS total FROM USUARIOS")["total"]

    if num_usuarios == 0:
        usuario = "Admin"
        contraseña = "administrador"
        contraseña_hash = bcrypt.hashpw(contraseña.encode('utf-8'), bcrypt.gensalt())
        try:
            with db.transaccion():
                db.ejecutar("INSERT INTO USUARIOS (USUARIO, CONTRASEÑA_HASH, NIVEL_DE_ACCESO) VALUES (?, ?, ?)", (usuario, contraseña_hash, 3))
        except sqlite3.IntegrityError:
            print("\n❌ Error: No se pudo crear un Superusuario.")

def productos_existe():
    try:
        db.ejecutar('''CREATE TABLE IF NOT EXISTS PRODUCTOS(
                    CODIGO INTEGER PRIMARY KEY,
                    NOMBRE TEXT NOT NULL,
                    PRECIO REAL NOT NULL CHECK (PRECIO >= 0),
                    STOCK INTEGER NOT NULL CHECK (STOCK >= 0 OR STOCK = -1),
                    ALERTA INTEGER NOT NULL DEFAULT 5,
                    PINMEDIATO INTEGER NOT NULL DEFAULT 0 CHECK (PINMEDIATO IN (0,1))),
                    GRUPO TEXT DEFAULT NULL)''')
    except Exception as e:
        print(f"❌ Error al crear la tabla PRODUCTOS: {e}")

def huespedes_existe():
    try:
        db.ejecutar('''CREATE TABLE IF NOT EXISTS HUESPEDES(NUMERO INTEGER PRIMARY KEY AUTOINCREMENT,
                    APELLIDO TEXT NOT NULL, NOMBRE TEXT NOT NULL, TELEFONO INTEGER, EMAIL TEXT, APP TEXT,
                    ESTADO TEXT NOT NULL CHECK(ESTADO IN ('ABIERTO','CERRADO','PROGRAMADO')),
                    CHECKIN TEXT, CHECKOUT TEXT, DOCUMENTO TEXT, HABITACION INTEGER NOT NULL,
                CONTINGENTE INTEGER, REGISTRO TEXT)''')
    except Exception as e:
        print(f"❌ Error al crear la tabla HUESPEDES: {e}")

def consumos_existe():
    try:
        db.ejecutar('''CREATE TABLE IF NOT EXISTS CONSUMOS(
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    HUESPED INTEGER NOT NULL, PRODUCTO INTEGER NOT NULL,
                    CANTIDAD INTEGER NOT NULL CHECK (CANTIDAD > 0),
                    FECHA TEXT NOT NULL, PAGADO INTEGER NOT NULL DEFAULT 0 CHECK (PAGADO IN (0,1)),
                    FOREIGN KEY (HUESPED) REFERENCES HUESPEDES(NUMERO),
                    FOREIGN KEY (PRODUCTO) REFERENCES PRODUCTOS(CODIGO)
                    ON UPDATE CASCADE ON DELETE RESTRICT)''')
    except Exception as e:
        print(f"❌ Error al crear la tabla CONSUMOS: {e}")

def cortesias_existe():
    try:
        db.ejecutar('''CREATE TABLE IF NOT EXISTS CORTESIAS(
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    PRODUCTO INTEGER NOT NULL,
                    CANTIDAD INTEGER NOT NULL CHECK (CANTIDAD > 0),
                    FECHA TEXT NOT NULL, AUTORIZA TEXT NOT NULL,
                    FOREIGN KEY (PRODUCTO) REFERENCES PRODUCTOS(CODIGO)
                    ON UPDATE CASCADE ON DELETE RESTRICT)''')
    except Exception as e:
        print(f"❌ Error al crear la tabla CORTESIAS: {e}")

def inicio():
    leyenda = "\n¿Qué querés hacer?:\n1.🧘 Gestion de huéspedes\n2.📋 Gestion de consumos\n3.🛍️  Gestion de productos\n4.📦 Gestion de inventario\n5.📈 Gestion de reportes\n6.👤 Gestion de usuarios\n0.❌ Cerrar\n"
    while True:
        respuesta = opcion_menu(leyenda, cero=True, minimo=1, maximo=6)
        if respuesta == 0:
            respuesta_cierre = pedir_confirmacion("¿Está seguro de que querés cerrar el programa? (si/no): ")
            if respuesta_cierre != "si":
                print("\n⮐ Volviendo al menú principal...")
                continue
            else:
                break
        if respuesta == 1:
            gestionar_huespedes()
        elif respuesta == 2:
            gestionar_consumos()
        elif respuesta == 3:
            gestionar_productos()
        elif respuesta == 4:
            gestionar_inventario()
        elif respuesta == 5:
            gestionar_reportes()
        elif respuesta == 6:
            gestionar_usuarios()

def gestionar_huespedes():
    leyenda = "\nGestión de huéspedes:\n1.➕ Registrar nuevo huesped\n2.✅ Realizar checkin\n3.🚪 Realizar checkout\n4.🔍 Buscar un huesped\n5.✏️  Editar huesped\n6. ⭾ Cambiar el estado de un huesped\n7.🗑️  Eliminar un huesped\n8.㏒ Ver registro\n0. ⮐ Volver al inicio\n"
    while True:
        respuesta = opcion_menu(leyenda, cero=True, minimo=1, maximo=8)
        if respuesta == 1:
            nuevo_huesped()
        elif respuesta == 2:
            realizar_checkin()
        elif respuesta == 3:
            realizar_checkout()
        elif respuesta == 4:
            buscar_huesped()
        elif respuesta == 5:
            editar_huesped()
        elif respuesta == 6:
            cambiar_estado()
        elif respuesta == 7:
            eliminar_huesped()
        elif respuesta == 8:
            ver_registro()
        elif respuesta == 0:
            return

def gestionar_consumos():
    leyenda = "\nGestión de consumos\n1.➕ Agregar consumo\n2.🔍 Ver consumos\n3.🗑️  Eliminar consumos\n4.💸 Registrar pago\n5.🆓 Consumo de cortesía\n0. ⮐ Volver al inicio\n"
    while True:
        respuesta = opcion_menu(leyenda, cero=True, minimo=1, maximo=5)
        if respuesta == 1:
            agregar_consumo()
        elif respuesta == 2:
            ver_consumos()
        elif respuesta == 3:
            eliminar_consumos()
        elif respuesta == 4:
            registrar_pago()
        elif respuesta == 5:
            consumo_cortesia()
        elif respuesta == 0:
            return

def gestionar_productos():
    leyenda = "\nGestión de productos\n1.➕ Agregar producto\n2.🔍 Buscar productos\n3.📋 Listado de productos\n4.✏️  Editar producto\n5.🗑️  Eliminar producto\n0. ⮐ Volver al inicio\n"
    while True:
        respuesta = opcion_menu(leyenda, cero=True, minimo=1, maximo=5)
        if respuesta == 1:
            nuevo_producto()
        elif respuesta == 2:
            buscar_producto()
        elif respuesta == 3:
            listado_productos()
        elif respuesta == 4:
            editar_producto()
        elif respuesta == 5:
            eliminar_producto()
        elif respuesta == 0:
            return

def gestionar_inventario():
    leyenda = "\nGestión de inventario:\n1.📦 Abrir inventario\n2.➕ Ingresar compra\n3.✏️  Editar inventario\n0. ⮐ Volver al inicio\n"
    while True:
        respuesta = opcion_menu(leyenda, cero=True, minimo=1, maximo=3)
        if respuesta == 1:
            abrir_inventario()
        elif respuesta == 2:
            ingresar_compra()
        elif respuesta == 3:
            editar_inventario()
        elif respuesta == 0:
            return

def gestionar_reportes():
    leyenda = "\nGestión de reportes\n1.📋 Generar reporte de consumos diarios\n2.🧘 Generar reporte de pasajeros abiertos\n3.👋 Generar reporte de pasajeros cerrados\n4.📆 Generar reporte de pronto checkin\n5.📦 Generar reporte de inventario\n6.📅 Generar reporte de ocupación\n7.㏒ Ver logs\n0. ⮐ Volver al inicio\n"
    while True:
        respuesta = opcion_menu(leyenda, cero=True, minimo=1, maximo=7)
        if respuesta == 1:
            reporte_diario()
        elif respuesta == 2:
            reporte_abiertos()
        elif respuesta == 3:
            reporte_cerrados()
        elif respuesta == 4:
            reporte_pronto_checkin()
        elif respuesta == 5:
            reporte_inventario()
        elif respuesta == 6:
            reporte_ocupacion()
        elif respuesta == 7:
            ver_logs()
        elif respuesta == 0:
            return

@requiere_acceso(3)
def gestionar_usuarios():
    print("\n--👤Menú de Gestión de Usuarios--")
    leyenda = "1.➕ Crear nuevo usuario\n2.✏️  Editar usuario\n3.🗑️  Eliminar usuario\n4.👥 Mostrar usuarios\n5.␎  Cerrar sesión\n0. ⮐ Volver al menú principal\n"
    while True:
        respuesta = opcion_menu(leyenda, cero=True, minimo=1, maximo=5)
        if respuesta == 1:
            crear_usuario()
        elif respuesta == 2:
            editar_usuario()
        elif respuesta == 3:
            eliminar_usuario()
        elif respuesta == 4:
            mostrar_usuarios()
        elif respuesta == 5:
            logout()
        elif respuesta == 0:
            return

### PROGRAMA ###

try:
    print("Bienvenido al sistema de gestión de la posada Onda de mar 2.1 (Beta)")
    usuarios_existe()
    productos_existe()
    huespedes_existe()
    consumos_existe()
    cortesias_existe()
    inicio()
except Exception:
    with open("error.log", "w") as f:
        f.write(traceback.format_exc())
finally:
    print("\nCerrando el programa...")
    db.cerrar()
    print("Conexión a la base de datos cerrada.")
    print("Adios!!!")