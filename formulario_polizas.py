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
 - NUEVA PESTAÑA: Asesoría Rizkora con generación de reporte financiero
"""

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import re
from dateutil.relativedelta import relativedelta
import numpy as np
import io
import matplotlib.pyplot as plt
import warnings
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import tempfile
warnings.filterwarnings('ignore')

# ================================
# CONFIGURACIÓN DE COLORES Rizkora
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
# ================================
# LOGO RIZKORA
# ================================
st.image("logo_vectorizado.png", width=250)

# Opciones
OPCIONES_PROMOCION = ["Sí", "No"]
OPCIONES_PRODUCTO = [
    "AHORRO",
    "API",
    "APE",
    "APC",
    "AUTO",
    "DAÑOS",
    "EDUCACIONAL",
    "FLOTILLA",
    "GMMC",
    "GMMI",
    "HOGAR",
    "OV",
    "PENDIENTE",
    "PPR",
    "TEMPORAL",
    "VG",
    "VIAJERO",
    "VPL"
]
OPCIONES_PAGO = ["CARGO TDC", "CARGO TDD","PAGO REFERENCIADO", "TRANSFERENCIA"]
OPCIONES_ASEG = [ "ALLIANZ", "ATLAS", "AXA","BANORTE", "GNP", "HIR", "PREVEM", "QUALITAS", "SKANDIA", "THONA", "ZURICH"]
OPCIONES_BANCO = ["NINGUNO", "AMERICAN EXPRESS", "BBVA", "BANAMEX", "BANCOMER", "BANREGIO", "HSBC", "SANTANDER"]
OPCIONES_PERSONA = ["MORAL", "FÍSICA"]
OPCIONES_MONEDA = ["MXN", "UDIS", "DLLS"]
OPCIONES_ESTATUS_SEGUIMIENTO = ["Seguimiento", "Descartado", "Convertido"]
OPCIONES_ESTADO_POLIZA = ["VIGENTE", "CANCELADO", "TERMINADO"]
OPCIONES_CONCEPTO_OPERACION = [ "Contabilidad","Gasolina", "Impuestos","Papelería","Patrocinio","Pautas Publicitarias", "Promocionales","Promoción de Regalo", "Redes y Mercadotecnia", "Tarjetas"]
OPCIONES_FORMA_PAGO_OPERACION = ["Efectivo", "TDC", "TDD", "Transferencia"]
OPCIONES_DEDUCIBLE = ["Sí", "No"]
OPCIONES_ESTATUS_COBRANZA = ["Pendiente", "Pagado", "Vencido", "Cancelado"]

# Función auxiliar para obtener índices de selectbox
def obtener_indice_selectbox(valor, opciones):
    """Obtiene el índice correcto para selectbox considerando el valor vacío"""
    if valor is None or valor == "" or str(valor).strip() == "":
        return 0  # Primer elemento vacío
    
    # Crear lista completa con elemento vacío
    opciones_completas = [""] + opciones
    
    try:
        return opciones_completas.index(valor)
    except ValueError:
        # Si el valor no está en la lista, buscar coincidencias parciales
        valor_str = str(valor).strip().upper()
        for i, opcion in enumerate(opciones_completas):
            if opcion and valor_str == str(opcion).strip().upper():
                return i
        return 0  # Por defecto, primer elemento vacío

# Inicializar estado de sesión
if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "👥 Prospectos"
if 'notas_prospecto_actual' not in st.session_state:
    st.session_state.notas_prospecto_actual = ""
if 'asesoria_data' not in st.session_state:
    st.session_state.asesoria_data = {
        'informacion_personal': {},
        'informacion_familiar': {},
        'informacion_financiera': {},
        'objetivos': {}
    }
if 'metricas_financieras' not in st.session_state:
    st.session_state.metricas_financieras = None
if 'modo_edicion_prospectos' not in st.session_state:
    st.session_state.modo_edicion_prospectos = False
if 'prospecto_editando' not in st.session_state:
    st.session_state.prospecto_editando = None
if 'prospecto_data' not in st.session_state:
    st.session_state.prospecto_data = {}
if 'form_key' not in st.session_state:
    st.session_state.form_key = 0
if 'modo_edicion_operacion' not in st.session_state:
    st.session_state.modo_edicion_operacion = False
if 'operacion_editando' not in st.session_state:
    st.session_state.operacion_editando = None
if 'operacion_data' not in st.session_state:
    st.session_state.operacion_data = {}
if 'cobranza_seleccionada' not in st.session_state:
    st.session_state.cobranza_seleccionada = None
if 'info_cobranza_actual' not in st.session_state:
    st.session_state.info_cobranza_actual = None
if 'filtro_cobranza' not in st.session_state:
    st.session_state.filtro_cobranza = True
if 'editando_cliente' not in st.session_state:
    st.session_state.editando_cliente = False
if 'cliente_data_edit' not in st.session_state:
    st.session_state.cliente_data_edit = {}
if 'editando_poliza' not in st.session_state:
    st.session_state.editando_poliza = False
if 'poliza_data_edit' not in st.session_state:
    st.session_state.poliza_data_edit = {}

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
    MODIFICADO: Excluye pólizas canceladas y verifica fecha de cancelación
    """
    try:
        _, df_polizas, df_cobranza, _, _ = cargar_datos()

        if df_polizas.empty:
            return pd.DataFrame()

        # Filtrar SOLO pólizas vigentes (excluir canceladas)
        df_vigentes = df_polizas[df_polizas["Estado"].astype(str).str.upper() == "VIGENTE"]
        if df_vigentes.empty:
            return pd.DataFrame()

        hoy = datetime.now()
        fecha_limite = hoy + timedelta(days=60)
        cobranza_mes = []

        def parse_monto(valor):
            if pd.isna(valor) or str(valor).strip() == "":
                return 0.0
            valor = str(valor).replace('$', '').replace(',', '').replace(' ', '').strip()
            try:
                return float(valor)
            except:
                return 0.0

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
            
            primer_pago = parse_monto(poliza.get("Primer Pago", 0))
            pagos_subsecuentes = parse_monto(poliza.get("Pagos Subsecuentes", 0))
            
            if pagos_subsecuentes == 0:
                pagos_subsecuentes = primer_pago

            inicio_vigencia_str = poliza.get("Inicio Vigencia", "")
            if not no_poliza or not inicio_vigencia_str:
                continue

            inicio_vigencia = safe_date_convert(inicio_vigencia_str)
            if inicio_vigencia is None:
                continue

            fecha_actual_calc = inicio_vigencia
            num_recibo = 1
            max_recibos = 36

            while num_recibo <= max_recibos and fecha_actual_calc <= fecha_limite:
                mes_cobranza = fecha_actual_calc.strftime("%m/%Y")
                fecha_vencimiento = fecha_actual_calc.strftime("%d/%m/%Y")

                existe_registro = False
                if not df_cobranza.empty and "No. Póliza" in df_cobranza.columns and "Recibo" in df_cobranza.columns:
                    existe_registro = (
                        (df_cobranza["No. Póliza"].astype(str).str.strip() == no_poliza) &
                        (df_cobranza["Recibo"] == num_recibo)
                    ).any()

                if not existe_registro:
                    if num_recibo == 1:
                        monto_prima = primer_pago
                    else:
                        monto_prima = pagos_subsecuentes

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

                if periodicidad == "CONTADO":
                    fecha_actual_calc += relativedelta(years=1)
                elif periodicidad == "TRIMESTRAL":
                    fecha_actual_calc += relativedelta(months=3)
                elif periodicidad == "SEMESTRAL":
                    fecha_actual_calc += relativedelta(months=6)
                elif periodicidad == "MENSUAL":
                    fecha_actual_calc += relativedelta(months=1)
                else:
                    fecha_actual_calc += relativedelta(months=1)

                num_recibo += 1

        df_resultado = pd.DataFrame(cobranza_mes)
        if df_resultado.empty:
            return df_resultado

        df_resultado = df_resultado.drop_duplicates(
            subset=["ID_Cobranza"], 
            keep="last"
        )

        return df_resultado

    except Exception as e:
        st.error(f"Error al calcular cobranza: {e}")
        return pd.DataFrame()
def cancelar_recibos_poliza(no_poliza, fecha_cancelacion, df_cobranza):
    """
    Cancela automáticamente los recibos futuros cuando se cancela una póliza
    
    Args:
        no_poliza: Número de póliza cancelada
        fecha_cancelacion: Fecha en que se canceló la póliza (dd/mm/yyyy)
        df_cobranza: DataFrame de cobranza
    
    Returns:
        DataFrame actualizado
    """
    try:
        if df_cobranza.empty:
            return df_cobranza
        
        # Convertir fecha de cancelación
        try:
            fecha_cancel_dt = datetime.strptime(fecha_cancelacion, "%d/%m/%Y")
        except:
            st.warning("No se pudo procesar la fecha de cancelación para actualizar recibos")
            return df_cobranza
        
        # Filtrar recibos de esta póliza
        mask_poliza = df_cobranza["No. Póliza"].astype(str).str.strip() == str(no_poliza).strip()
        
        # Para cada recibo de esta póliza
        for idx in df_cobranza[mask_poliza].index:
            fecha_vencimiento_str = df_cobranza.loc[idx, "Fecha Vencimiento"]
            estatus_actual = df_cobranza.loc[idx, "Estatus"]
            
            # Solo procesar recibos pendientes o vencidos
            if estatus_actual not in ["Pendiente", "Vencido"]:
                continue
            
            try:
                fecha_venc_dt = datetime.strptime(str(fecha_vencimiento_str), "%d/%m/%Y")
                
                # Si el vencimiento es posterior a la cancelación, cancelar el recibo
                if fecha_venc_dt > fecha_cancel_dt:
                    df_cobranza.loc[idx, "Estatus"] = "Cancelado"
                    df_cobranza.loc[idx, "Comentario"] = f"Cancelado automáticamente - Póliza cancelada el {fecha_cancelacion}"
                    df_cobranza.loc[idx, "Prima de Recibo"] = 0
                    df_cobranza.loc[idx, "Monto Pagado"] = 0
            except:
                continue
        
        return df_cobranza
        
    except Exception as e:
        st.error(f"Error al cancelar recibos: {e}")
        return df_cobranza
def mostrar_gestion_recibos(df_cobranza):
    """
    Permite gestionar (eliminar/cancelar) recibos de cobranza individualmente
    """
    st.subheader("🗑️ Gestión de Recibos de Cobranza")
    
    if df_cobranza.empty:
        st.info("No hay recibos para gestionar")
        return df_cobranza
    
    # Filtrar solo recibos pendientes o vencidos
    df_gestionables = df_cobranza[df_cobranza['Estatus'].isin(['Pendiente', 'Vencido'])]
    
    if df_gestionables.empty:
        st.success("No hay recibos pendientes o vencidos para gestionar")
        return df_cobranza
    
    # Crear lista de recibos
    opciones_recibos = []
    for idx, row in df_gestionables.iterrows():
        descripcion = f"{row['No. Póliza']} - Recibo {row['Recibo']} - {row.get('Nombre/Razón Social', '')} - Vence: {row.get('Fecha Vencimiento', '')} - {row.get('Estatus', '')}"
        opciones_recibos.append({
            'descripcion': descripcion,
            'id_cobranza': f"{row['No. Póliza']}_R{row['Recibo']}",
            'index': idx,
            'datos': row
        })
    
    # Selector
    recibo_seleccionado = st.selectbox(
        "Seleccionar Recibo para Cancelar/Eliminar",
        options=[""] + [r['descripcion'] for r in opciones_recibos],
        key="select_eliminar_recibo"
    )
    
    if recibo_seleccionado:
        recibo_data = next((r for r in opciones_recibos if r['descripcion'] == recibo_seleccionado), None)
        
        if recibo_data:
            st.warning(f"**⚠️ Atención:** Está por cancelar el recibo #{recibo_data['datos']['Recibo']}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Póliza:** {recibo_data['datos']['No. Póliza']}")
                st.write(f"**Cliente:** {recibo_data['datos'].get('Nombre/Razón Social', '')}")
                st.write(f"**Prima:** ${recibo_data['datos'].get('Prima de Recibo', 0):,.2f}")
            
            with col2:
                st.write(f"**Vencimiento:** {recibo_data['datos'].get('Fecha Vencimiento', '')}")
                st.write(f"**Estatus:** {recibo_data['datos'].get('Estatus', '')}")
            
            motivo = st.text_area(
                "Motivo de la Cancelación*",
                placeholder="Explique por qué se cancela este recibo...",
                key="motivo_cancelacion_recibo"
            )
            
            if st.button("🗑️ Confirmar Cancelación del Recibo", type="primary"):
                if not motivo.strip():
                    st.warning("Debe proporcionar un motivo para la cancelación")
                else:
                    # Actualizar el recibo
                    idx = recibo_data['index']
                    df_cobranza.loc[idx, 'Estatus'] = 'Cancelado'
                    df_cobranza.loc[idx, 'Prima de Recibo'] = 0
                    df_cobranza.loc[idx, 'Monto Pagado'] = 0
                    df_cobranza.loc[idx, 'Comentario'] = f"Cancelado manualmente: {motivo}"
                    
                    if guardar_datos(df_cobranza=df_cobranza):
                        st.success("✅ Recibo cancelado exitosamente")
                        st.rerun()
                    else:
                        st.error("❌ Error al cancelar el recibo")
    
    return df_cobranza
