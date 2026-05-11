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

def formatear_fecha_cr(fecha_iso, corto=False):
    if not fecha_iso or str(fecha_iso).lower() == 'nan': 
        return "Fecha no registrada"
    try:
        # Normalizamos a UTC para evitar conflictos de zona horaria
        dt_utc = pd.to_datetime(fecha_iso, utc=True)
        dt_cr = dt_utc.astimezone(ZONA_CR)
        if corto:
            return dt_cr.strftime("%d/%m/%y %H:%M")
        return dt_cr.strftime("%d/%m/%Y %I:%M %p")
    except Exception:
        return str(fecha_iso)[:16]

def generar_pdf_pro(df, titulo, total):
    try:
        from fpdf import FPDF
        class PDF(FPDF):
            def header(self):
                bg_seguro = preparar_fondo_para_pdf()
                if bg_seguro and os.path.exists(bg_seguro):
                    try: self.image(bg_seguro, x=0, y=0, w=210, h=297)
                    except Exception: pass
        
        pdf = PDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 22)
        pdf.set_text_color(75, 0, 130)
        pdf.cell(0, 20, txt=titulo, ln=True, align='C')
        pdf.ln(10)
        
        pdf.set_fill_color(75, 0, 130); pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(45, 10, "Fecha/Hora", 1, 0, 'C', True)
        pdf.cell(95, 10, "Concepto Detallado", 1, 0, 'C', True)
        pdf.cell(40, 10, "Monto", 1, 1, 'C', True)
        
        pdf.set_text_color(30, 30, 30); pdf.set_font("Arial", size=10)
        for _, row in df.iterrows():
            f_str = formatear_fecha_cr(row.get('created_at'), corto=True)
            c_str = str(row.get('concepto', 'Gasto'))[:45]
            m_str = f"CRC {row.get('monto', 0):,}"
            
            pdf.cell(45, 10, f_str, 1)
            pdf.cell(95, 10, c_str, 1)
            pdf.cell(40, 10, m_str, 1, 1)
            
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
    df_gastos['cat_base'] = df_gastos['concepto'].apply(lambda x: x.split(' - ')[0] if ' - ' in str(x) else x)
    por_cat = df_gastos.groupby('cat_base')['monto'].sum()
    max_cat = por_cat.idxmax()
    porcent = (por_cat.max() / total_g) * 100
    reporte = [f"ESTRUCTURA DE COSTOS: El area de {max_cat.upper()} representa el {porcent:.1f}% del gasto total."]
    if not df_viajes.empty:
        t_v = df_viajes['monto'].sum()
        margen = ((t_v - total_g) / t_v) * 100 if t_v > 0 else 0
        reporte.append(f"RENTABILIDAD: Margen operativo neto del {margen:.1f}%.")
    return "<br><br>".join(reporte)

def panel_mantenimiento(u):
    st.markdown("### ESTADO DE FLOTILLA Y TALLER")
    try:
        res_v = supabase.table("viajes").select("km_actual").eq("cliente_id", u).execute()
        res_g = supabase.table("gastos").select("km_actual").eq("cliente_id", u).execute()
        
        df_v_km = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()
        df_g_km = pd.DataFrame(res_g.data) if res_g.data else pd.DataFrame()
        
        km_v = df_v_km['km_actual'].max() if not df_v_km.empty and 'km_actual' in df_v_km.columns else 0
        km_g = df_g_km['km_actual'].max() if not df_g_km.empty and 'km_actual' in df_g_km.columns else 0
        km_actual = max(km_v, km_g)
        if pd.isna(km_actual): km_actual = 0
        
        res_m = supabase.table("gastos").select("km_actual").eq("cliente_id", u).ilike("concepto", "%Mantenimiento%").execute()
        df_m = pd.DataFrame(res_m.data) if res_m.data else pd.DataFrame()
        
        if not df_m.empty and 'km_actual' in df_m.columns:
            km_ult = df_m['km_actual'].max()
            if pd.isna(km_ult): km_ult = 0
            km_recorridos = km_actual - km_ult
            km_limite = 5000 
            km_restantes = km_limite - km_recorridos
            c1, c2, c3 = st.columns(3)
            c1.metric("Kilometraje Actual", f"{int(km_actual):,} km")
            c2.metric("Ultimo Servicio", f"{int(km_ult):,} km", f"Hace {int(km_recorridos):,} km", delta_color="off")
            st.progress(max(0.0, min(km_recorridos / km_limite, 1.0)))
            if km_restantes > 1000: st.success(f"Estado nominal. Proximo servicio: {int(km_ult + km_limite):,} km.")
            elif km_restantes > 0: st.warning(f"Preventivo: Faltan {int(km_restantes):,} km.")
            else: st.error(f"VENCIDO por {int(abs(km_restantes)):,} km.")
        else:
            st.info("Registre un gasto como 'Mantenimiento' para activar seguimiento.")
    except Exception as e:
        st.warning(f"Aviso taller: {str(e)[:50]}")

# --- 3. LOGIN ---
if 'autenticado' not in st.session_state: st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.markdown("<h1 style='text-align: center; color: #8A2BE2;'>AISAAC-SHIELD</h1>", unsafe_allow_html=True)
    pin = st.text_input("PIN DE ACCESO", type="password")
    if st.button("ACCEDER"):
        if pin == "8715": st.session_state.update({'autenticado': True, 'user': 1, 'nombre_ui': "Dani", 'ver': "Estandar"})
        elif pin == "8742": st.session_state.update({'autenticado': True, 'user': 2, 'nombre_ui': "Andrés", 'ver': "Premium"})
        else: st.error("PIN Incorrecto")
        if st.session_state['autenticado']: st.rerun()
    st.stop()

