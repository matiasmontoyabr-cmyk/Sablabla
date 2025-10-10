import re
import usuarios
from datetime import datetime
from db import db
from huespedes import buscar_huesped, _editar_huesped_db
from unidecode import unidecode
from utiles import registrar_log, imprimir_huesped, pedir_entero, pedir_confirmacion, imprimir_productos, formatear_fecha, marca_de_tiempo, opcion_menu, parse_fecha_a_datetime, pedir_precio


@usuarios.requiere_acceso(1)
def agregar_consumo():
    # Función principal para coordinar el proceso de agregar consumos a un huésped.
    leyenda = "\nIngresá el número de habitación para agregar un consumo, (*) para buscar ó (0) para cancelar: "
    huesped = _seleccionar_huesped(leyenda)
    if not huesped:
        print("\n❌ Operación cancelada.")
        return

    consumos_pendientes = _recolectar_consumos(huesped["NUMERO"])
    
    consumos_finales = _editar_consumos_agregados(consumos_pendientes)

    if consumos_finales:
        _guardar_consumos_en_db(consumos_finales, huesped)
    else:
        print("\n❌ No se registraron nuevos consumos.")

def _seleccionar_huesped(leyenda_hab):
    # Gestiona la selección de un huésped. Devuelve el diccionario del huésped
    # o None si se cancela la operación.
    while True:
        respuesta = opcion_menu(leyenda_hab, cero=True, asterisco=True, minimo=1, maximo=7)
        if respuesta == 0:
            return None
        if respuesta == "*":
            buscar_huesped()
            continue

        habitacion = respuesta
        huesped = db.obtener_uno("SELECT * FROM HUESPEDES WHERE HABITACION = ? AND ESTADO = 'ABIERTO'", (habitacion,))
        if huesped:
            nombre_display = ' '.join(word.capitalize() for word in str(huesped["NOMBRE"]).split())
            apellido_display = ' '.join(word.capitalize() for word in str(huesped["APELLIDO"]).split())
            print(f"Habitación {huesped['HABITACION']} - Huésped {nombre_display} {apellido_display}")
            return huesped
        else:
            print("\n❌ No se encontró un huésped ABIERTO en esa habitación.")

def _recolectar_consumos(huesped_numero):
    """
    Recolecta los productos consumidos por un huésped. Devuelve una lista de diccionarios de consumo.
    """
    consumos_agregados = []
    leyenda_cod = "\nIngresá el código del producto consumido, (*) para buscar ó (0) para finalizar: "
    while True:
        codigo = opcion_menu(leyenda_cod, cero=True, asterisco=True, minimo=1)
        if codigo == 0:
            break
        if codigo == "*":
            productos = db.obtener_todos("SELECT * FROM PRODUCTOS WHERE STOCK > 0 OR STOCK = -1")
            if not productos:
                print("\n❌ No hay productos en stock.")
            else:
                imprimir_productos(productos)
            continue

        producto = db.obtener_uno("SELECT * FROM PRODUCTOS WHERE CODIGO = ?", (codigo,))
        if not producto:
            print("\n❌ Producto no encontrado.")
            continue

        consumo = _procesar_un_producto(producto, huesped_numero)
        if consumo:
            consumos_agregados.append(consumo)
    
    return consumos_agregados

def _procesar_un_producto(producto, huesped_numero):
    # Maneja la lógica para agregar una cantidad específica de un producto.
    # Devuelve un diccionario de consumo o None si se cancela.

    nombre = producto["NOMBRE"]
    stock = producto["STOCK"]
    pinmediato = producto["PINMEDIATO"]
    print(f"\nProducto seleccionado: {nombre.capitalize()} (Stock: {'Infinito' if stock == -1 else stock})")

    while True:
        cantidad = pedir_entero("Ingresá la cantidad consumida ó (0) para cancelar: ", minimo=0)
        if cantidad == 0:
            print("\n❌ Producto cancelado.")
            return None
        
        if stock != -1 and cantidad > stock:
            print(f"\n❌ No hay suficiente stock. Disponibles: {stock}")
            continue

        pagado = 0
        if pinmediato == 1:
            if pedir_confirmacion(f"\n⚠️  '{nombre.title()}' debería ser pagado en el momento. ¿Querés registrarlo como pagado? (si/no): ") == "si":
                pagado = 1
                print("✔ Se registrará el consumo como pagado.")
            else:
                print("\n⚠️  El consumo se registrará como pendiente de pago.")

        print(f"\n✔ Se agregó a la lista: {cantidad} unidad(es) de '{nombre.capitalize()}'.")
        return {
            "huesped_id": huesped_numero,
            "codigo": producto["CODIGO"],
            "nombre": nombre,
            "cantidad": cantidad,
            "pagado": pagado,
            "stock_anterior": stock
        }

def _editar_consumos_agregados(consumos):
    # Permite al usuario eliminar consumos de la lista recién agregada.
    # Devuelve la lista modificada.

    if not consumos:
        return consumos

    print("\nConsumos recién agregados:")
    for i, consumo in enumerate(consumos):
        print(f"  {i + 1}. Producto: {consumo['nombre'].title():<20} (Cód: {consumo['codigo']:<10}), Cantidad: {consumo['cantidad']}")

    if pedir_confirmacion("\n¿Querés confirmar estos consumos? (si/no): ", defecto="si") != "no":
        return consumos
    
    a_eliminar_str = input("\nIngresá los items a eliminar (separados por comas o espacios), ó '0' para cancelar: ").strip()
    if a_eliminar_str == '0':
        return consumos
        
    indices_a_eliminar = set()
    partes = re.split(r'[,\s]+', a_eliminar_str)
    for parte in partes:
        try:
            indice = int(parte) - 1
            if 0 <= indice < len(consumos):
                indices_a_eliminar.add(indice)
            else:
                print(f"❌ El número {indice + 1} es inválido. Se ignorará.")
        except ValueError:
            print(f"❌ La entrada '{parte}' no es un número. Se ignorará.")

    if indices_a_eliminar:
        for indice in sorted(list(indices_a_eliminar), reverse=True):
            consumo_eliminado = consumos.pop(indice)
            print(f"\n✔ Consumo de '{consumo_eliminado['nombre']}' eliminado.")
    
    return consumos