# ================================
# 🆕 NUEVA PESTAÑA: ASESORÍA Rizkora
# ================================
def mostrar_asesoria_axa():
    st.header("📈 Asesoría Financiera Rizkora")
    st.markdown("### Detección de necesidades financieras para una asesoría ideal")
    
    # Asegurar que la estructura de datos esté inicializada correctamente
    if 'asesoria_data' not in st.session_state:
        st.session_state.asesoria_data = {
            'informacion_personal': {},
            'informacion_familiar': {},
            'informacion_financiera': {},
            'objetivos': {}
        }
    
    # Asegurar que todos los sub-diccionarios existan
    for key in ['informacion_personal', 'informacion_familiar', 'informacion_financiera', 'objetivos']:
        if key not in st.session_state.asesoria_data:
            st.session_state.asesoria_data[key] = {}
    
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
            # Asegurar que la clave exista antes de acceder
            nombre = st.session_state.asesoria_data['informacion_personal'].get('nombre', '')
            st.session_state.asesoria_data['informacion_personal']['nombre'] = st.text_input(
                "Nombre completo*", 
                value=nombre,
                placeholder="Ingrese nombre completo"
            )
            
            telefono = st.session_state.asesoria_data['informacion_personal'].get('telefono', '')
            st.session_state.asesoria_data['informacion_personal']['telefono'] = st.text_input(
                "Teléfono*", 
                value=telefono,
                placeholder="Ingrese teléfono"
            )
            
            email = st.session_state.asesoria_data['informacion_personal'].get('email', '')
            st.session_state.asesoria_data['informacion_personal']['email'] = st.text_input(
                "Email*", 
                value=email,
                placeholder="Ingrese correo electrónico"
            )
            
        with col2:
            ocupacion = st.session_state.asesoria_data['informacion_personal'].get('ocupacion', '')
            st.session_state.asesoria_data['informacion_personal']['ocupacion'] = st.text_input(
                "Ocupación*", 
                value=ocupacion,
                placeholder="Ingrese ocupación"
            )
            
            fumador = st.session_state.asesoria_data['informacion_personal'].get('fumador', '')
            fumador_index = obtener_indice_selectbox(fumador, ["Sí", "No"])
            st.session_state.asesoria_data['informacion_personal']['fumador'] = st.selectbox(
                "¿Has fumado en los últimos dos años?*", 
                options=["", "Sí", "No"],
                index=fumador_index
            )
            
            agente = st.session_state.asesoria_data['informacion_personal'].get('agente', '')
            st.session_state.asesoria_data['informacion_personal']['agente'] = st.text_input(
                "Nombre del agente*", 
                value=agente,
                placeholder="Ingrese nombre del agente"
            )
    
    with tab2:
        st.subheader("Información Familiar")
        col1, col2 = st.columns(2)
        
        with col1:
            estado_civil = st.session_state.asesoria_data['informacion_familiar'].get('estado_civil', '')
            estado_civil_index = obtener_indice_selectbox(estado_civil, ["Soltero", "Casado", "Unión libre", "Divorciado", "Viudo"])
            st.session_state.asesoria_data['informacion_familiar']['estado_civil'] = st.selectbox(
                "Estado civil", 
                options=["", "Soltero", "Casado", "Unión libre", "Divorciado", "Viudo"],
                index=estado_civil_index
            )
            
            fecha_nacimiento = st.session_state.asesoria_data['informacion_familiar'].get('fecha_nacimiento', '')
            st.session_state.asesoria_data['informacion_familiar']['fecha_nacimiento'] = st.text_input(
                "Fecha de nacimiento (dd/mm/yyyy)", 
                value=fecha_nacimiento,
                placeholder="dd/mm/yyyy"
            )
            
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
            
            hobbie = st.session_state.asesoria_data['informacion_familiar'].get('hobbie', '')
            st.session_state.asesoria_data['informacion_familiar']['hobbie'] = st.text_input(
                "¿Tienes algún hobbie? (opcional)", 
                value=hobbie,
                placeholder="Ingrese hobbies"
            )
            
        with col2:
            nombre_pareja = st.session_state.asesoria_data['informacion_familiar'].get('nombre_pareja', '')
            st.session_state.asesoria_data['informacion_familiar']['nombre_pareja'] = st.text_input(
                "Nombre y edad de tu esposo(a)/pareja (opcional)", 
                value=nombre_pareja,
                placeholder="Nombre y edad"
            )
            
            # Gestión de hijos
            num_hijos = st.session_state.asesoria_data['informacion_familiar'].get('num_hijos', 0) or 0
            st.session_state.asesoria_data['informacion_familiar']['num_hijos'] = st.number_input(
                "¿Cuántos hijos tienes?", 
                min_value=0, 
                max_value=10, 
                value=int(num_hijos),
                step=1
            )
            
            hijos = st.session_state.asesoria_data['informacion_familiar'].get('hijos', [])
            for i in range(st.session_state.asesoria_data['informacion_familiar']['num_hijos']):
                col_hijo1, col_hijo2 = st.columns(2)
                with col_hijo1:
                    nombre_key = f"hijo_{i}_nombre"
                    if i >= len(hijos):
                        hijos.append({'nombre': '', 'edad': ''})
                    hijos[i]['nombre'] = st.text_input(
                        f"Nombre hijo(a) {i+1}", 
                        value=hijos[i]['nombre'],
                        key=nombre_key,
                        placeholder="Nombre"
                    )
                with col_hijo2:
                    edad_key = f"hijo_{i}_edad"
                    hijos[i]['edad'] = st.text_input(
                        f"Edad hijo(a) {i+1}", 
                        value=hijos[i]['edad'],
                        key=edad_key,
                        placeholder="Edad"
                    )
            st.session_state.asesoria_data['informacion_familiar']['hijos'] = hijos
    
    with tab3:
        st.subheader("Información Financiera")
        col1, col2 = st.columns(2)
        
        with col1:
            ingreso_mensual = st.session_state.asesoria_data['informacion_financiera'].get('ingreso_mensual', 0)
            if isinstance(ingreso_mensual, str):
                try:
                    ingreso_mensual = float(ingreso_mensual)
                except:
                    ingreso_mensual = 0.0
            st.session_state.asesoria_data['informacion_financiera']['ingreso_mensual'] = st.number_input(
                "Ingreso mensual neto ($)*", 
                min_value=0.0,
                value=float(ingreso_mensual),
                step=100.0
            )
            
            gastos_mensuales = st.session_state.asesoria_data['informacion_financiera'].get('gastos_mensuales', 0)
            if isinstance(gastos_mensuales, str):
                try:
                    gastos_mensuales = float(gastos_mensuales)
                except:
                    gastos_mensuales = 0.0
            st.session_state.asesoria_data['informacion_financiera']['gastos_mensuales'] = st.number_input(
                "Gastos mensuales totales ($)*", 
                min_value=0.0,
                value=float(gastos_mensuales),
                step=100.0
            )
            
            ahorro_actual = st.session_state.asesoria_data['informacion_financiera'].get('ahorro_actual', 0)
            if isinstance(ahorro_actual, str):
                try:
                    ahorro_actual = float(ahorro_actual)
                except:
                    ahorro_actual = 0.0
            st.session_state.asesoria_data['informacion_financiera']['ahorro_actual'] = st.number_input(
                "Ahorro actual total ($)", 
                min_value=0.0,
                value=float(ahorro_actual),
                step=100.0
            )
            
        with col2:
            deudas_totales = st.session_state.asesoria_data['informacion_financiera'].get('deudas_totales', 0)
            if isinstance(deudas_totales, str):
                try:
                    deudas_totales = float(deudas_totales)
                except:
                    deudas_totales = 0.0
            st.session_state.asesoria_data['informacion_financiera']['deudas_totales'] = st.number_input(
                "Deudas totales ($)", 
                min_value=0.0,
                value=float(deudas_totales),
                step=100.0
            )
            
            gastos_alimentacion = st.session_state.asesoria_data['informacion_financiera'].get('gastos_alimentacion', 0)
            if isinstance(gastos_alimentacion, str):
                try:
                    gastos_alimentacion = float(gastos_alimentacion)
                except:
                    gastos_alimentacion = 0.0
            st.session_state.asesoria_data['informacion_financiera']['gastos_alimentacion'] = st.number_input(
                "Gastos en alimentación ($)", 
                min_value=0.0,
                value=float(gastos_alimentacion),
                step=100.0
            )
            
            gastos_vivienda = st.session_state.asesoria_data['informacion_financiera'].get('gastos_vivienda', 0)
            if isinstance(gastos_vivienda, str):
                try:
                    gastos_vivienda = float(gastos_vivienda)
                except:
                    gastos_vivienda = 0.0
            st.session_state.asesoria_data['informacion_financiera']['gastos_vivienda'] = st.number_input(
                "Gastos en vivienda ($)", 
                min_value=0.0,
                value=float(gastos_vivienda),
                step=100.0
            )
    
    with tab4:
        st.subheader("Objetivos Financieros")
        
        col1, col2 = st.columns(2)
        
        with col1:
            edad_retiro_deseada = st.session_state.asesoria_data['objetivos'].get('edad_retiro_deseada', 65)
            if isinstance(edad_retiro_deseada, str):
                try:
                    edad_retiro_deseada = int(edad_retiro_deseada)
                except:
                    edad_retiro_deseada = 65
            st.session_state.asesoria_data['objetivos']['edad_retiro_deseada'] = st.number_input(
                "¿A qué edad te quieres retirar?", 
                min_value=30,
                max_value=80,
                value=int(edad_retiro_deseada),
                step=1
            )
            
            ingreso_retiro_mensual = st.session_state.asesoria_data['objetivos'].get('ingreso_retiro_mensual', 0)
            if isinstance(ingreso_retiro_mensual, str):
                try:
                    ingreso_retiro_mensual = float(ingreso_retiro_mensual)
                except:
                    ingreso_retiro_mensual = 0.0
            st.session_state.asesoria_data['objetivos']['ingreso_retiro_mensual'] = st.number_input(
                "¿Qué ingreso mensual deseas en tu retiro? ($)", 
                min_value=0.0,
                value=float(ingreso_retiro_mensual),
                step=100.0
            )
            
            # Educación de hijos
            if st.session_state.asesoria_data['informacion_familiar'].get('num_hijos', 0) > 0:
                costo_universidad_por_hijo = st.session_state.asesoria_data['objetivos'].get('costo_universidad_por_hijo', 0)
                if isinstance(costo_universidad_por_hijo, str):
                    try:
                        costo_universidad_por_hijo = float(costo_universidad_por_hijo)
                    except:
                        costo_universidad_por_hijo = 0.0
                st.session_state.asesoria_data['objetivos']['costo_universidad_por_hijo'] = st.number_input(
                    "Costo estimado de universidad por hijo ($)", 
                    min_value=0.0,
                    value=float(costo_universidad_por_hijo),
                    step=1000.0
                )
        
        with col2:
            meses_proteccion_familiar = st.session_state.asesoria_data['objetivos'].get('meses_proteccion_familiar', 6)
            if isinstance(meses_proteccion_familiar, str):
                try:
                    meses_proteccion_familiar = int(meses_proteccion_familiar)
                except:
                    meses_proteccion_familiar = 6
            st.session_state.asesoria_data['objetivos']['meses_proteccion_familiar'] = st.number_input(
                "¿Cuántos meses de gastos quieres cubrir para tu familia?", 
                min_value=0,
                max_value=24,
                value=int(meses_proteccion_familiar),
                step=1
            )
            
            proyecto_futuro = st.session_state.asesoria_data['objetivos'].get('proyecto_futuro', '')
            st.session_state.asesoria_data['objetivos']['proyecto_futuro'] = st.text_input(
                "¿Tienes algún proyecto a mediano/largo plazo? (ej: casa, negocio)", 
                value=proyecto_futuro,
                placeholder="Describa su proyecto"
            )
            
            if st.session_state.asesoria_data['objetivos'].get('proyecto_futuro'):
                costo_proyecto = st.session_state.asesoria_data['objetivos'].get('costo_proyecto', 0)
                if isinstance(costo_proyecto, str):
                    try:
                        costo_proyecto = float(costo_proyecto)
                    except:
                        costo_proyecto = 0.0
                st.session_state.asesoria_data['objetivos']['costo_proyecto'] = st.number_input(
                    f"Costo estimado de {st.session_state.asesoria_data['objetivos'].get('proyecto_futuro')} ($)", 
                    min_value=0.0,
                    value=float(costo_proyecto),
                    step=1000.0
                )
    
    with tab5:
        st.subheader("📊 Reporte Financiero")
        # Botones de acción en la parte superior
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        
        with col_btn1:
            # Botón para borrar todos los datos del formulario
            if st.button("🗑️ Borrar Todos los Datos", type="secondary", use_container_width=True):
                st.session_state.asesoria_data = {
                    'informacion_personal': {},
                    'informacion_familiar': {},
                    'informacion_financiera': {},
                    'objetivos': {}
                }
                st.session_state.metricas_financieras = None
                st.success("✅ Todos los datos del formulario han sido borrados")
                st.rerun()
        
        with col_btn2:
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
                            plt.close(fig1)
                        
                        # Gráfico 2: Metas financieras
                        fig2 = crear_grafico_barras_metas(metricas)
                        if fig2:
                            st.pyplot(fig2)
                            plt.close(fig2)
                        
                        # Gráfico 3: Comparación de ahorro
                        fig3 = crear_grafico_ahorro(metricas)
                        if fig3:
                            st.pyplot(fig3)
                            plt.close(fig3)
                        
                        # Generar archivo Excel para descarga
                        excel_buffer = generar_excel_reporte(metricas)
                        
                        # Botón para descargar Excel
                        if excel_buffer:
                            nombre_cliente = st.session_state.asesoria_data['informacion_personal'].get('nombre', 'Cliente')
                            # Limpiar nombre para el archivo
                            nombre_archivo = f"Reporte_Financiero_{nombre_cliente.replace(' ', '_')}.xlsx"
                            
                            st.download_button(
                                label="📥 Descargar Reporte en Excel",
                                data=excel_buffer,
                                file_name=nombre_archivo,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                use_container_width=True
                            )
                    else:
                        st.error("❌ Error al calcular las métricas financieras")
        
        with col_btn3:
            # Botón para generar PDF (solo si hay métricas)
            if st.session_state.metricas_financieras:
                if st.button("📄 Generar PDF", type="primary", use_container_width=True):
                    with st.spinner("Generando PDF..."):
                        pdf_buffer = generar_pdf_reporte(st.session_state.metricas_financieras)
                        if pdf_buffer:
                            nombre_cliente = st.session_state.asesoria_data['informacion_personal'].get('nombre', 'Cliente')
                            nombre_archivo = f"Reporte_Financiero_{nombre_cliente.replace(' ', '_')}.pdf"
                            
                            st.download_button(
                                label="📥 Descargar PDF",
                                data=pdf_buffer,
                                file_name=nombre_archivo,
                                mime="application/pdf",
                                use_container_width=True
                            )
                        else:
                            st.error("❌ Error al generar el PDF")
            else:
                st.info("Genere el reporte primero")
        
        # Mostrar datos actuales si ya existen
        if st.session_state.metricas_financieras:
            st.success("✅ Reporte disponible. Puede generar el PDF o Excel.")
        

