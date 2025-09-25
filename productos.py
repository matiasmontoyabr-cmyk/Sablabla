import re
import sqlite3
import usuarios
from db import db
from unidecode import unidecode
from utiles import pedir_precio, pedir_entero, pedir_confirmacion, imprimir_productos, imprimir_producto, marca_de_tiempo, registrar_log

@usuarios.requiere_acceso(1)
def nuevo_producto():
    while True:
        respuesta_codigo = input("\nIngrese el código de producto, deje vacio para autogenerar, ó (0) para cancelar : ")
        try:
            if respuesta_codigo == "0":
                return
            if respuesta_codigo:
                if not respuesta_codigo.isdigit():
                    print("\n⚠️  El código debe ser un número positivo.")
                    continue
                codigo = int(respuesta_codigo)
            else:
                ultimo = db.obtener_uno("SELECT MAX(CODIGO) FROM PRODUCTOS")
                codigo = (ultimo["MAX(CODIGO)"] or 0) + 1
            break # Exit the loop after finding a valid code
        except Exception as e:
            print(f"❌ Error al procesar el código: {e}")
            continue

    while True:
        respuesta_nombre = input("Escriba el nombre del producto ó (0) para cancelar: ").strip()
        if respuesta_nombre == "0":
            return
        if not respuesta_nombre:
            print("\n⚠️  Para el nombre de un producto debe ingresar al menos una palabra:")
            continue
        nombre_unidecode = unidecode(respuesta_nombre)
        nombre_limpio = nombre_unidecode.replace('-', ' ').replace('_', ' ')
        nombre = re.sub(r"[^a-zA-Z0-9\s]", "", nombre_limpio).lower()
        if not nombre.strip():
            print("\n⚠️  El nombre del producto no puede contener solo caracteres especiales o signos.")
            continue
        break
        
    precio = pedir_precio("Ingrese el precio del producto: ")
    stock = pedir_entero("Ingrese el stock inicial: (-1 = infinito): ", minimo = -1)
    alerta = pedir_entero("Ingrese el nivel de alerta de stock ó deje vacío para usar el valor por defecto (5): ", minimo=1, defecto=5)
    respuesta_pago_inmediato = pedir_confirmacion("¿El producto se debe pagar en el momento? (si/no): ", defecto="no")
    pago_inmediato = 0 if respuesta_pago_inmediato != "si" else 1
    
    try:
        data = {"codigo": codigo, "nombre": nombre, "precio": precio, "stock": stock, "pinmediato": pago_inmediato, "alerta": alerta}
        # We'll try to insert the product
        # and let the database tell us if it already exists.
        sql = "INSERT INTO PRODUCTOS (CODIGO, NOMBRE, PRECIO, STOCK, ALERTA, PINMEDIATO) VALUES (?, ?, ?, ?, ?, ?)"
        db.ejecutar(sql, (data["codigo"], data["nombre"], data["precio"], data["stock"], data["alerta"], data["pinmediato"]))
        print(f'\n✔ Producto "{nombre.capitalize()}" registrado correctamente con codigo {codigo}.')
    except sqlite3.IntegrityError:
        print(f"❌ Ya existe un producto con el código {codigo}.")
    except Exception as e:
        print(f"❌ Error al registrar el producto: {e}")     
    return

@usuarios.requiere_acceso(0)
def listado_productos():
    while True:
        opcion = input("\n¿Cómo desea ordenar los productos? Por código (1), por nombre (2) ó cancelar (0): ").strip()
        if opcion == "0":
            return
        elif opcion == "1":
            orden = "CODIGO"
            break
        elif opcion == "2":
            orden = "NOMBRE"
            break
        else:
            print("\n⚠️  Opción inválida. Intente nuevamente.")
        
    try:
        productos = db.obtener_todos(f"SELECT CODIGO, NOMBRE, PRECIO, STOCK, ALERTA FROM PRODUCTOS ORDER BY {orden}")
        if not productos:
            print("\n❌ No hay productos registrados.")
            return
        else:        
            imprimir_productos(productos)
            return
    except Exception as e:
        print(f"\n❌ Error al obtener el listado de productos: {e}")
        return

