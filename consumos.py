import re
import usuarios
from datetime import datetime
from db import db
from huespedes import buscar_huesped, _editar_huesped_db
from unidecode import unidecode
from utiles import registrar_log, imprimir_huesped, pedir_entero, pedir_confirmacion, imprimir_productos, formatear_fecha, marca_de_tiempo, opcion_menu

def _seleccionar_huesped():
    # Gestiona la selección de un huésped. Devuelve el diccionario del huésped
    # o None si se cancela la operación.
    leyenda_hab = "\nIngresá el número de habitación para agregar un consumo, (*) para buscar ó (0) para cancelar: "
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
    print(f"Producto seleccionado: {nombre.capitalize()} (Stock: {'Infinito' if stock == -1 else stock})")

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
            if pedir_confirmacion(f"\n⚠️  '{nombre}' debería ser pagado en el momento. ¿Querés registrarlo como pagado? (si/no): ") == "si":
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

    if pedir_confirmacion("\n¿Querés eliminar alguno de los consumos recién agregados? (si/no): ", defecto="no") != "si":
        return consumos

    print("\nConsumos recién agregados:")
    for i, consumo in enumerate(consumos):
        print(f"  {i + 1}. Producto: {consumo['nombre']} (Cód: {consumo['codigo']}), Cantidad: {consumo['cantidad']}")

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
            print(f"✔ Consumo de '{consumo_eliminado['nombre']}' eliminado.")
    
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
def agregar_consumo():
    # Función principal para coordinar el proceso de agregar consumos a un huésped.
    huesped = _seleccionar_huesped()
    if not huesped:
        print("\n❌ Operación cancelada.")
        return

    consumos_pendientes = _recolectar_consumos(huesped["NUMERO"])
    
    consumos_finales = _editar_consumos_agregados(consumos_pendientes)

    if consumos_finales:
        _guardar_consumos_en_db(consumos_finales, huesped)
    else:
        print("\n❌ No se registraron nuevos consumos.")

@usuarios.requiere_acceso(0)
def ver_consumos():
    leyenda_hab = "\nIngresá el número de habitación para ver sus consumos, (*) para buscar ó (0) para cancelar: "
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

        query = """SELECT C.ID, C.FECHA, C.PRODUCTO, P.NOMBRE, C.CANTIDAD, P.PRECIO FROM CONSUMOS C JOIN PRODUCTOS P ON C.PRODUCTO = P.CODIGO WHERE C.HUESPED = ? ORDER BY C.FECHA DESC"""
        consumos = db.obtener_todos(query, (huesped["NUMERO"],))

        if consumos:
            print(f"\nHistorial de consumos de la habitación {huesped['HABITACION']}, huésped {huesped['NOMBRE'].title()} {huesped['APELLIDO'].title()}:\n")
            # Modificación: Agregar "PRECIO TOTAL" al encabezado
            print(f"{'#':<3} {'FECHA Y HORA':<20} {'PRODUCTO':<30} {'CANTIDAD':<6} {'P. UNIT':>10} {'PRECIO_TOTAL':>12}")
            print("-" * 90) # Ajustar la longitud de la línea separadora

            grand_total = 0.0 # Inicializar el total general

            for idx, consumo in enumerate(consumos, start=1):
                fecha = consumo["FECHA"]
                producto_nombre = consumo["NOMBRE"].capitalize()
                cantidad = consumo["CANTIDAD"]
                precio = consumo["PRECIO"]
                fecha_display = formatear_fecha(fecha)
                item_total = cantidad * precio # Calcular el total por item
                grand_total += item_total # Acumular al total general
                if len(producto_nombre) > 30:
                    producto_nombre = producto_nombre[:27] + '...'
                # Modificación: Imprimir el precio total por item
                print(f"{idx:<3} {fecha_display:<20} {producto_nombre:<30} {cantidad:<6} {precio:>10.2f} {item_total:>12.2f}")
            print("-" * 90) # Línea separadora antes del total
            print(f"{'TOTAL:':<70} {grand_total:>15.2f}") # Imprimir el total general
        else:
            print("\nEsta habitación no tiene consumos registrados.")
        return

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
            consumo_id = consumo["ID"]
            fecha = consumo["FECHA"]
            producto_id = consumo["PRODUCTO"]
            producto_nombre = consumo["NOMBRE"]
            cantidad = consumo["CANTIDAD"]
            print(f"{idx:<3} {formatear_fecha(fecha):<12} {producto_nombre:<30} {cantidad:<10}")

        seleccion = input("\nIngresá el/los número(s) de consumo a eliminar separados por coma (ej: 1,3): ").strip()
        seleccion = seleccion.split(",")
        a_eliminar = []
        for item in seleccion:
            item = item.strip()
            if item.isdigit():
                idx = int(item)
                if 1 <= idx <= len(consumos):
                    a_eliminar.append(idx - 1)
                else:
                    print(f"\n❌ Índice ({idx}) fuera de rango: ")
            else:
                print(f"\n❌ Entrada inválida: {item}")
        
        if not a_eliminar:
                print("❌ No se seleccionaron consumos válidos.")
                return
        
        try:
            # Inicia la transacción
            with db.transaccion():
                for i in a_eliminar:
                    consumo_data = consumos[i]
                    consumo_id = consumo_data["ID"]
                    producto_id = consumo_data["PRODUCTO"]
                    producto_nombre = consumo_data["NOMBRE"]
                    cantidad = consumo_data["CANTIDAD"]

                    # Restaurar stock si aplica
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
                        f"Producto: {producto_nombre} (ID: {producto_id}) | Cantidad: {cantidad} | Consumo_ID: {consumo_id}"
                        f"Acción realizada por: {usuarios.sesion.usuario}"
                    )
                    registrar_log("consumos_eliminados.log", log)
            print(f"✔ Se eliminaron {len(a_eliminar)} consumos.")
        except Exception as e:
            print(f"\n❌ La operación de eliminación falló y fue revertida.")
        return

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
        cid = consumo["ID"] # Se asume que el ORM lo renombra a 'ID' si el query lo pide
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