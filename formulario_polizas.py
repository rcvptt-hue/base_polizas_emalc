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
def conectar_google_sheets():
    """Conectar a Google Sheets usando credenciales de Streamlit secrets"""
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        spreadsheet = client.open("base_polizas_ealc")
        return spreadsheet
    except Exception as e:
        st.error(f"Error conectando a Google Sheets: {e}")
        return None

# Función para cargar datos
def cargar_datos():
    """Cargar datos desde Google Sheets"""
    try:
        spreadsheet = conectar_google_sheets()
        if not spreadsheet:
            return pd.DataFrame(), pd.DataFrame()
        
        # Cargar hojas
        try:
            worksheet_prospectos = spreadsheet.worksheet("Prospectos")
            df_prospectos = pd.DataFrame(worksheet_prospectos.get_all_records())
        except:
            df_prospectos = pd.DataFrame(columns=[
                "Tipo Persona", "Nombre/Razón Social", "Fecha Nacimiento", "RFC", "Teléfono",
                "Correo", "Producto", "Fecha Registro", "Fecha Contacto", "Seguimiento", "Representantes Legales"
            ])
        
        try:
            worksheet_polizas = spreadsheet.worksheet("Polizas")
            df_polizas = pd.DataFrame(worksheet_polizas.get_all_records())
            df_polizas["No. Póliza"] = df_polizas["No. Póliza"].astype(str).str.strip()
        except:
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

# Función para guardar datos
def guardar_datos(df_prospectos, df_polizas):
    """Guardar datos en Google Sheets"""
    try:
        spreadsheet = conectar_google_sheets()
        if not spreadsheet:
            return False
        
        # Actualizar hoja de Prospectos
        try:
            worksheet_prospectos = spreadsheet.worksheet("Prospectos")
            worksheet_prospectos.clear()
            worksheet_prospectos.update([df_prospectos.columns.values.tolist()] + df_prospectos.values.tolist())
        except:
            spreadsheet.add_worksheet(title="Prospectos", rows=1000, cols=20)
            worksheet_prospectos = spreadsheet.worksheet("Prospectos")
            worksheet_prospectos.update([df_prospectos.columns.values.tolist()] + df_prospectos.values.tolist())
        
        # Actualizar hoja de Pólizas
        try:
            worksheet_polizas = spreadsheet.worksheet("Polizas")
            worksheet_polizas.clear()
            worksheet_polizas.update([df_polizas.columns.values.tolist()] + df_polizas.values.tolist())
        except:
            spreadsheet.add_worksheet(title="Polizas", rows=1000, cols=25)
            worksheet_polizas = spreadsheet.worksheet("Polizas")
            worksheet_polizas.update([df_polizas.columns.values.tolist()] + df_polizas.values.tolist())
        
        return True
    except Exception as e:
        st.error(f"Error guardando datos: {e}")
        return False

