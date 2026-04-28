import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
import base64
import os
from PIL import Image
import io
import time
import plotly.express as px

# --- 0. CONFIGURACIÓN ---
st.set_page_config(page_title="Aisaac-Shield Systems", layout="wide")
ZONA_CR = timezone(timedelta(hours=-6)) 

@st.cache_resource
def init_conexion():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_conexion()

# --- 1. UTILIDADES ---
def procesar_foto(uploaded_file):
    img = Image.open(uploaded_file)
    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
    img.thumbnail((800, 800)) 
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=70)
    return base64.b64encode(output.getvalue()).decode()

def get_base64(file_path):
    if file_path and os.path.exists(file_path):
        with open(file_path, "rb") as f: return base64.b64encode(f.read()).decode()
    return None

def generar_pdf_mejorado(df, titulo, total):
    try:
        from fpdf import FPDF
        class PDF(FPDF):
            def header(self):
                ruta_bg = st.secrets.get("APP_REPORT_BG", "fondo_reporte.jpg")
                if os.path.exists(ruta_bg):
                    self.image(ruta_bg, x=0, y=0, w=210, h=297)
                    self.set_fill_color(255, 255, 255)
                    self.set_alpha(0.7)
                    self.rect(0, 0, 210, 297, 'F')
                    self.set_alpha(1)

        pdf = PDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 20)
        pdf.set_text_color(75, 0, 130) 
        pdf.cell(0, 20, txt=titulo, ln=True, align='C')
        pdf.ln(10)
        
        pdf.set_fill_color(75, 0, 130)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(40, 10, "Fecha", 1, 0, 'C', True)
        pdf.cell(100, 10, "Concepto / Detalle", 1, 0, 'C', True)
        pdf.cell(40, 10, "Monto", 1, 1, 'C', True)
        
        pdf.set_text_color(20, 20, 20)
        pdf.set_font("Arial", size=11)
        for i, row in df.iterrows():
            fecha = str(row.get('created_at',''))[:10]
            desc = str(row.get('concepto', row.get('cliente', 'Servicio')))
            monto = f"CRC {row.get('monto', 0):,}"
            pdf.cell(40, 10, fecha, 1)
            pdf.cell(100, 10, desc, 1)
            pdf.cell(40, 10, monto, 1, 1)
            
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 14)
        pdf.set_text_color(16, 124, 65)
        pdf.cell(140, 12, "TOTAL ACUMULADO:", 1, 0, 'R')
        pdf.cell(40, 12, f"CRC {total:,}", 1, 1, 'C')
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except: return b"Error PDF"

def crear_boton_descarga(datos, nombre, texto, color):
    b64 = base64.b64encode(datos).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{nombre}" style="background-color: {color}; color: white; padding: 12px; border-radius: 10px; text-decoration: none; font-weight: bold; display: block; text-align: center; margin-bottom: 15px;">{texto}</a>'

# --- 2. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False
if not st.session_state['autenticado']:
    st.markdown("<h1 style='text-align: center; color: #8A2BE2;'>AISAAC-SHIELD</h1>", unsafe_allow_html=True)
    pin = st.text_input("PIN", type="password")
    if st.button("DESBLOQUEAR"):
        if pin == "8715": st.session_state.update({'autenticado': True, 'user': "dany", 'ver': "Estandar"})
        elif pin == "8742": st.session_state.update({'autenticado': True, 'user': "padre_andres", 'ver': "Premium"})
        else: st.error("PIN Incorrecto")
        if st.session_state['autenticado']: st.rerun()
    st.stop()

u = st.session_state['user']
ver = st.session_state['ver']
color_pri = "#D4AF37" if ver == "Premium" else "#25D366"

st.markdown(f"<div style='border: 2px solid {color_pri}; padding:10px; border-radius:15px; text-align:center;'><h2 style='color:{color_pri};'>{u.upper()} - {ver.upper()}</h2></div>", unsafe_allow_html=True)

tabs = st.tabs(["VIAJES", "GASTOS", "DATOS"])

# --- TAB 1: VIAJES ---
with tabs[0]:
    st.subheader("Registrar Viaje")
    with st.form("f_v"):
        c = st.text_input("Cliente"); m = st.number_input("Monto", step=1); k = st.number_input("KM", step=1)
        if st.form_submit_button("GUARDAR"):
            supabase.table("viajes").insert({"cliente": c, "monto": int(m), "km_actual": int(k), "cliente_id": u}).execute()
            st.success("Guardado"); time.sleep(1); st.rerun()

# --- TAB 2: GASTOS (ENTRADA) ---
with tabs[1]:
    st.subheader("Registrar Gasto")
    with st.form("f_g"):
        t = st.selectbox("Tipo", ["Diesel", "Peaje", "Viaticos", "Otros"])
        mg = st.number_input("Monto", step=1); f = st.file_uploader("Foto", type=['jpg','png'])
        if st.form_submit_button("GUARDAR GASTO"):
            fb64 = procesar_foto(f) if f else None
            supabase.table("gastos").insert({"concepto": t, "monto": int(mg), "cliente_id": u, "foto_comprobante": fb64}).execute()
            st.success("Gasto Guardado"); time.sleep(1); st.rerun()

# --- TAB 3: DATOS (DASHBOARD + LISTADO) ---
with tabs[2]:
    res_v = supabase.table("viajes").select("*").eq("cliente_id", u).execute()
    res_g = supabase.table("gastos").select("*").eq("cliente_id", u).execute()
    df_v = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()
    df_g = pd.DataFrame(res_g.data) if res_g.data else pd.DataFrame()

    col1, col2 = st.columns(2)
    tot_v = df_v['monto'].sum() if not df_v.empty else 0
    tot_g = df_g['monto'].sum() if not df_g.empty else 0
    col1.metric("INGRESOS", f"CRC {tot_v:,}")
    col2.metric("GASTOS", f"CRC {tot_g:,}", delta=f"-{tot_g:,}", delta_color="inverse")

    if not df_g.empty:
        fig = px.bar(df_g.groupby("concepto")["monto"].sum().reset_index(), x="concepto", y="monto", color="concepto", text_auto=True)
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Reportes")
        pdf = generar_pdf_mejorado(df_g, f"REPORTE {u.upper()}", tot_g)
        st.markdown(crear_boton_descarga(pdf, "reporte.pdf", "📄 DESCARGAR PDF PRO", "#DA0B20"), unsafe_allow_html=True)

        st.write("---")
        st.subheader("Historial Detallado (Tus Gastos)")
        for i, row in df_g.iterrows():
            with st.expander(f"{row['concepto']} - CRC {row['monto']:,}"):
                if row.get('foto_comprobante'): st.image(f"data:image/jpeg;base64,{row['foto_comprobante']}")
                if st.button("Eliminar", key=f"del_{row['id']}"):
                    supabase.table("gastos").delete().eq("id", row['id']).execute(); st.rerun()
