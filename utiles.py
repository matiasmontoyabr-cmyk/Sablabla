import re
import os
from datetime import date, datetime
from db import db
from unidecode import unidecode

HABITACIONES = {
    1: {"tipo": "Doble", "capacidad": 2},
    2: {"tipo": "Doble", "capacidad": 2},
    3: {"tipo": "Doble", "capacidad": 2},
    4: {"tipo": "Doble", "capacidad": 2},
    5: {"tipo": "Triple", "capacidad": 3},
    6: {"tipo": "Triple", "capacidad": 3},
    7: {"tipo": "Master Suite", "capacidad": 4},  # o la capacidad real que quieras
}

def registrar_log(nombre_archivo, contenido):
    try:
        os.makedirs("logs", exist_ok=True)
        ruta = os.path.join("logs", nombre_archivo)
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(contenido + "\n" + "-"*60 + "\n")
    except Exception as e:
        # Evitar que un error de log rompa el flujo principal
        print(f"⚠️  No se pudo escribir el log '{nombre_archivo}': {e}")

def imprimir_huesped(huesped):
    print(f"\nHuésped seleccionado:")
    columnas = [
        "NUMERO", "APELLIDO", "NOMBRE", "TELEFONO", "EMAIL", "BOOKING", "ESTADO", "CHECKIN", "CHECKOUT",
        "DOCUMENTO", "NACIMIENTO", "HABITACION", "CONTINGENTE", "REGISTRO"]
    for col, val in zip(columnas, huesped):
        display_val = val # Por defecto, el valor es el mismo
        if col in ("APELLIDO", "NOMBRE"):
            if isinstance(val, str): # Asegurarse de que es una cadena antes de split/capitalize
                display_val = ' '.join(word.capitalize() for word in val.split())
        elif col in ("CHECKIN", "CHECKOUT"):
            display_val = formatear_fecha(val)
        elif col == "REGISTRO":
            if val:
                display_val = val.strip().split("\n---\n")[-1]
            else:
                display_val = "(Sin registro)"
        if display_val is None or (isinstance(display_val, str) and not display_val.strip()):
            display_val = "N/A" # O el valor que prefieras para campos vacíos
        print(f"{col:<15}: {display_val}")
    print("-" * 40)

def imprimir_huespedes(huespedes):
    print(f"{'NUMERO':<6} {'APELLIDO':<15} {'NOMBRE':<15} {'ESTADO':<10} {'HAB':<4} {'CHECKIN':<12} {'CHECKOUT':<12}")
    print("-" * 80)
    for i, h in enumerate(huespedes, start=1):
        numero = h["NUMERO"]
        apellido = h["APELLIDO"]
        nombre = h["NOMBRE"]
        estado = h["ESTADO"]
        habitacion = h["HABITACION"]
        checkin = formatear_fecha(h["CHECKIN"])
        checkout = formatear_fecha(h["CHECKOUT"])
        # --- CAPITALIZACIÓN PARA IMPRESIÓN ---
        # Capitalizar la primera letra de cada palabra para apellido y nombre
        apellido_display = ' '.join(word.capitalize() for word in str(apellido).split())
        nombre_display = ' '.join(word.capitalize() for word in str(nombre).split())
        # Truncamiento para asegurar que el formato de tabla no se rompa
        # Los anchos son 15 caracteres para Apellido y Nombre
        apellido_display = (apellido_display[:12] + '...') if len(apellido_display) > 15 else apellido_display
        nombre_display = (nombre_display[:12] + '...') if len(nombre_display) > 15 else nombre_display
        print(f"{numero:<6} {apellido_display:<15} {nombre_display:<15} {estado:<10} {habitacion:<4} {checkin:<12} {checkout:<12}")
    input("\nPresioná Enter para continuar...")

