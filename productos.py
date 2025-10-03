import re
import sqlite3
import usuarios
from db import db
from unidecode import unidecode
from utiles import pedir_precio, pedir_entero, pedir_confirmacion, imprimir_productos, imprimir_producto, marca_de_tiempo, registrar_log, opcion_menu, pedir_grupo

LISTA_BLANCA_PRODUCTOS = [
    "CODIGO",
    "NOMBRE",
    "PRECIO",
    "STOCK",
    "ALERTA",
    "PINMEDIATO"
]

@usuarios.requiere_acceso(1)
def nuevo_producto():
    codigo = None
    leyenda = "\nIngresá el código de producto, deje vacio para autogenerar, ó (0) para cancelar : "
    while codigo is None:
        respuesta_codigo = opcion_menu(leyenda, cero=True, vacio=True, minimo=1)

        if respuesta_codigo == 0:
            return #Cancelado
        # --- A. Autogenerar (Si está vacío) ---
        if respuesta_codigo is None:
            ultimo = db.obtener_uno("SELECT MAX(CODIGO) FROM PRODUCTOS")
            codigo = (ultimo["MAX(CODIGO)"] or 0) + 1
            # Nota: Aquí falta la validación de duplicado por autogeneración, 
            # pero el código ya lo hace en el bloque 'else' original.
        
        # --- B. Código Ingresado (Es un entero > 0) ---
        elif isinstance(respuesta_codigo, int):
            # opcion_menu garantiza que es un entero >= 1.
            # No hay necesidad de try/except si opcion_menu hace su trabajo.
            codigo = respuesta_codigo
            
            # ⚠️ Opcional: Validar si el código ya existe
            existe = db.obtener_uno("SELECT 1 FROM PRODUCTOS WHERE CODIGO = ?", (codigo,))
            if existe:
                print(f"\n⚠️ El código {codigo} ya está en uso. Elija otro.")
                codigo = None # Reinicia el bucle forzando a 'codigo' a ser None
                continue
        break # Exit the loop after finding a valid code

    # Nombre del producto
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
        
    precio = pedir_precio("Ingresá el precio del producto: ")
    stock = pedir_entero("Ingresá el stock inicial: (-1 = infinito): ", minimo = -1)
    alerta = pedir_entero("Ingresá el nivel de alerta de stock ó deje vacío para usar el valor por defecto (5): ", minimo=1, defecto=5)
    grupo = pedir_grupo()
    if grupo is False:
        # Si pedir_grupo() devolvió False, no intentamos la inserción
        return
    respuesta_pago_inmediato = pedir_confirmacion("¿El producto se debe pagar en el momento? (si/no): ", defecto="no")
    pago_inmediato = 0 if respuesta_pago_inmediato != "si" else 1
    
    _guardar_producto_y_notificar(codigo, nombre, precio, stock, alerta, grupo, pago_inmediato)     
    
    return

def _guardar_producto_y_notificar(codigo, nombre, precio, stock, alerta, grupo, pago_inmediato):
    #Intenta insertar el producto en la base de datos y notifica el resultado.

    data = {
        "codigo": codigo, 
        "nombre": nombre, 
        "precio": precio, 
        "stock": stock, 
        "pinmediato": pago_inmediato, 
        "alerta": alerta, 
        "grupo": grupo
    }
    
    try:
        with db.transaccion():
            sql = """INSERT INTO PRODUCTOS (CODIGO, NOMBRE, PRECIO, STOCK, ALERTA, PINMEDIATO, GRUPO)
                     VALUES (?, ?, ?, ?, ?, ?, ?)"""
            db.ejecutar(sql, (data["codigo"], data["nombre"], data["precio"], data["stock"], data["alerta"], data["pinmediato"], data["grupo"]))
            
        print(f'\n✔ Producto "{nombre.capitalize()}" registrado correctamente con codigo {codigo}.')

        # Lógica de notificación de grupo (si la inserción fue exitosa)
        if grupo is not None:
            sql_productos_grupo = """
                SELECT NOMBRE FROM PRODUCTOS 
                WHERE GRUPO = ? AND CODIGO != ?
            """
            productos_registros = db.obtener_todos(sql_productos_grupo, (grupo, codigo))
            productos_del_grupo = [registro['NOMBRE'] for registro in productos_registros]

            if productos_del_grupo:
                productos_str = ", ".join(productos_del_grupo)
                print(f"\n🏷️ Grupo: {grupo.capitalize()}")
                print(f"📦 Productos del Grupo: {productos_str}")
            else:
                print(f"🏷️ Este es el primer producto registrado en el grupo {grupo.capitalize()}.")
                
    except sqlite3.IntegrityError:
        print(f"❌ Ya existe un producto con el código {codigo}.")
    except Exception as e:
        print(f"❌ Error al registrar el producto: {e}")

