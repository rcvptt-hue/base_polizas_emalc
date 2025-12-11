# -*- coding: utf-8 -*-
"""
Created on Sat Nov  1 21:11:49 2025
Updated full version with:
 - Reorganización de pestañas según requerimientos
 - Nueva funcionalidad de Consulta de Clientes
 - Cambio de Próximos Vencimientos a Renovaciones
 - Todas las secciones originales mejoradas
 - Nueva pestaña de Operación para gastos operacionales
 - Cobranza que incluye recibos vencidos con comentario especial
 - NUEVA PESTAÑA: Asesoría AXA con generación de reporte financiero
"""

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import re
from dateutil.relativedelta import relativedelta
import matplotlib.pyplot as plt
import numpy as np
import io
import base64
from io import BytesIO

# ================================
# CONFIGURACIÓN DE COLORES AXA
# ================================
COLORES_AXA = {
    'azul_principal': '#064c78',      # Mayor uso
    'verde_oscuro': '#00796b',
    'verde_agua': '#00bfa5',
    'azul_claro': '#90caf9',
    'amarillo': '#fff59d',
    'gris': '#e0e0e0',
    'lila': '#b39ddb',
    'azul_gris': '#7986cb',
    'morado': '#c95ef5'
}

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
OPCIONES_CONCEPTO_OPERACION = ["Papelería", "Contabilidad", "Patrocinio", "Tarjetas", "Promocionales", "Impuestos", "Gasolina"]
OPCIONES_FORMA_PAGO_OPERACION = ["Efectivo", "TDC", "TDD", "Transferencia"]
OPCIONES_DEDUCIBLE = ["Sí", "No"]
OPCIONES_ESTATUS_COBRANZA = ["Pendiente", "Vencido", "Pagado"]

# Inicializar estado de sesión
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "👥 Prospectos"
if 'notas_prospecto_actual' not in st.session_state:
    st.session_state.notas_prospecto_actual = ""
if 'asesoria_data' not in st.session_state:
    st.session_state.asesoria_data = {}

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
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # Cargar hojas existentes
        try:
            worksheet_prospectos = spreadsheet.worksheet("Prospectos")
            df_prospectos = pd.DataFrame(worksheet_prospectos.get_all_records())
        except Exception as e:
            st.error(f"❌ Error al cargar hoja 'Prospectos': {e}")
            df_prospectos = pd.DataFrame(columns=[
                "Tipo Persona", "Nombre/Razón Social", "Fecha Nacimiento", "RFC", "Teléfono",
                "Correo", "Producto", "Fecha Registro", "Fecha Contacto", "Seguimiento",
                "Representantes Legales", "Referenciador", "Estatus", "Notas", "Dirección"
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
                "No. Póliza", "Mes Cobranza", "Prima de Recibo", "Monto Pagado",
                "Fecha Pago", "Estatus", "Días Atraso", "Fecha Vencimiento", "Nombre/Razón Social", "Días Restantes",
                "Periodicidad", "Moneda", "Recibo", "Clave de Emisión", "Comentario"
            ])
 
        try:
            worksheet_seguimiento = spreadsheet.worksheet("Seguimiento")
            df_seguimiento = pd.DataFrame(worksheet_seguimiento.get_all_records())
        except Exception as e:
            df_seguimiento = pd.DataFrame(columns=[
                "Nombre/Razón Social", "Fecha Contacto", "Estatus", "Comentarios", "Fecha Registro"
            ])

        try:
            worksheet_operacion = spreadsheet.worksheet("Operacion")
            df_operacion = pd.DataFrame(worksheet_operacion.get_all_records())
        except Exception as e:
            df_operacion = pd.DataFrame(columns=[
                "Fecha", "Concepto", "Proveedor", "Monto", "Forma de Pago", 
                "Banco", "Responsable del pago", "Finalidad", "Deducible"
            ])
 
        return df_prospectos, df_polizas, df_cobranza, df_seguimiento, df_operacion

    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# Función para guardar datos (invalida el cache)
