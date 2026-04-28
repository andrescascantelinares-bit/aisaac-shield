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
                if os.path.exists("fondo_reporte.jpg"):
                    self.image("fondo_reporte.jpg", x=0, y=0, w=210, h=297)
                    self.set_fill_color(255, 255, 255)
                    self.set_alpha(0.65)
                    self.rect(0, 0, 210, 297, 'F')
                    self.set_alpha(1)
        pdf = PDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 22)
        pdf.set_text_color(75, 0, 130)
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
        pdf.cell(140, 12, "TOTAL:", 1, 0, 'R')
        pdf.cell(40, 12, f"CRC {total:,}", 1, 1, 'C')
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except: return b"Error PDF"

def crear_boton_descarga(datos, nombre, texto, color):
    b64 = base64.b64encode(datos).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{nombre}" style="background-color: {color}; color: white; padding: 12px; border-radius: 10px; text-decoration: none; font-weight: bold; display: block; text-align: center; margin-bottom: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.3);">{texto}</a>'

# --- 2. MOTOR DE IA INTERACTIVO (SIN EMOJIS) ---
def motor_ia_analisis(df_gastos, df_viajes):
    if df_gastos.empty: return "SISTEMA: Es necesario registrar operaciones para iniciar el análisis."
    
    total_g = df_gastos['monto'].sum()
    diesel = df_gastos[df_gastos['concepto'] == 'Diesel']['monto'].sum()
    
    consejos = []
    if diesel > (total_g * 0.4):
        consejos.append(f"ALERTA DE COMBUSTIBLE: Los gastos en Diesel representan el {int((diesel/total_g)*100)}% del total. Se recomienda evaluar la eficiencia de las rutas actuales.")
    
    if not df_viajes.empty:
        ingresos = df_viajes['monto'].sum()
        if ingresos < total_g:
            consejos.append("ALERTA DE BALANCE: Los costos operativos superan los ingresos generados. Es necesario realizar un ajuste en las tarifas de servicio o reducir gastos.")
        else:
            consejos.append("ESTADO OPERATIVO: Rendimiento estable. Los ingresos cubren los costos operativos.")

    consejos.append("MANTENIMIENTO PREVENTIVO: Se sugiere verificar la presión de los neumáticos semanalmente para optimizar el consumo de combustible hasta en un 3%.")
    return "\n\n".join(consejos)

# --- 3. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False
if not st.session_state['autenticado']:
    st.markdown("<h1 style='text-align: center; color: #8A2BE2;'>AISAAC-SHIELD</h1>", unsafe_allow_html=True)
    pin = st.text_input("PIN DE ACCESO", type="password")
    if st.button("ACCEDER AL SISTEMA"):
        if pin == "8715": st.session_state.update({'autenticado': True, 'user': "dany", 'ver': "Estandar"})
        elif pin == "8742": st.session_state.update({'autenticado': True, 'user': "padre_andres", 'ver': "Premium"})
        else: st.error("PIN Incorrecto")
        if st.session_state['autenticado']: st.rerun()
    st.stop()

# --- 4. INTERFAZ PRINCIPAL ---
u = st.session_state['user']
ver = st.session_state['ver']
color_pri = "#D4AF37" if ver == "Premium" else "#25D366"

c_logo, c_tit = st.columns([1, 5])
with c_logo:
    if os.path.exists("logo.png"): st.image("logo.png", width=130)
with c_tit:
    st.markdown(f"<div style='border: 2px solid {color_pri}; padding:10px; border-radius:15px; text-align:center; background: rgba(0,0,0,0.8);'><h2 style='color:{color_pri}; margin:0;'>{u.upper()} - {ver.upper()}</h2></div>", unsafe_allow_html=True)

tabs = st.tabs(["REGISTRAR VIAJE", "GASTOS", "DATOS"])