def pedir_fecha_valida(mensaje, allow_past=False):
    while True:
        respuesta_fecha = input(mensaje).strip()
        fecha = None
        if re.fullmatch(r"\d{8}", respuesta_fecha):
            try:
                dia = int(respuesta_fecha[0:2])
                mes = int(respuesta_fecha[2:4])
                anio = int(respuesta_fecha[4:8])
                fecha = date(anio, mes, dia)
            except ValueError:
                pass
        if fecha is None:
            fecha_input = re.sub(r"[^\d-]", "-", respuesta_fecha)
            try:
                partes = fecha_input.split("-")
                partes = [p for p in partes if p]
                if len(partes) != 3:
                    raise ValueError("\n❌ Número incorrecto de partes en la fecha.")
                dia, mes, anio = map(int, partes)
                fecha = date(anio, mes, dia)
            except ValueError as e:
                print(f"\n❌ Formato de fecha inválido o fecha no existente: {e}. Ingrese una fecha como 07-05-2025 o 07052025.")
                continue
            except Exception as e:
                print(f"\n❌ Ocurrió un error inesperado al procesar la fecha: {e}. Intente de nuevo.")
                continue
        if fecha:
            if fecha < date.today():
                if allow_past:
                    respuesta = pedir_confirmacion("\n⚠️  La fecha de check-in es anterior a hoy. ¿Desea registrarla de todas formas? (si/no): ")
                    if respuesta == "si":
                        return fecha.isoformat()
                    else:
                        continue
                else:
                    print("\n❌La fecha debe ser igual o posterior a hoy.")
                    continue
            else:
                return fecha.isoformat()
        else:
            print("❌No se pudo interpretar la fecha. Ingrese una fecha como 07-05-2025 o 07052025.")
            continue

def formatear_fecha(fecha_iso):
    """
    Acepta tanto 'YYYY-MM-DD' como 'YYYY-MM-DD HH:MM:SS'.
    Devuelve 'DD-MM-YYYY' si solo hay fecha,
    o 'DD-MM-YYYY HH:MM' si incluye hora.
    """
    formatos = [
        ("%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M"),  # fecha + hora
        ("%Y-%m-%d", "%d-%m-%Y")                  # solo fecha
    ]

    for fmt_in, fmt_out in formatos:
        try:
            return datetime.strptime(fecha_iso, fmt_in).strftime(fmt_out)
        except Exception:
            continue

    # Si no se puede parsear, devolver tal cual
    return fecha_iso

def marca_de_tiempo():
    return datetime.now().strftime("%d-%m-%Y %H:%M")

def pedir_entero(mensaje, minimo=None, maximo=None, defecto=None):
    while True:
        respuesta_entero = input(mensaje).strip()
        solo_digitos = re.sub(r"\D", "", respuesta_entero)  # Quita todo excepto dígitos
        if not solo_digitos:
            if defecto is not None:
                return defecto
            print("\n❌ Debe ingresar un número entero válido.")
            continue
        valor = int(solo_digitos)
        if minimo is not None and valor < minimo:
            print(f"\n❌ Debe ser mayor o igual a {minimo}.")
            continue
        if maximo is not None and valor > maximo:
            print(f"\n❌ Debe ser menor o igual a {maximo}.")
            continue
        return valor

def pedir_telefono(mensaje="Ingrese un número de WhatsApp (11 dígitos mínimo): "):
    while True:
        respuesta_telefono = input(mensaje).strip()
        solo_digitos = re.sub(r"\D", "", respuesta_telefono)  # Elimina todo lo que no sea número
        
        if len(solo_digitos) < 11:
            print("\n❌ El número debe tener al menos 11 dígitos.")
            continue

        return int(solo_digitos)

def pedir_confirmacion(mensaje="¿Confirma? (si/no): ", defecto=None):
    while True:
        respuesta = unidecode(input(mensaje)).strip().lower()

        # Si está vacío y hay defecto → devolverlo
        if not respuesta and defecto is not None:
            return defecto

        if respuesta in ("si", "s"):
            return "si"
        elif respuesta in ("no", "n"):
            return "no"
        else:
            print("⚠️  Escriba 'si' o 'no'.")

