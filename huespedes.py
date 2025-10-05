import re
import sqlite3
import usuarios
from datetime import datetime, date, timedelta
from db import db
from unidecode import unidecode
from utiles import HABITACIONES, registrar_log, imprimir_huesped, imprimir_huespedes, pedir_fecha_valida, pedir_entero, pedir_telefono, pedir_confirmacion, pedir_mail, habitacion_ocupada, marca_de_tiempo, pedir_habitación, opcion_menu, pedir_nombre, formatear_fecha, parse_fecha_a_datetime

LISTA_BLANCA_HUESPED = [
    "APELLIDO",
    "NOMBRE",
    "TELEFONO",
    "EMAIL",
    "APP",
    "CHECKIN",
    "CHECKOUT",
    "DOCUMENTO",
    "CONTINGENTE",
    "REGISTRO",
    "ESTADO",
    "HABITACION"
]

@usuarios.requiere_acceso(1)
def nuevo_huesped():
    estado = None
    documento = "0"
    telefono = 0
    email = "0"
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
        
    mensaje_nombre = "Escriba el nombre del huesped ó (0) para cancelar: "
    nombre = pedir_nombre(mensaje_nombre)
    if nombre is None:
        return
    
    mensaje_apellido = "Escribí el apellido del huesped ó (0) para cancelar: "
    apellido = pedir_nombre(mensaje_apellido)
    if apellido is None: # Si es None, el usuario canceló
        return
    
    contingente = pedir_entero("Ingresá la cantidad de huéspedes: ",minimo=1,maximo=4)
    aplicativo = pedir_confirmacion("¿Es una reserva de aplicativo? si/no: ")
    if estado == "ABIERTO":
        telefono = pedir_telefono("Ingresá un whatsapp de contacto: ")
        email = pedir_mail()
        documento = input("Ingersá el número de documento: ").strip()
        checkin = date.today().isoformat()
    if estado == "PROGRAMADO":
        checkin = pedir_fecha_valida("Ingresá la fecha de checkin: ", allow_past=True)
    checkout = pedir_fecha_valida("Ingresá la fecha de checkout: ")
    while checkout < checkin:
        print("\n⚠️  La fecha de checkout no puede ser anterior al checkin.")
        checkout = pedir_fecha_valida("Ingresá la fecha de checkout nuevamente: ")
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
        with db.transaccion():
            sql = """
            INSERT INTO HUESPEDES (
                APELLIDO, NOMBRE, TELEFONO, EMAIL, APP, ESTADO,
                CHECKIN, CHECKOUT, DOCUMENTO, HABITACION,
                CONTINGENTE, REGISTRO
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            valores = (data["apellido"],data["nombre"], data["telefono"], data["email"], data["aplicativo"],
                data["estado"], data["checkin"], data["checkout"], data["documento"],
                data["habitacion"], data["contingente"], data["registro"])
            
            db.ejecutar(sql, valores)
    except Exception as e:
        print(f"\n❌ Error al registrar el huésped: {e}")
    print("\n✔ Huésped registrado correctamente.")
    return

def _pedir_datos(huesped):
    # Pide teléfono, email y/o documento si los valores son None, 0 o "".
    # Retorna un diccionario con los updates a aplicar.
    
    updates = {}
    
    # 1. DOCUMENTO
    # Si el documento es None, "0", o una cadena vacía, lo solicitamos.
    documento_actual = str(huesped["DOCUMENTO"] or "").strip()
    if not documento_actual or documento_actual == "0":
        while True:
            documento = input("Ingresá el número de documento del huésped: ").strip()
            if not documento: 
                print("\n⚠️ El documento no puede estar vacío.")
                continue
            updates["DOCUMENTO"] = documento
            break
    else:
        updates["DOCUMENTO"] = documento_actual

    # 2. TELÉFONO
    # Si el teléfono es None, 0, o una cadena vacía, lo solicitamos.
    telefono_actual = huesped["TELEFONO"]
    if not telefono_actual:
        nuevo_telefono = pedir_telefono("Ingresá un whatsapp de contacto : ")
        if nuevo_telefono == 0:
            updates["TELEFONO"] = huesped["TELEFONO"]
        elif nuevo_telefono:
            updates["TELEFONO"] = nuevo_telefono

    # 3. EMAIL
    # 1. Obtener el email actual. Mapea None a cadena vacía y elimina el marcador "0".
    email_actual = str(huesped["EMAIL"] or "").strip()
    # 2. Incluimos el "0" en el 'or' para que str() no lo convierta, y luego el .strip() lo elimine.
    # Condición: SOLO PEDIR el email si actualmente está vacío (incluyendo el caso "0")
    if not email_actual or email_actual == "0":
        nuevo_email = pedir_mail("Ingresá un email de contacto: ")
        if nuevo_email == "":
            updates["EMAIL"] = huesped["EMAIL"]
        elif nuevo_email:
            # Si el usuario ingresó un valor válido (la función pedir_mail lo garantiza)
            updates["EMAIL"] = nuevo_email

    return updates

@usuarios.requiere_acceso(1)
def realizar_checkin():
    # Muestra huéspedes programados para hoy y mañana
    hoy = date.today().isoformat()
    manana = (date.today() + timedelta(days=1)).isoformat()
    
    # Busca huéspedes con estado 'PROGRAMADO' hasta mañana
    programados = db.obtener_todos(
        "SELECT NUMERO, APELLIDO, NOMBRE, HABITACION, CHECKIN FROM HUESPEDES WHERE ESTADO = 'PROGRAMADO' AND CHECKIN <= ? ORDER BY APELLIDO", 
        (manana,)
    )

    if programados:
        programados_atrasados = [h for h in programados if h['CHECKIN'] < hoy]
        programados_ok = [h for h in programados if h['CHECKIN'] >= hoy]
        if programados_atrasados:
                print("\n🕰️  Huéspedes programados con CHECK-IN ATRASADO:")
                print(f"{'APELLIDO':<20} {'NOMBRE':<20} {'HAB':<5} {'CHECK-IN PROG':<15}")
                print("-" * 70)
                for h in programados_atrasados:
                    print(f"{h['APELLIDO'].title():<20} {h['NOMBRE'].title():<20} {h['HABITACION']:<5} {formatear_fecha(h['CHECKIN']):<15}")
                print("-" * 70)
        if programados_ok:
            print("\n🗓️  Huéspedes programados (ordenados por apellido):")
            print(f"{'APELLIDO':<20} {'NOMBRE':<20} {'HAB':<5} {'CHECK-IN':<15}")
            print("-" * 70)
            for h in programados_ok:
                print(f"{h['APELLIDO'].title():<20} {h['NOMBRE'].title():<20} {h['HABITACION']:<5} {formatear_fecha(h['CHECKIN']):<15}")
            print("-" * 70)
    else:
        print("\n⚠️  No hay huéspedes programados para el checkin.")
        return

    leyenda = "\nIngresá el número de habitación para hacer checkin ó (0) para cancelar: "
    while True:
        habitacion = opcion_menu(leyenda, cero=True, minimo=1, maximo=7)
        if habitacion == 0:
            print("\n❌ Checkin cancelado.")
            return

        # Buscar huésped PROGRAMADO en esa habitación
        huesped = db.obtener_uno("SELECT * FROM HUESPEDES WHERE HABITACION = ? AND ESTADO = 'PROGRAMADO'", (habitacion,))
        if not huesped:
            print(f"\n⚠️  No hay huésped programado en la habitación {habitacion}.")
            continue

        # Manejar la fecha real del Check-in (Integración de la nueva lógica)
        checkin_programado = huesped["CHECKIN"]
        checkin_definitivo = date.today().isoformat() # Por defecto, la fecha de hoy

        # Si la fecha programada es anterior a hoy, pedimos la fecha real de check-in
        if checkin_programado < checkin_definitivo:
            imprimir_huesped(huesped)
            
            # Llama a la función que maneja la interacción y la validación del rango de fechas
            fecha_auxiliar = _pedir_fecha_checkin_real(checkin_programado)
            
            if fecha_auxiliar:
                checkin_definitivo = fecha_auxiliar
            else:
                # Si se cancela la selección de fecha, se vuelve a preguntar por habitación.
                continue 

        numero = huesped["NUMERO"]
        imprimir_huesped(huesped)

        # Luego de previsualizar el huesped pide confirmación
        if not pedir_confirmacion("\n¿Confirmás que querés realizar el checkin (si/no): ") == "si":
            print("\n❌ Checkin cancelado por el usuario.")
            return
        
        # --- Recolección de datos y actualización (Lógica correcta) ---
        datos_recopilados = _pedir_datos(huesped)
        
        registro_anterior = str(huesped["REGISTRO"] or "")
        separador = "\n---\n"
        
        # Creación del registro
        if checkin_definitivo != checkin_programado:
            registro_checkin = (
                f"CHECK-IN REALIZADO (Fecha programada: {formatear_fecha(checkin_programado)} - Fecha definitiva: {formatear_fecha(checkin_definitivo)}) "
                f"- Estado cambiado a ABIERTO - {marca_de_tiempo()}"
            )
        else:
            registro_checkin = f"CHECK-IN REALIZADO - Estado cambiado a ABIERTO - {marca_de_tiempo()}" 
        
        nuevo_registro = registro_anterior + separador + registro_checkin if registro_anterior.strip() else registro_checkin

        updates = {
            "ESTADO": "ABIERTO",
            "CHECKIN": checkin_definitivo, # Se usa la fecha determinada/elegida
            "REGISTRO": nuevo_registro
        }
        updates.update(datos_recopilados)

        try:
            with db.transaccion():
                _editar_huesped_db(numero, updates)
            print(f"\n✔ Checkin realizado para {huesped['APELLIDO'].title()} {huesped['NOMBRE'].title()} en la habitación {huesped['HABITACION']}.")
            
            # Log de auditoría
            log = (
                f"[{marca_de_tiempo()}] CHECK-IN REALIZADO:\n"
                f"Huésped: {huesped['NOMBRE'].title()} {huesped['APELLIDO'].title()} (Nro: {numero})\n"
                f"Habitación: {huesped['HABITACION']} | Fecha definitiva: {checkin_definitivo}\n"
                f"Acción realizada por: {usuarios.sesion.usuario}" 
            )
            # Puedes simplificar la adición de la fecha programada al log así:
            if checkin_definitivo != checkin_programado:
                log = f"Fecha programada: {checkin_programado}\n" + log
                
            registrar_log("checkins.log", log) 
            
            return # Termina la función
        except Exception as e:
            print(f"\n❌ Error al actualizar la base de datos: {e}")
            return

def _pedir_fecha_checkin_real(fecha_programada):
    """
    Pide la fecha real del check-in, validando el rango entre la fecha programada y hoy.
    Utiliza pedir_fecha_valida(allow_past=True) para que acepte fechas pasadas.
    """
    hoy = date.today()
    min_date = parse_fecha_a_datetime(fecha_programada).date()
    max_date = hoy
    
    # ⚠️ Nota: Usamos allow_past=True para permitir que se ingresen fechas anteriores
    # a hoy, ya que min_date siempre será anterior a hoy en este contexto.
    leyenda = (
        f"Ingresá la fecha definitiva del Check-in, entre {formatear_fecha(min_date.isoformat())} y {formatear_fecha(max_date.isoformat())}: "
    )
    
    print("\n⚠️  El check-in estaba programado para un día anterior.") 

    while True:
        fecha_str_iso = pedir_fecha_valida(leyenda, allow_past=True, confirmacion=False)
        # Convertimos la ISO string a objeto date para la comparación de rango.
        fecha_real = date.fromisoformat(fecha_str_iso)
        
        if min_date <= fecha_real <= max_date:
            return fecha_real.isoformat()
        else:
            print("❌ Fecha fuera del rango permitido.")

@usuarios.requiere_acceso(1)
def realizar_checkout():
    leyenda = "\nIngresá el número de habitación a cerrar, (*) para buscar ó (0) para cancelar: "
    while True:
        habitacion = opcion_menu(leyenda, cero=True, asterisco=True, minimo=1, maximo=7,)
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
                    print(f"{huesped['HABITACION']:<5} {huesped['APELLIDO'].title():<20} {huesped['NOMBRE'].title():<20}")
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
        try:
            with db.transaccion():
                checkout_ok, registro_actualizado, total_pendiente = _verificar_consumos_impagos(numero, registro_anterior)

                if not checkout_ok:
                    # El checkout fue cancelado
                    return

                #CERRAR HABITACIÓN
                registro_nuevo = f"Estado modificado a CERRADO - {marca_de_tiempo()}"

                # Usamos el registro_actualizado que puede o no tener la nota de pago/advertencia
                if registro_actualizado.strip():
                    registro_final = registro_actualizado + separador + registro_nuevo
                else:
                    registro_final = registro_nuevo
                
                updates = {"ESTADO": "CERRADO", "CHECKOUT": hoy, "HABITACION": 0, "REGISTRO": registro_final}

                _editar_huesped_db(numero, updates)
            
            # 5. LOG DE AUDITORÍA
            log = (
                f"[{marca_de_tiempo()}] HUÉSPED CERRADO:\n"
                f"Nombre: {huesped['NOMBRE'].title()} {huesped['APELLIDO'].title()} | Habitación: {habitacion}\n"
                f"Total de consumos no pagados al momento del cierre: R {total_pendiente:.2f}\n" 
                f"Acción realizada por: {usuarios.sesion.usuario}"
            )
            registrar_log("huespedes_cerrados.log", log)
            print(f"\n✔ Checkout de Habitación {habitacion} realizado correctamente.")
            
        except Exception as e:
            if str(e) != "Checkout cancelado por el usuario.":
                 print(f"\n❌ Error al realizar el checkout. La operación fue revertida. {e}")
        return

@usuarios.requiere_acceso(0)
def buscar_huesped():
    opciones = {
        1: ("APELLIDO", lambda: pedir_nombre("Ingresá el apellido: ")),
        2: ("NOMBRE", lambda: pedir_nombre("Ingresá el nombre: ")),
        3: ("NUMERO", lambda: input("Ingresá el número de huesped: ").strip()),
        4: ("HABITACION", lambda: input("Ingresá el número de habitación: ").strip()),
        5: ("DOCUMENTO", lambda: input("Ingresá el número de documento: ").strip()),
        6: ("*", None)  # Ver todos
    }

    leyenda = "\n¿Cómo querés buscar al huesped?\n1. Por apellido\n2. Por nombre\n3. Por número de huesped\n4. Por número de habitación\n5. Por documento\n6. Imprimir todos\n0. Cancelar\n"
    while True:
        opcion = opcion_menu(leyenda, cero=True, minimo=1, maximo=6,)

        if opcion == 0:
            return

        if opcion in opciones:
            campo, get_valor = opciones[opcion]
            huesped = None
            huespedes = None

            if campo == "*":
                huespedes = db.obtener_todos("SELECT * FROM HUESPEDES ORDER BY LOWER(APELLIDO), LOWER(NOMBRE)")
            elif campo in ("APELLIDO", "NOMBRE"):
                # Búsqueda por texto (Apellido o Nombre) - LÓGICA UNIFICADA
                valor_normalizado = get_valor()
                if valor_normalizado is None:  # Si el usuario canceló
                    return
                # 1. Búsqueda en SQL: Traer un subconjunto usando LIKE (más rápido)
                # Se usa el valor normalizado para la búsqueda LIKE
                query = f"SELECT * FROM HUESPEDES WHERE LOWER({campo}) LIKE ?"
                # Añadimos '%' para búsqueda parcial. LOWER() asegura insensibilidad a mayúsculas.
                patron_sql = f"%{valor_normalizado}%"
                # Obtenemos los huéspedes que *probablemente* coinciden
                huespedes_amplio = db.obtener_todos(query, (patron_sql,))
                # 2. Filtrado final en Python: Asegurar coincidencia de tildes (máxima precisión)
                huespedes = [
                    h for h in huespedes_amplio
                    # Comparamos: valor_normalizado IN (unidecode del valor en BD)
                    if valor_normalizado in unidecode(h[campo]).lower()
                ]
            else: 
                valor_raw = get_valor()
                if not valor_raw:
                    print("\n⚠️  El valor de búsqueda no puede estar vacío.")
                    continue
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
        "5": ("APP", lambda: pedir_confirmacion("\n¿Es una reserva de aplicativo? si/no ")),
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
                with db.transaccion():
                    _editar_huesped_db(numero, updates)
                print(f"✔ {campo_sql} actualizado correctamente.")
            except ValueError as e:
                print(f"\n{e}")
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
                with db.transaccion():
                    db.ejecutar("DELETE FROM HUESPEDES WHERE NUMERO = ?", (numero,))
                    marca_tiempo = marca_de_tiempo()
                    log = (
                        f"[{marca_tiempo}] HUÉSPED ELIMINADO:\n"
                        f"| NUMERO: {huesped['NUMERO']} | Apellido: {huesped['APELLIDO']} | "
                        f"| Nombre: {huesped['NOMBRE']} | Teléfono: {huesped['TELEFONO']} | "
                        f"| Email: {huesped['EMAIL']} | Booking: {huesped['APP']} | "
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
    opciones = {1: "PROGRAMADO",2: "ABIERTO",3: "CERRADO"}
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
        with db.transaccion():
            _editar_huesped_db(numero, updates) 
        print("\n✔ Estado actualizado a PROGRAMADO.")
        return True
    except ValueError as e:
        print(f"{e}") 
    except Exception as e:
        print(f"\n❌ Error al actualizar el estado a PROGRAMADO: {e}")
        return False

def _actualizar_a_abierto(numero, registro_anterior, separador):
    # Maneja la lógica para cambiar el estado a ABIERTO.
    # La función debe obtener el huésped actual para chequear datos faltantes
    huesped_actual = db.obtener_uno("SELECT * FROM HUESPEDES WHERE NUMERO = ?", (numero,))
    if not huesped_actual:
        print("\n❌ Error interno: Huésped no encontrado.")
        return False
    hoy = date.today().isoformat()
    
    # 1. Adquisición y validación de datos
        # RECOLECCIÓN DE DATOS FALTANTES
    datos_contacto_updates = _pedir_datos(huesped_actual)
    checkout = pedir_fecha_valida("Ingresá la fecha de checkout (DD-MM-YYYY): ")
    while checkout < hoy:
        print("\n⚠️  La fecha de checkout no puede ser anterior al checkin (hoy).")
        checkout = pedir_fecha_valida("Ingresá la fecha de checkout nuevamente (DD-MM-YYYY): ")
    contingente = pedir_entero("Ingresá la cantidad de huéspedes: ", minimo=1, maximo=4)
    habitacion = pedir_habitación(hoy, checkout, contingente, numero)
    
    # 2. Construcción del registro y updates
    registro_nuevo = f"Estado modificado a ABIERTO - {datetime.now().isoformat(sep=' ', timespec='seconds')}"
    registro = registro_anterior + separador + registro_nuevo

    updates = {
        "ESTADO": "ABIERTO", "CHECKIN": hoy, "CHECKOUT": checkout, 
        "HABITACION": habitacion, "CONTINGENTE": contingente,
        "REGISTRO": registro
    }

    # Agregar los datos de contacto/documento recopilados al diccionario updates
    updates.update(datos_contacto_updates) 
    
    # 3. Ejecución y manejo de errores
    try:
        with db.transaccion():
            _editar_huesped_db(numero, updates)
        print("\n✔ Estado actualizado a ABIERTO.")
        return True
    except ValueError as e:
        print(f"{e}") 
    except Exception as e:
        print(f"\n❌ Error al actualizar el estado a ABIERTO: {e}")
        return False

def _actualizar_a_cerrado(numero, registro_anterior, separador):
    # Maneja la lógica para cambiar el estado a CERRADO."""
    # Obtiene el huesped actual para el log si es necesario
    huesped_data = db.obtener_uno("SELECT * FROM HUESPEDES WHERE NUMERO = ?", (numero,))
    if not huesped_data:
        print("\n❌ Error interno: Huésped no encontrado.")
        return False
    try:
        with db.transaccion():
            hoy = date.today().isoformat()
            
            # 1. VERIFICAR CONSUMOS Y GESTIONAR PAGO (Lógica Delegada)
            checkout_ok, registro_modificado, total_pendiente = _verificar_consumos_impagos(numero, registro_anterior)
            if not checkout_ok:
                # El cierre fue cancelado por el usuario o falló el pago.
                return False
            # Usamos el registro devuelto, que ya incluye notas de pago o de deuda
            registro_anterior = registro_modificado 
            
            # 2. Lógica de Cierre y Log
            registro_nuevo = f"Estado modificado a CERRADO - {datetime.now().isoformat(sep=' ', timespec='seconds')}"
            registro = registro_anterior + separador + registro_nuevo
            updates = {"ESTADO": "CERRADO", "CHECKOUT": hoy, "HABITACION": 0, "REGISTRO": registro}

            # Ejecución del cierre
            _editar_huesped_db(numero, updates) 
                
        # Este código solo se ejecuta si la transacción fue exitosa
        log = (
                    f"[{marca_de_tiempo()}] HUÉSPED CERRADO:\n"
                    f"Nombre: {huesped_data['NOMBRE']} {huesped_data['APELLIDO']} | Habitación: {huesped_data['HABITACION']} | Estado anterior: {huesped_data['ESTADO']}\n"
                    f"Total de consumos no pagados al momento del cierre: R {total_pendiente:.2f}\n"
                    f"Acción realizada por: {usuarios.sesion.usuario}"
                )
        registrar_log("huespedes_cerrados.log", log)
        print("\n✔ Huésped cerrado.")
        return True
    except ValueError as e:
        print(f"{e}") 
    except Exception as e:
        print(f"\n❌ Error al cerrar el huésped: {e}")
        return False

