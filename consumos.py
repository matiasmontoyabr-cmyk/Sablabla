import re
import usuarios
from datetime import datetime
from db import db
from huespedes import buscar_huesped, editar_huesped_db
from unidecode import unidecode
from utiles import registrar_log, imprimir_huesped, pedir_entero, pedir_confirmacion, imprimir_productos, formatear_fecha, marca_de_tiempo, opcion_menu

@usuarios.requiere_acceso(1)
def agregar_consumo():
    leyenda_hab = "\nIngresá el número de habitación para agregar un consumo, (*) para buscar ó (0) para cancelar: "
    while True:
        respuesta = opcion_menu(leyenda_hab, cero=True, asterisco=True, minimo=1, maximo=7)
        if respuesta == 0:
            return
        if respuesta == "*":
            buscar_huesped()
            continue
        habitacion = respuesta
        huesped = db.obtener_uno("SELECT * FROM HUESPEDES WHERE HABITACION = ? AND ESTADO = 'ABIERTO'", (habitacion,))
        if huesped is None:
            print("\n❌ No se encontró un huésped ABIERTO en esa habitación.")
            continue

        nombre_display = ' '.join(word.capitalize() for word in str(huesped["NOMBRE"]).split())
        apellido_display = ' '.join(word.capitalize() for word in str(huesped["APELLIDO"]).split())
        print(f"Habitación {huesped['HABITACION']} - Huésped {nombre_display} {apellido_display}")
        break

    numero_huesped = huesped["NUMERO"]
    consumos_agregados = []

    while True:
        leyenda_cod = "\nIngresá el código del producto consumido, (*) para buscar ó (0) para finalizar: "
        codigo = opcion_menu(leyenda_cod, cero=True, asterisco=True, minimo=1)
        if codigo == 0:
            break
        elif codigo == "*":
            productos = db.obtener_todos("SELECT * FROM PRODUCTOS WHERE STOCK > 0 OR STOCK = -1")
            if not productos:
                print("\n❌ No hay productos en stock.")
                return
            else:
                imprimir_productos(productos)
                continue

        producto = db.obtener_uno("SELECT * FROM PRODUCTOS WHERE CODIGO = ?", (codigo,))
        if not producto:
            print("\n❌ Producto no encontrado.")
            continue

        nombre = producto["NOMBRE"]
        stock = producto["STOCK"]
        pinmediato = producto["PINMEDIATO"]
        print(f"Producto seleccionado: {nombre.capitalize()} (Stock: {'Infinito' if stock == -1 else stock})")

        while True:
            cantidad = pedir_entero("Ingresá la cantidad consumida ó (0) para cancelar: ", minimo=0)
            if cantidad == 0:
                print("\n❌ Producto cancelado.")
                break
            elif stock != -1 and cantidad > stock:
                print(f"\n❌ No hay suficiente stock. Disponibles: {stock}")
                continue
            else:
                pagado = 0
                if pinmediato == 1:
                    if pedir_confirmacion(f"\n⚠️  '{nombre}' debería ser pagado en el momento. ¿Querés registrarlo como pagado? (si/no): ") == "si":
                        pagado = 1
                        print("✔ Se registrará el consumo como pagado.")
                    else:
                        print("\n⚠️  El consumo se registrará como pendiente de pago.")

                consumos_agregados.append({
                    "huesped_id": huesped["NUMERO"],
                    "codigo": codigo,
                    "nombre": nombre,
                    "cantidad": cantidad,
                    "pagado": pagado,
                    "stock_anterior": stock
                })
                print(f"\n✔ Se agregó a la lista: {cantidad} unidad(es) de '{nombre}'.")
                break
    if consumos_agregados:
        respuesta = pedir_confirmacion("\n¿Querés eliminar alguno de los consumos recién agregados? (si/no): ", defecto="no")
        if respuesta == "si":
            print("\nConsumos recién agregados:")
            for i, consumo in enumerate(consumos_agregados):
                print(f"  {i + 1}. Producto: {consumo['nombre']} (Cód: {consumo['codigo']}), Cantidad: {consumo['cantidad']}")

            a_eliminar_str = input("\nIngresá los items a eliminar (separados por comas o espacios), ó '0' para cancelar: ").strip()
            
            if a_eliminar_str != '0':
                indices_a_eliminar = set()
                partes = re.split(r'[,\s]+', a_eliminar_str)
                for parte in partes:
                    try:
                        indice = int(parte) - 1
                        if 0 <= indice < len(consumos_agregados):
                            indices_a_eliminar.add(indice)
                        else:
                            print(f"❌ El número {indice + 1} es inválido. Se ignorará.")
                    except ValueError:
                        print(f"❌ La entrada '{parte}' no es un número. Se ignorará.")

                if indices_a_eliminar:
                    for indice in sorted(list(indices_a_eliminar), reverse=True):
                        consumo_eliminado = consumos_agregados.pop(indice)
                        print(f"✔ Consumo de '{consumo_eliminado['nombre']}' eliminado.")

    # Finalmente, se guardan los consumos que quedaron en la lista
    if consumos_agregados:
        print("\n✔ Registrando consumos en la base de datos...")
        try:
            for consumo in consumos_agregados:
                fecha = datetime.now().isoformat(sep=" ", timespec="seconds")
                db.ejecutar("INSERT INTO CONSUMOS (HUESPED, PRODUCTO, CANTIDAD, FECHA, PAGADO) VALUES (?, ?, ?, ?, ?)",
                            (consumo['huesped_id'], consumo['codigo'], consumo['cantidad'], fecha, consumo['pagado']))
                
                if consumo['stock_anterior'] != -1:
                    nuevo_stock = consumo['stock_anterior'] - consumo['cantidad']
                    db.ejecutar("UPDATE PRODUCTOS SET STOCK = ? WHERE CODIGO = ?", (nuevo_stock, consumo['codigo']))
                    
                registro_anterior_data = db.obtener_uno("SELECT REGISTRO FROM HUESPEDES WHERE NUMERO = ?", (numero_huesped,))
                registro_anterior = str(registro_anterior_data["REGISTRO"] or "") if registro_anterior_data else ""
                separador = "\n---\n"
                registro_consumo = f"Consumo agregado: {consumo['nombre']} (x{consumo['cantidad']}) - {fecha}"
                if consumo['pagado'] == 1:
                    registro_consumo += " (PAGADO)"
                if registro_anterior.strip():
                    nuevo_registro = registro_anterior + separador + registro_consumo
                else:
                    nuevo_registro = registro_consumo
                editar_huesped_db(numero_huesped, {"REGISTRO": nuevo_registro})
            print(f"✔ Consumos agregados para {huesped['NOMBRE'].capitalize()} {huesped['APELLIDO'].capitalize()}, de la habitación {habitacion}:")
            for i, consumo in enumerate(consumos_agregados):
                print(f"  {i + 1}. Producto: {consumo['nombre'].capitalize()} (Cód: {consumo['codigo']}), Cantidad: {consumo['cantidad']}")
        except Exception as e:
            print(f"\n❌ Error al registrar consumos: {e}")
    else:
        print("\n❌ No se registraron nuevos consumos.")

    return

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
                producto_nombre = consumo["PRODUCTO"]
                cantidad = consumo["CANTIDAD"]
                precio = consumo["PRECIO"]
                fecha_display = formatear_fecha(fecha)
                item_total = cantidad * precio # Calcular el total por item
                grand_total += item_total # Acumular al total general
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
            consumo_id = consumo["NUMERO"]
            fecha = consumo["FECHA"]
            producto_id = consumo["PRODUCTO"]
            producto_nombre = consumo["PRODUCTO_NOMBRE"]
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
            print(f"\n❌ Error al eliminar consumos: {e}")
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

        numero_huesped = huesped["NUMERO"]
        query = """
            SELECT C.ID, C.FECHA, P.NOMBRE, C.CANTIDAD, P.PRECIO
            FROM CONSUMOS C
            JOIN PRODUCTOS P ON C.PRODUCTO = P.CODIGO
            WHERE C.HUESPED = ? AND C.PAGADO = 0
            ORDER BY C.FECHA DESC
        """
        consumos = db.obtener_todos(query, (numero_huesped,))
        if not consumos:
            # Verificar si hay consumos en total para ese huésped
            todos = db.obtener_todos("SELECT ID FROM CONSUMOS WHERE HUESPED = ?", (numero_huesped,))
            if not todos:
                print("✔ Esta habitación no tiene consumos registrados.")
            else:
                print("✔ Todos los consumos ya están marcados como pagados.")
            return

        print(f"\nConsumos pendientes de pago para {huesped['NOMBRE'].title()} {huesped['APELLIDO'].title()} (habitación {habitacion}):\n")
        print(f"{'#':<3} {'FECHA':<20} {'PRODUCTO':<25} {'CANT':<5} {'TOTAL':>10}")
        print("-" * 70)

        for idx, consumo in enumerate(consumos, start=1):
            cid = consumo["NUMERO"]
            fecha = consumo["FECHA"]
            producto = consumo["PRODUCTO"]
            cant = consumo["CANTIDAD"]
            precio = consumo["PRECIO"]
            total = cant * precio
            print(f"{idx:<3} {fecha:<20} {producto:<25} {cant:<5} {total:>10.2f}")

        seleccion = input("\nIngresá los números de los consumos a marcar como pagos separados por coma (ej: 1,3,4), ó (0) para cancelar: ").strip()
        if seleccion == "0":
            print("❌ Operación cancelada.")
            return

        indices = [s.strip() for s in seleccion.split(",") if s.strip().isdigit()]
        consumos_a_pagar = []
        for i in indices:
            idx = int(i)
            if 1 <= idx <= len(consumos):
                consumos_a_pagar.append(consumos[idx - 1]["ID"])  # ID del consumo
            else:
                print(f"❌ Índice fuera de rango: {idx}")

        if not consumos_a_pagar:
            print("❌ No se seleccionaron consumos válidos.")
            return
        try:
            for cid in consumos_a_pagar:
                db.ejecutar("UPDATE CONSUMOS SET PAGADO = 1 WHERE ID = ?", (cid,))
            print(f"\n✔ Se marcaron {len(consumos_a_pagar)} consumo(s) como pagados.")
        except Exception as e:
            print(f"\n❌ Error al registrar el pago: {e}")
            return