def _guardar_consumos_en_db(consumos, huesped):
    # Guarda la lista final de consumos en la base de datos, actualizando stock y registro.

    numero_huesped = huesped["NUMERO"]

    with db.transaccion():
        for consumo in consumos:
            fecha = datetime.now().isoformat(sep=" ", timespec="seconds")
            
            # 1. Insertar el consumo
            db.ejecutar("INSERT INTO CONSUMOS (HUESPED, PRODUCTO, CANTIDAD, FECHA, PAGADO) VALUES (?, ?, ?, ?, ?)",
                        (consumo['huesped_id'], consumo['codigo'], consumo['cantidad'], fecha, consumo['pagado']))
            
            # 2. Actualizar stock del producto
            if consumo['stock_anterior'] != -1:
                grupo_info = db.obtener_uno("SELECT GRUPO FROM PRODUCTOS WHERE CODIGO = ?", (consumo['codigo'],))
                grupo = grupo_info["GRUPO"] if grupo_info else None

                if grupo:
                    # Buscar todos los productos en el mismo grupo
                    equivalentes = db.obtener_todos("SELECT CODIGO, STOCK FROM PRODUCTOS WHERE GRUPO = ?", (grupo,))
                    for eq in equivalentes:
                        if eq["STOCK"] != -1:  # no tocar stock infinito
                            nuevo_stock = eq["STOCK"] - consumo['cantidad']
                            db.ejecutar("UPDATE PRODUCTOS SET STOCK = ? WHERE CODIGO = ?", (nuevo_stock, eq["CODIGO"]))
                else:
                    # Producto sin grupo → descuenta solo a él
                    nuevo_stock = consumo['stock_anterior'] - consumo['cantidad']
                    db.ejecutar("UPDATE PRODUCTOS SET STOCK = ? WHERE CODIGO = ?", (nuevo_stock, consumo['codigo']))

            # 3. Abre el registro del huésped
            registro_anterior_data = db.obtener_uno("SELECT REGISTRO FROM HUESPEDES WHERE NUMERO = ?", (numero_huesped,))
            registro_anterior = str(registro_anterior_data["REGISTRO"] or "") if registro_anterior_data else ""
            
            # 4. Prepara el registro de la acción actual
            registro_consumo = f"Consumo agregado: {consumo['nombre']} (x{consumo['cantidad']}) - {fecha}"
            if consumo['pagado'] == 1:
                registro_consumo += " (PAGADO)"
            
            nuevo_registro = (registro_anterior + "\n---\n" + registro_consumo) if registro_anterior.strip() else registro_consumo
            _editar_huesped_db(numero_huesped, {"REGISTRO": nuevo_registro})

    print(f"✔ Consumos agregados para {huesped['NOMBRE'].capitalize()} {huesped['APELLIDO'].capitalize()}, de la habitación {huesped['HABITACION']}:")
    for i, consumo in enumerate(consumos):
        print(f"  {i + 1}. Producto: {consumo['nombre'].capitalize()} (Cód: {consumo['codigo']}), Cantidad: {consumo['cantidad']}")

@usuarios.requiere_acceso(1)
def ver_consumos():
    """
    Muestra los consumos de una habitación.
    Por defecto solo muestra los NO PAGOS, y si hay pagos, ofrece mostrarlos.
    """

    # --- PROCESO PRINCIPAL ---
    leyenda = "\nIngresá el número de habitación para ver sus consumos, (*) para buscar ó (0) para cancelar: "
    while True:
        habitacion = opcion_menu(leyenda, cero=True, asterisco=True, minimo=1, maximo=7)
        if habitacion == 0:
            return
        if habitacion == "*":
            buscar_huesped()
            continue

        huesped, estado = _obtener_huesped(habitacion)
        if not huesped:
            print("❌ Habitación libre o sin reservas activas ni programadas.")
            continue
        if estado == "PROGRAMADO":
            print(f"❌ La habitación {habitacion} está reservada para {huesped['NOMBRE'].title()} {huesped['APELLIDO'].title()}, pero todavía no hizo checkin.")
            continue

        # Mostrar solo no pagos
        consumos_no_pagos = _obtener_consumos(huesped, incluir_pagos=False)
        consumos_todos = _obtener_consumos(huesped, incluir_pagos=True)
        consumos_pagos = [c for c in consumos_todos if c["PAGADO"] == 1]

        if not consumos_no_pagos and not consumos_pagos:
            print("\nEsta habitación no tiene consumos registrados.")
            return

        if not consumos_no_pagos:
            if pedir_confirmacion("Todos los consumos de esta estadía fueron pagados. ¿Querés verlos igualmente? (si/no): ") == "si":
                agrupados = _preparar_consumos(consumos_pagos)
                print(f"\nHistorial de consumos PAGADOS de la habitación {huesped['HABITACION']}, huésped {huesped['NOMBRE'].title()} {huesped['APELLIDO'].title()}:\n")
                _imprimir_consumos(agrupados, incluir_columna_pagado=True)
            return

        # Mostrar NO PAGOS
        print(f"\nHistorial de consumos NO PAGOS de la habitación {huesped['HABITACION']}, huésped {huesped['NOMBRE'].title()} {huesped['APELLIDO'].title()}:\n")
        agrupados = _preparar_consumos(consumos_no_pagos)
        total_impagos = _imprimir_consumos(huesped, agrupados)

        if total_impagos > 0:
            _imprimir_total(huesped, total_impagos)
        else:
            print("\n" + "=" * 84)
            print(f"{'TOTAL PENDIENTE: R$ 0.00. No hay cargos impagos para calcular propina/descuentos.':<84}")
            print("=" * 84)

        # Si hay pagos, ofrecer mostrarlos
        if consumos_pagos and pedir_confirmacion("\n💰 Hay consumos ya pagos. ¿Querés verlos también? (si/no): ") == "si":
                agrupados_pagos = _preparar_consumos(consumos_pagos)
                print(f"\nHistorial de consumos PAGADOS de la habitación {huesped['HABITACION']}, huésped {huesped['NOMBRE'].title()} {huesped['APELLIDO'].title()}:\n")
                _imprimir_consumos(agrupados_pagos, incluir_columna_pagado=True)
        return

