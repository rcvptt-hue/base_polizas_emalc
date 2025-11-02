# -*- coding: utf-8 -*-
"""
Created on Sat Nov  1 21:11:49 2025

@author: rccorreall
"""

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import re

# Configuración de la página
st.set_page_config(
    page_title="Gestor de Pólizas EALC",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Opciones para combobox
OPCIONES_PRODUCTO = [
    "GMMI", "GMMC", "API", "APE", "APC", "PPL", "OV", "PPR",
    "EDUCACIONAL", "AHORRO", "TEMPORAL", "VG", "AUTO", "FLOTILLA", "HOGAR", "VIAJERO", "DAÑOS"
]
OPCIONES_PAGO = ["PAGO REFERENCIADO", "TRANSFERENCIA", "CARGO TDC", "CARGO TDD"]
OPCIONES_ASEG = ["AXA", "ALLIANZ", "ATLAS", "BANORTE", "ZURICH", "GNP", "HIR", "QUALITAS"]
OPCIONES_BANCO = ["NINGUNO", "AMERICAN EXPRESS", "BBVA", "BANCOMER", "BANREGIO", "HSBC", "SANTANDER"]
OPCIONES_PERSONA = ["MORAL", "FÍSICA"]

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

# Conectar a la hoja específica
@st.cache_resource(ttl=3600)
def conectar_google_sheets():
    """Conectar a la hoja base_polizas_ealc"""
    try:
        spreadsheet = client.open("base_polizas_ealc")
        return spreadsheet
    except Exception as e:
        st.error(f"❌ Error al conectar con la hoja 'base_polizas_ealc': {str(e)}")
        st.info("ℹ️ Asegúrate de que la hoja 'base_polizas_ealc' exista y esté compartida con el servicio account")
        return None

# Función para cargar datos con cache
@st.cache_data(ttl=300)
def cargar_datos():
    """Cargar datos desde Google Sheets"""
    try:
        spreadsheet = conectar_google_sheets()
        if not spreadsheet:
            return pd.DataFrame(), pd.DataFrame()
        
        # Cargar hojas existentes sin intentar crearlas
        try:
            worksheet_prospectos = spreadsheet.worksheet("Prospectos")
            df_prospectos = pd.DataFrame(worksheet_prospectos.get_all_records())
        except Exception as e:
            st.error(f"❌ Error al cargar hoja 'Prospectos': {e}")
            df_prospectos = pd.DataFrame(columns=[
                "Tipo Persona", "Nombre/Razón Social", "Fecha Nacimiento", "RFC", "Teléfono",
                "Correo", "Producto", "Fecha Registro", "Fecha Contacto", "Seguimiento", "Representantes Legales"
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
                "Monto Periodo", "Aseguradora", "% Comisión", "Comisión", "Estado", "Contacto", "Dirección",
                "Teléfono", "Correo", "Fecha Nacimiento"
            ])
        
        return df_prospectos, df_polizas
        
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame(), pd.DataFrame()

# Función para guardar datos (invalida el cache)
def guardar_datos(df_prospectos, df_polizas):
    """Guardar datos en Google Sheets e invalidar cache"""
    try:
        spreadsheet = conectar_google_sheets()
        if not spreadsheet:
            return False
        
        # Actualizar hoja de Prospectos (usar existente)
        try:
            worksheet_prospectos = spreadsheet.worksheet("Prospectos")
            # Limpiar y actualizar manteniendo formato
            worksheet_prospectos.clear()
            if not df_prospectos.empty:
                # Preparar datos para actualizar
                data = [df_prospectos.columns.values.tolist()] + df_prospectos.fillna('').values.tolist()
                worksheet_prospectos.update(data, value_input_option='USER_ENTERED')
        except Exception as e:
            st.error(f"❌ Error al actualizar hoja 'Prospectos': {e}")
            return False
        
        # Actualizar hoja de Pólizas (usar existente)
        try:
            worksheet_polizas = spreadsheet.worksheet("Polizas")
            # Limpiar y actualizar manteniendo formato
            worksheet_polizas.clear()
            if not df_polizas.empty:
                # Preparar datos para actualizar
                data = [df_polizas.columns.values.tolist()] + df_polizas.fillna('').values.tolist()
                worksheet_polizas.update(data, value_input_option='USER_ENTERED')
        except Exception as e:
            st.error(f"❌ Error al actualizar hoja 'Polizas': {e}")
            return False
        
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
    
    # Limpiar espacios
    fecha_str = str(fecha_str).strip()
    
    patron = r'^\d{1,2}/\d{1,2}/\d{4}$'
    if re.match(patron, fecha_str):
        try:
            # Verificar que la fecha sea válida
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
        _, df_polizas = cargar_datos()
        
        if df_polizas.empty:
            return pd.DataFrame()
        
        # Filtrar solo pólizas vigentes
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

# Función principal
def main():
    st.title("📊 Gestor de Prospectos y Pólizas EALC")
    
    # Botón para forzar recarga de datos
    col1, col2, col3 = st.columns([3, 1, 1])
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
    df_prospectos, df_polizas = cargar_datos()
    
    # Crear pestañas
    tab1, tab2, tab3, tab4 = st.tabs([
        "👥 Prospectos", 
        "📋 Póliza Prospectos", 
        "🆕 Pólizas Nuevas", 
        "⏰ Próximos Vencimientos"
    ])
    
    # --- PESTAÑA 1: PROSPECTOS ---
    with tab1:
        st.header("Gestión de Prospectos")
        
        with st.form("form_prospectos"):
            col1, col2 = st.columns(2)
            
            with col1:
                tipo_persona = st.selectbox("Tipo Persona", OPCIONES_PERSONA, key="prospecto_tipo")
                nombre_razon = st.text_input("Nombre/Razón Social*", key="prospecto_nombre")
                fecha_nacimiento = st.text_input("Fecha Nacimiento (dd/mm/yyyy)", 
                                               placeholder="dd/mm/yyyy",
                                               key="prospecto_nacimiento")
                rfc = st.text_input("RFC", key="prospecto_rfc")
                telefono = st.text_input("Teléfono", key="prospecto_telefono")
                correo = st.text_input("Correo", key="prospecto_correo")
            
            with col2:
                producto = st.selectbox("Producto", OPCIONES_PRODUCTO, key="prospecto_producto")
                fecha_registro = st.text_input("Fecha Registro*", 
                                            value=fecha_actual(),
                                            placeholder="dd/mm/yyyy",
                                            key="prospecto_registro")
                fecha_contacto = st.text_input("Fecha Contacto (dd/mm/yyyy)", 
                                             placeholder="dd/mm/yyyy",
                                             key="prospecto_contacto")
                seguimiento = st.text_input("Seguimiento (dd/mm/yyyy)", 
                                          placeholder="dd/mm/yyyy",
                                          key="prospecto_seguimiento")
                representantes = st.text_area("Representantes Legales (separar por comas)", 
                                            placeholder="Ej: Juan Pérez, María García",
                                            key="prospecto_representantes")
            
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
            
            submitted_prospecto = st.form_submit_button("💾 Agregar Prospecto")
            if submitted_prospecto:
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
                        "Producto": producto,
                        "Fecha Registro": fecha_registro if fecha_registro else fecha_actual(),
                        "Fecha Contacto": fecha_contacto if fecha_contacto else "",
                        "Seguimiento": seguimiento if seguimiento else "",
                        "Representantes Legales": representantes
                    }
                    
                    df_prospectos = pd.concat([df_prospectos, pd.DataFrame([nuevo_prospecto])], ignore_index=True)
                    if guardar_datos(df_prospectos, df_polizas):
                        st.success("✅ Prospecto agregado correctamente")
                        st.rerun()
                    else:
                        st.error("❌ Error al guardar el prospecto")
        
        # Mostrar lista de prospectos
        st.subheader("Lista de Prospectos")
        if not df_prospectos.empty:
            st.dataframe(df_prospectos, use_container_width=True)
        else:
            st.info("No hay prospectos registrados")
    
    # --- PESTAÑA 2: PÓLIZA PROSPECTOS ---
    with tab2:
        st.header("Convertir Prospecto a Póliza")
        
        # Seleccionar prospecto - FUERA del formulario para evitar el cambio de pestaña
        if not df_prospectos.empty:
            prospectos_lista = df_prospectos["Nombre/Razón Social"].dropna().tolist()
            prospecto_seleccionado = st.selectbox("Seleccionar Prospecto", [""] + prospectos_lista, key="poliza_prospecto")
            
            if prospecto_seleccionado:
                # Cargar datos del prospecto seleccionado
                prospecto_data = df_prospectos[df_prospectos["Nombre/Razón Social"] == prospecto_seleccionado].iloc[0]
                
                with st.form("form_poliza_prospecto"):
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
                    
                    with col2:
                        banco = st.selectbox("Banco", OPCIONES_BANCO, key="poliza_banco")
                        periodicidad = st.selectbox("Periodicidad", ["ANUAL", "MENSUAL", "TRIMESTRAL", "SEMESTRAL"], key="poliza_periodicidad")
                        prima_emitida = st.text_input("Prima Total Emitida", key="poliza_prima")
                        prima_neta = st.text_input("Prima Neta", key="poliza_prima_neta")
                        primer_pago = st.text_input("Primer Pago", key="poliza_primer_pago")
                        pagos_subsecuentes = st.text_input("Pagos Subsecuentes", key="poliza_pagos_sub")
                        aseguradora = st.selectbox("Aseguradora", OPCIONES_ASEG, key="poliza_aseguradora")
                        comision_porcentaje = st.text_input("% Comisión", key="poliza_comision_pct")
                    
                    col3, col4 = st.columns(2)
                    with col3:
                        estado = st.selectbox("Estado", ["VIGENTE", "CANCELADO", "TERMINADO"], key="poliza_estado")
                        contacto = st.text_input("Contacto", key="poliza_contacto")
                        direccion = st.text_input("Dirección", key="poliza_direccion")
                    
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
                                    "Fecha Nacimiento": fecha_nacimiento_poliza if fecha_nacimiento_poliza else ""
                                }
                                
                                df_polizas = pd.concat([df_polizas, pd.DataFrame([nueva_poliza])], ignore_index=True)
                                
                                # Remover el prospecto de la lista
                                df_prospectos = df_prospectos[df_prospectos["Nombre/Razón Social"] != prospecto_seleccionado]
                                
                                if guardar_datos(df_prospectos, df_polizas):
                                    st.success("✅ Póliza agregada correctamente")
                                    st.rerun()
                                else:
                                    st.error("❌ Error al guardar la póliza")
        else:
            st.info("No hay prospectos disponibles para convertir")
    
    # --- PESTAÑA 3: PÓLIZAS NUEVAS ---
    with tab3:
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
                
                with st.form("form_nueva_poliza"):
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
                    
                    with col2:
                        prima_emitida = st.text_input("Prima Total Emitida", key="nueva_poliza_prima")
                        prima_neta = st.text_input("Prima Neta", key="nueva_poliza_prima_neta")
                        aseguradora = st.selectbox("Aseguradora", OPCIONES_ASEG, key="nueva_poliza_aseguradora")
                        comision_porcentaje = st.text_input("% Comisión", key="nueva_poliza_comision_pct")
                        estado = st.selectbox("Estado", ["VIGENTE", "CANCELADO", "TERMINADO"], key="nueva_poliza_estado")
                        contacto = st.text_input("Contacto", key="nueva_poliza_contacto")
                    
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
                    
                    # Botones de acción
                    col_btn1, col_btn2, col_btn3 = st.columns(3)
                    
                    with col_btn1:
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
                                        "Dirección": cliente_data.get("Dirección", ""),
                                        "Teléfono": cliente_data.get("Teléfono", ""),
                                        "Correo": cliente_data.get("Correo", ""),
                                        "Fecha Nacimiento": cliente_data.get("Fecha Nacimiento", "")
                                    }
                                    
                                    df_polizas = pd.concat([df_polizas, pd.DataFrame([nueva_poliza])], ignore_index=True)
                                    
                                    if guardar_datos(df_prospectos, df_polizas):
                                        st.success("✅ Nueva póliza agregada correctamente")
                                        st.rerun()
                                    else:
                                        st.error("❌ Error al guardar la póliza")
        else:
            st.info("No hay clientes registrados")
    
    # --- PESTAÑA 4: PRÓXIMOS VENCIMIENTOS ---
    with tab4:
        st.header("⏰ Pólizas Próximas a Vencer (45-60 días)")
        
        if st.button("🔄 Actualizar Lista", key="actualizar_vencimientos"):
            st.cache_data.clear()
            st.rerun()
        
        df_vencimientos = obtener_polizas_proximas_vencer(45, 60)
        
        if not df_vencimientos.empty:
            st.success(f"📊 Se encontraron {len(df_vencimientos)} pólizas próximas a vencer")
            
            # Mostrar tabla con estilo condicional
            columnas_mostrar = ["Nombre/Razón Social", "No. Póliza", "Producto", "Fin Vigencia", "Días Restantes"]
            columnas_disponibles = [col for col in columnas_mostrar if col in df_vencimientos.columns]
            
            if columnas_disponibles:
                styled_df = df_vencimientos[columnas_disponibles].copy()
                
                # Aplicar estilo condicional si tenemos la columna de días
                if "Días Restantes" in styled_df.columns:
                    def highlight_days(row):
                        if row['Días Restantes'] <= 50:
                            return ['background-color: #fff3cd; color: #856404;'] * len(row)
                        return [''] * len(row)
                    
                    styled_df = styled_df.style.apply(highlight_days, axis=1)
                
                st.dataframe(styled_df, use_container_width=True)
                
                # Detalles de pólizas seleccionadas
                st.subheader("Detalles de Póliza")
                if "No. Póliza" in df_vencimientos.columns:
                    polizas_lista = df_vencimientos["No. Póliza"].tolist()
                    poliza_seleccionada = st.selectbox("Seleccionar Póliza para ver detalles", polizas_lista, key="detalle_poliza")
                    
                    if poliza_seleccionada:
                        poliza_detalle = df_vencimientos[df_vencimientos["No. Póliza"] == poliza_seleccionada].iloc[0]
                        
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
                            st.write(f"**Días Restantes:** {poliza_detalle.get('Días Restantes', '')}")
                            
                            st.write("**Datos de Contacto:**")
                            st.write(f"**Teléfono:** {poliza_detalle.get('Teléfono', '')}")
                            st.write(f"**Correo:** {poliza_detalle.get('Correo', '')}")
            else:
                st.info("No hay datos suficientes para mostrar")
        else:
            st.info("No hay pólizas que venzan en los próximos 45-60 días")

if __name__ == "__main__":
    main()
