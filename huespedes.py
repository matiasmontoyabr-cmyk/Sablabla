import re
import sqlite3
import usuarios
from datetime import datetime, date
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
    "HABITACION",
    "DESCUENTO"
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
        documento = input("Ingresá el número de documento: ").strip()
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
        # Solo agrega al update si el usuario ingresó un valor válido y no canceló (0)
        if nuevo_telefono != 0: 
            updates["TELEFONO"] = nuevo_telefono

    # 3. EMAIL
    # 1. Obtener el email actual. Mapea None a cadena vacía y elimina el marcador "0".
    email_actual = str(huesped["EMAIL"] or "").strip()
    # 2. Incluimos el "0" en el 'or' para que str() no lo convierta, y luego el .strip() lo elimine.
    # Condición: SOLO PEDIR el email si actualmente está vacío (incluyendo el caso "0")
    if not email_actual or email_actual == "0":
        nuevo_email = pedir_mail("Ingresá un email de contacto: ")
        if nuevo_email != "":
            # Si el usuario ingresó un valor válido (la función pedir_mail lo garantiza)
            updates["EMAIL"] = nuevo_email

    return updates

@usuarios.requiere_acceso(1)
def realizar_checkin():
    # Muestra huéspedes programados para hoy
    hoy = date.today().isoformat()
    
    # Busca huéspedes con estado 'PROGRAMADO' hasta hoy (incluyendo atrasados)
    programados = db.obtener_todos(
        "SELECT NUMERO, APELLIDO, NOMBRE, HABITACION, CHECKIN FROM HUESPEDES WHERE ESTADO = 'PROGRAMADO' AND CHECKIN <= ? ORDER BY APELLIDO", 
        (hoy,)
    )

    if not programados:
        print("\n⚠️  No hay huéspedes programados para el checkin.")
        return

    # 1. MOSTRAR LISTADO (Delegado)
    _mostrar_programados(programados, hoy)

    leyenda = "\nIngresá el número de habitación para hacer checkin ó (0) para cancelar: "
    while True:
        habitacion = opcion_menu(leyenda, cero=True, minimo=1, maximo=7)
        if habitacion == 0:
            print("\n❌ Checkin cancelado.")
            return

        # 2. BUSCAR HUÉSPED PROGRAMADO (Lógica Original)
        # Ordenamos por CHECKIN ascendente para tomar el más antiguo/próximo.
        huesped = db.obtener_uno(
            "SELECT * FROM HUESPEDES WHERE HABITACION = ? AND ESTADO = 'PROGRAMADO' AND CHECKIN <= ? ORDER BY DATE(CHECKIN) ASC",
            (habitacion, hoy,)
        )

        if not huesped:
            print(f"\n⚠️  No hay huésped programado en la habitación {habitacion}.")
            continue

        # 3. MANEJO DE FECHA REAL (Lógica Original)
        checkin_programado = huesped["CHECKIN"]
        checkin_definitivo = date.today().isoformat() # Por defecto, la fecha de hoy

        # Si la fecha programada es anterior a hoy, pedimos la fecha real de check-in
        if checkin_programado < checkin_definitivo:
            imprimir_huesped(huesped)
            
            # Asegúrate que '_pedir_fecha_checkin_real' está disponible
            fecha_auxiliar = _pedir_fecha_checkin_real(checkin_programado)
            
            if fecha_auxiliar:
                checkin_definitivo = fecha_auxiliar
            else:
                # Si se cancela la selección de fecha, se vuelve a preguntar por habitación.
                continue 

        # 4. PROCESAR CHECK-IN Y ACTUALIZAR (Delegado)
        if _procesar_checkin_y_actualizar(huesped, checkin_definitivo, checkin_programado):
            return # Termina la función después de un check-in exitoso.
        
        # Si la actualización falló (_procesar_checkin_y_actualizar devolvió False),
        # la función simplemente termina o continúa el bucle, dependiendo de cómo maneje
        # _procesar_checkin_y_actualizar los errores internos. Como ya pusimos el 'return'
        # dentro de la función auxiliar en caso de cancelación/éxito, aseguramos que
        # un fallo de DB dentro de la auxiliar termine la ejecución principal.
        
        # Si por alguna razón la actualización falla pero queremos seguir pidiendo habitaciones:
        # continue 
        
        # En este caso, si la función auxiliar devuelve False, asumimos que se debe salir:
        return

