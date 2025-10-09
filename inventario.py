import re
import unidecode
import usuarios
from db import db
from productos import _ejecutar_busqueda
from utiles import imprimir_productos, pedir_entero, registrar_log, marca_de_tiempo, opcion_menu, pedir_confirmacion

@usuarios.requiere_acceso(1)
def abrir_inventario():
    productos = db.obtener_todos("SELECT CODIGO, NOMBRE, STOCK FROM PRODUCTOS ORDER BY NOMBRE")
    if not productos:
        print("❌ No hay productos cargados.")
        return

    print("\n📦 Inventario actual:")
    print(f"{'CÓDIGO':<7} {'NOMBRE':<30} {'STOCK':<10}")
    print("-" * 50)
    for producto in productos:
        codigo = producto["CODIGO"]
        nombre = producto["NOMBRE"]
        stock = producto["STOCK"]
        print(f"{codigo:<7} {nombre:<30} {stock:<10}")
    
    return

@usuarios.requiere_acceso(1)
def ingresar_compra():
    producto = _seleccionar_producto("comprado")
    if not producto:
        return  # Cancelado

    codigo = producto["CODIGO"]
    nombre = producto["NOMBRE"].title()
    stock  = producto["STOCK"]
    grupo = producto.get("GRUPO")
    if grupo:
        grupo = grupo.title()

    cantidad = pedir_entero(f"Ingresá la cantidad comprada de '{nombre}' ó (0) para cancelar: ", minimo=0)
    
    if cantidad == 0:
        print("\n❌ Compra cancelada por cantidad cero.")
        return # Salir de la función
    
    if grupo:
        # Si tiene grupo: la actualización será masiva
        update_query = "UPDATE PRODUCTOS SET STOCK = STOCK + ? WHERE GRUPO = ?"
        params = (cantidad, grupo)
        # Mensajes para el usuario y el log
        mensaje_impresion = f"el stock de TODOS los productos del grupo '{grupo}'"
        log_info = f"Grupo: '{grupo}'. Stock anterior del producto ({nombre}): {stock}"
        nuevo_stock = stock + cantidad
    else:
        # Si no tiene grupo: la actualización es solo para este producto
        nuevo_stock = stock + cantidad
        update_query = "UPDATE PRODUCTOS SET STOCK = ? WHERE CODIGO = ?"
        params = (nuevo_stock, codigo)
        # Mensajes para el usuario y el log
        mensaje_impresion = f"el stock de \"{nombre}\""
        log_info = f"Stock anterior: {stock}"

    try:
        with db.transaccion():
            db.ejecutar(update_query, params)
            
            marca_tiempo = marca_de_tiempo()
            log = (
                f"[{marca_tiempo}] COMPRA INGRESADA por {usuarios.sesion.usuario}:\n"
                f"Producto: {nombre} (ID: {codigo}). {log_info} | "
                f"Cantidad agregada: {cantidad} | Nuevo stock: {nuevo_stock}"
            )
            registrar_log("inventario_compras.log", log)
            
        # 6. Mensaje de éxito
        plural = "unidad" if cantidad == 1 else "unidades"
        print(f"\n✔ Se aumentó {cantidad} {plural} {mensaje_impresion} (Nuevo stock de {nombre}: {nuevo_stock}).")
        
    except Exception as e:
        print(f"\n❌ Error al actualizar el stock: {e}")

    return # Finaliza después de la operación exitosa/fallida

