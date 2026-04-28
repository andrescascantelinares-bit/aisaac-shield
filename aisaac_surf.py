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

# --- 0. CONFIGURACION ---
st.set_page_config(page_title="Aisaac-Shield Systems", layout="wide")
ZONA_CR = timezone(timedelta(hours=-6)) 

@st.cache_resource
def init_conexion():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_conexion()

# --- 1. UTILIDADES MAESTRAS ---
def procesar_foto(uploaded_file):
    img = Image.open(uploaded_file)
    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
    img.thumbnail((800, 800)) 
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=70)
    return base64.b64encode(output.getvalue()).decode()

def obtener_ruta_exacta(nombre_archivo):
    # Primero intentamos en la carpeta donde esta el script
    ruta_script = os.path.dirname(os.path.abspath(__file__))
    ruta_completa = os.path.join(ruta_script, nombre_archivo)
    
    if os.path.exists(ruta_completa):
        return ruta_completa
    
    # Si no, intentamos en el directorio de trabajo actual
    ruta_cwd = os.path.join(os.getcwd(), nombre_archivo)
    if os.path.exists(ruta_cwd):
        return ruta_cwd
        
    return None

def generar_pdf_pro(df, titulo, total):
    try:
        from fpdf import FPDF
        class PDF(FPDF):
            def header(self):
                # BUSQUEDA DEL FONDO ESPECIFICO
                ruta_bg = obtener_ruta_exacta("fondo_reporte.jpg.jpg")
                if ruta_bg:
                    try:
                        self.image(ruta_bg, x=0, y=0, w=210, h=297)
                        # Capa blanca semi-transparente para legibilidad
                        self.set_fill_color(255, 255, 255)
                        # Nota: fpdf2 maneja transparencias con set_alpha
                        try:
                            self.set_alpha(0.7)
                            self.rect(0, 0, 210, 297, 'F')
                            self.set_alpha(1)
                        except:
                            pass
                    except Exception as e:
                        self.set_text_color(200, 0, 0)
                        self.cell(0, 10, f"Error de imagen: {str(e)[:30]}", ln=True)
                else:
                    self.set_text_color(255, 0, 0)
                    self.set_font("Arial", 'B', 10)
                    self.cell(0, 10, "SISTEMA: Archivo 'fondo_reporte.jpg.jpg' no encontrado.", ln=True)
        
        pdf = PDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 22)
        pdf.set_text_color(75, 0, 130)
        pdf.cell(0, 20, txt=titulo, ln=True, align='C')
        pdf.ln(10)
        
        # Encabezados de tabla
        pdf.set_fill_color(75, 0, 130); pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(40, 10, "Fecha", 1, 0, 'C', True)
        pdf.cell(100, 10, "Concepto", 1, 0, 'C', True)
        pdf.cell(40, 10, "Monto", 1, 1, 'C', True)
        
        # Datos
        pdf.set_text_color(30, 30, 30); pdf.set_font("Arial", size=11)
        for _, row in df.iterrows():
            pdf.cell(40, 10, str(row.get('created_at',''))[:10], 1)
            pdf.cell(100, 10, str(row.get('concepto', 'Gasto')), 1)
            pdf.cell(40, 10, f"CRC {row.get('monto', 0):,}", 1, 1)
            
        pdf.ln(5); pdf.set_font("Arial", 'B', 14); pdf.set_text_color(16, 124, 65)
        pdf.cell(140, 12, "TOTAL ACUMULADO:", 1, 0, 'R')
        pdf.cell(40, 12, f"CRC {total:,}", 1, 1, 'C')
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except Exception as e:
        return f"Error critico PDF: {str(e)}".encode('latin-1')

def crear_boton_descarga(datos, nombre, texto, color):
    b64 = base64.b64encode(datos).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{nombre}" style="background-color: {color}; color: white; padding: 12px; border-radius: 10px; text-decoration: none; font-weight: bold; display: block; text-align: center; margin-bottom: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.3);">{texto}</a>'

# --- 2. LOGIN (PIN 8715 / 8742) ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False
if not st.session_state['autenticado']:
    st.markdown("<h1 style='text-align: center; color: #8A2BE2;'>AISAAC-SHIELD</h1>", unsafe_allow_html=True)
    pin = st.text_input("PIN DE ACCESO", type="password")
    if st.button("ACCEDER"):
        if pin == "8715": st.session_state.update({'autenticado': True, 'user': "dany", 'ver': "Estandar"})
        elif pin == "8742": st.session_state.update({'autenticado': True, 'user': "andres", 'ver': "Premium"})
        else: st.error("PIN Incorrecto")
        if st.session_state['autenticado']: st.rerun()
    st.stop()

# --- 3. INTERFAZ ---
u = st.session_state['user']
ver = st.session_state['ver']
color_pri = "#D4AF37" if ver == "Premium" else "#25D366"

# Logo e Identificacion
c_logo, c_tit = st.columns([1, 5])
with c_logo:
    ruta_logo = obtener_ruta_exacta("logo.png")
    if ruta_logo: st.image(ruta_logo, width=120)

with c_tit:
    st.markdown(f"<div style='border: 2px solid {color_pri}; padding:10px; border-radius:15px; text-align:center; background: rgba(0,0,0,0.8);'><h2 style='color:{color_pri}; margin:0;'>{u.upper()} - {ver.upper()}</h2></div>", unsafe_allow_html=True)

tabs = st.tabs(["VIAJES", "GASTOS", "DATOS"])

with tabs[1]: # Seccion de Gastos
    with st.form("f_g", clear_on_submit=True):
        t = st.selectbox("Concepto", ["Diesel", "Peaje", "Repuestos", "Otros"])
        mg = st.number_input("Monto (CRC)", step=1)
        f = st.file_uploader("Foto Comprobante", type=['jpg','png'])
        if st.form_submit_button("GUARDAR"):
            fb64 = procesar_foto(f) if f else None
            supabase.table("gastos").insert({"concepto": t, "monto": int(mg), "cliente_id": u, "foto_comprobante": fb64}).execute()
            st.success("Guardado"); st.rerun()

with tabs[2]: # Visualizacion y PDF
    res_g = supabase.table("gastos").select("*").eq("cliente_id", u).execute()
    df_g = pd.DataFrame(res_g.data) if res_g.data else pd.DataFrame()

    if not df_g.empty:
        total_g = df_g['monto'].sum()
        st.metric("TOTAL GASTOS", f"CRC {total_g:,}")
        
        # Boton de Descarga con el Fondo Corregido
        pdf = generar_pdf_pro(df_g, f"REPORTE OPERATIVO: {u.upper()}", total_g)
        st.markdown(crear_boton_descarga(pdf, "Reporte_Aisaac.pdf", "📄 GENERAR PDF CON FONDO", "#DA0B20"), unsafe_allow_html=True)
        
        st.write("---")
        for i, row in df_g.iterrows():
            with st.expander(f"{row['concepto']} - CRC {row['monto']:,}"):
                if row.get('foto_comprobante'): st.image(f"data:image/jpeg;base64,{row['foto_comprobante']}")
