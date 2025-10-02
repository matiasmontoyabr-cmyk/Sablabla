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
    print("\nHuésped seleccionado:")
    columnas = [
        "NUMERO", "APELLIDO", "NOMBRE", "TELEFONO", "EMAIL", "APP", "ESTADO", "CHECKIN", "CHECKOUT",
        "DOCUMENTO", "HABITACION", "CONTINGENTE", "REGISTRO"]
    for col in columnas:
        val = huesped[col] # Accede al valor por el nombre de la columna
        display_val = val # Por defecto, el valor es el mismo
        if col in ("APELLIDO", "NOMBRE"):
            if isinstance(val, str): # Asegurarse de que es una cadena antes de split/capitalize
                display_val = ' '.join(word.capitalize() for word in val.split())
        elif col in ("CHECKIN", "CHECKOUT"):
            display_val = formatear_fecha(val)
        elif col == "REGISTRO":
            val_str = str(val or "")
            if val_str.strip():
                display_val = val_str.strip().split("\n---\n")[-1]
            else:
                display_val = "(Sin registro)"
        if display_val is None or (isinstance(display_val, str) and not display_val.strip()):
            display_val = "N/A" # O el valor que prefieras para campos vacíos
        print(f"{col:<15}: {display_val}")
    print("-" * 40)

def imprimir_huespedes(huespedes):
    print(f"{'NUMERO':<6} {'APELLIDO':<15} {'NOMBRE':<15} {'ESTADO':^10} {'HAB':^5} {'CHECKIN':^12} {'CHECKOUT':^12}")
    print("-" * 80)
    for _, h in enumerate(huespedes, start=1):
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
        # Impresión
        print(f"{numero:<6} {apellido_display:<15} {nombre_display:<15} {estado:<10} {habitacion:^5} {checkin:<12} {checkout:<12}")
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
                if anio < 100:
                    # Asume que cualquier año de dos dígitos (ej: 25) es del siglo 21 (2025)
                    # Esto es seguro para un sistema de reservas moderno.
                    anio += 2000
                fecha = date(anio, mes, dia)
            except ValueError as e:
                print(f"\n❌ Formato de fecha inválido o fecha no existente: {e}. Ingresá una fecha como 07-05-2025 o 07052025.")
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
            print("❌No se pudo interpretar la fecha. Ingresá una fecha como 07-05-2025 o 07052025.")
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

def opcion_menu(leyenda, cero=False, vacio=False, asterisco=False, minimo=None, maximo=None):
    # Solicita una opción numérica al usuario, validando contra una serie de reglas.
    # Retorna el entero validado, 0 si se permite y elige cancelar, o None si se permite vacío.

    while True:
        entrada = input(f"{leyenda}").strip()

        # 1. Validar entrada vacía (Enter)
        if not entrada:
            if vacio:
                return None
            else:
                print("\n⚠️ Tenés que ingresar una opción.")
                continue

        # 2. Validar cancelación (Cero)
        if entrada == "0":
            if cero:
                return 0
            else:
                print("\n⚠️ '0' no es una opción valida.")
                continue

        if entrada == "*":
            if asterisco:
                return "*"
            else:
                print("\n⚠️ Asterisco no es una opción válida aquí.")
                continue

        # 4. Intentar convertir a número entero
        try:
            opcion = int(entrada)
        except ValueError:
            print("\n⚠️  La opción debe ser un número: ")
            continue
            
        # 5. Validar contra el rango (Mínimo/Máximo)
        if minimo is not None and opcion < minimo:
            print(f"\n⚠️  Opción inválida, debe ser igual o mayor que {minimo}.")
            continue
        
        if maximo is not None and opcion > maximo:
            print(f"\n⚠️  Opción inválida, debe ser igual o menor que {maximo}.")
            continue

        # 6. Éxito
        return opcion

def pedir_entero(mensaje, minimo=None, maximo=None, defecto=None):
    while True:
        respuesta_entero = input(mensaje).strip()
        solo_digitos = re.sub(r"[^0-9-]", "", respuesta_entero)  # Quita todo excepto dígitos y "-""
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

def pedir_telefono(mensaje="Ingresá un número de WhatsApp (11 dígitos mínimo): "):
    while True:
        respuesta_telefono = input(mensaje).strip()
        if not respuesta_telefono:
            return 0
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

def pedir_mail(mensaje="Ingresá el e-mail de contacto: "):
    while True:
        email = input(mensaje).strip()
        # 1. Comprueba si el campo está vacío
        if not email:
            return "" # Retorna una cadena vacía si no se ingresó nada
        # 2. Comprueba si el email es válido (si no está vacío)
        # El patrón de regex que tienes es: r"[^@]+@[^@]+\.[^@]+"
        if re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return email
        print("\n❌ Correo electrónico inválido, intente nuevamente.")

