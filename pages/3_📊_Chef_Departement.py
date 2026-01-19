"""
Page Chef de Département
Validation et statistiques par département
ACCÈS RESTREINT: Chef de Département uniquement
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db_connection import db

st.set_page_config(
    page_title="Chef de Département - Num_Exam",
    page_icon="📊",
    layout="wide"
)

# ===== VÉRIFICATION D'AUTORISATION =====
def check_auth():
    """Vérifier l'authentification"""
    if 'role' not in st.session_state or st.session_state.role != "Chef de Département":
        st.error("🚫 Accès non autorisé")
        st.warning("Cette page est réservée aux Chefs de Département uniquement")
        st.info("Veuillez vous connecter avec les bons identifiants")
        st.stop()

check_auth()
# ========================================

# Récupérer les infos du département
dept_id = st.session_state.user_id

dept_info = db.execute_query("""
    SELECT id, nom, code, responsable
    FROM departements
    WHERE id = %s
""", (dept_id,))

if not dept_info:
    st.error("❌ Département introuvable")
    st.stop()

dept_info = dept_info[0]

# En-tête
st.markdown(f"""
    <div style='text-align: center; padding: 1.5rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
         color: white; border-radius: 10px; margin-bottom: 2rem;'>
        <h1>📊 Département {dept_info['nom']}</h1>
        <p>Gestion et Validation des Examens</p>
    </div>
""", unsafe_allow_html=True)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Vue d'Ensemble",
    "📅 Planning Détaillé",
    "⚠️ Conflits",
    "📈 Statistiques"
])

# TAB 1: Vue d'ensemble
with tab1:
    # Statistiques du département
    stats = db.get_department_stats(dept_id, session_id=1)
    
    if stats:
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("📚 Formations", stats['nb_formations'])
        with col2:
            st.metric("📖 Modules", stats['nb_modules'])
        with col3:
            st.metric("👨‍🎓 Étudiants", f"{stats['nb_etudiants']:,}")
        with col4:
            st.metric("📝 Examens", stats['nb_examens_planifies'])
        with col5:
            conflits = stats['nb_conflits'] or 0
            color = "normal" if conflits == 0 else "inverse"
            st.metric("⚠️ Conflits", conflits, delta_color=color)
        
        st.markdown("---")
        
        # Liste des formations
        st.markdown("### 🎓 Formations du Département")
        
        formations = db.get_formations_by_department(dept_id)
        
        if not formations.empty:
            # Ajouter des stats par formation
            for idx, formation in formations.iterrows():
                with st.expander(f"**{formation['nom']}** - {formation['code']}"):
                    
                    # Stats de cette formation
                    form_stats = db.execute_query("""
                        SELECT 
                            COUNT(DISTINCT m.id) as nb_modules,
                            COUNT(DISTINCT e.id) as nb_etudiants,
                            COUNT(DISTINCT ex.id) as nb_examens
                        FROM formations f
                        LEFT JOIN modules m ON m.formation_id = f.id
                        LEFT JOIN etudiants e ON e.formation_id = f.id
                        LEFT JOIN examens ex ON ex.module_id = m.id AND ex.session_id = 1
                        WHERE f.id = %s
                        GROUP BY f.id
                    """, (formation['id'],))
                    
                    if form_stats:
                        form_stats = form_stats[0]
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Modules", form_stats['nb_modules'])
                        with col2:
                            st.metric("Étudiants", form_stats['nb_etudiants'])
                        with col3:
                            st.metric("Examens planifiés", form_stats['nb_examens'])
    else:
        st.info("🔭 Aucune statistique disponible")