def _obtener_huesped(habitacion):
        # Busca huésped ABIERTO o PROGRAMADO
        huesped = db.obtener_uno(
            "SELECT * FROM HUESPEDES WHERE HABITACION = ? AND ESTADO = 'ABIERTO'", 
            (habitacion,)
        )
        if huesped:
            return huesped, "ABIERTO"
        huesped = db.obtener_uno(
            "SELECT * FROM HUESPEDES WHERE HABITACION = ? AND ESTADO = 'PROGRAMADO' ORDER BY DATE(CHECKIN) ASC", 
            (habitacion,)
        )
        return (huesped, "PROGRAMADO") if huesped else (None, None)

def _obtener_consumos(huesped, incluir_pagos=False):
    query = """
        SELECT C.ID, C.FECHA, C.PRODUCTO, P.NOMBRE, C.CANTIDAD, P.PRECIO, C.PAGADO 
        FROM CONSUMOS C 
        JOIN PRODUCTOS P ON C.PRODUCTO = P.CODIGO 
        WHERE C.HUESPED = ? AND C.FECHA >= ?
    """
    params = [huesped["NUMERO"], huesped["CHECKIN"]]
    if not incluir_pagos:
        query += " AND C.PAGADO = 0"
    query += " ORDER BY C.FECHA ASC"
    return db.obtener_todos(query, tuple(params))

def _preparar_consumos(consumos):
    agrupados = {}
    for c in consumos:
        dt = parse_fecha_a_datetime(c["FECHA"])
        if not dt:
            continue
        c["ITEM_TOTAL"] = c["CANTIDAD"] * c["PRECIO"]
        c["FECHA_SOLO"] = dt.date().isoformat()
        c["HORA_SOLO"] = dt.strftime("%H:%M") if dt.time() != datetime.min.time() else ""
        agrupados.setdefault(c["FECHA_SOLO"], []).append(c)
    return agrupados

def _imprimir_consumos(consumos_agrupados, incluir_columna_pagado=False):
    if incluir_columna_pagado:
        print(f"{'#':<3} {'HORA':<15} {'PRODUCTO':<28} {'CANTIDAD':<6} {'P.UNIT':>10} {'P.TOTAL':>12} {'PAGADO':>5}")
        print("-" * 88)
    else:
        print(f"{'#':<3} {'HORA':<15} {'PRODUCTO':<30} {'CANTIDAD':<6} {'P.UNIT':>10} {'P.TOTAL':>12}")
        print("-" * 84)

    indice = 1
    total_general = 0.0

    for fecha_dia in sorted(consumos_agrupados.keys()):
        consumos_dia = consumos_agrupados[fecha_dia]
        subtotal = 0.0
        fecha_fmt = formatear_fecha(fecha_dia)
        separador = 85 - len(fecha_fmt) - 13 + (4 if incluir_columna_pagado else 0)
        print(f"\n--- FECHA: {fecha_fmt} " + "-" * separador)

        for c in consumos_dia:
            prod = c["NOMBRE"].title()
            if len(prod) > (28 if incluir_columna_pagado else 30):
                prod = prod[:(25 if incluir_columna_pagado else 27)] + '...'

            subtotal += c["ITEM_TOTAL"]

            if incluir_columna_pagado:
                pagado = "SI" if c["PAGADO"] else "NO"
                print(f"{indice:<3} {c['HORA_SOLO']:<15} {prod:<28} {c['CANTIDAD']:<6} {c['PRECIO']:>10.2f} {c['ITEM_TOTAL']:>12.2f} {pagado:>5}")
            else:
                print(f"{indice:<3} {c['HORA_SOLO']:<15} {prod:<30} {c['CANTIDAD']:<6} {c['PRECIO']:>10.2f} {c['ITEM_TOTAL']:>12.2f}")
            indice += 1

        ancho = 88 if incluir_columna_pagado else 84
        print("-" * ancho)
        print(f"{'SUBTOTAL DIARIO:':<{ancho - 16}} {subtotal:>12.2f}")
        print("=" * ancho)
        total_general += subtotal

    return total_general