def calcular_metricas_financieras():
    """Calcula métricas financieras basadas en los datos ingresados"""
    try:
        datos = st.session_state.asesoria_data
        
        # Extraer datos básicos con valores por defecto seguros
        ingreso_mensual = datos['informacion_financiera'].get('ingreso_mensual', 0)
        gastos_mensuales = datos['informacion_financiera'].get('gastos_mensuales', 0)
        ahorro_actual = datos['informacion_financiera'].get('ahorro_actual', 0)
        edad = datos['informacion_familiar'].get('edad', 30)
        
        # Convertir a float si es necesario
        if isinstance(ingreso_mensual, str):
            try:
                ingreso_mensual = float(ingreso_mensual)
            except:
                ingreso_mensual = 0.0
        
        if isinstance(gastos_mensuales, str):
            try:
                gastos_mensuales = float(gastos_mensuales)
            except:
                gastos_mensuales = 0.0
        
        if isinstance(ahorro_actual, str):
            try:
                ahorro_actual = float(ahorro_actual)
            except:
                ahorro_actual = 0.0
        
        if isinstance(edad, str):
            try:
                edad = int(edad)
            except:
                edad = 30
        
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
        if isinstance(meses_proteccion, str):
            try:
                meses_proteccion = int(meses_proteccion)
            except:
                meses_proteccion = 6
        necesidad_proteccion = gastos_mensuales * meses_proteccion
        
        # Necesidad de retiro
        edad_retiro_deseada = datos['objetivos'].get('edad_retiro_deseada', 65)
        if isinstance(edad_retiro_deseada, str):
            try:
                edad_retiro_deseada = int(edad_retiro_deseada)
            except:
                edad_retiro_deseada = 65
        
        años_hasta_retiro = max(0, edad_retiro_deseada - edad) if edad_retiro_deseada > edad else 0
        
        ingreso_retiro_mensual = datos['objetivos'].get('ingreso_retiro_mensual', 0)
        if isinstance(ingreso_retiro_mensual, str):
            try:
                ingreso_retiro_mensual = float(ingreso_retiro_mensual)
            except:
                ingreso_retiro_mensual = 0.0
        
        años_retiro = max(0, 80 - edad_retiro_deseada)  # Esperanza de vida 80 años
        necesidad_retiro_total = ingreso_retiro_mensual * 12 * años_retiro
        
        # Necesidad educación
        necesidad_educacion = 0
        num_hijos = datos['informacion_familiar'].get('num_hijos', 0)
        hijos = datos['informacion_familiar'].get('hijos', [])
        costo_universidad = datos['objetivos'].get('costo_universidad_por_hijo', 0)
        
        if isinstance(costo_universidad, str):
            try:
                costo_universidad = float(costo_universidad)
            except:
                costo_universidad = 0.0
        
        for i in range(min(num_hijos, len(hijos))):
            if hijos[i].get('edad'):
                try:
                    edad_hijo = int(hijos[i]['edad'])
                    if edad_hijo < 18:
                        necesidad_educacion += costo_universidad
                except:
                    necesidad_educacion += costo_universidad
        
        # Necesidad proyecto
        necesidad_proyecto = datos['objetivos'].get('costo_proyecto', 0)
        if isinstance(necesidad_proyecto, str):
            try:
                necesidad_proyecto = float(necesidad_proyecto)
            except:
                necesidad_proyecto = 0.0
        
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
        
        # Asegurarse de incluir TODAS las métricas necesarias
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
            'necesidad_proyecto': necesidad_proyecto,  # ¡IMPORTANTE! Esta es la clave faltante
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
        import traceback
        st.error(f"Detalle del error: {traceback.format_exc()}")
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
            datos.get('deudas_totales', 0)
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
                    f"${metricas['datos_basicos'].get('deudas_totales', 0):,.2f}",
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
        import traceback
        st.error(f"Detalle del error: {traceback.format_exc()}")
        return None

def generar_pdf_reporte(metricas):
    """Genera un archivo PDF con el reporte financiero"""
    try:
        # Verificar que todas las claves necesarias existan
        keys_required = [
            'necesidad_proyecto', 'necesidad_proteccion', 
            'necesidad_retiro_total', 'necesidad_educacion'
        ]
        
        for key in keys_required:
            if key not in metricas:
                metricas[key] = 0.0  # Valor por defecto
        
        # Verificar que 'metas' exista
        if 'metas' not in metricas:
            metricas['metas'] = {
                'Protección': metricas.get('necesidad_proteccion', 0),
                'Retiro': metricas.get('necesidad_retiro_total', 0),
                'Educación': metricas.get('necesidad_educacion', 0),
                'Proyecto': metricas.get('necesidad_proyecto', 0)
            }
        
        # Crear un buffer en memoria para el PDF
        buffer = io.BytesIO()
        
        # Crear el documento PDF
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        
        # Crear estilos personalizados
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor(COLORES_AXA['azul_principal']),
            spaceAfter=30
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor(COLORES_AXA['verde_oscuro']),
            spaceAfter=15
        )
        
        normal_style = styles['Normal']
        
        # Contenido del PDF
        story = []
        
        # Título principal
        nombre_cliente = st.session_state.asesoria_data['informacion_personal'].get('nombre', 'Cliente')
        story.append(Paragraph(f"REPORTE FINANCIERO - {nombre_cliente.upper()}", title_style))
        story.append(Paragraph(f"Fecha de generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}", normal_style))
        story.append(Spacer(1, 20))
        
        # Información Personal
        story.append(Paragraph("INFORMACIÓN PERSONAL", subtitle_style))
        
        datos_personales = st.session_state.asesoria_data['informacion_personal']
        datos_familiares = st.session_state.asesoria_data['informacion_familiar']
        
        personal_data = [
            ["Nombre:", datos_personales.get('nombre', 'No especificado')],
            ["Teléfono:", datos_personales.get('telefono', 'No especificado')],
            ["Email:", datos_personales.get('email', 'No especificado')],
            ["Ocupación:", datos_personales.get('ocupacion', 'No especificado')],
            ["Agente:", datos_personales.get('agente', 'No especificado')],
            ["Estado Civil:", datos_familiares.get('estado_civil', 'No especificado')],
            ["Fecha Nacimiento:", datos_familiares.get('fecha_nacimiento', 'No especificado')],
            ["Edad:", str(datos_familiares.get('edad', 'No especificado'))],
            ["Hijos:", str(datos_familiares.get('num_hijos', 0))]
        ]
        
        personal_table = Table(personal_data, colWidths=[2*inch, 4*inch])
        personal_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor(COLORES_AXA['azul_claro'])),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        
        story.append(personal_table)
        story.append(Spacer(1, 20))
        
        # Información Financiera
        story.append(Paragraph("INFORMACIÓN FINANCIERA", subtitle_style))
        
        datos_financieros = st.session_state.asesoria_data['informacion_financiera']
        financial_data = [
            ["Ingreso Mensual Neto:", f"${datos_financieros.get('ingreso_mensual', 0):,.2f}"],
            ["Gastos Mensuales Totales:", f"${datos_financieros.get('gastos_mensuales', 0):,.2f}"],
            ["Ahorro Actual:", f"${datos_financieros.get('ahorro_actual', 0):,.2f}"],
            ["Deudas Totales:", f"${datos_financieros.get('deudas_totales', 0):,.2f}"],
            ["Capacidad de Ahorro Mensual:", f"${metricas.get('ahorro_mensual', 0):,.2f}"],
            ["Porcentaje de Ahorro:", f"{metricas.get('porcentaje_ahorro', 0):.1f}%"],
            ["Fondo Emergencia Recomendado:", f"${metricas.get('fondo_emergencia_recomendado', 0):,.2f}"]
        ]
        
        financial_table = Table(financial_data, colWidths=[2.5*inch, 3.5*inch])
        financial_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor(COLORES_AXA['verde_agua'])),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))
        
        story.append(financial_table)
        story.append(Spacer(1, 20))
        
        # Metas Financieras - Usar metricas['metas'] en lugar de claves individuales
        story.append(Paragraph("METAS FINANCIERAS", subtitle_style))
        
        objetivos = st.session_state.asesoria_data['objetivos']
        metas_data = [
            ["Categoría", "Monto Requerido", "Descripción"],
            ["Protección Familiar", f"${metricas['metas']['Protección']:,.2f}", 
             f"{objetivos.get('meses_proteccion_familiar', 6)} meses de gastos"],
            ["Retiro", f"${metricas['metas']['Retiro']:,.2f}", 
             f"Ingreso mensual deseado: ${objetivos.get('ingreso_retiro_mensual', 0):,.2f}"],
            ["Educación", f"${metricas['metas']['Educación']:,.2f}", 
             f"Para {datos_familiares.get('num_hijos', 0)} hijo(s)"],
            ["Proyecto Futuro", f"${metricas['metas']['Proyecto']:,.2f}", 
             objetivos.get('proyecto_futuro', 'No especificado')]
        ]
        
        metas_table = Table(metas_data, colWidths=[1.5*inch, 2*inch, 3*inch])
        metas_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLORES_AXA['azul_principal'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor(COLORES_AXA['azul_claro'])),
            ('BACKGROUND', (1, 1), (1, -1), colors.HexColor(COLORES_AXA['verde_agua'])),
            ('BACKGROUND', (2, 1), (2, -1), colors.HexColor('#f0f0f0'))
        ]))
        
        story.append(metas_table)
        story.append(Spacer(1, 20))
        
        # Plan de Ahorro - Usar claves individuales con valores por defecto
        story.append(Paragraph("PLAN DE AHORRO RECOMENDADO", subtitle_style))
        
        años_hasta_retiro = metricas.get('años_hasta_retiro', 0)
        plan_data = [
            ["Recomendación", "Monto Mensual", "Plazo", "Prioridad"],
            ["Fondo de Emergencia", f"${metricas.get('fondo_emergencia_recomendado', 0)/12:,.2f}", "12 meses", "Alta"],
            ["Protección Familiar", f"${metricas.get('necesidad_proteccion', 0)/24:,.2f}" if metricas.get('necesidad_proteccion', 0) > 0 else "$0.00", "24 meses", "Alta"],
            ["Retiro", f"${metricas.get('necesidad_retiro_total', 0)/(años_hasta_retiro*12):,.2f}" if años_hasta_retiro > 0 else "$0.00", f"{años_hasta_retiro*12} meses", "Media"],
            ["Educación", f"${metricas.get('necesidad_educacion', 0)/120:,.2f}" if metricas.get('necesidad_educacion', 0) > 0 else "$0.00", "120 meses", "Media"],
            ["Proyecto", f"${metricas.get('necesidad_proyecto', 0)/60:,.2f}" if metricas.get('necesidad_proyecto', 0) > 0 else "$0.00", "60 meses", "Baja"]
        ]
        
        plan_table = Table(plan_data, colWidths=[1.5*inch, 1.5*inch, 1.2*inch, 1.2*inch])
        plan_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(COLORES_AXA['verde_oscuro'])),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('BACKGROUND', (3, 1), (3, 1), colors.HexColor('#ffcccc')),  # Alta - rojo claro
            ('BACKGROUND', (3, 2), (3, 2), colors.HexColor('#ffcccc')),  # Alta - rojo claro
            ('BACKGROUND', (3, 3), (3, 3), colors.HexColor('#ffffcc')),  # Media - amarillo claro
            ('BACKGROUND', (3, 4), (3, 4), colors.HexColor('#ffffcc')),  # Media - amarillo claro
            ('BACKGROUND', (3, 5), (3, 5), colors.HexColor('#ccffcc'))   # Baja - verde claro
        ]))
        
        story.append(plan_table)
        story.append(Spacer(1, 30))
        
        # Recomendaciones finales
        story.append(Paragraph("RECOMENDACIONES GENERALES", subtitle_style))
        
        recomendaciones = [
            "1. Establecer un fondo de emergencia equivalente a 6 meses de gastos",
            "2. Considerar un seguro de vida para proteger a la familia",
            "3. Iniciar un plan de ahorro para el retiro lo antes posible",
            "4. Diversificar las inversiones para reducir riesgos",
            "5. Revisar periódicamente el plan financiero (al menos cada 6 meses)",
            "6. Considerar instrumentos de inversión acordes al perfil de riesgo"
        ]
        
        for rec in recomendaciones:
            story.append(Paragraph(rec, normal_style))
            story.append(Spacer(1, 5))
        
        story.append(Spacer(1, 20))
        
        # Pie de página
        footer = Paragraph(
            f"Reporte generado por Sistema de Asesoría Financiera Rizkora • {datetime.now().strftime('%d/%m/%Y')} • Página 1 de 1",
            ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.grey,
                alignment=1
            )
        )
        story.append(footer)
        
        # Construir el PDF
        doc.build(story)
        
        # Obtener los datos del buffer
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        st.error(f"Error al generar PDF: {str(e)}")
        import traceback
        st.error(f"Detalle del error: {traceback.format_exc()}")
        return None

