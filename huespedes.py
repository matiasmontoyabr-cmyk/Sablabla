import re
import sqlite3
import usuarios
from datetime import datetime, date
from db import db
from unidecode import unidecode
from utiles import HABITACIONES, registrar_log, imprimir_huesped, imprimir_huespedes, pedir_fecha_valida, pedir_entero, pedir_telefono, pedir_confirmacion, pedir_mail, habitacion_ocupada, marca_de_tiempo, pedir_habitación, opcion_menu, pedir_nombre

@usuarios.requiere_acceso(1)
def nuevo_huesped():
    estado = None
    documento = 0
    habitacion = 0
    leyenda = "\n¿Querés agregar un huesped programado (1), un checkin (2) o cancelar (0)?: "
    while True:
        pregunta_estado = opcion_menu(leyenda, cero=True, minimo=1, maximo=2)
        if pregunta_estado == 1:
            estado = "PROGRAMADO"
            break
        elif pregunta_estado == 2:
            estado = "ABIERTO"
            break
        elif pregunta_estado == 0:
            print("\n❌ Registro de huésped cancelado.")
            return
    
    mensaje_apellido = "Escribí el apellido del huesped ó (0) para cancelar: "
    apellido = pedir_nombre(mensaje_apellido)
    if apellido is None: # Si es None, el usuario canceló
        return
    
    mensaje_nombre = "Escriba el nombre del huesped ó (0) para cancelar: "
    nombre = pedir_nombre(mensaje_nombre)
    if nombre is None:
        return
    
    contingente = pedir_entero("Ingresá la cantidad de huéspedes: ",minimo=1,maximo=4)
    telefono = pedir_telefono("Ingresá un whatsapp de contacto: ")
    email = pedir_mail()
    aplicativo = pedir_confirmacion("¿Es una reserva de aplicativo? si/no: ")
    checkin = pedir_fecha_valida("Ingresá la fecha de checkin: ", allow_past=True)
    checkout = pedir_fecha_valida("Ingresá la fecha de checkout: ")
    while checkout < checkin:
        print("\n⚠️  La fecha de checkout no puede ser anterior al checkin.")
        checkout = pedir_fecha_valida("Ingresá la fecha de checkout nuevamente: ")
    if estado == "ABIERTO":
        documento = input("Ingersá el número de documento: ").strip()
    if estado in ("ABIERTO", "PROGRAMADO"):
        while True:
            habitacion = pedir_entero("Ingresá el número de habitación: ", minimo=1 , maximo=7)
            if habitacion_ocupada(habitacion, checkin, checkout):
                print(f"\n⚠️  La habitación {habitacion} ya está ocupada en esas fechas.")
                continue
            if habitacion in HABITACIONES:
                capacidad = HABITACIONES[habitacion]["capacidad"]
                if contingente > capacidad:
                    print(f"\n⚠️  La habitación {habitacion} ({HABITACIONES[habitacion]['tipo']}) "
                        f"tiene capacidad para {capacidad} pasajeros, pero el contingente es de {contingente}.")
                    continue
            else:
                print(f"\n⚠️  La habitación {habitacion} no está definida.")
                continue
            break
    registro = f"CREADO {estado} - {marca_de_tiempo()}"

    data = {"apellido": apellido, "nombre": nombre, "telefono": telefono, "email": email, "aplicativo": aplicativo, "estado": estado, "checkin": checkin, "checkout": checkout, "documento": documento, "habitacion": habitacion, "contingente": contingente, "registro": registro}

    try:
        sql = """
        INSERT INTO HUESPEDES (
            APELLIDO, NOMBRE, TELEFONO, EMAIL, APP, ESTADO,
            CHECKIN, CHECKOUT, DOCUMENTO, HABITACION,
            CONTINGENTE, REGISTRO
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        valores = (data["apellido"],data["nombre"], data["telefono"], data["email"], data["aplicativo"],
            data["estado"], data["checkin"], data["checkout"], data["documento"],
            data["habitacion"], data["contingente"], data["registro"])
        
        db.ejecutar(sql, valores)
    except Exception as e:
        print(f"\n❌ Error al registrar el huésped: {e}")
    print("\n✔ Huésped registrado correctamente.")
    return

@usuarios.requiere_acceso(1)
def cerrar_habitacion():
    leyenda = "\nIngresá el número de habitación a cerrar, (*) para buscar ó (0) para cancelar: "
    while True:
        habitacion = opcion_menu(leyenda, cero=True, minimo=1, maximo=7,)
        if habitacion == 0:
            return
        if habitacion == "*":
            abiertas = db.obtener_todos("SELECT HABITACION, APELLIDO, NOMBRE FROM HUESPEDES WHERE ESTADO = 'ABIERTO' ORDER BY HABITACION")
            if not abiertas:
                print("\n❌ No hay habitaciones abiertas en este momento.")
                return
            else:
                print("\n📋 Habitaciones abiertas:")
                print(f"{'HAB':<5} {'APELLIDO':<20} {'NOMBRE':<20}")
                print("-" * 45)
                for huesped in abiertas:
                    hab = huesped["HABITACION"]
                    ape = huesped["APELLIDO"]
                    nom = huesped["NOMBRE"]
                    print(f"{hab:<5} {ape:<20} {nom:<20}")
                print("-" * 45)
            continue

        # Buscar huésped ABIERTO en esa habitación
        huesped = db.obtener_uno("SELECT * FROM HUESPEDES WHERE HABITACION = ? AND ESTADO = 'ABIERTO'", (habitacion,))
        if huesped is None:
            print(f"\n⚠️  La habitación {habitacion} no está ocupada.")
            continue

        imprimir_huesped(huesped)
        numero = huesped["NUMERO"]
        hoy = date.today().isoformat()
        separador = "\n---\n"
        registro_anterior = str(huesped["REGISTRO"] or "")

        # Verificar consumos impagos
        query = """
            SELECT C.CANTIDAD, P.PRECIO
            FROM CONSUMOS C
            JOIN PRODUCTOS P ON C.PRODUCTO = P.CODIGO
            WHERE C.HUESPED = ? AND C.PAGADO = 0
        """
        consumos_no_pagados = db.obtener_todos(query, (numero,))
        total_pendiente = sum(c["CANTIDAD"] * c["PRECIO"] for c in consumos_no_pagados)

        if consumos_no_pagados:
            print(f"\n💰 Total pendiente por consumos NO pagados: R {total_pendiente:.2f}")
            respuesta_pago = pedir_confirmacion("\n⚠️¿Querés marcar estos consumos como pagados? (si/no): ")
            if respuesta_pago == "si":
                try:
                    db.ejecutar("UPDATE CONSUMOS SET PAGADO = 1 WHERE HUESPED = ? AND PAGADO = 0", (numero,))
                    marca_tiempo = marca_de_tiempo()
                    registro_pago = f"Se marcaron como pagados consumos por R {total_pendiente:.2f} - {marca_tiempo}"
                    nuevo_registro = registro_anterior + separador + registro_pago
                    editar_huesped_db(numero, {"REGISTRO": nuevo_registro})
                    print("\n✔ Todos los consumos pendientes fueron marcados como pagados.")
                except Exception as e:
                    print(f"\n❌ Error al marcar consumos como pagados: {e}")
            else:
                confirmar_cierre = pedir_confirmacion("\n⚠️  ¿Querés cerrar la habitación aun con consumos impagos? (si/no): ")
                if confirmar_cierre != "si":
                    print("\n❌ Cierre cancelado.")
                    return
        else:
            print("\n✔ No hay consumos pendientes de pago para esta habitación.")

        # Releer el registro actualizado de la base antes de cerrar
        registro_anterior = str(huesped["REGISTRO"] or "")
        separador = "\n---\n"

        registro_nuevo = f"Estado modificado a CERRADO - {marca_de_tiempo()}"
        if registro_anterior.strip():
            registro = registro_anterior + separador + registro_nuevo
        else:
            registro = registro_nuevo

        updates = {"ESTADO": "CERRADO", "CHECKOUT": hoy, "HABITACION": 0, "REGISTRO": registro}

        try:
            editar_huesped_db(numero, updates)
            # Construir log de cierre
            marca_tiempo = marca_de_tiempo()
            # Obtener información previa del huésped para el log
            huesped_data = db.obtener_uno("SELECT * FROM HUESPEDES WHERE NUMERO = ?", (numero,))
            if huesped_data:
                nombre = huesped_data["NOMBRE"]
                apellido = huesped_data["APELLIDO"]
                habitacion = huesped_data["HABITACION"]
                estado_anterior = huesped_data["ESTADO"]
                registro_anterior = huesped_data["REGISTRO"]
            else:
                nombre = apellido = "Desconocido"
                habitacion = estado_anterior = registro_anterior = "?"
            log = (
                f"[{marca_tiempo}] HUÉSPED CERRADO:\n"
                f"Nombre: {nombre} {apellido} | Habitación: {habitacion} | Estado anterior: {estado_anterior}\n"
                f"Total de consumos no pagados al momento del cierre: R {total_pendiente:.2f}\n"
                f"Registro previo:\n{registro_anterior.strip()}"
                f"Acción realizada por: {usuarios.sesion.usuario}"
            )
            registrar_log("huespedes_cerrados.log", log)
            print(f"\n✔ Habitación {habitacion} cerrada correctamente.")
        except Exception as e:
            print(f"\n❌ Error al cerrar la habitación: {e}")
        return

@usuarios.requiere_acceso(0)
def buscar_huesped():
    opciones = {
        1: ("APELLIDO", lambda: input("Ingresá el apellido: ").strip()),
        2: ("NUMERO", lambda: input("Ingresá el número de huesped: ").strip()),
        3: ("HABITACION", lambda: input("Ingresá el número de habitación: ").strip()),
        4: ("DOCUMENTO", lambda: input("Ingresá el número de documento: ").strip()),
        5: ("*", None)  # Ver todos
    }

    leyenda = "\n¿Cómo querés buscar al huesped?\n1. Por apellido\n2. Por número de huesped\n3. Por número de habitación\n4. Por documento\n5. Imprimir todos\n0. Cancelar: "
    while True:
        opcion = opcion_menu(leyenda, cero=True, minimo=1, maximo=5,)

        if opcion == 0:
            return

        if opcion in opciones:
            campo, get_valor = opciones[opcion]
            huesped = None
            huespedes = None

            if campo == "*":
                huespedes = db.obtener_todos("SELECT * FROM HUESPEDES ORDER BY LOWER(APELLIDO), LOWER(NOMBRE)")
            else: 
                valor_raw = get_valor()
                if not valor_raw:
                    print("\n⚠️  El valor de búsqueda no puede estar vacío.")
                    continue
                if campo == "APELLIDO":
                    # La consulta a la DB se hace amplia, sin normalizar acentos
                    query = "SELECT * FROM HUESPEDES WHERE APELLIDO LIKE ?"
                    params = (f"%{valor_raw}%",)
                    huespedes_iniciales = db.obtener_todos(query, params)
                    # Ahora, filtramos en Python usando unidecode
                    valor_normalizado = unidecode(valor_raw).lower()
                    huespedes_final = [
                        h for h in huespedes_iniciales
                        if valor_normalizado in unidecode(h["APELLIDO"]).lower()
                    ]
                    huespedes = huespedes_final # Asigna el resultado filtrado a la variable final
                else:
                    query = f"SELECT * FROM HUESPEDES WHERE {campo} = ?"
                    huesped = db.obtener_uno(query, (valor_raw,))
            if huespedes:
                print("\nListado de huéspedes:")
                imprimir_huespedes(huespedes)
            elif huesped:
                imprimir_huesped(huesped)
            else:
                print("\n❌ No se encontraron coincidencias.")
            break
        else:
            print("\n⚠️  Opción inválida. Intente nuevamente.")
    return

@usuarios.requiere_acceso(1)
def cambiar_estado():
    #Función principal que orquesta el cambio de estado."""
    
    # 1. Obtener huésped
    numero = _obtener_huesped()
    if numero is None:
        return

    # 2. Seleccionar estado
    nuevo_estado = _nuevo_estado()
    if nuevo_estado is None:
        return

    # 3. Preparar datos comunes
    registro_anterior_data = db.obtener_uno("SELECT REGISTRO FROM HUESPEDES WHERE NUMERO = ?", (numero,))
    registro_anterior = str(registro_anterior_data["REGISTRO"] or "") if registro_anterior_data else ""
    separador = "\n---\n"
    
    # 4. Delegar la ejecución
    if nuevo_estado == "PROGRAMADO":
        _actualizar_a_programado(numero, registro_anterior, separador)
    elif nuevo_estado == "ABIERTO":
        _actualizar_a_abierto(numero, registro_anterior, separador)
    elif nuevo_estado == "CERRADO":
        _actualizar_a_cerrado(numero, registro_anterior, separador)
    
    # La función termina aquí, el programa vuelve al menú principal.