def _imprimir_total(huesped, grand_subtotal):
    """
    Imprime el total final de la cuenta del huésped, aplicando descuentos si existen
    y la propina del 10%, alineando todo igual que los subtotales diarios de ver_consumos().
    """
    ANCHO_TOTAL_LINEA = 84
    print("\n" + "=" * ANCHO_TOTAL_LINEA)

    # TOTAL DE CONSUMOS
    _formato_print("TOTAL DE CONSUMOS:", grand_subtotal)

    # --- Inicialización de variables de descuento ---
    descuento_str = huesped.get("DESCUENTO")
    monto_dcto_consumos = 0.0
    monto_dcto_final = 0.0
    lugar = tipo = valor = None
    dcto_descripcion = ""
    dcto_descripcion_final = ""

    # --- Lógica de descuentos ---
    if descuento_str:
        try:
            partes = descuento_str.split('-')
            lugar, tipo, valor_str = partes[0], partes[1], partes[2]
            valor = float(valor_str)

            if lugar == 'consumos':
                if tipo == 'pct':
                    monto_dcto_consumos = grand_subtotal * (valor / 100.0)
                    dcto_descripcion = f"DESCUENTO ({valor}%)"
                elif tipo == 'valor':
                    monto_dcto_consumos = valor
                    dcto_descripcion = f"DESCUENTO (R$ {valor:.2f})"

                if monto_dcto_consumos > 0:
                    monto_negativo_dcto_consumos = -1 * monto_dcto_consumos
                    _formato_print(dcto_descripcion + ":", monto_negativo_dcto_consumos)
                    print("-" * ANCHO_TOTAL_LINEA)

        except (IndexError, ValueError):
            print("❗ Advertencia: Formato de descuento inválido. Ignorando descuento.")
            descuento_str = None
            lugar = None

    # --- Subtotal después de descuento sobre consumos ---
    subtotal_descontado = grand_subtotal - monto_dcto_consumos
    if monto_dcto_consumos > 0:
        _formato_print("SUBTOTAL:", subtotal_descontado)

    # --- Propina 10% ---
    propina = subtotal_descontado * 0.10
    _formato_print("PROPINA (10%):", propina)

    total_con_propina = subtotal_descontado + propina

    # --- Descuento final (tipo 'final') ---
    if descuento_str and lugar == 'final':
        print("-" * ANCHO_TOTAL_LINEA)
        _formato_print("SUBTOTAL + PROPINA:", total_con_propina)

        if tipo == 'pct':
            monto_dcto_final = total_con_propina * (valor / 100.0)
            dcto_descripcion_final = f"DESCUENTO ({valor}%)"
        else:
            monto_dcto_final = min(valor, total_con_propina)
            dcto_descripcion_final = f"DESCUENTO (R$ {valor:.2f})"

        if monto_dcto_final > 0:
            monto_negativo_dcto_final = -1 * monto_dcto_final
            _formato_print(dcto_descripcion_final + ":", monto_negativo_dcto_final)

    # --- Total final ---
    total_final = total_con_propina - monto_dcto_final
    print("=" * ANCHO_TOTAL_LINEA)
    _formato_print("TOTAL A PAGAR:", total_final)
    print("=" * ANCHO_TOTAL_LINEA)

def _formato_print(etiqueta, valor):
    """
    Imprime un total con etiqueta de 70 chars, R$ y número alineado igual que en ver_consumos().
    """
    ETQ_WIDTH = 69
    R = "R$"
    NUM_WIDTH = 8   # signo + 2-4 dígitos + .00 + espacio
    NUM_EXTRA_SPACES = 3
    print(f"{etiqueta:<{ETQ_WIDTH}} {R} {valor:>{NUM_WIDTH}.2f}{' ' * NUM_EXTRA_SPACES}")

@usuarios.requiere_acceso(2)
def eliminar_consumos():
    leyenda_hab = "\nIngresá el número de habitación para eliminar consumos, (*) para buscar ó (0) para cancelar: "
    while True:
        habitacion = opcion_menu(leyenda_hab, cero=True, asterisco=True, minimo=1, maximo=7)
        if habitacion == 0:
            return
        if habitacion == "*":
            buscar_huesped()
            continue

        huesped = db.obtener_uno("SELECT * FROM HUESPEDES WHERE HABITACION = ?", (habitacion,))
        if huesped is None:
            print("❌ Habitación no encontrada.")
            continue

        imprimir_huesped(huesped)

        query = """ SELECT C.ID, C.FECHA, C.PRODUCTO, P.NOMBRE, C.CANTIDAD FROM CONSUMOS C JOIN PRODUCTOS P ON C.PRODUCTO = P.CODIGO WHERE C.HUESPED = ? ORDER BY C.FECHA DESC"""
        consumos = db.obtener_todos(query, (huesped["NUMERO"],))

        if not consumos:
            print("\n❌ Esta habitación no tiene consumos registrados.")
            return

        print(f"\nConsumos de la habitación {huesped['HABITACION']}, huésped {huesped['NOMBRE'].title()} {huesped['APELLIDO'].title()}:\n")
        print(f"{'#':<3} {'FECHA':<12} {'PRODUCTO':<30} {'CANTIDAD':<10}")
        print("-" * 60)
        for idx, consumo in enumerate(consumos, start=1):
            fecha = consumo["FECHA"]
            producto_nombre = consumo["NOMBRE"]
            cantidad = consumo["CANTIDAD"]
            print(f"{idx:<3} {formatear_fecha(fecha):<12} {producto_nombre:<30} {cantidad:<10}")

        _seleccionar_consumos_a_eliminar(huesped, consumos) 
        
        return