def _verificar_consumos_impagos(numero_huesped, registro_actual):
    # Verifica consumos impagos para un huésped, maneja el pago y la confirmación
    # de cierre. Retorna (True, registro_actualizado) si el checkout puede continuar, 
    # (False, None) si se cancela el checkout.

    separador = "\n---\n"
    
    # 1. Verificar consumos impagos
    query = """
        SELECT C.CANTIDAD, P.PRECIO
        FROM CONSUMOS C
        JOIN PRODUCTOS P ON C.PRODUCTO = P.CODIGO
        WHERE C.HUESPED = ? AND C.PAGADO = 0
    """
    consumos_no_pagados = db.obtener_todos(query, (numero_huesped,))
    # Calcular el total de consumos brutos (sin propina)
    total_consumos_bruto = sum(c["CANTIDAD"] * c["PRECIO"] for c in consumos_no_pagados)
    
    # LÓGICA DE PROPINAS APLICADA AQUÍ
    propina = total_consumos_bruto * 0.10
    total_pendiente = total_consumos_bruto + propina # Este es el monto final a pagar

    if not consumos_no_pagados:
        print("\n✔ No hay consumos pendientes de pago para esta habitación.")
        return True, registro_actual, total_pendiente # Se devuelve el total para el log
    
    # 2. Consumos pendientes
    print("\n=========================================")
    print("💰 Detalle de la cuenta pendiente:")
    print(f"   Consumos:          R {total_consumos_bruto:.2f}")
    print(f"   Propina (10%):     R {propina:.2f}")
    print(f"   TOTAL PENDIENTE:   R {total_pendiente:.2f}")
    print("=========================================")
    respuesta_pago = pedir_confirmacion("\n⚠️ ¿Querés marcar estos consumos como pagados? (si/no): ")
    
    if respuesta_pago == "si":
        try:
            with db.transaccion():
                # Marcar consumos como pagados
                db.ejecutar("UPDATE CONSUMOS SET PAGADO = 1 WHERE HUESPED = ? AND PAGADO = 0", (numero_huesped,))
                
                # Actualizar registro del huésped
                marca_tiempo = marca_de_tiempo()
                registro_pago = f"Se marcaron como pagados consumos e incluyó propina. Total cobrado: R {total_pendiente:.2f} (Consumos: R{total_consumos_bruto:.2f} + Propina: R{propina:.2f}) - {marca_tiempo}"
                nuevo_registro = registro_actual + separador + registro_pago
                _editar_huesped_db(numero_huesped, {"REGISTRO": nuevo_registro})
            
            print("\n✔ Todos los consumos pendientes fueron marcados como pagados.")
            return True, nuevo_registro, total_pendiente
        
        except ValueError as e:
            print(f"{e}") 
        except Exception as e:
            print(f"\n❌ Error al marcar consumos como pagados: {e}")
            # Se devuelve True para permitir que el checkout continúe si el error no es crítico,
            # pero es más seguro cancelar si el pago falló.
            print("\n❌ Cierre cancelado debido a un error de pago.")
            return False, None, total_pendiente 
            
    else:
        # Preguntar si desea cerrar aun con deuda
        confirmar_cierre = pedir_confirmacion("\n⚠️ ¿Querés cerrar la habitación aun con consumos impagos? (si/no): ")
        if confirmar_cierre != "si":
            print("\n❌ Cierre cancelado.")
            return False, None, total_pendiente
            
        # Registra la acción de cierre con deuda
        marca_tiempo = marca_de_tiempo()
        registro_impago = f"ADVERTENCIA: Habitación cerrada con deuda pendiente (Consumos + Propina) por un total de R{total_pendiente:.2f} - {marca_tiempo}"
        nuevo_registro_con_adv = registro_actual + separador + registro_impago
        
        print(f"\n✅ Habitación marcada para cierre. Se ha registrado la deuda pendiente (R {total_pendiente:.2f}).")
        
        # Se devuelve True y el registro con la advertencia
        return True, nuevo_registro_con_adv, total_pendiente