# ---- FUNCIONES PARA PESTAÑA OPERACIÓN ----
def mostrar_operacion(df_operacion):
    st.header("💰 Operación - Gastos Operacionales RIZKORA")

    # Inicializar estado para la edición
    if 'modo_edicion_operacion' not in st.session_state:
        st.session_state.modo_edicion_operacion = False
    if 'operacion_editando' not in st.session_state:
        st.session_state.operacion_editando = None
    if 'operacion_data' not in st.session_state:
        st.session_state.operacion_data = {}

    # Mostrar estadísticas generales
    if not df_operacion.empty:
        col_stats1, col_stats2, col_stats3 = st.columns(3)
        
        with col_stats1:
            try:
                total_gastos = df_operacion['Monto'].sum()
                st.metric("Total Gastos", f"${total_gastos:,.2f}")
            except:
                st.metric("Total Gastos", "N/A")
        
        with col_stats2:
            try:
                # Calcular gastos del mes actual
                df_operacion['Fecha DT'] = pd.to_datetime(df_operacion['Fecha'], dayfirst=True, errors='coerce')
                mes_actual = datetime.now().month
                gastos_mes = df_operacion[df_operacion['Fecha DT'].dt.month == mes_actual]['Monto'].sum()
                st.metric("Gastos del Mes", f"${gastos_mes:,.2f}")
            except:
                st.metric("Gastos del Mes", "N/A")
        
        with col_stats3:
            try:
                # Calcular gastos deducibles
                gastos_deducibles = df_operacion[df_operacion['Deducible'] == 'Sí']['Monto'].sum()
                st.metric("Gastos Deducibles", f"${gastos_deducibles:,.2f}")
            except:
                st.metric("Gastos Deducibles", "N/A")

    # Selector para editar gasto existente
    if not df_operacion.empty:
        # Crear lista de gastos para seleccionar
        gastos_lista = []
        for idx, row in df_operacion.iterrows():
            fecha = row.get('Fecha', '')
            concepto = row.get('Concepto', '')
            proveedor = row.get('Proveedor', '')
            monto = row.get('Monto', 0)
            gastos_lista.append(f"{fecha} - {concepto} - {proveedor} - ${monto}")
        
        gasto_seleccionado = st.selectbox(
            "Seleccionar Gasto para editar",
            [""] + gastos_lista,
            key="select_editar_operacion"
        )

        # Botones para cargar datos o limpiar selección
        if gasto_seleccionado:
            col_btn1, col_btn2 = st.columns([1, 1])
            with col_btn1:
                if st.button("📝 Cargar Datos para Editar", use_container_width=True, key="btn_cargar_datos_operacion"):
                    # Encontrar el índice del gasto seleccionado
                    idx_seleccionado = gastos_lista.index(gasto_seleccionado)
                    # Obtener los datos del gasto seleccionado
                    if idx_seleccionado < len(df_operacion):
                        fila = df_operacion.iloc[idx_seleccionado]
                        st.session_state.operacion_data = fila.to_dict()
                        st.session_state.operacion_editando = idx_seleccionado
                        st.session_state.modo_edicion_operacion = True
                        st.rerun()

            with col_btn2:
                if st.button("❌ Limpiar selección", use_container_width=True, key="btn_limpiar_seleccion_operacion"):
                    st.session_state.operacion_editando = None
                    st.session_state.modo_edicion_operacion = False
                    st.session_state.operacion_data = {}
                    st.rerun()

            # Mostrar información del gasto seleccionado
            if st.session_state.operacion_editando == idx_seleccionado:
                st.info(f"**Editando:** {gasto_seleccionado}")

    # Botón para cancelar edición
    if st.session_state.modo_edicion_operacion:
        if st.button("❌ Cancelar Edición", key="btn_cancelar_edicion_operacion"):
            st.session_state.operacion_editando = None
            st.session_state.modo_edicion_operacion = False
            st.session_state.operacion_data = {}
            st.rerun()

    # --- FORMULARIO DE GASTOS OPERACIONALES ---
    with st.form("form_operacion", clear_on_submit=True):
        st.subheader("📝 Formulario de Gasto Operacional")
        
        # Mostrar información de edición
        if st.session_state.modo_edicion_operacion and st.session_state.operacion_editando is not None:
            st.info(f"Editando gasto #{st.session_state.operacion_editando + 1}")

        col1, col2 = st.columns(2)

        with col1:
            # Fecha
            fecha_val = st.session_state.operacion_data.get("Fecha", "")
            fecha = st.text_input(
                "Fecha (dd/mm/yyyy)*", 
                value=fecha_val,
                placeholder="dd/mm/yyyy"
            )

            # Concepto
            concepto_val = st.session_state.operacion_data.get("Concepto", "")
            concepto_index = obtener_indice_selectbox(concepto_val, OPCIONES_CONCEPTO_OPERACION)
            concepto = st.selectbox(
                "Concepto*", 
                [""] + OPCIONES_CONCEPTO_OPERACION, 
                index=concepto_index
            )

            # Proveedor
            proveedor = st.text_input(
                "Proveedor*", 
                value=st.session_state.operacion_data.get("Proveedor", ""),
                placeholder="Nombre del proveedor"
            )

            # Monto
            monto_val = st.session_state.operacion_data.get("Monto", 0)
            monto = st.number_input(
                "Monto ($)*", 
                min_value=0.0,
                value=float(monto_val) if monto_val else 0.0,
                step=0.01,
                format="%.2f"
            )

        with col2:
            # Forma de Pago
            forma_pago_val = st.session_state.operacion_data.get("Forma de Pago", "")
            forma_pago_index = obtener_indice_selectbox(forma_pago_val, OPCIONES_FORMA_PAGO_OPERACION)
            forma_pago = st.selectbox(
                "Forma de Pago*", 
                [""] + OPCIONES_FORMA_PAGO_OPERACION, 
                index=forma_pago_index
            )

            # Banco
            banco_val = st.session_state.operacion_data.get("Banco", "NINGUNO")
            banco_index = obtener_indice_selectbox(banco_val, OPCIONES_BANCO)
            banco = st.selectbox(
                "Banco", 
                [""] + OPCIONES_BANCO, 
                index=banco_index
            )

            # Responsable del pago
            responsable = st.text_input(
                "Responsable del pago*", 
                value=st.session_state.operacion_data.get("Responsable del pago", ""),
                placeholder="Persona que realizó el pago"
            )

            # Finalidad
            finalidad = st.text_area(
                "Finalidad*", 
                value=st.session_state.operacion_data.get("Finalidad", ""),
                placeholder="Descripción detallada del gasto"
            )

            # Deducible
            deducible_val = st.session_state.operacion_data.get("Deducible", "No")
            deducible_index = obtener_indice_selectbox(deducible_val, OPCIONES_DEDUCIBLE)
            deducible = st.selectbox(
                "Deducible", 
                [""]+OPCIONES_DEDUCIBLE, 
                index=deducible_index
            )

        # Validar fecha
        fecha_error = None
        if fecha:
            valido, error = validar_fecha(fecha)
            if not valido:
                fecha_error = error

        # Mostrar error de fecha si existe
        if fecha_error:
            st.error(f"Fecha: {fecha_error}")

        # --- BOTONES DEL FORMULARIO ---
        col_b1, col_b2 = st.columns(2)
        
        with col_b1:
            # Botón de envío principal
            if st.session_state.modo_edicion_operacion:
                submit_button = st.form_submit_button("💾 Actualizar Gasto", use_container_width=True)
            else:
                submit_button = st.form_submit_button("💾 Agregar Nuevo Gasto", use_container_width=True)
        
        with col_b2:
            # Botón de cancelar secundario
            cancel_button = st.form_submit_button("🚫 Cancelar", use_container_width=True, type="secondary")

        # --- PROCESAR BOTÓN CANCELAR ---
        if cancel_button:
            st.session_state.operacion_editando = None
            st.session_state.modo_edicion_operacion = False
            st.session_state.operacion_data = {}
            st.rerun()

        # --- PROCESAR BOTÓN DE ENVÍO ---
        if submit_button:
            # Validaciones
            errores = []
            
            if not fecha:
                errores.append("La fecha es obligatoria")
            elif fecha_error:
                errores.append(f"Fecha: {fecha_error}")
            
            if not proveedor.strip():
                errores.append("El proveedor es obligatorio")
            
            if monto <= 0:
                errores.append("El monto debe ser mayor a 0")
            
            if not responsable.strip():
                errores.append("El responsable del pago es obligatorio")
            
            if not finalidad.strip():
                errores.append("La finalidad es obligatoria")
            
            if errores:
                for error in errores:
                    st.warning(error)
            else:
                # Crear objeto con los datos del gasto
                nuevo_gasto = {
                    "Fecha": fecha,
                    "Concepto": concepto,
                    "Proveedor": proveedor.strip(),
                    "Monto": float(monto),
                    "Forma de Pago": forma_pago,
                    "Banco": banco,
                    "Responsable del pago": responsable.strip(),
                    "Finalidad": finalidad.strip(),
                    "Deducible": deducible
                }

                if st.session_state.modo_edicion_operacion and st.session_state.operacion_editando is not None:
                    # ACTUALIZAR gasto existente
                    idx = st.session_state.operacion_editando
                    if idx < len(df_operacion):
                        for key, value in nuevo_gasto.items():
                            df_operacion.loc[idx, key] = value
                        mensaje = "✅ Gasto actualizado correctamente"
                    else:
                        st.error("❌ No se encontró el gasto a actualizar")
                        return
                else:
                    # AGREGAR nuevo gasto
                    df_operacion = pd.concat([df_operacion, pd.DataFrame([nuevo_gasto])], ignore_index=True)
                    mensaje = "✅ Gasto agregado correctamente"

                # Guardar cambios
                if guardar_datos(df_operacion=df_operacion):
                    st.success(mensaje)
                    
                    # Limpiar estado después de guardar
                    st.session_state.operacion_editando = None
                    st.session_state.modo_edicion_operacion = False
                    st.session_state.operacion_data = {}
                    
                    st.rerun()
                else:
                    st.error("❌ Error al guardar el gasto")

    # --- MOSTRAR LISTA DE GASTOS OPERACIONALES ---
    st.subheader("📋 Historial de Gastos Operacionales")
    
    if not df_operacion.empty:
        # Crear una copia para no modificar el original
        df_mostrar = df_operacion.copy()
        
        # Ordenar por fecha más reciente primero
        try:
            df_mostrar['Fecha DT'] = pd.to_datetime(df_mostrar['Fecha'], dayfirst=True, errors='coerce')
            df_mostrar = df_mostrar.sort_values('Fecha DT', ascending=False)
        except:
            pass
        
        # Formatear montos para mejor visualización
        def formatear_monto(monto):
            try:
                return f"${float(monto):,.2f}"
            except:
                return str(monto)
        
        df_mostrar['Monto Formateado'] = df_mostrar['Monto'].apply(formatear_monto)
        
        # Columnas a mostrar
        columnas_mostrar = ['Fecha', 'Concepto', 'Proveedor', 'Monto Formateado', 'Forma de Pago', 'Deducible', 'Responsable del pago']
        columnas_disponibles = [col for col in columnas_mostrar if col in df_mostrar.columns]
        
        # Aplicar estilo para resaltar gastos deducibles
        def style_deducible(val):
            if val == 'Sí':
                return 'background-color: #d4edda; color: #155724; font-weight: bold;'  # Verde
            else:
                return 'background-color: #f8d7da; color: #721c24;'  # Rojo
        
        try:
            styled_df = df_mostrar[columnas_disponibles].style.applymap(
                style_deducible, 
                subset=['Deducible']
            )
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        except:
            st.dataframe(df_mostrar[columnas_disponibles], use_container_width=True, hide_index=True)

        # --- ESTADÍSTICAS DETALLADAS ---
        st.subheader("📊 Estadísticas Detalladas")
        
        try:
            # Estadísticas por concepto
            col_stats1, col_stats2 = st.columns(2)
            
            with col_stats1:
                st.write("**Gastos por Concepto:**")
                gastos_por_concepto = df_operacion.groupby('Concepto')['Monto'].sum().sort_values(ascending=False)
                for concepto, total in gastos_por_concepto.items():
                    st.write(f"- {concepto}: ${total:,.2f}")
            
            with col_stats2:
                st.write("**Gastos por Forma de Pago:**")
                gastos_por_pago = df_operacion.groupby('Forma de Pago')['Monto'].sum().sort_values(ascending=False)
                for forma_pago, total in gastos_por_pago.items():
                    st.write(f"- {forma_pago}: ${total:,.2f}")
            
            # Estadísticas por mes
            st.write("**Gastos por Mes (Últimos 6 meses):**")
            try:
                df_operacion['Mes'] = df_operacion['Fecha DT'].dt.strftime('%Y-%m')
                ultimos_6_meses = df_operacion.groupby('Mes')['Monto'].sum().sort_index(ascending=False).head(6)
                for mes, total in ultimos_6_meses.items():
                    st.write(f"- {mes}: ${total:,.2f}")
            except:
                st.write("No se pudieron calcular los gastos por mes")
                
        except Exception as e:
            st.write(f"No se pudieron generar estadísticas detalladas: {e}")

    else:
        st.info("No hay gastos operacionales registrados")

