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
                # Fondo con opacidad (simulado con imagen clara si existe)
                ruta_bg = st.secrets.get("APP_REPORT_BG", "fondo_reporte.jpg")
                if os.path.exists(ruta_bg):
                    self.image(ruta_bg, x=0, y=0, w=210, h=297) # Ajuste a hoja A4
                    # Capa de "blanqueado" para opacidad
                    self.set_fill_color(255, 255, 255)
                    self.set_alpha(0.7) # Fondo 70% invisible
                    self.rect(0, 0, 210, 297, 'F')
                    self.set_alpha(1)

        pdf = PDF()
        pdf.add_page()
        
        # Título con color fuerte (Morado Aisaac)
        pdf.set_font("Arial", 'B', 20)
        pdf.set_text_color(75, 0, 130) 
        pdf.cell(0, 20, txt=titulo, ln=True, align='C')
        pdf.ln(10)
        
        # Encabezados de tabla
        pdf.set_fill_color(75, 0, 130)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(40, 10, "Fecha", 1, 0, 'C', True)
        pdf.cell(100, 10, "Concepto / Detalle", 1, 0, 'C', True)
        pdf.cell(40, 10, "Monto", 1, 1, 'C', True)
        
        # Datos con color de letra nítido
        pdf.set_text_color(20, 20, 20)
        pdf.set_font("Arial", size=11)
        for i, row in df.iterrows():
            fecha = str(row.get('created_at',''))[:10]
            desc = str(row.get('concepto', row.get('cliente', 'Servicio de Ruta')))
            monto = f"CRC {row.get('monto', 0):,}"
            pdf.cell(40, 10, fecha, 1)
            pdf.cell(100, 10, desc, 1)
            pdf.cell(40, 10, monto, 1, 1)
            
        # Fila de Total (Verde Excel)
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 14)
        pdf.set_text_color(16, 124, 65)
        pdf.cell(140, 12, "TOTAL ACUMULADO:", 1, 0, 'R')
        pdf.cell(40, 12, f"CRC {total:,}", 1, 1, 'C')
        
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except Exception as e:
        return b"Error: Instalar fpdf y subir fondo_reporte.jpg"

def crear_boton_descarga(datos, nombre, texto, color):
    b64 = base64.b64encode(datos).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{nombre}" style="background-color: {color}; color: white; padding: 12px; border-radius: 10px; text-decoration: none; font-weight: bold; display: block; text-align: center; margin-bottom: 15px; border: 1px solid rgba(255,255,255,0.2); box-shadow: 0 4px 15px rgba(0,0,0,0.4);">{texto}</a>'

# --- 2. PANTALLA DE INICIO ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.markdown("""
    <style>
        [data-testid="stHeader"], footer { visibility: hidden; display: none !important; }
        .stApp {
            background-color: #050010;
            background-image: linear-gradient(#4b008240 1px, transparent 1px), linear-gradient(90deg, #4b008240 1px, transparent 1px);
            background-size: 40px 40px;
        }
    </style>
    """, unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #8A2BE2; text-shadow: 0 0 15px #8A2BE2; margin-top: 10vh;'>AISAAC-SHIELD</h1>", unsafe_allow_html=True)
    pin = st.text_input("PIN DE ACCESO", type="password")
    if st.button("DESBLOQUEAR SISTEMA", use_container_width=True):
        if pin == "8715": st.session_state.update({'autenticado': True, 'user': "dany", 'ver': "Estandar"})
        elif pin == "8742": st.session_state.update({'autenticado': True, 'user': "padre_andres", 'ver': "Premium"})
        else: st.error("PIN Incorrecto")
        if st.session_state['autenticado']: st.rerun()
    st.stop()

# --- 3. ESTILO Y TABS ---
u = st.session_state['user']
ver = st.session_state['ver']
color_pri = "#D4AF37" if ver == "Premium" else "#25D366"
label_app = "GOLD SYSTEM" if ver == "Premium" else "RUTAMASTER"

st.markdown(f"<div style='background: rgba(0,0,0,0.8); padding: 15px; border-radius: 15px; border: 2px solid {color_pri}; text-align: center; margin-bottom: 20px; box-shadow: 0 0 15px {color_pri};'><h2 style='margin:0; color:{color_pri};'>{label_app} - {u.upper()}</h2></div>", unsafe_allow_html=True)

tabs = st.tabs(["REGISTRAR VIAJE", "GASTOS", "DATOS"])

# (Lógica de Registro omitida para brevedad, se mantiene igual a tu código previo)

# --- 4. SECCIÓN DATOS (DASHBOARD + PDF TUNING) ---
with tabs[2]:
    st.subheader("Análisis de Operaciones")
    try:
        res_v = supabase.table("viajes").select("*").eq("cliente_id", u).execute()
        res_g = supabase.table("gastos").select("*").eq("cliente_id", u).execute()
        df_v = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()
        df_g = pd.DataFrame(res_g.data) if res_g.data else pd.DataFrame()
        
        c1, c2, c3 = st.columns(3)
        total_viajes = df_v['monto'].sum() if not df_v.empty else 0
        total_gastos = df_g['monto'].sum() if not df_g.empty else 0
        c1.metric("INGRESOS", f"CRC {total_viajes:,}")
        c2.metric("GASTOS", f"CRC {total_gastos:,}")
        c3.metric("BALANCE", f"CRC {total_viajes - total_gastos:,}")

        if not df_g.empty:
            df_sum = df_g.groupby("concepto")["monto"].sum().reset_index()
            fig = px.bar(df_sum, x="concepto", y="monto", color="concepto", text_auto=',.0f', title="Gastos por Categoría")
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color=color_pri)
            st.plotly_chart(fig, use_container_width=True)

        st.write("---")
        st.subheader("Reportes Profesionales")
        cp, cx = st.columns(2)
        with cp:
            if st.button("Generar PDF con Diseño"):
                datos = df_g if not df_g.empty else df_v
                pdf_bytes = generar_pdf_mejorado(datos, f"REPORTE AISAAC-SHIELD: {u.upper()}", total_gastos if not df_g.empty else total_viajes)
                st.markdown(crear_boton_descarga(pdf_bytes, "Reporte_Aisaac_Premium.pdf", "📄 DESCARGAR PDF CON FONDO", "#DA0B20"), unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error: {e}")