@usuarios.requiere_acceso(2)
def editar_inventario():
    producto = _seleccionar_producto("comprado")
    if not producto:
        return  # Cancelado

    # 1. Lógica de Edición de Inventario (a partir de aquí tu código original)

    producto = producto_elegido
    codigo = producto["CODIGO"]
    nombre = producto["NOMBRE"].title()
    stock_anterior = producto["STOCK"]
    grupo = producto.get("GRUPO")
    if grupo:
        grupo = grupo.title()

    nuevo_stock = pedir_entero(f"Ingresá el nuevo stock de '{nombre}': ", minimo=0)
    
    # 2. Definir la consulta y los parámetros por defecto (solo el producto)
    update_query = "UPDATE PRODUCTOS SET STOCK = ? WHERE CODIGO = ?"
    params = (nuevo_stock, codigo)
    mensaje_accion = f"Modificado solo el stock de '{nombre}'"

    # 3. Lógica de Grupo
    if grupo:
        # Si el producto pertenece a un grupo, preguntar si aplicar el cambio a todo el grupo
        pregunta = f"\n⚠️  El producto pertenece al grupo '{grupo}'. ¿Deseas aplicar el nuevo stock a TODOS los productos de este grupo? (si/no): "
        
        if pedir_confirmacion(pregunta) == "si":
            # Aplicar a todo el grupo
            update_query = "UPDATE PRODUCTOS SET STOCK = ? WHERE GRUPO = ?"
            params = (nuevo_stock, grupo)
            mensaje_accion = f"Modificado el stock del grupo '{grupo}'"
            
        else:
            # Aplicar solo al producto editado (se usa el query/params por defecto)
            pass # No es necesario hacer nada, ya está configurado arriba
    
    # 4. Ejecutar la transacción
    try:
        with db.transaccion():
            db.ejecutar(update_query, params)
            
            marca_tiempo = marca_de_tiempo()
            log = (
                f"[{marca_tiempo}] INVENTARIO EDITADO por {usuarios.sesion.usuario}:\n"
                f"Producto: {nombre} (ID: {codigo}) | "
                f"Stock anterior: {stock_anterior} | Nuevo stock: {nuevo_stock}. "
                f"Acción: {mensaje_accion}"
            )
            registrar_log("inventario_ediciones.log", log)
            
        print(f"\n✔ {mensaje_accion}. Nuevo stock: {nuevo_stock}.")
        
    except Exception as e: 
        print(f"\n❌ Error al actualizar el inventario: {e}")

    return # Sale de la función después de la operación

def _seleccionar_producto(accion="a gestionar"):
    """
    Permite buscar y seleccionar un producto por nombre o código.
    Retorna el diccionario del producto elegido o None si se cancela.
    
    Parámetros:
        accion (str): Texto descriptivo que se muestra al usuario.
                      Ejemplo: 'comprado', 'a modificar', etc.
    """

    leyenda = f"\nIngresá el nombre o el CÓDIGO del producto {accion}, (*) para buscar ó (0) para cancelar: "

    while True:
        entrada = input(leyenda).strip()  # 🔹 Acepta texto y números

        if entrada == "0":
            print("❌ Operación cancelada.")
            return None

        resultados = []

        # 🔹 Mostrar todos los productos
        if entrada == "*":
            productos = db.obtener_todos("SELECT * FROM PRODUCTOS ORDER BY CODIGO")
            if productos:
                imprimir_productos(productos)
                continue
            else:
                print("\n❌ No hay productos cargados.")
                return None

        # 🔹 Búsqueda por código
        elif str(entrada).isdigit():
            codigo = int(entrada)
            producto = _ejecutar_busqueda("codigo", codigo)
            if producto:
                resultados = [producto]
            else:
                print(f"\n❌ Producto con código {codigo} no encontrado.")
                continue

        # 🔹 Búsqueda por nombre
        else:
            criterio_limpio = re.sub(r"[^a-zA-Z0-9\s/]", "", unidecode(entrada).lower().replace('-', ' ').replace('_', ' ').replace('/', ' '))
            criterios = criterio_limpio.split()
            
            if not criterios:
                print("\n⚠️ El texto ingresado no es válido para buscar.")
                continue
                
            resultados = _ejecutar_busqueda("nombre", criterios)

        # 🔹 Evaluar resultados
        if not resultados:
            if not str(entrada).isdigit():
                print(f"\n❌ No se encontraron productos que coincidan con '{entrada}'.")
            continue

        # 🔹 Resultado único
        if len(resultados) == 1:
            return resultados[0]

        # 🔹 Múltiples resultados
        print("\n➡️  Múltiples resultados encontrados:")
        imprimir_productos(resultados)

        leyenda_elegir = "\nIngresá el CÓDIGO exacto para seleccionar el producto, ó (0) para cancelar: "
        codigo_elegido = opcion_menu(leyenda_elegir, cero=True, minimo=1)

        if codigo_elegido == 0:
            print("❌ Selección cancelada.")
            continue

        producto_elegido = next((p for p in resultados if p['CODIGO'] == codigo_elegido), None)

        if not producto_elegido:
            print("\n❌ Código no válido para esta lista. Intentá de nuevo.")
            continue

        return producto_elegido