def _obtener_huesped():
    # Bucle de entrada para obtener y validar el número de huésped.
    leyenda = "\nIngresá el número de huésped que querés cambiar de estado, (*) para buscar ó (0) para cancelar: "
    while True:
        numero = opcion_menu(leyenda, cero=True, asterisco=True, minimo=1)
        if numero == "*":
            buscar_huesped() # Llamar a la función de búsqueda
            return None      # Volver al menú o repetir la llamada a cambiar_estado
        if numero == 0:
            print("\n❌ Cambio cancelado.")
            return None
        
        huesped = db.obtener_uno("SELECT * FROM HUESPEDES WHERE NUMERO = ?", (numero,))
        
        if huesped is None:
            print("\n⚠️  Huésped no encontrado. Intente nuevamente.")
            continue
        
        imprimir_huesped(huesped)
        return numero # Devuelve el número de huésped validado

def _nuevo_estado():
    # Bucle de entrada para seleccionar y validar el nuevo estado."""
    opciones = {"1": "PROGRAMADO","2": "ABIERTO","3": "CERRADO"}
    leyenda = "\n¿A qué estado querés cambiar?\nIngresá (1) PROGRAMADO, (2) ABIERTO, (3) CERRADO, ó (0) para cancelar: "
    while True:
        seleccion = opcion_menu(leyenda, cero=True, asterisco=True, minimo=1, maximo=3)
        if seleccion == 0:
            return None # Cancelar selección
        return opciones[seleccion] # Devuelve el nombre del estado