def pedir_precio(mensaje="Ingresá el precio: "):
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
            print("\n❌ Ingresá un número válido (ej: 1499.90).")

def pedir_nombre(mensaje):
    # Devuelve el nombre limpio (en minúsculas) si es válido, o None si el usuario cancela.
    while True:
        respuesta = input(mensaje).strip()
        
        # 1. Cancelación
        if respuesta == "0":
            print("\n❌ Operación cancelada.")
            return None # Devolvemos None para indicar cancelación

        # 2. No vacío
        if not respuesta:
            print("\n⚠️  El campo no puede estar vacío.")
            continue
            
        # 3. Limpieza de caracteres (Lógica actual)
        # Quitar acentos, reemplazar guiones por espacios y quitar caracteres especiales
        nombre_unidecode = unidecode(respuesta)
        nombre_limpio = nombre_unidecode.replace('-', ' ').replace('_', ' ')
        nombre_final = re.sub(r"[^a-zA-Z0-9\s]", "", nombre_limpio).lower()
        
        # 4. Verificación de contenido válido
        if not nombre_final.strip():
            print("\n⚠️  El valor ingresado no puede contener solo caracteres especiales o signos.")
            continue
            
        return nombre_final # Devolvemos el nombre limpio y validado

def pedir_habitación(checkin, checkout, contingente, excluir_numero=None):
    while True:
            habitacion = pedir_entero("Ingresá el número de habitación: ", minimo=1 , maximo=7)
            if habitacion_ocupada(habitacion, checkin, checkout, excluir_numero=excluir_numero):
                print(f"\n⚠️  La habitación {habitacion} ya está ocupada en esas fechas.")
                continue
            if habitacion in HABITACIONES:
                capacidad = HABITACIONES[habitacion]["capacidad"]
                if contingente > capacidad:
                    print(f"\n⚠️  La habitación {habitacion} ({HABITACIONES[habitacion]['tipo']}) "
                        f"tiene capacidad para {capacidad} pasajeros, pero el contingente es de {contingente}.")
                    continue
            else:
                print(f"\n⚠️  La habitación {habitacion} no está definida en la configuración.")
                continue
            return habitacion

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
        num = h["NUMERO"]
        h_in = h["CHECKIN"]
        h_out = h["CHECKOUT"]
        if excluir_numero and num == excluir_numero:
            continue  # Ignorar al mismo huésped que estamos editando
        try:
            h_in = date.fromisoformat(h_in)
            h_out = date.fromisoformat(h_out)
        except ValueError:
            # Si las fechas en la DB no son ISO, intenta el formato DD/MM/YY
            h_in = datetime.strptime(h_in, '%d/%m/%y').date()
            h_out = datetime.strptime(h_out, '%d/%m/%y').date()
        # Verificar solapamiento
        if fecha_in < h_out and h_in < fecha_out:
            return True  # Está ocupada en ese rango

    return False  # Libre en esas fechas

def imprimir_producto(producto):
    if not producto:
        print("\n❌ No hay producto para mostrar.")
        return
    print("\nProducto seleccionado:")
    columnas_a_mostrar = {
        "CODIGO": "CODIGO",
        "NOMBRE": "NOMBRE",
        "PRECIO": "PRECIO",
        "STOCK": "STOCK",
        "ALERTA": "ALERTA",
        "PINMEDIATO": "PINMEDIATO"
    }
    for col_key, col_display in columnas_a_mostrar.items():
        val = producto[col_key]
        display_val = val
        
        if col_key == "NOMBRE":
            if isinstance(val, str):
                display_val = val.capitalize()
        elif col_key == "PRECIO":
            display_val = f"R {val:.2f}"
        elif col_key == "STOCK":
            if val == -1:
                display_val = "∞"
        elif col_key == "PINMEDIATO":
            display_val = "Sí" if val == 1 else "No"
        elif col_key == "ALERTA":
            display_val = str(val) if val is not None else "-"
            
        print(f"{col_display:<15}: {display_val}")

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
        # Asegúrate de que los datos estén en el formato correcto para la impresión
        # Ya que db.obtener_todos devuelve una lista de diccionarios, es mejor acceder por claves
        # para evitar errores de "too many values to unpack".
        nombre_original = producto['NOMBRE']
        
        # --- CAPITALIZACIÓN Y TRUNCADO PARA IMPRESIÓN ---
        # Asegura que el nombre no exceda los 35 caracteres definidos en el header_format
        nombre_display = nombre_original.capitalize()
        if len(nombre_display) > 35:
            nombre_display = nombre_display[:32] + '...'

        precio_display = f"R {producto['PRECIO']:.2f}"
        stock_display = "∞" if producto['STOCK'] == -1 else str(producto['STOCK'])

        print(header_format.format(producto['CODIGO'], nombre_display, precio_display, stock_display))

    print(line_separator)
    input("\nPresioná Enter para continuar...")