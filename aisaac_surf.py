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
        dt_utc = datetime.fromisoformat(str(fecha_iso).replace('Z', '+00:00'))
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
            
            porcentaje = max(0.0, min(km_recorridos / km_limite, 1.0))
            st.write("Progreso hacia el proximo servicio de seguridad:")
            st.progress(porcentaje)
            
            if km_restantes > 1000:
                st.success(f"Sistema en estado nominal. Proximo servicio a los {int(km_ult + km_limite):,} km.")
            elif km_restantes > 0:
                st.warning(f"Atencion preventiva: Faltan {int(km_restantes):,} km para el servicio.")
            else:
                st.error(f"ALERTA CRITICA: Servicio de mantenimiento vencido por {int(abs(km_restantes)):,} km.")
        else:
            st.info("Para activar el seguimiento logistico, registre un gasto bajo la categoria Mantenimiento.")
            
    except Exception as e:
        st.warning(f"Aviso de sistema: Configurando modulo de mantenimiento. Detalle tecnico: {str(e)[:50]}")


# --- 3. LOGIN ---
if 'autenticado' not in st.session_state or 'nombre_ui' not in st.session_state: 
    st.session_state['autenticado'] = False

if not st.session_state['autenticado']:
    st.markdown("<h1 style='text-align: center; color: #8A2BE2;'>AISAAC-SHIELD</h1>", unsafe_allow_html=True)
    pin = st.text_input("PIN DE ACCESO", type="password")
    
    if st.button("ACCEDER AL SISTEMA"):
        if pin == "8715": 
            st.session_state.update({'autenticado': True, 'user': 1, 'nombre_ui': "Dani", 'ver': "Estandar"})
        elif pin == "8742": 
            st.session_state.update({'autenticado': True, 'user': 2, 'nombre_ui': "Andrés", 'ver': "Premium"})
        else: 
            st.error("PIN Incorrecto")
            
        if st.session_state['autenticado']: st.rerun()
    st.stop()

# --- 4. INTERFAZ Y ESTILOS ---
u = st.session_state['user']
nombre_pantalla = st.session_state['nombre_ui']
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
    st.markdown(f"<div style='border: 2px solid {color_pri}; padding:10px; border-radius:15px; text-align:center; background: {bg_style};'><h2 style='color:{color_pri}; margin:0;'>{nombre_pantalla.upper()} - {titulo_app}</h2></div>", unsafe_allow_html=True)

tabs = st.tabs(["VIAJES", "GASTOS", "DATOS", "TALLER"])

with tabs[0]: 
    with st.form("f_v", clear_on_submit=True):
        c = st.text_input("Cliente / Empresa")
        m = st.number_input("Monto (CRC)", min_value=0, step=1)
        k = st.number_input("Kilometraje Actual", min_value=0, step=1)
        if st.form_submit_button("GUARDAR VIAJE"):
            try:
                supabase.table("viajes").insert({"cliente": c, "monto": int(m), "km_actual": int(k), "cliente_id": u}).execute()
                st.success("Operacion registrada")
                st.rerun()
            except Exception as e:
                st.error(f"Error de comunicacion con el servidor: {str(e)}")

with tabs[1]: 
    with st.form("f_g", clear_on_submit=True):
        c_base = st.selectbox("Categoria", ["Diesel", "Peaje", "Viaticos", "Repuestos", "Mantenimiento", "Otro"])
        c_especifico = st.text_input("Detalle del gasto (Que se compro?)")
        mg = st.number_input("Monto (CRC)", min_value=0, step=1)
        kg = st.number_input("Kilometraje del Vehiculo", min_value=0, step=1)
        f = st.file_uploader("Comprobante Digital", type=['jpg','png','jpeg'])
        
        if st.form_submit_button("REGISTRAR GASTO"):
            try:
                concepto_final = f"{c_base} - {c_especifico.strip()}" if c_especifico.strip() else c_base
                fb64 = procesar_foto(f) if f else None
                supabase.table("gastos").insert({
                    "concepto": concepto_final, 
                    "monto": int(mg), 
                    "cliente_id": u, 
                    "foto_comprobante": fb64, 
                    "km_actual": int(kg)
                }).execute()
                st.success("Gasto procesado")
                st.rerun()
            except Exception as e:
                st.error(f"Error: Verifique la conexion con la base de datos. Detalle: {str(e)}")