def guardar_datos(df_prospectos=None, df_polizas=None, df_cobranza=None, df_seguimiento=None, df_operacion=None):
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

        # Actualizar hoja de Operación si se proporciona
        if df_operacion is not None:
            try:
                worksheet_operacion = spreadsheet.worksheet("Operacion")
                worksheet_operacion.clear()
                if not df_operacion.empty:
                    data = [df_operacion.columns.values.tolist()] + df_operacion.fillna('').values.tolist()
                    worksheet_operacion.update(data, value_input_option='USER_ENTERED')
            except:
                # Crear hoja si no existe
                try:
                    worksheet_operacion = spreadsheet.add_worksheet(title="Operacion", rows=1000, cols=20)
                    if not df_operacion.empty:
                        data = [df_operacion.columns.values.tolist()] + df_operacion.fillna('').values.tolist()
                        worksheet_operacion.update(data, value_input_option='USER_ENTERED')
                except Exception as e:
                    st.error(f"❌ Error al crear/actualizar hoja 'Operacion': {e}")

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
# 🔧 FUNCIÓN CALCULAR_COBRANZA
# =========================
def calcular_cobranza():
    """
    Calcula los registros de cobranza basándose en las pólizas vigentes.
    """
    try:
        _, df_polizas, df_cobranza, _, _ = cargar_datos()

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
            max_recibos = 36

            while num_recibo <= max_recibos and fecha_actual_calc <= fecha_limite:
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

                    # Determinar estatus basado en fecha de vencimiento
                    if fecha_actual_calc.date() < hoy.date():
                        estatus = "Vencido"
                        comentario = "Cobranza vencida - registro tardío"
                        dias_restantes = (fecha_actual_calc - hoy).days
                        dias_atraso = abs(dias_restantes)
                    else:
                        estatus = "Pendiente"
                        comentario = ""
                        dias_restantes = (fecha_actual_calc - hoy).days
                        dias_atraso = 0

                    cobranza_mes.append({
                        "No. Póliza": no_poliza,
                        "Nombre/Razón Social": poliza.get("Nombre/Razón Social", ""),
                        "Mes Cobranza": mes_cobranza,
                        "Fecha Vencimiento": fecha_vencimiento,
                        "Prima de Recibo": monto_prima,
                        "Monto Pagado": 0,
                        "Fecha Pago": "",
                        "Estatus": estatus,
                        "Días Restantes": dias_restantes,
                        "Días Atraso": dias_atraso,
                        "Periodicidad": periodicidad,
                        "Moneda": moneda,
                        "Recibo": num_recibo,
                        "Clave de Emisión": poliza.get("Clave de Emisión", ""),
                        "Comentario": comentario,
                        "ID_Cobranza": f"{no_poliza}_R{num_recibo}"
                    })

                # Avanzar a la siguiente fecha según periodicidad
                if periodicidad == "ANUAL":
                    fecha_actual_calc += relativedelta(years=1)
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

        # Crear DataFrame
        df_resultado = pd.DataFrame(cobranza_mes)
        if df_resultado.empty:
            return df_resultado

        # Eliminar duplicados por ID único
        df_resultado = df_resultado.drop_duplicates(
            subset=["ID_Cobranza"], 
            keep="last"
        )

        return df_resultado

    except Exception as e:
        st.error(f"Error al calcular cobranza: {e}")
        return pd.DataFrame()