# ---- Funciones para cada pestaña (completas) ----

# 1. Prospectos - SOLUCIÓN DEFINITIVA
def mostrar_prospectos(df_prospectos, df_polizas):
    st.header("👥 Gestión de Prospectos")

    # --- Inicializar estado para la edición ---
    if 'modo_edicion_prospectos' not in st.session_state:
        st.session_state.modo_edicion_prospectos = False
    if 'prospecto_editando' not in st.session_state:
        st.session_state.prospecto_editando = None
    if 'prospecto_data' not in st.session_state:
        st.session_state.prospecto_data = {}
    # Estado clave para forzar actualización
    if 'form_key' not in st.session_state:
        st.session_state.form_key = 0

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
                        fila = fila.iloc[0].fillna("")
                        st.session_state.prospecto_data = {k: str(v) if v is not None else "" for k, v in fila.to_dict().items()}
                        st.session_state.prospecto_editando = prospecto_seleccionado
                        st.session_state.modo_edicion_prospectos = True
                        # Incrementar la clave del formulario para forzar reinicio
                        st.session_state.form_key += 1
                        st.rerun()

            with col_btn2:
                if st.button("❌ Limpiar selección", use_container_width=True, key="btn_limpiar_seleccion"):
                    # Limpiar estado
                    st.session_state.prospecto_editando = None
                    st.session_state.modo_edicion_prospectos = False
                    st.session_state.prospecto_data = {}
                    # Incrementar la clave del formulario para forzar reinicio
                    st.session_state.form_key += 1
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
            # Incrementar la clave del formulario para forzar reinicio
            st.session_state.form_key += 1
            st.rerun()

    # --- FORMULARIO PRINCIPAL - USAR KEY DINÁMICA ---
    # Usamos una clave dinámica para forzar la recreación del formulario
    form_key = f"form_prospectos_{st.session_state.form_key}"
    
    with st.form(form_key, clear_on_submit=True):
        st.subheader("📝 Formulario de Prospecto")
        
        # Mostrar información de edición
        if st.session_state.modo_edicion_prospectos and st.session_state.prospecto_editando:
            st.info(f"Editando: **{st.session_state.prospecto_editando}**")

        col1, col2 = st.columns(2)

        with col1:
            # Tipo Persona - usar valor actual o vacío
            tipo_persona_val = st.session_state.prospecto_data.get("Tipo Persona", "")
            tipo_persona_index = obtener_indice_selectbox(tipo_persona_val, OPCIONES_PERSONA)
            tipo_persona = st.selectbox(
                "Tipo Persona", 
                 [""]+OPCIONES_PERSONA, 
                index=tipo_persona_index,
                key=f"tipo_persona_{st.session_state.form_key}"
            )

            # Nombre/Razón Social
            nombre_razon = st.text_input(
                "Nombre/Razón Social*", 
                value=st.session_state.prospecto_data.get("Nombre/Razón Social", ""),
                key=f"nombre_razon_{st.session_state.form_key}",
                placeholder="Ingrese nombre o razón social"
            )

            # Fecha Nacimiento
            fecha_nacimiento = st.text_input(
                "Fecha Nacimiento (dd/mm/yyyy)", 
                value=st.session_state.prospecto_data.get("Fecha Nacimiento", ""),
                placeholder="dd/mm/yyyy",
                key=f"fecha_nacimiento_{st.session_state.form_key}"
            )

            # RFC
            rfc = st.text_input(
                "RFC", 
                value=st.session_state.prospecto_data.get("RFC", ""),
                key=f"rfc_{st.session_state.form_key}",
                placeholder="Ingrese RFC"
            )

            # Teléfono
            telefono = st.text_input(
                "Teléfono", 
                value=st.session_state.prospecto_data.get("Teléfono", ""),
                key=f"telefono_{st.session_state.form_key}",
                placeholder="Ingrese teléfono"
            )

            # Correo
            correo = st.text_input(
                "Correo", 
                value=st.session_state.prospecto_data.get("Correo", ""),
                key=f"correo_{st.session_state.form_key}",
                placeholder="Ingrese correo electrónico"
            )

            # Notas - AQUÍ ESTÁ LA CLAVE: usar directamente de prospecto_data
            notas_valor = st.session_state.prospecto_data.get("Notas", "")
            notas = st.text_area(
                "Notas", 
                value=notas_valor,
                placeholder="Notas del prospecto...",
                height=100,
                key=f"notas_{st.session_state.form_key}"
            )

        with col2:
            # Producto
            producto_val = st.session_state.prospecto_data.get("Producto", "")
            producto_index = obtener_indice_selectbox(producto_val, OPCIONES_PRODUCTO)
            producto = st.selectbox(
                "Producto", 
                 [""]+OPCIONES_PRODUCTO, 
                index=producto_index,
                key=f"producto_{st.session_state.form_key}"
            )

            # Fecha Registro
            fecha_registro = st.text_input(
                "Fecha Registro*", 
                value=st.session_state.prospecto_data.get("Fecha Registro", ""),
                placeholder="dd/mm/yyyy",
                key=f"fecha_registro_{st.session_state.form_key}"
            )

            # Fecha Contacto
            fecha_contacto = st.text_input(
                "Fecha Contacto (dd/mm/yyyy)", 
                value=st.session_state.prospecto_data.get("Fecha Contacto", ""),
                placeholder="dd/mm/yyyy",
                key=f"fecha_contacto_{st.session_state.form_key}"
            )

            # Seguimiento
            seguimiento = st.text_input(
                "Seguimiento (dd/mm/yyyy)", 
                value=st.session_state.prospecto_data.get("Seguimiento", ""),
                placeholder="dd/mm/yyyy",
                key=f"seguimiento_{st.session_state.form_key}"
            )

            # Representantes Legales
            representantes = st.text_area(
                "Representantes Legales (separar por comas)", 
                value=st.session_state.prospecto_data.get("Representantes Legales", ""),
                placeholder="Ej: Juan Pérez, María García",
                key=f"representantes_{st.session_state.form_key}"
            )

            # Referenciador
            referenciador = st.text_input(
                "Referenciador", 
                value=st.session_state.prospecto_data.get("Referenciador", ""),
                placeholder="Origen del cliente/promoción",
                key=f"referenciador_{st.session_state.form_key}"
            )

            # Estatus
            estatus_val = st.session_state.prospecto_data.get("Estatus", "")
            estatus = st.text_input(
                "Estatus", 
                value=estatus_val,
                placeholder="Estado actual del prospecto",
                key=f"estatus_{st.session_state.form_key}"
            )

            # Dirección
            direccion = st.text_input(
                "Dirección", 
                value=st.session_state.prospecto_data.get("Dirección", ""),
                placeholder="Ej: Calle 123, CDMX, 03100",
                key=f"direccion_{st.session_state.form_key}"
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
            # Botón de envío principal
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
            # Incrementar la clave del formulario para forzar reinicio
            st.session_state.form_key += 1
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
                    "Notas": notas,
                    "Referenciador": referenciador,
                    "Estatus": estatus
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
                    # Incrementar la clave del formulario para forzar reinicio
                    st.session_state.form_key += 1
                    
                    st.rerun()
                else:
                    st.error("❌ Error al guardar el prospecto")

    # --- MOSTRAR LISTA DE PROSPECTOS ---
    st.subheader("📋 Lista de Prospectos")
    if not df_prospectos.empty:
        # Mostrar columnas más relevantes
        columnas_mostrar = [
            "Nombre/Razón Social", "Producto", "Teléfono", "Correo",
            "Fecha Registro", "Referenciador", "Notas", "Estatus"
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
                                                       value="",
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
                    no_poliza = st.text_input("No. Póliza*", key="registro_numero", placeholder="Ingrese número de póliza")
                    producto_poliza = st.selectbox("Producto", [""] + OPCIONES_PRODUCTO, 
                                          index=obtener_indice_selectbox(prospecto_data.get("Producto", ""), OPCIONES_PRODUCTO),
                                          key="registro_producto")
                    inicio_vigencia = st.text_input("Inicio Vigencia (dd/mm/yyyy)*", 
                                                  placeholder="dd/mm/yyyy",
                                                  key="registro_inicio")
                    fin_vigencia = st.text_input("Fin Vigencia (dd/mm/yyyy)*", 
                                               placeholder="dd/mm/yyyy",
                                               key="registro_fin")
                    rfc_poliza = st.text_input("RFC", value=prospecto_data.get("RFC", ""), key="registro_rfc")
                    forma_pago = st.selectbox("Forma de Pago", OPCIONES_PAGO, key="registro_pago")
                    moneda = st.selectbox("Moneda", [""] + OPCIONES_MONEDA,placeholder="Selecciona Moneda", key="registro_moneda")

                with col2:
                    banco = st.selectbox("Banco", [""] + OPCIONES_BANCO, key="registro_banco")
                    periodicidad = st.selectbox("Periodicidad", [" ", "CONTADO", "MENSUAL", "TRIMESTRAL", "SEMESTRAL"], key="registro_periodicidad")
                    prima_total_emitida = st.text_input("Prima Total Emitida", key="registro_prima_total", placeholder="Ingrese monto")
                    prima_neta = st.text_input("Prima Neta", key="registro_prima_neta", placeholder="Ingrese monto")
                    primer_pago = st.text_input("Primer Pago", key="registro_primer_pago", placeholder="Ingrese monto")
                    pagos_subsecuentes = st.text_input("Pagos Subsecuentes", key="registro_pagos_subsecuentes", placeholder="Ingrese monto")
                    aseguradora = st.selectbox("Aseguradora", [""] + OPCIONES_ASEG, key="registro_aseguradora")
                    comision_porcentaje = st.text_input("% Comisión", key="registro_comision_pct", placeholder="Ej: 10.5")
                    estado = st.selectbox("Estado", [""] + OPCIONES_ESTADO_POLIZA, key="registro_estado")
                    contacto = st.text_input("Contacto", key="registro_contacto", placeholder="Persona de contacto")
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
                    clave_emision = st.selectbox("Clave de Emisión", [" ","Emilia Alcocer","José Carlos Ibarra","Suemy Alcocer"],key="registro_clave_emision")
                    # Promoción
                    promocion_val = st.session_state.poliza_data_edit.get("Promoción", "No")
                    promocion_index = obtener_indice_selectbox(promocion_val, OPCIONES_PROMOCION)
                    promocion = st.selectbox(
                        "Promoción", 
                        [""] + OPCIONES_PROMOCION, 
                        index=promocion_index,
                        key="edit_promocion"
                    )
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
                                "Clave de Emisión": clave_emision,
                                "Promoción": promocion
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
    cliente_seleccionado = st.selectbox("Seleccionar Cliente", [""] + clientes_unicos, key="consulta_cliente")

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
                        tipo_persona_val = st.session_state.cliente_data_edit.get("Tipo Persona", "")
                        tipo_persona_index = obtener_indice_selectbox(tipo_persona_val, OPCIONES_PERSONA)
                        tipo_persona_edit = st.selectbox(
                            "Tipo Persona", 
                            [""] + OPCIONES_PERSONA,
                            index=tipo_persona_index,
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
                        promocion_val = st.session_state.poliza_data_edit.get("Promoción", "No")
                        promocion_index = obtener_indice_selectbox(promocion_val, OPCIONES_PROMOCION)
                        promocion = st.selectbox(
                            "Promoción", 
                            [""] + OPCIONES_PROMOCION, 
                            index=promocion_index,
                            key="edit_promocion"
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
                                df_polizas.loc[mask, 'Promoción'] = promocion
                                # NUEVO: Si se cambió el estado a CANCELADO, cancelar recibos futuros
                                estado_anterior = df_polizas[mask]['Estado'].values[0] if mask.any() else None
                                
                                if estado == "CANCELADO" and estado_anterior != "CANCELADO":
                                    # Usar fecha actual como fecha de cancelación por defecto
                                    fecha_cancelacion_input = datetime.now().strftime("%d/%m/%Y")
                                    
                                    st.info(f"⚠️ La póliza será cancelada. Se cancelarán automáticamente los recibos con vencimiento posterior al {fecha_cancelacion_input}")
                                    
                                    # Cargar cobranza actual
                                    _, _, df_cobranza_actual, _, _ = cargar_datos()
                                    
                                    # Cancelar recibos futuros
                                    df_cobranza_actualizada = cancelar_recibos_poliza(
                                        poliza_seleccionada,
                                        fecha_cancelacion_input,
                                        df_cobranza_actual
                                    )
                                    
                                    # Guardar ambos cambios
                                    if guardar_datos(df_polizas=df_polizas, df_cobranza=df_cobranza_actualizada):
                                        st.success("✅ Póliza actualizada y recibos futuros cancelados")
                                        st.info(f"ℹ️ Se han cancelado automáticamente los recibos con vencimiento posterior al {fecha_cancelacion_input}")
                                        st.session_state.editando_poliza = False
                                        st.session_state.poliza_data_edit = {}
                                        st.rerun()
                                    else:
                                        st.error("❌ Error al actualizar la póliza")
                                else:
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
            poliza_seleccionada = st.selectbox("Seleccionar Póliza para ver detalles", [""] + polizas_lista, key="detalle_poliza_consulta")
            
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
                    st.write(f"**Promoción:** {poliza_detalle.get('Promoción', 'N/A')}")

                # ===========================================
                # 🆕 SECCIÓN PARA EDITAR PÓLIZA
                # ===========================================
                st.markdown("---")
                st.subheader("✏️ Editar Póliza")
                
                # Inicializar estado para edición
                if 'editando_poliza' not in st.session_state:
                    st.session_state.editando_poliza = False
                if 'poliza_data_edit' not in st.session_state:
                    st.session_state.poliza_data_edit = {}
                
                # Botón para iniciar edición
                if not st.session_state.editando_poliza:
                    if st.button("✏️ Editar esta Póliza", key="btn_editar_poliza"):
                        st.session_state.editando_poliza = True
                        st.session_state.poliza_data_edit = poliza_detalle.to_dict()
                        st.rerun()
                else:
                    # Formulario de edición
                    with st.form("form_editar_poliza"):
                        st.write(f"**Editando Póliza:** {poliza_seleccionada}")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Número de póliza (no editable)
                            st.text_input("No. Póliza (no editable)", 
                                        value=poliza_seleccionada, 
                                        disabled=True,
                                        key="edit_no_poliza")
                            
                            # Producto
                            producto_val = st.session_state.poliza_data_edit.get("Producto", "")
                            producto_index = obtener_indice_selectbox(producto_val, OPCIONES_PRODUCTO)
                            producto = st.selectbox(
                                "Producto*", 
                                [""] + OPCIONES_PRODUCTO, 
                                index=producto_index,
                                key="edit_producto"
                            )
                            
                            # Inicio Vigencia
                            inicio_vigencia = st.text_input(
                                "Inicio Vigencia (dd/mm/yyyy)*", 
                                value=st.session_state.poliza_data_edit.get("Inicio Vigencia", ""),
                                placeholder="dd/mm/yyyy",
                                key="edit_inicio_vigencia"
                            )
                            
                            # Fin Vigencia
                            fin_vigencia = st.text_input(
                                "Fin Vigencia (dd/mm/yyyy)*", 
                                value=st.session_state.poliza_data_edit.get("Fin Vigencia", ""),
                                placeholder="dd/mm/yyyy",
                                key="edit_fin_vigencia"
                            )
                            
                            # RFC
                            rfc = st.text_input(
                                "RFC", 
                                value=st.session_state.poliza_data_edit.get("RFC", ""),
                                key="edit_rfc"
                            )
                            
                            # Forma de Pago
                            forma_pago_val = st.session_state.poliza_data_edit.get("Forma de Pago", "")
                            forma_pago_index = obtener_indice_selectbox(forma_pago_val, OPCIONES_PAGO)
                            forma_pago = st.selectbox(
                                "Forma de Pago", 
                                [""] + OPCIONES_PAGO, 
                                index=forma_pago_index,
                                key="edit_forma_pago"
                            )
                            
                            # Banco
                            banco_val = st.session_state.poliza_data_edit.get("Banco", "NINGUNO")
                            banco_index = obtener_indice_selectbox(banco_val, OPCIONES_BANCO)
                            banco = st.selectbox(
                                "Banco", 
                                [""] + OPCIONES_BANCO, 
                                index=banco_index,
                                key="edit_banco"
                            )
                            
                            # Periodicidad
                            periodicidad_options = [" ", "CONTADO", "MENSUAL", "TRIMESTRAL", "SEMESTRAL"]
                            periodicidad_val = st.session_state.poliza_data_edit.get("Periodicidad", " ")
                            periodicidad_index = periodicidad_options.index(periodicidad_val) if periodicidad_val in periodicidad_options else 0
                            periodicidad = st.selectbox(
                                "Periodicidad", 
                                periodicidad_options, 
                                index=periodicidad_index,
                                key="edit_periodicidad"
                            )
                        
                        with col2:
                            # Prima Total Emitida
                            prima_total_emitida = st.text_input(
                                "Prima Total Emitida", 
                                value=st.session_state.poliza_data_edit.get("Prima Total Emitida", ""),
                                key="edit_prima_total"
                            )
                            
                            # Prima Neta
                            prima_neta = st.text_input(
                                "Prima Neta", 
                                value=st.session_state.poliza_data_edit.get("Prima Neta", ""),
                                key="edit_prima_neta"
                            )
                            
                            # Primer Pago
                            primer_pago = st.text_input(
                                "Primer Pago", 
                                value=st.session_state.poliza_data_edit.get("Primer Pago", ""),
                                key="edit_primer_pago"
                            )
                            
                            # Pagos Subsecuentes
                            pagos_subsecuentes = st.text_input(
                                "Pagos Subsecuentes", 
                                value=st.session_state.poliza_data_edit.get("Pagos Subsecuentes", ""),
                                key="edit_pagos_subsecuentes"
                            )
                            
                            # Aseguradora
                            aseguradora_val = st.session_state.poliza_data_edit.get("Aseguradora", "")
                            aseguradora_index = obtener_indice_selectbox(aseguradora_val, OPCIONES_ASEG)
                            aseguradora = st.selectbox(
                                "Aseguradora", 
                                [""] + OPCIONES_ASEG, 
                                index=aseguradora_index,
                                key="edit_aseguradora"
                            )
                            
                            # % Comisión
                            comision_porcentaje = st.text_input(
                                "% Comisión", 
                                value=st.session_state.poliza_data_edit.get("% Comisión", ""),
                                key="edit_comision_pct"
                            )
                            
                            # Estado
                            estado_val = st.session_state.poliza_data_edit.get("Estado", "VIGENTE")
                            estado_index = obtener_indice_selectbox(estado_val, OPCIONES_ESTADO_POLIZA)
                            estado = st.selectbox(
                                "Estado", 
                                [""] + OPCIONES_ESTADO_POLIZA, 
                                index=estado_index,
                                key="edit_estado"
                            )
                            
                            # Moneda
                            moneda_val = st.session_state.poliza_data_edit.get("Moneda", "MXN")
                            moneda_index = obtener_indice_selectbox(moneda_val, OPCIONES_MONEDA)
                            moneda = st.selectbox(
                                "Moneda", 
                                [""] + OPCIONES_MONEDA,
                                index=moneda_index,
                                key="edit_moneda"
                            )
                            
                            # Clave de Emisión
                            clave_emision_options = [" ", "Emilia Alcocer", "José Carlos Ibarra", "Suemy Alcocer"]
                            clave_emision_val = st.session_state.poliza_data_edit.get("Clave de Emisión", " ")
                            clave_emision_index = clave_emision_options.index(clave_emision_val) if clave_emision_val in clave_emision_options else 0
                            clave_emision = st.selectbox(
                                "Clave de Emisión", 
                                clave_emision_options, 
                                index=clave_emision_index,
                                key="edit_clave_emision"
                            )
                            # Promoción
                            promocion_val = st.session_state.poliza_data_edit.get("Promoción", "No")
                            promocion_index = obtener_indice_selectbox(promocion_val, OPCIONES_PROMOCION)
                            promocion = st.selectbox(
                                "Promoción", 
                                [""] + OPCIONES_PROMOCION, 
                                index=promocion_index,
                                key="edit_promocion"
                            )
                        
                        # Validaciones
                        fecha_errors = []
                        if inicio_vigencia:
                            valido, error = validar_fecha(inicio_vigencia)
                            if not valido:
                                fecha_errors.append(f"Inicio Vigencia: {error}")
                        
                        if fin_vigencia:
                            valido, error = validar_fecha(fin_vigencia)
                            if not valido:
                                fecha_errors.append(f"Fin Vigencia: {error}")
                        
                        if fecha_errors:
                            for error in fecha_errors:
                                st.error(error)
                        
                        # Botones
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            submitted = st.form_submit_button("💾 Guardar Cambios")
                        with col_btn2:
                            cancel = st.form_submit_button("❌ Cancelar Edición")
                        
                        if cancel:
                            st.session_state.editando_poliza = False
                            st.session_state.poliza_data_edit = {}
                            st.rerun()
                        
                        if submitted:
                            if fecha_errors:
                                st.warning("Corrija los errores en las fechas antes de guardar")
                            else:
                                # Actualizar la póliza en el DataFrame
                                mask = df_polizas['No. Póliza'] == poliza_seleccionada
                                
                                # Actualizar todos los campos
                                df_polizas.loc[mask, 'Producto'] = producto
                                df_polizas.loc[mask, 'Inicio Vigencia'] = inicio_vigencia
                                df_polizas.loc[mask, 'Fin Vigencia'] = fin_vigencia
                                df_polizas.loc[mask, 'RFC'] = rfc
                                df_polizas.loc[mask, 'Forma de Pago'] = forma_pago
                                df_polizas.loc[mask, 'Banco'] = banco
                                df_polizas.loc[mask, 'Periodicidad'] = periodicidad
                                df_polizas.loc[mask, 'Prima Total Emitida'] = prima_total_emitida
                                df_polizas.loc[mask, 'Prima Neta'] = prima_neta
                                df_polizas.loc[mask, 'Primer Pago'] = primer_pago
                                df_polizas.loc[mask, 'Pagos Subsecuentes'] = pagos_subsecuentes
                                df_polizas.loc[mask, 'Aseguradora'] = aseguradora
                                df_polizas.loc[mask, '% Comisión'] = comision_porcentaje
                                df_polizas.loc[mask, 'Estado'] = estado
                                df_polizas.loc[mask, 'Moneda'] = moneda
                                df_polizas.loc[mask, 'Clave de Emisión'] = clave_emision
                                df_polizas.loc[mask, 'Promoción'] = promocion
                                
                                if guardar_datos(df_polizas=df_polizas):
                                    st.success("✅ Póliza actualizada correctamente")
                                    st.session_state.editando_poliza = False
                                    st.session_state.poliza_data_edit = {}
                                    st.rerun()
                                else:
                                    st.error("❌ Error al actualizar la póliza")

                # Formulario para actualizar estado de la póliza
                with st.form("form_actualizar_estado"):
                    st.write("**Actualizar Estado de la Póliza**")
                    nuevo_estado = st.selectbox("Nuevo Estado",[""] +  OPCIONES_ESTADO_POLIZA, 
                                               index=obtener_indice_selectbox(poliza_detalle.get('Estado', 'VIGENTE'), OPCIONES_ESTADO_POLIZA))
                    
                    if st.form_submit_button("💾 Actualizar Estado"):
                        # Actualizar el estado en el DataFrame
                        mask = (df_polizas['No. Póliza'] == poliza_seleccionada)
                        df_polizas.loc[mask, 'Estado'] = nuevo_estado
                        
                        if guardar_datos(df_polizas=df_polizas):
                            st.success("✅ Estado de la póliza actualizado correctamente")
                            st.rerun()
                        else:
                            st.error("❌ Error al actualizar el estado")

# 5. Póliza Nueva (para clientes existentes) - CON VALIDACIÓN MEJORADA
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
                    no_poliza = st.text_input("No. Póliza*", 
                                            placeholder="Ingrese el número de póliza",
                                            key="nueva_poliza_numero")
                    producto = st.selectbox("Producto*", [""] + OPCIONES_PRODUCTO, 
                                          key="nueva_poliza_producto")
                    inicio_vigencia = st.text_input("Inicio Vigencia (dd/mm/yyyy)*", 
                                                  placeholder="dd/mm/yyyy",
                                                  key="nueva_poliza_inicio")
                    fin_vigencia = st.text_input("Fin Vigencia (dd/mm/yyyy)*", 
                                               placeholder="dd/mm/yyyy",
                                               key="nueva_poliza_fin")
                    forma_pago = st.selectbox("Forma de Pago*",[""] +  OPCIONES_PAGO, 
                                            key="nueva_poliza_pago")
                    banco = st.selectbox("Banco*", [""] + OPCIONES_BANCO, 
                                       key="nueva_poliza_banco")
                    periodicidad = st.selectbox("Periodicidad*", [" ", "CONTADO", "MENSUAL", "TRIMESTRAL", "SEMESTRAL"], 
                                              key="nueva_poliza_periodicidad")
                    moneda = st.selectbox("Moneda*", [""] + OPCIONES_MONEDA, 
                                        key="nueva_poliza_moneda")

                with col2:
                    prima_total_emitida = st.text_input("Prima Total Emitida*", 
                                                      placeholder="Ej: 15000.00",
                                                      key="nueva_poliza_prima_total")
                    prima_neta = st.text_input("Prima Neta*", 
                                             placeholder="Ej: 14000.00",
                                             key="nueva_poliza_prima_neta")
                    primer_pago = st.text_input("Primer Pago*", 
                                              placeholder="Ej: 5000.00",
                                              key="nueva_poliza_primer_pago")
                    pagos_subsecuentes = st.text_input("Pagos Subsecuentes*", 
                                                      placeholder="Ej: 1000.00",
                                                      key="nueva_poliza_pagos_subsecuentes")
                    aseguradora = st.selectbox("Aseguradora*", [""] + OPCIONES_ASEG, 
                                             key="nueva_poliza_aseguradora")
                    comision_porcentaje = st.text_input("% Comisión*", 
                                                      placeholder="Ej: 10.5",
                                                      key="nueva_poliza_comision_pct")
                    estado = st.selectbox("Estado*", [""] + OPCIONES_ESTADO_POLIZA, 
                                        key="nueva_poliza_estado")
                    contacto = st.text_input("Contacto (opcional)", 
                                           placeholder="Persona de contacto",
                                           key="nueva_poliza_contacto")
                    direccion = st.text_input("Dirección (opcional, indicar ciudad y CP)", 
                                            placeholder="Ej: Calle 123, CDMX, 03100",
                                            key="nueva_poliza_direccion")
                    referenciador = st.text_input("Referenciador*", 
                                                placeholder="Origen del cliente/promoción",
                                                key="nueva_poliza_referenciador")
                    clave_emision = st.selectbox("Clave de Emisión*", 
                                               [" ", "Emilia Alcocer","José Carlos Ibarra","Suemy Alcocer"], 
                                               key="nueva_poliza_clave_emision")
                    promocion = st.selectbox("Promoción*", [""] + OPCIONES_PROMOCION, key="nueva_poliza_promocion")

                # Lista de campos obligatorios (todos excepto Contacto y Dirección)
                campos_obligatorios = [
                    ("No. Póliza", no_poliza),
                    ("Producto", producto),
                    ("Inicio Vigencia", inicio_vigencia),
                    ("Fin Vigencia", fin_vigencia),
                    ("Forma de Pago", forma_pago),
                    ("Banco", banco),
                    ("Periodicidad", periodicidad),
                    ("Moneda", moneda),
                    ("Prima Total Emitida", prima_total_emitida),
                    ("Prima Neta", prima_neta),
                    ("Primer Pago", primer_pago),
                    ("Pagos Subsecuentes", pagos_subsecuentes),
                    ("Aseguradora", aseguradora),
                    ("% Comisión", comision_porcentaje),
                    ("Estado", estado),
                    ("Referenciador", referenciador),
                    ("Clave de Emisión", clave_emision),
                    ("Promoción", promocion)
                ]

                errores = []

                # Validar fechas
                if inicio_vigencia:
                    valido, error = validar_fecha(inicio_vigencia)
                    if not valido:
                        errores.append(f"Inicio Vigencia: {error}")
                else:
                    errores.append("Inicio Vigencia es obligatorio")

                if fin_vigencia:
                    valido, error = validar_fecha(fin_vigencia)
                    if not valido:
                        errores.append(f"Fin Vigencia: {error}")
                else:
                    errores.append("Fin Vigencia es obligatorio")

                # Validar que los campos obligatorios no estén vacíos
                for campo_nombre, campo_valor in campos_obligatorios:
                    if not campo_valor or str(campo_valor).strip() == "" or str(campo_valor).strip() == " ":
                        errores.append(f"{campo_nombre} es obligatorio")

                # Validar que los campos numéricos tengan valores válidos
                try:
                    if prima_total_emitida and prima_total_emitida.strip():
                        float(prima_total_emitida.replace(',', ''))
                except ValueError:
                    errores.append("Prima Total Emitida debe ser un número válido")
                
                try:
                    if prima_neta and prima_neta.strip():
                        float(prima_neta.replace(',', ''))
                except ValueError:
                    errores.append("Prima Neta debe ser un número válido")
                
                try:
                    if primer_pago and primer_pago.strip():
                        float(primer_pago.replace(',', ''))
                except ValueError:
                    errores.append("Primer Pago debe ser un número válido")
                
                try:
                    if pagos_subsecuentes and pagos_subsecuentes.strip():
                        float(pagos_subsecuentes.replace(',', ''))
                except ValueError:
                    errores.append("Pagos Subsecuentes debe ser un número válido")
                
                try:
                    if comision_porcentaje and comision_porcentaje.strip():
                        float(comision_porcentaje.replace(',', ''))
                except ValueError:
                    errores.append("% Comisión debe ser un número válido")

                submitted_nueva_poliza = st.form_submit_button("💾 Guardar Nueva Póliza")
                if submitted_nueva_poliza:
                    if errores:
                        for error in errores:
                            st.error(error)
                        st.warning("Por favor, complete todos los campos obligatorios antes de guardar.")
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
                                "Clave de Emisión": clave_emision,
                                "Promoción": promocion
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
                [""] + polizas_lista, 
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

# 7. Cobranza (versión actualizada que incluye recibos vencidos)
def mostrar_cobranza(df_polizas, df_cobranza):
    st.header("💰 Cobranza")

    # Botón para recalcular cobranza (incluyendo vencidos)
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔄 Recalcular Cobranza (Incluye Vencidos)", use_container_width=True):
            df_cobranza_proxima = calcular_cobranza()
            if not df_cobranza_proxima.empty:
                # Combinar con datos existentes
                if df_cobranza is not None and not df_cobranza.empty:
                    # Usar ID_Cobranza para evitar duplicados
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
                
                if guardar_datos(df_cobranza=df_cobranza_completa):
                    st.success("✅ Cobranza recalculada exitosamente (incluyendo recibos vencidos)")
                    st.rerun()
    
    with col_btn2:
        if st.button("📊 Ver Solo Pendientes", use_container_width=True):
            if 'filtro_cobranza' not in st.session_state:
                st.session_state.filtro_cobranza = True
            else:
                st.session_state.filtro_cobranza = not st.session_state.filtro_cobranza
            st.rerun()

    # Calcular cobranza de los próximos 60 días (incluye vencidos)
    df_cobranza_proxima = calcular_cobranza()

    if df_cobranza_proxima.empty and (df_cobranza is None or df_cobranza.empty):
        st.info("No hay cobranza registrada")
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

    # Filtrar según el filtro seleccionado
    if 'Estatus' in df_cobranza_completa.columns:
        # Verificar si debemos mostrar solo pendientes o todos
        if 'filtro_cobranza' not in st.session_state or st.session_state.filtro_cobranza:
            df_mostrar = df_cobranza_completa[df_cobranza_completa['Estatus'].isin(['Pendiente', 'Vencido'])]
            st.info("Mostrando recibos Pendientes y Vencidos")
        else:
            df_mostrar = df_cobranza_completa[df_cobranza_completa['Estatus'] == 'Pendiente']
            st.info("Mostrando solo recibos Pendientes")
    else:
        df_mostrar = df_cobranza_completa

    if df_mostrar.empty:
        st.success("🎉 No hay recibos pendientes o vencidos")
        return

    # Obtener información de las pólizas
    df_mostrar_con_info = df_mostrar.copy()
    
    # Buscar la información adicional para cada póliza
    for idx, row in df_mostrar_con_info.iterrows():
        no_poliza = row['No. Póliza']
        poliza_info = df_polizas[df_polizas['No. Póliza'].astype(str) == str(no_poliza)]
        
        if not poliza_info.empty:
            clave_emision = poliza_info.iloc[0].get('Clave de Emisión', '')
            df_mostrar_con_info.at[idx, 'Clave de Emisión'] = clave_emision
        else:
            df_mostrar_con_info.at[idx, 'Clave de Emisión'] = ""

    # Calcular días transcurridos desde el vencimiento
    hoy = datetime.now().date()
    
    def calcular_dias_transcurridos(fecha_vencimiento_str):
        if not fecha_vencimiento_str or pd.isna(fecha_vencimiento_str) or fecha_vencimiento_str == "":
            return None
        
        try:
            # Convertir fecha de vencimiento a datetime
            fecha_vencimiento = datetime.strptime(fecha_vencimiento_str, "%d/%m/%Y").date()
            # Calcular días transcurridos desde la fecha de vencimiento
            dias_transcurridos = (hoy - fecha_vencimiento).days
            return max(0, dias_transcurridos)  # No mostrar negativos
        except:
            return None

    # Aplicar cálculo de días transcurridos
    df_mostrar_con_info['Días Transcurridos'] = df_mostrar_con_info['Fecha Vencimiento'].apply(calcular_dias_transcurridos)

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
    df_mostrar_con_info['Prima de Recibo Formateado'] = df_mostrar_con_info['Prima de Recibo'].apply(formatear_monto)
    df_mostrar_con_info['Monto Pagado Formateado'] = df_mostrar_con_info['Monto Pagado'].apply(formatear_monto)

    # Crear DataFrame para mostrar
    columnas_base = [
        'Recibo', 'Periodicidad', 'Moneda', 'Prima de Recibo Formateado', 
        'Monto Pagado Formateado', 'Fecha Vencimiento', 'Días Transcurridos',
        'No. Póliza', 'Nombre/Razón Social', 'Clave de Emisión', 'Mes Cobranza', 
        'Fecha Pago', 'Estatus', 'Comentario'
    ]
    
    # Filtrar solo las columnas que existen en el DataFrame
    columnas_finales = [col for col in columnas_base if col in df_mostrar_con_info.columns]
    
    # Crear el DataFrame final para mostrar
    df_display = df_mostrar_con_info[columnas_finales].rename(columns={
        'Prima de Recibo Formateado': 'Prima de Recibo',
        'Monto Pagado Formateado': 'Monto Pagado'
    })

    # Aplicar colores según estatus y días transcurridos
    def color_row_by_status(row):
        estatus = row.get('Estatus', '')
        dias_transcurridos = row.get('Días Transcurridos', 0)
        
        if estatus == 'Vencido':
            return ['background-color: #8B0000; color: white; font-weight: bold;'] * len(row)
        elif estatus == 'Pagado':
            return ['background-color: #d4edda; color: #155724;'] * len(row)
        elif dias_transcurridos is None:
            return [''] * len(row)
        elif dias_transcurridos >= 20:
            return ['background-color: #f8d7da; color: #721c24; font-weight: bold;'] * len(row)
        elif dias_transcurridos >= 11:
            return ['background-color: #ffe6cc; color: #cc6600; font-weight: bold;'] * len(row)
        elif dias_transcurridos >= 5:
            return ['background-color: #fff3cd; color: #856404;'] * len(row)
        else:
            return ['background-color: #d4edda; color: #155724;'] * len(row)

    # Mostrar el DataFrame sin índice
    try:
        styled_df = df_display.style.apply(color_row_by_status, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    except Exception:
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    # Leyenda de colores
    st.markdown("""
    **Leyenda de colores:**
    - 🟢 **Verde claro:** Pagado
    - 🟢 **Verde oscuro:** Menos de 5 días transcurridos
    - 🟡 **Amarillo:** 5-10 días transcurridos
    - 🟠 **Naranja:** 11-20 días transcurridos
    - 🔴 **Rojo:** Más de 20 días transcurridos
    - 🔴 **Rojo oscuro:** Recibos vencidos (cobranza vencida)
    - ⚫ **Gris:** Recibos cancelados
    """)

    # Formulario para registrar pagos (incluye recibos vencidos)
    st.subheader("Registrar Pago (Incluye Vencidos)")

    # Inicializar estado para la selección de cobranza
    if 'cobranza_seleccionada' not in st.session_state:
        st.session_state.cobranza_seleccionada = None
    if 'info_cobranza_actual' not in st.session_state:
        st.session_state.info_cobranza_actual = None

    # Crear lista de opciones para selección individual de recibos (excluye pagados)
    if not df_mostrar_con_info.empty:
        df_no_pagados = df_mostrar_con_info[~df_mostrar_con_info['Estatus'].isin(['Pagado'])]
        
        if not df_no_pagados.empty:
            opciones_cobranza = []
            for idx, row in df_no_pagados.iterrows():
                # Formatear monto
                monto_formateado = formatear_monto(row.get('Prima de Recibo', 0))
                # Crear descripción amigable
                estatus_display = "VENCIDO" if row.get('Estatus') == 'Vencido' else row.get('Estatus', '')
                descripcion = f"{row['No. Póliza']} - Recibo {row['Recibo']} - {row.get('Nombre/Razón Social', '')} - {monto_formateado} {row.get('Moneda', 'MXN')} - Vence: {row.get('Fecha Vencimiento', '')} - {estatus_display}"
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
                        col_info1, col_info2 = st.columns(2)
                        
                        with col_info1:
                            st.write(f"**Recibo seleccionado:** {info_cobranza.get('Recibo', '')}")
                            st.write(f"**Cliente:** {info_cobranza.get('Nombre/Razón Social', '')}")
                            st.write(f"**No. Póliza:** {info_cobranza.get('No. Póliza', '')}")
                            st.write(f"**Clave de Emisión:** {info_cobranza.get('Clave de Emisión', 'No disponible')}")
                        
                        with col_info2:
                            # Mostrar Prima de Recibo directamente
                            prima_recibo = info_cobranza.get('Prima de Recibo', 0)
                            moneda = info_cobranza.get('Moneda', 'MXN')
                            prima_recibo_formateado = formatear_monto(prima_recibo)
                            st.write(f"**Prima de Recibo:** {prima_recibo_formateado} {moneda}")
                            st.write(f"**Fecha Vencimiento:** {info_cobranza.get('Fecha Vencimiento', '')}")
                            st.write(f"**Periodicidad:** {info_cobranza.get('Periodicidad', '')}")
                            st.write(f"**Estatus actual:** {info_cobranza.get('Estatus', '')}")
                        
                        # Mostrar comentario si existe
                        comentario = info_cobranza.get('Comentario', '')
                        if comentario:
                            st.warning(f"**Comentario:** {comentario}")
                        
                        # Mostrar días transcurridos
                        dias_transcurridos = calcular_dias_transcurridos(info_cobranza.get('Fecha Vencimiento', ''))
                        if dias_transcurridos is not None and dias_transcurridos > 0:
                            st.error(f"**⚠️ ALERTA:** Este recibo tiene {dias_transcurridos} días de vencido")

                        # Formulario para el pago - SOLO SE MUESTRA CUANDO HAY UN RECIBO SELECCIONADO
                        with st.form("form_pago"):
                            col_form1, col_form2 = st.columns(2)
                            
                            with col_form1:
                                # Monto Pagado con valor por defecto igual a la prima
                                monto_prima = info_cobranza.get('Prima de Recibo', 0)
                                monto_pagado = st.number_input(
                                    "Monto Pagado", 
                                    min_value=0.0,
                                    value=float(monto_prima) if monto_prima else 0.0,
                                    step=0.01, 
                                    key="monto_pagado"
                                )
                                
                                # Mostrar la moneda del pago
                                moneda_cobranza = info_cobranza.get('Moneda', 'MXN')
                                st.write(f"**Moneda del pago:** {moneda_cobranza}")
                            
                            with col_form2:
                                fecha_pago = st.text_input(
                                    "Fecha de Pago (dd/mm/yyyy)", 
                                    value="", 
                                    placeholder="dd/mm/yyyy",
                                    key="fecha_pago_cob"
                                )
                                
                                # Campo opcional para comentario de pago
                                comentario_pago = st.text_area(
                                    "Comentario del Pago (opcional)",
                                    placeholder="Ej: Pago realizado con retraso, se contactó al cliente, etc.",
                                    key="comentario_pago"
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
                                            # Actualizar el monto pagado, fecha, estatus y comentario
                                            df_cobranza_completa.loc[mask, 'Monto Pagado'] = monto_pagado
                                            df_cobranza_completa.loc[mask, 'Fecha Pago'] = fecha_pago
                                            df_cobranza_completa.loc[mask, 'Estatus'] = 'Pagado'
                                            
                                            # Actualizar días de atraso si existe la columna
                                            if 'Días Atraso' in df_cobranza_completa.columns:
                                                fecha_vencimiento = info_cobranza.get('Fecha Vencimiento', '')
                                                if fecha_vencimiento:
                                                    try:
                                                        fecha_vencimiento_dt = datetime.strptime(fecha_vencimiento, "%d/%m/%Y")
                                                        fecha_pago_dt = datetime.strptime(fecha_pago, "%d/%m/%Y")
                                                        dias_atraso = max(0, (fecha_pago_dt - fecha_vencimiento_dt).days)
                                                        df_cobranza_completa.loc[mask, 'Días Atraso'] = dias_atraso
                                                    except:
                                                        pass
                                            
                                            # Agregar comentario si se proporcionó
                                            if comentario_pago:
                                                comentario_actual = df_cobranza_completa.loc[mask, 'Comentario'].values[0]
                                                nuevo_comentario = f"{comentario_actual} | Pago: {comentario_pago}" if comentario_actual else f"Pago: {comentario_pago}"
                                                df_cobranza_completa.loc[mask, 'Comentario'] = nuevo_comentario
                                        else:
                                            # Si no existe (caso raro), agregamos un registro como pagado
                                            nuevo = {
                                                "No. Póliza": info_cobranza['No. Póliza'],
                                                "Nombre/Razón Social": info_cobranza.get('Nombre/Razón Social', ''),
                                                "Mes Cobranza": info_cobranza.get('Mes Cobranza', ''),
                                                "Fecha Vencimiento": info_cobranza.get('Fecha Vencimiento', ''),
                                                "Prima de Recibo": info_cobranza.get('Prima de Recibo', 0),
                                                "Monto Pagado": monto_pagado,
                                                "Fecha Pago": fecha_pago,
                                                "Estatus": "Pagado",
                                                "Periodicidad": info_cobranza.get('Periodicidad', ''),
                                                "Moneda": info_cobranza.get('Moneda', 'MXN'),
                                                "Recibo": info_cobranza.get('Recibo', ''),
                                                "Clave de Emisión": info_cobranza.get('Clave de Emisión', ''),
                                                "Comentario": f"Pago: {comentario_pago}" if comentario_pago else "",
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
                st.info("No hay recibos pendientes o vencidos disponibles para seleccionar")
        else:
            st.success("🎉 ¡Todos los recibos están pagados!")
    else:
        st.info("No hay recibos para mostrar")
    # Sección para gestión de recibos
    st.markdown("---")
    df_cobranza_completa = mostrar_gestion_recibos(df_cobranza_completa)
    st.markdown("---")
    # HISTORIAL DE PAGOS CON FILTROS MEJORADOS
    if df_cobranza is not None and not df_cobranza.empty:
        if 'Estatus' in df_cobranza.columns:
            df_pagados = df_cobranza[df_cobranza['Estatus'] == 'Pagado']
        else:
            df_pagados = pd.DataFrame()
            
        if not df_pagados.empty:
            st.subheader("📋 Historial de Pagos")
            
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
                'Periodicidad', 'Moneda', 'Clave de Emisión', 'Comentario'
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
        "💰 Operación"
    ]
        #"📈 Asesoría Rizkora"  # NUEVA PESTAÑA
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
    #elif st.session_state.active_tab == "📈 Asesoría Rizkora":  # NUEVA PESTAÑA
        #mostrar_asesoria_axa()

# ================================
# EJECUTAR LA APLICACIÓN
# ================================
if __name__ == "__main__":
    # Configurar estilo de matplotlib
    plt.style.use('seaborn-v0_8-whitegrid')
    
    # Ejecutar la aplicación
    main()