def _seleccionar_consumos_a_eliminar(huesped, consumos):
    """
    Gestiona la selección, validación, confirmación y eliminación de consumos.

    :param huesped: Diccionario con la información del huésped.
    :param consumos: Lista de diccionarios de consumos registrados para el huésped.
    :return: True si se eliminó al menos un consumo, False si se canceló o no se seleccionó nada válido.
    """
    # 1. Selección de consumos
    seleccion = input("\nIngresá el/los número(s) de consumo a eliminar separados por coma (ej: 1,3): ").strip().split(",")
    a_eliminar = [] # Contendrá los índices (0-based) de 'consumos' que se van a eliminar

    # 2. Validación de la selección
    for item in seleccion:
        item = item.strip()
        if item.isdigit():
            idx = int(item)
            if 1 <= idx <= len(consumos):
                a_eliminar.append(idx - 1) # Guardamos el índice 0-based
            else:
                print(f"\n❌ Índice ({idx}) fuera de rango: ")
        else:
            print(f"\n❌ Entrada inválida: {item}")
    
    if not a_eliminar:
        print("❌ No se seleccionaron consumos válidos.")
        return False
    
    # 3. Mostrar consumos seleccionados para confirmación
    consumos_a_mostrar = [consumos[i] for i in a_eliminar]
    
    print("\n📋 Consumo(s) seleccionado(s) para eliminar:")
    print(f"{'#':<3} {'PRODUCTO':<30} {'CANTIDAD':<10} {'FECHA':<12}")
    print("-" * 60)
    
    # Obtenemos los números originales (1-based) para mostrar:
    numeros_seleccionados = [i + 1 for i in a_eliminar] 
    
    for i, consumo in enumerate(consumos_a_mostrar):
        fecha = consumo["FECHA"]
        producto_nombre = consumo["NOMBRE"]
        cantidad = consumo["CANTIDAD"]
        # Usamos el número original de la lista para mostrar la referencia
        print(f"{numeros_seleccionados[i]:<3} {producto_nombre:<30} {cantidad:<10} {formatear_fecha(fecha):<12}")

    # 4. Pedir confirmación
    if pedir_confirmacion("\n¿Estás seguro que querés eliminar los siguientes consumo(s)? (si/no): ") != "si":
        print("❌ Operación cancelada.")
        return False

    # 5. Ejecutar eliminación en DB
    try:
        # Se mantiene la llamada original a _eliminar_consumos_db
        eliminados = _eliminar_consumos_db(huesped, consumos, a_eliminar)
        print(f"✔ Se eliminaron {eliminados} consumos.")
        return True
    except Exception as e:
        print(f"\n❌ Error al eliminar en la base de datos: {e}")
        return False

def _eliminar_consumos_db(huesped, consumos, a_eliminar):
    """
    Elimina consumos seleccionados y restaura stock en la DB.
    Devuelve la cantidad de consumos eliminados.
    """
    try:
        with db.transaccion():
            for i in a_eliminar:
                consumo_data = consumos[i]
                consumo_id = consumo_data["ID"]
                producto_id = consumo_data["PRODUCTO"]
                producto_nombre = consumo_data["NOMBRE"]
                cantidad = consumo_data["CANTIDAD"]

                # Restaurar stock (producto y equivalentes de su grupo)
                grupo_info = db.obtener_uno("SELECT GRUPO FROM PRODUCTOS WHERE CODIGO = ?", (producto_id,))
                grupo = grupo_info["GRUPO"] if grupo_info else None

                if grupo:
                    equivalentes = db.obtener_todos("SELECT CODIGO, STOCK FROM PRODUCTOS WHERE GRUPO = ?", (grupo,))
                    for eq in equivalentes:
                        if eq["STOCK"] != -1:
                            nuevo_stock = eq["STOCK"] + cantidad
                            db.ejecutar("UPDATE PRODUCTOS SET STOCK = ? WHERE CODIGO = ?", (nuevo_stock, eq["CODIGO"]))
                else:
                    producto = db.obtener_uno("SELECT STOCK FROM PRODUCTOS WHERE CODIGO = ?", (producto_id,))
                    if producto and producto["STOCK"] != -1:
                        nuevo_stock = producto["STOCK"] + cantidad
                        db.ejecutar("UPDATE PRODUCTOS SET STOCK = ? WHERE CODIGO = ?", (nuevo_stock, producto_id))

                # Eliminar consumo
                db.ejecutar("DELETE FROM CONSUMOS WHERE ID = ?", (consumo_id,))

                # Log
                marca_tiempo = marca_de_tiempo()
                log = (
                    f"[{marca_tiempo}] CONSUMO ELIMINADO:\n"
                    f"Huésped: {huesped['NOMBRE']} {huesped['APELLIDO']} | Habitación: {huesped['HABITACION']} | Huesped_ID: {huesped['NUMERO']}\n"
                    f"Producto: {producto_nombre} (ID: {producto_id}) | Cantidad: {cantidad} | Consumo_ID: {consumo_id}\n"
                    f"Acción realizada por: {usuarios.sesion.usuario}"
                )
                registrar_log("consumos_eliminados.log", log)
        return len(a_eliminar)
    except Exception as e:
        raise RuntimeError(f"La operación de eliminación falló y fue revertida: {e}")

@usuarios.requiere_acceso(1)
def registrar_pago():
    leyenda_hab = "\nIngresá el número de habitación para registrar el pago, (*) para buscar ó (0) para cancelar: "
    while True:
        habitacion = opcion_menu(leyenda_hab, cero=True, asterisco=True, minimo=1, maximo=7)
        if habitacion == 0:
            return
        if habitacion == "*":
            buscar_huesped()
            continue

        huesped = db.obtener_uno("SELECT * FROM HUESPEDES WHERE HABITACION = ?", (habitacion,))
        if not huesped:
            print("❌ Huesped no encontrado en esa habmitación.")
            continue
        break
    consumos_pendientes = _obtener_y_mostrar_consumos(huesped)
    
    if consumos_pendientes:
        # Procesar la selección del usuario y ejecutar la transacción
        _procesar_pago(consumos_pendientes)
        
    return