@usuarios.requiere_acceso(0)
def buscar_producto_b():
    while True:
        criterio = input("\nIngrese el nombre o código del producto, (*) para ver todos, ó (0) para cancelar: ").strip()
        if not criterio:
            print("\n⚠️  Debe ingresar al menos un número o una palabra para buscar.")
            continue
        elif criterio == "0":
            return
        elif criterio == "*":
            productos = db.obtener_todos("SELECT CODIGO, NOMBRE, PRECIO, STOCK, ALERTA FROM PRODUCTOS")
            if not productos:
                print("\n❌ No hay productos registrados.")
                return
            imprimir_productos(productos)
            return
        elif criterio.isdigit():
            codigo = int(criterio)
            query = "SELECT CODIGO, NOMBRE, PRECIO, STOCK, ALERTA FROM PRODUCTOS WHERE CODIGO = ?"
            producto = db.obtener_uno(query, (codigo,))
            if not producto:
                print("\n⚠️  No se encontró un producto con ese código.")
                continue
            else:
                imprimir_producto(producto)
                return
        else:
            try:
                criterio_limpio = re.sub(r"[^a-zA-Z0-9\s/]", "", unidecode(criterio).lower().replace('-', ' ').replace('_', ' ').replace('/', ' '))
                criterios = criterio_limpio.split()
                if not criterios:
                    print("\n⚠️  Debe ingresar al menos una palabra")
                    continue
                else:
                    where_clauses = ["LOWER(NOMBRE) LIKE ?"] * len(criterios)
                    params = [f"%{palabra}%" for palabra in criterios]

                    query = f"SELECT CODIGO, NOMBRE, PRECIO, STOCK, ALERTA FROM PRODUCTOS WHERE {' OR '.join(where_clauses)}"
                    productos = db.obtener_todos(query, params)

                    # Ordenar por relevancia (cantidad de palabras que coinciden en el nombre)
                    resultados = [(prod, sum(1 for palabra in criterios if palabra in prod["NOMBRE"].lower())) for prod in productos]
                    resultados.sort(key=lambda x: x[1], reverse=True)

                    if resultados:
                        print(f"\nResultados para: '{criterio}'\n")
                        productos_ordenados = [p for p, _ in resultados]
                        imprimir_productos(productos_ordenados)
                        return
                    else:
                        print("\n❌ No se encontraron productos que coincidan con la búsqueda.")
                        return
            except Exception as e:
                # Si algo sale mal, imprime el error y sigue el programa
                print(f"\n❌ Error al realizar la búsqueda: {e}")

@usuarios.requiere_acceso(0)
def buscar_producto():
    opcion = None
    while True:
        entrada = input("\nIngresá el nombre o código del producto, (*) para ver todos, ó (0) para cancelar: ").strip()
        
        if not entrada:
            print("\n⚠️  Tenés que ingresar al menos un número o una palabra para buscar.")
            continue

        if entrada == "0":
            print("❌ Búsqueda cancelada.")
            return
        
        if not entrada.isdigit() and entrada != '*':
            # Aplicamos la misma lógica de limpieza que usaríamos para la búsqueda por nombre
            criterio_limpio = re.sub(r"[^a-zA-Z0-9\s/]", "", unidecode(entrada).lower().replace('-', ' ').replace('_', ' ').replace('/', ' '))
            
            # Si después de limpiar y dividir, la lista de palabras queda vacía
            if not criterio_limpio.split():
                 print("\n⚠️ El texto ingresado solo contenía caracteres inválidos. Intentá de nuevo.")
                 continue # Vuelve al inicio del bucle

        opcion = entrada
        break

    if opcion == "*":
        productos = db.obtener_todos("SELECT CODIGO, NOMBRE, PRECIO, STOCK, ALERTA FROM PRODUCTOS")
        if not productos:
            print("\n❌ No hay productos registrados.")
            return
        imprimir_productos(productos)
        return

    # Búsqueda por código (más directa)
    elif opcion.isdigit():
        codigo = int(opcion)
        # Ejecutamos la búsqueda específica
        producto = _ejecutar_busqueda("codigo", codigo) 

        if producto:
            imprimir_producto(producto)
            return
        else:
            print("\n⚠️  No se encontró un producto con ese código.")
            return

    # Búsqueda por nombre (más flexible)
    else:
        criterio_limpio = re.sub(r"[^a-zA-Z0-9\s/]", "", unidecode(opcion).lower().replace('-', ' ').replace('_', ' ').replace('/', ' '))
        criterios = criterio_limpio.split()
        resultados = _ejecutar_busqueda("nombre", criterios)

    # 3. Mostrar resultados y decidir si continuar
    if resultados:
        imprimir_productos(resultados)
        return
    else:
        print("\n❌ No se encontraron productos que coincidan con la búsqueda.")
        return

