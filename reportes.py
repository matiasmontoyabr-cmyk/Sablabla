import os
import usuarios
from datetime import datetime, date, timedelta
from db import db
from utiles import HABITACIONES,pedir_confirmacion, imprimir_huespedes

@usuarios.requiere_acceso(1)
def reporte_diario():
    hoy = date.today().isoformat()

    query = """SELECT H.HABITACION, H.NOMBRE, H.APELLIDO, C.FECHA, P.NOMBRE, C.CANTIDAD FROM CONSUMOS C JOIN HUESPEDES H ON C.HUESPED = H.NUMERO JOIN PRODUCTOS P ON C.PRODUCTO = P.CODIGO WHERE C.FECHA LIKE ? ORDER BY H.HABITACION, C.FECHA"""

    consumos = db.obtener_todos(query, (f"{hoy}%",)) 

    if not consumos:
        print(f"\n❌ No se registraron consumos en la fecha de hoy ({date.today().strftime('%d-%m-%Y')}).")
        return

    print(f"\nConsumos registrados hoy ({date.today().strftime('%d-%m-%Y')}):")

    habitacion_actual = None
    for habitacion, nombre, apellido, fecha, producto, cantidad in consumos:
        if habitacion != habitacion_actual:
            habitacion_actual = habitacion
            print(f"\nHabitación {habitacion} - Huésped: {nombre} {apellido}")

        hora = datetime.strptime(fecha, "%Y-%m-%d %H:%M:%S").strftime("%H:%M") 
        print(f"  - {hora} {producto} (x{cantidad})")

    print("-" * 50)
    input("\nPresione Enter para continuar...")

@usuarios.requiere_acceso(1)
def reporte_abiertos():
    fecha = date.today()
    fecha_iso = fecha.isoformat()
    query_vencidos = "SELECT * FROM HUESPEDES WHERE ESTADO = 'ABIERTO' AND CHECKOUT <= ? ORDER BY CAST(HABITACION AS INTEGER)"
    vencidos = db.obtener_todos(query_vencidos, (fecha_iso,))
    if vencidos:
        respuesta = pedir_confirmacion("\n⚠️  ¡¡¡Atención!!! ⚠️ \nSe encontraron huéspedes abiertos con checkout vencido.\n¿Desea verlos? (si/no): ")
        if respuesta == "si":
            print("\n⚠️  Huéspedes con checkout vencido:\n")
            imprimir_huespedes(vencidos)
            input("\nPresione Enter para continuar...")
            return
    query = "SELECT * FROM HUESPEDES WHERE ESTADO = ? ORDER BY CAST(HABITACION AS INTEGER)"
    huespedes = db.obtener_todos(query, ("ABIERTO",))
    if huespedes:
        print(f"\nHuéspedes abiertos:\n")
        imprimir_huespedes(huespedes)
        input("\nPresione Enter para continuar...")
        return
    else:
        print("\n❌ No se hallaron huéspedes abiertos")
        return

@usuarios.requiere_acceso(1)
def reporte_cerrados():
    while True:
        fecha_str = input("\nIngrese una fecha para generar el reporte, o deje vacío para el día de la fecha: ")
        if fecha_str:
            try:
                fecha = datetime.strptime(fecha_str, "%d-%m-%Y").date()
                break
            except ValueError:
                print("❌ Fecha inválida. Use el formato DD-MM-YYYY.")
                continue
        else:
            fecha = date.today()
            break
    fecha_iso = fecha.isoformat()
    query = "SELECT * FROM HUESPEDES WHERE ESTADO = 'CERRADO' AND CHECKOUT = ? ORDER BY CAST(HABITACION AS INTEGER)"
    cerrados = db.obtener_todos(query, (fecha_iso,))

    if cerrados:
        print(f"\nHuéspedes cerrados el {fecha.strftime('%d-%m-%Y')}:\n")
        imprimir_huespedes(cerrados)
        input("\nPresione Enter para continuar...")
        return
    else:
        query_vencidos = "SELECT * FROM HUESPEDES WHERE ESTADO = 'ABIERTO' AND CHECKOUT <= ? ORDER BY CAST(HABITACION AS INTEGER)"
        vencidos = db.obtener_todos(query_vencidos, (fecha_iso,))

        if vencidos:
            respuesta = pedir_confirmacion("\n⚠️ ¡¡¡Atención!!! ⚠️\nNo se encontraron huéspedes cerrados pero HAY HUÉSPEDES CON CHECKOUT VENCIDO\n¿Desea verlos? (si/no): ")
            if respuesta == "si":
                print("\n⚠️  Huéspedes con checkout vencido:\n")
                imprimir_huespedes(vencidos)
                input("\nPresione Enter para continuar...")
                return
        else:
            print("\n❌ No se hallaron huéspedes cerrados el día de hoy")