def _mostrar_programados(programados, hoy):
    """
    Toma la lista de huéspedes programados y los imprime, dividiendo
    entre atrasados y en fecha.
    """
    programados_atrasados = [h for h in programados if h['CHECKIN'] < hoy]
    programados_ok = [h for h in programados if h['CHECKIN'] >= hoy]
    
    if programados_atrasados:
        print("\n🕰️  Huéspedes programados con CHECK-IN ATRASADO:")
        print(f"{'APELLIDO':<20} {'NOMBRE':<20} {'HAB':<5} {'CHECK-IN PROG':<15}")
        print("-" * 70)
        for h in programados_atrasados:
            # Asegúrate que 'formatear_fecha' está disponible
            print(f"{h['APELLIDO'].title():<20} {h['NOMBRE'].title():<20} {h['HABITACION']:<5} {formatear_fecha(h['CHECKIN']):<15}")
        print("-" * 70)
        
    if programados_ok:
        print("\n🗓️  Huéspedes programados (ordenados por apellido):")
        print(f"{'APELLIDO':<20} {'NOMBRE':<20} {'HAB':<5} {'CHECK-IN':<15}")
        print("-" * 70)
        for h in programados_ok:
            print(f"{h['APELLIDO'].title():<20} {h['NOMBRE'].title():<20} {h['HABITACION']:<5} {formatear_fecha(h['CHECKIN']):<15}")
        print("-" * 70)

def _procesar_checkin_y_actualizar(huesped, checkin_definitivo, checkin_programado):
    """
    Realiza la recolección de datos, la actualización de la BD y el logging.
    Aísla toda la lógica de escritura.
    """
    numero = huesped["NUMERO"]
    
    # Previsualización y confirmación (se mantiene aquí por contexto inmediato)
    imprimir_huesped(huesped)
    if not pedir_confirmacion("\n¿Confirmás que querés realizar el checkin (si/no): ") == "si":
        print("\n❌ Checkin cancelado por el usuario.")
        return False
    
    # --- Recolección de datos y actualización (Lógica correcta) ---
    # Asegúrate que '_pedir_datos' está disponible
    datos_recopilados = _pedir_datos(huesped)
    
    registro_anterior = str(huesped["REGISTRO"] or "")
    separador = "\n---\n"
    
    # Creación del registro (Lógica original)
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
        "CHECKIN": checkin_definitivo, 
        "REGISTRO": nuevo_registro
    }
    updates.update(datos_recopilados)

    try:
        # La transacción es CRÍTICA
        with db.transaccion():
            # Asegúrate que '_editar_huesped_db' está disponible
            _editar_huesped_db(numero, updates)
        print(f"\n✔ Checkin realizado para {huesped['APELLIDO'].title()} {huesped['NOMBRE'].title()} en la habitación {huesped['HABITACION']}.")
        
        # Log de auditoría
        log = (
            f"[{marca_de_tiempo()}] CHECK-IN REALIZADO:\n"
            f"Huésped: {huesped['NOMBRE'].title()} {huesped['APELLIDO'].title()} (Nro: {numero})\n"
            f"Habitación: {huesped['HABITACION']} | Fecha definitiva: {checkin_definitivo}\n"
            f"Acción realizada por: {usuarios.sesion.usuario}" 
        )
        if checkin_definitivo != checkin_programado:
            log = f"Fecha programada: {checkin_programado}\n" + log
            
        registrar_log("checkins.log", log) 
        
        return True # Indica éxito
        
    except Exception as e:
        print(f"\n❌ Error al actualizar la base de datos: {e}")
        return False # Indica fallo

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