def _ejecutar_busqueda(criterio, valor):
    #Genera y ejecuta la consulta SQL basada en el criterio dado."""
    
    if criterio == "codigo":
        query = "SELECT CODIGO, NOMBRE, PRECIO, STOCK, ALERTA FROM PRODUCTOS WHERE CODIGO = ?"
        # Como el código es único, obtener solo uno es más eficiente
        return db.obtener_uno(query, (valor,))

    elif criterio == "nombre":
        where_clauses = ["LOWER(NOMBRE) LIKE ?"] * len(valor)
        params = [f"%{palabra}%" for palabra in valor]
        
        # Usar LIKE para búsquedas parciales (añadir comodines % manualmente)
        query = f"SELECT CODIGO, NOMBRE, PRECIO, STOCK, ALERTA FROM PRODUCTOS WHERE {' OR '.join(where_clauses)} ORDER BY NOMBRE"
        productos = db.obtener_todos(query, params)

        if productos:
            resultados = [(prod, sum(1 for palabra in valor if palabra in prod["NOMBRE"].lower())) for prod in productos]
            resultados.sort(key=lambda x: x[1], reverse=True)
            productos_ordenados = [prod_score[0] for prod_score in resultados]
            return productos_ordenados
        else:
            return [] # Si el criterio no es reconocido, devuelve una lista vacía

def actualizar_producto_db(database, codigo, campo, valor):
    database.ejecutar(f"UPDATE PRODUCTOS SET {campo} = ? WHERE CODIGO = ?", (valor, codigo))

