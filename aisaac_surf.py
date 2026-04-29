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

def obtener_ruta_fondo():
    nombres = ["fondo_reporte.jpg", "fondo_reporte.jpg.jpg", "fondo_reporte.jpeg", "fondo_reporte.png"]
    dirs = [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]
    for d in dirs:
        for n in nombres:
            ruta = os.path.join(d, n)
            if os.path.exists(ruta): return ruta
    return None

def preparar_fondo_para_pdf():
    ruta_original = obtener_ruta_fondo()
    if not ruta_original: return None
    try:
        img = Image.open(ruta_original).convert('RGBA')
        capa_blanca = Image.new('RGBA', img.size, (255, 255, 255, 165))
        img_mezclada = Image.alpha_composite(img, capa_blanca)
        img_final = img_mezclada.convert('RGB')
        ruta_segura = os.path.join(os.getcwd(), "temp_fondo_fpdf.jpg")
        img_final.save(ruta_segura, "JPEG", quality=85)
        return ruta_segura
    except Exception:
        return ruta_original

def generar_pdf_pro(df, titulo, total):
    try:
        from fpdf import FPDF
        class PDF(FPDF):
            def header(self):
                bg_seguro = preparar_fondo_para_pdf()
                if bg_seguro and os.path.exists(bg_seguro):
                    try: self.image(bg_seguro, x=0, y=0, w=210, h=297)
                    except: pass
        
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
        pdf.cell(140, 12, "TOTAL ACUMULADO:", 1, 0, 'R')
        pdf.cell(40, 12, f"CRC {total:,}", 1, 1, 'C')
        return pdf.output(dest='S').encode('latin-1', 'replace')
    except Exception as e:
        return f"Error general PDF: {str(e)}".encode('latin-1')

def crear_boton_descarga(datos, nombre, texto, color):
    b64 = base64.b64encode(datos).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{nombre}" style="background-color: {color}; color: white; padding: 12px; border-radius: 10px; text-decoration: none; font-weight: bold; display: block; text-align: center; margin-bottom: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.3); border: none;">{texto}</a>'

# --- 2. MODULOS DE IA Y MANTENIMIENTO ---
def motor_ia_analisis(df_gastos, df_viajes):
    if df_gastos.empty: return "SISTEMA: Datos insuficientes para generar analisis."
    total_g = df_gastos['monto'].sum()
    por_cat = df_gastos.groupby('concepto')['monto'].sum()
    max_cat = por_cat.idxmax()
    porcent = (por_cat.max() / total_g) * 100
    reporte = [f"ESTRUCTURA DE COSTOS: El gasto dominante es {max_cat.upper()} ({porcent:.1f}% del total)."]
    if not df_viajes.empty:
        t_v = df_viajes['monto'].sum()
        margen = ((t_v - total_g) / t_v) * 100 if t_v > 0 else 0
        reporte.append(f"RENTABILIDAD: Margen neto calculado del {margen:.1f}%.")
    return "<br><br>".join(reporte)

def panel_mantenimiento(u):
    st.markdown("### 🛠️ Estado de Flotilla y Taller")
    
    try:
        # 1. Obtener KM mas alto registrado
        res_v = supabase.table("viajes").select("km_actual").eq("cliente_id", u).order("km_actual", desc=True).limit(1).execute()
        res_g = supabase.table("gastos").select("km_actual").eq("cliente_id", u).order("km_actual", desc=True).limit(1).execute()
        km_v = res_v.data[0]['km_actual'] if res_v.data and res_v.data[0].get('km_actual') else 0
        km_g = res_g.data[0]['km_actual'] if res_g.data and res_g.data[0].get('km_actual') else 0
        km_actual = max(km_v, km_g)
        
        # 2. Obtener KM del ultimo mantenimiento
        res_m = supabase.table("gastos").select("km_actual, created_at").eq("cliente_id", u).eq("concepto", "Mantenimiento").order("km_actual", desc=True).limit(1).execute()
        
        if res_m.data and res_m.data[0].get('km_actual'):
            km_ult = res_m.data[0]['km_actual']
            
            km_recorridos = km_actual - km_ult
            km_limite = 5000  # Intervalo para cambio de aceite/revision
            km_restantes = km_limite - km_recorridos
            porcentaje = max(0.0, min(km_recorridos / km_limite, 1.0))
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Kilometraje Actual", f"{km_actual:,} km")
            c2.metric("Último Servicio", f"{km_ult:,} km", f"Hace {km_recorridos:,} km", delta_color="off")
            
            st.write("Progreso hacia el próximo servicio:")
            
            if km_restantes > 1000:
                c3.metric("Próximo en", f"{km_restantes:,} km")
                st.progress(porcentaje)
                st.success(f"✅ Flotilla en estado óptimo. Próxima revisión sugerida a los {km_ult + km_limite:,} km.")
            elif km_restantes > 0:
                c3.metric("Próximo en", f"{km_restantes:,} km", "¡Pronto!", delta_color="inverse")
                st.progress(porcentaje)
                st.warning(f"⚠️ Atención: Preparar presupuesto. Se acerca el servicio de 5,000 km. (A los {km_ult + km_limite:,} km)")
            else:
                c3.metric("Atraso de Servicio", f"{abs(km_restantes):,} km", "CRÍTICO", delta_color="inverse")
                st.progress(1.0)
                st.error(f"🚨 ALERTA ROJA: El vehículo ha excedido el límite de mantenimiento de seguridad. Programar taller INMEDIATAMENTE.")
        else:
            st.info("ℹ️ No hay registros de 'Mantenimiento'. Cuando realices un cambio de aceite, regístralo en la pestaña GASTOS seleccionando 'Mantenimiento' e ingresando el kilometraje actual.")
            
    except Exception as e:
        st.warning(f"⚠️ El panel de mantenimiento requiere una pequeña configuración en Supabase. Asegúrate de añadir la columna 'km_actual' (tipo int8) a la tabla 'gastos'.")

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