@usuarios.requiere_acceso(1)
def realizar_checkout():
    # 1. Obtener y mostrar la lista de habitaciones abiertas (CHECK-INs pendientes)
    abiertas = db.obtener_todos("SELECT HABITACION, APELLIDO, NOMBRE FROM HUESPEDES WHERE ESTADO = 'ABIERTO' ORDER BY HABITACION")
    
    if not abiertas:
        print("\n❌ No hay habitaciones abiertas en este momento.")
        return

    print("\n📋 Habitaciones abiertas:")
    print(f"{'HAB':<5} {'APELLIDO':<20} {'NOMBRE':<20}")
    print("-" * 45)
    for huesped in abiertas:
        print(f"{huesped['HABITACION']:<5} {huesped['APELLIDO'].title():<20} {huesped['NOMBRE'].title():<20}")
    print("-" * 45)

    # 2. Pedir el número de habitación
    leyenda = "\nIngresá el número de habitación a cerrar ó (0) para cancelar: "
    while True:
        habitacion = opcion_menu(leyenda, cero=True, minimo=1, maximo=7,)
        if habitacion == 0:
            return

        # Buscar huésped ABIERTO en esa habitación
        huesped = db.obtener_uno("SELECT * FROM HUESPEDES WHERE HABITACION = ? AND ESTADO = 'ABIERTO'", (habitacion,))
        if huesped is None:
            print(f"\n⚠️  La habitación {habitacion} no está ocupada.")
            continue

        imprimir_huesped(huesped)
        if not pedir_confirmacion("\n¿Confirmás que querés realizar el checkout (si/no): ") == "si":
            print("\n❌ Checkout cancelado por el usuario.")
            return
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

def _verificar_consumos_impagos(numero_huesped, registro_actual):
    """
    Verifica consumos impagos para un huésped, maneja el pago y la confirmación
    de cierre, aplicando el descuento si existe. 
    Retorna (True, registro_actualizado, total_final) si el checkout puede continuar, 
    (False, None, total_final) si se cancela el checkout.
    """
    
    # 0. OBTENER INFORMACIÓN DEL HUÉSPED
    huesped = db.obtener_uno("SELECT * FROM HUESPEDES WHERE NUMERO = ?", (numero_huesped,))
    if not huesped:
        print(f"❌ Error: No se encontró el huésped con número {numero_huesped}.")
        return False, None, 0.00
    
    # 1. Verificar consumos impagos (Calculando el total de consumos BRUTOS)
    query = """
        SELECT C.CANTIDAD, P.PRECIO
        FROM CONSUMOS C
        JOIN PRODUCTOS P ON C.PRODUCTO = P.CODIGO
        WHERE C.HUESPED = ? AND C.PAGADO = 0
    """
    consumos_no_pagados = db.obtener_todos(query, (numero_huesped,))
    
    # Calcular el total de consumos BRUTOS (base para los cálculos)
    grand_subtotal = sum(c["CANTIDAD"] * c["PRECIO"] for c in consumos_no_pagados)
    
    if not consumos_no_pagados:
        print("\n✔ No hay consumos pendientes de pago para esta habitación.")
        # Se devuelve True, el registro actual y un total final de 0.00
        return True, registro_actual, 0.00

    # 2. CALCULAR, MOSTRAR TOTALES Y DESCUENTOS (Delegado)
    total_pendiente, propina, grand_subtotal, dcto_log = _calcular_y_mostrar_totales(huesped, grand_subtotal)
    
    # 3. MANEJAR PAGO, CONFIRMACIÓN Y REGISTRO (Delegado)
    checkout_ok, nuevo_registro_actual = _manejar_pago_y_registro(
        numero_huesped, 
        registro_actual, 
        total_pendiente, 
        grand_subtotal, 
        propina, 
        dcto_log
    )
    
    # 4. DEVOLVER EL RESULTADO FINAL
    return checkout_ok, nuevo_registro_actual, total_pendiente