def _obtener_y_mostrar_consumos(huesped):
    """
    Obtiene los consumos pendientes de un huésped y los imprime.
    Retorna la lista de consumos pendientes o None si no hay.
    """
    numero_huesped = huesped["NUMERO"]
    habitacion = huesped["HABITACION"]
    
    query = """
        SELECT C.ID, C.FECHA, P.NOMBRE, C.CANTIDAD, P.PRECIO
        FROM CONSUMOS C
        JOIN PRODUCTOS P ON C.PRODUCTO = P.CODIGO
        WHERE C.HUESPED = ? AND C.PAGADO = 0
        ORDER BY C.FECHA DESC
    """
    consumos = db.obtener_todos(query, (numero_huesped,))

    if not consumos:
        # Chequeo para dar un mensaje más específico
        todos = db.obtener_todos("SELECT ID FROM CONSUMOS WHERE HUESPED = ?", (numero_huesped,))
        if not todos:
            print("✔ Esta habitación no tiene consumos registrados.")
        else:
            print("✔ Todos los consumos ya están marcados como pagados.")
        return None # Indica que no hay nada que pagar

    # Impresión de la lista de consumos
    print(f"\nConsumos pendientes de pago para {huesped['NOMBRE'].title()} {huesped['APELLIDO'].title()} (habitación {habitacion}):\n")
    print(f"{'#':<3} {'FECHA':<20} {'PRODUCTO':<25} {'CANT':<5} {'TOTAL':>10}")
    print("-" * 70)

    for idx, consumo in enumerate(consumos, start=1):
        # Usamos 'ID' por convención, pero el query retorna 'C.ID'
        fecha = consumo["FECHA"]
        producto = consumo["NOMBRE"] # Usamos NOMBRE en lugar de PRODUCTO para el JOIN
        cant = consumo["CANTIDAD"]
        precio = consumo["PRECIO"]
        total = cant * precio
        # Aquí también estamos asumiendo que el campo C.ID se mapea en el diccionario por ID
        print(f"{idx:<3} {fecha:<20} {producto:<25} {cant:<5} {total:>10.2f}")
        
    return consumos

def _procesar_pago(consumos_pendientes):
    """
    Maneja la interacción para seleccionar y marcar los consumos como pagados.
    """
    seleccion = input("\nIngresá los números de los consumos a marcar como pagos separados por coma (ej: 1,3,4), ó (0) para cancelar: ").strip()
    
    if seleccion == "0":
        print("❌ Operación cancelada.")
        return

    # 1. Parsing y validación de índices
    indices_str = [s.strip() for s in seleccion.split(",") if s.strip().isdigit()]
    
    consumos_a_pagar_ids = []
    
    for i in indices_str:
        try:
            idx = int(i)
            # Chequea si el índice está dentro del rango válido (1 a len(consumos))
            if 1 <= idx <= len(consumos_pendientes):
                # El ID de la BD es lo que necesitamos para la transacción
                consumos_a_pagar_ids.append(consumos_pendientes[idx - 1]["ID"]) 
            else:
                print(f"❌ Índice fuera de rango: {idx}")
        except ValueError:
            # Esto no debería ocurrir si filtramos con isdigit(), pero es buena práctica
            pass 

    if not consumos_a_pagar_ids:
        print("❌ No se seleccionaron consumos válidos.")
        return

    # 2. Ejecución de la transacción
    try:
        with db.transaccion():
            for cid in consumos_a_pagar_ids:
                db.ejecutar("UPDATE CONSUMOS SET PAGADO = 1 WHERE ID = ?", (cid,))
        print(f"\n✔ Se marcaron {len(consumos_a_pagar_ids)} consumo(s) como pagados.")
    except Exception as e:
        print(f"\n❌ La operación de registrar pago falló y fue revertida. Error: {e}")

@usuarios.requiere_acceso(2)
def asignar_descuento():
    """
    Asigna un único descuento (lugar, tipo de valor y cantidad) a la cuenta de un huésped.
    El formato de guardado es: LUGAR-TIPO_VALOR-VALOR_O_PCT
    Ej: consumos-pct-15, final-valor-50.00
    """
    # 0. SELECCIÓN DE HUÉSPED
    # Asegúrate que '_seleccionar_huesped' está disponible
    huesped = _seleccionar_huesped("\nIngresá el número de habitación para agregar un descuento, (*) para buscar ó (0) para cancelar: ")
    if not huesped:
        return

    numero_huesped = huesped["NUMERO"]
    descuento_actual_str = huesped.get("DESCUENTO")

    print("\n--- Asignar Descuento ---")
    print(f"Huésped: {huesped['NOMBRE'].title()} {huesped['APELLIDO'].title()}")

    # Parsear y mostrar el descuento actual
    if descuento_actual_str:
        try:
            lugar, tipo_val, valor_str = descuento_actual_str.split('-')
            lugar_display = "sobre consumos" if lugar == "consumos" else "sobre el total final"
            if tipo_val == "pct":
                descuento_display = f"{valor_str}% {lugar_display}"
            else: # tipo_val == "valor"
                # Usamos float(valor_str) para asegurar un formato limpio en el display
                descuento_display = f"R$ {float(valor_str):.2f} {lugar_display}"
            
            print(f"Descuento actual: {descuento_display}")
        except Exception:
            print("Advertencia: Descuento actual en formato desconocido.")
    else:
        print("Actualmente no tiene ningún descuento asignado.")
    print("-----------------------------")

    # 1. RECOLECCIÓN DE PARÁMETROS (Delegado)
    lugar_str, tipo_str, valor_numerico, valor_guardado, valor_display = _recolectar_parametros_descuento()

    if lugar_str is None: # Si se canceló la operación en la recolección
        print("\n❌ Operación cancelada."); return
    
    # 2. CONSTRUCCIÓN DEL VALOR DE GUARDADO Y LOG (Lógica Original)
    nuevo_valor_descuento = None
    log_string = ""
    
    if valor_numerico > 0: 
        # Formato de guardado: LUGAR-TIPO_VALOR-VALOR_O_PCT
        nuevo_valor_descuento = f"{lugar_str}-{tipo_str}-{valor_guardado}"
        
        lugar_log = "sobre consumos" if lugar_str == "consumos" else "sobre el total"
        # valor_display ya tiene el % o R$
        log_string = f"Se asignó un descuento de {valor_display} {lugar_log}" 
    else:
        # Se ingresó 0 o 0.0 para quitar el descuento
        log_string = "Se quitó el descuento existente"

    # 3. EJECUTAR ACTUALIZACIÓN Y LOG (Delegado)
    _ejecutar_actualizacion_descuento(numero_huesped, nuevo_valor_descuento, log_string)

