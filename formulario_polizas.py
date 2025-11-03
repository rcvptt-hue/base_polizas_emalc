# -*- coding: utf-8 -*-
"""
Created on Sat Nov  1 21:11:49 2025
Updated full version with:
 - Auto-fill of prospect fields when selecting a prospect to edit
 - Improved cobrarza calculation (±60 days window, robust parsing)
 - Editable 'Monto a pagar' field before registering payments
 - All original sections included: Prospectos, Póliza Prospectos, Pólizas Nuevas,
   Próximos Vencimientos, Cobranza, Seguimiento
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
    page_title="Gestor de Pólizas EALC",
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
                "Fin Vigencia", "RFC", "Forma de Pago", "Banco", "Periodicidad", "Prima Emitida",
                "Prima Neta", "Monto Periodo", "Aseguradora", "% Comisión", "Comisión", "Estado", "Contacto", "Dirección",
                "Teléfono", "Correo", "Fecha Nacimiento", "Moneda", "Referenciador"
            ])

        try:
            worksheet_cobranza = spreadsheet.worksheet("Cobranza")
            df_cobranza = pd.DataFrame(worksheet_cobranza.get_all_records())
        except Exception as e:
            df_cobranza = pd.DataFrame(columns=[
                "No. Póliza", "Mes Cobranza", "Monto Esperado", "Monto Pagado",
                "Fecha Pago", "Estatus", "Días Atraso", "Fecha Vencimiento", "Nombre/Razón Social", "Días Restantes"
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

# Función para obtener pólizas próximas a vencer
def obtener_polizas_proximas_vencer(dias_min=45, dias_max=60):
    try:
        _, df_polizas, _, _ = cargar_datos()

        if df_polizas.empty:
            return pd.DataFrame()

        if "Estado" in df_polizas.columns:
            df_vigentes = df_polizas[df_polizas["Estado"] == "VIGENTE"]
        else:
            df_vigentes = pd.DataFrame()

        if df_vigentes.empty:
            return pd.DataFrame()

        polizas_proximas = []
        hoy = datetime.now().date()

        for _, poliza in df_vigentes.iterrows():
            fecha_fin_str = poliza.get("Fin Vigencia", "")
            if pd.isna(fecha_fin_str) or fecha_fin_str == "":
                continue

            try:
                fecha_fin = None
                if isinstance(fecha_fin_str, str):
                    try:
                        fecha_fin = datetime.strptime(fecha_fin_str, "%d/%m/%Y").date()
                    except ValueError:
                        try:
                            fecha_fin = datetime.strptime(fecha_fin_str, "%Y-%m-%d").date()
                        except ValueError:
                            continue

                if fecha_fin is None:
                    continue

                dias_restantes = (fecha_fin - hoy).days

                if dias_min <= dias_restantes <= dias_max:
                    poliza_data = poliza.to_dict()
                    poliza_data["Días Restantes"] = dias_restantes
                    poliza_data["Fin Vigencia"] = fecha_fin.strftime("%d/%m/%Y")
                    polizas_proximas.append(poliza_data)

            except Exception as e:
                continue

        return pd.DataFrame(polizas_proximas)

    except Exception as e:
        st.error(f"Error al obtener pólizas próximas a vencer: {e}")
        return pd.DataFrame()

# Función para calcular cobranza (versión mejorada)
def calcular_cobranza():
    try:
        _, df_polizas, df_cobranza, _ = cargar_datos()

        if df_polizas.empty:
            return pd.DataFrame()

        # Filtrar pólizas vigentes
        df_vigentes = df_polizas[df_polizas["Estado"].astype(str).str.upper() == "VIGENTE"]

        if df_vigentes.empty:
            return pd.DataFrame()

        hoy = datetime.now()
        fecha_limite = hoy + timedelta(days=60)  # ventana extendida a 60 días
        cobranza_mes = []

        for _, poliza in df_vigentes.iterrows():
            no_poliza = str(poliza.get("No. Póliza", "")).strip()
            periodicidad = str(poliza.get("Periodicidad", "")).upper().strip()
            # Intentar tomar campo Monto Periodo; si no existe, usar Prima Neta o Prima Emitida
            monto_periodo = poliza.get("Monto Periodo", poliza.get("Prima Neta", poliza.get("Prima Emitida", 0)))
            inicio_vigencia_str = poliza.get("Inicio Vigencia", "")

            if not no_poliza or not inicio_vigencia_str:
                continue

            try:
                # Convertir fecha de inicio
                inicio_vigencia = None
                if isinstance(inicio_vigencia_str, str):
                    try:
                        inicio_vigencia = datetime.strptime(inicio_vigencia_str, "%d/%m/%Y")
                    except ValueError:
                        try:
                            inicio_vigencia = datetime.strptime(inicio_vigencia_str, "%Y-%m-%d")
                        except ValueError:
                            continue

                if inicio_vigencia is None:
                    continue

                # Calcular próximas fechas de pago en la ventana
                frecuencias = {
                    "MENSUAL": 1,
                    "TRIMESTRAL": 3,
                    "SEMESTRAL": 6,
                    "ANUAL": 12
                }

                frecuencia = frecuencias.get(periodicidad, 1)

                # Calcular meses desde inicio hasta hoy
                meses_diff = (hoy.year - inicio_vigencia.year) * 12 + hoy.month - inicio_vigencia.month

                # Buscar el próximo pago dentro de la ventana (buscamos varios periodos por seguridad)
                for i in range(0, 24):  # revisar hasta 24 periodos por seguridad
                    meses_proximo = meses_diff + i
                    # Encontrar múltiplos de la frecuencia
                    if meses_proximo % frecuencia == 0:
                        proxima_fecha = inicio_vigencia + relativedelta(months=meses_proximo)

                        # Verificar si está dentro de los próximos 60 días o hasta 10 días atrás (para pagos recientes)
                        if (hoy - timedelta(days=10)) <= proxima_fecha <= fecha_limite:
                            mes_cobranza = proxima_fecha.strftime("%m/%Y")

                            # Verificar si ya existe registro en cobranza
                            existe_registro = False
                            if not df_cobranza.empty and "No. Póliza" in df_cobranza.columns and "Mes Cobranza" in df_cobranza.columns:
                                existe_registro = ((df_cobranza["No. Póliza"].astype(str) == no_poliza) &
                                                  (df_cobranza["Mes Cobranza"] == mes_cobranza)).any()

                            if not existe_registro:
                                # Parse monto a float robustamente
                                try:
                                    monto_float = float(str(monto_periodo).replace(',', '').replace('$', '')) if monto_periodo not in (None, "") else 0.0
                                except:
                                    monto_float = 0.0

                                dias_restantes = (proxima_fecha - hoy).days
                                cobranza_mes.append({
                                    "No. Póliza": no_poliza,
                                    "Nombre/Razón Social": poliza.get("Nombre/Razón Social", ""),
                                    "Mes Cobranza": mes_cobranza,
                                    "Fecha Vencimiento": proxima_fecha.strftime("%d/%m/%Y"),
                                    "Monto Esperado": monto_float,
                                    "Monto Pagado": 0,
                                    "Fecha Pago": "",
                                    "Estatus": "Pendiente",
                                    "Días Restantes": dias_restantes
                                })
                            break  # Solo agregar el próximo pago encontrado

            except Exception:
                continue

        return pd.DataFrame(cobranza_mes)

    except Exception as e:
        st.error(f"Error al calcular cobranza: {e}")
        return pd.DataFrame()

# Función para manejar el cambio de pestaña
def cambiar_pestaña(nombre_pestaña):
    st.session_state.active_tab = nombre_pestaña

# ---- Funciones para cada pestaña (completas) ----

# Prospectos
def mostrar_prospectos(df_prospectos, df_polizas):
    st.header("Gestión de Prospectos")

    # Inicializar estado para la edición
    if 'modo_edicion_prospectos' not in st.session_state:
        st.session_state.modo_edicion_prospectos = False
    if 'prospecto_editando' not in st.session_state:
        st.session_state.prospecto_editando = None
    if 'prospecto_data' not in st.session_state:
        st.session_state.prospecto_data = {}

    # Selector para editar prospecto existente
    if not df_prospectos.empty:
        prospectos_lista = df_prospectos["Nombre/Razón Social"].dropna().tolist()
        
        # Crear clave única para el selectbox
        prospecto_seleccionado = st.selectbox(
            "Seleccionar Prospecto para editar", 
            [""] + prospectos_lista, 
            key="select_editar_prospecto"
        )

        # Botón para cargar datos del prospecto seleccionado
        if prospecto_seleccionado:
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("📝 Cargar Datos para Editar", use_container_width=True):
                    st.session_state.prospecto_editando = prospecto_seleccionado
                    st.session_state.modo_edicion_prospectos = True
                    # Cargar datos del prospecto seleccionado
                    prospecto_data = df_prospectos[df_prospectos["Nombre/Razón Social"] == prospecto_seleccionado].iloc[0]
                    st.session_state.prospecto_data = prospecto_data.to_dict()
                    st.rerun()
            
            # Mostrar información del prospecto seleccionado (solo lectura)
            if st.session_state.prospecto_editando == prospecto_seleccionado:
                st.info(f"**Editando:** {prospecto_seleccionado}")
        else:
            # Si no hay prospecto seleccionado, limpiar estado
            if st.session_state.modo_edicion_prospectos:
                st.session_state.modo_edicion_prospectos = False
                st.session_state.prospecto_editando = None
                st.session_state.prospecto_data = {}

    # Si estamos en modo edición, mostrar botón para cancelar
    if st.session_state.modo_edicion_prospectos:
        if st.button("❌ Cancelar Edición", key="btn_cancelar_edicion"):
            st.session_state.modo_edicion_prospectos = False
            st.session_state.prospecto_editando = None
            st.session_state.prospecto_data = {}
            st.rerun()

    # Usar datos almacenados en session_state
    prospecto_data = st.session_state.prospecto_data

    with st.form("form_prospectos", clear_on_submit=False):
        st.subheader("📝 Formulario de Prospecto")
        
        if st.session_state.modo_edicion_prospectos:
            st.info(f"Editando: **{st.session_state.prospecto_editando}**")
        
        col1, col2 = st.columns(2)

        with col1:
            # Determinar índice para Tipo Persona
            tipo_persona_index = 0
            if prospecto_data.get("Tipo Persona") in OPCIONES_PERSONA:
                tipo_persona_index = OPCIONES_PERSONA.index(prospecto_data.get("Tipo Persona"))
            
            tipo_persona = st.selectbox(
                "Tipo Persona", 
                OPCIONES_PERSONA,
                index=tipo_persona_index,
                key="prospecto_tipo"
            )
            
            nombre_razon = st.text_input(
                "Nombre/Razón Social*", 
                value=prospecto_data.get("Nombre/Razón Social", ""), 
                key="prospecto_nombre"
            )
            
            fecha_nacimiento = st.text_input(
                "Fecha Nacimiento (dd/mm/yyyy)", 
                value=prospecto_data.get("Fecha Nacimiento", ""),
                placeholder="dd/mm/yyyy",
                key="prospecto_nacimiento"
            )
            
            rfc = st.text_input(
                "RFC", 
                value=prospecto_data.get("RFC", ""), 
                key="prospecto_rfc"
            )
            
            telefono = st.text_input(
                "Teléfono", 
                value=prospecto_data.get("Teléfono", ""), 
                key="prospecto_telefono"
            )
            
            correo = st.text_input(
                "Correo", 
                value=prospecto_data.get("Correo", ""), 
                key="prospecto_correo"
            )

        with col2:
            # Determinar índice para Producto
            producto_index = 0
            if prospecto_data.get("Producto") in OPCIONES_PRODUCTO:
                producto_index = OPCIONES_PRODUCTO.index(prospecto_data.get("Producto"))
            
            producto = st.selectbox(
                "Producto", 
                OPCIONES_PRODUCTO,
                index=producto_index,
                key="prospecto_producto"
            )
            
            fecha_registro = st.text_input(
                "Fecha Registro*", 
                value=prospecto_data.get("Fecha Registro", fecha_actual()),
                placeholder="dd/mm/yyyy",
                key="prospecto_registro"
            )
            
            fecha_contacto = st.text_input(
                "Fecha Contacto (dd/mm/yyyy)", 
                value=prospecto_data.get("Fecha Contacto", ""),
                placeholder="dd/mm/yyyy",
                key="prospecto_contacto"
            )
            
            seguimiento = st.text_input(
                "Seguimiento (dd/mm/yyyy)", 
                value=prospecto_data.get("Seguimiento", ""),
                placeholder="dd/mm/yyyy",
                key="prospecto_seguimiento"
            )
            
            representantes = st.text_area(
                "Representantes Legales (separar por comas)", 
                value=prospecto_data.get("Representantes Legales", ""),
                placeholder="Ej: Juan Pérez, María García",
                key="prospecto_representantes"
            )
            
            referenciador = st.text_input(
                "Referenciador", 
                value=prospecto_data.get("Referenciador", ""),
                placeholder="Origen del cliente/promoción",
                key="prospecto_referenciador"
            )
            
            direccion = st.text_input(
                "Dirección", 
                value=prospecto_data.get("Dirección", ""),
                placeholder="Ej: Calle 123, CDMX, 03100",
                key="prospecto_direccion"
            )

        # Validar fechas
        fecha_errors = []
        if fecha_nacimiento:
            valido, error = validar_fecha(fecha_nacimiento)
            if not valido:
                fecha_errors.append(f"Fecha Nacimiento: {error}")

        if fecha_registro:
            valido, error = validar_fecha(fecha_registro)
            if not valido:
                fecha_errors.append(f"Fecha Registro: {error}")

        if fecha_contacto:
            valido, error = validar_fecha(fecha_contacto)
            if not valido:
                fecha_errors.append(f"Fecha Contacto: {error}")

        if seguimiento:
            valido, error = validar_fecha(seguimiento)
            if not valido:
                fecha_errors.append(f"Seguimiento: {error}")

        if fecha_errors:
            for error in fecha_errors:
                st.error(error)

        # Botones de acción
        col_b1, col_b2 = st.columns(2)

        with col_b1:
            if st.session_state.modo_edicion_prospectos:
                submitted = st.form_submit_button("💾 Actualizar Prospecto", use_container_width=True)
            else:
                submitted = st.form_submit_button("💾 Agregar Nuevo Prospecto", use_container_width=True)

        with col_b2:
            if st.session_state.modo_edicion_prospectos:
                if st.form_submit_button("🚫 Cancelar", use_container_width=True, type="secondary"):
                    st.session_state.modo_edicion_prospectos = False
                    st.session_state.prospecto_editando = None
                    st.session_state.prospecto_data = {}
                    st.rerun()

        if submitted:
            if not nombre_razon:
                st.warning("Debe completar al menos el nombre o razón social")
            elif fecha_errors:
                st.warning("Corrija los errores en las fechas antes de guardar")
            else:
                nuevo_prospecto = {
                    "Tipo Persona": tipo_persona,
                    "Nombre/Razón Social": nombre_razon,
                    "Fecha Nacimiento": fecha_nacimiento if fecha_nacimiento else "",
                    "RFC": rfc,
                    "Teléfono": telefono,
                    "Correo": correo,
                    "Dirección": direccion,
                    "Producto": producto,
                    "Fecha Registro": fecha_registro if fecha_registro else fecha_actual(),
                    "Fecha Contacto": fecha_contacto if fecha_contacto else "",
                    "Seguimiento": seguimiento if seguimiento else "",
                    "Representantes Legales": representantes,
                    "Referenciador": referenciador
                }

                if st.session_state.modo_edicion_prospectos:
                    # Actualizar prospecto existente
                    index = df_prospectos[df_prospectos["Nombre/Razón Social"] == st.session_state.prospecto_editando].index
                    for key, value in nuevo_prospecto.items():
                        df_prospectos.loc[index, key] = value
                    mensaje = "✅ Prospecto actualizado correctamente"

                    # Salir del modo edición después de guardar
                    st.session_state.modo_edicion_prospectos = False
                    st.session_state.prospecto_editando = None
                    st.session_state.prospecto_data = {}
                else:
                    # Agregar nuevo prospecto
                    df_prospectos = pd.concat([df_prospectos, pd.DataFrame([nuevo_prospecto])], ignore_index=True)
                    mensaje = "✅ Prospecto agregado correctamente"

                if guardar_datos(df_prospectos=df_prospectos, df_polizas=df_polizas):
                    st.success(mensaje)
                    st.rerun()
                else:
                    st.error("❌ Error al guardar el prospecto")

    # Mostrar lista de prospectos
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
            
        # Estadísticas rápidas
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
                    # Intentar contar prospectos del mes actual
                    df_prospectos['Fecha Registro DT'] = pd.to_datetime(df_prospectos['Fecha Registro'], dayfirst=True, errors='coerce')
                    mes_actual = datetime.now().month
                    prospectos_mes = len(df_prospectos[df_prospectos['Fecha Registro DT'].dt.month == mes_actual])
                    st.metric("Prospectos este Mes", prospectos_mes)
                except:
                    st.metric("Prospectos este Mes", "N/A")
    else:
        st.info("No hay prospectos registrados")
# Función para mostrar la pestaña de Póliza Prospectos
def mostrar_poliza_prospectos(df_prospectos, df_polizas):
    st.header("Convertir Prospecto a Póliza")

    # Seleccionar prospecto
    if not df_prospectos.empty:
        prospectos_lista = df_prospectos["Nombre/Razón Social"].dropna().tolist()
        prospecto_seleccionado = st.selectbox("Seleccionar Prospecto", [""] + prospectos_lista, key="poliza_prospecto")

        if prospecto_seleccionado:
            # Cargar datos del prospecto seleccionado
            prospecto_data = df_prospectos[df_prospectos["Nombre/Razón Social"] == prospecto_seleccionado].iloc[0]

            with st.form("form_poliza_prospecto", clear_on_submit=True):
                st.subheader(f"Creando Póliza para: {prospecto_seleccionado}")

                col1, col2 = st.columns(2)

                with col1:
                    st.text_input("Tipo Persona", value=prospecto_data.get("Tipo Persona", ""), key="poliza_tipo", disabled=True)
                    st.text_input("Nombre/Razón Social", value=prospecto_data.get("Nombre/Razón Social", ""), key="poliza_nombre", disabled=True)
                    no_poliza = st.text_input("No. Póliza*", key="poliza_numero")
                    producto_poliza = st.selectbox("Producto", OPCIONES_PRODUCTO, 
                                          index=OPCIONES_PRODUCTO.index(prospecto_data.get("Producto", "")) 
                                          if prospecto_data.get("Producto") in OPCIONES_PRODUCTO else 0,
                                          key="poliza_producto")
                    inicio_vigencia = st.text_input("Inicio Vigencia (dd/mm/yyyy)*", 
                                                  placeholder="dd/mm/yyyy",
                                                  key="poliza_inicio")
                    fin_vigencia = st.text_input("Fin Vigencia (dd/mm/yyyy)*", 
                                               placeholder="dd/mm/yyyy",
                                               key="poliza_fin")
                    rfc_poliza = st.text_input("RFC", value=prospecto_data.get("RFC", ""), key="poliza_rfc")
                    forma_pago = st.selectbox("Forma de Pago", OPCIONES_PAGO, key="poliza_pago")
                    moneda = st.selectbox("Moneda", OPCIONES_MONEDA, key="poliza_moneda")

                with col2:
                    banco = st.selectbox("Banco", OPCIONES_BANCO, key="poliza_banco")
                    periodicidad = st.selectbox("Periodicidad", ["ANUAL", "MENSUAL", "TRIMESTRAL", "SEMESTRAL"], key="poliza_periodicidad")
                    prima_emitida = st.text_input("Prima Total Emitida", key="poliza_prima")
                    prima_neta = st.text_input("Prima Neta", key="poliza_prima_neta")
                    primer_pago = st.text_input("Primer Pago", key="poliza_primer_pago")
                    pagos_subsecuentes = st.text_input("Pagos Subsecuentes", key="poliza_pagos_sub")
                    aseguradora = st.selectbox("Aseguradora", OPCIONES_ASEG, key="poliza_aseguradora")
                    comision_porcentaje = st.text_input("% Comisión", key="poliza_comision_pct")
                    referenciador_poliza = st.text_input("Referenciador", 
                                                       value=prospecto_data.get("Referenciador", ""),
                                                       placeholder="Origen del cliente/promoción",
                                                       key="poliza_referenciador")

                col3, col4 = st.columns(2)
                with col3:
                    estado = st.selectbox("Estado", ["VIGENTE", "CANCELADO", "TERMINADO"], key="poliza_estado")
                    contacto = st.text_input("Contacto", key="poliza_contacto")
                    direccion = st.text_input("Dirección (Indicar ciudad y CP)", 
                                            value=prospecto_data.get("Dirección", ""),
                                            placeholder="Ej: Calle 123, CDMX, 03100",
                                            key="poliza_direccion")

                with col4:
                    telefono_poliza = st.text_input("Teléfono", value=prospecto_data.get("Teléfono", ""), key="poliza_telefono")
                    correo_poliza = st.text_input("Correo", value=prospecto_data.get("Correo", ""), key="poliza_correo")
                    fecha_nacimiento_poliza = st.text_input("Fecha Nacimiento (dd/mm/yyyy)", 
                                                   value=prospecto_data.get("Fecha Nacimiento", ""),
                                                   placeholder="dd/mm/yyyy",
                                                   key="poliza_fecha_nac")

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

                submitted_poliza = st.form_submit_button("💾 Agregar Póliza")
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
                                "Prima Total Emitida": prima_emitida,
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
                                "Moneda": moneda if 'moneda' in locals() else "",
                                "Referenciador": referenciador_poliza
                            }

                            df_polizas = pd.concat([df_polizas, pd.DataFrame([nueva_poliza])], ignore_index=True)

                            # Remover el prospecto de la lista
                            df_prospectos = df_prospectos[df_prospectos["Nombre/Razón Social"] != prospecto_seleccionado]

                            if guardar_datos(df_prospectos=df_prospectos, df_polizas=df_polizas):
                                st.success("✅ Póliza agregada correctamente")
                                cambiar_pestaña("🆕 Pólizas Nuevas")
                                st.rerun()
        else:
            st.info("No hay prospectos disponibles para convertir")

# Función para mostrar la pestaña de Pólizas Nuevas
def mostrar_polizas_nuevas(df_prospectos, df_polizas):
    st.header("Gestión de Pólizas para Clientes Existentes")

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
                    prima_emitida = st.text_input("Prima Total Emitida", key="nueva_poliza_prima")
                    prima_neta = st.text_input("Prima Neta", key="nueva_poliza_prima_neta")
                    aseguradora = st.selectbox("Aseguradora", OPCIONES_ASEG, key="nueva_poliza_aseguradora")
                    comision_porcentaje = st.text_input("% Comisión", key="nueva_poliza_comision_pct")
                    estado = st.selectbox("Estado", ["VIGENTE", "CANCELADO", "TERMINADO"], key="nueva_poliza_estado")
                    contacto = st.text_input("Contacto", key="nueva_poliza_contacto")
                    direccion = st.text_input("Dirección (Indicar ciudad y CP)", 
                                            placeholder="Ej: Calle 123, CDMX, 03100",
                                            key="nueva_poliza_direccion")
                    referenciador = st.text_input("Referenciador", 
                                                placeholder="Origen del cliente/promoción",
                                                key="nueva_poliza_referenciador")

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
                                "Prima Total Emitida": prima_emitida,
                                "Prima Neta": prima_neta,
                                "Aseguradora": aseguradora,
                                "% Comisión": comision_porcentaje,
                                "Estado": estado,
                                "Contacto": contacto,
                                "Dirección": direccion,
                                "Teléfono": cliente_data.get("Teléfono", ""),
                                "Correo": cliente_data.get("Correo", ""),
                                "Fecha Nacimiento": cliente_data.get("Fecha Nacimiento", ""),
                                "Moneda": moneda,
                                "Referenciador": referenciador
                            }

                            df_polizas = pd.concat([df_polizas, pd.DataFrame([nueva_poliza])], ignore_index=True)

                            if guardar_datos(df_prospectos=df_prospectos, df_polizas=df_polizas):
                                st.success("✅ Nueva póliza agregada correctamente")
                                st.rerun()
        else:
            st.info("No hay clientes registrados")

# Función para mostrar la pestaña de Vencimientos
def mostrar_vencimientos(df_polizas):
    st.header("⏰ Pólizas Próximas a Vencer (45-60 días)")

    if st.button("🔄 Actualizar Lista", key="actualizar_vencimientos"):
        st.cache_data.clear()

    if df_polizas.empty:
        st.info("No hay pólizas registradas")
        return

    # Intentar convertir columna "Fin Vigencia" a datetime (soporta dd/mm/yyyy y yyyy-mm-dd)
    df = df_polizas.copy()
    df["Fin Vigencia DT"] = pd.to_datetime(df["Fin Vigencia"], dayfirst=True, errors='coerce')
    hoy = datetime.now().date()
    df["Días_Restantes"] = (df["Fin Vigencia DT"].dt.date - hoy).dt.days
    df_venc = df[(df["Días_Restantes"] >= 45) & (df["Días_Restantes"] <= 60)]

    if df_venc.empty:
        st.info("No hay pólizas que venzan en los próximos 45-60 días")
        return

    columnas_mostrar = ["Nombre/Razón Social", "No. Póliza", "Producto", "Fin Vigencia", "Días_Restantes"]
    columnas_disponibles = [col for col in columnas_mostrar if col in df_venc.columns]
    st.dataframe(df_venc[columnas_disponibles], use_container_width=True)

    # Detalles de póliza
    st.subheader("Detalles de Póliza")
    if "No. Póliza" in df_venc.columns:
        polizas_lista = df_venc["No. Póliza"].tolist()
        poliza_seleccionada = st.selectbox("Seleccionar Póliza para ver detalles", polizas_lista, key="detalle_poliza")
        if poliza_seleccionada:
            poliza_detalle = df_venc[df_venc["No. Póliza"] == poliza_seleccionada].iloc[0]
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Información General:**")
                st.write(f"**Cliente:** {poliza_detalle.get('Nombre/Razón Social', '')}")
                st.write(f"**No. Póliza:** {poliza_detalle.get('No. Póliza', '')}")
                st.write(f"**Producto:** {poliza_detalle.get('Producto', '')}")
                st.write(f"**Aseguradora:** {poliza_detalle.get('Aseguradora', '')}")
                st.write(f"**Estado:** {poliza_detalle.get('Estado', '')}")
            with col2:
                st.write("**Fechas:**")
                st.write(f"**Inicio Vigencia:** {poliza_detalle.get('Inicio Vigencia', '')}")
                st.write(f"**Fin Vigencia:** {poliza_detalle.get('Fin Vigencia', '')}")
                st.write(f"**Días Restantes:** {poliza_detalle.get('Días_Restantes', '')}")
                st.write("**Datos de Contacto:**")
                st.write(f"**Teléfono:** {poliza_detalle.get('Teléfono', '')}")
                st.write(f"**Correo:** {poliza_detalle.get('Correo', '')}")

# Función para mostrar la pestaña de Cobranza (versión mejorada)
def mostrar_cobranza(df_polizas, df_cobranza):
    st.header("💰 Cobranza - Próximos 60 días")

    # Calcular cobranza de los próximos 60 días
    df_cobranza_proxima = calcular_cobranza()

    if df_cobranza_proxima.empty and (df_cobranza is None or df_cobranza.empty):
        st.info("No hay cobranza pendiente para los próximos 60 días")
        return

    # Combinar con datos existentes de cobranza
    if df_cobranza is not None and not df_cobranza.empty:
        df_cobranza_completa = pd.concat([df_cobranza, df_cobranza_proxima]).drop_duplicates(
            subset=['No. Póliza', 'Mes Cobranza'], keep='last'
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

    # Aplicar colores según días restantes si existe la columna
    if 'Días Restantes' in df_pendientes.columns:
        def color_row(dias_restantes):
            if dias_restantes <= 5:
                return 'background-color: #f8d7da; color: #721c24;'
            elif dias_restantes <= 10:
                return 'background-color: #fff3cd; color: #856404;'
            elif dias_restantes <= 20:
                return 'background-color: #ffe6cc; color: #cc6600;'
            else:
                return 'background-color: #d4edda; color: #155724;'

        try:
            styled_df = df_pendientes.style.applymap(lambda v: color_row(v) if isinstance(v, (int, float)) else '', subset=['Días Restantes'])
            st.dataframe(styled_df, use_container_width=True)
        except Exception:
            st.dataframe(df_pendientes, use_container_width=True)
    else:
        st.dataframe(df_pendientes, use_container_width=True)

    # Formulario para registrar pagos
    st.subheader("Registrar Pago")
    with st.form("form_pago"):
        polizas_pendientes = df_pendientes["No. Póliza"].tolist()
        poliza_pago = st.selectbox("Seleccionar Póliza", polizas_pendientes, key="select_pol_pago")

        info_poliza = None
        if poliza_pago:
            info_poliza = df_pendientes[df_pendientes["No. Póliza"] == poliza_pago].iloc[0]
            st.write(f"**Cliente:** {info_poliza.get('Nombre/Razón Social', '')}")
            st.write(f"**Monto Esperado Actual:** ${info_poliza.get('Monto Esperado', 0):,.2f}")
            st.write(f"**Fecha Vencimiento:** {info_poliza.get('Fecha Vencimiento', '')}")

        # Campo editable para monto a pagar (solo en el formulario, no modifica la hoja hasta confirmar)
        monto_editable = st.number_input("Monto a pagar (MXN) — editable", min_value=0.0,
                                         value=float(info_poliza.get('Monto Esperado', 0)) if info_poliza is not None else 0.0,
                                         step=0.01, key="monto_editable")

        monto_pagado = st.number_input("Monto Pagado (MXN)", min_value=0.0,
                                       value=monto_editable, step=0.01, key="monto_pagado")
        fecha_pago = st.text_input("Fecha de Pago (dd/mm/yyyy)", value=fecha_actual(), key="fecha_pago_cob")

        if st.form_submit_button("💾 Registrar Pago"):
            # Validaciones
            if monto_pagado <= 0:
                st.warning("El monto pagado debe ser mayor a 0")
            else:
                valido, error = validar_fecha(fecha_pago)
                if not valido:
                    st.error(f"Fecha de pago: {error}")
                else:
                    mask = (df_cobranza_completa['No. Póliza'] == poliza_pago) & (df_cobranza_completa['Estatus'] == 'Pendiente')
                    if mask.any():
                        df_cobranza_completa.loc[mask, 'Monto Pagado'] = monto_pagado
                        df_cobranza_completa.loc[mask, 'Monto Esperado'] = monto_editable
                        df_cobranza_completa.loc[mask, 'Fecha Pago'] = fecha_pago
                        df_cobranza_completa.loc[mask, 'Estatus'] = 'Pagado'
                    else:
                        # Si no existe (caso raro), agregamos un registro como pagado
                        nuevo = {
                            "No. Póliza": poliza_pago,
                            "Nombre/Razón Social": info_poliza.get('Nombre/Razón Social', '') if info_poliza is not None else "",
                            "Mes Cobranza": info_poliza.get('Mes Cobranza', '') if info_poliza is not None else "",
                            "Fecha Vencimiento": info_poliza.get('Fecha Vencimiento', '') if info_poliza is not None else "",
                            "Monto Esperado": monto_editable,
                            "Monto Pagado": monto_pagado,
                            "Fecha Pago": fecha_pago,
                            "Estatus": "Pagado",
                            "Días Restantes": info_poliza.get('Días Restantes', None) if info_poliza is not None else None
                        }
                        df_cobranza_completa = pd.concat([df_cobranza_completa, pd.DataFrame([nuevo])], ignore_index=True)

                    if guardar_datos(df_cobranza=df_cobranza_completa):
                        st.success("✅ Pago registrado correctamente")
                        st.rerun()
                    else:
                        st.error("❌ Error al registrar el pago")

    # Mostrar historial de pagos registrados (si existe)
    if df_cobranza is not None and not df_cobranza.empty:
        df_pagados = df_cobranza[df_cobranza['Estatus'] == 'Pagado'] if 'Estatus' in df_cobranza.columns else pd.DataFrame()
        if not df_pagados.empty:
            st.subheader("Historial de Pagos")
            st.dataframe(df_pagados, use_container_width=True)

# Seguimiento
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
                                st.info("ℹ️ El prospecto ha sido marcado como 'Convertido'. Puedes proceder a crear su póliza en la pestaña 'Póliza Prospectos'")
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

# ---- Función principal ----
def main():
    st.title("📊 Gestor de Prospectos y Pólizas EALC")

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

    # Crear pestañas
    tab_names = [
        "👥 Prospectos", 
        "📋 Póliza Prospectos", 
        "🆕 Pólizas Nuevas", 
        "⏰ Próximos Vencimientos",
        "💰 Cobranza",
        "📞 Seguimiento"
    ]

    cols = st.columns(len(tab_names))
    for i, tab_name in enumerate(tab_names):
        with cols[i]:
            if st.button(tab_name, use_container_width=True, 
                        type="primary" if st.session_state.active_tab == tab_name else "secondary"):
                cambiar_pestaña(tab_name)

    st.markdown("---")

    # Mostrar el contenido de la pestaña activa
    if st.session_state.active_tab == "👥 Prospectos":
        mostrar_prospectos(df_prospectos, df_polizas)
    elif st.session_state.active_tab == "📋 Póliza Prospectos":
        mostrar_poliza_prospectos(df_prospectos, df_polizas)
    elif st.session_state.active_tab == "🆕 Pólizas Nuevas":
        mostrar_polizas_nuevas(df_prospectos, df_polizas)
    elif st.session_state.active_tab == "⏰ Próximos Vencimientos":
        mostrar_vencimientos(df_polizas)
    elif st.session_state.active_tab == "💰 Cobranza":
        mostrar_cobranza(df_polizas, df_cobranza)
    elif st.session_state.active_tab == "📞 Seguimiento":
        mostrar_seguimiento(df_prospectos, df_seguimiento)

if __name__ == "__main__":
    main()