def _calcular_y_mostrar_totales(huesped, grand_subtotal):
    """
    Calcula los descuentos, la propina y el total pendiente, y lo imprime.
    Retorna (total_pendiente, propina, grand_subtotal, dcto_log).
    """
    LINE_WIDTH = 84
    LABEL_WIDTH = 69
    VALUE_FORMAT_WIDTH = 12 

    # Variables de descuento
    descuento_str = huesped.get("DESCUENTO")
    monto_dcto_consumos, monto_dcto_final = 0.0, 0.0
    lugar = tipo = valor = None
    dcto_log = ""
    
    print("\n" + "=" * LINE_WIDTH)
    print(f"{'TOTAL DE CONSUMOS (Bruto):':<{LABEL_WIDTH}} R$ {grand_subtotal:>{VALUE_FORMAT_WIDTH}.2f}")

    # --- LÓGICA DE DESCUENTOS ---
    if descuento_str:
        try:
            partes = descuento_str.split('-')
            lugar, tipo, valor_str = partes[0], partes[1], partes[2]
            valor = float(valor_str)

            if lugar == 'consumos':
                if tipo == 'pct':
                    monto_dcto_consumos = grand_subtotal * (valor / 100.0)
                    dcto_descripcion = f"DESCUENTO ({valor}%)"
                    dcto_log += f"Descuento Consumos: {valor}% "
                elif tipo == 'valor':
                    monto_dcto_consumos = valor
                    dcto_descripcion = f"DESCUENTO (R$ {valor:.2f})"
                    dcto_log += f"Descuento Consumos: R${valor:.2f} "

            if monto_dcto_consumos > 0:
                monto_negativo_dcto_consumos = -1 * monto_dcto_consumos
                print(f"{dcto_descripcion:<{LABEL_WIDTH}} R$ {monto_negativo_dcto_consumos:>{VALUE_FORMAT_WIDTH}.2f}") 
                print("-" * LINE_WIDTH)
        
        except (IndexError, ValueError):
            print("❗ Advertencia: Formato de descuento inválido. Ignorando descuento.")
            descuento_str = None 
            lugar = None
            dcto_log = "Advertencia: Descuento inválido ignorado. "
    
    # --- CÁLCULO DE SUBTOTAL Y PROPINA ---
    subtotal_descontado = grand_subtotal - monto_dcto_consumos
    
    if monto_dcto_consumos > 0:
        print(f"{'SUBTOTAL:':<{LABEL_WIDTH}} R$ {subtotal_descontado:>{VALUE_FORMAT_WIDTH}.2f}")
    
    propina = subtotal_descontado * 0.10
    print(f"{'PROPINA (10%):':<{LABEL_WIDTH}} R$ {propina:>{VALUE_FORMAT_WIDTH}.2f}")

    total_con_propina = subtotal_descontado + propina
    
    if descuento_str and lugar == 'final':
        print("-" * LINE_WIDTH)
        print(f"{'SUBTOTAL + PROPINA:':<{LABEL_WIDTH}} R$ {total_con_propina:>{VALUE_FORMAT_WIDTH}.2f}")

    # --- DESCUENTO FINAL (Si aplica) ---
    if descuento_str and lugar == 'final':
        # Se asume que 'tipo' y 'valor' están definidos si 'lugar' es 'final'
        if tipo == 'pct':
            monto_dcto_final = total_con_propina * (valor / 100.0)
            dcto_descripcion_final = f"DESCUENTO ({valor}%)"
            dcto_log += f"Descuento Final: {valor}% "
        elif tipo == 'valor':
            monto_dcto_final = valor
            monto_dcto_final = min(monto_dcto_final, total_con_propina) 
            dcto_descripcion_final = f"DESCUENTO (R$ {valor:.2f})"
            dcto_log += f"Descuento Final: R${valor:.2f} "
        
        if monto_dcto_final > 0:
            monto_negativo_dcto_final = -1 * float(monto_dcto_final)
            print(f"{dcto_descripcion_final:<{LABEL_WIDTH}} R$ {monto_negativo_dcto_final:>{VALUE_FORMAT_WIDTH}.2f}")

    # --- TOTAL FINAL PENDIENTE ---
    total_pendiente = total_con_propina - monto_dcto_final
    print("=" * LINE_WIDTH)
    print(f"{'TOTAL PENDIENTE:':<{LABEL_WIDTH}} R$ {total_pendiente:>{VALUE_FORMAT_WIDTH}.2f}")
    print("=" * LINE_WIDTH)
    
    return total_pendiente, propina, grand_subtotal, dcto_log