# ================================
# 🆕 NUEVA PESTAÑA: ASESORÍA AXA
# ================================
def mostrar_asesoria_axa():
    st.header("📈 Asesoría Financiera AXA")
    st.markdown("### Detección de necesidades financieras para una asesoría ideal")
    
    # Inicializar datos de asesoría si no existen
    if 'asesoria_data' not in st.session_state:
        st.session_state.asesoria_data = {
            'informacion_personal': {},
            'informacion_familiar': {},
            'informacion_financiera': {},
            'objetivos': {}
        }
    
    # Usar pestañas para organizar el formulario
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Información Personal", 
        "👨‍👩‍👧‍👦 Información Familiar", 
        "💰 Información Financiera", 
        "🎯 Objetivos Financieros",
        "📊 Reporte"
    ])
    
    with tab1:
        st.subheader("Información Personal")
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.asesoria_data['informacion_personal']['nombre'] = st.text_input(
                "Nombre completo*", 
                value=st.session_state.asesoria_data['informacion_personal'].get('nombre', '')
            )
            st.session_state.asesoria_data['informacion_personal']['telefono'] = st.text_input(
                "Teléfono*", 
                value=st.session_state.asesoria_data['informacion_personal'].get('telefono', '')
            )
            st.session_state.asesoria_data['informacion_personal']['email'] = st.text_input(
                "Email*", 
                value=st.session_state.asesoria_data['informacion_personal'].get('email', '')
            )
            
        with col2:
            st.session_state.asesoria_data['informacion_personal']['ocupacion'] = st.text_input(
                "Ocupación*", 
                value=st.session_state.asesoria_data['informacion_personal'].get('ocupacion', '')
            )
            st.session_state.asesoria_data['informacion_personal']['fumador'] = st.selectbox(
                "¿Has fumado en los últimos dos años?*", 
                options=["", "Sí", "No"],
                index=["", "Sí", "No"].index(st.session_state.asesoria_data['informacion_personal'].get('fumador', '')) if st.session_state.asesoria_data['informacion_personal'].get('fumador') in ["", "Sí", "No"] else 0
            )
            st.session_state.asesoria_data['informacion_personal']['agente'] = st.text_input(
                "Nombre del agente*", 
                value=st.session_state.asesoria_data['informacion_personal'].get('agente', '')
            )
    
    with tab2:
        st.subheader("Información Familiar")
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.asesoria_data['informacion_familiar']['estado_civil'] = st.selectbox(
                "Estado civil", 
                options=["", "Soltero", "Casado", "Unión libre", "Divorciado", "Viudo"],
                index=["", "Soltero", "Casado", "Unión libre", "Divorciado", "Viudo"].index(st.session_state.asesoria_data['informacion_familiar'].get('estado_civil', '')) if st.session_state.asesoria_data['informacion_familiar'].get('estado_civil') in ["", "Soltero", "Casado", "Unión libre", "Divorciado", "Viudo"] else 0
            )
            
            fecha_nacimiento = st.text_input(
                "Fecha de nacimiento (dd/mm/yyyy)", 
                value=st.session_state.asesoria_data['informacion_familiar'].get('fecha_nacimiento', ''),
                placeholder="dd/mm/yyyy"
            )
            st.session_state.asesoria_data['informacion_familiar']['fecha_nacimiento'] = fecha_nacimiento
            
            # Calcular edad si se proporciona fecha
            if fecha_nacimiento:
                try:
                    fecha_nac = datetime.strptime(fecha_nacimiento, "%d/%m/%Y")
                    hoy = datetime.now()
                    edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
                    st.session_state.asesoria_data['informacion_familiar']['edad'] = edad
                    st.info(f"Edad calculada: {edad} años")
                except:
                    st.session_state.asesoria_data['informacion_familiar']['edad'] = None
            
            st.session_state.asesoria_data['informacion_familiar']['hobbie'] = st.text_input(
                "¿Tienes algún hobbie? (opcional)", 
                value=st.session_state.asesoria_data['informacion_familiar'].get('hobbie', '')
            )
            
        with col2:
            st.session_state.asesoria_data['informacion_familiar']['nombre_pareja'] = st.text_input(
                "Nombre y edad de tu esposo(a)/pareja (opcional)", 
                value=st.session_state.asesoria_data['informacion_familiar'].get('nombre_pareja', '')
            )
            
            # Gestión de hijos
            num_hijos = st.number_input(
                "¿Cuántos hijos tienes?", 
                min_value=0, 
                max_value=10, 
                value=st.session_state.asesoria_data['informacion_familiar'].get('num_hijos', 0) or 0,
                step=1
            )
            st.session_state.asesoria_data['informacion_familiar']['num_hijos'] = num_hijos
            
            hijos = st.session_state.asesoria_data['informacion_familiar'].get('hijos', [])
            for i in range(num_hijos):
                col_hijo1, col_hijo2 = st.columns(2)
                with col_hijo1:
                    nombre_key = f"hijo_{i}_nombre"
                    if i >= len(hijos):
                        hijos.append({'nombre': '', 'edad': ''})
                    hijos[i]['nombre'] = st.text_input(
                        f"Nombre hijo(a) {i+1}", 
                        value=hijos[i]['nombre'],
                        key=nombre_key
                    )
                with col_hijo2:
                    edad_key = f"hijo_{i}_edad"
                    hijos[i]['edad'] = st.text_input(
                        f"Edad hijo(a) {i+1}", 
                        value=hijos[i]['edad'],
                        key=edad_key
                    )
            st.session_state.asesoria_data['informacion_familiar']['hijos'] = hijos
    
    with tab3:
        st.subheader("Información Financiera")
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.asesoria_data['informacion_financiera']['ingreso_mensual'] = st.number_input(
                "Ingreso mensual neto ($)*", 
                min_value=0.0,
                value=float(st.session_state.asesoria_data['informacion_financiera'].get('ingreso_mensual', 0)),
                step=100.0
            )
            st.session_state.asesoria_data['informacion_financiera']['gastos_mensuales'] = st.number_input(
                "Gastos mensuales totales ($)*", 
                min_value=0.0,
                value=float(st.session_state.asesoria_data['informacion_financiera'].get('gastos_mensuales', 0)),
                step=100.0
            )
            st.session_state.asesoria_data['informacion_financiera']['ahorro_actual'] = st.number_input(
                "Ahorro actual total ($)", 
                min_value=0.0,
                value=float(st.session_state.asesoria_data['informacion_financiera'].get('ahorro_actual', 0)),
                step=100.0
            )
            
        with col2:
            st.session_state.asesoria_data['informacion_financiera']['deudas_totales'] = st.number_input(
                "Deudas totales ($)", 
                min_value=0.0,
                value=float(st.session_state.asesoria_data['informacion_financiera'].get('deudas_totales', 0)),
                step=100.0
            )
            st.session_state.asesoria_data['informacion_financiera']['gastos_alimentacion'] = st.number_input(
                "Gastos en alimentación ($)", 
                min_value=0.0,
                value=float(st.session_state.asesoria_data['informacion_financiera'].get('gastos_alimentacion', 0)),
                step=100.0
            )
            st.session_state.asesoria_data['informacion_financiera']['gastos_vivienda'] = st.number_input(
                "Gastos en vivienda ($)", 
                min_value=0.0,
                value=float(st.session_state.asesoria_data['informacion_financiera'].get('gastos_vivienda', 0)),
                step=100.0
            )
    
    with tab4:
        st.subheader("Objetivos Financieros")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.asesoria_data['objetivos']['edad_retiro_deseada'] = st.number_input(
                "¿A qué edad te quieres retirar?", 
                min_value=30,
                max_value=80,
                value=st.session_state.asesoria_data['objetivos'].get('edad_retiro_deseada', 65),
                step=1
            )
            st.session_state.asesoria_data['objetivos']['ingreso_retiro_mensual'] = st.number_input(
                "¿Qué ingreso mensual deseas en tu retiro? ($)", 
                min_value=0.0,
                value=float(st.session_state.asesoria_data['objetivos'].get('ingreso_retiro_mensual', 0)),
                step=100.0
            )
            
            # Educación de hijos
            if st.session_state.asesoria_data['informacion_familiar'].get('num_hijos', 0) > 0:
                st.session_state.asesoria_data['objetivos']['costo_universidad_por_hijo'] = st.number_input(
                    "Costo estimado de universidad por hijo ($)", 
                    min_value=0.0,
                    value=float(st.session_state.asesoria_data['objetivos'].get('costo_universidad_por_hijo', 0)),
                    step=1000.0
                )
        
        with col2:
            st.session_state.asesoria_data['objetivos']['meses_proteccion_familiar'] = st.number_input(
                "¿Cuántos meses de gastos quieres cubrir para tu familia?", 
                min_value=0,
                max_value=24,
                value=st.session_state.asesoria_data['objetivos'].get('meses_proteccion_familiar', 6),
                step=1
            )
            
            st.session_state.asesoria_data['objetivos']['proyecto_futuro'] = st.text_input(
                "¿Tienes algún proyecto a mediano/largo plazo? (ej: casa, negocio)", 
                value=st.session_state.asesoria_data['objetivos'].get('proyecto_futuro', '')
            )
            
            if st.session_state.asesoria_data['objetivos'].get('proyecto_futuro'):
                st.session_state.asesoria_data['objetivos']['costo_proyecto'] = st.number_input(
                    f"Costo estimado de {st.session_state.asesoria_data['objetivos'].get('proyecto_futuro')} ($)", 
                    min_value=0.0,
                    value=float(st.session_state.asesoria_data['objetivos'].get('costo_proyecto', 0)),
                    step=1000.0
                )
    
    with tab5:
        st.subheader("📊 Reporte Financiero")
        
        # Botón para generar reporte
        if st.button("📈 Generar Reporte Completo", type="primary", use_container_width=True):
            with st.spinner("Generando reporte financiero..."):
                # Calcular métricas
                metricas = calcular_metricas_financieras()
                
                if metricas:
                    # Mostrar resumen
                    st.success("✅ Reporte generado exitosamente")
                    
                    # Crear columnas para métricas clave
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Capacidad de Ahorro Mensual", f"${metricas['ahorro_mensual']:,.2f}")
                    with col2:
                        st.metric("Porcentaje de Ahorro", f"{metricas['porcentaje_ahorro']:.1f}%")
                    with col3:
                        st.metric("Fondo Emergencia Recomendado", f"${metricas['fondo_emergencia_recomendado']:,.2f}")
                    
                    # Mostrar gráficos
                    st.subheader("📊 Gráficos Financieros")
                    
                    # Gráfico 1: Distribución financiera actual
                    fig1 = crear_grafico_pastel_gastos(metricas)
                    if fig1:
                        st.pyplot(fig1)
                    
                    # Gráfico 2: Metas financieras
                    fig2 = crear_grafico_barras_metas(metricas)
                    if fig2:
                        st.pyplot(fig2)
                    
                    # Gráfico 3: Comparación de ahorro
                    fig3 = crear_grafico_ahorro(metricas)
                    if fig3:
                        st.pyplot(fig3)
                    
                    # Generar archivo Excel para descarga
                    excel_buffer = generar_excel_reporte(metricas)
                    
                    # Botón para descargar Excel
                    st.download_button(
                        label="📥 Descargar Reporte en Excel",
                        data=excel_buffer,
                        file_name=f"Reporte_Financiero_{st.session_state.asesoria_data['informacion_personal'].get('nombre', 'Cliente')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                    
                    # Botón para descargar PDF (simulado)
                    if st.button("📄 Generar PDF del Reporte", use_container_width=True):
                        st.info("La generación de PDF estará disponible en la próxima actualización")
                else:
                    st.error("❌ Error al calcular las métricas financieras")
        
        # Mostrar datos actuales si ya existen
        if 'metricas' in st.session_state:
            st.info("Ya tienes un reporte generado. Haz clic en 'Generar Reporte Completo' para actualizarlo.")

def calcular_metricas_financieras():
    """Calcula métricas financieras basadas en los datos ingresados"""
    try:
        datos = st.session_state.asesoria_data
        
        # Extraer datos básicos
        ingreso_mensual = datos['informacion_financiera'].get('ingreso_mensual', 0)
        gastos_mensuales = datos['informacion_financiera'].get('gastos_mensuales', 0)
        ahorro_actual = datos['informacion_financiera'].get('ahorro_actual', 0)
        edad = datos['informacion_familiar'].get('edad', 30)
        
        # Cálculos básicos
        ingreso_anual = ingreso_mensual * 12
        gastos_anuales = gastos_mensuales * 12
        ahorro_mensual = ingreso_mensual - gastos_mensuales
        ahorro_anual = ahorro_mensual * 12
        porcentaje_ahorro = (ahorro_mensual / ingreso_mensual * 100) if ingreso_mensual > 0 else 0
        
        # Fondo de emergencia recomendado (6 meses de gastos)
        fondo_emergencia_recomendado = gastos_mensuales * 6
        
        # Necesidad de protección familiar
        meses_proteccion = datos['objetivos'].get('meses_proteccion_familiar', 6)
        necesidad_proteccion = gastos_mensuales * meses_proteccion
        
        # Necesidad de retiro
        edad_retiro_deseada = datos['objetivos'].get('edad_retiro_deseada', 65)
        años_hasta_retiro = edad_retiro_deseada - edad if edad_retiro_deseada > edad else 0
        ingreso_retiro_mensual = datos['objetivos'].get('ingreso_retiro_mensual', 0)
        años_retiro = 80 - edad_retiro_deseada  # Esperanza de vida 80 años
        necesidad_retiro_total = ingreso_retiro_mensual * 12 * años_retiro
        
        # Necesidad educación
        necesidad_educacion = 0
        num_hijos = datos['informacion_familiar'].get('num_hijos', 0)
        hijos = datos['informacion_familiar'].get('hijos', [])
        costo_universidad = datos['objetivos'].get('costo_universidad_por_hijo', 0)
        
        for i in range(min(num_hijos, len(hijos))):
            if hijos[i]['edad']:
                try:
                    edad_hijo = int(hijos[i]['edad'])
                    if edad_hijo < 18:
                        necesidad_educacion += costo_universidad
                except:
                    necesidad_educacion += costo_universidad
        
        # Necesidad proyecto
        necesidad_proyecto = datos['objetivos'].get('costo_proyecto', 0)
        
        # Metas financieras
        metas = {
            'Protección': necesidad_proteccion,
            'Retiro': necesidad_retiro_total,
            'Educación': necesidad_educacion,
            'Proyecto': necesidad_proyecto
        }
        
        # Ahorro recomendado (10% del ingreso anual)
        ahorro_recomendado_10 = ingreso_anual * 0.10
        ahorro_recomendado_7 = ingreso_mensual * 0.07 * 12
        
        metricas = {
            'ingreso_anual': ingreso_anual,
            'gastos_anuales': gastos_anuales,
            'ahorro_mensual': ahorro_mensual,
            'ahorro_anual': ahorro_anual,
            'porcentaje_ahorro': porcentaje_ahorro,
            'fondo_emergencia_recomendado': fondo_emergencia_recomendado,
            'años_hasta_retiro': años_hasta_retiro,
            'necesidad_retiro_total': necesidad_retiro_total,
            'necesidad_educacion': necesidad_educacion,
            'necesidad_proteccion': necesidad_proteccion,
            'ahorro_recomendado_10': ahorro_recomendado_10,
            'ahorro_recomendado_7': ahorro_recomendado_7,
            'metas': metas,
            'datos_basicos': {
                'ingreso_mensual': ingreso_mensual,
                'gastos_mensuales': gastos_mensuales,
                'ahorro_actual': ahorro_actual,
                'deudas_totales': datos['informacion_financiera'].get('deudas_totales', 0)
            }
        }
        
        # Guardar en session state para uso posterior
        st.session_state.metricas_financieras = metricas
        return metricas
        
    except Exception as e:
        st.error(f"Error al calcular métricas: {str(e)}")
        return None

def crear_grafico_pastel_gastos(metricas):
    """Crea gráfico de pastel para distribución de finanzas"""
    try:
        fig, ax = plt.subplots(figsize=(8, 6))
        
        datos = metricas['datos_basicos']
        labels = ['Gastos Mensuales', 'Ahorro Actual', 'Deudas Totales']
        sizes = [
            datos['gastos_mensuales'],
            datos['ahorro_actual'],
            datos['deudas_totales']
        ]
        
        # Filtrar valores cero
        filtered_labels = []
        filtered_sizes = []
        colors = []
        
        for i, (label, size) in enumerate(zip(labels, sizes)):
            if size > 0:
                filtered_labels.append(label)
                filtered_sizes.append(size)
                colors.append(list(COLORES_AXA.values())[i % len(COLORES_AXA)])
        
        if filtered_sizes:
            wedges, texts, autotexts = ax.pie(
                filtered_sizes, 
                labels=filtered_labels,
                colors=colors,
                autopct='%1.1f%%',
                startangle=90,
                textprops={'fontsize': 9}
            )
            
            ax.set_title('Distribución Financiera Actual', 
                        fontsize=14, 
                        fontweight='bold',
                        color=COLORES_AXA['azul_principal'])
            
            plt.tight_layout()
            return fig
        return None
        
    except Exception as e:
        st.error(f"Error al crear gráfico de pastel: {str(e)}")
        return None

def crear_grafico_barras_metas(metricas):
    """Crea gráfico de barras para metas financieras"""
    try:
        fig, ax = plt.subplots(figsize=(10, 6))
        
        metas = metricas['metas']
        labels = list(metas.keys())
        valores = list(metas.values())
        
        # Filtrar metas con valor > 0
        filtered_labels = []
        filtered_valores = []
        for label, valor in zip(labels, valores):
            if valor > 0:
                filtered_labels.append(label)
                filtered_valores.append(valor)
        
        if filtered_valores:
            bars = ax.bar(filtered_labels, filtered_valores, 
                         color=[COLORES_AXA['azul_principal'],
                               COLORES_AXA['verde_oscuro'],
                               COLORES_AXA['verde_agua'],
                               COLORES_AXA['azul_claro']][:len(filtered_labels)])
            
            # Agregar valores en las barras
            for bar, valor in zip(bars, filtered_valores):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                       f'${valor:,.0f}',
                       ha='center', va='bottom',
                       fontsize=9, fontweight='bold')
            
            ax.set_title('Metas Financieras por Categoría', 
                        fontsize=14, 
                        fontweight='bold',
                        color=COLORES_AXA['azul_principal'])
            ax.set_ylabel('Monto ($)', fontsize=12)
            ax.grid(axis='y', alpha=0.3)
            ax.set_axisbelow(True)
            
            # Formatear eje Y
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
            
            plt.xticks(rotation=15)
            plt.tight_layout()
            return fig
        return None
        
    except Exception as e:
        st.error(f"Error al crear gráfico de barras: {str(e)}")
        return None