@usuarios.requiere_acceso(2)
def consumo_cortesia():
    cortesias_agregadas = []
    leyenda_cod = "\nIngresá el código del producto consumido, (*) para buscar ó (0) para finalizar: "
    while True:
        codigo = opcion_menu(leyenda_cod, cero=True, asterisco=True, minimo=1)
        if codigo == 0:
            break
        elif codigo == "*":
            productos = db.obtener_todos("SELECT * FROM PRODUCTOS WHERE STOCK > 0 OR STOCK = -1")
            if not productos:
                print("\n❌ No hay productos en stock.")
                continue
            else:
                imprimir_productos(productos)
                continue

        producto = db.obtener_uno("SELECT * FROM PRODUCTOS WHERE CODIGO = ?", (codigo,))
        if not producto:
            print("\n⚠️  Producto no encontrado.")
            continue

        nombre = producto["NOMBRE"]
        stock  = producto["STOCK"]
        print(f"\nProducto seleccionado: {nombre} (Stock: {'Infinito' if stock == -1 else stock})")

        while True:
            cantidad = pedir_entero("Ingresá la cantidad ó (0) para cancelar: ", minimo=0)
            if cantidad == 0:
                print("\n❌ Producto cancelado.")
                break
            elif stock != -1 and cantidad > stock:
                print(f"\n❌ No hay suficiente stock. Disponibles: {stock}")
                continue
            else:
                cortesias_agregadas.append({
                    "codigo": codigo,
                    "nombre": nombre,
                    "cantidad": cantidad,
                    "stock_anterior": stock
                })
                print(f"✔ Se agregó a la lista: {cantidad} unidad(es) de '{nombre}'.")
                break
    if cortesias_agregadas:
        respuesta = pedir_confirmacion("\n¿Querés eliminar alguno de las cortesías recién agregadas? (si/no): ")
        if respuesta == "si":
            print("\nCortesías recién agregadas:")
            for i, cortesia in enumerate(cortesias_agregadas):
                print(f"  {i + 1}. Producto: {cortesia['nombre']} (Cód: {cortesia['codigo']}), Cantidad: {cortesia['cantidad']}")

            a_eliminar_str = input("Ingresá los items a eliminar (separados por comas o espacios), ó '0' para cancelar: ").strip()
            
            if a_eliminar_str != '0':
                indices_a_eliminar = set()
                partes = re.split(r'[,\s]+', a_eliminar_str)
                for parte in partes:
                    try:
                        indice = int(parte) - 1
                        if 0 <= indice < len(cortesias_agregadas):
                            indices_a_eliminar.add(indice)
                        else:
                            print(f"❌ El número {indice + 1} es inválido. Se ignorará.")
                    except ValueError:
                        print(f"❌ La entrada '{parte}' no es un número. Se ignorará.")

                if indices_a_eliminar:
                    for indice in sorted(list(indices_a_eliminar), reverse=True):
                        cortesia_eliminada = cortesias_agregadas.pop(indice)
                        print(f"✔ Cortesía de '{cortesia_eliminada['nombre']}' eliminada.")
        if not cortesias_agregadas:
            print("\n❌ No quedaron cortesías para registrar.")
            return
    
        while True:
            respuesta_autoriza = input("Ingresá quién autoriza la cortesía ó (0) para cancelar: ").strip()
            if respuesta_autoriza == "0":
                print("\n❌ Registro de cortesía cancelado.")
                return
            if not respuesta_autoriza:
                print("\n⚠️  El nombre del autorizante no puede estar vacío.")
                continue
            autoriza_unidecode = unidecode(respuesta_autoriza)
            autoriza_limpio = autoriza_unidecode.replace('-', ' ').replace('_', ' ')
            autoriza = re.sub(r"[^a-zA-Z0-9\s]", "", autoriza_limpio).lower()
            if not autoriza.strip():
                print("\n⚠️  El nombre del autorizante no puede contener solo caracteres especiales o signos.")
                continue
            break

    # Finalmente, se guardan las cortesías que quedaron en la lista
    if cortesias_agregadas:
        print("\nRegistrando cortesía...")
        try:
            for cortesia in cortesias_agregadas:
                fecha = datetime.now().isoformat(sep=" ", timespec="seconds")
                db.ejecutar("INSERT INTO CORTESIAS (PRODUCTO, CANTIDAD, FECHA, AUTORIZA) VALUES (?, ?, ?, ?)",
                            (cortesia['codigo'], cortesia['cantidad'], fecha, autoriza))
                if cortesia['stock_anterior'] != -1:
                    nuevo_stock = cortesia['stock_anterior'] - cortesia['cantidad']
                    db.ejecutar("UPDATE PRODUCTOS SET STOCK = ? WHERE CODIGO = ?", (nuevo_stock, cortesia['codigo']))
                marca_tiempo = marca_de_tiempo()
                log = (
                    f"[{marca_tiempo}] CONSUMO DE CORTESÍA:\n"
                    f"Producto: {producto['NOMBRE']} (ID: {producto['CODIGO']}) | "
                    f"Cantidad: {cantidad} | "
                    f"Autorizado por: {autoriza.title()} | "
                    f"Registrado por: {usuarios.sesion.usuario}"
                )
                registrar_log("consumos_cortesia.log", log)
            print(f"\n✔ Cortesía autorizada por {autoriza.capitalize()} registrada correctamente.")
            for i, cortesia in enumerate(cortesias_agregadas):
                print(f"  {i + 1}. {cortesia['nombre'].capitalize()}, (x{cortesia['cantidad']})")
        except Exception as e:
            print(f"\n❌ Error al registrar la cortesía: {e}")
    else:
        print("\n❌ No se registraron nuevas cortesías.")

    return