import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
import gspread
from google.oauth2.service_account import Credentials
import json
import os

st.set_page_config(page_title="Tracker de Platinos", page_icon="🎮", layout="wide")
st.title("🎮 Mi Tracker de Platinos")

# --- CONFIGURACIÓN DE GOOGLE SHEETS ---
URL_SHEET = "URL_DE_TU_GOOGLE_SHEET" # REEMPLAZA ESTO CON TU URL REAL

@st.cache_resource
def init_connection():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_dict = json.loads(st.secrets["gcp_json"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_url(URL_SHEET)

sheet = init_connection()

def load_data(tab_name, cols):
    ws = sheet.worksheet(tab_name)
    records = ws.get_all_records()
    if records:
        return pd.DataFrame(records)
    return pd.DataFrame(columns=cols)

def save_data(tab_name, df):
    ws = sheet.worksheet(tab_name)
    ws.clear()
    if not df.empty:
        datos = [df.columns.values.tolist()] + df.fillna("").astype(str).values.tolist()
        ws.update(datos)
    else:
        ws.update([df.columns.values.tolist()])

st.markdown("""
    <style>
        dataframe, th, td { text-align: center !important; }
        div[data-testid="stDataFrame"] th { text-align: center !important; }
    </style>
""", unsafe_allow_html=True)

# --- CARGA INICIAL DE DATOS DESDE LA NUBE ---
cols_juegos = ['Juego', 'Platino_Obtenido', 'Trofeos_Faltantes', 'Ultima_Actualizacion']
cols_trofeos = ['Juego', 'Categoria', 'Trofeo', 'Descripcion', 'Estado']

df_juegos = load_data('mis_juegos', cols_juegos)
df_trofeos = load_data('trofeos', cols_trofeos)

# --- 🚀 SISTEMA DE AUTO-REPARACIÓN DE BASE DE DATOS ---
if not df_trofeos.empty:
    juegos_en_trofeos = df_trofeos['Juego'].unique()
    juegos_registrados = df_juegos['Juego'].values if not df_juegos.empty else []
    
    juegos_faltantes = [j for j in juegos_en_trofeos if j not in juegos_registrados]
    
    if juegos_faltantes:
        nuevos_registros = []
        for j in juegos_faltantes:
            faltantes = len(df_trofeos[(df_trofeos['Juego'] == j) & (df_trofeos['Estado'] == 'Pendiente')])
            nuevos_registros.append({
                'Juego': j,
                'Platino_Obtenido': 'Sí' if faltantes == 0 else 'No',
                'Trofeos_Faltantes': faltantes,
                'Ultima_Actualizacion': pd.Timestamp.today().strftime('%Y-%m-%d')
            })
        
        df_juegos = pd.concat([df_juegos, pd.DataFrame(nuevos_registros)], ignore_index=True)
        save_data('mis_juegos', df_juegos)

# --- PANEL DE MÉTRICAS GLOBALES (KPIs) ---
col1, col2, col3 = st.columns(3)
total_juegos = len(df_juegos)
total_platinos = len(df_juegos[df_juegos['Platino_Obtenido'] == 'Sí']) if not df_juegos.empty else 0
total_trofeos = len(df_trofeos)
trofeos_completados = len(df_trofeos[df_trofeos['Estado'] == 'Completado']) if not df_trofeos.empty else 0

col1.metric("Juegos Registrados", total_juegos)
col2.metric("Platinos Conseguidos", total_platinos)

if total_trofeos > 0:
    progreso_global = (trofeos_completados / total_trofeos) * 100
    col3.write("Progreso Global:")
    col3.progress(progreso_global / 100)
    col3.caption(f"{trofeos_completados} de {total_trofeos} trofeos obtenidos")

st.markdown("---")

# 0. Botón para agregar juego manualmente
with st.expander("➕ Agregar nuevo juego manualmente"):
    with st.form("form_nuevo_juego", clear_on_submit=True):
        nuevo_nombre = st.text_input("Nombre del juego:")
        submit_juego = st.form_submit_button("Crear registro de juego")
        
        if submit_juego:
            if nuevo_nombre:
                if nuevo_nombre not in df_juegos['Juego'].values:
                    nuevo_juego = {
                        'Juego': nuevo_nombre, 
                        'Platino_Obtenido': 'No', 
                        'Trofeos_Faltantes': 0, 
                        'Ultima_Actualizacion': pd.Timestamp.today().strftime('%Y-%m-%d')
                    }
                    df_juegos = pd.concat([df_juegos, pd.DataFrame([nuevo_juego])], ignore_index=True)
                    save_data('mis_juegos', df_juegos)
                    st.success(f"¡{nuevo_nombre} añadido a tu lista!")
                    st.rerun()
                else:
                    st.warning("Ese juego ya existe en tu lista.")
            else:
                st.error("Por favor, ingresa un nombre.")

# 1. Panel de Carga (Subir HTML)
st.sidebar.header("📥 Importar Juego")
archivo_subido = st.sidebar.file_uploader("Arrastra aquí el archivo .html de PSNProfiles", type=['html'])

if archivo_subido is not None:
    nombre_juego = st.sidebar.text_input("Nombre del juego para este archivo:")
    if st.sidebar.button("Procesar HTML"):
        if not nombre_juego:
            st.sidebar.error("Por favor, escribe el nombre del juego.")
        else:
            soup = BeautifulSoup(archivo_subido, 'html.parser')
            
            if 'Juego' in df_trofeos.columns:
                df_trofeos = df_trofeos[df_trofeos['Juego'] != nombre_juego]

            nuevos_datos = []
            categoria_actual = "Base Game"
            
            for tr in soup.find_all(['tr', 'h3']):
                if tr.name == 'h3':
                    categoria_actual = tr.text.strip()
                    continue
                
                a_title = tr.find('a', class_='title')
                if a_title:
                    titulo = a_title.text.strip()
                    if titulo and not titulo.lower() in [nombre_juego.lower(), "julianespitia10"]:
                        descripcion = "Sin descripción"
                        celda = a_title.find_parent('td')
                        if celda:
                            textos = [t.strip() for t in celda.stripped_strings]
                            for txt in textos:
                                if txt != titulo and len(txt) > 8 and not any(x in txt for x in ['http', 'Aug', 'Rare']):
                                    descripcion = txt
                                    break

                        nuevos_datos.append({
                            'Juego': nombre_juego, 
                            'Categoria': categoria_actual,
                            'Trofeo': titulo, 
                            'Descripcion': descripcion, 
                            'Estado': 'Pendiente'
                        })

            if nuevos_datos:
                df_nuevos = pd.DataFrame(nuevos_datos)
                df_trofeos = pd.concat([df_trofeos, df_nuevos], ignore_index=True)
                save_data('trofeos', df_trofeos)
                
            if nombre_juego not in df_juegos['Juego'].values:
                nuevo_juego = {
                    'Juego': nombre_juego, 
                    'Platino_Obtenido': 'No', 
                    'Trofeos_Faltantes': len(nuevos_datos), 
                    'Ultima_Actualizacion': pd.Timestamp.today().strftime('%Y-%m-%d')
                }
                df_juegos = pd.concat([df_juegos, pd.DataFrame([nuevo_juego])], ignore_index=True)
            else:
                idx_j = df_juegos[df_juegos['Juego'] == nombre_juego].index[0]
                df_juegos.at[idx_j, 'Trofeos_Faltantes'] = len(nuevos_datos)
                
            save_data('mis_juegos', df_juegos)
            st.sidebar.success(f"¡{nombre_juego} importado con éxito ({len(nuevos_datos)} trofeos)!")
            st.rerun()

# 2. Sincronización Optimizada de Juegos
cambios_en_juegos = False
for idx, row in df_juegos.iterrows():
    juego = row['Juego']
    trofeos_juego = df_trofeos[df_trofeos['Juego'] == juego]
    if not trofeos_juego.empty:
        pendientes = len(trofeos_juego[trofeos_juego['Estado'] == 'Pendiente'])
        platino = 'Sí' if pendientes == 0 else 'No'
        
        # Validar si hubo cambios antes de actualizar para ahorrar cuota de Google API
        if str(row['Trofeos_Faltantes']) != str(pendientes) or str(row['Platino_Obtenido']) != platino:
            df_juegos.at[idx, 'Trofeos_Faltantes'] = pendientes
            df_juegos.at[idx, 'Platino_Obtenido'] = platino
            cambios_en_juegos = True

if cambios_en_juegos:
    save_data('mis_juegos', df_juegos)

st.subheader("Tus Juegos Registrados")
if not df_juegos.empty:
    st.dataframe(df_juegos, use_container_width=True, hide_index=True)

# 3. Gestión de Trofeos con KPIs, Filtros y Pestañas
st.subheader("Gestión de Trofeos")
if not df_trofeos.empty:
    juegos_disponibles = df_trofeos['Juego'].unique()
    if len(juegos_disponibles) > 0:
        juego_seleccionado = st.selectbox("Selecciona un juego:", juegos_disponibles)
        
        # --- MÉTRICAS ESPECÍFICAS DEL JUEGO ---
        trofeos_del_juego = df_trofeos[df_trofeos['Juego'] == juego_seleccionado]
        total_j = len(trofeos_del_juego)
        completados_j = len(trofeos_del_juego[trofeos_del_juego['Estado'] == 'Completado'])
        faltantes_j = total_j - completados_j
        
        col_m1, col_m2 = st.columns([1, 3])
        with col_m1:
            st.metric(f"Trofeos de {juego_seleccionado}", f"{completados_j} / {total_j}")
        with col_m2:
            st.write("Progreso de completitud:")
            if total_j > 0:
                st.progress(completados_j / total_j)
                st.caption(f"Te faltan {faltantes_j} trofeos para completarlo al 100%")
        
        st.write("") 
        
        # --- FILTRO AVANZADO ---
        filtro_estado = st.radio("Filtro de visualización:", ["Todos", "Pendientes", "Completados"], horizontal=True)
        st.write("") 
        
        categorias = df_trofeos[df_trofeos['Juego'] == juego_seleccionado]['Categoria'].dropna().unique().tolist()
        
        if categorias:
            tabs = st.tabs(categorias)
            
            for i, cat in enumerate(categorias):
                with tabs[i]:
                    trofeos_cat = df_trofeos[(df_trofeos['Juego'] == juego_seleccionado) & (df_trofeos['Categoria'] == cat)]
                    
                    if filtro_estado == "Pendientes":
                        trofeos_cat = trofeos_cat[trofeos_cat['Estado'] == 'Pendiente']
                    elif filtro_estado == "Completados":
                        trofeos_cat = trofeos_cat[trofeos_cat['Estado'] == 'Completado']
                    
                    with st.form(key=f'form_{juego_seleccionado}_{i}'):
                        if trofeos_cat.empty:
                            st.info(f"No hay trofeos {filtro_estado.lower()} en esta categoría.")
                            st.form_submit_button("Guardar cambios", disabled=True)
                        else:
                            actualizaciones = []
                            a_eliminar = []
                            
                            for idx, row in trofeos_cat.iterrows():
                                col_check, col_info, col_del = st.columns([0.3, 4.2, 0.5])
                                
                                with col_check:
                                    completado = st.checkbox("Hecho", value=(row['Estado'] == 'Completado'), key=f"t_{idx}")
                                with col_info:
                                    desc = row['Descripcion'] if 'Descripcion' in row and pd.notna(row['Descripcion']) else "Sin descripción"
                                    st.markdown(f"**{row['Trofeo']}**<br><span style='color:#a0a0a0; font-size: 0.9em;'>{desc}</span>", unsafe_allow_html=True)
                                with col_del:
                                    borrar = st.checkbox("Borrar", value=False, key=f"del_{idx}")
                                
                                st.markdown("---")
                                
                                nuevo_estado = 'Completado' if completado else 'Pendiente'
                                actualizaciones.append((idx, nuevo_estado))
                                if borrar:
                                    a_eliminar.append(idx)
                            
                            guardar = st.form_submit_button("Guardar cambios y actualizar")
                            if guardar:
                                if a_eliminar:
                                    df_trofeos = df_trofeos.drop(a_eliminar)
                                
                                for idx_update, nuevo_estado in actualizaciones:
                                    if idx_update in df_trofeos.index:
                                        df_trofeos.at[idx_update, 'Estado'] = nuevo_estado
                                        
                                save_data('trofeos', df_trofeos)
                                st.success("¡Cambios guardados en la nube con éxito!")
                                st.rerun()