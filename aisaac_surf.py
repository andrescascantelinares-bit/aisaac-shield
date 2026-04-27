import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
import base64
import os
from PIL import Image
import io
import time

# --- 0. CONFIGURACIÓN ---
st.set_page_config(page_title="Aisaac-Shield Systems", layout="centered")
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

def generar_pdf(df, titulo):
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, txt=titulo, ln=True, align='C')
        pdf.set_font("Arial", size=10)
        for i, row in df.iterrows():
            txt = f"Fecha: {row.get('created_at','N/A')[:10]} | Ref: {row.get('concepto', row.get('cliente', 'Ruta'))} | Monto: CRC {row.get('monto', 0)}"
            pdf.cell(0, 8, txt=txt, ln=True)
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except:
        return b"Error: Instalar fpdf"

def crear_boton_descarga(datos, nombre, texto, color):
    b64 = base64.b64encode(datos).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{nombre}" style="background-color: {color}; color: white; padding: 10px; border-radius: 8px; text-decoration: none; font-weight: bold; display: block; text-align: center; margin-bottom: 10px; border: 1px solid rgba(255,255,255,0.3); box-shadow: 0 4px 6px rgba(0,0,0,0.3);">{texto}</a>'

# --- 2. PANTALLA DE INICIO BLINDADA ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.markdown("""
    <style>
        [data-testid="stHeader"], footer { visibility: hidden; display: none !important; }
        .stApp {
            background-color: #050010;
            background-image: 
                linear-gradient(#4b008240 1px, transparent 1px),
                linear-gradient(90deg, #4b008240 1px, transparent 1px);
            background-size: 40px 40px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("<h1 style='text-align: center; color: #8A2BE2; text-shadow: 0 0 15px #8A2BE2; margin-top: 10vh;'>AISAAC-SHIELD</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #aaa; margin-bottom: 30px;'>PORTAL DE SEGURIDAD</p>", unsafe_allow_html=True)
    
    pin = st.text_input("PIN DE ACCESO", type="password")
    if st.button("DESBLOQUEAR SISTEMA", use_container_width=True):
        if pin == "8715": st.session_state.update({'autenticado': True, 'user': "dany", 'ver': "Estandar"})
        elif pin == "8742": st.session_state.update({'autenticado': True, 'user': "padre_andres", 'ver': "Premium"})
        else: st.error("PIN Incorrecto")
        if st.session_state['autenticado']: st.rerun()
    st.stop()

# --- 3. VARIABLES Y ESTILO PRINCIPAL ---
u = st.session_state['user']
ver = st.session_state['ver']
hoy_cr = datetime.now(ZONA_CR)

color_pri = "#D4AF37" if ver == "Premium" else "#25D366"
label_app = "GOLD SYSTEM" if ver == "Premium" else "RUTAMASTER"

ruta_fondo = st.secrets.get("APP_BACKGROUND_PATH", "")
fondo_b64 = get_base64(ruta_fondo) if ruta_fondo else None
css_fondo = f"background-image: url('data:image/png;base64,{fondo_b64}'); background-size: cover; background-attachment: fixed;" if fondo_b64 else "background-color: #111;"

st.markdown(f"""
<style>
    [data-testid="stHeader"], footer {{ visibility: hidden; display: none !important; }}
    .stApp {{ {css_fondo} }}
    [data-testid="stAppViewBlockContainer"] {{ 
        background-color: rgba(15, 15, 15, 0.9); 
        border-radius: 20px; padding: 2rem; 
        border: 2px solid {color_pri};
        box-shadow: 0 0 25px {color_pri}40; 
    }}
    .header-led {{
        background: rgba(0,0,0,0.8); padding: 15px; border-radius: 15px;
        border: 2px solid {color_pri}; text-align: center; margin-bottom: 20px;
        box-shadow: 0 0 15px {color_pri}; text-shadow: 0 0 10px {color_pri};
    }}
    h1, h2, h3, label, .stMetric {{ color: {color_pri} !important; }}
    .stButton>button {{ background: rgba(0,0,0,0.8); color: {color_pri}; border: 1px solid {color_pri}; border-radius: 10px; width: 100%; transition: 0.3s; }}
    .stButton>button:hover {{ background: {color_pri}; color: black; box-shadow: 0 0 15px {color_pri}; }}
</style>
""", unsafe_allow_html=True)

st.markdown(f"<div class='header-led'><h2 style='margin:0;'>{label_app} - {u.upper()}</h2></div>", unsafe_allow_html=True)

# --- 4. MOTOR PRINCIPAL UNIFICADO ---
tabs = st.tabs(["REGISTRAR VIAJE", "GASTOS", "DATOS"])

# Obtener último KM
km_actual = 0
try:
    rv = supabase.table("viajes").select("km_actual").eq("cliente_id", u).order("id", desc=True).limit(1).execute()
    if rv.data: km_actual = rv.data[0]['km_actual']
except: pass

with tabs[0]:
    st.subheader("Registrar Nuevo Viaje")
    with st.form("f_viaje", clear_on_submit=True):
        cli = st.text_input("Cliente / Empresa")
        c1, c2 = st.columns(2)
        orig = c1.text_input("Origen"); dest = c2.text_input("Destino")
        c3, c4 = st.columns(2)
        monto = c3.number_input("Costo del Viaje (CRC)", min_value=0, value=None)
        km = c4.number_input("KM Llegada", min_value=km_actual, value=None, placeholder=f"Mínimo: {km_actual}")
        if st.form_submit_button("GUARDAR VIAJE"):
            if cli and km is not None:
                supabase.table("viajes").insert({"cliente": cli, "origen": orig, "destino": dest, "km_actual": int(km), "monto": int(monto) if monto else 0, "cliente_id": u}).execute()
                st.success("VIAJE GUARDADO"); time.sleep(1); st.rerun()

with tabs[1]:
    st.subheader("Entrada de Gastos")
    with st.form("f_gasto", clear_on_submit=True):
        opciones_gasto = ["Diesel", "Repuestos", "Mantenimiento", "Peaje", "Viaticos", "Otros"] if ver == "Premium" else ["Diesel", "Peaje", "Viaticos", "Otros"]
        tipo = st.selectbox("Concepto", opciones_gasto)
        monto_g = st.number_input("Monto (CRC)", min_value=0, value=None)
        foto = st.file_uploader("Subir Comprobante", type=['jpg','png','jpeg'])
        if st.form_submit_button("GUARDAR GASTO"):
            if monto_g:
                fb64 = procesar_foto(foto) if foto else None
                supabase.table("gastos").insert({"concepto": tipo, "monto": int(monto_g), "cliente_id": u, "foto_comprobante": fb64}).execute()
                st.success("GASTO REGISTRADO"); time.sleep(1); st.rerun()

with tabs[2]:
    st.subheader("Registros y Reportes")
    if st.button("ACTUALIZAR DATOS DE LA NUBE"): st.cache_resource.clear(); st.rerun()
    
    tipo_hist = st.radio("Selecciona qué ver:", ["Viajes", "Gastos"], horizontal=True)

    try:
        if tipo_hist == "Viajes":
            res = supabase.table("viajes").select("*").eq("cliente_id", u).order("id", desc=True).execute()
            if res.data:
                df_v = pd.DataFrame(res.data)
                st.dataframe(df_v[["created_at", "cliente", "origen", "destino", "km_actual", "monto"]])
                
                csv_v = df_v.to_csv(index=False).encode('utf-8')
                pdf_v = generar_pdf(df_v, f"Reporte de Viajes - {u.upper()}")
                c_ex, c_pdf = st.columns(2)
                c_ex.markdown(crear_boton_descarga(csv_v, "viajes.csv", "📥 DESCARGAR EXCEL", "#107C41"), unsafe_allow_html=True)
                c_pdf.markdown(crear_boton_descarga(pdf_v, "viajes.pdf", "📄 DESCARGAR PDF", "#DA0B20"), unsafe_allow_html=True)
            else: st.info("No hay viajes registrados en la nube.")
            
        else:
            res = supabase.table("gastos").select("*").eq("cliente_id", u).order("id", desc=True).execute()
            if res.data:
                df_g = pd.DataFrame(res.data)
                
                csv_g = df_g.to_csv(index=False).encode('utf-8')
                pdf_g = generar_pdf(df_g, f"Reporte de Gastos - {u.upper()}")
                c_ex, c_pdf = st.columns(2)
                c_ex.markdown(crear_boton_descarga(csv_g, "gastos.csv", "📥 DESCARGAR EXCEL", "#107C41"), unsafe_allow_html=True)
                c_pdf.markdown(crear_boton_descarga(pdf_g, "gastos.pdf", "📄 DESCARGAR PDF", "#DA0B20"), unsafe_allow_html=True)

                st.write("---")
                for i, row in df_g.iterrows():
                    with st.expander(f"{row['concepto']} - CRC {row['monto']:,}"):
                        if row.get('foto_comprobante'): st.image(f"data:image/jpeg;base64,{row['foto_comprobante']}")
                        if st.button("Borrar Registro", key=f"del_{row['id']}"):
                            supabase.table("gastos").delete().eq("id", row['id']).execute(); st.rerun()
            else: st.info("No hay gastos registrados en la nube.")
    except Exception as e:
        st.error(f"Error de base de datos: {e}")

st.markdown(f"<div style='text-align: center; color: {color_pri}; margin-top: 50px; padding: 10px; border: 1px solid {color_pri}; border-radius: 10px; background: rgba(0,0,0,0.8); box-shadow: 0 0 15px {color_pri};'>AISAAC-SHIELD PROTECTED</div>", unsafe_allow_html=True)