def _actualizar_a_programado(numero, registro_anterior, separador):
    # Maneja la lógica para cambiar el estado a PROGRAMADO.
    # 1. Adquisición y validación de fechas
    checkin = pedir_fecha_valida("Ingresá la nueva fecha de checkin (DD-MM-YYYY): ")
    checkout = pedir_fecha_valida("Ingresá la nueva fecha de checkout (DD-MM-YYYY): ")
    while checkout < checkin:
        print("\n⚠️  La fecha de checkout no puede ser anterior al checkin.")
        checkout = pedir_fecha_valida("Ingresá la fecha de checkout nuevamente (DD-MM-YYYY): ")
    contingente = pedir_entero("Ingresá la cantidad de huéspedes: ", minimo=1, maximo=4)
    habitacion = pedir_habitación(checkin, checkout, contingente, numero)

    # 2. Construcción del registro y updates
    registro_nuevo = f"Estado modificado a PROGRAMADO - {datetime.now().isoformat(sep=' ', timespec='seconds')}"
    registro = registro_anterior + separador + registro_nuevo if registro_anterior.strip() else registro_nuevo
    
    updates = {
        "ESTADO": "PROGRAMADO", 
        "CHECKIN": checkin, 
        "CHECKOUT": checkout, 
        "HABITACION": habitacion,
        "CONTINGENTE": contingente,
        "REGISTRO": registro
    }
    
    # 3. Ejecución y manejo de errores
    try:
        editar_huesped_db(numero, updates) 
        print("\n✔ Estado actualizado a PROGRAMADO.")
        return True
    except Exception as e:
        print(f"\n❌ Error al actualizar el estado a PROGRAMADO: {e}")
        return False