@usuarios.requiere_acceso(2)
def editar_producto():
    while True:
        codigo = input("\nIngrese el código del producto que desea editar, ingrese (*) para ver el listado ó ingrese (0) para cancelar: ").strip()
        if codigo == "*":
            listado_productos()
            continue
        if codigo == "0":
            return
        if not codigo.isdigit():
            print("\n❌ Código inválido.")
            continue

        codigo_original = int(codigo)
        producto = db.obtener_uno("SELECT * FROM PRODUCTOS WHERE CODIGO = ?", (codigo_original,))
        if not producto:
            print("\n⚠️  Producto no encontrado.")
            continue
        estado_anterior = {
            "CODIGO": producto["CODIGO"],
            "NOMBRE": producto["NOMBRE"],
            "PRECIO": producto["PRECIO"],
            "STOCK": producto["STOCK"],
            "ALERTA": producto["ALERTA"]
        }

        imprimir_producto(producto)
        break

    while True:
        opcion = input("\n¿Desea editar el código (1), nombre (2), el precio (3), stock (4), alerta de stock (5) ó cancelar (0)? ").strip()
        if opcion == "0":
            return
        if opcion == "1":
            while True:
                respuesta_codigo = input("\nIngrese el nuevo código del producto (deje vacío para autogenerar): ").strip()
                if respuesta_codigo:
                    if not respuesta_codigo.isdigit():
                        print("\n⚠️  El código debe ser un número positivo.")
                        continue
                    nuevo_codigo = int(respuesta_codigo)
                    if nuevo_codigo != codigo_original:
                        existe = db.obtener_uno("SELECT 1 FROM PRODUCTOS WHERE CODIGO = ?", (nuevo_codigo,))
                        if existe:
                            print(f"\n⚠️  El código {nuevo_codigo} ya está en uso. Elija otro.")
                            continue
                    codigo = nuevo_codigo
                    break
                else:
                    ultimo = db.obtener_uno("SELECT MAX(CODIGO) FROM PRODUCTOS")
                    nuevo_codigo = (ultimo["MAX(CODIGO)"] or 0) + 1
                    while db.obtener_uno("SELECT 1 FROM PRODUCTOS WHERE CODIGO = ?", (nuevo_codigo,)):
                        nuevo_codigo += 1
                    codigo = nuevo_codigo
                    break
            try:
                actualizar_producto_db(db, codigo_original, "CODIGO", codigo)
                marca_tiempo = marca_de_tiempo()
                log = (
                    f"[{marca_tiempo}] PRODUCTO EDITADO por {usuarios.sesion.usuario}:\n"
                    f"Estado anterior -> Código: {estado_anterior['CODIGO']}, "
                    f"Nombre: {estado_anterior['NOMBRE']}, "
                    f"Precio: {estado_anterior['PRECIO']}, "
                    f"Stock: {estado_anterior['STOCK']}, "
                    f"Alerta: {estado_anterior['ALERTA']}\n"
                    f"Campo modificado -> \"CODIGO\": {nuevo_codigo}"
                )
                registrar_log("productos_editados.log", log)
                print(f"\n✔ Código actualizado de {codigo_original} a {codigo}.")
            except Exception as e:
                print(f"\n❌ Error al actualizar el código: {e}")
            return
        if opcion == "2":
            while True:
                respuesta_nombre = input("Ingrese el nuevo nombre: ").strip()
                if len(respuesta_nombre) < 1:
                    print("\n⚠️  El nombre no puede estar vacío.")
                    continue
                nombre_unidecode = unidecode(respuesta_nombre)
                nombre_limpio = nombre_unidecode.replace('-', ' ').replace('_', ' ')
                nombre = re.sub(r"[^a-zA-Z0-9\s/]", "", nombre_limpio).lower()
                if not nombre.strip(): # Verifica que el nombre no quede vacío después de la limpieza
                    print("\n⚠️  El nombre del producto no puede contener solo caracteres o signos.")
                    continue
                try:
                    actualizar_producto_db(db, codigo, "NOMBRE", nombre)
                    marca_tiempo = marca_de_tiempo()
                    log = (
                        f"[{marca_tiempo}] PRODUCTO EDITADO por {usuarios.sesion.usuario}:\n"
                        f"Estado anterior -> Código: {estado_anterior['CODIGO']}, "
                        f"Nombre: {estado_anterior['NOMBRE']}, "
                        f"Precio: {estado_anterior['PRECIO']}, "
                        f"Stock: {estado_anterior['STOCK']}, "
                        f"Alerta: {estado_anterior['ALERTA']}\n"
                        f"Campo modificado -> \"NOMBRE\": {nombre}"
                    )
                    registrar_log("productos_editados.log", log)
                    print("\n✔ Nombre actualizado.")
                except Exception as e:
                    print(f"\n❌ Error al actualizar el nombre: {e}")
                return
        elif opcion == "3":
            respuesta_precio = pedir_precio("Ingrese el nuevo precio: ")
            try:
                actualizar_producto_db(db, codigo, "PRECIO", respuesta_precio)
                marca_tiempo = marca_de_tiempo()
                log = (
                    f"[{marca_tiempo}] PRODUCTO EDITADO por {usuarios.sesion.usuario}:\n"
                    f"Estado anterior -> Código: {estado_anterior['CODIGO']}, "
                    f"Nombre: {estado_anterior['NOMBRE']}, "
                    f"Precio: {estado_anterior['PRECIO']}, "
                    f"Stock: {estado_anterior['STOCK']}, "
                    f"Alerta: {estado_anterior['ALERTA']}\n"
                    f"Campo modificado -> \"PRECIO\": {respuesta_precio}"
                )
                registrar_log("productos_editados.log", log)
                print("\n✔ Precio actualizado.")
            except Exception as e:
                print(f"❌ Error al actualizar el precio: {e}")
            return
        elif opcion == "4":
            if pedir_confirmacion("¿Desea stock infinito? si/no: ") == "si":
                stock = -1
            else:
                stock = pedir_entero("Ingrese el nuevo stock: ", minimo=0)
            try:
                actualizar_producto_db(db, codigo, "STOCK", stock)
                marca_tiempo = marca_de_tiempo()
                log = (
                    f"[{marca_tiempo}] PRODUCTO EDITADO por {usuarios.sesion.usuario}:\n"
                    f"Estado anterior -> Código: {estado_anterior['CODIGO']}, "
                    f"Nombre: {estado_anterior['NOMBRE']}, "
                    f"Precio: {estado_anterior['PRECIO']}, "
                    f"Stock: {estado_anterior['STOCK']}, "
                    f"Alerta: {estado_anterior['ALERTA']}\n"
                    f"Campo modificado -> \"STOCK\": {stock}"
                )
                registrar_log("productos_editados.log", log)
                print("\n✔ Stock actualizado.")
            except sqlite3.IntegrityError:
                print("\n❌ No se puede actualizar el stock: tiene consumos o cortesías asociadas.")
            except Exception as e:
                print(f"\n❌ Error al actualizar el stock: {e}")
            return
        elif opcion == "5":
            while True:
                alerta = pedir_entero("Ingrese el nuevo nivel de alerta de stock: ", minimo=1)
                try:
                    actualizar_producto_db(db, codigo, "ALERTA", alerta)
                    marca_tiempo = marca_de_tiempo()
                    log = (
                        f"[{marca_tiempo}] PRODUCTO EDITADO por {usuarios.sesion.usuario}:\n"
                        f"Estado anterior -> Código: {estado_anterior['CODIGO']}, "
                        f"Nombre: {estado_anterior['NOMBRE']}, "
                        f"Precio: {estado_anterior['PRECIO']}, "
                        f"Stock: {estado_anterior['STOCK']}, "
                        f"Alerta: {estado_anterior['ALERTA']}\n"
                        f"Campo modificado -> \"ALERTA\": {alerta}"
                    )
                    registrar_log("productos_editados.log", log)
                    print("\n✔ Alerta de stock actualizada.")
                except Exception as e:
                    print(f"\n❌ Error al actualizar la alerta de stock: {e}")
                return
        else:
            print("\n⚠️  Opción inválida.")