with tabs[2]: 
    try:
        # CONSULTA INICIAL A SUPABASE
        res_v = supabase.table("viajes").select("*").eq("cliente_id", u).execute()
        res_g = supabase.table("gastos").select("*").eq("cliente_id", u).execute()
        
        df_v = pd.DataFrame(res_v.data) if res_v.data else pd.DataFrame()
        df_g = pd.DataFrame(res_g.data) if res_g.data else pd.DataFrame()

        # FILTRO POR MES Y AÑO
        st.subheader("Filtro de Periodo")
        c_mes, c_ano = st.columns(2)
        meses_nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        
        mes_sel = c_mes.selectbox("Seleccionar Mes", range(1, 13), index=datetime.now().month-1, format_func=lambda x: meses_nombres[x-1])
        ano_sel = c_ano.selectbox("Seleccionar Año", [2024, 2025, 2026], index=2)

        # APLICAR FILTRO A LOS DATAFRAMES SI TIENEN DATOS
        if not df_v.empty:
            df_v['fecha_dt'] = pd.to_datetime(df_v['created_at'])
            df_v = df_v[(df_v['fecha_dt'].dt.month == mes_sel) & (df_v['fecha_dt'].dt.year == ano_sel)]
            
        if not df_g.empty:
            df_g['fecha_dt'] = pd.to_datetime(df_g['created_at'])
            df_g = df_g[(df_g['fecha_dt'].dt.month == mes_sel) & (df_g['fecha_dt'].dt.year == ano_sel)]
            if 'id' in df_g.columns:
                df_g = df_g.sort_values(by='id', ascending=False)

        # CALCULOS CON DATOS FILTRADOS
        t_v = df_v['monto'].sum() if not df_v.empty else 0
        t_g = df_g['monto'].sum() if not df_g.empty else 0
        
        c1, c2, c3 = st.columns(3)
        c1.metric("INGRESOS TOTALES", f"CRC {t_v:,}")
        c2.metric("GASTOS TOTALES", f"CRC {t_g:,}")
        c3.metric("BALANCE NETO", f"CRC {t_v - t_g:,}")

        if st.button("ANALISIS DE IA"):
            st.markdown(f"<div style='border: 1px solid #8A2BE2; padding: 15px; border-radius: 10px;'>{motor_ia_analisis(df_g, df_v)}</div>", unsafe_allow_html=True)

        if not df_g.empty:
            df_g['cat_grafica'] = df_g['concepto'].apply(lambda x: x.split(' - ')[0] if ' - ' in str(x) else x)
            st.plotly_chart(px.bar(df_g.groupby("cat_grafica")["monto"].sum().reset_index(), x="cat_grafica", y="monto", color="cat_grafica"), use_container_width=True)
            
            d1, d2 = st.columns(2)
            with d1:
                pdf = generar_pdf_pro(df_g, f"REPORTE {nombre_pantalla.upper()} - {meses_nombres[mes_sel-1]} {ano_sel}", t_g)
                st.markdown(crear_boton_descarga(pdf, f"Reporte_{mes_sel}_{ano_sel}.pdf", "GENERAR PDF", "#DA0B20"), unsafe_allow_html=True)
            with d2:
                df_xl = df_g.drop(columns=['foto_comprobante', 'cat_grafica', 'fecha_dt'], errors='ignore')
                csv = df_xl.to_csv(index=False).encode('utf-8')
                st.markdown(crear_boton_descarga(csv, f"Gastos_{mes_sel}_{ano_sel}.csv", "GENERAR EXCEL", "#107C41"), unsafe_allow_html=True)
            
            st.write("---")
            st.subheader("Historial detallado con marca de tiempo")
            for i, row in df_g.iterrows():
                timestamp = formatear_fecha_cr(row.get('created_at'))
                with st.expander(f"{timestamp} | {row['concepto']} | CRC {row['monto']:,}"):
                    if row.get('foto_comprobante'): st.image(f"data:image/jpeg;base64,{row['foto_comprobante']}")
                    if st.button("Eliminar", key=f"del_{row['id']}"):
                        supabase.table("gastos").delete().eq("id", row['id']).execute()
                        st.rerun()
    except Exception as e:
        st.error(f"Error al procesar los datos visuales. Detalle: {str(e)[:50]}")

with tabs[3]:
    panel_mantenimiento(u)

st.markdown(f"<div style='text-align: center; color: {color_pri}; margin-top: 50px; opacity: 0.5;'>AISAAC-SHIELD PROTECTED</div>", unsafe_allow_html=True)
