import usuarios
from db import db
from utiles import imprimir_productos, pedir_entero, registrar_log, marca_de_tiempo

@usuarios.requiere_acceso(1)
def abrir_inventario():
    productos = db.obtener_todos("SELECT CODIGO, NOMBRE, STOCK FROM PRODUCTOS ORDER BY NOMBRE")
    if not productos:
        print("❌ No hay productos cargados.")
        return

    print("\n📦 Inventario actual:")
    print(f"{'CÓDIGO':<7} {'NOMBRE':<30} {'STOCK':<10}")
    print("-" * 50)
    for codigo, nombre, stock in productos:
        print(f"{codigo:<7} {nombre:<30} {stock:<10}")
    
    return

@usuarios.requiere_acceso(1)
def ingresar_compra():
    productos = db.obtener_todos("SELECT * FROM PRODUCTOS ORDER BY NOMBRE")
    if not productos:
        print("\n❌ No hay productos cargados.")
        return

    imprimir_productos(productos)

    while True:
        codigo = input("\nIngrese el CÓDIGO del producto comprado ó (0) para cancelar: ").strip()
        if codigo == "0":
            return
        if not codigo.isdigit():
            print("\n⚠️  Código inválido.")
            continue

        codigo = int(codigo)
        producto = db.obtener_uno("SELECT * FROM PRODUCTOS WHERE CODIGO = ?", (codigo,))
        if not producto:
            print("\n❌ Producto no encontrado.")
            continue

        nombre = producto["NOMBRE"]
        stock  = producto["STOCK"]
        cantidad = pedir_entero(f"Ingrese la cantidad comprada de '{nombre}': ", minimo=1)
        nuevo_stock = stock + cantidad
        try:
            db.ejecutar("UPDATE PRODUCTOS SET STOCK = ? WHERE CODIGO = ?", (nuevo_stock, codigo))
            marca_tiempo = marca_de_tiempo()
            log = (
                f"[{marca_tiempo}] COMPRA INGRESADA por {usuarios.sesion.usuario}:\n"
                f"Producto: {nombre} (ID: {codigo}) | "
                f"Stock anterior: {stock} | Agregado: {cantidad} | Nuevo stock: {nuevo_stock}"
            )
            registrar_log("inventario_compras.log", log)
            if cantidad == 1:
                print(f"\n✔ Se aumentó {cantidad} unidad el stock de '{nombre}' (Nuevo stock: {nuevo_stock}).")
            else:
                print(f"\n✔ Se aumentó {cantidad} unidades el stock de '{nombre}' (Nuevo stock: {nuevo_stock}).")
        except Exception as e:
            print(f"\n❌ Error al actualizar el stock de '{nombre}': {e}")

        return

@usuarios.requiere_acceso(2)
def editar_inventario():
    productos = db.obtener_todos("SELECT * FROM PRODUCTOS ORDER BY NOMBRE")
    if not productos:
        print("\n❌ No hay productos cargados.")
        return

    imprimir_productos(productos)

    while True:
        codigo = input("\nIngrese el CÓDIGO del producto a modificar ó (0) para cancelar: ").strip()
        if codigo == "0":
            return
        if not codigo.isdigit():
            print("\n⚠️  Código inválido.")
            continue

        codigo = int(codigo)
        producto = db.obtener_uno("SELECT * FROM PRODUCTOS WHERE CODIGO = ?", (codigo,))
        if not producto:
            print("\n⚠️  Producto no encontrado.")
            continue

        nombre = producto["NOMBRE"]
        nuevo_stock = pedir_entero(f"Ingrese el nuevo stock de '{nombre}': ", minimo=0)
        try:
            db.ejecutar("UPDATE PRODUCTOS SET STOCK = ? WHERE CODIGO = ?", (nuevo_stock, codigo))
            marca_tiempo = marca_de_tiempo()
            log = (
                f"[{marca_tiempo}] INVENTARIO EDITADO por {usuarios.sesion.usuario}:\n"
                f"Producto: {nombre} (ID: {codigo}) | "
                f"Stock anterior: {producto['STOCK']} | Nuevo stock: {nuevo_stock}"
            )
            registrar_log("inventario_ediciones.log", log)
            print(f"\n✔ Stock actualizado para '{nombre}'. Nuevo stock: {nuevo_stock}.")
        except Exception as e: 
            print(f"\n❌ Error al actualizar el inventario: {e}")

        return