@usuarios.requiere_acceso(0)
def listado_productos():
    leyenda = "\n¿Cómo querés ordenar los productos? Por código (1), por nombre (2) ó cancelar (0): "
    while True:
        opcion = opcion_menu(leyenda, cero=True, minimo=1, maximo=2)
        if opcion == 0:
            return
        elif opcion == 1:
            orden = "CODIGO"
            break
        elif opcion == 2:
            orden = "NOMBRE"
            break
        
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

    # 3. Mostrar resultados
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

@usuarios.requiere_acceso(2)
def editar_producto():
    # Coordina el proceso de edición de un producto.
    producto = _seleccionar_producto_a_editar()
    if not producto:
        print("\n❌ Operación cancelada.")
        return

    # Diccionario de Despacho: mapea opciones a funciones
    manejadores = {
        1: _editar_codigo,
        2: _editar_nombre,
        3: _editar_precio,
        4: _editar_stock,
        5: _editar_alerta,
        6: _editar_pinmediato,
        7: _editar_grupo
    }

    leyenda = "\n¿Querés editar (1) el código, (2) nombre, (3) precio, (4) stock, (5) alerta de stock, (6) pago inmediato, (7) grupo ó cancelar (0)?: "

    while True:
        opcion = opcion_menu(leyenda, cero=True, minimo=1, maximo=7)
        if opcion == 0:
            print("\n❌ Edición cancelada.")
            break
        
        manejador = manejadores.get(opcion)
        if manejador:
            manejador(producto)
            break # Termina después de una edición exitosa
        # El else para opción inválida ya lo maneja 'opcion_menu' o el bucle.

def _seleccionar_producto_a_editar():
    # Busca y selecciona un producto para editar.
    # Devuelve el diccionario del producto o None si se cancela.
    
    leyenda = "\nIngresá el código del producto a editar, (*) para ver listado ó (0) para cancelar: "
    while True:
        codigo = opcion_menu(leyenda, cero=True, asterisco=True, minimo=1)
        if codigo == 0:
            return None
        if codigo == "*":
            listado_productos()
            continue

        producto = db.obtener_uno("SELECT * FROM PRODUCTOS WHERE CODIGO = ?", (codigo,))
        if producto:
            imprimir_producto(producto)
            return producto
        else:
            print("\n⚠️  Producto no encontrado.")

def _editar_codigo(producto):
    # Manejador para la edición del código del producto."""
    leyenda = "\nIngresá el nuevo código (deje vacío para autogenerar): "
    while True:
        nuevo_codigo = opcion_menu(leyenda, vacio=True, minimo=1) # Permite input de texto     
        if nuevo_codigo is not None: # Si el usuario ingresó un código manualmente
            if nuevo_codigo != producto["CODIGO"]: #Y es distinto al original
                existe = db.obtener_uno("SELECT 1 FROM PRODUCTOS WHERE CODIGO = ?", (nuevo_codigo,))
                #Y ya existe
                if existe:
                    print(f"\n⚠️ El código {nuevo_codigo} ya está en uso. Elija otro.")
                    continue
            else:
                print("\n⚠️ El nuevo código es igual al original. No se realizarán cambios.")
                return
            # Si es distinto al original y no existe
            break
        else: # Si se dejó vacío para autogenerar
            ultimo = db.obtener_uno("SELECT MAX(CODIGO) FROM PRODUCTOS")
            nuevo_codigo = (ultimo["MAX(CODIGO)"] or 0) + 1
            while db.obtener_uno("SELECT 1 FROM PRODUCTOS WHERE CODIGO = ?", (nuevo_codigo,)):
                nuevo_codigo += 1
            break
    _actualizar_y_registrar_log(producto, "CODIGO", nuevo_codigo)

def _editar_nombre(producto):
    # Manejador para la edición del nombre del producto.
    while True:
        nuevo_nombre_raw = input("Ingresá el nuevo nombre: ").strip()
        if not nuevo_nombre_raw:
            print("\n⚠️ El nombre no puede estar vacío.")
            continue
        
        nombre_limpio = unidecode(nuevo_nombre_raw).replace('-', ' ').replace('_', ' ')
        nuevo_nombre = re.sub(r"[^a-zA-Z0-9\s/]", "", nombre_limpio).lower()
        
        if not nuevo_nombre.strip():
            print("\n⚠️ El nombre del producto no puede contener solo caracteres especiales.")
            continue
        
        _actualizar_y_registrar_log(producto, "NOMBRE", nuevo_nombre)
        break

def _editar_precio(producto):
    #Manejador para la edición del precio del producto.
    nuevo_precio = pedir_precio("Ingresá el nuevo precio: ")
    _actualizar_y_registrar_log(producto, "PRECIO", nuevo_precio)

def _editar_stock(producto):
    # Manejador para la edición del stock del producto.
    if pedir_confirmacion("¿Desea stock infinito? si/no: ") == "si":
        nuevo_stock = -1
    else:
        nuevo_stock = pedir_entero("Ingresá el nuevo stock: ", minimo=0)
    _actualizar_y_registrar_log(producto, "STOCK", nuevo_stock)