# TAB 2: Planning détaillé
with tab2:
    st.markdown("### 📅 Planning Complet du Département")
    
    schedule = db.get_department_schedule(dept_id, session_id=1)
    
    if not schedule.empty:
        # Filtres
        col1, col2, col3 = st.columns(3)
        
        with col1:
            formations_list = ["Toutes"] + schedule['formation'].unique().tolist()
            selected_formation = st.selectbox("Filtrer par formation", formations_list)
        
        with col2:
            dates_list = ["Toutes"] + sorted(schedule['date_examen'].unique().tolist())
            selected_date = st.selectbox("Filtrer par date", dates_list)
        
        with col3:
            statuts_list = ["Tous"] + schedule['statut'].unique().tolist()
            selected_statut = st.selectbox("Filtrer par statut", statuts_list)
        
        # Appliquer les filtres
        filtered_schedule = schedule.copy()
        
        if selected_formation != "Toutes":
            filtered_schedule = filtered_schedule[filtered_schedule['formation'] == selected_formation]
        
        if selected_date != "Toutes":
            filtered_schedule = filtered_schedule[filtered_schedule['date_examen'] == selected_date]
        
        if selected_statut != "Tous":
            filtered_schedule = filtered_schedule[filtered_schedule['statut'] == selected_statut]
        
        # Affichage
        st.markdown(f"**{len(filtered_schedule)}** examen(s) affiché(s)")
        
        # Formater pour affichage
        display_schedule = filtered_schedule.copy()
        display_schedule['Date'] = pd.to_datetime(display_schedule['date_examen']).dt.strftime('%d/%m/%Y')
        display_schedule['Heure'] = display_schedule['heure_debut'].astype(str)
        display_schedule['Durée'] = display_schedule['duree_minutes'].astype(str) + ' min'
        
        st.dataframe(
            display_schedule[['Date', 'Heure', 'Durée', 'code_module', 'nom_module', 
                            'formation', 'lieu', 'nb_inscrits', 'surveillant', 'statut']],
            use_container_width=True,
            hide_index=True,
            column_config={
                "statut": st.column_config.TextColumn(
                    "Statut",
                    help="Statut de l'examen"
                )
            }
        )
        
        # Export
        if st.button("📥 Exporter en CSV"):
            csv = display_schedule.to_csv(index=False)
            st.download_button(
                "Télécharger le CSV",
                csv,
                f"planning_{dept_info['code']}.csv",
                "text/csv",
                key='download-csv'
            )
        
        # Visualisation calendrier
        st.markdown("### 📆 Vue Calendrier")
        
        fig = px.timeline(
            filtered_schedule,
            x_start='date_examen',
            x_end='date_examen',
            y='formation',
            color='statut',
            hover_data=['code_module', 'lieu', 'surveillant'],
            title=f"Calendrier des examens - {dept_info['nom']}"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    else:
        st.info("🔭 Aucun examen planifié pour ce département")

# TAB 3: Conflits
with tab3:
    st.markdown("### ⚠️ Conflits Détectés dans le Département")
    
    # Récupérer tous les conflits
    all_conflicts = db.get_all_conflicts(session_id=1, resolved=False)
    
    if not all_conflicts.empty:
        # Filtrer par département
        dept_modules = db.execute_to_dataframe("""
            SELECT m.id as module_id
            FROM modules m
            JOIN formations f ON m.formation_id = f.id
            WHERE f.dept_id = %s
        """, (dept_id,))
        
        dept_module_ids = dept_modules['module_id'].tolist()
        
        # Filtrer les conflits du département (basé sur code_module)
        dept_conflicts = all_conflicts[
            all_conflicts['code_module'].str.contains('|'.join([str(mid) for mid in dept_module_ids]), na=False)
        ]
        
        if not dept_conflicts.empty:
            # Statistiques
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total conflits", len(dept_conflicts))
            with col2:
                high_severity = len(dept_conflicts[dept_conflicts['severite'] >= 4])
                st.metric("Haute sévérité", high_severity)
            with col3:
                conflict_types = dept_conflicts['type_conflit'].nunique()
                st.metric("Types de conflits", conflict_types)
            
            st.markdown("---")
            
            # Liste des conflits par type
            for conflict_type in dept_conflicts['type_conflit'].unique():
                type_conflicts = dept_conflicts[dept_conflicts['type_conflit'] == conflict_type]
                
                with st.expander(f"**{conflict_type}** ({len(type_conflicts)} conflit(s))"):
                    st.dataframe(
                        type_conflicts[['date_examen', 'code_module', 'nom_module', 
                                      'description', 'severite', 'date_detection']],
                        use_container_width=True,
                        hide_index=True
                    )
        else:
            st.success("✅ Aucun conflit détecté dans votre département")
    else:
        st.success("✅ Aucun conflit détecté")

# TAB 4: Statistiques
with tab4:
    st.markdown("### 📈 Statistiques du Département")
    
    schedule = db.get_department_schedule(dept_id, session_id=1)
    
    if not schedule.empty:
        # Distribution par formation
        st.markdown("#### 📊 Examens par Formation")
        
        formation_stats = schedule.groupby('formation').agg({
            'code_module': 'count',
            'nb_inscrits': 'sum'
        }).reset_index()
        formation_stats.columns = ['Formation', 'Nombre d\'examens', 'Total étudiants']
        
        fig1 = px.bar(
            formation_stats,
            x='Formation',
            y='Nombre d\'examens',
            title="Nombre d'examens par formation",
            color='Nombre d\'examens',
            color_continuous_scale='Blues'
        )
        fig1.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig1, use_container_width=True)
        
        # Distribution temporelle
        st.markdown("#### 📅 Distribution Temporelle")
        
        daily_count = schedule.groupby('date_examen').size().reset_index(name='Nombre d\'examens')
        
        fig2 = px.line(
            daily_count,
            x='date_examen',
            y='Nombre d\'examens',
            title="Nombre d'examens par jour",
            markers=True
        )
        st.plotly_chart(fig2, use_container_width=True)
        
        # Utilisation des lieux
        st.markdown("#### 🏢 Utilisation des Lieux")
        
        lieu_usage = schedule.groupby('lieu').size().reset_index(name='Utilisations')
        lieu_usage = lieu_usage.sort_values('Utilisations', ascending=False)
        
        fig3 = px.bar(
            lieu_usage.head(10),
            x='lieu',
            y='Utilisations',
            title="Top 10 des lieux les plus utilisés",
            color='Utilisations',
            color_continuous_scale='Viridis'
        )
        fig3.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig3, use_container_width=True)
        
        # Répartition des surveillances
        st.markdown("#### 👨‍🏫 Surveillances")
        
        surveillant_count = schedule[schedule['surveillant'].notna()].groupby('surveillant').size().reset_index(name='Surveillances')
        surveillant_count = surveillant_count.sort_values('Surveillances', ascending=False)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Professeurs mobilisés", len(surveillant_count))
        with col2:
            avg_surv = surveillant_count['Surveillances'].mean()
            st.metric("Moyenne/professeur", f"{avg_surv:.1f}")
        
        st.dataframe(
            surveillant_count.head(20),
            use_container_width=True,
            hide_index=True
        )
    
    else:
        st.info("🔭 Aucune donnée statistique disponible")

# Bouton de validation
st.markdown("---")
col1, col2, col3 = st.columns([1, 1, 1])

with col2:
    if st.button("✅ Valider le Planning du Département", type="primary", use_container_width=True):
        st.success(f"✅ Planning du département {dept_info['nom']} validé avec succès!")
        st.balloons()