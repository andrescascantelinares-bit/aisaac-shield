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

def generar_pdf_pro(df, titulo, total):
    try:
        from fpdf import FPDF
        class PDF(FPDF):
            def header(self):
                # Fondo de la playa corregido
                if os.path.exists("fondo_reporte.jpg"):
                    self.image("fondo_reporte.jpg", x=0, y=0, w=210, h=297)
                    self.set_fill_color(255, 255, 255)
                    self.set_alpha(0.65) # Opacidad para legibilidad
                    self.rect(0, 0, 210, 297, 'F')
                    self.set_alpha(1)
        
        pdf = PDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 22)
        pdf.set_text_color(75, 0, 130) # Morado Aisaac
        pdf.cell(0, 20, txt=titulo, ln=True, align='C')
        pdf.ln(10)
        
        # Tabla de Datos
        pdf.set_fill_color(75, 0, 130); pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(40, 10, "Fecha", 1, 0, 'C', True)
        pdf.cell(100, 10, "Concepto", 1, 0, 'C', True)
        pdf.cell(40, 10, "Monto", 1, 1, 'C', True)
        
        pdf.set_text_color(30, 30, 30); pdf.set_font("Arial", size=11)
        for _, row in df.iterrows():
            pdf.cell(40, 10, str(row.get('created_at',''))[:10], 1)
            pdf.cell(100, 10, str(row.get('concepto', 'Gasto')), 1)
            pdf.cell(40, 10, f"CRC {row.get('monto', 0):,}", 1, 1)
            
        pdf.ln(5); pdf.set_font("Arial", 'B', 14); pdf.set_text_color(16, 124, 65)
        pdf.cell(140, 12, "TOTAL ACUMULADO:", 1, 0, 'R')
        pdf.cell(40, 12, f"CRC {total:,}", 1, 1, 'C')
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except: return b"Error al generar PDF"

def crear_boton_descarga(datos, nombre, texto, color):
    b64 = base64.b64encode(datos).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{nombre}" style="background-color: {color}; color: white; padding: 12px; border-radius: 10px; text-decoration: none; font-weight: bold; display: block; text-align: center; margin-bottom: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.3);">{texto}</a>'

# --- 2. ACCESO ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False
if not st.session_state['autenticado']:
    st.markdown("<h1 style='text-align: center; color: #8A2BE2;'>AISAAC-SHIELD</h1>", unsafe_allow_html=True)
    pin = st.text_input("PIN DE SEGURIDAD", type="password")
    if st.button("DESBLOQUEAR SISTEMA"):
        if pin == "8715": st.session_state.update({'autenticado': True, 'user': "dany", 'ver': "Estandar"})
        elif pin == "8742": st.session_state.update({'autenticado': True, 'user': "padre_andres", 'ver': "Premium"})
        else: st.error("PIN Incorrecto")
        if st.session_state['autenticado']: st.rerun()
    st.stop()

# --- 3. INTERFAZ ---
u = st.session_state['user']
ver = st.session_state['ver']
color_pri = "#D4AF37" if ver == "Premium" else "#25D366"

# Header con Logo del Usuario
c_logo, c_tit = st.columns([1, 5])
with c_logo:
    if os.path.exists("logo.png"): st.image("logo.png", width=120)
with c_tit:
    st.markdown(f"<div style='border: 2px solid {color_pri}; padding:10px; border-radius:15px; text-align:center; background: rgba(0,0,0,0.8);'><h2 style='color:{color_pri}; margin:0;'>{u.upper()} - {ver.upper()}</h2></div>", unsafe_allow_html=True)

tabs = st.tabs(["REGISTRAR VIAJE", "GASTOS", "DATOS"])

with tabs[0]: # Registro de Viajes
    st.subheader("Registrar Finalización de Ruta")
    with st.form("f_v"):
        cli = st.text_input("Cliente"); mon = st.number_input("Monto", step=1); km = st.number_input("KM Llegada", step=1)
        if st.form_submit_button("GUARDAR"):
            supabase.table("viajes").insert({"cliente": cli, "monto": int(mon), "km_actual": int(km), "cliente_id": u}).execute()
            st.success("Sincronizado"); time.sleep(1); st.rerun()

with tabs[1]: # Registro de Gastos
    st.subheader("Registrar Gasto de Operación")
    with st.form("f_g"):
        tipo = st.selectbox("Tipo de Gasto", ["Diesel", "Peaje", "Viaticos", "Repuestos", "Mantenimiento", "Otros"])
        mg = st.number_input("Monto (CRC)", step=1); f = st.file_uploader("Foto del Recibo", type=['jpg','png','jpeg'])
        if st.form_submit_button("GUARDAR GASTO"):
            fb64 = procesar_foto(f) if f else None
            supabase.table("gastos").insert({"concepto": tipo, "monto": int(mg), "cliente_id": u, "foto_comprobante": fb64}).execute()
            st.success("Guardado con éxito"); time.sleep(1); st.rerun()

with tabs[2]: # Dashboard e Historial
    res_v = supabase.table("viajes").select("*").eq("cliente_id", u).execute()
    res_g = supabase.table("gastos").select("*").eq("cliente_id", u).execute()
    df_v = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()
    df_g = pd.DataFrame(res_g.data) if res_g.data else pd.DataFrame()

    col1, col2, col3 = st.columns(3)
    t_v = df_v['monto'].sum() if not df_v.empty else 0
    t_g = df_g['monto'].sum() if not df_g.empty else 0
    col1.metric("INGRESOS", f"CRC {t_v:,}")
    col2.metric("GASTOS", f"CRC {t_g:,}", delta=f"-{t_g:,}", delta_color="inverse")
    col3.metric("NETO", f"CRC {t_v - t_g:,}")

    if not df_g.empty:
        st.plotly_chart(px.bar(df_g.groupby("concepto")["monto"].sum().reset_index(), x="concepto", y="monto", color="concepto", text_auto=True), use_container_width=True)
        
        st.subheader("Descargas")
        d_pdf, d_xls = st.columns(2)
        with d_pdf:
            pdf = generar_pdf_pro(df_g, f"REPORTE AISAAC-SHIELD: {u.upper()}", t_g)
            st.markdown(crear_boton_descarga(pdf, "Reporte.pdf", "📄 PDF PRO CON FONDO", "#DA0B20"), unsafe_allow_html=True)
        with d_xls:
            # Excel Limpio: Sin código de fotos
            df_limpio = df_g.drop(columns=['foto_comprobante'], errors='ignore')
            csv = df_limpio.to_csv(index=False).encode('utf-8')
            st.markdown(crear_boton_descarga(csv, "Gastos.csv", "📥 EXCEL (CSV)", "#107C41"), unsafe_allow_html=True)

        st.write("---")
        st.subheader("Historial Detallado")
        for i, row in df_g.iterrows():
            with st.expander(f"{row['concepto']} - CRC {row['monto']:,}"):
                if row.get('foto_comprobante'): st.image(f"data:image/jpeg;base64,{row['foto_comprobante']}")
                if st.button("Eliminar Registro", key=f"del_{row['id']}"):
                    supabase.table("gastos").delete().eq("id", row['id']).execute(); st.rerun()

st.markdown(f"<div style='text-align: center; color: {color_pri}; margin-top: 50px; opacity: 0.5;'>AISAAC-SHIELD PROTECTED</div>", unsafe_allow_html=True)
