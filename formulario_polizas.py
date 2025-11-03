# -*- coding: utf-8 -*-
"""
Updated version of form.py with:
- Automatic field population when selecting a prospect to edit.
- Improved cobranza calculation logic (wider date window, better float parsing, fixed filtering).
"""

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import re

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestor de Pólizas EALC", page_icon="📊", layout="wide")

OPCIONES_PERSONA = ["MORAL", "FÍSICA"]
OPCIONES_PRODUCTO = ["GMMI", "GMMC", "API", "APE", "APC", "VPL", "OV", "PPR", "EDUCACIONAL", "AHORRO", "TEMPORAL", "VG", "AUTO", "FLOTILLA", "HOGAR", "VIAJERO", "DAÑOS", "PENDIENTE"]
OPCIONES_PAGO = ["PAGO REFERENCIADO", "TRANSFERENCIA", "CARGO TDC", "CARGO TDD"]
OPCIONES_MONEDA = ["MXN", "UDIS", "DLLS"]
OPCIONES_ASEG = ["AXA", "ALLIANZ", "ATLAS", "BANORTE", "ZURICH", "GNP", "HIR", "QUALITAS"]

# --- AUTENTICACIÓN GOOGLE SHEETS ---
@st.cache_resource(ttl=3600)
def init_google_sheets():
    if 'google_service_account' not in st.secrets:
        st.error("❌ No se encontró 'google_service_account' en los secrets de Streamlit")
        return None
    creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return gspread.authorize(creds)

client = init_google_sheets()
if client is None:
    st.stop()

@st.cache_resource(ttl=3600)
def conectar_google_sheets():
    try:
        return client.open("base_polizas_ealc")
    except Exception as e:
        st.error(f"❌ Error al conectar con Google Sheets: {e}")
        return None

# --- FUNCIONES AUXILIARES ---
def fecha_actual():
    return datetime.now().strftime("%d/%m/%Y")

def validar_fecha(f):
    if not f: return True, ""
    try:
        datetime.strptime(f, "%d/%m/%Y")
        return True, ""
    except:
        return False, "Formato incorrecto (dd/mm/yyyy)"

# --- CARGA Y GUARDADO ---
@st.cache_data(ttl=300)
def cargar_datos():
    s = conectar_google_sheets()
    if not s:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        p = pd.DataFrame(s.worksheet("Prospectos").get_all_records())
    except: p = pd.DataFrame()
    try:
        pol = pd.DataFrame(s.worksheet("Polizas").get_all_records())
    except: pol = pd.DataFrame()
    try:
        c = pd.DataFrame(s.worksheet("Cobranza").get_all_records())
    except: c = pd.DataFrame()
    return p, pol, c

def guardar_datos(df_prospectos=None, df_polizas=None, df_cobranza=None):
    s = conectar_google_sheets()
    if not s: return False
    if df_prospectos is not None:
        ws = s.worksheet("Prospectos"); ws.clear()
        data = [df_prospectos.columns.tolist()] + df_prospectos.fillna('').values.tolist()
        ws.update(data, value_input_option='USER_ENTERED')
    if df_polizas is not None:
        ws = s.worksheet("Polizas"); ws.clear()
        data = [df_polizas.columns.tolist()] + df_polizas.fillna('').values.tolist()
        ws.update(data, value_input_option='USER_ENTERED')
    if df_cobranza is not None:
        ws = s.worksheet("Cobranza"); ws.clear()
        data = [df_cobranza.columns.tolist()] + df_cobranza.fillna('').values.tolist()
        ws.update(data, value_input_option='USER_ENTERED')
    st.cache_data.clear()
    return True

# --- COBRANZA MEJORADA ---
def calcular_cobranza():
    try:
        _, df_polizas, df_cobranza = cargar_datos()
        if df_polizas.empty: return pd.DataFrame()
        df_vigentes = df_polizas[df_polizas["Estado"].str.upper() == "VIGENTE"]
        if df_vigentes.empty: return pd.DataFrame()

        hoy = datetime.now(); limite = hoy + timedelta(days=30)
        cobranza = []
        for _, p in df_vigentes.iterrows():
            no = str(p.get("No. Póliza", "")).strip()
            per = str(p.get("Periodicidad", "MENSUAL")).upper().strip()
            monto = p.get("Monto Periodo", p.get("Prima Neta", 0))
            f0 = p.get("Inicio Vigencia", "")
            if not no or not f0: continue
            try:
                f0 = datetime.strptime(f0, "%d/%m/%Y")
            except: continue
            freq = {"MENSUAL":1, "TRIMESTRAL":3, "SEMESTRAL":6, "ANUAL":12}.get(per, 1)
            for i in range(0,13):
                fx = f0 + relativedelta(months=i*freq)
                if hoy - timedelta(days=10) <= fx <= limite:
                    mes = fx.strftime("%m/%Y")
                    existe = not df_cobranza.empty and ((df_cobranza["No. Póliza"].astype(str)==no)&(df_cobranza["Mes Cobranza"]==mes)).any()
                    if not existe:
                        dias = (fx - hoy).days
                        cobranza.append({
                            "No. Póliza": no,
                            "Nombre/Razón Social": p.get("Nombre/Razón Social", ""),
                            "Mes Cobranza": mes,
                            "Fecha Vencimiento": fx.strftime("%d/%m/%Y"),
                            "Monto Esperado": float(str(monto).replace(',','').replace('$','') or 0),
                            "Monto Pagado": 0,
                            "Fecha Pago": "",
                            "Estatus": "Pendiente",
                            "Días Restantes": dias
                        })
                    break
        return pd.DataFrame(cobranza)
    except Exception as e:
        st.error(f"Error en cálculo de cobranza: {e}")
        return pd.DataFrame()