def _actualizar_a_abierto(numero, registro_anterior, separador):
    # Maneja la lógica para cambiar el estado a ABIERTO.
    hoy = date.today().isoformat()
    
    # 1. Adquisición y validación de datos
    checkout = pedir_fecha_valida("Ingresá la fecha de checkout (DD-MM-YYYY): ")
    while checkout < hoy:
        print("\n⚠️  La fecha de checkout no puede ser anterior al checkin (hoy).")
        checkout = pedir_fecha_valida("Ingresá la fecha de checkout nuevamente (DD-MM-YYYY): ")
    documento = input("Ingersá el número de documento: ").strip()
    contingente = pedir_entero("Ingresá la cantidad de huéspedes: ", minimo=1, maximo=4)
    habitacion = pedir_habitación(hoy, checkout, contingente, numero)
    
    # 2. Construcción del registro y updates
    registro_nuevo = f"Estado modificado a ABIERTO - {datetime.now().isoformat(sep=' ', timespec='seconds')}"
    registro = registro_anterior + separador + registro_nuevo

    updates = {
        "ESTADO": "ABIERTO", "CHECKIN": hoy, "CHECKOUT": checkout, 
        "DOCUMENTO": documento, "HABITACION": habitacion,
        "CONTINGENTE": contingente, "REGISTRO": registro
    }
    
    # 3. Ejecución y manejo de errores
    try:
        editar_huesped_db(numero, updates)
        print("\n✔ Estado actualizado a ABIERTO.")
        return True
    except Exception as e:
        print(f"\n❌ Error al actualizar el estado a ABIERTO: {e}")
        return False