# Función para convertir fechas
def convertir_fecha(valor):
    try:
        if isinstance(valor, str):
            # Intentar con formato día/mes/año
            try:
                return datetime.strptime(valor, "%d/%m/%Y").strftime("%d/%m/%Y")
            except:
                # Intentar con formato año-mes-día
                try:
                    return datetime.strptime(valor, "%Y-%m-%d").strftime("%d/%m/%Y")
                except:
                    # Intentar con formato año-mes-día hora:minuto:segundo
                    try:
                        return datetime.strptime(valor, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y")
                    except:
                        return valor
        return valor
    except:
        return valor

# Función para obtener pólizas próximas a vencer
def obtener_polizas_proximas_vencer(dias_min=45, dias_max=60):
    try:
        _, df_polizas = cargar_datos()
        
        if df_polizas.empty:
            return pd.DataFrame()
        
        # Filtrar solo pólizas vigentes
        df_vigentes = df_polizas[df_polizas["Estado"] == "VIGENTE"]
        
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
                nombre_razon = st.text_input("Nombre/Razón Social", key="prospecto_nombre")
                fecha_nacimiento = st.date_input("Fecha Nacimiento", key="prospecto_nacimiento")
                rfc = st.text_input("RFC", key="prospecto_rfc")
                telefono = st.text_input("Teléfono", key="prospecto_telefono")
                correo = st.text_input("Correo", key="prospecto_correo")
            
            with col2:
                producto = st.selectbox("Producto", OPCIONES_PRODUCTO, key="prospecto_producto")
                fecha_registro = st.date_input("Fecha Registro", value=datetime.now(), key="prospecto_registro")
                fecha_contacto = st.date_input("Fecha Contacto", key="prospecto_contacto")
                seguimiento = st.date_input("Seguimiento", key="prospecto_seguimiento")
                representantes = st.text_area("Representantes Legales (separar por comas)", 
                                            placeholder="Ej: Juan Pérez, María García",
                                            key="prospecto_representantes")
            
            if st.form_submit_button("💾 Agregar Prospecto"):
                if not nombre_razon:
                    st.warning("Debe completar al menos el nombre o razón social")
                else:
                    nuevo_prospecto = {
                        "Tipo Persona": tipo_persona,
                        "Nombre/Razón Social": nombre_razon,
                        "Fecha Nacimiento": fecha_nacimiento.strftime("%d/%m/%Y") if fecha_nacimiento else "",
                        "RFC": rfc,
                        "Teléfono": telefono,
                        "Correo": correo,
                        "Producto": producto,
                        "Fecha Registro": fecha_registro.strftime("%d/%m/%Y"),
                        "Fecha Contacto": fecha_contacto.strftime("%d/%m/%Y") if fecha_contacto else "",
                        "Seguimiento": seguimiento.strftime("%d/%m/%Y") if seguimiento else "",
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
        
        # Seleccionar prospecto
        if not df_prospectos.empty:
            prospectos_lista = df_prospectos["Nombre/Razón Social"].dropna().tolist()
            prospecto_seleccionado = st.selectbox("Seleccionar Prospecto", [""] + prospectos_lista, key="poliza_prospecto")
            
            if prospecto_seleccionado:
                # Cargar datos del prospecto seleccionado
                prospecto_data = df_prospectos[df_prospectos["Nombre/Razón Social"] == prospecto_seleccionado].iloc[0]
                
                with st.form("form_poliza_prospecto"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.text_input("Tipo Persona", value=prospecto_data.get("Tipo Persona", ""), key="poliza_tipo", disabled=True)
                        st.text_input("Nombre/Razón Social", value=prospecto_data.get("Nombre/Razón Social", ""), key="poliza_nombre", disabled=True)
                        no_poliza = st.text_input("No. Póliza*", key="poliza_numero")
                        producto = st.selectbox("Producto", OPCIONES_PRODUCTO, 
                                              index=OPCIONES_PRODUCTO.index(prospecto_data.get("Producto", "")) 
                                              if prospecto_data.get("Producto") in OPCIONES_PRODUCTO else 0,
                                              key="poliza_producto")
                        inicio_vigencia = st.date_input("Inicio Vigencia", key="poliza_inicio")
                        fin_vigencia = st.date_input("Fin Vigencia", key="poliza_fin")
                        rfc = st.text_input("RFC", value=prospecto_data.get("RFC", ""), key="poliza_rfc")
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
                        telefono = st.text_input("Teléfono", value=prospecto_data.get("Teléfono", ""), key="poliza_telefono")
                        correo = st.text_input("Correo", value=prospecto_data.get("Correo", ""), key="poliza_correo")
                        fecha_nacimiento = st.date_input("Fecha Nacimiento", 
                                                       value=datetime.strptime(prospecto_data.get("Fecha Nacimiento", "01/01/2000"), "%d/%m/%Y") 
                                                       if prospecto_data.get("Fecha Nacimiento") and "/" in prospecto_data.get("Fecha Nacimiento") 
                                                       else datetime(2000, 1, 1),
                                                       key="poliza_fecha_nac")
                    
                    if st.form_submit_button("💾 Agregar Póliza"):
                        if not no_poliza:
                            st.warning("Debe completar el número de póliza")
                        else:
                            # Verificar si ya existe el número de póliza
                            if not df_polizas.empty and str(no_poliza).strip() in df_polizas["No. Póliza"].astype(str).str.strip().values:
                                st.warning("⚠️ Este número de póliza ya existe")
                            else:
                                nueva_poliza = {
                                    "Tipo Persona": prospecto_data.get("Tipo Persona", ""),
                                    "Nombre/Razón Social": prospecto_data.get("Nombre/Razón Social", ""),
                                    "No. Póliza": no_poliza,
                                    "Producto": producto,
                                    "Inicio Vigencia": inicio_vigencia.strftime("%d/%m/%Y"),
                                    "Fin Vigencia": fin_vigencia.strftime("%d/%m/%Y"),
                                    "RFC": rfc,
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
                                    "Teléfono": telefono,
                                    "Correo": correo,
                                    "Fecha Nacimiento": fecha_nacimiento.strftime("%d/%m/%Y")
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
        if not df_polizas.empty:
            clientes_unicos = df_polizas["Nombre/Razón Social"].dropna().unique().tolist()
            cliente_seleccionado = st.selectbox("Seleccionar Cliente", [""] + clientes_unicos, key="cliente_existente")
            
            if cliente_seleccionado:
                # Mostrar pólizas existentes del cliente
                st.subheader(f"Pólizas existentes de {cliente_seleccionado}")
                polizas_cliente = df_polizas[df_polizas["Nombre/Razón Social"] == cliente_seleccionado]
                st.dataframe(polizas_cliente[["No. Póliza", "Producto", "Aseguradora", "Fin Vigencia", "Estado"]], 
                           use_container_width=True)
                
                # Formulario para nueva póliza
                st.subheader("Agregar Nueva Póliza")
                
                with st.form("form_nueva_poliza"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        no_poliza = st.text_input("No. Póliza*", key="nueva_poliza_numero")
                        producto = st.selectbox("Producto", OPCIONES_PRODUCTO, key="nueva_poliza_producto")
                        inicio_vigencia = st.date_input("Inicio Vigencia", key="nueva_poliza_inicio")
                        fin_vigencia = st.date_input("Fin Vigencia", key="nueva_poliza_fin")
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
                    
                    # Botones de acción
                    col_btn1, col_btn2, col_btn3 = st.columns(3)
                    
                    with col_btn1:
                        if st.form_submit_button("💾 Guardar Nueva Póliza"):
                            if not no_poliza:
                                st.warning("Debe completar el número de póliza")
                            else:
                                # Verificar si ya existe el número de póliza
                                if str(no_poliza).strip() in df_polizas["No. Póliza"].astype(str).str.strip().values:
                                    st.warning("⚠️ Este número de póliza ya existe")
                                else:
                                    # Obtener datos básicos del cliente
                                    cliente_data = polizas_cliente.iloc[0]
                                    
                                    nueva_poliza = {
                                        "Tipo Persona": cliente_data.get("Tipo Persona", ""),
                                        "Nombre/Razón Social": cliente_seleccionado,
                                        "No. Póliza": no_poliza,
                                        "Producto": producto,
                                        "Inicio Vigencia": inicio_vigencia.strftime("%d/%m/%Y"),
                                        "Fin Vigencia": fin_vigencia.strftime("%d/%m/%Y"),
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
            st.rerun()
        
        df_vencimientos = obtener_polizas_proximas_vencer(45, 60)
        
        if not df_vencimientos.empty:
            st.success(f"📊 Se encontraron {len(df_vencimientos)} pólizas próximas a vencer")
            
            # Mostrar tabla con estilo condicional
            styled_df = df_vencimientos[["Nombre/Razón Social", "No. Póliza", "Producto", "Fin Vigencia", "Días Restantes"]].copy()
            
            # Aplicar estilo condicional
            def highlight_days(val):
                if val <= 50:
                    return 'background-color: #fff3cd; color: #856404;'
                return ''
            
            styled_df = styled_df.style.applymap(highlight_days, subset=['Días Restantes'])
            
            st.dataframe(styled_df, use_container_width=True)
            
            # Detalles de pólizas seleccionadas
            st.subheader("Detalles de Póliza")
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
            st.info("No hay pólizas que venzan en los próximos 45-60 días")

if __name__ == "__main__":
    main()