def _manejar_pago_y_registro(numero_huesped, registro_actual, total_pendiente, grand_subtotal, propina, dcto_log):
    """
    Maneja la interacción con el usuario para el pago y actualiza la BD.
    Retorna (True/False, registro_final).
    """
    separador = "\n---\n"
    
    respuesta_pago = pedir_confirmacion("\n⚠️ ¿Querés marcar estos consumos como pagados? (si/no): ")
    
    if respuesta_pago == "si":
        try:
            with db.transaccion():
                # Marcar consumos como pagados
                db.ejecutar("UPDATE CONSUMOS SET PAGADO = 1 WHERE HUESPED = ? AND PAGADO = 0", (numero_huesped,))
                
                # Actualizar registro del huésped (registro de pago)
                registro_pago = (
                    f"Se marcaron como pagados consumos e incluyó propina. {dcto_log}"
                    f"Total cobrado: R{total_pendiente:.2f} "
                    f"(Consumos Bruto: R{grand_subtotal:.2f}; Propina: R{propina:.2f}). "
                    f"- {marca_de_tiempo()}"
                )
                nuevo_registro = registro_actual + separador + registro_pago
                _editar_huesped_db(numero_huesped, {"REGISTRO": nuevo_registro}) 
            
            print("\n✔ Todos los consumos pendientes fueron marcados como pagados.")
            return True, nuevo_registro
        
        except Exception as e:
            print(f"\n❌ Error al marcar consumos como pagados: {e}")
            print("\n❌ Cierre cancelado debido a un error de pago.")
            return False, None 
            
    else:
        # Preguntar si desea cerrar aun con deuda
        confirmar_cierre = pedir_confirmacion("\n⚠️ ¿Querés cerrar la habitación con consumos impagos? (si/no): ")
        if confirmar_cierre != "si":
            print("\n❌ Cierre cancelado.")
            return False, None
            
        # Registra la acción de cierre con deuda
        registro_impago = f"ADVERTENCIA: Habitación cerrada con deuda pendiente (Total Final: R{total_pendiente:.2f}). {dcto_log} - {marca_de_tiempo()}"
        nuevo_registro_con_adv = registro_actual + separador + registro_impago
        
        print(f"\n✅ Habitación marcada para cierre. Se ha registrado la deuda pendiente (R {total_pendiente:.2f}).")
        
        return True, nuevo_registro_con_adv