def crear_grafico_ahorro(metricas):
    """Crea gráfico comparativo de ahorro"""
    try:
        fig, ax = plt.subplots(figsize=(8, 6))
        
        datos = metricas['datos_basicos']
        labels = ['Ahorro Actual', 'Ahorro Recomendado 10%', 'Ahorro Recomendado 7%']
        valores = [
            datos['ahorro_actual'],
            metricas['ahorro_recomendado_10'],
            metricas['ahorro_recomendado_7']
        ]
        
        bars = ax.bar(labels, valores, 
                     color=[COLORES_AXA['verde_agua'], 
                           COLORES_AXA['azul_principal'], 
                           COLORES_AXA['azul_claro']])
        
        # Agregar valores
        for bar, valor in zip(bars, valores):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                   f'${valor:,.0f}',
                   ha='center', va='bottom',
                   fontsize=9, fontweight='bold')
        
        ax.set_title('Comparación de Ahorro', 
                    fontsize=14, 
                    fontweight='bold',
                    color=COLORES_AXA['azul_principal'])
        ax.set_ylabel('Monto ($)', fontsize=12)
        ax.grid(axis='y', alpha=0.3)
        ax.set_axisbelow(True)
        
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))
        plt.xticks(rotation=15)
        plt.tight_layout()
        return fig
        
    except Exception as e:
        st.error(f"Error al crear gráfico de ahorro: {str(e)}")
        return None