def _actualizar_a_cerrado(numero, registro_anterior, separador):
    # Maneja la lógica para cambiar el estado a CERRADO."""
    hoy = date.today().isoformat()
    
    # 1. Lógica de Consumos y Pago
    query = """
        SELECT C.CANTIDAD, P.PRECIO
        FROM CONSUMOS C JOIN PRODUCTOS P ON C.PRODUCTO = P.CODIGO
        WHERE C.HUESPED = ? AND C.PAGADO = 0
    """
    consumos_no_pagados = db.obtener_todos(query, (numero,))
    if consumos_no_pagados:
        total_pendiente = sum(c["CANTIDAD"] * c["PRECIO"] for c in consumos_no_pagados) # Asumo que la fila DB es un dict/Row

        if total_pendiente > 0:
            print(f"\n💰 Total pendiente por consumos NO pagados: R {total_pendiente:.2f}")
            respuesta_pago = pedir_confirmacion("\n⚠️  ¿Querés marcar estos consumos como pagados? (si/no): ")

            if respuesta_pago == "si":
                try:
                    # Actualiza consumos y añade registro de pago (si es exitoso)
                    db.ejecutar("UPDATE CONSUMOS SET PAGADO = 1 WHERE HUESPED = ? AND PAGADO = 0", (numero,))
                    
                    timestamp = datetime.now().isoformat(sep=" ", timespec="seconds")
                    registro_pago = f"Se marcaron como pagados consumos por R {total_pendiente:.2f} - {timestamp}"
                    registro_anterior += separador + registro_pago # Actualiza el registro_anterior para el paso 2
                    
                    print("\n✔ Todos los consumos pendientes fueron marcados como pagados.")
                except Exception as e:
                    print(f"\n❌ Error al marcar consumos como pagados: {e}")
                    return False # Si el pago falla, abortar el cierre.
            else:
                confirmar_cierre = pedir_confirmacion("\n⚠️ ¿Deseás cerrar el huésped aun con consumos impagos? (si/no): ")
                if confirmar_cierre != "si":
                    print("\n❌ Cierre cancelado.")
                    return False
        else:
            print("\n✔ No hay consumos pendientes de pago para este huésped.")
        
    # 2. Lógica de Cierre y Log
    registro_nuevo = f"Estado modificado a CERRADO - {datetime.now().isoformat(sep=' ', timespec='seconds')}"
    registro = registro_anterior + separador + registro_nuevo
    updates = {"ESTADO": "CERRADO", "CHECKOUT": hoy, "HABITACION": 0, "REGISTRO": registro}

    try:
        # Ejecución del cierre
        editar_huesped_db(numero, updates) 
        
        # Log de cierre (extraer la lógica de log a una función auxiliar es aún mejor)
        huesped_data = db.obtener_uno("SELECT * FROM HUESPEDES WHERE NUMERO = ?", (numero,))
        # ... (código de log simplificado)
        log = (
                    f"[{marca_de_tiempo()}] HUÉSPED CERRADO:\n"
                    f"Nombre: {huesped_data['NOMBRE']} {huesped_data['APELLIDO']} | Habitación: {huesped_data['HABITACION']} | Estado anterior: {huesped_data['ESTADO']}\n"
                    f"Total de consumos no pagados al momento del cierre: R {total_pendiente:.2f}\n"
                    f"Registro previo:\n{registro_anterior.strip()}"
                    f"Acción realizada por: {usuarios.sesion.usuario}"
                )
        registrar_log("huespedes_cerrados.log", log)
        
        print("\n✔ Huésped cerrado.")
        return True
    except Exception as e:
        print(f"\n❌ Error al cerrar el huésped: {e}")
        return False