# --- 4. INTERFAZ ---
u = st.session_state['user']
nombre_pantalla = st.session_state['nombre_ui']
ver = st.session_state['ver']
color_pri = "#D4AF37" if ver == "Premium" else "#25D366"

st.markdown(f"<style>h1, h2, h3, label, .stMetric {{ color: {color_pri} !important; }}</style>", unsafe_allow_html=True)
st.markdown(f"<div style='border: 2px solid {color_pri}; padding:10px; border-radius:15px; text-align:center;'><h2 style='margin:0;'>{nombre_pantalla.upper()} - {'PREMIUM' if ver == 'Premium' else 'ESTANDAR'} SYSTEM</h2></div>", unsafe_allow_html=True)

tabs = st.tabs(["VIAJES", "GASTOS", "DATOS", "TALLER"])

with tabs[0]: 
    with st.form("f_v", clear_on_submit=True):
        c = st.text_input("Cliente")
        m = st.number_input("Monto (CRC)", min_value=0, step=1)
        k = st.number_input("Kilometraje", min_value=0, step=1)
        if st.form_submit_button("GUARDAR"):
            supabase.table("viajes").insert({"cliente": c, "monto": int(m), "km_actual": int(k), "cliente_id": u}).execute()
            st.success("Registrado"); st.rerun()

with tabs[1]: 
    with st.form("f_g", clear_on_submit=True):
        cat = st.selectbox("Categoria", ["Diesel", "Peaje", "Viaticos", "Repuestos", "Mantenimiento", "Otro"])
        det = st.text_input("Detalle")
        mg = st.number_input("Monto (CRC)", min_value=0, step=1)
        kg = st.number_input("Kilometraje", min_value=0, step=1)
        f = st.file_uploader("Foto", type=['jpg','png','jpeg'])
        if st.form_submit_button("REGISTRAR"):
            fb64 = procesar_foto(f) if f else None
            supabase.table("gastos").insert({"concepto": f"{cat} - {det}", "monto": int(mg), "cliente_id": u, "foto_comprobante": fb64, "km_actual": int(kg)}).execute()
            st.success("Gasto guardado"); st.rerun()

with tabs[2]: 
    try:
        res_v = supabase.table("viajes").select("*").eq("cliente_id", u).execute()
        res_g = supabase.table("gastos").select("*").eq("cliente_id", u).execute()
        
        df_v = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()
        df_g = pd.DataFrame(res_g.data) if res_g.data else pd.DataFrame()

        st.subheader("Filtro de Periodo")
        c_mes, c_ano = st.columns(2)
        mes_sel = c_mes.selectbox("Mes", range(1, 13), index=datetime.now().month-1, format_func=lambda x: ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"][x-1])
        ano_sel = c_ano.selectbox("Año", [2024, 2025, 2026], index=2)

        def filtrar(df, m, a):
            if df.empty: return df
            df['created_at'] = df['created_at'].fillna(datetime.now().isoformat())
            # Normalización de zona horaria a UTC para evitar el error "Mixed timezones"
            df['fecha_dt'] = pd.to_datetime(df['created_at'], utc=True, format='ISO8601', errors='coerce')
            df = df.dropna(subset=['fecha_dt'])
            return df[(df['fecha_dt'].dt.month == m) & (df['fecha_dt'].dt.year == a)]

        df_v = filtrar(df_v, mes_sel, ano_sel)
        df_g = filtrar(df_g, mes_sel, ano_sel)

        t_v = df_v['monto'].sum() if not df_v.empty else 0
        t_g = df_g['monto'].sum() if not df_g.empty else 0
        
        col1, col2, col3 = st.columns(3)
        col1.metric("INGRESOS", f"CRC {t_v:,}")
        col2.metric("GASTOS", f"CRC {t_g:,}")
        col3.metric("NETO", f"CRC {t_v - t_g:,}")

        if not df_g.empty:
            df_g['cat'] = df_g['concepto'].apply(lambda x: str(x).split(' - ')[0])
            st.plotly_chart(px.bar(df_g.groupby("cat")["monto"].sum().reset_index(), x="cat", y="monto", color="cat"), use_container_width=True)
            
            if st.button("ANALISIS IA"): st.info(motor_ia_analisis(df_g, df_v))
            
            pdf = generar_pdf_pro(df_g, f"REPORTE {mes_sel}/{ano_sel}", t_g)
            st.markdown(crear_boton_descarga(pdf, f"Reporte_{mes_sel}.pdf", "DESCARGAR PDF", "#DA0B20"), unsafe_allow_html=True)
            
            for i, r in df_g.sort_values('fecha_dt', ascending=False).iterrows():
                with st.expander(f"{formatear_fecha_cr(r['created_at'], True)} | {r['concepto']} | CRC {r['monto']:,}"):
                    if r.get('foto_comprobante'): st.image(f"data:image/jpeg;base64,{r['foto_comprobante']}")
                    if st.button("Borrar", key=f"d_{r['id']}"):
                        supabase.table("gastos").delete().eq("id", r['id']).execute()
                        st.rerun()
    except Exception as e: st.error(f"Error carga: {e}")

with tabs[3]: panel_mantenimiento(u)
st.markdown("<center style='opacity:0.3;'>AISAAC-SHIELD PROTECTED</center>", unsafe_allow_html=True)