# --- 4. INTERFAZ Y ESTILOS ---
u = st.session_state['user']
ver = st.session_state['ver']

color_pri = "#D4AF37" if ver == "Premium" else "#25D366"
bg_style = "rgba(0, 0, 0, 0.94)" if ver == "Premium" else "rgba(5, 5, 5, 0.92)"
titulo_app = "PREMIUM SYSTEM" if ver == "Premium" else "ESTANDAR SYSTEM"

st.markdown(f"""
    <style>
    .stApp {{ background-color: #0e1117; }}
    h1, h2, h3, label, .stMetric {{ color: {color_pri} !important; }}
    </style>
""", unsafe_allow_html=True)

c_logo, c_tit = st.columns([1, 5])
with c_logo:
    if ver == "Premium":
        if os.path.exists("logo.png"): st.image("logo.png", width=120)
    else:
        if os.path.exists("logo_primo.png"): st.image("logo_primo.png", width=120)
        elif os.path.exists("logo.png"): st.image("logo.png", width=120)

with c_tit:
    st.markdown(f"<div style='border: 2px solid {color_pri}; padding:10px; border-radius:15px; text-align:center; background: {bg_style};'><h2 style='color:{color_pri}; margin:0;'>{u.upper()} - {titulo_app}</h2></div>", unsafe_allow_html=True)

tabs = st.tabs(["VIAJES", "GASTOS", "DATOS", "TALLER"])

with tabs[0]: 
    with st.form("f_v", clear_on_submit=True):
        c = st.text_input("Cliente / Empresa")
        m = st.number_input("Monto (CRC)", min_value=0, step=1)
        k = st.number_input("Kilometraje Actual", min_value=0, step=1)
        if st.form_submit_button("GUARDAR VIAJE"):
            try:
                supabase.table("viajes").insert({"cliente": c, "monto": int(m), "km_actual": int(k), "cliente_id": u}).execute()
                st.success("Ruta registrada"); st.rerun()
            except Exception as e:
                st.error("Error al guardar. Revisa la base de datos.")

with tabs[1]: 
    with st.form("f_g", clear_on_submit=True):
        t = st.selectbox("Concepto", ["Diesel", "Peaje", "Viaticos", "Repuestos", "Mantenimiento", "Otros"])
        mg = st.number_input("Monto (CRC)", min_value=0, step=1)
        kg = st.number_input("Kilometraje del Gasto (Requerido para Mantenimiento)", min_value=0, step=1)
        f = st.file_uploader("Comprobante", type=['jpg','png','jpeg'])
        if st.form_submit_button("REGISTRAR GASTO"):
            try:
                fb64 = procesar_foto(f) if f else None
                supabase.table("gastos").insert({"concepto": t, "monto": int(mg), "cliente_id": u, "foto_comprobante": fb64, "km_actual": int(kg)}).execute()
                st.success("Guardado exitosamente"); st.rerun()
            except Exception as e:
                st.error("⚠️ Error: Supabase necesita la columna 'km_actual' en la tabla 'gastos'. Agrégala para guardar correctamente.")

with tabs[2]: 
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

    if st.button("ANALISIS DE IA"):
        st.markdown(f"<div style='border: 1px solid #8A2BE2; padding: 15px; border-radius: 10px;'>{motor_ia_analisis(df_g, df_v)}</div>", unsafe_allow_html=True)

    if not df_g.empty:
        st.plotly_chart(px.bar(df_g.groupby("concepto")["monto"].sum().reset_index(), x="concepto", y="monto", color="concepto"), use_container_width=True)
        
        d1, d2 = st.columns(2)
        with d1:
            pdf = generar_pdf_pro(df_g, f"REPORTE {u.upper()}", t_g)
            st.markdown(crear_boton_descarga(pdf, "Reporte.pdf", "PDF", "#DA0B20"), unsafe_allow_html=True)
        with d2:
            df_limpio = df_g.drop(columns=['foto_comprobante'], errors='ignore')
            csv = df_limpio.to_csv(index=False).encode('utf-8')
            st.markdown(crear_boton_descarga(csv, "Gastos.csv", "EXCEL", "#107C41"), unsafe_allow_html=True)
        
        for i, row in df_g.iterrows():
            with st.expander(f"{row['concepto']} - CRC {row['monto']:,}"):
                if row.get('foto_comprobante'): st.image(f"data:image/jpeg;base64,{row['foto_comprobante']}")
                if st.button("Eliminar", key=f"del_{row['id']}"):
                    supabase.table("gastos").delete().eq("id", row['id']).execute(); st.rerun()

with tabs[3]:
    panel_mantenimiento(u)

st.markdown(f"<div style='text-align: center; color: {color_pri}; margin-top: 50px; opacity: 0.5;'>AISAAC-SHIELD PROTECTED</div>", unsafe_allow_html=True)