def _editar_alerta(producto):
    # Manejador para la edición de la alerta de stock.
    nueva_alerta = pedir_entero("Ingresá el nuevo nivel de alerta de stock: ", minimo=1)
    _actualizar_y_registrar_log(producto, "ALERTA", nueva_alerta)

def _editar_pinmediato(producto):
    # Manejador para la edición del pago inmediato.
    nuevo_pinmediato = pedir_confirmacion(f"¿Querés que el producto {producto["NOMBRE"]} tenga pago inmediato? : ", defecto = "no").upper
    _actualizar_y_registrar_log(producto, "PINMEDIATO", nuevo_pinmediato)

def _editar_grupo(producto):
    # 1. Obtener la nueva información del grupo
    nuevo_grupo = pedir_grupo()
    
    # 2. Verificar si la operación no fue cancelada
    # Solo si el resultado NO es False (cancelación), procede a actualizar.
    if nuevo_grupo is not False:
        _actualizar_y_registrar_log(producto, "GRUPO", nuevo_grupo)
        # Opcional: Podrías añadir un mensaje de éxito/fracaso aquí
    else:
        # El caso donde nuevo_grupo es False (cancelación)
        print("Edición del grupo cancelada. No se realizaron cambios.")

def _actualizar_y_registrar_log(producto_original, campo, nuevo_valor):
    # Función centralizada que actualiza la BD y registra el cambio en el log.

    codigo_original = producto_original["CODIGO"]
    try:
        with db.transaccion():
            _actualizar_producto_db(db, codigo_original, campo, nuevo_valor)

            log = (
                f"[{marca_de_tiempo()}] PRODUCTO EDITADO por {usuarios.sesion.usuario}:\n"
                f"Estado anterior -> Código: {producto_original['CODIGO']}, Nombre: {producto_original['NOMBRE']}, "
                f"Precio: {producto_original['PRECIO']}, Stock: {producto_original['STOCK']}, "
                f"Alerta: {producto_original['ALERTA']}\n, P.Inmediato: {producto_original['PINMEDIATO']}"
                f"  Campo modificado -> \"{campo}\": {nuevo_valor}"
            )
            registrar_log("productos_editados.log", log)
        print(f"\n✔ {campo.capitalize()} actualizado correctamente.")
        return True
    except sqlite3.IntegrityError:
        print(f"\n❌ No se puede actualizar el {campo.lower()}: tiene consumos o cortesías asociadas.")
    except Exception as e:
        print(f"\n❌ Error al actualizar el {campo.lower()}: {e}")
    return False

def _actualizar_producto_db(database, codigo, campo, valor):
    # 1. Validación de la Lista Blanca (El parche de seguridad)
    if campo not in LISTA_BLANCA_PRODUCTOS:
        print(f"\n❌ ERROR de seguridad: El campo '{campo}' no está permitido para ser actualizado.")
        return False
    # 2. Ejecución Segura
    try:
        # La consulta es segura porque:
        # a) El nombre del campo ({campo}) ha sido validado contra la lista blanca.
        # b) El valor (?) se pasa como parámetro, evitando inyección en el valor.
        sql = f"UPDATE PRODUCTOS SET {campo} = ? WHERE CODIGO = ?"
        database.ejecutar(sql, (valor, codigo))
        print(f"\n✔ Campo '{campo}' del producto {codigo} actualizado correctamente.")
        return True
        
    except sqlite3.IntegrityError:
        # Captura errores si, por ejemplo, intentas usar un 'CODIGO' que ya existe.
        print(f"\n❌ Error de integridad: El valor '{valor}' para el campo '{campo}' ya existe o es inválido.")
        return False
    except Exception as e:
        print(f"\n❌ Error al actualizar el producto {codigo}: {e}")
        return False

@usuarios.requiere_acceso(2)
def eliminar_producto():
    leyenda = "\nIngresá el código del producto que querés eliminar, ingrese (*) para ver el listado ó ingrese (0) para cancelar: "
    while True:
        codigo = opcion_menu(leyenda, cero=True, asterisco=True, minimo=1)
        if codigo == "*":
            listado_productos()
            continue
        if codigo == 0:
            print("\n❌ Eliminación cancelada.")
            return
        
        try:
            producto = db.obtener_uno("SELECT CODIGO, NOMBRE, PRECIO, STOCK, ALERTA FROM PRODUCTOS WHERE CODIGO = ?", (codigo,))
            if not producto:
                print("\n⚠️  Producto no encontrado.")
                continue

            print("Producto seleccionado: ")
            imprimir_producto(producto)

            confirmacion = pedir_confirmacion("\n⚠️¿Está seguro que querés eliminar este producto? (si/no): ")
            if confirmacion == "si":
                try:
                    with db.transaccion():
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