def _recolectar_parametros_descuento():
    """
    Guía al usuario para seleccionar el lugar, el tipo y el valor del descuento.
    Retorna (tipo_str, tipo_valor_str, valor_numerico, valor_guardado, valor_display)
    o (None, None, None, None, None) si se cancela.
    """
    # 1. Preguntar por el lugar de aplicación
    leyenda_lugar = "\n¿Dónde se aplica el descuento?\n1. Sobre los consumos\n2. Sobre el total\n0. Cancelar\n"
    opcion_lugar = opcion_menu(leyenda_lugar, cero=True, minimo=1, maximo=2)

    if opcion_lugar == 0:
        return None, None, None, None, None
    
    lugar_str = "consumos" if opcion_lugar == 1 else "final"

    # 2. Preguntar por el tipo de valor (Porcentaje o Valor Fijo)
    leyenda_tipo = "\n¿Cómo es el descuento?\n1. Porcentaje (%)\n2. Valor Fijo (R$)\n0. Cancelar\n"
    opcion_tipo = opcion_menu(leyenda_tipo, cero=True, minimo=1, maximo=2)

    if opcion_tipo == 0:
        return None, None, None, None, None
    
    tipo_str = "pct" if opcion_tipo == 1 else "valor"

    # 3. Preguntar por el valor y formatearlo
    valor_numerico = 0.0
    valor_display = ""
    valor_guardado = ""
    
    if tipo_str == "pct":
        valor_numerico = pedir_entero("Ingresá el porcentaje de descuento (0 para quitar): ", minimo=0, maximo=100)
        valor_display = f"{valor_numerico}%"
        valor_guardado = str(valor_numerico) # Se guarda como cadena (ej: "15")
    else: # tipo_valor_str == "valor"
        valor_numerico = pedir_precio("Ingresá el valor fijo del descuento (R$ 0.00 para quitar): ") 
        valor_display = f"R$ {valor_numerico:.2f}"
        valor_guardado = f"{valor_numerico:.2f}"
        
    return lugar_str, tipo_str, valor_numerico, valor_guardado, valor_display

def _ejecutar_actualizacion_descuento(numero_huesped, nuevo_valor_descuento, log_string):
    """
    Prepara y ejecuta la actualización del campo DESCUENTO y el REGISTRO.
    """
    updates = {"DESCUENTO": nuevo_valor_descuento}
    
    # Obtener el registro actual
    registro_anterior_data = db.obtener_uno("SELECT REGISTRO FROM HUESPEDES WHERE NUMERO = ?", (numero_huesped,))
    registro_anterior = str(registro_anterior_data["REGISTRO"] or "")
    
    # Crear el nuevo registro (Asegúrate que 'marca_de_tiempo' y 'usuarios.sesion.usuario' están disponibles)
    registro_descuento = f"{log_string} por {usuarios.sesion.usuario} - {marca_de_tiempo()}"
    updates["REGISTRO"] = (registro_anterior + "\n---\n" + registro_descuento) if registro_anterior.strip() else registro_descuento

    try:
        with db.transaccion():
            _editar_huesped_db(numero_huesped, updates) 
        print("\n✔ Operación de descuento realizada correctamente.")
        return True
    except Exception as e:
        print(f"\n❌ Error al aplicar el descuento: {e}")
        return False

@usuarios.requiere_acceso(2)
def consumo_cortesia():
    # Coordina el proceso de registrar un consumo de cortesía.
    # 1. Recolectar productos
    cortesias_iniciales = _recolectar_cortesias()
    if not cortesias_iniciales:
        print("\n❌ No se agregaron productos. Operación finalizada.")
        return

    # 2. Permitir edición de la lista
    cortesias_finales = _editar_lista_cortesias(cortesias_iniciales)
    if not cortesias_finales:
        print("\n❌ No quedaron cortesías para registrar.")
        return

    # 3. Obtener autorización
    autorizante = _obtener_autorizante()
    if not autorizante:
        return # Mensaje de cancelación ya mostrado en la función auxiliar

    # 4. Guardar y registrar todo
    _guardar_y_registrar_cortesias(cortesias_finales, autorizante)