def pedir_mail(mensaje="Ingrese el e-mail de contacto: "):
    while True:
        email = input(mensaje).strip()
        if re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return email
        print("\n❌ Correo electrónico inválido, intente nuevamente.")

def pedir_precio(mensaje="Ingrese el precio: "):
    while True:
        entrada = input(mensaje).strip()

        # Reemplaza coma por punto y elimina todo lo que no sea número o punto
        entrada_limpia = re.sub(r"[^\d.]", "", entrada.replace(",", "."))

        try:
            precio = float(entrada_limpia)

            if precio < 0:
                print("\n❌ El precio no puede ser negativo.")
                continue

            if precio == 0:
                confirmar = pedir_confirmacion("\n¿Está seguro que el precio es 0? (si/no): ")
                if confirmar != "si":
                    continue

            return round(precio, 2)

        except ValueError:
            print("\n❌ Ingrese un número válido (ej: 1499.90).")

def habitacion_ocupada(habitacion, checkin, checkout, excluir_numero=None):
    """
    Verifica si una habitación está ocupada (ABIERTO o PROGRAMADO)
    en el rango de fechas dado [checkin, checkout].

    - habitacion: número de la habitación
    - checkin / checkout: fechas ISO (YYYY-MM-DD)
    - excluir_numero: opcional, para ignorar un huésped concreto (útil al editar)
    """
    query = """
        SELECT NUMERO, CHECKIN, CHECKOUT
        FROM HUESPEDES
        WHERE HABITACION = ?
          AND ESTADO IN ('ABIERTO', 'PROGRAMADO')
    """
    huespedes = db.obtener_todos(query, (habitacion,))

    fecha_in = date.fromisoformat(checkin)
    fecha_out = date.fromisoformat(checkout)

    for h in huespedes:
        num, h_in, h_out = h
        if excluir_numero and num == excluir_numero:
            continue  # ignorar al mismo huésped que estamos editando
        h_in = date.fromisoformat(h_in)
        h_out = date.fromisoformat(h_out)

        # Verificar solapamiento
        if fecha_in <= h_out and h_in <= fecha_out:
            return True  # está ocupada en ese rango

    return False  # libre en esas fechas

def imprimir_producto(producto):
    columnas = ["CODIGO", "NOMBRE", "PRECIO", "STOCK", "ALERTA", "PINMEDIATO"]
    print("\nProducto seleccionado:")
    for col, val in zip(columnas, producto):
        display_val = val
        if col == "NOMBRE":
            if isinstance(val, str):
                display_val = val.capitalize()
        elif col == "PRECIO":
            display_val = f"R {val:.2f}"
        elif col == "STOCK":
            if val == -1:
                display_val = "∞"
        elif col == "PINMEDIATO":
            display_val = "Sí" if val == 1 else "No"
        elif col == "ALERTA":
            display_val = str(val) if val is not None else "-"
        print(f"{col:<15}: {display_val}")

def imprimir_productos(productos):
    if not productos:
        print("No hay productos para mostrar.")
        return

    header_format = "{:<8} {:<35} {:<12} {:<8}"
    line_separator = "-" * 70  # Ajustar longitud

    print("\nListado de Productos\n")
    # Imprimir la cabecera de la tabla
    print(header_format.format("CÓDIGO", "NOMBRE", "PRECIO", "STOCK"))
    print(line_separator)

    # Imprimir cada producto en una fila
    for producto in productos:
        # producto = (CODIGO, NOMBRE, PRECIO, STOCK, PINMEDIATO)
        codigo, nombre_db, precio, stock, _ = producto  # ignoramos pinmediato

        # --- CAPITALIZACIÓN PARA IMPRESIÓN ---
        nombre_display = nombre_db.capitalize()
        nombre_display = (nombre_display[:32] + '...') if len(nombre_display) > 35 else nombre_display

        precio_display = f"R {precio:.2f}"
        stock_display = "∞" if stock == -1 else str(stock)

        print(header_format.format(codigo, nombre_display, precio_display, stock_display))

    print(line_separator)
    input("\nPresioná Enter para continuar...")