@usuarios.requiere_acceso(2)
def eliminar_producto():
    while True:
        codigo = input("\nIngrese el código del producto que desea eliminar, ingrese (*) para ver el listado ó ingrese (0) para cancelar: ").strip()
        if codigo == "*":
            listado_productos()
            continue
        if codigo == "0":
            print("\n❌ Eliminación cancelada.")
            return
        
        try:
            if not codigo.isdigit():
                print("\n⚠️  Código inválido.")
                continue

            codigo = int(codigo)

            producto = db.obtener_uno("SELECT CODIGO, NOMBRE, PRECIO, STOCK, ALERTA FROM PRODUCTOS WHERE CODIGO = ?", (codigo,))
            if not producto:
                print("\n⚠️  Producto no encontrado.")
                continue

            print("Producto seleccionado: ")
            imprimir_producto(producto)

            confirmacion = pedir_confirmacion("\n⚠️¿Está seguro que desea eliminar este producto? (si/no): ")
            if confirmacion == "si":
                try:
                    db.ejecutar("DELETE FROM PRODUCTOS WHERE CODIGO = ?", (codigo,))
                    marca_tiempo = marca_de_tiempo()
                    log = (
                        f"[{marca_tiempo}] PRODUCTO ELIMINADO por {usuarios.sesion.usuario}:\n"
                        f"Código: {producto['CODIGO']} | "
                        f"Nombre: {producto['NOMBRE']} | "
                        f"Precio: {producto['PRECIO']} | "
                        f"Stock: {producto['STOCK']}"
                    )
                    registrar_log("productos_eliminados.log", log)
                    print("\n✔ Producto eliminado.")
                    return
                except sqlite3.IntegrityError:
                    print(f"\n❌ No se puede eliminar el producto {codigo}: tiene consumos o cortesías asociadas.")
                    return
                except Exception as e:
                    print(f"\n❌ Ocurrió un error inesperado al eliminar el producto: {e}")
                    return
            else:
                print("\n❌ Eliminación cancelada.")
                return
        except Exception as e:
            print(f"\n❌ Ocurrió un error inesperado al procesar la solicitud: {e}")
            continue # Volvemos al inicio del bucle si hay un error