def _recolectar_cortesias():
    # Recolecta productos para cortesía en un bucle interactivo.
    # Devuelve una lista de diccionarios de cortesías.

        cortesias = []
        leyenda = "\nIngresá el código del producto, (*) para buscar ó (0) para finalizar: "
        while True:
            codigo = opcion_menu(leyenda, cero=True, asterisco=True, minimo=1)
            if codigo == 0:
                break
            if codigo == "*":
                productos = db.obtener_todos("SELECT * FROM PRODUCTOS WHERE STOCK > 0 OR STOCK = -1")
                if productos:
                    imprimir_productos(productos)
                else:
                    print("\n❌ No hay productos en stock.")
                continue

            producto = db.obtener_uno("SELECT * FROM PRODUCTOS WHERE CODIGO = ?", (codigo,))
            if not producto:
                print("\n⚠️  Producto no encontrado.")
                continue
            
            # Procesa la cantidad para el producto seleccionado
            nombre = producto["NOMBRE"]
            stock = producto["STOCK"]
            print(f"\nProducto seleccionado: {nombre} (Stock: {'Infinito' if stock == -1 else stock})")
            
            while True:
                cantidad = pedir_entero("Ingresá la cantidad ó (0) para cancelar: ", minimo=0)
                if cantidad == 0:
                    print("\n❌ Producto cancelado.")
                    break
                if stock != -1 and cantidad > stock:
                    print(f"\n❌ No hay suficiente stock. Disponibles: {stock}")
                    continue
                
                cortesias.append({
                    "codigo": codigo, "nombre": nombre, "cantidad": cantidad, "stock_anterior": stock
                })
                print(f"✔ Se agregó a la lista: {cantidad} unidad(es) de '{nombre}'.")
                break # Sale del bucle de cantidad
                
        return cortesias

def _editar_lista_cortesias(cortesias):
    # Permite al usuario eliminar elementos de la lista de cortesías.
    # Devuelve la lista modificada.

    if not cortesias or pedir_confirmacion("\n¿Querés eliminar alguna de las cortesías? (si/no): ") != "si":
        return cortesias

    print("\nCortesías recién agregadas:")
    for i, cortesia in enumerate(cortesias):
        print(f"  {i + 1}. {cortesia['nombre']} (Cód: {cortesia['codigo']}), Cantidad: {cortesia['cantidad']}")

    a_eliminar_str = input("Ingresá los ítems a eliminar (separados por comas/espacios), ó '0' para cancelar: ").strip()
    if a_eliminar_str == '0':
        return cortesias

    indices_a_eliminar = set()
    partes = re.split(r'[,\s]+', a_eliminar_str)
    for parte in partes:
        try:
            indice = int(parte) - 1
            if 0 <= indice < len(cortesias):
                indices_a_eliminar.add(indice)
            else:
                print(f"❌ El número {indice + 1} es inválido. Se ignorará.")
        except ValueError:
            print(f"❌ La entrada '{parte}' no es un número. Se ignorará.")

    # Eliminar índices en orden inverso para no afectar las posiciones
    for indice in sorted(list(indices_a_eliminar), reverse=True):
        item_eliminado = cortesias.pop(indice)
        print(f"✔ Cortesía de '{item_eliminado['nombre']}' eliminada.")
        
    return cortesias

def _obtener_autorizante():
    # Solicita y valida el nombre de la persona que autoriza la cortesía.
    # Devuelve el nombre limpio o None si se cancela.

    while True:
        respuesta = input("\nIngresá quién autoriza la cortesía ó (0) para cancelar: ").strip()
        if respuesta == "0":
            print("\n❌ Registro de cortesía cancelado.")
            return None
        if not respuesta:
            print("\n⚠️  El nombre del autorizante no puede estar vacío.")
            continue

        # Limpieza del nombre
        autoriza_limpio = unidecode(respuesta).replace('-', ' ').replace('_', ' ')
        autoriza_final = re.sub(r"[^a-zA-Z0-9\s]", "", autoriza_limpio).lower()
        
        if not autoriza_final.strip():
            print("\n⚠️  El nombre no puede contener solo caracteres especiales.")
            continue
        
        return autoriza_final

def _guardar_y_registrar_cortesias(cortesias, autoriza):
    # Guarda las cortesías en la BD, actualiza el stock y escribe en el archivo de log.

    try:
        with db.transaccion():
            for cortesia in cortesias:
                fecha = datetime.now().isoformat(sep=" ", timespec="seconds")
                
                # 1. Insertar en la tabla de CORTESIAS
                db.ejecutar("INSERT INTO CORTESIAS (PRODUCTO, CANTIDAD, FECHA, AUTORIZA) VALUES (?, ?, ?, ?)",
                            (cortesia['codigo'], cortesia['cantidad'], fecha, autoriza))

                # 2. Actualizar stock del producto
                if cortesia['stock_anterior'] != -1:
                    nuevo_stock = cortesia['stock_anterior'] - cortesia['cantidad']
                    db.ejecutar("UPDATE PRODUCTOS SET STOCK = ? WHERE CODIGO = ?", (nuevo_stock, cortesia['codigo']))

                # 3. Registrar en el archivo de log
                log = (
                    f"[{marca_de_tiempo()}] CONSUMO DE CORTESÍA:\n"
                    f"Producto: {cortesia['nombre']} (ID: {cortesia['codigo']}) | "
                    f"Cantidad: {cortesia['cantidad']} | "
                    f"Autorizado por: {autoriza.title()} | "
                    f"Registrado por: {usuarios.sesion.usuario}"
                )
                registrar_log("consumos_cortesia.log", log)
        print(f"\n✔ Cortesía autorizada por {autoriza.capitalize()} registrada correctamente.")
        for i, cortesia in enumerate(cortesias):
            print(f"  {i + 1}. {cortesia['nombre'].capitalize()}, (x{cortesia['cantidad']})")

    except Exception as e:
        print(f"\n❌ Hubo un error al registrar la cortesía y fue cancelado: {e}")