def editar_huesped_db(numero, updates_dict):
    """
    Actualiza uno o varios campos del huésped dado su número de registro.
    updates_dict es un diccionario con {campo: valor}.
    """
    if not updates_dict:
        print("\n⚠️  No hay cambios para aplicar.")
        return

    set_clauses = []
    valores = []
    for campo, valor in updates_dict.items():
        set_clauses.append(f"{campo} = ?")
        valores.append(valor)

    # Añadir el número del huésped al final de los valores para la cláusula WHERE
    valores.append(numero)

    sql = f"UPDATE HUESPEDES SET {', '.join(set_clauses)} WHERE NUMERO = ?"
    db.ejecutar(sql, tuple(valores))

@usuarios.requiere_acceso(1)
def editar_huesped():
    leyenda = "\nIngresá el número de huésped que querés editar, (*) para buscar ó (0) para cancelar: "
    while True:
        numero = opcion_menu(leyenda, cero=True, asterisco=True, minimo=1)
        if numero == "*":
            return buscar_huesped()
        if numero == 0:
            print("Edición cancelada.")
            return

        numero = int(numero)
        huesped = db.obtener_uno("SELECT * FROM HUESPEDES WHERE NUMERO = ?", (numero,))
        if huesped is None:
            print("Huésped no encontrado.")
            continue

        imprimir_huesped(huesped)
        break
    campos = {
        "1": ("APELLIDO", lambda: input("\nIngresá el nuevo apellido: ").strip()),
        "2": ("NOMBRE", lambda: input("\nIngresá el nuevo nombre: ").strip()),
        "3": ("TELEFONO", lambda: pedir_telefono("\nIngresá el nuevo número de WhatsApp (11 dígitos): ")),
        "4": ("EMAIL", lambda: pedir_mail("\nIngresá el nuevo e-mail:")),
        "5": ("BOOKING", lambda: pedir_confirmacion("\n¿Es una reserva de Booking? si/no ")),
        "6": ("CHECKIN", lambda: pedir_fecha_valida("\nIngresá la fecha de checkin (DD-MM-YYYY): ", allow_past=True)),
        "7": ("CHECKOUT", lambda: pedir_fecha_valida("\nIngresá la nueva fecha de checkout (DD-MM-YYYY): ")),
        "8": ("DOCUMENTO", lambda: input("\nIngresá el nuevo documento: ").strip()),
        "9": ("HABITACION", lambda: pedir_entero("\nIngresá la nueva habitación: ", minimo=1, maximo=7)),
        "10": ("CONTINGENTE", lambda: pedir_entero("\nIngresá la cantidad de huéspedes: ", minimo=1))
    }
    
    while True:
        opcion = input(
            "\n¿Qué querés editar? Ingresá:\n"
            "(1) Apellido,    (2) Nombre,      (3) Teléfono,\n"
            "(4) Email,       (5) Booking,     (6) Checkin,\n"
            "(7) Checkout,    (8) Documento,   (9) Habitación,\n"
            "(10)Contingente, ó ingrese (0) para cancelar\n"
        ).strip()
        if opcion == "0":
            print("Edición cancelada.")
            break

        if opcion in campos:
            campo_sql, funcion_valor = campos[opcion]
            valor_ingresado = funcion_valor()
            if opcion in ("1", "2"):
                # Primero unidecode para manejar acentos, luego re.sub para limpiar caracteres
                valor_unidecode = unidecode(valor_ingresado)
                valor_limpio = valor_unidecode.replace('-', ' ').replace('_', ' ')
                nuevo_valor = re.sub(r"[^a-zA-Z0-9\s]", "", valor_limpio).lower()
                
                if not nuevo_valor.strip():
                    print(f"El {'apellido' if opcion == '1' else 'nombre'} del huésped no puede contener solo caracteres especiales y signos.")
                    continue # Volver a pedir la opción de edición
            else:
                # Para otros campos, usar el valor tal cual lo devuelve la función lambda (ya puede estar validado/formateado)
                nuevo_valor = valor_ingresado
            registro_anterior_data = db.obtener_uno("SELECT REGISTRO FROM HUESPEDES WHERE NUMERO = ?", (numero,))
            registro_anterior = registro_anterior_data["REGISTRO"] if registro_anterior_data and "REGISTRO" in registro_anterior_data else ""
            separador = "\n---\n"
            registro_actual = f"Se modificó {campo_sql} a '{nuevo_valor}' - {datetime.now().isoformat(sep=" ", timespec='seconds')}"
            nuevo_registro = registro_anterior + separador + registro_actual
            updates = {campo_sql: nuevo_valor, "REGISTRO": nuevo_registro}
            try:
                editar_huesped_db(numero, updates)
                print(f"✔ {campo_sql} actualizado correctamente.")
            except Exception as e:
                print(f"Error al actualizar {campo_sql}: {e}")
            break
        else:
            print("\n❌ Opción inválida. Intente nuevamente.")

    return