with tabs[0]:
    with st.form("f_v", clear_on_submit=True):
        cli = st.text_input("Cliente / Empresa")
        mon = st.number_input("Monto (CRC)", step=1); km = st.number_input("Kilometraje", step=1)
        if st.form_submit_button("GUARDAR VIAJE"):
            supabase.table("viajes").insert({"cliente": cli, "monto": int(mon), "km_actual": int(km), "cliente_id": u}).execute()
            st.success("Registro Sincronizado"); st.rerun()

with tabs[1]:
    with st.form("f_g", clear_on_submit=True):
        tipo = st.selectbox("Concepto", ["Diesel", "Peaje", "Viaticos", "Repuestos", "Otros"])
        mg = st.number_input("Monto (CRC)", step=1); f = st.file_uploader("Adjuntar Comprobante", type=['jpg','png'])
        if st.form_submit_button("REGISTRAR GASTO"):
            fb64 = procesar_foto(f) if f else None
            supabase.table("gastos").insert({"concepto": tipo, "monto": int(mg), "cliente_id": u, "foto_comprobante": fb64}).execute()
            st.success("Registro Guardado"); st.rerun()

with tabs[2]:
    res_v = supabase.table("viajes").select("*").eq("cliente_id", u).execute()
    res_g = supabase.table("gastos").select("*").eq("cliente_id", u).execute()
    df_v = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()
    df_g = pd.DataFrame(res_g.data) if res_g.data else pd.DataFrame()

    t_v = df_v['monto'].sum() if not df_v.empty else 0
    t_g = df_g['monto'].sum() if not df_g.empty else 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("TOTAL INGRESOS", f"CRC {t_v:,}")
    col2.metric("TOTAL GASTOS", f"CRC {t_g:,}")
    col3.metric("BALANCE NETO", f"CRC {t_v - t_g:,}")

    # --- MÓDULO DE IA (SOBRIO Y TÉCNICO) ---
    st.write("---")
    st.subheader("Análisis Estratégico Aisaac-AI")
    
    if st.button("SOLICITAR ANÁLISIS DE DATOS"):
        with st.spinner("Procesando información de la base de datos..."):
            time.sleep(2)
            st.markdown(f"""
            <div style='background: rgba(138, 43, 226, 0.15); border: 2px solid #8A2BE2; padding: 20px; border-radius: 15px; box-shadow: 0 0 10px #8A2BE240;'>
                <strong>REPORTE DE SISTEMA:</strong><br><br>
                {motor_ia_analisis(df_g, df_v).replace(chr(10), '<br>')}
            </div>
            """, unsafe_allow_html=True)

    if not df_g.empty:
        st.plotly_chart(px.bar(df_g.groupby("concepto")["monto"].sum().reset_index(), x="concepto", y="monto", color="concepto"), use_container_width=True)
        
        st.subheader("Exportar Documentación")
        d_pdf, d_xls = st.columns(2)
        with d_pdf:
            pdf = generar_pdf_pro(df_g, f"REPORTE {u.upper()}", t_g)
            st.markdown(crear_boton_descarga(pdf, "Reporte.pdf", "DESCARGAR DOCUMENTO PDF", "#DA0B20"), unsafe_allow_html=True)
        with d_xls:
            df_excel = df_g.drop(columns=['foto_comprobante'], errors='ignore')
            csv = df_excel.to_csv(index=False).encode('utf-8')
            st.markdown(crear_boton_descarga(csv, "Gastos.csv", "DESCARGAR FORMATO EXCEL", "#107C41"), unsafe_allow_html=True)

        st.write("---")
        st.subheader("Historial de Comprobantes")
        for i, row in df_g.iterrows():
            with st.expander(f"{row['concepto']} - CRC {row['monto']:,}"):
                if row.get('foto_comprobante'): st.image(f"data:image/jpeg;base64,{row['foto_comprobante']}")
                if st.button("Eliminar Registro", key=f"del_{row['id']}"):
                    supabase.table("gastos").delete().eq("id", row['id']).execute(); st.rerun()

st.markdown(f"<div style='text-align: center; color: {color_pri}; margin-top: 50px; opacity: 0.5;'>AISAAC-SHIELD PROTECTED</div>", unsafe_allow_html=True)
