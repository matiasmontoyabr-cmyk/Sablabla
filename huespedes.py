import re
import usuarios
from datetime import datetime, date
from db import db
from unidecode import unidecode
from utiles import HABITACIONES,registrar_log, imprimir_huesped, imprimir_huespedes, pedir_fecha_valida, pedir_entero, pedir_telefono, pedir_confirmacion, pedir_mail, habitacion_ocupada, marca_de_tiempo

@usuarios.requiere_acceso(1)
def nuevo_huesped():
    estado = None
    documento = 0
    nacimiento = 0
    habitacion = 0
    while True:
        pregunta_estado = input("\n¿Quiere agregar un huesped programado (1), un checkin (2) o cancelar (0)?: ").strip()
        if pregunta_estado == "1":
            estado = "PROGRAMADO"
            break
        elif pregunta_estado == "2":
            estado = "ABIERTO"
            break
        elif pregunta_estado == "0":
            print("\n❌ Registro de huésped cancelado.")
            return
        else:
            print("\n⚠️  Respuesta inválida. Intente nuevamente. ")
            continue
    while True:
        respuesta_apellido = input("Escriba el apellido del huesped ó (0) para cancelar: ").strip()
        if respuesta_apellido == "0":
            print("\n❌ Registro de huésped cancelado.")
            return
        if not respuesta_apellido:
            print("\n⚠️  El apellido no puede estar vacío.")
            continue
        apellido_unidecode = unidecode(respuesta_apellido)
        apellido_limpio = apellido_unidecode.replace('-', ' ').replace('_', ' ')
        apellido = re.sub(r"[^a-zA-Z0-9\s]", "", apellido_limpio).lower()
        if not apellido.strip():
            print("\n⚠️  El apellido del huésped no puede contener solo caracteres especiales o signos.")
            continue
        break
    while True:
        respuesta_nombre = input("Escriba el nombre del huesped ó (0) para cancelar: ").strip()
        if respuesta_nombre == "0":
            print("\n❌ Registro de huésped cancelado.")
            return
        if not respuesta_nombre:
            print("\n⚠️  El nombre no puede estar vacío")
            continue
        nombre_unidecode = unidecode(respuesta_nombre)
        nombre_limpio = nombre_unidecode.replace('-', ' ').replace('_', ' ')
        nombre = re.sub(r"[^a-zA-Z0-9\s]", "", nombre_limpio).lower()
        if not nombre.strip():
            print("\n⚠️  El nombre del huésped no puede contener solo caracteres especiales o signos.")
            continue
        break
    contingente = pedir_entero("Ingrese la cantidad de huéspedes: ",minimo=1,maximo=4)
    while True:
        telefono = pedir_telefono("Ingrese un whatsapp de contacto: ")
        break
    email = pedir_mail()
    booking = pedir_confirmacion("¿Es una reserva de booking? si/no: ")
    checkin = pedir_fecha_valida("Ingrese la fecha de checkin: ", allow_past=True)
    checkout = pedir_fecha_valida("Ingrese la fecha de checkout: ")
    while checkout < checkin:
        print("\n⚠️  La fecha de checkout no puede ser anterior al checkin.")
        checkout = pedir_fecha_valida("Ingrese la fecha de checkout nuevamente: ")
    if estado == "ABIERTO":
        documento = input("Ingerse el documento: ").strip()
        nacimiento = pedir_entero("Ingrese el año de nacimiento: ", minimo=1900)
    if estado in ("ABIERTO", "PROGRAMADO"):
        while True:
            habitacion = pedir_entero("Ingrese el número de habitación: ", minimo=1 , maximo=7)
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
                print(f"\n⚠️  La habitación {habitacion} no está definida en la configuración.")
                continue
            break
    registro = f"CREADO {estado} - {marca_de_tiempo()}"

    data = {"apellido": apellido, "nombre": nombre, "telefono": telefono, "email": email, "booking": booking, "estado": estado, "checkin": checkin, "checkout": checkout, "documento": documento, "nacimiento": nacimiento, "habitacion": habitacion, "contingente": contingente, "registro": registro}

    try:
        db.iniciar()
        sql = """
        INSERT INTO HUESPEDES (
            APELLIDO, NOMBRE, TELEFONO, EMAIL, BOOKING, ESTADO,
            CHECKIN, CHECKOUT, DOCUMENTO, NACIMIENTO, HABITACION,
            CONTINGENTE, REGISTRO
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        valores = (data["apellido"],data["nombre"], data["telefono"], data["email"], data["booking"],
            data["estado"], data["checkin"], data["checkout"], data["documento"], data["nacimiento"],
            data["habitacion"], data["contingente"], data["registro"])
        
        db.ejecutar(sql, valores)
        db.confirmar()
    except Exception as e:
        db.revertir()
        print(f"\n❌ Error al registrar el huésped: {e}")
    print("\n✔ Huésped registrado correctamente.")
    return

@usuarios.requiere_acceso(1)
def cerrar_habitacion():
    while True:
        habitacion = input("\nIngrese el número de habitación a cerrar, (*) para buscar ó (0) para cancelar: ").strip()
        if habitacion == "0":
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
                for hab, ape, nom in abiertas:
                    apellido_display = ' '.join(word.capitalize() for word in str(ape).split())
                    nombre_display = ' '.join(word.capitalize() for word in str(nom).split())
                    print(f"{hab:<5} {apellido_display:<20} {nombre_display:<20}")
                print("-" * 45)
            continue
        if not habitacion.isdigit():
            print("\n⚠️  Número inválido.")
            continue

        habitacion = int(habitacion)
        # Buscar huésped ABIERTO en esa habitación
        huesped = db.obtener_uno("SELECT * FROM HUESPEDES WHERE HABITACION = ? AND ESTADO = 'ABIERTO'", (habitacion,))
        if huesped is None:
            print(f"\n⚠️  La habitación {habitacion} no está ocupada.")
            continue

        imprimir_huesped(huesped)
        numero = huesped["NUMERO"]
        hoy = date.today().isoformat()
        separador = "\n---\n"
        registro_anterior = huesped["REGISTRO"] if huesped["REGISTRO"] else ""

        # Verificar consumos impagos
        query = """
            SELECT C.CANTIDAD, P.PRECIO
            FROM CONSUMOS C
            JOIN PRODUCTOS P ON C.PRODUCTO = P.CODIGO
            WHERE C.HUESPED = ? AND C.PAGADO = 0
        """
        consumos_no_pagados = db.obtener_todos(query, (numero,))
        total_pendiente = sum(cant * precio for cant, precio in consumos_no_pagados)

        if consumos_no_pagados:
            print(f"\n💰 Total pendiente por consumos NO pagados: R {total_pendiente:.2f}")
            respuesta_pago = pedir_confirmacion("\n⚠️¿Desea marcar estos consumos como pagados? (si/no): ")
            if respuesta_pago == "si":
                try:
                    db.iniciar()
                    db.ejecutar("UPDATE CONSUMOS SET PAGADO = 1 WHERE HUESPED = ? AND PAGADO = 0", (numero,))
                    marca_tiempo = marca_de_tiempo()
                    registro_pago = f"Se marcaron como pagados consumos por R {total_pendiente:.2f} - {marca_tiempo}"
                    nuevo_registro = registro_anterior + separador + registro_pago
                    editar_huesped_db(db, numero, {"REGISTRO": nuevo_registro})
                    db.confirmar()
                    print("\n✔ Todos los consumos pendientes fueron marcados como pagados.")
                except Exception as e:
                    db.revertir()
                    print(f"\n❌ Error al marcar consumos como pagados: {e}")
            else:
                confirmar_cierre = pedir_confirmacion("\n⚠️  ¿Desea cerrar la habitación aun con consumos impagos? (si/no): ")
                if confirmar_cierre != "si":
                    print("\n❌ Cierre cancelado.")
                    return
        else:
            print("\n✔ No hay consumos pendientes de pago para esta habitación.")

        # Releer el registro actualizado de la base antes de cerrar
        row = db.obtener_uno("SELECT REGISTRO FROM HUESPEDES WHERE NUMERO = ?", (numero,))
        registro_anterior = row["REGISTRO"] if row and "REGISTRO" in row else ""
        separador = "\n---\n"

        registro_nuevo = f"Estado modificado a CERRADO - {marca_de_tiempo()}"
        registro = registro_anterior + separador + registro_nuevo

        updates = {"ESTADO": "CERRADO", "CHECKOUT": hoy, "HABITACION": 0, "REGISTRO": registro}

        try:
            db.iniciar()
            editar_huesped_db(db, numero, updates)
            db.confirmar()

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
                f"Acción realizada por: {usuarios.USUARIO_ACTUAL}"
            )
            registrar_log("huespedes_cerrados.log", log)
            print(f"\n✔ Habitación {habitacion} cerrada correctamente.")
        except Exception as e:
            db.revertir()
            print(f"\n❌ Error al cerrar la habitación: {e}")
        return

@usuarios.requiere_acceso(0)
def buscar_huesped():
    opciones = {
        "1": ("APELLIDO", lambda: f"%{input("Ingrese el apellido: ").strip()}%"),
        "2": ("NUMERO", lambda: input("Ingrese el número de huesped: ").strip()),
        "3": ("HABITACION", lambda: input("Ingrese el número de habitación: ").strip()),
        "4": ("DOCUMENTO", lambda: input("Ingrese el número de documento: ").strip()),
        "5": ("*", None)  # Ver todos
    }

    while True:
        opcion = input("\n¿Cómo desea buscar al huesped?\n1. Por apellido\n2. Por número de huesped\n3. Por número de habitación\n4. Por documento\n5. Imprimir todos\n0. Cancelar\n").strip()

        if opcion == "0":
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
                    # Aplicamos la estandarización para el apellido
                    valor = unidecode(valor_raw).lower()
                    # La consulta también debe usar LOWER y unidecode en la columna para que la búsqueda sea efectiva
                    query = f"SELECT * FROM HUESPEDES WHERE LOWER({campo}) LIKE ?"
                    # Ya  el comodín % para búsqueda parcial
                    valor = f"%{valor}%"
                    huespedes = db.obtener_todos(query, (valor,))
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
    while True:
        numero = input("\nIngrese el número de huésped que desea cambiar de estado, (*) para buscar ó (0) para cancelar: ").strip()
        if numero == "*":
            return buscar_huesped()
        if numero == "0":
            print("\n❌ Cambio cancelado.")
            return
        if not numero.isdigit():
            print("\n⚠️  Número inválido. Intente nuevamente.")
            continue

        numero = int(numero)
        huesped = db.obtener_uno("SELECT * FROM HUESPEDES WHERE NUMERO = ?", (numero,))
        if huesped is None:
            print("\n⚠️  Huésped no encontrado. Intente nuevamente.")
            continue

        imprimir_huesped(huesped)
        break

    opciones = {"1": "PROGRAMADO","2": "ABIERTO","3": "CERRADO"}

    while True:
        seleccion = input('\n¿A qué estado quiere cambiar\nIngrese (1) "PROGRAMADO", (2) "ABIERTO", (3) "CERRADO", ó (0) para cancelar: ').strip()

        if seleccion == "0":
            print("\n❌ Cambio cancelado.")
            return cambiar_estado()

        if seleccion not in opciones:
            print("\n⚠️  Opción inválida. Intente nuevamente.")
            continue

        nuevo_estado = opciones[seleccion]
        hoy = date.today().isoformat()
        registro_anterior_data = db.obtener_uno("SELECT REGISTRO FROM HUESPEDES WHERE NUMERO = ?", (numero,))
        registro_anterior = registro_anterior_data["REGISTRO"] if registro_anterior_data and "REGISTRO" in registro_anterior_data else ""
        separador = "\n---\n"

        if nuevo_estado == "PROGRAMADO":
            checkin = pedir_fecha_valida("Ingrese la nueva fecha de checkin (DD-MM-YYYY): ")
            checkout = pedir_fecha_valida("Ingrese la nueva fecha de checkout (DD-MM-YYYY): ")
            while checkout < checkin:
                print("\n⚠️  La fecha de checkout no puede ser anterior al checkin.")
                checkout = pedir_fecha_valida("Ingrese la fecha de checkout nuevamente (DD-MM-YYYY): ")
            nacimiento_data = db.obtener_uno("SELECT NACIMIENTO FROM HUESPEDES WHERE NUMERO = ?", (numero,))
            nacimiento = nacimiento_data["NACIMIENTO"] if nacimiento_data and "NACIMIENTO" in nacimiento_data else ""
            if nacimiento < 1900:
                nacimiento = pedir_entero("Ingrese el año de nacimiento: ", minimo=1900)
            registro_nuevo = f"Estado modificado a {nuevo_estado} - {datetime.now().isoformat(sep=" ", timespec='seconds')}"
            registro = registro_anterior + separador + registro_nuevo
            updates = {"ESTADO": nuevo_estado, "CHECKIN": checkin, "CHECKOUT": checkout, "HABITACION": 0, "NACIMIENTO": nacimiento, "REGISTRO": registro}
            try:
                db.iniciar()
                editar_huesped_db(db, numero, updates)
                db.confirmar()
                print(f"\n✔ Estado actualizado a {nuevo_estado}.")
            except Exception as e:
                db.revertir()
                print(f"\n❌ Error al actualizar el estado: {e}")
            break

        elif nuevo_estado == "ABIERTO":
            checkin = hoy
            checkout = pedir_fecha_valida("Ingrese la nueva fecha de checkout (DD-MM-YYYY): ")
            while checkout < checkin:
                print("\n⚠️  La fecha de checkout no puede ser anterior al checkin.")
                checkout = pedir_fecha_valida("Ingrese la fecha de checkout nuevamente (DD-MM-YYYY): ")
            documento = input("Ingrese el documento: ").strip()
            nacimiento = db.obtener_uno("SELECT NACIMIENTO FROM HUESPEDES WHERE NUMERO = ?", (numero,))["NACIMIENTO"]
            if nacimiento < 1900:
                nacimiento = pedir_entero("Ingrese el año de nacimiento: ", minimo=1900)
            while True:
                habitacion = pedir_entero("Ingrese el número de habitación: ", minimo=1, maximo=7)
                if habitacion_ocupada(habitacion, checkin, checkout, excluir_numero=numero):
                    print(f"\n⚠️  La habitación {habitacion} ya está ocupada en esas fechas.")
                    continue
                break
            contingente = pedir_entero("Ingrese la cantidad de huéspedes: ", minimo=1,maximo=4)
            registro_nuevo = f"Estado modificado a {nuevo_estado} - {datetime.now().isoformat(sep=" ", timespec='seconds')}"
            registro = registro_anterior + separador + registro_nuevo

            # Unificar todas las actualizaciones en un diccionario
            updates = {"ESTADO": nuevo_estado, "CHECKIN": checkin, "CHECKOUT": checkout, "DOCUMENTO": documento, "NACIMIENTO": nacimiento, "HABITACION": habitacion, "CONTINGENTE": contingente, "REGISTRO": registro}
            try:
                db.iniciar()
                editar_huesped_db(db, numero, updates)
                db.confirmar()
                print(f"\n✔ Estado actualizado a {nuevo_estado}.")
            except Exception as e:
                db.revertir()
                print(f"\n❌ Error al actualizar el estado: {e}")
            break

        elif nuevo_estado == "CERRADO":
            query = """
                SELECT C.CANTIDAD, P.PRECIO
                FROM CONSUMOS C
                JOIN PRODUCTOS P ON C.PRODUCTO = P.CODIGO
                WHERE C.HUESPED = ? AND C.PAGADO = 0
            """
            consumos_no_pagados = db.obtener_todos(query, (numero,))
            total_pendiente = sum(cant * precio for cant, precio in consumos_no_pagados)

            if consumos_no_pagados:
                print(f"\n💰 Total pendiente por consumos NO pagados: R {total_pendiente:.2f}")
                respuesta_pago = pedir_confirmacion("\n⚠️  ¿Desea marcar estos consumos como pagados? (si/no): ")

                if respuesta_pago == "si":
                    try:
                        db.iniciar()
                        db.ejecutar("UPDATE CONSUMOS SET PAGADO = 1 WHERE HUESPED = ? AND PAGADO = 0", (numero,))

                        # Añadir entrada en el registro del huésped
                        registro_anterior_data = db.obtener_uno("SELECT REGISTRO FROM HUESPEDES WHERE NUMERO = ?", (numero,))
                        registro_anterior = registro_anterior_data["REGISTRO"] if registro_anterior_data and "REGISTRO" in registro_anterior_data else ""
                        separador = "\n---\n"
                        timestamp = datetime.now().isoformat(sep=" ", timespec="seconds")
                        registro_pago = f"Se marcaron como pagados consumos por R {total_pendiente:.2f} - {timestamp}"
                        nuevo_registro = registro_anterior + separador + registro_pago
                        
                        editar_huesped_db(db, numero, {"REGISTRO": nuevo_registro})
                        db.confirmar()
                        print("\n✔ Todos los consumos pendientes fueron marcados como pagados.")
                    except Exception as e:
                        db.revertir()
                        print(f"\n❌ Error al marcar consumos como pagados: {e}")
                else:
                    confirmar_cierre = pedir_confirmacion("\n⚠️¿Desea cerrar el huésped aun con consumos impagos? (si/no): ")
                    if confirmar_cierre != "si":
                        print("\n❌ Cierre cancelado.")
                        return
            else:
                print("\n✔ No hay consumos pendientes de pago para este huésped.")
            row = db.obtener_uno("SELECT REGISTRO FROM HUESPEDES WHERE NUMERO = ?", (numero,))
            registro_anterior = row["REGISTRO"] if row and "REGISTRO" in row else ""
            registro_nuevo = f"Estado modificado a {nuevo_estado} - {datetime.now().isoformat(sep=' ', timespec='seconds')}"
            registro = registro_anterior + separador + registro_nuevo
            updates = {"ESTADO": nuevo_estado, "CHECKOUT": hoy, "HABITACION": 0, "REGISTRO": registro}

            try:
                db.iniciar()
                editar_huesped_db(db, numero, updates)
                db.confirmar()

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
                    f"Acción realizada por: {usuarios.USUARIO_ACTUAL}"
                )
                registrar_log("huespedes_cerrados.log", log)
            except Exception as e:
                db.revertir()
                print(f"\n❌ Error al cerrar el huésped: {e}")

    return

def editar_huesped_db(database, numero, updates_dict):
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
    database.ejecutar(sql, tuple(valores))

@usuarios.requiere_acceso(1)
def editar_huesped():
    while True:
        numero = input("\nIngrese el número de huésped que desea editar, (*) para buscar ó (0) para cancelar: ").strip()
        if numero == "*":
            return buscar_huesped()
        if numero == "0":
            print("Edición cancelada.")
            return
        if not numero.isdigit():
            print("Número inválido. Intente nuevamente.")
            continue

        numero = int(numero)
        huesped = db.obtener_uno("SELECT * FROM HUESPEDES WHERE NUMERO = ?", (numero,))
        if huesped is None:
            print("Huésped no encontrado.")
            continue

        imprimir_huesped(huesped)
        break
    campos = {
        "1": ("APELLIDO", lambda: input("\nIngrese el nuevo apellido: ").strip()),
        "2": ("NOMBRE", lambda: input("\nIngrese el nuevo nombre: ").strip()),
        "3": ("TELEFONO", lambda: pedir_telefono("\nIngrese el nuevo número de WhatsApp (11 dígitos): ")),
        "4": ("EMAIL", lambda: pedir_mail("\nIngrese el nuevo e-mail:")),
        "5": ("BOOKING", lambda: pedir_confirmacion("\n¿Es una reserva de Booking? si/no ")),
        "6": ("CHECKIN", lambda: pedir_fecha_valida("\nIngrese la fecha de checkin (DD-MM-YYYY): ", allow_past=True)),
        "7": ("CHECKOUT", lambda: pedir_fecha_valida("\nIngrese la nueva fecha de checkout (DD-MM-YYYY): ")),
        "8": ("DOCUMENTO", lambda: input("\nIngrese el nuevo documento: ").strip()),
        "9": ("NACIMIENTO", lambda: pedir_entero("\nIngrese el año de nacimiento: ", minimo=1900, maximo=2100)),
        "10": ("HABITACION", lambda: pedir_entero("\nIngrese la nueva habitación: ", minimo=1, maximo=7)),
        "11": ("CONTINGENTE", lambda: pedir_entero("\nIngrese la cantidad de huéspedes: ", minimo=1))
    }
    
    while True:
        opcion = input(
            "\n¿Qué desea editar? Ingrese:\n"
            "(1) Apellido,    (2) Nombre,      (3) Teléfono,\n"
            "(4) Email,       (5) Booking,     (6) Checkin,\n"
            "(7) Checkout,    (8) Documento,   (9) Nacimiento,\n"
            "(10)Habitación,  (11)Contingente,\n"
            "ó ingrese (0) para cancelar\n"
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
                db.iniciar()
                editar_huesped_db(db, numero, updates)
                db.confirmar()
                print(f"✔ {campo_sql} actualizado correctamente.")
            except Exception as e:
                db.revertir()
                print(f"Error al actualizar {campo_sql}: {e}")
            break
        else:
            print("\n❌ Opción inválida. Intente nuevamente.")

    return

@usuarios.requiere_acceso(2)
def eliminar_huesped():
    while True:
        numero = input("\nIngrese el número del huésped a eliminar, (*) para buscar ó (0) para cancelar: ").strip()
        if numero == "*":
            buscar_huesped()
            continue
        if numero == "0":
            print("\n❌ Eliminación cancelada.")
            return
        if not numero.isdigit():
            print("\n⚠️  Número inválido. Intente nuevamente.")
            continue

        numero = int(numero)
        huesped = db.obtener_uno("SELECT * FROM HUESPEDES WHERE NUMERO = ?", (numero,))
        if huesped is None:
            print("\n⚠️Huésped no encontrado.")
            continue

        imprimir_huesped(huesped)

        confirmacion = pedir_confirmacion("\n⚠️¿Está seguro que desea eliminar este huésped? (si/no): ")
        if confirmacion == "si":
            try:
                db.iniciar()
                db.ejecutar("DELETE FROM HUESPEDES WHERE NUMERO = ?", (numero,))
                db.confirmar()
                marca_tiempo = marca_de_tiempo()
                log = (
                    f"[{marca_tiempo}] HUÉSPED ELIMINADO:\n"
                    f"NUMERO: {huesped['NUMERO']} | "
                    f"Apellido: {huesped['APELLIDO']} | Nombre: {huesped['NOMBRE']} | "
                    f"Teléfono: {huesped['TELEFONO']} | Email: {huesped['EMAIL']} | "
                    f"Booking: {huesped['BOOKING']} | Estado: {huesped['ESTADO']} | "
                    f"Checkin: {huesped['CHECKIN']} | Checkout: {huesped['CHECKOUT']} | "
                    f"Documento: {huesped['DOCUMENTO']} | Nacimiento: {huesped['NACIMIENTO']} | "
                    f"Habitación: {huesped['HABITACION']} | Contingente: {huesped['CONTINGENTE']} | "
                    f"Registro: {huesped['REGISTRO']}\n"
                    f"Acción realizada por: {usuarios.USUARIO_ACTUAL}"
                )
                registrar_log("huespedes_eliminados.log", log)
                print("\n✔ Huésped eliminado.")
            except db.IntegrityError:
                db.revertir()
                print("\n❌ No se puede eliminar el huésped porque tiene consumos pendientes.")
            except Exception as e:
                db.revertir()
                print(f"\n❌ Error al eliminar huésped: {e}")
            return
        else:
            print("\n❌ Eliminación cancelada.")
            return

@usuarios.requiere_acceso(2)
def ver_registro():
    while True:
        numero = input("Ingrese el número de huésped para ver su historial, (*) para buscar ó (0) para cancelar: ").strip()
        if numero == "0":
            return
        if numero == "*":
            buscar_huesped()
            continue
        if not numero.isdigit():
            print("\n⚠️Número inválido.")
            continue

        numero = int(numero)
        huesped = db.obtener_uno("SELECT NOMBRE, APELLIDO, REGISTRO FROM HUESPEDES WHERE NUMERO = ?", (numero,))
        if huesped is None:
            print("\n❌ Huésped no encontrado.")
            continue

        nombre, apellido, registro = huesped
        print(f"\nHistorial del huésped {nombre} {apellido}:\n")

        if not registro:
            print("\n❌ Este huésped no tiene historial registrado.")
        else:
            entradas = registro.split("\n---\n")
            for i, linea in enumerate(entradas, start=1):
                print(f"{i}. {linea.strip()}\n")

        return