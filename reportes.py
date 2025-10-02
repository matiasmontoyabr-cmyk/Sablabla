import os
import usuarios
from datetime import datetime, date, timedelta
from db import db
from utiles import HABITACIONES,pedir_confirmacion, imprimir_huespedes, opcion_menu

@usuarios.requiere_acceso(1)
def reporte_diario():
    hoy = date.today().isoformat()

    query = """SELECT H.HABITACION, H.NOMBRE AS HUESPED_NOMBRE, H.APELLIDO, C.FECHA,
    P.NOMBRE AS PRODUCTO, C.CANTIDAD FROM CONSUMOS C
    JOIN HUESPEDES H ON C.HUESPED = H.NUMERO
    JOIN PRODUCTOS P ON C.PRODUCTO = P.CODIGO
    WHERE C.FECHA LIKE ?
    ORDER BY H.HABITACION, C.FECHA
    """

    consumos = db.obtener_todos(query, (f"{hoy}%",)) 

    if not consumos:
        print(f"\n❌ No se registraron consumos en la fecha de hoy ({date.today().strftime('%d-%m-%Y')}).")
        return

    print(f"\nConsumos registrados hoy ({date.today().strftime('%d-%m-%Y')}):")

    habitacion_actual = None
    for consumo in consumos:
        habitacion = consumo["HABITACION"]
        nombre = consumo["HUESPED_NOMBRE"]
        apellido = consumo["APELLIDO"]
        fecha = consumo["FECHA"]
        producto = consumo["PRODUCTO"]
        cantidad = consumo["CANTIDAD"]
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
        print("\nHuéspedes abiertos:\n")
        imprimir_huespedes(huespedes)
        return
    else:
        print("\n❌ No se hallaron huéspedes abiertos")
        return

@usuarios.requiere_acceso(1)
def reporte_cerrados():
    while True:
        fecha_str = input("\nIngresá una fecha para generar el reporte, o deje vacío para el día de la fecha: ")
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
        print("\nHuéspedes con check-in programado proximamente:")
        imprimir_huespedes(huespedes)
        return
    else:
        print("\n❌ No hay huéspedes con check-in programado para hoy ni para mañana.")
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
    col_w = 3  # ancho fijo de cada columna
     
    ANCHO_ETIQUETA = 0 # Hab # (Tipo de Habitación) |
    for hab in range(1, 8):
        tipo = HABITACIONES[hab]["tipo"]
        # Calculamos la longitud de la base (Ej: "Hab 7 (Master Suite)")
        label_base = f"Hab {hab} ({tipo})"
        if len(label_base) > ANCHO_ETIQUETA:
            ANCHO_ETIQUETA = len(label_base)

    # Traer huéspedes abiertos y programados
    huespedes = db.obtener_todos("""
        SELECT NUMERO, NOMBRE, APELLIDO, HABITACION, CHECKIN, CHECKOUT, ESTADO
        FROM HUESPEDES
        WHERE ESTADO IN ('ABIERTO', 'PROGRAMADO')
    """)

    # Inicializar mapa de ocupación (habitaciones 1..7)
    ocupacion = {hab: [" . " for _ in range(dias)] for hab in range(1, 8)}

    # Proceso de marcaje: Se delega toda la complejidad a la función auxiliar
    for h in huespedes:
        # Aquí se llama a la función con la complejidad ciclomática (del bucle huésped)
        _marcar_reserva_en_mapa(ocupacion, h, hoy, dias)
        # Nota: La validación de errores de fecha (try/except) ahora está en la auxiliar, 
        # simplificando este bucle.

    # -------------------------------------------------------------
    # IMPRESIÓN Y ALINEACIÓN
    # -------------------------------------------------------------

    # Encabezado de días (01<espacio>)
    header_days = "".join(f"{(hoy + timedelta(days=i)).day:02}".ljust(col_w) for i in range(dias))
    print("\n📊 Informe de ocupación de habitaciones (20 días):\n")
    
    # La alineación del encabezado necesita la longitud de la base (max_label_length) 
    # más 2 espacios (el '|' y el espacio de separación).
    # Usaremos max_label_length + 2.
    print(" " * (ANCHO_ETIQUETA + 2) + header_days)

    # Filas
    for hab in range(1, 8):
        tipo = HABITACIONES[hab]["tipo"]  # Obtener tipo de habitación
        label_base = f"Hab {hab} ({tipo})"
        aligned_base = label_base.ljust(ANCHO_ETIQUETA)
        fila_celdas = "".join(s for s in ocupacion[hab])
        print(f"{aligned_base}| {fila_celdas}")

    print("\nLeyenda: CI=Checkin, CO=Checkout, O/I=Checkou/in solapado, X=Ocupado, P=Programado, .. = Libre")
    input("\nPresione Enter para continuar...")

def _marcar_reserva_en_mapa(ocupacion, h, hoy, dias):
    """
    Aplica la lógica de una única reserva (h) al mapa de ocupación.
    Retorna True si el marcaje fue exitoso, False si hubo error de formato de fecha.
    """
    hab = h["HABITACION"]
    if not hab or hab == 0:
        return True # Se ignora, no es un error

    try:
        f_in = date.fromisoformat(h["CHECKIN"])
        f_out = date.fromisoformat(h["CHECKOUT"])
    except ValueError:
        return False # Error en el formato de fecha

    estado = h["ESTADO"]
    
    # 1. Marcar días de estadía (X o P)
    for i in range(dias):
        d = hoy + timedelta(days=i)
        
        if f_in <= d < f_out: # Checkeamos todos los días de la reserva
            if estado == "ABIERTO":
                ocupacion[hab][i] = " X "
            # 'PROGRAMADO' solo marca si la celda está libre (" . ")
            elif ocupacion[hab][i] == " . ": 
                ocupacion[hab][i] = " P "

    # 2. Marcar Checkout (CO) o Solapamiento (O/I)
    idx_out = (f_out - hoy).days
    if 0 <= idx_out < dias: 
        if ocupacion[hab][idx_out] == "CI ":
            ocupacion[hab][idx_out] = "O/I" # Sobrescribe CI
        elif ocupacion[hab][idx_out] == " . ": 
            ocupacion[hab][idx_out] = "CO " 

    # 3. Marcar Check-In (CI) o Solapamiento (O/I)
    idx_in = (f_in - hoy).days
    if 0 <= idx_in < dias:
        if ocupacion[hab][idx_in] == "CO ":
            ocupacion[hab][idx_in] = "O/I" # Sobrescribe CO
        else:
            ocupacion[hab][idx_in] = "CI " # Sobrescribe P/X/o libre

    return True

@usuarios.requiere_acceso(2)
def ver_logs():
    leyenda = "\n¿Qué log querés ver?\n1. Consumos de cortesía\n2. Consumos eliminados\n3. Huéspedes cerrados\n4. Huéspedes eliminados\n5. Productos editados\n6. Check-ins realizados\nó 0. Cancelar\n"
    
    logs = {
        1: "consumos_cortesia.log", 
        2: "consumos_eliminados.log", 
        3: "huespedes_cerrados.log", 
        4: "huespedes_eliminados.log", 
        5: "productos_editados.log",
        6: "checkins.log" 
    }
    while True:
        opcion = opcion_menu(leyenda, cero=True, minimo=1, maximo=6)
        if opcion == 0:
            return
        elif opcion in logs:
            path = os.path.join("logs", logs[opcion])
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    print("\n" + f.read())
                input("\nPresione Enter para continuar...")
            else:
                print("\n❌ No se encontró el archivo de log.")