@usuarios.requiere_acceso(1)
def reporte_pronto_checkin():
    hoy = date.today()
    manana = hoy + timedelta(days=1)
    hoy_iso = hoy.isoformat()
    manana_iso = manana.isoformat()

    query = "SELECT * FROM HUESPEDES WHERE ESTADO = 'PROGRAMADO' AND CHECKIN IN (?, ?)"
    huespedes = db.obtener_todos(query, (hoy_iso, manana_iso))

    if huespedes:
        print(f"\nHuéspedes con check-in programado proximamente:")
        imprimir_huespedes(huespedes)
        input("\nPresione Enter para continuar...")
        return
    else:
        print(f"\n❌ No hay huéspedes con check-in programado para hoy ni para mañana.")
        return

@usuarios.requiere_acceso(1)
def reporte_inventario():
    """
    Muestra un reporte de productos con stock bajo (<= ALERTA),
    ignorando los de stock infinito (-1).
    """
    bajo_stock = db.obtener_todos(
        "SELECT CODIGO, NOMBRE, STOCK, ALERTA FROM PRODUCTOS WHERE STOCK != -1 AND STOCK <= ALERTA ORDER BY STOCK ASC"
    )

    if not bajo_stock:
        print("\n✔ Todos los productos tienen stock suficiente.")
        return

    print("\n⚠️️  Productos con bajo stock:")
    print(f"{'CÓDIGO':<7} {'NOMBRE':<30} {'STOCK':<10} {'ALERTA':<10}")
    print("-" * 60)
    for codigo, nombre, stock, alerta in bajo_stock:
        print(f"{codigo:<7} {nombre:<30} {stock:<10} {alerta:<10}")
    input("\nPresione Enter para continuar...")

@usuarios.requiere_acceso(1)
def reporte_ocupacion():
    hoy = date.today()
    dias = 20  # rango de días a mostrar
    col_w = 2  # ancho fijo de cada columna

    # Traer huéspedes abiertos y programados
    huespedes = db.obtener_todos("""
        SELECT NUMERO, NOMBRE, APELLIDO, HABITACION, CHECKIN, CHECKOUT, ESTADO
        FROM HUESPEDES
        WHERE ESTADO IN ('ABIERTO', 'PROGRAMADO')
    """)

    # Inicializar mapa de ocupación (habitaciones 1..7)
    ocupacion = {hab: ["." for _ in range(dias)] for hab in range(1, 8)}

    for h in huespedes:
        hab = h["HABITACION"]
        checkin = h["CHECKIN"]
        checkout = h["CHECKOUT"]
        estado = h["ESTADO"]
        if not hab or hab == 0:
            continue
        f_in = date.fromisoformat(checkin)
        f_out = date.fromisoformat(checkout)

        for i in range(dias):
            d = hoy + timedelta(days=i)
            if f_in <= d <= f_out:
                if d == f_in:
                    ocupacion[hab][i] = "CI"
                elif d == f_out:
                    ocupacion[hab][i] = "CO"
                else:
                    if estado == "ABIERTO":
                        ocupacion[hab][i] = "X"
                    else:  # PROGRAMADO
                        if ocupacion[hab][i] == ".":
                            ocupacion[hab][i] = "P"

    # Encabezado (2 caracteres por día)
    header_days = "".join(f"{(hoy + timedelta(days=i)).day:02}".ljust(col_w) for i in range(dias))
    print("\n📊 Informe de ocupación de habitaciones (20 días):\n")
    print(" " * 8 + header_days)

    # Filas
    for hab in range(1, 8):
        tipo = HABITACIONES[hab]["tipo"]  # Obtener tipo de habitación
        fila_celdas = "".join(s.ljust(col_w) for s in ocupacion[hab])
        print(f"Hab {hab} ({tipo:<10})| {fila_celdas}")

    print("\nLeyenda: CI = Check-in, CO = Check-out, X = Ocupado, P = Programado, . = Libre")
    input("\nPresione Enter para continuar...")

@usuarios.requiere_acceso(2)
def ver_logs():
    while True:
        logs = {"1": "huespedes_eliminados.log", "2": "huespedes_cerrados.log", "3": "consumos_eliminados.log"}
        print("\n¿Qué log quiere ver?\n1. Huéspedes eliminados\n2. Huéspedes cerrados\n3. Consumos eliminados\n0. Cancelar")
        opcion = input("\nSeleccione una opción: ").strip()
        if opcion == "0":
            return
        elif opcion not in logs:
            print("❌ Opción inválida.")
        elif opcion in logs:
            path = os.path.join("logs", logs[opcion])
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    print("\n" + f.read())
                input("\nPresione Enter para continuar...")
            else:
                print("\n❌ No se encontró el archivo de log.")