@usuarios.requiere_acceso(1)
def buscar_huesped():
    opciones = {
        1: ("APELLIDO", lambda: pedir_nombre("Ingresá el apellido: ")),
        2: ("NOMBRE", lambda: pedir_nombre("Ingresá el nombre: ")),
        3: ("NUMERO", lambda: input("Ingresá el número de huesped: ").strip()),
        4: ("HABITACION", lambda: input("Ingresá el número de habitación: ").strip()),
        5: ("DOCUMENTO", lambda: input("Ingresá el número de documento: ").strip()),
        6: ("*", None)  # Ver todos
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
            fecha_busqueda = None
            input_ok = True # Flag para la validación de input

            if campo == "HABITACION":
                num_habitacion = get_valor()
                if not num_habitacion:
                    print("\n⚠️  El número de habitación no puede estar vacío.")
                    continue
                # Delegamos la lógica compleja de HABITACION
                huesped, fecha_busqueda = _buscar_por_habitacion_y_fecha(db, num_habitacion)
                if huesped is None and fecha_busqueda is None: # Cancelación
                    return 
            
            elif campo == "*":
                huespedes = db.obtener_todos("SELECT * FROM HUESPEDES ORDER BY LOWER(APELLIDO), LOWER(NOMBRE)")
                
            elif campo in ("APELLIDO", "NOMBRE"):
                # Delegamos la lógica de búsqueda por texto
                huespedes = _buscar_por_nombre_o_apellido(db, campo, get_valor)
                if huespedes is None: # Cancelación
                    return 
            
            else: # NUMERO o DOCUMENTO
                # Delegamos la lógica de búsqueda exacta
                input_ok, huesped = _buscar_por_exacto(db, campo, get_valor)
                if not input_ok:
                    continue # Vuelve a pedir la opción si el input falló
            
            # --- Lógica de Impresión de Resultados ---
            
            # Caso de búsqueda por HABITACION (ya que sale inmediatamente después)
            if campo == "HABITACION":
                if huesped:
                    print(f"\n✔ Huésped encontrado en la habitación {num_habitacion} el {formatear_fecha(fecha_busqueda)}.")
                    imprimir_huesped(huesped)
                else:
                    print(f"\n❌ La habitación {num_habitacion} no estaba ocupada el {formatear_fecha(fecha_busqueda)}.")
                return # Terminamos la función ya que es una búsqueda específica

            # Casos de búsqueda que devuelven listas o un solo resultado
            if huespedes:
                print("\nListado de huéspedes:")
                imprimir_huespedes(huespedes)
            elif huesped:
                imprimir_huesped(huesped)
            else:
                print("\n❌ No se encontraron coincidencias.")
            
            break # Sale del while True después de mostrar el resultado
            
        else:
            print("\n⚠️  Opción inválida. Intente nuevamente.")
    return

def _buscar_por_habitacion_y_fecha(num_habitacion):
    """Maneja la lógica de búsqueda compleja por HABITACION y FECHA."""
    
    # Pedir la fecha para verificar la estadía (manteniendo la lógica original)
    print("\n📅 Ahora ingresá la fecha para verificar la ocupación.")
    # NOTA: Debes asegurar que las funciones 'pedir_fecha_valida', 'formatear_fecha', etc.,
    # estén accesibles en tu entorno.
    fecha_busqueda = pedir_fecha_valida(
        "Ingresá la fecha para verificar ocupación ó (0) para cancelar: ", 
        allow_past=True, # Permitir buscar en fechas pasadas
        confirmacion=False, # No preguntar si es fecha pasada, solo obtenerla
        cero=True, # Permite cancelar con '0'
        vacio = True
    )
    
    if fecha_busqueda is None:
        # El usuario ingresó '0'
        print("\n❌ Búsqueda cancelada.")
        return None, None # Devuelve (huésped, fecha)

    # Si la cadena está vacía, usamos la fecha de hoy
    if fecha_busqueda == "":
        fecha_busqueda = date.today().isoformat()

    # La consulta original (con la única mejora de seguridad de usar DATE()
    # que es crítica para esta operación de rango)
    query = """
        SELECT * FROM HUESPEDES 
        WHERE HABITACION = ? 
          AND DATE(CHECKIN) <= DATE(?) 
          AND (DATE(CHECKOUT) >= DATE(?) OR ESTADO = 'ABIERTO') 
          AND ESTADO != 'CERRADO'
        ORDER BY CHECKIN DESC
        LIMIT 1
    """
    
    huesped = db.obtener_uno(query, (num_habitacion, fecha_busqueda, fecha_busqueda))
    return huesped, fecha_busqueda

def _buscar_por_nombre_o_apellido(campo, get_valor):
    """Maneja la lógica de búsqueda por texto (LIKE + unidecode)."""
    # NOTA: La función 'unidecode' debe estar disponible.
    valor_normalizado = get_valor()
    if valor_normalizado is None: # Si el usuario canceló
        return None
        
    # 1. Búsqueda en SQL: Traer un subconjunto usando LIKE
    query = f"SELECT * FROM HUESPEDES WHERE LOWER({campo}) LIKE ?"
    patron_sql = f"%{valor_normalizado}%"
    huespedes_amplio = db.obtener_todos(query, (patron_sql,))
    
    # 2. Filtrado final en Python: Asegurar coincidencia de tildes
    huespedes = [
        h for h in huespedes_amplio
        if valor_normalizado in unidecode(h[campo]).lower()
    ]
    return huespedes

def _buscar_por_exacto(campo, get_valor):
    """Maneja la lógica de búsqueda exacta por NUMERO o DOCUMENTO."""
    valor_raw = get_valor()
    if not valor_raw:
        print("\n⚠️  El valor de búsqueda no puede estar vacío.")
        return False, None # Indica error en el input, no en la BD

    query = f"SELECT * FROM HUESPEDES WHERE {campo} = ?"
    return True, db.obtener_uno(query, (valor_raw,)) # Devuelve (éxito_input, huésped)

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

@usuarios.requiere_acceso(1)
def editar_huesped():
    leyenda = "\nIngresá el número de huésped que querés editar, (*) para buscar ó (0) para cancelar: "
    while True:
        numero = opcion_menu(leyenda, cero=True, asterisco=True, minimo=1)
        if numero == "*":
            buscar_huesped()
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
            "(4) Email,       (5) App,     (6) Checkin,\n"
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
                print(f"✔ {campo_sql} actualizado correctamente a {nuevo_valor}.")
            except ValueError as e:
                print(f"\n{e}")
            except Exception as e:
                print(f"Error al actualizar {campo_sql}: {e}")
            break
        else:
            print("\n❌ Opción inválida. Intente nuevamente.")

    return

def ver_programados():
    huespedes = db.obtener_todos("SELECT * FROM HUESPEDES WHERE ESTADO = 'PROGRAMADO' ORDER BY CHECKIN, CHECKOUT")
    if huespedes:
        print("\nListado de huéspedes:")
        imprimir_huespedes(huespedes)
    else:
        print("\n❌ No se encontraron coincidencias.")

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
                        f"| Email: {huesped['EMAIL']} | Aplicativo: {huesped['APP']} | "
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