def generar_excel_reporte(metricas):
    """Genera archivo Excel con el reporte financiero"""
    try:
        # Crear un buffer en memoria para el Excel
        output = io.BytesIO()
        
        # Crear un Excel writer
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Hoja 1: Resumen Ejecutivo
            datos_personales = st.session_state.asesoria_data['informacion_personal']
            datos_familiares = st.session_state.asesoria_data['informacion_familiar']
            
            resumen_data = {
                'SECCIÓN': [
                    'INFORMACIÓN PERSONAL',
                    'Nombre',
                    'Teléfono',
                    'Email',
                    'Ocupación',
                    'Agente',
                    'Fecha Nacimiento',
                    'Edad',
                    'Estado Civil',
                    '',
                    'INFORMACIÓN FINANCIERA',
                    'Ingreso Mensual',
                    'Gastos Mensuales',
                    'Ahorro Actual',
                    'Deudas Totales',
                    'Capacidad de Ahorro Mensual',
                    'Porcentaje de Ahorro',
                    '',
                    'METAS FINANCIERAS',
                    'Fondo Emergencia Recomendado',
                    'Necesidad Protección Familiar',
                    'Necesidad Retiro Total',
                    'Necesidad Educación',
                    'Ahorro Recomendado 10%',
                    'Ahorro Recomendado 7%'
                ],
                'VALOR': [
                    '',
                    datos_personales.get('nombre', ''),
                    datos_personales.get('telefono', ''),
                    datos_personales.get('email', ''),
                    datos_personales.get('ocupacion', ''),
                    datos_personales.get('agente', ''),
                    datos_familiares.get('fecha_nacimiento', ''),
                    datos_familiares.get('edad', ''),
                    datos_familiares.get('estado_civil', ''),
                    '',
                    '',
                    f"${metricas['datos_basicos']['ingreso_mensual']:,.2f}",
                    f"${metricas['datos_basicos']['gastos_mensuales']:,.2f}",
                    f"${metricas['datos_basicos']['ahorro_actual']:,.2f}",
                    f"${metricas['datos_basicos']['deudas_totales']:,.2f}",
                    f"${metricas['ahorro_mensual']:,.2f}",
                    f"{metricas['porcentaje_ahorro']:.1f}%",
                    '',
                    '',
                    f"${metricas['fondo_emergencia_recomendado']:,.2f}",
                    f"${metricas['necesidad_proteccion']:,.2f}",
                    f"${metricas['necesidad_retiro_total']:,.2f}",
                    f"${metricas['necesidad_educacion']:,.2f}",
                    f"${metricas['ahorro_recomendado_10']:,.2f}",
                    f"${metricas['ahorro_recomendado_7']:,.2f}"
                ]
            }
            
            df_resumen = pd.DataFrame(resumen_data)
            df_resumen.to_excel(writer, sheet_name='RESUMEN EJECUTIVO', index=False)
            
            # Hoja 2: Detalle de Metas
            metas_data = {
                'Meta': ['Protección Familiar', 'Retiro', 'Educación', 'Proyecto Futuro'],
                'Monto Requerido': [
                    metricas['metas']['Protección'],
                    metricas['metas']['Retiro'],
                    metricas['metas']['Educación'],
                    metricas['metas']['Proyecto']
                ],
                'Descripción': [
                    f"{st.session_state.asesoria_data['objetivos'].get('meses_proteccion_familiar', 6)} meses de gastos",
                    f"Ingreso mensual deseado: ${st.session_state.asesoria_data['objetivos'].get('ingreso_retiro_mensual', 0):,.2f}",
                    f"Para {st.session_state.asesoria_data['informacion_familiar'].get('num_hijos', 0)} hijo(s)",
                    st.session_state.asesoria_data['objetivos'].get('proyecto_futuro', 'No especificado')
                ]
            }
            
            df_metas = pd.DataFrame(metas_data)
            df_metas.to_excel(writer, sheet_name='METAS DETALLADAS', index=False)
            
            # Hoja 3: Plan de Ahorro
            plan_data = {
                'Recomendación': [
                    'Fondo de Emergencia',
                    'Ahorro para Protección',
                    'Ahorro para Retiro',
                    'Ahorro para Educación',
                    'Ahorro para Proyecto'
                ],
                'Monto Mensual Sugerido': [
                    metricas['fondo_emergencia_recomendado'] / 12,
                    metricas['metas']['Protección'] / 24 if metricas['metas']['Protección'] > 0 else 0,
                    metricas['metas']['Retiro'] / (metricas['años_hasta_retiro'] * 12) if metricas['años_hasta_retiro'] > 0 else 0,
                    metricas['metas']['Educación'] / 120 if metricas['metas']['Educación'] > 0 else 0,
                    metricas['metas']['Proyecto'] / 60 if metricas['metas']['Proyecto'] > 0 else 0
                ],
                'Plazo (meses)': [12, 24, metricas['años_hasta_retiro'] * 12, 120, 60],
                'Prioridad': ['Alta', 'Alta', 'Media', 'Media', 'Baja']
            }
            
            df_plan = pd.DataFrame(plan_data)
            df_plan.to_excel(writer, sheet_name='PLAN DE AHORRO', index=False)
        
        output.seek(0)
        return output
        
    except Exception as e:
        st.error(f"Error al generar Excel: {str(e)}")
        return None

