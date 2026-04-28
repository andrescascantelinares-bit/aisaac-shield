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

# --- 1. UTILIDADES MAESTRAS ---
def procesar_foto(uploaded_file):
    img = Image.open(uploaded_file)
    if img.mode in ("RGBA", "P"): img = img.convert("RGB")
    img.thumbnail((800, 800)) 
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=70)
    return base64.b64encode(output.getvalue()).decode()

def buscar_archivo_fondo():
    # Busca cualquier variante del nombre para evitar errores de extension
    posibles = ["fondo_reporte.jpg", "fondo_reporte.jpg.jpg", "fondo_reporte.jpeg"]
    for p in posibles:
        if os.path.exists(p): return p
    return None

def generar_pdf_pro(df, titulo, total):
    try:
        from fpdf import FPDF
        class PDF(FPDF):
            def header(self):
                bg = buscar_archivo_fondo()
                if bg:
                    self.image(bg, x=0, y=0, w=210, h=297)
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
    except: return b"Error PDF"

def crear_boton_descarga(datos, nombre, texto, color):
    b64 = base64.b64encode(datos).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{nombre}" style="background-color: {color}; color: white; padding: 12px; border-radius: 10px; text-decoration: none; font-weight: bold; display: block; text-align: center; margin-bottom: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.3); border: none;">{texto}</a>'

# --- 2. MOTOR DE IA ---
def motor_ia_analisis(df_g, df_v):
    if df_g.empty: return "SISTEMA: Datos insuficientes para analisis."
    t_g = df_g['monto'].sum()
    por_cat = df_g.groupby('concepto')['monto'].sum()
    max_c = por_cat.idxmax()
    res = [f"ESTRUCTURA: El gasto dominante es {max_c.upper()} ({ (por_cat.max()/t_g)*100 :.1f}%)."]
    if not df_v.empty:
        t_v = df_v['monto'].sum()
        margen = ((t_v - t_g) / t_v) * 100 if t_v > 0 else 0
        res.append(f"RENTABILIDAD: Margen neto calculado del {margen:.1f}%.")
    return "<br><br>".join(res)

# --- 3. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False
if not st.session_state['autenticado']:
    st.markdown("<h1 style='text-align: center; color: #8A2BE2;'>AISAAC-SHIELD</h1>", unsafe_allow_html=True)
    pin = st.text_input("PIN DE ACCESO", type="password")
    if st.button("ACCEDER"):
        if pin == "8715": st.session_state.update({'autenticado': True, 'user': "dany", 'ver': "Estandar"})
        elif pin == "8742": st.session_state.update({'autenticado': True, 'user': "padre_andres", 'ver': "Premium"})
        else: st.error("PIN Incorrecto")
        if st.session_state['autenticado']: st.rerun()
    st.stop()

# --- 4. INTERFAZ ---
u = st.session_state['user']
ver = st.session_state['ver']
color_pri = "#D4AF37" if ver == "Premium" else "#25D366"

if os.path.exists("logo.png"): st.image("logo.png", width=120)
st.markdown(f"<div style='border: 2px solid {color_pri}; padding:10px; border-radius:15px; text-align:center; background: rgba(0,0,0,0.8);'><h2 style='color:{color_pri}; margin:0;'>{u.upper()} - {ver.upper()}</h2></div>", unsafe_allow_html=True)

tabs = st.tabs(["REGISTRAR VIAJE", "GASTOS", "DATOS"])

with tabs[0]: # Registro Viajes
    with st.form("f_v", clear_on_submit=True):
        cli = st.text_input("Cliente"); mon = st.number_input("Monto", step=1); km = st.number_input("KM", step=1)
        if st.form_submit_button("GUARDAR VIAJE"):
            supabase.table("viajes").insert({"cliente": cli, "monto": int(mon), "km_actual": int(km), "cliente_id": u}).execute()
            st.success("Sincronizado"); st.rerun()

with tabs[1]: # Registro Gastos
    with st.form("f_g", clear_on_submit=True):
        tipo = st.selectbox("Concepto", ["Diesel", "Peaje", "Viaticos", "Repuestos", "Otros"])
        mg = st.number_input("Monto", step=1); f = st.file_uploader("Foto", type=['jpg','png'])
        if st.form_submit_button("REGISTRAR GASTO"):
            fb64 = procesar_foto(f) if f else None
            supabase.table("gastos").insert({"concepto": tipo, "monto": int(mg), "cliente_id": u, "foto_comprobante": fb64}).execute()
            st.success("Guardado"); st.rerun()

with tabs[2]: # Dashboard e Historial
    res_v = supabase.table("viajes").select("*").eq("cliente_id", u).execute()
    res_g = supabase.table("gastos").select("*").eq("cliente_id", u).execute()
    df_v = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()
    df_g = pd.DataFrame(res_g.data) if res_g.data else pd.DataFrame()

    t_v = df_v['monto'].sum() if not df_v.empty else 0
    t_g = df_g['monto'].sum() if not df_g.empty else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("INGRESOS", f"CRC {t_v:,}")
    c2.metric("GASTOS", f"CRC {t_g:,}")
    c3.metric("NETO", f"CRC {t_v - t_g:,}")

    if st.button("ANALIZAR CON IA"):
        st.markdown(f"<div style='border: 1px solid #8A2BE2; padding: 15px; border-radius: 10px;'>{motor_ia_analisis(df_g, df_v)}</div>", unsafe_allow_html=True)

    if not df_g.empty:
        st.plotly_chart(px.bar(df_g.groupby("concepto")["monto"].sum().reset_index(), x="concepto", y="monto", color="concepto"), use_container_width=True)
        
        st.subheader("Exportar")
        d_p, d_x = st.columns(2)
        with d_p:
            pdf_b = generar_pdf_pro(df_g, f"REPORTE {u.upper()}", t_g)
            st.markdown(crear_boton_descarga(pdf_b, "Reporte.pdf", "📄 DESCARGAR PDF", "#DA0B20"), unsafe_allow_html=True)
        with d_x:
            # EXCEL RECUPERADO Y LIMPIO
            df_xl = df_g.drop(columns=['foto_comprobante'], errors='ignore')
            csv = df_xl.to_csv(index=False).encode('utf-8')
            st.markdown(crear_boton_descarga(csv, "Gastos.csv", "📥 DESCARGAR EXCEL", "#107C41"), unsafe_allow_html=True)

        st.write("---")
        st.subheader("Historial Detallado")
        for i, row in df_g.iterrows():
            with st.expander(f"{row['concepto']} - CRC {row['monto']:,}"):
                if row.get('foto_comprobante'): st.image(f"data:image/jpeg;base64,{row['foto_comprobante']}")
                if st.button("Eliminar", key=f"del_{row['id']}"):
                    supabase.table("gastos").delete().eq("id", row['id']).execute(); st.rerun()

st.markdown(f"<div style='text-align: center; color: {color_pri}; margin-top: 50px; opacity: 0.5;'>AISAAC-SHIELD PROTECTED</div>", unsafe_allow_html=True)