# --- PROSPECTOS ---
def mostrar_prospectos(df_prospectos, df_polizas):
    st.header("Gestión de Prospectos")
    if 'modo_edicion' not in st.session_state: st.session_state.modo_edicion = False
    if 'prospecto_editando' not in st.session_state: st.session_state.prospecto_editando = None

    if not df_prospectos.empty:
        lista = df_prospectos["Nombre/Razón Social"].dropna().tolist()
        prospecto_sel = st.selectbox("Seleccionar Prospecto para editar", [""]+lista)
        if prospecto_sel and st.session_state.prospecto_editando != prospecto_sel:
            st.session_state.prospecto_editando = prospecto_sel
            st.session_state.modo_edicion = True
            st.rerun()
        prospecto_data = df_prospectos[df_prospectos["Nombre/Razón Social"]==st.session_state.prospecto_editando].iloc[0] if st.session_state.modo_edicion else {}
    else:
        prospecto_data = {}

    if st.session_state.modo_edicion:
        if st.button("❌ Cancelar Edición"): st.session_state.modo_edicion=False; st.session_state.prospecto_editando=None; st.rerun()

    with st.form("form_prospecto", clear_on_submit=not st.session_state.modo_edicion):
        col1, col2 = st.columns(2)
        with col1:
            tipo = st.selectbox("Tipo Persona", OPCIONES_PERSONA, index=OPCIONES_PERSONA.index(prospecto_data.get("Tipo Persona","")) if prospecto_data.get("Tipo Persona") in OPCIONES_PERSONA else 0)
            nombre = st.text_input("Nombre/Razón Social", value=prospecto_data.get("Nombre/Razón Social", ""))
            nacimiento = st.text_input("Fecha Nacimiento (dd/mm/yyyy)", value=prospecto_data.get("Fecha Nacimiento", ""))
            rfc = st.text_input("RFC", value=prospecto_data.get("RFC", ""))
            tel = st.text_input("Teléfono", value=prospecto_data.get("Teléfono", ""))
            correo = st.text_input("Correo", value=prospecto_data.get("Correo", ""))
        with col2:
            prod = st.selectbox("Producto", OPCIONES_PRODUCTO, index=OPCIONES_PRODUCTO.index(prospecto_data.get("Producto","")) if prospecto_data.get("Producto") in OPCIONES_PRODUCTO else 0)
            f_reg = st.text_input("Fecha Registro", value=prospecto_data.get("Fecha Registro", fecha_actual()))
            f_cont = st.text_input("Fecha Contacto", value=prospecto_data.get("Fecha Contacto", ""))
            seg = st.text_input("Seguimiento", value=prospecto_data.get("Seguimiento", ""))
            rep = st.text_area("Representantes Legales", value=prospecto_data.get("Representantes Legales", ""))
            ref = st.text_input("Referenciador", value=prospecto_data.get("Referenciador", ""))

        sub = st.form_submit_button("💾 Guardar")
        if sub:
            nuevo = {"Tipo Persona":tipo, "Nombre/Razón Social":nombre, "Fecha Nacimiento":nacimiento, "RFC":rfc, "Teléfono":tel, "Correo":correo, "Producto":prod, "Fecha Registro":f_reg, "Fecha Contacto":f_cont, "Seguimiento":seg, "Representantes Legales":rep, "Referenciador":ref}
            if st.session_state.modo_edicion:
                idx = df_prospectos[df_prospectos["Nombre/Razón Social"]==st.session_state.prospecto_editando].index
                for k,v in nuevo.items(): df_prospectos.loc[idx,k]=v
            else:
                df_prospectos = pd.concat([df_prospectos, pd.DataFrame([nuevo])], ignore_index=True)
            if guardar_datos(df_prospectos=df_prospectos, df_polizas=df_polizas): st.success("✅ Guardado correctamente"); st.rerun()

    st.subheader("Lista de Prospectos")
    if not df_prospectos.empty: st.dataframe(df_prospectos, use_container_width=True)
    else: st.info("No hay prospectos registrados")

# --- MAIN ---
def main():
    st.title("📊 Gestor de Prospectos y Pólizas EALC")
    df_p, df_pol, df_cob = cargar_datos()
    tabs = ["👥 Prospectos", "💰 Cobranza"]
    sel = st.tabs(tabs)
    with sel[0]: mostrar_prospectos(df_p, df_pol)
    with sel[1]:
        st.header("💰 Cobranza (Próximos 30 días)")
        df_c = calcular_cobranza()
        if not df_c.empty:
            st.dataframe(df_c, use_container_width=True)
        else:
            st.info("No hay registros de cobranza próximos")

if __name__ == "__main__":
    main()