@usuarios.requiere_acceso(2)
def eliminar_huesped():
    leyenda = "\nIngresá el número del huésped a eliminar, (*) para buscar ó (0) para cancelar: "
    while True:
        numero = opcion_menu(leyenda, cero=True, asterisco=True, minimo=1)
        if numero == "*":
            buscar_huesped()
            continue
        if numero == 0:
            print("\n❌ Eliminación cancelada.")
            return

        huesped = db.obtener_uno("SELECT * FROM HUESPEDES WHERE NUMERO = ?", (numero,))
        if huesped is None:
            print("\n⚠️Huésped no encontrado.")
            continue

        imprimir_huesped(huesped)

        confirmacion = pedir_confirmacion("\n⚠️¿Está seguro que querés eliminar este huésped? (si/no): ")
        if confirmacion == "si":
            try:
                db.ejecutar("DELETE FROM HUESPEDES WHERE NUMERO = ?", (numero,))
                marca_tiempo = marca_de_tiempo()
                log = (
                    f"[{marca_tiempo}] HUÉSPED ELIMINADO:\n"
                    f"| NUMERO: {huesped['NUMERO']} | Apellido: {huesped['APELLIDO']} | "
                    f"| Nombre: {huesped['NOMBRE']} | Teléfono: {huesped['TELEFONO']} | "
                    f"| Email: {huesped['EMAIL']} | Booking: {huesped['BOOKING']} | "
                    f"| Estado: {huesped['ESTADO']} | Checkin: {huesped['CHECKIN']} | "
                    f"| Checkout: {huesped['CHECKOUT']} | Documento: {huesped['DOCUMENTO']} | "
                    f"| Habitación: {huesped['HABITACION']} | Contingente: {huesped['CONTINGENTE']} | "
                    f"| Registro: {huesped['REGISTRO']}\n"
                    f"| Acción realizada por: {usuarios.sesion.usuario}"
                )
                registrar_log("huespedes_eliminados.log", log)
                print("\n✔ Huésped eliminado.")
            except sqlite3.IntegrityError:
                print("\n❌ No se puede eliminar el huésped porque tiene consumos pendientes.")
            except Exception as e:
                print(f"\n❌ Error al eliminar huésped: {e}")
            return
        else:
            print("\n❌ Eliminación cancelada.")
            return

@usuarios.requiere_acceso(2)
def ver_registro():
    leyenda = "Ingresá el número de huésped para ver su historial, (*) para buscar ó (0) para cancelar: "
    while True:
        numero = opcion_menu(leyenda, cero=True, asterisco=True, minimo=1)
        if numero == 0:
            return
        if numero == "*":
            buscar_huesped()
            continue
        
        huesped = db.obtener_uno("SELECT NOMBRE, APELLIDO, REGISTRO FROM HUESPEDES WHERE NUMERO = ?", (numero,))
        if huesped is None:
            print("\n❌ Huésped no encontrado.")
            continue

        nombre = huesped["NOMBRE"]
        apellido = huesped["APELLIDO"]
        registro = huesped["REGISTRO"]
        print(f"\nHistorial del huésped {nombre} {apellido}:\n")

        if not registro:
            print("\n❌ Este huésped no tiene historial registrado.")
        else:
            entradas = registro.split("\n---\n")
            for i, linea in enumerate(entradas, start=1):
                print(f"{i}. {linea.strip()}\n")

        return