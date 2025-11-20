# -*- coding: utf-8 -*-
"""
Created on Sat Nov  1 21:11:49 2025
Updated full version with:
 - Reorganización de pestañas según requerimientos
 - Nueva funcionalidad de Consulta de Clientes
 - Cambio de Próximos Vencimientos a Renovaciones
 - Todas las secciones originales mejoradas
"""

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import re
from dateutil.relativedelta import relativedelta

# Configuración de la página
st.set_page_config(
    page_title="Gestor de Cartera Rizkora",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Opciones
OPCIONES_PRODUCTO = [
    "GMMI", "GMMC", "API", "APE", "APC", "VPL", "OV", "PPR",
    "EDUCACIONAL", "AHORRO", "TEMPORAL", "VG", "AUTO", "FLOTILLA", "HOGAR", "VIAJERO", "DAÑOS", "PENDIENTE"
]
OPCIONES_PAGO = ["PAGO REFERENCIADO", "TRANSFERENCIA", "CARGO TDC", "CARGO TDD"]
OPCIONES_ASEG = ["AXA", "ALLIANZ", "ATLAS", "BANORTE", "ZURICH", "GNP", "HIR", "QUALITAS"]
OPCIONES_BANCO = ["NINGUNO", "AMERICAN EXPRESS", "BBVA", "BANCOMER", "BANREGIO", "HSBC", "SANTANDER"]
OPCIONES_PERSONA = ["MORAL", "FÍSICA"]
OPCIONES_MONEDA = ["MXN", "UDIS", "DLLS"]
OPCIONES_ESTATUS_SEGUIMIENTO = ["Seguimiento", "Descartado", "Convertido"]
OPCIONES_ESTADO_POLIZA = ["VIGENTE", "CANCELADO", "TERMINADO"]

# Inicializar estado de sesión
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "👥 Prospectos"

# Configuración de Google Sheets
@st.cache_resource(ttl=3600)
def init_google_sheets():
    """Inicializa la conexión con Google Sheets con manejo de errores"""
    try:
        if 'google_service_account' not in st.secrets:
            st.error("❌ No se encontró 'google_service_account' en los secrets de Streamlit")
            return None

        creds = Credentials.from_service_account_info(
            st.secrets["google_service_account"],
            scopes=["https://www.googleapis.com/auth/spreadsheets",
                    "https://www.googleapis.com/auth/drive"]
        )

        client = gspread.authorize(creds)
        return client

    except Exception as e:
        st.error(f"❌ Error al autenticar con Google Sheets: {str(e)}")
        return None

# Inicializar cliente
client = init_google_sheets()
if client is None:
    st.stop()

@st.cache_resource(ttl=3600)
def conectar_google_sheets():
    """Conectar a la hoja base_polizas_ealc"""
    try:
        spreadsheet = client.open("base_polizas_ealc")
        return spreadsheet
    except Exception as e:
        st.error(f"❌ Error al conectar con la hoja 'base_polizas_ealc': {str(e)}")
        st.info("ℹ️ Asegúrate de que la hoja 'base_polizas_ealc' exista y esté compartida con el service account")
        return None

# Función para cargar datos con cache
@st.cache_data(ttl=300)
def cargar_datos():
    """Cargar datos desde Google Sheets"""
    try:
        spreadsheet = conectar_google_sheets()
        if not spreadsheet:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # Cargar hojas existentes
        try:
            worksheet_prospectos = spreadsheet.worksheet("Prospectos")
            df_prospectos = pd.DataFrame(worksheet_prospectos.get_all_records())
        except Exception as e:
            st.error(f"❌ Error al cargar hoja 'Prospectos': {e}")
            df_prospectos = pd.DataFrame(columns=[
                "Tipo Persona", "Nombre/Razón Social", "Fecha Nacimiento", "RFC", "Teléfono",
                "Correo", "Producto", "Fecha Registro", "Fecha Contacto", "Seguimiento",
                "Representantes Legales", "Referenciador", "Estatus", "Comentarios", "Dirección"
            ])

        try:
            worksheet_polizas = spreadsheet.worksheet("Polizas")
            df_polizas = pd.DataFrame(worksheet_polizas.get_all_records())
            if not df_polizas.empty and "No. Póliza" in df_polizas.columns:
                df_polizas["No. Póliza"] = df_polizas["No. Póliza"].astype(str).str.strip()
        except Exception as e:
            st.error(f"❌ Error al cargar hoja 'Polizas': {e}")
            df_polizas = pd.DataFrame(columns=[
                "Tipo Persona", "Nombre/Razón Social", "No. Póliza", "Producto", "Inicio Vigencia",
                "Fin Vigencia", "RFC", "Forma de Pago", "Banco", "Periodicidad", "Prima Total Emitida",
                "Prima Neta", "Primer Pago", "Pagos Subsecuentes", "Aseguradora", "% Comisión", "Estado", "Contacto", "Dirección",
                "Teléfono", "Correo", "Fecha Nacimiento", "Moneda", "Referenciador", "Clave de Emisión"
            ])

        try:
            worksheet_cobranza = spreadsheet.worksheet("Cobranza")
            df_cobranza = pd.DataFrame(worksheet_cobranza.get_all_records())
        except Exception as e:
            df_cobranza = pd.DataFrame(columns=[
                "No. Póliza", "Mes Cobranza", "Prima de Recibo", "Monto Pagado",  # Cambiado Monto Esperado por Prima de Recibo
                "Fecha Pago", "Estatus", "Días Atraso", "Fecha Vencimiento", "Nombre/Razón Social", "Días Restantes",
                "Periodicidad", "Moneda", "Recibo", "Clave de Emisión"
            ])
 
        try:
             worksheet_seguimiento = spreadsheet.worksheet("Seguimiento")
             df_seguimiento = pd.DataFrame(worksheet_seguimiento.get_all_records())
        except Exception as e:
             df_seguimiento = pd.DataFrame(columns=[
                 "Nombre/Razón Social", "Fecha Contacto", "Estatus", "Comentarios", "Fecha Registro"
             ])
 
        return df_prospectos, df_polizas, df_cobranza, df_seguimiento

    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# Función para guardar datos (invalida el cache)
def guardar_datos(df_prospectos=None, df_polizas=None, df_cobranza=None, df_seguimiento=None):
    """Guardar datos en Google Sheets e invalidar cache"""
    try:
        spreadsheet = conectar_google_sheets()
        if not spreadsheet:
            return False

        # Actualizar hoja de Prospectos si se proporciona
        if df_prospectos is not None:
            try:
                worksheet_prospectos = spreadsheet.worksheet("Prospectos")
                worksheet_prospectos.clear()
                if not df_prospectos.empty:
                    data = [df_prospectos.columns.values.tolist()] + df_prospectos.fillna('').values.tolist()
                    worksheet_prospectos.update(data, value_input_option='USER_ENTERED')
            except Exception as e:
                st.error(f"❌ Error al actualizar hoja 'Prospectos': {e}")
                return False

        # Actualizar hoja de Pólizas si se proporciona
        if df_polizas is not None:
            try:
                worksheet_polizas = spreadsheet.worksheet("Polizas")
                worksheet_polizas.clear()
                if not df_polizas.empty:
                    data = [df_polizas.columns.values.tolist()] + df_polizas.fillna('').values.tolist()
                    worksheet_polizas.update(data, value_input_option='USER_ENTERED')
            except Exception as e:
                st.error(f"❌ Error al actualizar hoja 'Polizas': {e}")
                return False

        # Actualizar hoja de Cobranza si se proporciona
        if df_cobranza is not None:
           try:
              worksheet_cobranza = spreadsheet.worksheet("Cobranza")
              worksheet_cobranza.clear()
              if not df_cobranza.empty:
                  data = [df_cobranza.columns.values.tolist()] + df_cobranza.fillna('').values.tolist()
                  worksheet_cobranza.update(data, value_input_option='USER_ENTERED')
           except:
              # Crear hoja si no existe
              try:
                  worksheet_cobranza = spreadsheet.add_worksheet(title="Cobranza", rows=1000, cols=20)
                  if not df_cobranza.empty:
                      data = [df_cobranza.columns.values.tolist()] + df_cobranza.fillna('').values.tolist()
                      worksheet_cobranza.update(data, value_input_option='USER_ENTERED')
              except Exception as e:
                  st.error(f"❌ Error al crear/actualizar hoja 'Cobranza': {e}")

        # Actualizar hoja de Seguimiento si se proporciona
        if df_seguimiento is not None:
            try:
                worksheet_seguimiento = spreadsheet.worksheet("Seguimiento")
                worksheet_seguimiento.clear()
                if not df_seguimiento.empty:
                    data = [df_seguimiento.columns.values.tolist()] + df_seguimiento.fillna('').values.tolist()
                    worksheet_seguimiento.update(data, value_input_option='USER_ENTERED')
            except:
                # Crear hoja si no existe
                try:
                    worksheet_seguimiento = spreadsheet.add_worksheet(title="Seguimiento", rows=1000, cols=20)
                    if not df_seguimiento.empty:
                        data = [df_seguimiento.columns.values.tolist()] + df_seguimiento.fillna('').values.tolist()
                        worksheet_seguimiento.update(data, value_input_option='USER_ENTERED')
                except Exception as e:
                    st.error(f"❌ Error al crear/actualizar hoja 'Seguimiento': {e}")

        # Invalidar cache para forzar recarga
        st.cache_data.clear()
        return True

    except Exception as e:
        st.error(f"Error guardando datos: {e}")
        return False

# Función para validar formato de fecha
def validar_fecha(fecha_str):
    """Validar que la fecha tenga formato dd/mm/yyyy"""
    if not fecha_str or pd.isna(fecha_str) or fecha_str == "":
        return True, ""

    fecha_str = str(fecha_str).strip()

    patron = r'^\d{1,2}/\d{1,2}/\d{4}$'
    if re.match(patron, fecha_str):
        try:
            dia, mes, anio = map(int, fecha_str.split('/'))
            datetime(anio, mes, dia)
            return True, ""
        except ValueError:
            return False, "La fecha no es válida (ejemplo: 15/03/1990)"
    else:
        return False, "Formato incorrecto. Use dd/mm/yyyy (ejemplo: 15/03/1990)"

# Función para obtener fecha actual en formato texto
def fecha_actual():
    return datetime.now().strftime("%d/%m/%Y")

# =========================
# 🔧 FUNCIÓN CALCULAR_COBRANZA (Versión final mejorada)
# =========================
def calcular_cobranza():
    """
    Calcula los registros de cobranza basándose en las pólizas vigentes.
    - Toma la fecha de Inicio Vigencia como primer pago
    - Para periodicidad ANUAL: genera un solo registro anual
    - Para otras periodicidades: genera múltiples registros según la periodicidad
    - Usa Primer Pago para el primer registro y Pagos Subsecuentes para los siguientes
    - Evita duplicados verificando por No. Póliza y número de recibo
    """
    try:
        _, df_polizas, df_cobranza, _ = cargar_datos()

        if df_polizas.empty:
            return pd.DataFrame()

        # Filtrar pólizas vigentes
        df_vigentes = df_polizas[df_polizas["Estado"].astype(str).str.upper() == "VIGENTE"]
        if df_vigentes.empty:
            return pd.DataFrame()

        hoy = datetime.now()
        fecha_limite = hoy + timedelta(days=60)
        cobranza_mes = []

        # Función auxiliar para limpiar montos
        def parse_monto(valor):
            if pd.isna(valor) or str(valor).strip() == "":
                return 0.0
            valor = str(valor).replace('$', '').replace(',', '').replace(' ', '').strip()
            try:
                return float(valor)
            except:
                return 0.0

        # Función para convertir fechas de manera segura
        def safe_date_convert(date_str):
            if pd.isna(date_str) or not date_str:
                return None
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                try:
                    return datetime.strptime(str(date_str).strip(), fmt)
                except ValueError:
                    continue
            return None

        for _, poliza in df_vigentes.iterrows():
            no_poliza = str(poliza.get("No. Póliza", "")).strip()
            periodicidad = str(poliza.get("Periodicidad", "")).upper().strip()
            moneda = poliza.get("Moneda", "MXN")
            
            # Limpiar montos
            primer_pago = parse_monto(poliza.get("Primer Pago", 0))
            pagos_subsecuentes = parse_monto(poliza.get("Pagos Subsecuentes", 0))
            
            # Si no hay pago subsecuente, usar el primer pago como default
            if pagos_subsecuentes == 0:
                pagos_subsecuentes = primer_pago

            inicio_vigencia_str = poliza.get("Inicio Vigencia", "")
            if not no_poliza or not inicio_vigencia_str:
                continue

            # Convertir fecha de inicio de vigencia
            inicio_vigencia = safe_date_convert(inicio_vigencia_str)
            if inicio_vigencia is None:
                continue

            fecha_actual_calc = inicio_vigencia
            num_recibo = 1
            max_recibos = 24  # Aumentamos el límite para cubrir 2 años completos

            while num_recibo <= max_recibos:
                # Solo incluir pagos en el rango relevante (10 días atrás y 60 adelante)
                if (hoy - timedelta(days=10)) <= fecha_actual_calc <= fecha_limite:
                    mes_cobranza = fecha_actual_calc.strftime("%m/%Y")
                    fecha_vencimiento = fecha_actual_calc.strftime("%d/%m/%Y")

                    # Verificar si ya existe este registro en cobranza usando No. Póliza + Recibo
                    existe_registro = False
                    if not df_cobranza.empty and "No. Póliza" in df_cobranza.columns and "Recibo" in df_cobranza.columns:
                        existe_registro = (
                            (df_cobranza["No. Póliza"].astype(str).str.strip() == no_poliza) &
                            (df_cobranza["Recibo"] == num_recibo)
                        ).any()

                    if not existe_registro:
                        # Determinar monto según el número de recibo
                        if num_recibo == 1:
                            monto_prima = primer_pago
                        else:
                            monto_prima = pagos_subsecuentes

                        dias_restantes = (fecha_actual_calc - hoy).days

                        cobranza_mes.append({
                            "No. Póliza": no_poliza,
                            "Nombre/Razón Social": poliza.get("Nombre/Razón Social", ""),
                            "Mes Cobranza": mes_cobranza,
                            "Fecha Vencimiento": fecha_vencimiento,
                            "Prima de Recibo": monto_prima,
                            "Monto Pagado": 0,
                            "Fecha Pago": "",
                            "Estatus": "Pendiente",
                            "Días Restantes": dias_restantes,
                            "Periodicidad": periodicidad,
                            "Moneda": moneda,
                            "Recibo": num_recibo,
                            "ID_Cobranza": f"{no_poliza}_R{num_recibo}"  # Identificador único
                        })

                # Avanzar a la siguiente fecha según periodicidad
                if periodicidad == "ANUAL":
                    # Para anual, solo generamos un registro y salimos
                    if num_recibo == 1:
                        fecha_actual_calc += relativedelta(years=1)
                    else:
                        break
                elif periodicidad == "TRIMESTRAL":
                    fecha_actual_calc += relativedelta(months=3)
                elif periodicidad == "SEMESTRAL":
                    fecha_actual_calc += relativedelta(months=6)
                elif periodicidad == "MENSUAL":
                    fecha_actual_calc += relativedelta(months=1)
                else:
                    # Por defecto mensual
                    fecha_actual_calc += relativedelta(months=1)

                num_recibo += 1

                # Para anual, solo generamos un pago por año en el rango
                if periodicidad == "ANUAL" and num_recibo > 1:
                    break

        # Crear DataFrame
        df_resultado = pd.DataFrame(cobranza_mes)
        if df_resultado.empty:
            return df_resultado

        # Eliminar duplicados por ID único
        df_resultado = df_resultado.drop_duplicates(
            subset=["ID_Cobranza"], 
            keep="last"
        )

        print(f"✅ Cobranza generada: {len(df_resultado)} registros")
        return df_resultado

    except Exception as e:
        st.error(f"Error al calcular cobranza: {e}")
        import traceback
        st.error(f"Detalle del error: {traceback.format_exc()}")
        return pd.DataFrame()

# Función para manejar el cambio de pestaña
def cambiar_pestaña(nombre_pestaña):
    st.session_state.active_tab = nombre_pestaña

# ---- Funciones para cada pestaña (completas) ----

# 1. Prospectos
def mostrar_prospectos(df_prospectos, df_polizas):
    st.header("👥 Gestión de Prospectos")

    # --- Inicializar estado para la edición ---
    if 'modo_edicion_prospectos' not in st.session_state:
        st.session_state.modo_edicion_prospectos = False
    if 'prospecto_editando' not in st.session_state:
        st.session_state.prospecto_editando = None
    if 'prospecto_data' not in st.session_state:
        st.session_state.prospecto_data = {}

    # --- Selector para editar prospecto existente ---
    if not df_prospectos.empty:
        prospectos_lista = df_prospectos["Nombre/Razón Social"].dropna().tolist()
        prospecto_seleccionado = st.selectbox(
            "Seleccionar Prospecto para editar",
            [""] + prospectos_lista,
            key="select_editar_prospecto"
        )

        # Botones para cargar datos o limpiar selección
        if prospecto_seleccionado:
            col_btn1, col_btn2 = st.columns([1, 1])
            with col_btn1:
                if st.button("📝 Cargar Datos para Editar", use_container_width=True, key="btn_cargar_datos"):
                    # Buscar y cargar datos del prospecto
                    fila = df_prospectos[df_prospectos["Nombre/Razón Social"] == prospecto_seleccionado]
                    if not fila.empty:
                        fila = fila.iloc[0]
                        st.session_state.prospecto_data = fila.to_dict()
                        st.session_state.prospecto_editando = prospecto_seleccionado
                        st.session_state.modo_edicion_prospectos = True
                        st.rerun()

            with col_btn2:
                if st.button("❌ Limpiar selección", use_container_width=True, key="btn_limpiar_seleccion"):
                    # Limpiar estado
                    st.session_state.prospecto_editando = None
                    st.session_state.modo_edicion_prospectos = False
                    st.session_state.prospecto_data = {}
                    st.rerun()

            # Mostrar información del prospecto seleccionado
            if st.session_state.prospecto_editando == prospecto_seleccionado:
                st.info(f"**Editando:** {prospecto_seleccionado}")
    else:
        st.info("No hay prospectos registrados")

    # --- Botón para cancelar edición ---
    if st.session_state.modo_edicion_prospectos:
        if st.button("❌ Cancelar Edición", key="btn_cancelar_edicion_global"):
            st.session_state.prospecto_editando = None
            st.session_state.modo_edicion_prospectos = False
            st.session_state.prospecto_data = {}
            st.rerun()

    # --- FORMULARIO PRINCIPAL ---
    with st.form("form_prospectos", clear_on_submit=True):
        st.subheader("📝 Formulario de Prospecto")
        
        # Mostrar información de edición
        if st.session_state.modo_edicion_prospectos and st.session_state.prospecto_editando:
            st.info(f"Editando: **{st.session_state.prospecto_editando}**")

        col1, col2 = st.columns(2)

        with col1:
            # Tipo Persona - usar valor actual o vacío
            tipo_persona_val = st.session_state.prospecto_data.get("Tipo Persona", "")
            tipo_persona_index = OPCIONES_PERSONA.index(tipo_persona_val) if tipo_persona_val in OPCIONES_PERSONA else 0
            tipo_persona = st.selectbox(
                "Tipo Persona", 
                OPCIONES_PERSONA, 
                index=tipo_persona_index
            )

            # Nombre/Razón Social
            nombre_razon = st.text_input(
                "Nombre/Razón Social*", 
                value=st.session_state.prospecto_data.get("Nombre/Razón Social", "")
            )

            # Fecha Nacimiento
            fecha_nacimiento = st.text_input(
                "Fecha Nacimiento (dd/mm/yyyy)", 
                value=st.session_state.prospecto_data.get("Fecha Nacimiento", ""),
                placeholder="dd/mm/yyyy"
            )

            # RFC
            rfc = st.text_input(
                "RFC", 
                value=st.session_state.prospecto_data.get("RFC", "")
            )

            # Teléfono
            telefono = st.text_input(
                "Teléfono", 
                value=st.session_state.prospecto_data.get("Teléfono", "")
            )

            # Correo
            correo = st.text_input(
                "Correo", 
                value=st.session_state.prospecto_data.get("Correo", "")
            )

        with col2:
            # Producto
            producto_val = st.session_state.prospecto_data.get("Producto", "")
            producto_index = OPCIONES_PRODUCTO.index(producto_val) if producto_val in OPCIONES_PRODUCTO else 0
            producto = st.selectbox(
                "Producto", 
                OPCIONES_PRODUCTO, 
                index=producto_index
            )

            # Fecha Registro
            fecha_registro = st.text_input(
                "Fecha Registro*", 
                value=st.session_state.prospecto_data.get("Fecha Registro", fecha_actual()),
                placeholder="dd/mm/yyyy"
            )

            # Fecha Contacto
            fecha_contacto = st.text_input(
                "Fecha Contacto (dd/mm/yyyy)", 
                value=st.session_state.prospecto_data.get("Fecha Contacto", ""),
                placeholder="dd/mm/yyyy"
            )

            # Seguimiento
            seguimiento = st.text_input(
                "Seguimiento (dd/mm/yyyy)", 
                value=st.session_state.prospecto_data.get("Seguimiento", ""),
                placeholder="dd/mm/yyyy"
            )

            # Representantes Legales
            representantes = st.text_area(
                "Representantes Legales (separar por comas)", 
                value=st.session_state.prospecto_data.get("Representantes Legales", ""),
                placeholder="Ej: Juan Pérez, María García"
            )

            # Referenciador
            referenciador = st.text_input(
                "Referenciador", 
                value=st.session_state.prospecto_data.get("Referenciador", ""),
                placeholder="Origen del cliente/promoción"
            )

            # Dirección
            direccion = st.text_input(
                "Dirección", 
                value=st.session_state.prospecto_data.get("Dirección", ""),
                placeholder="Ej: Calle 123, CDMX, 03100"
            )

        # --- VALIDACIONES DE FECHAS ---
        fecha_errors = []
        
        if fecha_nacimiento:
            valido, error = validar_fecha(fecha_nacimiento)
            if not valido:
                fecha_errors.append(f"Fecha Nacimiento: {error}")

        if fecha_registro:
            valido, error = validar_fecha(fecha_registro)
            if not valido:
                fecha_errors.append(f"Fecha Registro: {error}")
        else:
            fecha_errors.append("Fecha Registro es obligatoria")

        if fecha_contacto:
            valido, error = validar_fecha(fecha_contacto)
            if not valido:
                fecha_errors.append(f"Fecha Contacto: {error}")

        if seguimiento:
            valido, error = validar_fecha(seguimiento)
            if not valido:
                fecha_errors.append(f"Seguimiento: {error}")

        # Mostrar errores de fecha
        if fecha_errors:
            for error in fecha_errors:
                st.error(error)

        # --- BOTONES DEL FORMULARIO ---
        col_b1, col_b2 = st.columns(2)
        
        with col_b1:
            # Botón de envío principal - SIEMPRE debe estar presente
            if st.session_state.modo_edicion_prospectos:
                submit_button = st.form_submit_button("💾 Actualizar Prospecto", use_container_width=True)
            else:
                submit_button = st.form_submit_button("💾 Agregar Nuevo Prospecto", use_container_width=True)
        
        with col_b2:
            # Botón de cancelar secundario
            cancel_button = st.form_submit_button("🚫 Cancelar", use_container_width=True, type="secondary")

        # --- PROCESAR BOTÓN CANCELAR ---
        if cancel_button:
            st.session_state.prospecto_editando = None
            st.session_state.modo_edicion_prospectos = False
            st.session_state.prospecto_data = {}
            st.rerun()

        # --- PROCESAR BOTÓN DE ENVÍO ---
        if submit_button:
            if not nombre_razon.strip():
                st.warning("Debe completar al menos el nombre o razón social")
            elif fecha_errors:
                st.warning("Corrija los errores en las fechas antes de guardar")
            else:
                # Crear objeto con los datos del prospecto
                nuevo_prospecto = {
                    "Tipo Persona": tipo_persona,
                    "Nombre/Razón Social": nombre_razon.strip(),
                    "Fecha Nacimiento": fecha_nacimiento,
                    "RFC": rfc,
                    "Teléfono": telefono,
                    "Correo": correo,
                    "Dirección": direccion,
                    "Producto": producto,
                    "Fecha Registro": fecha_registro if fecha_registro else fecha_actual(),
                    "Fecha Contacto": fecha_contacto,
                    "Seguimiento": seguimiento,
                    "Representantes Legales": representantes,
                    "Referenciador": referenciador
                }

                if st.session_state.modo_edicion_prospectos and st.session_state.prospecto_editando:
                    # ACTUALIZAR prospecto existente
                    index = df_prospectos[df_prospectos["Nombre/Razón Social"] == st.session_state.prospecto_editando].index
                    if not index.empty:
                        for key, value in nuevo_prospecto.items():
                            df_prospectos.loc[index, key] = value
                        mensaje = "✅ Prospecto actualizado correctamente"
                    else:
                        st.error("❌ No se encontró el prospecto a actualizar")
                        return
                else:
                    # AGREGAR nuevo prospecto
                    df_prospectos = pd.concat([df_prospectos, pd.DataFrame([nuevo_prospecto])], ignore_index=True)
                    mensaje = "✅ Prospecto agregado correctamente"

                # Guardar cambios
                if guardar_datos(df_prospectos=df_prospectos, df_polizas=df_polizas):
                    st.success(mensaje)
                    
                    # Limpiar estado después de guardar
                    st.session_state.prospecto_editando = None
                    st.session_state.modo_edicion_prospectos = False
                    st.session_state.prospecto_data = {}
                    
                    st.rerun()
                else:
                    st.error("❌ Error al guardar el prospecto")

    # --- MOSTRAR LISTA DE PROSPECTOS ---
    st.subheader("📋 Lista de Prospectos")
    if not df_prospectos.empty:
        # Mostrar columnas más relevantes
        columnas_mostrar = [
            "Nombre/Razón Social", "Producto", "Teléfono", "Correo",
            "Fecha Registro", "Referenciador"
        ]
        columnas_disponibles = [col for col in columnas_mostrar if col in df_prospectos.columns]

        if columnas_disponibles:
            st.dataframe(df_prospectos[columnas_disponibles], use_container_width=True)
        else:
            st.dataframe(df_prospectos, use_container_width=True)

        # Estadísticas
        st.subheader("📊 Estadísticas")
        col_stats1, col_stats2, col_stats3 = st.columns(3)
        with col_stats1:
            st.metric("Total Prospectos", len(df_prospectos))
        with col_stats2:
            if "Producto" in df_prospectos.columns:
                productos_unicos = df_prospectos["Producto"].nunique()
                st.metric("Productos Diferentes", productos_unicos)
        with col_stats3:
            if "Fecha Registro" in df_prospectos.columns:
                try:
                    df_temp = df_prospectos.copy()
                    df_temp['Fecha Registro DT'] = pd.to_datetime(df_temp['Fecha Registro'], dayfirst=True, errors='coerce')
                    mes_actual = datetime.now().month
                    prospectos_mes = len(df_temp[df_temp['Fecha Registro DT'].dt.month == mes_actual])
                    st.metric("Prospectos este Mes", prospectos_mes)
                except:
                    st.metric("Prospectos este Mes", "N/A")
    else:
        st.info("No hay prospectos registrados")

# 2. Seguimiento
def mostrar_seguimiento(df_prospectos, df_seguimiento):
    st.header("📞 Seguimiento de Prospectos")

    # Selector de prospecto
    if not df_prospectos.empty:
        prospectos_lista = df_prospectos["Nombre/Razón Social"].dropna().tolist()
        prospecto_seleccionado = st.selectbox("Seleccionar Prospecto", [""] + prospectos_lista, key="seguimiento_prospecto")

        if prospecto_seleccionado:
            # Buscar seguimientos existentes
            seguimientos_existentes = pd.DataFrame()
            if not df_seguimiento.empty and "Nombre/Razón Social" in df_seguimiento.columns:
                seguimientos_existentes = df_seguimiento[df_seguimiento["Nombre/Razón Social"] == prospecto_seleccionado]

            with st.form("form_seguimiento", clear_on_submit=True):
                col1, col2 = st.columns(2)

                with col1:
                    nueva_fecha_contacto = st.text_input("Nueva Fecha de Contacto (dd/mm/yyyy)*", 
                                                       value=fecha_actual(),
                                                       placeholder="dd/mm/yyyy",
                                                       key="nueva_fecha_contacto")
                    estatus = st.selectbox("Estatus", OPCIONES_ESTATUS_SEGUIMIENTO, key="estatus_seguimiento")

                with col2:
                    comentarios = st.text_area("Comentarios*", 
                                             placeholder="Anotar lo que indique el prospecto...",
                                             key="comentarios_seguimiento")

                submitted = st.form_submit_button("💾 Guardar Seguimiento")

                if submitted:
                    # Validar fecha
                    valido, error = validar_fecha(nueva_fecha_contacto)
                    if not valido:
                        st.error(f"Fecha de contacto: {error}")
                    elif not comentarios:
                        st.warning("Los comentarios son obligatorios")
                    else:
                        nuevo_seguimiento = {
                            "Nombre/Razón Social": prospecto_seleccionado,
                            "Fecha Contacto": nueva_fecha_contacto,
                            "Estatus": estatus,
                            "Comentarios": comentarios,
                            "Fecha Registro": fecha_actual()
                        }

                        df_seguimiento = pd.concat([df_seguimiento, pd.DataFrame([nuevo_seguimiento])], ignore_index=True)

                        if guardar_datos(df_seguimiento=df_seguimiento):
                            st.success("✅ Seguimiento guardado correctamente")
                            # Si el estatus es "Convertido", notificamos
                            if estatus == "Convertido":
                                st.info("ℹ️ El prospecto ha sido marcado como 'Convertido'. Puedes proceder a crear su póliza en la pestaña 'Registro de Cliente'")
                            st.rerun()
                        else:
                            st.error("❌ Error al guardar el seguimiento")

            # Mostrar historial de seguimientos
            if not seguimientos_existentes.empty:
                st.subheader("Historial de Seguimientos")
                try:
                    # Intentar ordenar por Fecha Contacto si posible
                    seguimientos_existentes = seguimientos_existentes.sort_values("Fecha Contacto", ascending=False)
                except Exception:
                    pass
                st.dataframe(seguimientos_existentes, use_container_width=True)
    else:
        st.info("No hay prospectos registrados")

    # Mostrar todos los seguimientos
    if not df_seguimiento.empty:
        st.subheader("Todos los Seguimientos")
        st.dataframe(df_seguimiento, use_container_width=True)

# 3. Registro de Cliente (Primera Póliza)
def mostrar_registro_cliente(df_prospectos, df_polizas):
    st.header("👤 Registro de Cliente (Primera Póliza)")

    # Seleccionar prospecto
    if not df_prospectos.empty:
        prospectos_lista = df_prospectos["Nombre/Razón Social"].dropna().tolist()
        prospecto_seleccionado = st.selectbox("Seleccionar Prospecto", [""] + prospectos_lista, key="registro_cliente")

        if prospecto_seleccionado:
            # Cargar datos del prospecto seleccionado
            prospecto_data = df_prospectos[df_prospectos["Nombre/Razón Social"] == prospecto_seleccionado].iloc[0]

            with st.form("form_registro_cliente", clear_on_submit=True):
                st.subheader(f"Creando Primera Póliza para: {prospecto_seleccionado}")

                col1, col2 = st.columns(2)

                with col1:
                    st.text_input("Tipo Persona", value=prospecto_data.get("Tipo Persona", ""), key="registro_tipo", disabled=True)
                    st.text_input("Nombre/Razón Social", value=prospecto_data.get("Nombre/Razón Social", ""), key="registro_nombre", disabled=True)
                    no_poliza = st.text_input("No. Póliza*", key="registro_numero")
                    producto_poliza = st.selectbox("Producto", OPCIONES_PRODUCTO, 
                                          index=OPCIONES_PRODUCTO.index(prospecto_data.get("Producto", "")) 
                                          if prospecto_data.get("Producto") in OPCIONES_PRODUCTO else 0,
                                          key="registro_producto")
                    inicio_vigencia = st.text_input("Inicio Vigencia (dd/mm/yyyy)*", 
                                                  placeholder="dd/mm/yyyy",
                                                  key="registro_inicio")
                    fin_vigencia = st.text_input("Fin Vigencia (dd/mm/yyyy)*", 
                                               placeholder="dd/mm/yyyy",
                                               key="registro_fin")
                    rfc_poliza = st.text_input("RFC", value=prospecto_data.get("RFC", ""), key="registro_rfc")
                    forma_pago = st.selectbox("Forma de Pago", OPCIONES_PAGO, key="registro_pago")
                    moneda = st.selectbox("Moneda", OPCIONES_MONEDA, key="registro_moneda")

                with col2:
                    banco = st.selectbox("Banco", OPCIONES_BANCO, key="registro_banco")
                    periodicidad = st.selectbox("Periodicidad", ["ANUAL", "MENSUAL", "TRIMESTRAL", "SEMESTRAL"], key="registro_periodicidad")
                    prima_total_emitida = st.text_input("Prima Total Emitida", key="registro_prima_total")
                    prima_neta = st.text_input("Prima Neta", key="registro_prima_neta")
                    primer_pago = st.text_input("Primer Pago", key="registro_primer_pago")
                    pagos_subsecuentes = st.text_input("Pagos Subsecuentes", key="registro_pagos_subsecuentes")
                    aseguradora = st.selectbox("Aseguradora", OPCIONES_ASEG, key="registro_aseguradora")
                    comision_porcentaje = st.text_input("% Comisión", key="registro_comision_pct")
                    estado = st.selectbox("Estado", OPCIONES_ESTADO_POLIZA, key="registro_estado")
                    contacto = st.text_input("Contacto", key="registro_contacto")
                    direccion = st.text_input("Dirección (Indicar ciudad y CP)", 
                                            value=prospecto_data.get("Dirección", ""),
                                            placeholder="Ej: Calle 123, CDMX, 03100",
                                            key="registro_direccion")

                col3, col4 = st.columns(2)
                with col3:
                    telefono_poliza = st.text_input("Teléfono", value=prospecto_data.get("Teléfono", ""), key="registro_telefono")
                    correo_poliza = st.text_input("Correo", value=prospecto_data.get("Correo", ""), key="registro_correo")
                    fecha_nacimiento_poliza = st.text_input("Fecha Nacimiento (dd/mm/yyyy)", 
                                                   value=prospecto_data.get("Fecha Nacimiento", ""),
                                                   placeholder="dd/mm/yyyy",
                                                   key="registro_fecha_nac")

                with col4:
                    referenciador_poliza = st.text_input("Referenciador", 
                                                       value=prospecto_data.get("Referenciador", ""),
                                                       placeholder="Origen del cliente/promoción",
                                                       key="registro_referenciador")
                    clave_emision = st.text_input("Clave de Emisión", key="registro_clave_emision")
                 
                # Validar fechas obligatorias
                fecha_errors = []
                if inicio_vigencia:
                    valido, error = validar_fecha(inicio_vigencia)
                    if not valido:
                        fecha_errors.append(f"Inicio Vigencia: {error}")
                else:
                    fecha_errors.append("Inicio Vigencia es obligatorio")

                if fin_vigencia:
                    valido, error = validar_fecha(fin_vigencia)
                    if not valido:
                        fecha_errors.append(f"Fin Vigencia: {error}")
                else:
                    fecha_errors.append("Fin Vigencia es obligatorio")

                if fecha_nacimiento_poliza:
                    valido, error = validar_fecha(fecha_nacimiento_poliza)
                    if not valido:
                        fecha_errors.append(f"Fecha Nacimiento: {error}")

                if fecha_errors:
                    for error in fecha_errors:
                        st.error(error)

                submitted_poliza = st.form_submit_button("💾 Registrar Cliente y Póliza")
                if submitted_poliza:
                    if not no_poliza:
                        st.warning("Debe completar el número de póliza")
                    elif fecha_errors:
                        st.warning("Corrija los errores en las fechas antes de guardar")
                    else:
                        # Verificar si ya existe el número de póliza
                        poliza_existe = False
                        if not df_polizas.empty and "No. Póliza" in df_polizas.columns:
                            poliza_existe = str(no_poliza).strip() in df_polizas["No. Póliza"].astype(str).str.strip().values

                        if poliza_existe:
                            st.warning("⚠️ Este número de póliza ya existe")
                        else:
                            nueva_poliza = {
                                "Tipo Persona": prospecto_data.get("Tipo Persona", ""),
                                "Nombre/Razón Social": prospecto_data.get("Nombre/Razón Social", ""),
                                "No. Póliza": no_poliza,
                                "Producto": producto_poliza,
                                "Inicio Vigencia": inicio_vigencia,
                                "Fin Vigencia": fin_vigencia,
                                "RFC": rfc_poliza,
                                "Forma de Pago": forma_pago,
                                "Banco": banco,
                                "Periodicidad": periodicidad,
                                "Prima Total Emitida": prima_total_emitida,
                                "Prima Neta": prima_neta,
                                "Primer Pago": primer_pago,
                                "Pagos Subsecuentes": pagos_subsecuentes,
                                "Aseguradora": aseguradora,
                                "% Comisión": comision_porcentaje,
                                "Estado": estado,
                                "Contacto": contacto,
                                "Dirección": direccion,
                                "Teléfono": telefono_poliza,
                                "Correo": correo_poliza,
                                "Fecha Nacimiento": fecha_nacimiento_poliza if fecha_nacimiento_poliza else "",
                                "Moneda": moneda,
                                "Referenciador": referenciador_poliza,
                                "Clave de Emisión": clave_emision
                            }

                            df_polizas = pd.concat([df_polizas, pd.DataFrame([nueva_poliza])], ignore_index=True)

                            # Remover el prospecto de la lista
                            df_prospectos = df_prospectos[df_prospectos["Nombre/Razón Social"] != prospecto_seleccionado]

                            if guardar_datos(df_prospectos=df_prospectos, df_polizas=df_polizas):
                                st.success("✅ Cliente registrado correctamente con su primera póliza")
                                st.rerun()
        else:
            st.info("No hay prospectos disponibles para convertir en clientes")

# 4. Consulta de Clientes
def mostrar_consulta_clientes(df_polizas):
    st.header("🔍 Consulta de Clientes")

    if df_polizas.empty:
        st.info("No hay clientes registrados")
        return

    # Obtener lista única de clientes
    clientes_unicos = df_polizas["Nombre/Razón Social"].dropna().unique().tolist()
    
    if not clientes_unicos:
        st.info("No hay clientes registrados")
        return

    # Seleccionar cliente
    cliente_seleccionado = st.selectbox("Seleccionar Cliente", clientes_unicos, key="consulta_cliente")

    if cliente_seleccionado:
        # Filtrar pólizas del cliente seleccionado
        polizas_cliente = df_polizas[df_polizas["Nombre/Razón Social"] == cliente_seleccionado]
        
        # Mostrar información general del cliente (tomada de la primera póliza)
        if not polizas_cliente.empty:
            info_cliente = polizas_cliente.iloc[0]
            
            st.subheader(f"Información del Cliente: {cliente_seleccionado}")
            
            # Inicializar estado para edición
            if 'editando_cliente' not in st.session_state:
                st.session_state.editando_cliente = False
            if 'cliente_data_edit' not in st.session_state:
                st.session_state.cliente_data_edit = {}
            
            # Botón para editar
            if not st.session_state.editando_cliente:
                if st.button("✏️ Editar Datos del Cliente", key="btn_editar_cliente"):
                    st.session_state.editando_cliente = True
                    st.session_state.cliente_data_edit = info_cliente.to_dict()
                    st.rerun()
            else:
                if st.button("❌ Cancelar Edición", key="btn_cancelar_edicion_cliente"):
                    st.session_state.editando_cliente = False
                    st.session_state.cliente_data_edit = {}
                    st.rerun()
            
            # Formulario de edición o visualización
            if st.session_state.editando_cliente:
                with st.form("form_editar_cliente"):
                    st.write("**Editar Información del Cliente**")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        tipo_persona_edit = st.selectbox(
                            "Tipo Persona", 
                            OPCIONES_PERSONA,
                            index=OPCIONES_PERSONA.index(st.session_state.cliente_data_edit.get("Tipo Persona", OPCIONES_PERSONA[0])) 
                            if st.session_state.cliente_data_edit.get("Tipo Persona") in OPCIONES_PERSONA else 0,
                            key="edit_tipo_persona"
                        )
                        rfc_edit = st.text_input(
                            "RFC", 
                            value=st.session_state.cliente_data_edit.get("RFC", ""),
                            key="edit_rfc"
                        )
                        telefono_edit = st.text_input(
                            "Teléfono", 
                            value=st.session_state.cliente_data_edit.get("Teléfono", ""),
                            key="edit_telefono"
                        )
                        correo_edit = st.text_input(
                            "Correo", 
                            value=st.session_state.cliente_data_edit.get("Correo", ""),
                            key="edit_correo"
                        )
                        fecha_nacimiento_edit = st.text_input(
                            "Fecha Nacimiento (dd/mm/yyyy)", 
                            value=st.session_state.cliente_data_edit.get("Fecha Nacimiento", ""),
                            placeholder="dd/mm/yyyy",
                            key="edit_fecha_nac"
                        )
                    
                    with col2:
                        direccion_edit = st.text_input(
                            "Dirección", 
                            value=st.session_state.cliente_data_edit.get("Dirección", ""),
                            placeholder="Ej: Calle 123, CDMX, 03100",
                            key="edit_direccion"
                        )
                        contacto_edit = st.text_input(
                            "Contacto", 
                            value=st.session_state.cliente_data_edit.get("Contacto", ""),
                            key="edit_contacto"
                        )
                        referenciador_edit = st.text_input(
                            "Referenciador", 
                            value=st.session_state.cliente_data_edit.get("Referenciador", ""),
                            key="edit_referenciador"
                        )
                    
                    # Validar fecha
                    fecha_error = None
                    if fecha_nacimiento_edit:
                        valido, error = validar_fecha(fecha_nacimiento_edit)
                        if not valido:
                            fecha_error = f"Fecha Nacimiento: {error}"
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        submitted_edit = st.form_submit_button("💾 Guardar Cambios")
                    with col_btn2:
                        cancel_edit = st.form_submit_button("🚫 Cancelar")
                    
                    if cancel_edit:
                        st.session_state.editando_cliente = False
                        st.session_state.cliente_data_edit = {}
                        st.rerun()
                    
                    if submitted_edit:
                        if fecha_error:
                            st.error(fecha_error)
                        else:
                            # Actualizar todas las pólizas del cliente con los nuevos datos
                            for index in polizas_cliente.index:
                                df_polizas.loc[index, "Tipo Persona"] = tipo_persona_edit
                                df_polizas.loc[index, "RFC"] = rfc_edit
                                df_polizas.loc[index, "Teléfono"] = telefono_edit
                                df_polizas.loc[index, "Correo"] = correo_edit
                                df_polizas.loc[index, "Fecha Nacimiento"] = fecha_nacimiento_edit
                                df_polizas.loc[index, "Dirección"] = direccion_edit
                                df_polizas.loc[index, "Contacto"] = contacto_edit
                                df_polizas.loc[index, "Referenciador"] = referenciador_edit
                            
                            if guardar_datos(df_polizas=df_polizas):
                                st.success("✅ Datos del cliente actualizados correctamente")
                                st.session_state.editando_cliente = False
                                st.session_state.cliente_data_edit = {}
                                st.rerun()
                            else:
                                st.error("❌ Error al actualizar los datos del cliente")
            else:
                # Mostrar información en modo lectura
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Información General:**")
                    st.write(f"**Tipo Persona:** {info_cliente.get('Tipo Persona', 'N/A')}")
                    st.write(f"**RFC:** {info_cliente.get('RFC', 'N/A')}")
                    st.write(f"**Teléfono:** {info_cliente.get('Teléfono', 'N/A')}")
                    st.write(f"**Correo:** {info_cliente.get('Correo', 'N/A')}")
                    st.write(f"**Fecha Nacimiento:** {info_cliente.get('Fecha Nacimiento', 'N/A')}")
                
                with col2:
                    st.write("**Dirección y Contacto:**")
                    st.write(f"**Dirección:** {info_cliente.get('Dirección', 'N/A')}")
                    st.write(f"**Contacto:** {info_cliente.get('Contacto', 'N/A')}")
                    st.write(f"**Referenciador:** {info_cliente.get('Referenciador', 'N/A')}")

        # Mostrar todas las pólizas del cliente
        st.subheader(f"Pólizas de {cliente_seleccionado}")
        
        # Contadores por estado
        if 'Estado' in polizas_cliente.columns:
            vigentes = len(polizas_cliente[polizas_cliente['Estado'] == 'VIGENTE'])
            canceladas = len(polizas_cliente[polizas_cliente['Estado'] == 'CANCELADO'])
            terminadas = len(polizas_cliente[polizas_cliente['Estado'] == 'TERMINADO'])
            
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            with col_stat1:
                st.metric("Pólizas Vigentes", vigentes)
            with col_stat2:
                st.metric("Pólizas Canceladas", canceladas)
            with col_stat3:
                st.metric("Pólizas Terminadas", terminadas)

        # Mostrar tabla de pólizas
        columnas_mostrar = ["No. Póliza", "Producto", "Aseguradora", "Inicio Vigencia", "Fin Vigencia", "Estado", "Moneda"]
        columnas_disponibles = [col for col in columnas_mostrar if col in polizas_cliente.columns]
        
        if columnas_disponibles:
            st.dataframe(polizas_cliente[columnas_disponibles], use_container_width=True)
        else:
            st.dataframe(polizas_cliente, use_container_width=True)

        # Detalles de póliza específica
        st.subheader("Detalles de Póliza Específica")
        if "No. Póliza" in polizas_cliente.columns:
            polizas_lista = polizas_cliente["No. Póliza"].tolist()
            poliza_seleccionada = st.selectbox("Seleccionar Póliza para ver detalles", polizas_lista, key="detalle_poliza_consulta")
            
            if poliza_seleccionada:
                poliza_detalle = polizas_cliente[polizas_cliente["No. Póliza"] == poliza_seleccionada].iloc[0]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Información de la Póliza:**")
                    st.write(f"**No. Póliza:** {poliza_detalle.get('No. Póliza', 'N/A')}")
                    st.write(f"**Producto:** {poliza_detalle.get('Producto', 'N/A')}")
                    st.write(f"**Aseguradora:** {poliza_detalle.get('Aseguradora', 'N/A')}")
                    st.write(f"**Estado:** {poliza_detalle.get('Estado', 'N/A')}")
                    st.write(f"**Moneda:** {poliza_detalle.get('Moneda', 'N/A')}")
                    st.write(f"**Periodicidad:** {poliza_detalle.get('Periodicidad', 'N/A')}")
                    st.write(f"**Clave de Emisión:** {poliza_detalle.get('Clave de Emisión', 'N/A')}")
                
                with col2:
                    st.write("**Fechas y Montos:**")
                    st.write(f"**Inicio Vigencia:** {poliza_detalle.get('Inicio Vigencia', 'N/A')}")
                    st.write(f"**Fin Vigencia:** {poliza_detalle.get('Fin Vigencia', 'N/A')}")
                    st.write(f"**Prima Total Emitida:** {poliza_detalle.get('Prima Total Emitida', 'N/A')}")
                    st.write(f"**Prima Neta:** {poliza_detalle.get('Prima Neta', 'N/A')}")
                    st.write(f"**Primer Pago:** {poliza_detalle.get('Primer Pago', 'N/A')}")
                    st.write(f"**Pagos Subsecuentes:** {poliza_detalle.get('Pagos Subsecuentes', 'N/A')}")
                    st.write(f"**% Comisión:** {poliza_detalle.get('% Comisión', 'N/A')}")

                # Formulario para actualizar estado de la póliza
                with st.form("form_actualizar_estado"):
                    st.write("**Actualizar Estado de la Póliza**")
                    nuevo_estado = st.selectbox("Nuevo Estado", OPCIONES_ESTADO_POLIZA, 
                                               index=OPCIONES_ESTADO_POLIZA.index(poliza_detalle.get('Estado', 'VIGENTE')) 
                                               if poliza_detalle.get('Estado') in OPCIONES_ESTADO_POLIZA else 0)
                    
                    if st.form_submit_button("💾 Actualizar Estado"):
                        # Actualizar el estado en el DataFrame
                        mask = (df_polizas['No. Póliza'] == poliza_seleccionada)
                        df_polizas.loc[mask, 'Estado'] = nuevo_estado
                        
                        if guardar_datos(df_polizas=df_polizas):
                            st.success("✅ Estado de la póliza actualizado correctamente")
                            st.rerun()
                        else:
                            st.error("❌ Error al actualizar el estado")

# 5. Póliza Nueva (para clientes existentes)
def mostrar_poliza_nueva(df_prospectos, df_polizas):
    st.header("🆕 Póliza Nueva para Cliente Existente")

    # Seleccionar cliente existente
    if not df_polizas.empty and "Nombre/Razón Social" in df_polizas.columns:
        clientes_unicos = df_polizas["Nombre/Razón Social"].dropna().unique().tolist()
        cliente_seleccionado = st.selectbox("Seleccionar Cliente", [""] + clientes_unicos, key="cliente_existente")

        if cliente_seleccionado:
            # Mostrar pólizas existentes del cliente
            st.subheader(f"Pólizas existentes de {cliente_seleccionado}")
            polizas_cliente = df_polizas[df_polizas["Nombre/Razón Social"] == cliente_seleccionado]

            columnas_mostrar = ["No. Póliza", "Producto", "Aseguradora", "Fin Vigencia", "Estado"]
            columnas_disponibles = [col for col in columnas_mostrar if col in polizas_cliente.columns]

            if columnas_disponibles:
                st.dataframe(polizas_cliente[columnas_disponibles], use_container_width=True)
            else:
                st.info("No hay columnas disponibles para mostrar")

            # Formulario para nueva póliza
            st.subheader("Agregar Nueva Póliza")

            with st.form("form_nueva_poliza", clear_on_submit=True):
                col1, col2 = st.columns(2)

                with col1:
                    no_poliza = st.text_input("No. Póliza*", key="nueva_poliza_numero")
                    producto = st.selectbox("Producto", OPCIONES_PRODUCTO, key="nueva_poliza_producto")
                    inicio_vigencia = st.text_input("Inicio Vigencia (dd/mm/yyyy)*", 
                                                  placeholder="dd/mm/yyyy",
                                                  key="nueva_poliza_inicio")
                    fin_vigencia = st.text_input("Fin Vigencia (dd/mm/yyyy)*", 
                                               placeholder="dd/mm/yyyy",
                                               key="nueva_poliza_fin")
                    forma_pago = st.selectbox("Forma de Pago", OPCIONES_PAGO, key="nueva_poliza_pago")
                    banco = st.selectbox("Banco", OPCIONES_BANCO, key="nueva_poliza_banco")
                    periodicidad = st.selectbox("Periodicidad", ["ANUAL", "MENSUAL", "TRIMESTRAL", "SEMESTRAL"], key="nueva_poliza_periodicidad")
                    moneda = st.selectbox("Moneda", OPCIONES_MONEDA, key="nueva_poliza_moneda")

                with col2:
                    prima_total_emitida = st.text_input("Prima Total Emitida", key="nueva_poliza_prima_total")
                    prima_neta = st.text_input("Prima Neta", key="nueva_poliza_prima_neta")
                    primer_pago = st.text_input("Primer Pago", key="nueva_poliza_primer_pago")
                    pagos_subsecuentes = st.text_input("Pagos Subsecuentes", key="nueva_poliza_pagos_subsecuentes")
                    aseguradora = st.selectbox("Aseguradora", OPCIONES_ASEG, key="nueva_poliza_aseguradora")
                    comision_porcentaje = st.text_input("% Comisión", key="nueva_poliza_comision_pct")
                    estado = st.selectbox("Estado", OPCIONES_ESTADO_POLIZA, key="nueva_poliza_estado")
                    contacto = st.text_input("Contacto", key="nueva_poliza_contacto")
                    direccion = st.text_input("Dirección (Indicar ciudad y CP)", 
                                            placeholder="Ej: Calle 123, CDMX, 03100",
                                            key="nueva_poliza_direccion")
                    referenciador = st.text_input("Referenciador", 
                                                placeholder="Origen del cliente/promoción",
                                                key="nueva_poliza_referenciador")
                    clave_emision = st.text_input("Clave de Emisión", key="nueva_poliza_clave_emision")

                # Validar fechas obligatorias
                fecha_errors = []
                if inicio_vigencia:
                    valido, error = validar_fecha(inicio_vigencia)
                    if not valido:
                        fecha_errors.append(f"Inicio Vigencia: {error}")
                else:
                    fecha_errors.append("Inicio Vigencia es obligatorio")

                if fin_vigencia:
                    valido, error = validar_fecha(fin_vigencia)
                    if not valido:
                        fecha_errors.append(f"Fin Vigencia: {error}")
                else:
                    fecha_errors.append("Fin Vigencia es obligatorio")

                if fecha_errors:
                    for error in fecha_errors:
                        st.error(error)

                submitted_nueva_poliza = st.form_submit_button("💾 Guardar Nueva Póliza")
                if submitted_nueva_poliza:
                    if not no_poliza:
                        st.warning("Debe completar el número de póliza")
                    elif fecha_errors:
                        st.warning("Corrija los errores en las fechas antes de guardar")
                    else:
                        # Verificar si ya existe el número de póliza
                        poliza_existe = False
                        if "No. Póliza" in df_polizas.columns:
                            poliza_existe = str(no_poliza).strip() in df_polizas["No. Póliza"].astype(str).str.strip().values

                        if poliza_existe:
                            st.warning("⚠️ Este número de póliza ya existe")
                        else:
                            # Obtener datos básicos del cliente
                            if not polizas_cliente.empty:
                                cliente_data = polizas_cliente.iloc[0]
                            else:
                                cliente_data = {}

                            nueva_poliza = {
                                "Tipo Persona": cliente_data.get("Tipo Persona", ""),
                                "Nombre/Razón Social": cliente_seleccionado,
                                "No. Póliza": no_poliza,
                                "Producto": producto,
                                "Inicio Vigencia": inicio_vigencia,
                                "Fin Vigencia": fin_vigencia,
                                "RFC": cliente_data.get("RFC", ""),
                                "Forma de Pago": forma_pago,
                                "Banco": banco,
                                "Periodicidad": periodicidad,
                                "Prima Total Emitida": prima_total_emitida,
                                "Prima Neta": prima_neta,
                                "Primer Pago": primer_pago,
                                "Pagos Subsecuentes": pagos_subsecuentes,
                                "Aseguradora": aseguradora,
                                "% Comisión": comision_porcentaje,
                                "Estado": estado,
                                "Contacto": contacto,
                                "Dirección": direccion,
                                "Teléfono": cliente_data.get("Teléfono", ""),
                                "Correo": cliente_data.get("Correo", ""),
                                "Fecha Nacimiento": cliente_data.get("Fecha Nacimiento", ""),
                                "Moneda": moneda,
                                "Referenciador": referenciador,
                                "Clave de Emisión": clave_emision
                            }

                            df_polizas = pd.concat([df_polizas, pd.DataFrame([nueva_poliza])], ignore_index=True)

                            if guardar_datos(df_prospectos=df_prospectos, df_polizas=df_polizas):
                                st.success("✅ Nueva póliza agregada correctamente")
                                st.rerun()
        else:
            st.info("No hay clientes registrados")

# 6. Renovaciones (antes Próximos Vencimientos)
def mostrar_renovaciones(df_polizas):
    st.header("🔄 Renovaciones (Pólizas por Vencer)")

    if st.button("🔄 Actualizar Lista", key="actualizar_renovaciones"):
        st.cache_data.clear()

    if df_polizas.empty:
        st.info("No hay pólizas registradas")
        return

    # Crear una copia para no modificar el original
    df = df_polizas.copy()
    
    # Limpiar y convertir fechas de manera segura
    df_clean = df.copy()
    
    # Función para convertir fecha de manera segura
    def safe_date_conversion(date_str):
        if pd.isna(date_str) or date_str == "" or date_str is None:
            return None
        
        date_str = str(date_str).strip()
        
        # Lista de formatos a probar
        formats = [
            "%d/%m/%Y",  # 31/12/2023
            "%Y-%m-%d",  # 2023-12-31
            "%d-%m-%Y",  # 31-12-2023
            "%m/%d/%Y",  # 12/31/2023 (formato americano)
            "%Y/%m/%d",  # 2023/12/31
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        # Si ningún formato funciona, usar pandas como último recurso
        try:
            result = pd.to_datetime(date_str, dayfirst=True, errors='coerce')
            if not pd.isna(result):
                return result.date()
        except:
            pass
        
        return None

    # Aplicar conversión segura
    df_clean['Fin_Vigencia_Date'] = df_clean['Fin Vigencia'].apply(safe_date_conversion)
    
    # Filtrar solo las que tienen fecha válida
    df_valid = df_clean[df_clean['Fin_Vigencia_Date'].notna()]
    
    if df_valid.empty:
        st.info("No hay pólizas con fechas de vencimiento válidas")
        return

    # Calcular días restantes
    hoy = datetime.now().date()
    df_valid['Dias_Restantes'] = df_valid['Fin_Vigencia_Date'].apply(
        lambda x: (x - hoy).days if x else None
    )
    
    # Filtrar por estado VIGENTE si existe la columna
    if 'Estado' in df_valid.columns:
        df_vigentes = df_valid[df_valid['Estado'].astype(str).str.upper() == 'VIGENTE']
    else:
        df_vigentes = df_valid
    
    # Filtrar por rango de días (45-60 días para renovaciones)
    df_renovaciones = df_vigentes[
        (df_vigentes['Dias_Restantes'] >= 45) & 
        (df_vigentes['Dias_Restantes'] <= 60)
    ]

    if df_renovaciones.empty:
        st.info("No hay pólizas por renovar en los próximos 45-60 días")
        
        # Mostrar algunas estadísticas
        if not df_vigentes.empty and 'Dias_Restantes' in df_vigentes.columns:
            st.subheader("Estadísticas de Pólizas Vigentes")
            col1, col2, col_stats3 = st.columns(3)
            
            with col1:
                por_renovar = len(df_vigentes[df_vigentes['Dias_Restantes'] < 45])
                st.metric("Por renovar (<45 días)", por_renovar)
            
            with col2:
                renovaciones_lejanas = len(df_vigentes[df_vigentes['Dias_Restantes'] > 60])
                st.metric("Renovaciones lejanas (>60 días)", renovaciones_lejanas)
            
            with col_stats3:
                total_vigentes = len(df_vigentes)
                st.metric("Total Vigentes", total_vigentes)
        
        return

    # Preparar datos para mostrar
    df_mostrar = df_renovaciones.copy()
    df_mostrar['Fin_Vigencia_Formateada'] = df_mostrar['Fin_Vigencia_Date'].apply(
        lambda x: x.strftime('%d/%m/%Y') if x else 'Fecha inválida'
    )

    # Columnas a mostrar
    columnas_mostrar = ['Nombre/Razón Social', 'No. Póliza', 'Producto', 'Fin_Vigencia_Formateada', 'Dias_Restantes']
    columnas_disponibles = [col for col in columnas_mostrar if col in df_mostrar.columns]
    
    # Renombrar para mejor presentación
    df_display = df_mostrar[columnas_disponibles].rename(columns={
        'Fin_Vigencia_Formateada': 'Fin Vigencia',
        'Dias_Restantes': 'Días para Renovación'
    })
    
    # Aplicar estilo para resaltar por días restantes
    def style_dias_renovacion(val):
        if val <= 50:
            return 'background-color: #ffcccc; color: #cc0000; font-weight: bold;'
        elif val <= 55:
            return 'background-color: #fff0cc; color: #cc8800;'
        else:
            return 'background-color: #e6ffe6; color: #006600;'
    
    try:
        styled_df = df_display.style.applymap(
            style_dias_renovacion, 
            subset=['Días para Renovación']
        )
        st.dataframe(styled_df, use_container_width=True)
    except Exception:
        st.dataframe(df_display, use_container_width=True)

    # Detalles de póliza seleccionada
    st.subheader("Detalles para Renovación")
    
    if 'No. Póliza' in df_renovaciones.columns:
        polizas_lista = df_renovaciones['No. Póliza'].astype(str).tolist()
        
        if polizas_lista:
            poliza_seleccionada = st.selectbox(
                "Seleccionar Póliza para ver detalles", 
                polizas_lista, 
                key="detalle_poliza_renovaciones"
            )
            
            if poliza_seleccionada:
                # Encontrar la póliza seleccionada
                poliza_mask = df_renovaciones['No. Póliza'].astype(str) == poliza_seleccionada
                if poliza_mask.any():
                    poliza_detalle = df_renovaciones[poliza_mask].iloc[0]
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Información General:**")
                        st.write(f"**Cliente:** {poliza_detalle.get('Nombre/Razón Social', 'N/A')}")
                        st.write(f"**No. Póliza:** {poliza_detalle.get('No. Póliza', 'N/A')}")
                        st.write(f"**Producto:** {poliza_detalle.get('Producto', 'N/A')}")
                        st.write(f"**Aseguradora:** {poliza_detalle.get('Aseguradora', 'N/A')}")
                        st.write(f"**Estado:** {poliza_detalle.get('Estado', 'N/A')}")
                        st.write(f"**Días para Renovación:** {poliza_detalle.get('Dias_Restantes', 'N/A')}")
                    
                    with col2:
                        st.write("**Fechas:**")
                        st.write(f"**Inicio Vigencia:** {poliza_detalle.get('Inicio Vigencia', 'N/A')}")
                        st.write(f"**Fin Vigencia:** {poliza_detalle.get('Fin_Vigencia_Date', 'N/A')}")
                        
                        st.write("**Datos de Contacto:**")
                        st.write(f"**Teléfono:** {poliza_detalle.get('Teléfono', 'N/A')}")
                        st.write(f"**Correo:** {poliza_detalle.get('Correo', 'N/A')}")
                        st.write(f"**Contacto:** {poliza_detalle.get('Contacto', 'N/A')}")
                        
                        if poliza_detalle.get('Dias_Restantes', 0) <= 50:
                            st.warning("⚠️ Esta póliza está próxima a vencer. Contactar al cliente para renovación.")

# 7. Cobranza (versión completamente corregida)
def mostrar_cobranza(df_polizas, df_cobranza):
    st.header("💰 Cobranza")

    # Calcular cobranza de los próximos 60 días
    df_cobranza_proxima = calcular_cobranza()

    if df_cobranza_proxima.empty and (df_cobranza is None or df_cobranza.empty):
        st.info("No hay cobranza pendiente para los próximos 60 días")
        return

    # Combinar con datos existentes de cobranza
    if df_cobranza is not None and not df_cobranza.empty:
        # Usar ID_Cobranza para evitar duplicados si existe, si no usar No. Póliza y Recibo
        if 'ID_Cobranza' in df_cobranza.columns and 'ID_Cobranza' in df_cobranza_proxima.columns:
            df_cobranza_completa = pd.concat([df_cobranza, df_cobranza_proxima]).drop_duplicates(
                subset=['ID_Cobranza'], keep='last'
            )
        else:
            df_cobranza_completa = pd.concat([df_cobranza, df_cobranza_proxima]).drop_duplicates(
                subset=['No. Póliza', 'Recibo'], keep='last'
            )
    else:
        df_cobranza_completa = df_cobranza_proxima

    # Filtrar solo pendientes para mostrar
    if 'Estatus' in df_cobranza_completa.columns:
        df_pendientes = df_cobranza_completa[df_cobranza_completa['Estatus'] == 'Pendiente']
    else:
        df_pendientes = df_cobranza_completa

    if df_pendientes.empty:
        st.success("🎉 No hay recibos pendientes de pago en los próximos 60 días")
        return

    # Obtener información de inicio de vigencia y clave de emisión de las pólizas
    df_pendientes_con_info = df_pendientes.copy()
    
    # Buscar la información adicional para cada póliza
    for idx, row in df_pendientes_con_info.iterrows():
        no_poliza = row['No. Póliza']
        poliza_info = df_polizas[df_polizas['No. Póliza'].astype(str) == str(no_poliza)]
        
        if not poliza_info.empty:
            inicio_vigencia = poliza_info.iloc[0].get('Inicio Vigencia', '')
            periodicidad = row.get('Periodicidad', 'MENSUAL')
            recibo = row.get('Recibo', 1)
            clave_emision = poliza_info.iloc[0].get('Clave de Emisión', '')
            
            # Calcular próximo pago (ya lo tenemos en Fecha Vencimiento, pero lo dejamos por si acaso)
            proximo_pago = row.get('Fecha Vencimiento', '')
            df_pendientes_con_info.at[idx, 'Próximo pago'] = proximo_pago
            df_pendientes_con_info.at[idx, 'Clave de Emisión'] = clave_emision
        else:
            df_pendientes_con_info.at[idx, 'Próximo pago'] = ""
            df_pendientes_con_info.at[idx, 'Clave de Emisión'] = ""

    # Calcular días transcurridos desde el próximo pago
    hoy = datetime.now().date()
    
    def calcular_dias_transcurridos(proximo_pago_str):
        if not proximo_pago_str or pd.isna(proximo_pago_str) or proximo_pago_str == "":
            return None
        
        try:
            # Convertir fecha de próximo pago a datetime
            proximo_pago = datetime.strptime(proximo_pago_str, "%d/%m/%Y").date()
            # Calcular días transcurridos desde la fecha de próximo pago
            dias_transcurridos = (hoy - proximo_pago).days
            return max(0, dias_transcurridos)  # No mostrar negativos
        except:
            return None

    # Aplicar cálculo de días transcurridos
    df_pendientes_con_info['Días Transcurridos'] = df_pendientes_con_info['Próximo pago'].apply(calcular_dias_transcurridos)

    # Formatear montos con 2 decimales y separador de miles
    def formatear_monto(monto):
        try:
            if pd.isna(monto) or monto == "" or monto is None:
                return "0.00"
            # Si ya es float, formatearlo directamente
            if isinstance(monto, (int, float)):
                return f"{monto:,.2f}"
            # Si es string, limpiarlo y convertir
            monto_limpio = str(monto).replace(',', '').replace('$', '').replace(' ', '').strip()
            if monto_limpio == '':
                return "0.00"
            monto_float = float(monto_limpio)
            return f"{monto_float:,.2f}"
        except Exception as e:
            print(f"Error formateando monto '{monto}': {e}")
            return "0.00"

    # Aplicar formato a los montos
    df_pendientes_con_info['Prima de Recibo Formateado'] = df_pendientes_con_info['Prima de Recibo'].apply(formatear_monto)
    df_pendientes_con_info['Monto Pagado Formateado'] = df_pendientes_con_info['Monto Pagado'].apply(formatear_monto)

    # Crear DataFrame para mostrar con las columnas reorganizadas
    df_mostrar = df_pendientes_con_info.copy()
    
    # Definir el orden de columnas según los requerimientos
    columnas_base = [
        'Recibo', 'Periodicidad', 'Moneda', 'Prima de Recibo Formateado', 
        'Monto Pagado Formateado', 'Próximo pago', 'Días Transcurridos',
        'No. Póliza', 'Nombre/Razón Social', 'Clave de Emisión', 'Mes Cobranza', 'Fecha Pago', 'Estatus'
    ]
    
    # Filtrar solo las columnas que existen en el DataFrame
    columnas_finales = [col for col in columnas_base if col in df_mostrar.columns]
    
    # Agregar cualquier columna adicional que no esté en la lista base
    columnas_adicionales = [col for col in df_mostrar.columns if col not in columnas_base and col not in ['Prima de Recibo', 'Monto Pagado', 'Días Restantes', 'Fecha Vencimiento']]
    columnas_finales.extend(columnas_adicionales)
    
    # Crear el DataFrame final para mostrar
    df_display = df_mostrar[columnas_finales].rename(columns={
        'Prima de Recibo Formateado': 'Prima de Recibo',
        'Monto Pagado Formateado': 'Monto Pagado'
    })

    # Aplicar colores según días transcurridos
    def color_row_by_dias_transcurridos(dias_transcurridos):
        if dias_transcurridos is None:
            return ''
        elif dias_transcurridos >= 20:
            return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'  # Rojo
        elif dias_transcurridos >= 11:
            return 'background-color: #ffe6cc; color: #cc6600; font-weight: bold;'  # Naranja
        elif dias_transcurridos >= 5:
            return 'background-color: #fff3cd; color: #856404;'  # Amarillo
        else:
            return 'background-color: #d4edda; color: #155724;'  # Verde (menos de 5 días)

    # Mostrar el DataFrame sin índice
    try:
        styled_df = df_display.style.applymap(
            lambda v: color_row_by_dias_transcurridos(v) if isinstance(v, (int, float)) else '', 
            subset=['Días Transcurridos']
        )
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    except Exception:
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    # Leyenda de colores
    st.markdown("""
    **Leyenda de colores días transcurridos desde inicio de pago de recibo:**
    - 🟢 **Verde:** Menos de 5 días
    - 🟡 **Amarillo:** 5-10 días
    - 🟠 **Naranja:** 11-20 días
    - 🔴 **Rojo:** Más de 20 días
    """)

    # Formulario para registrar pagos
    st.subheader("Registrar Pago")

    # Inicializar estado para la selección de cobranza
    if 'cobranza_seleccionada' not in st.session_state:
        st.session_state.cobranza_seleccionada = None
    if 'info_cobranza_actual' not in st.session_state:
        st.session_state.info_cobranza_actual = None

    # Crear lista de opciones para selección individual de recibos
    if not df_pendientes_con_info.empty:
        # Crear identificador único para cada recibo
        opciones_cobranza = []
        for idx, row in df_pendientes_con_info.iterrows():
            # Formatear monto
            monto_formateado = formatear_monto(row.get('Prima de Recibo', 0))
            # Crear descripción amigable
            descripcion = f"{row['No. Póliza']} - Recibo {row['Recibo']} - {row.get('Nombre/Razón Social', '')} - {monto_formateado} {row.get('Moneda', 'MXN')} - Vence: {row.get('Próximo pago', '')}"
            opciones_cobranza.append({
                'descripcion': descripcion,
                'id_cobranza': f"{row['No. Póliza']}_R{row['Recibo']}",
                'datos': row
            })
        
        # Selector de recibo específico
        if opciones_cobranza:
            opcion_seleccionada = st.selectbox(
                "Seleccionar Recibo de Cobranza",
                options=[""] + [opc['descripcion'] for opc in opciones_cobranza],
                key="select_recibo_cobranza"
            )
            
            if opcion_seleccionada:
                # Encontrar los datos del recibo seleccionado
                recibo_seleccionado = next((opc for opc in opciones_cobranza if opc['descripcion'] == opcion_seleccionada), None)
                
                if recibo_seleccionado:
                    info_cobranza = recibo_seleccionado['datos']
                    st.session_state.cobranza_seleccionada = recibo_seleccionado['id_cobranza']
                    st.session_state.info_cobranza_actual = info_cobranza
                    
                    # Mostrar información del recibo seleccionado
                    st.write(f"**Recibo seleccionado:** {info_cobranza.get('Recibo', '')}")
                    st.write(f"**Cliente:** {info_cobranza.get('Nombre/Razón Social', '')}")
                    
                    # Mostrar Prima de Recibo directamente
                    prima_recibo = info_cobranza.get('Prima de Recibo', 0)
                    moneda = info_cobranza.get('Moneda', 'MXN')
                    prima_recibo_formateado = formatear_monto(prima_recibo)
                    st.write(f"**Prima de Recibo:** {prima_recibo_formateado} {moneda}")
                    
                    # Mostrar Clave de Emisión
                    st.write(f"**Clave de Emisión:** {info_cobranza.get('Clave de Emisión', 'No disponible')}")
                    
                    st.write(f"**Próximo pago:** {info_cobranza.get('Próximo pago', '')}")
                    st.write(f"**Periodicidad:** {info_cobranza.get('Periodicidad', '')}")
                    
                    # Mostrar días transcurridos
                    dias_transcurridos = calcular_dias_transcurridos(info_cobranza.get('Próximo pago', ''))
                    if dias_transcurridos is not None:
                        st.write(f"**Días transcurridos desde vencimiento:** {dias_transcurridos}")
                        
                        # Mostrar alerta según días transcurridos
                        if dias_transcurridos >= 20:
                            st.error("⚠️ **ALERTA:** Recibo con más de 20 días de vencido - Contacto urgente requerido")
                        elif dias_transcurridos >= 11:
                            st.warning("⚠️ **ATENCIÓN:** Recibo con 11-20 días de vencido - Seguimiento necesario")
                        elif dias_transcurridos >= 5:
                            st.info("ℹ️ **AVISO:** Recibo con 5-10 días de vencido - Recordatorio de pago")

                    # Formulario para el pago - SOLO SE MUESTRA CUANDO HAY UN RECIBO SELECCIONADO
                    with st.form("form_pago"):
                        # Solo el campo Monto Pagado con valor 0 por defecto
                        monto_pagado = st.number_input(
                            "Monto Pagado", 
                            min_value=0.0,
                            value=0.0,  # Valor por defecto 0
                            step=0.01, 
                            key="monto_pagado"
                        )
                        
                        # Mostrar la moneda del pago
                        moneda_cobranza = info_cobranza.get('Moneda', 'MXN')
                        st.write(f"**Moneda del pago:** {moneda_cobranza}")
                        
                        fecha_pago = st.text_input(
                            "Fecha de Pago (dd/mm/yyyy)", 
                            value=fecha_actual(), 
                            key="fecha_pago_cob"
                        )

                        submitted = st.form_submit_button("💾 Registrar Pago")
                        
                        if submitted:
                            # Validaciones
                            if monto_pagado <= 0:
                                st.warning("El monto pagado debe ser mayor a 0")
                            else:
                                valido, error = validar_fecha(fecha_pago)
                                if not valido:
                                    st.error(f"Fecha de pago: {error}")
                                else:
                                    # Buscar el registro específico por ID único
                                    mask = (
                                        (df_cobranza_completa['No. Póliza'] == info_cobranza['No. Póliza']) & 
                                        (df_cobranza_completa['Recibo'] == info_cobranza['Recibo'])
                                    )
                                    
                                    if mask.any():
                                        # Actualizar solo el monto pagado, fecha y estatus
                                        df_cobranza_completa.loc[mask, 'Monto Pagado'] = monto_pagado
                                        df_cobranza_completa.loc[mask, 'Fecha Pago'] = fecha_pago
                                        df_cobranza_completa.loc[mask, 'Estatus'] = 'Pagado'
                                        
                                        # Actualizar días de atraso si existe la columna
                                        if 'Días Atraso' in df_cobranza_completa.columns:
                                            proximo_pago = info_cobranza.get('Próximo pago', '')
                                            if proximo_pago:
                                                try:
                                                    proximo_pago_dt = datetime.strptime(proximo_pago, "%d/%m/%Y")
                                                    fecha_pago_dt = datetime.strptime(fecha_pago, "%d/%m/%Y")
                                                    dias_atraso = max(0, (fecha_pago_dt - proximo_pago_dt).days)
                                                    df_cobranza_completa.loc[mask, 'Días Atraso'] = dias_atraso
                                                except:
                                                    pass
                                    else:
                                        # Si no existe (caso raro), agregamos un registro como pagado
                                        nuevo = {
                                            "No. Póliza": info_cobranza['No. Póliza'],
                                            "Nombre/Razón Social": info_cobranza.get('Nombre/Razón Social', ''),
                                            "Mes Cobranza": info_cobranza.get('Mes Cobranza', ''),
                                            "Próximo pago": info_cobranza.get('Próximo pago', ''),
                                            "Prima de Recibo": info_cobranza.get('Prima de Recibo', 0),
                                            "Monto Pagado": monto_pagado,
                                            "Fecha Pago": fecha_pago,
                                            "Estatus": "Pagado",
                                            "Periodicidad": info_cobranza.get('Periodicidad', ''),
                                            "Moneda": info_cobranza.get('Moneda', 'MXN'),
                                            "Recibo": info_cobranza.get('Recibo', ''),
                                            "ID_Cobranza": f"{info_cobranza['No. Póliza']}_R{info_cobranza.get('Recibo', '')}"
                                        }
                                        df_cobranza_completa = pd.concat([df_cobranza_completa, pd.DataFrame([nuevo])], ignore_index=True)

                                    if guardar_datos(df_cobranza=df_cobranza_completa):
                                        st.success("✅ Pago registrado correctamente")
                                        st.rerun()
                                    else:
                                        st.error("❌ Error al registrar el pago")
            else:
                st.info("Seleccione un recibo de cobranza para registrar el pago")
        else:
            st.info("No hay recibos pendientes disponibles para seleccionar")
    else:
        st.info("No hay recibos pendientes para mostrar")

    # HISTORIAL DE PAGOS CON FILTROS MEJORADOS
    if df_cobranza is not None and not df_cobranza.empty:
        if 'Estatus' in df_cobranza.columns:
            df_pagados = df_cobranza[df_cobranza['Estatus'] == 'Pagado']
        else:
            df_pagados = pd.DataFrame()
            
        if not df_pagados.empty:
            st.subheader("Historial de Pagos")
            
            # Enriquecer el historial con información de las pólizas (Clave de Emisión)
            df_historial = df_pagados.copy()
            
            # Agregar Clave de Emisión al historial
            claves_emision = []
            for idx, pago in df_historial.iterrows():
                no_poliza = pago['No. Póliza']
                poliza_info = df_polizas[df_polizas['No. Póliza'].astype(str) == str(no_poliza)]
                if not poliza_info.empty:
                    claves_emision.append(poliza_info.iloc[0].get('Clave de Emisión', ''))
                else:
                    claves_emision.append('')
            
            df_historial['Clave de Emisión'] = claves_emision
            
            # Crear columnas de año y mes para filtros
            df_historial['Fecha Pago DT'] = pd.to_datetime(df_historial['Fecha Pago'], dayfirst=True, errors='coerce')
            df_historial['Año'] = df_historial['Fecha Pago DT'].dt.year
            df_historial['Mes'] = df_historial['Fecha Pago DT'].dt.month
            
            # Filtros
            col_filtro1, col_filtro2 = st.columns(2)
            
            with col_filtro1:
                años = sorted(df_historial['Año'].dropna().unique(), reverse=True)
                año_seleccionado = st.selectbox(
                    "Filtrar por Año",
                    options=["Todos"] + años,
                    key="filtro_año_historial"
                )
            
            with col_filtro2:
                if año_seleccionado != "Todos":
                    meses_disponibles = sorted(df_historial[df_historial['Año'] == año_seleccionado]['Mes'].dropna().unique(), reverse=True)
                else:
                    meses_disponibles = sorted(df_historial['Mes'].dropna().unique(), reverse=True)
                
                mes_seleccionado = st.selectbox(
                    "Filtrar por Mes",
                    options=["Todos"] + meses_disponibles,
                    key="filtro_mes_historial"
                )
            
            # Aplicar filtros
            df_filtrado = df_historial.copy()
            if año_seleccionado != "Todos":
                df_filtrado = df_filtrado[df_filtrado['Año'] == año_seleccionado]
            if mes_seleccionado != "Todos":
                df_filtrado = df_filtrado[df_filtrado['Mes'] == mes_seleccionado]
            
            # Formatear montos para el historial
            df_filtrado['Prima de Recibo Formateado'] = df_filtrado['Prima de Recibo'].apply(formatear_monto)
            df_filtrado['Monto Pagado Formateado'] = df_filtrado['Monto Pagado'].apply(formatear_monto)
            
            # Columnas para mostrar en el historial
            columnas_historial = [
                'Recibo', 'No. Póliza', 'Nombre/Razón Social', 'Mes Cobranza', 
                'Prima de Recibo Formateado', 'Monto Pagado Formateado', 'Fecha Pago',
                'Periodicidad', 'Moneda', 'Clave de Emisión'
            ]
            columnas_disponibles = [col for col in columnas_historial if col in df_filtrado.columns]
            
            # Renombrar columnas para mostrar
            df_historial_display = df_filtrado[columnas_disponibles].rename(columns={
                'Prima de Recibo Formateado': 'Prima de Recibo',
                'Monto Pagado Formateado': 'Monto Pagado'
            })
            
            # Mostrar estadísticas del filtro aplicado
            st.write(f"**Mostrando {len(df_filtrado)} registros**")
            
            st.dataframe(df_historial_display, use_container_width=True, hide_index=True)
         
# ---- Función principal ----
def main():
    st.title("📊 Gestor de Cartera Rizkora")

    # Botones para recargar o limpiar cache
    col1, col2, col3 = st.columns([3,1,1])
    with col2:
        if st.button("🔄 Recargar Datos", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with col3:
        if st.button("🧹 Limpiar Cache", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("✅ Cache limpiado")
            st.rerun()

    # Cargar datos iniciales
    df_prospectos, df_polizas, df_cobranza, df_seguimiento = cargar_datos()

    # Crear pestañas en el orden solicitado
    tab_names = [
        "👥 Prospectos", 
        "📞 Seguimiento",
        "👤 Registro de Cliente", 
        "🔍 Consulta de Clientes",
        "🆕 Póliza Nueva",
        "🔄 Renovaciones",
        "💰 Cobranza"
    ]

    # Usar radio buttons para una selección más confiable
    st.markdown("---")
    
    st.markdown("**Navegación:**")
    active_tab = st.radio(
        "Selecciona una sección:",
        options=tab_names,
        horizontal=True,
        label_visibility="collapsed",
        key="tab_selector"
    )
    
    # Actualizar el estado de la pestaña activa
    st.session_state.active_tab = active_tab

    st.markdown("---")

    # Mostrar el contenido de la pestaña activa
    if st.session_state.active_tab == "👥 Prospectos":
        mostrar_prospectos(df_prospectos, df_polizas)
    elif st.session_state.active_tab == "📞 Seguimiento":
        mostrar_seguimiento(df_prospectos, df_seguimiento)
    elif st.session_state.active_tab == "👤 Registro de Cliente":
        mostrar_registro_cliente(df_prospectos, df_polizas)
    elif st.session_state.active_tab == "🔍 Consulta de Clientes":
        mostrar_consulta_clientes(df_polizas)
    elif st.session_state.active_tab == "🆕 Póliza Nueva":
        mostrar_poliza_nueva(df_prospectos, df_polizas)
    elif st.session_state.active_tab == "🔄 Renovaciones":
        mostrar_renovaciones(df_polizas)
    elif st.session_state.active_tab == "💰 Cobranza":
        mostrar_cobranza(df_polizas, df_cobranza)

if __name__ == "__main__":
    main()












