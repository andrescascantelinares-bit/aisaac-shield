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

# --- 2. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.markdown("<h1 style='text-align: center; color: #25D366; text-shadow: 0 0 15px #25D366;'>AISAAC-SHIELD</h1>", unsafe_allow_html=True)
    pin = st.text_input("PIN DE ACCESO", type="password")
    if st.button("DESBLOQUEAR SISTEMA"):
        if pin == "8715": st.session_state.update({'autenticado': True, 'user': "dany", 'ver': "Estandar"})
        elif pin == "8742": st.session_state.update({'autenticado': True, 'user': "padre_andres", 'ver': "Premium"})
        else: st.error("PIN Incorrecto")
        if st.session_state['autenticado']: st.rerun()
    st.stop()

# --- 3. VARIABLES Y ESTILO VISUAL ---
u = st.session_state['user']
ver = st.session_state['ver']
hoy_cr = datetime.now(ZONA_CR)
meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
mes_actual = meses[hoy_cr.month - 1]

color_pri = "#D4AF37" if ver == "Premium" else "#25D366"
label_app = "GOLD SYSTEM" if ver == "Premium" else "RUTAMASTER"

# Cargar imagen de fondo si existe en secrets
ruta_fondo = st.secrets.get("APP_BACKGROUND_PATH", "")
fondo_b64 = get_base64(ruta_fondo) if ruta_fondo else None
css_fondo = f"background-image: url('data:image/png;base64,{fondo_b64}'); background-size: cover; background-attachment: fixed;" if fondo_b64 else "background-color: #111;"

st.markdown(f"""
<style>
    [data-testid="stHeader"], .stDeployButton, footer {{ visibility: hidden; display: none !important; }}
    .stApp {{ {css_fondo} }}
    [data-testid="stAppViewBlockContainer"] {{ 
        background-color: rgba(15, 15, 15, 0.85); 
        border-radius: 20px; 
        padding: 2rem; 
        border: 2px solid {color_pri};
        box-shadow: 0 0 25px {color_pri}40; 
    }}
    .header-led {{
        background: rgba(0,0,0,0.8);
        padding: 15px;
        border-radius: 15px;
        border: 2px solid {color_pri};
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 0 15px {color_pri};
        text-shadow: 0 0 10px {color_pri};
    }}
    h1, h2, h3, label, .stMetric {{ color: {color_pri} !important; }}
    .stButton>button {{ 
        background: rgba(0,0,0,0.8); 
        color: {color_pri}; 
        font-weight: bold; 
        border: 1px solid {color_pri};
        border-radius: 10px;
        width: 100%;
        transition: 0.3s;
    }}
    .stButton>button:hover {{
        background: {color_pri};
        color: black;
        box-shadow: 0 0 15px {color_pri};
    }}
</style>
""", unsafe_allow_html=True)

# --- ENCABEZADO LED Y PERIODO ---
st.markdown(f"<div class='header-led'><h2 style='margin:0;'>{label_app} - {u.upper()}</h2></div>", unsafe_allow_html=True)

with st.expander(f"PERIODO: {mes_actual}"):
    st.write(f"Fecha del sistema: {hoy_cr.strftime('%Y/%m/%d')}")

# --- 4. LOGICA DE DATOS ---
if ver == "Premium":
    tabs = st.tabs(["REGISTRO PRO", "HISTORIAL", "DATOS"])
    
    with tabs[0]:
        st.subheader("Entrada de Gastos Gerenciales")
        with st.form("f_pro", clear_on_submit=True):
            concepto = st.selectbox("Concepto", ["Diesel", "Repuestos", "Mantenimiento", "Peaje"])
            monto = st.number_input("Monto (CRC)", min_value=0, value=None, placeholder="Escribe el monto...")
            km = st.number_input("Kilometraje Actual", min_value=0, value=None, placeholder="Mínimo: 0")
            foto = st.file_uploader("Subir Comprobante", type=['jpg','png','jpeg'])
            if st.form_submit_button("SINCRONIZAR DATOS"):
                if monto:
                    foto_b64 = procesar_foto(foto) if foto else None
                    supabase.table("gastos").insert({"concepto": concepto, "monto": int(monto), "cliente_id": u, "foto_comprobante": foto_b64}).execute()
                    st.success("DATOS SINCRONIZADOS"); time.sleep(1); st.rerun()