# ---- Funciones para cada pestaña (solo incluyo las necesarias para mantener el código dentro del límite) ----
# Nota: Las funciones de las otras pestañas (mostrar_prospectos, mostrar_seguimiento, etc.) 
# permanecen igual que en tu código original. Solo estoy mostrando la nueva pestaña.

# ================================
# FUNCIÓN PRINCIPAL
# ================================
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
    df_prospectos, df_polizas, df_cobranza, df_seguimiento, df_operacion = cargar_datos()

    # Crear pestañas en el orden solicitado (incluyendo la nueva)
    tab_names = [
        "👥 Prospectos", 
        "📞 Seguimiento",
        "👤 Registro de Cliente", 
        "🔍 Consulta de Clientes",
        "🆕 Póliza Nueva",
        "🔄 Renovaciones",
        "💰 Cobranza",
        "💰 Operación",
        "📈 Asesoría AXA"  # NUEVA PESTAÑA
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
    elif st.session_state.active_tab == "💰 Operación":
        mostrar_operacion(df_operacion)
    elif st.session_state.active_tab == "📈 Asesoría AXA":  # NUEVA PESTAÑA
        mostrar_asesoria_axa()

# ================================
# EJECUTAR LA APLICACIÓN
# ================================
if __name__ == "__main__":
    main()
