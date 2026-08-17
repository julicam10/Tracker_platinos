import streamlit as st
import pandas as pd
from bs4 import BeautifulSoup
import os

st.set_page_config(page_title="Tracker de Platinos", page_icon="🎮", layout="wide")
st.title("🎮 Mi Tracker de Platinos")

st.markdown("""
    <style>
        dataframe, th, td {
            text-align: center !important;
        }
        div[data-testid="stDataFrame"] th {
            text-align: center !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- PANEL DE MÉTRICAS GLOBALES (KPIs) ---
if os.path.exists('mis_juegos.csv') and os.path.exists('trofeos.csv'):
    df_juegos_kpi = pd.read_csv('mis_juegos.csv')
    df_trofeos_kpi = pd.read_csv('trofeos.csv')

    col1, col2, col3 = st.columns(3)
    
    total_juegos = len(df_juegos_kpi)
    total_platinos = len(df_juegos_kpi[df_juegos_kpi['Platino_Obtenido'] == 'Sí'])
    total_trofeos = len(df_trofeos_kpi)
    trofeos_completados = len(df_trofeos_kpi[df_trofeos_kpi['Estado'] == 'Completado'])
    
    col1.metric("Juegos Registrados", total_juegos)
    col2.metric("Platinos Conseguidos", total_platinos)
    
    if total_trofeos > 0:
        progreso_global = (trofeos_completados / total_trofeos) * 100
        col3.write("Progreso Global:")
        col3.progress(progreso_global / 100)
        col3.caption(f"{trofeos_completados} de {total_trofeos} trofeos obtenidos")
    
    st.markdown("---")

# 0. Botón para agregar juego manually
with st.expander("➕ Agregar nuevo juego manualmente"):
    with st.form("form_nuevo_juego", clear_on_submit=True):
        nuevo_nombre = st.text_input("Nombre del juego:")
        submit_juego = st.form_submit_button("Crear registro de juego")
        
        if submit_juego:
            if nuevo_nombre:
                if os.path.exists('mis_juegos.csv'):
                    df_juegos = pd.read_csv('mis_juegos.csv')
                else:
                    df_juegos = pd.DataFrame(columns=['Juego', 'Platino_Obtenido', 'Trofeos_Faltantes', 'Ultima_Actualizacion'])
                
                if nuevo_nombre not in df_juegos['Juego'].values:
                    nuevo_juego = {'Juego': nuevo_nombre, 'Platino_Obtenido': 'No', 'Trofeos_Faltantes': 0, 'Ultima_Actualizacion': pd.Timestamp.today().strftime('%Y-%m-%d')}
                    df_juegos = pd.concat([df_juegos, pd.DataFrame([nuevo_juego])], ignore_index=True)
                    df_juegos.to_csv('mis_juegos.csv', index=False)
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
            
            if os.path.exists('trofeos.csv'):
                df_trofeos = pd.read_csv('trofeos.csv')
            else:
                df_trofeos = pd.DataFrame(columns=['Juego', 'Categoria', 'Trofeo', 'Descripcion', 'Estado'])
            
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
                df_trofeos.to_csv('trofeos.csv', index=False)
                
            if os.path.exists('mis_juegos.csv'):
                df_juegos = pd.read_csv('mis_juegos.csv')
            else:
                df_juegos = pd.DataFrame(columns=['Juego', 'Platino_Obtenido', 'Trofeos_Faltantes', 'Ultima_Actualizacion'])
                
            if nombre_juego not in df_juegos['Juego'].values:
                nuevo_juego = {'Juego': nombre_juego, 'Platino_Obtenido': 'No', 'Trofeos_Faltantes': len(nuevos_datos), 'Ultima_Actualizacion': pd.Timestamp.today().strftime('%Y-%m-%d')}
                df_juegos = pd.concat([df_juegos, pd.DataFrame([nuevo_juego])], ignore_index=True)
            else:
                idx_j = df_juegos[df_juegos['Juego'] == nombre_juego].index[0]
                df_juegos.at[idx_j, 'Trofeos_Faltantes'] = len(nuevos_datos)
                
            df_juegos.to_csv('mis_juegos.csv', index=False)
            st.sidebar.success(f"¡{nombre_juego} importado con éxito ({len(nuevos_datos)} trofeos)!")
            st.rerun()

# 2. Sincronización y Visualización de Juegos
if os.path.exists('mis_juegos.csv') and os.path.exists('trofeos.csv'):
    df_juegos = pd.read_csv('mis_juegos.csv')
    df_trofeos = pd.read_csv('trofeos.csv')
    
    for idx, row in df_juegos.iterrows():
        juego = row['Juego']
        trofeos_juego = df_trofeos[df_trofeos['Juego'] == juego]
        if not trofeos_juego.empty:
            pendientes = len(trofeos_juego[trofeos_juego['Estado'] == 'Pendiente'])
            df_juegos.at[idx, 'Trofeos_Faltantes'] = pendientes
            df_juegos.at[idx, 'Platino_Obtenido'] = 'Sí' if pendientes == 0 else 'No'
            
    df_juegos.to_csv('mis_juegos.csv', index=False)

st.subheader("Tus Juegos Registrados")
if os.path.exists('mis_juegos.csv'):
    df_juegos = pd.read_csv('mis_juegos.csv')
    st.dataframe(df_juegos, use_container_width=True, hide_index=True)

# 3. Gestión de Trofeos con KPIs, Filtros y Pestañas
st.subheader("Gestión de Trofeos")
if os.path.exists('trofeos.csv'):
    df_trofeos = pd.read_csv('trofeos.csv')
    if 'Juego' in df_trofeos.columns and not df_trofeos.empty:
        juego_seleccionado = st.selectbox("Selecciona un juego:", df_trofeos['Juego'].unique())
        
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
        
        st.write("") # Espacio visual
        
        # --- FILTRO AVANZADO ---
        filtro_estado = st.radio(
            "Filtro de visualización:", 
            ["Todos", "Pendientes", "Completados"], 
            horizontal=True
        )
        st.write("") # Espacio visual
        # -----------------------
        
        categorias = df_trofeos[df_trofeos['Juego'] == juego_seleccionado]['Categoria'].dropna().unique().tolist()
        
        if categorias:
            tabs = st.tabs(categorias)
            
            for i, cat in enumerate(categorias):
                with tabs[i]:
                    # Filtramos primero por juego y categoría
                    trofeos_cat = df_trofeos[(df_trofeos['Juego'] == juego_seleccionado) & (df_trofeos['Categoria'] == cat)]
                    
                    # Aplicamos el filtro seleccionado por el usuario
                    if filtro_estado == "Pendientes":
                        trofeos_cat = trofeos_cat[trofeos_cat['Estado'] == 'Pendiente']
                    elif filtro_estado == "Completados":
                        trofeos_cat = trofeos_cat[trofeos_cat['Estado'] == 'Completado']
                    
                    with st.form(key=f'form_{juego_seleccionado}_{i}'):
                        # Mensaje si el filtro deja la lista vacía
                        if trofeos_cat.empty:
                            st.info(f"No hay trofeos {filtro_estado.lower()} en esta categoría.")
                            st.form_submit_button("Guardar cambios", disabled=True)
                        else:
                            actualizaciones = []
                            a_eliminar = []
                            
                            for idx, row in trofeos_cat.iterrows():
                                col_check, col_info, col_del = st.columns([0.5, 4.2, 0.5])
                                
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
                                
                                for idx, nuevo_estado in actualizaciones:
                                    if idx in df_trofeos.index:
                                        df_trofeos.at[idx, 'Estado'] = nuevo_estado
                                        
                                df_trofeos.to_csv('trofeos.csv', index=False)
                                st.success("¡Cambios guardados con éxito!")
                                st.rerun()