else:
    tabs = st.tabs(["REGISTRO", "GASTOS", "HISTORIAL"])
    
    rv = supabase.table("viajes").select("km_actual").eq("cliente_id", u).order("id", desc=True).limit(1).execute()
    km_actual = rv.data[0]['km_actual'] if rv.data else 0

    with tabs[0]:
        st.subheader("Finalizar Viaje")
        with st.form("f_viaje", clear_on_submit=True):
            st.text_input("Fecha", value=hoy_cr.strftime("%Y/%m/%d"), disabled=True)
            cli = st.text_input("Cliente / Empresa")
            c1, c2 = st.columns(2)
            orig = c1.text_input("Origen"); dest = c2.text_input("Destino")
            c3, c4 = st.columns(2)
            monto = c3.number_input("Costo (CRC)", min_value=0, value=None, placeholder="Escribe el monto...")
            km = c4.number_input("KM Llegada", min_value=km_actual, value=None, placeholder=f"Mínimo: {km_actual}")
            if st.form_submit_button("REGISTRAR VIAJE"):
                if cli and km is not None:
                    supabase.table("viajes").insert({"cliente": cli, "origen": orig, "destino": dest, "km_actual": int(km), "monto": int(monto) if monto else 0, "cliente_id": u}).execute()
                    st.success("VIAJE GUARDADO"); time.sleep(1); st.rerun()

    with tabs[1]:
        st.subheader("Registrar Gasto de Ruta")
        with st.form("f_gasto_dani", clear_on_submit=True):
            tipo = st.selectbox("Concepto", ["Diesel", "Peaje", "Viaticos", "Otros"])
            monto_g = st.number_input("Monto (CRC)", min_value=0, value=None, placeholder="Escribe el monto...")
            foto = st.file_uploader("Foto del recibo", type=['jpg','png','jpeg'])
            if st.form_submit_button("GUARDAR GASTO"):
                if monto_g:
                    fb64 = procesar_foto(foto) if foto else None
                    supabase.table("gastos").insert({"concepto": tipo, "monto": int(monto_g), "cliente_id": u, "foto_comprobante": fb64}).execute()
                    st.success("GASTO REGISTRADO"); time.sleep(1); st.rerun()

# ==========================================
# LECTURA DE HISTORIAL EN TIEMPO REAL
# ==========================================
with tabs[1] if ver == "Premium" else tabs[2]:
    st.subheader("Registros en la Nube")
    if st.button("ACTUALIZAR DATOS"):
        st.cache_resource.clear()
        st.rerun()

    tipo_hist = st.radio("Ver historial de:", ["Viajes", "Gastos"], horizontal=True) if ver != "Premium" else "Gastos"

    try:
        if tipo_hist == "Viajes":
            res = supabase.table("viajes").select("*").eq("cliente_id", u).order("id", desc=True).execute()
            if res.data:
                st.dataframe(pd.DataFrame(res.data)[["cliente", "origen", "destino", "km_actual", "monto"]])
            else: st.info("No hay viajes registrados.")
        else:
            res = supabase.table("gastos").select("*").eq("cliente_id", u).order("id", desc=True).execute()
            if res.data:
                for row in res.data:
                    with st.expander(f"{row['concepto']} - CRC {row['monto']:,}"):
                        if row.get('foto_comprobante'): st.image(f"data:image/jpeg;base64,{row['foto_comprobante']}")
                        if st.button("Borrar Registro", key=f"del_{row['id']}"):
                            supabase.table("gastos").delete().eq("id", row['id']).execute(); st.rerun()
            else: st.info("No hay gastos registrados.")
    except Exception as e:
        st.error(f"Error de lectura: {e}")

# --- PIE DE PÁGINA ---
st.markdown(f"""
<div style='text-align: center; color: {color_pri}; margin-top: 50px; padding: 10px; border: 1px solid {color_pri}; border-radius: 10px; background: rgba(0,0,0,0.8); box-shadow: 0 0 15px {color_pri}; text-shadow: 0 0 5px {color_pri};'>
    AISAAC-SHIELD PROTECTED
</div>
""", unsafe_allow_html=True)