def _editar_huesped_db(numero, updates_dict):
    # Actualiza uno o varios campos del huésped dado su número de registro.
    # updates_dict es un diccionario con {campo: valor}.

    if not updates_dict:
        print("\n⚠️  No hay cambios para aplicar.")
        return

    set_clauses = []
    valores = []


    for campo, valor in updates_dict.items():
        # 1. Verifica que el nombre del campo esté en la lista blanca
        if campo in LISTA_BLANCA_HUESPED:
            # 2. Construye la cláusula SET con el nombre de columna filtrado
            set_clauses.append(f"{campo} = ?")
            # 3. Agrega el valor a la lista de parámetros (seguro)
            valores.append(valor)
        else:
            # 4. (Opcional) Notifica o ignora los campos no válidos
            print(f"⚠️  ADVERTENCIA DE SEGURIDAD: Campo '{campo}' ignorado (no permitido).")
    
    # Si después del filtrado no quedan campos para actualizar
    if not set_clauses:
        raise ValueError("⚠️  No quedaron campos válidos para actualizar.")

    sql = f"UPDATE HUESPEDES SET {', '.join(set_clauses)} WHERE NUMERO = ?"

    # Añadir el número del huésped al final de los valores para la cláusula WHERE
    valores.append(numero)

    try:
        db.ejecutar(sql, tuple(valores))
    except Exception as e:
        print(f"\n❌ Error al actualizar el huésped en la DB: {e}")
