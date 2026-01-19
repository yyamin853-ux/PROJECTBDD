"""
Page Vice-Doyen
Vue stratégique globale de la faculté
ACCÈS RESTREINT: Vice-Doyen uniquement
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
    page_title="Vue Stratégique - Num_Exam",
    page_icon="👨‍💼",
    layout="wide"
)

# ===== VÉRIFICATION D'AUTORISATION =====
def check_auth():
    """Vérifier que l'utilisateur est bien Vice-Doyen"""
    if 'role' not in st.session_state or st.session_state.role != "Vice-Doyen":
        st.error("🚫 Accès non autorisé")
        st.warning("Cette page est réservée au Vice-Doyen uniquement")
        st.info("Veuillez vous connecter avec les bons identifiants")
        st.stop()

check_auth()
# ========================================

# En-tête
st.markdown("""
    <div style='text-align: center; padding: 1.5rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
         color: white; border-radius: 10px; margin-bottom: 2rem;'>
        <h1>👨‍💼 Tableau de Bord - Vice-Doyen</h1>
        <p>Vue Stratégique Globale de la Faculté</p>
    </div>
""", unsafe_allow_html=True)

# KPIs Globaux
try:
    kpis = db.get_global_kpis()
    
    # Métriques totales
    st.markdown("### 📊 Indicateurs Globaux")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        total_examens = int(kpis['nb_examens_planifies'].sum())
        st.metric("📝 Examens Planifiés", f"{total_examens:,}")
    
    with col2:
        total_etudiants = int(kpis['nb_etudiants'].sum())
        st.metric("👨‍🎓 Étudiants", f"{total_etudiants:,}")
    
    with col3:
        total_modules = int(kpis['nb_modules_total'].sum())
        st.metric("📚 Modules", f"{total_modules}")
    
    with col4:
        total_lieux = int(kpis['nb_lieux_utilises'].sum())
        st.metric("🏢 Lieux Utilisés", f"{total_lieux}")
    
    with col5:
        total_conflits = int(kpis['nb_conflits_non_resolus'].sum())
        color = "normal" if total_conflits == 0 else "inverse"
        st.metric("⚠️ Conflits", f"{total_conflits}", delta_color=color)
    
    st.markdown("---")
    
    # Graphiques principaux
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown("### 🏛️ Examens par Département")
        
        fig_dept = px.bar(
            kpis,
            x='departement',
            y='nb_examens_planifies',
            title="Nombre d'examens planifiés par département",
            labels={'departement': 'Département', 'nb_examens_planifies': 'Nombre d\'examens'},
            color='nb_examens_planifies',
            color_continuous_scale='Blues'
        )
        fig_dept.update_layout(showlegend=False, xaxis_tickangle=-45)
        st.plotly_chart(fig_dept, use_container_width=True)
    
    with col_right:
        st.markdown("### 👨‍🎓 Étudiants par Département")
        
        fig_students = px.pie(
            kpis,
            values='nb_etudiants',
            names='departement',
            title="Répartition des étudiants"
        )
        st.plotly_chart(fig_students, use_container_width=True)
    
    # Taux de conflits
    st.markdown("### ⚠️ Taux de Conflits par Département")
    
    kpis['taux_conflits'] = (kpis['nb_conflits_non_resolus'] / kpis['nb_examens_planifies'] * 100).fillna(0)
    
    fig_conflits = px.bar(
        kpis,
        x='departement',
        y='taux_conflits',
        title="Pourcentage de conflits par département",
        labels={'departement': 'Département', 'taux_conflits': 'Taux de conflits (%)'},
        color='taux_conflits',
        color_continuous_scale='Reds'
    )
    fig_conflits.add_hline(y=5, line_dash="dash", line_color="orange", annotation_text="Seuil acceptable (5%)")
    st.plotly_chart(fig_conflits, use_container_width=True)
    
    # Tableau détaillé
    st.markdown("### 📋 Vue Détaillée par Département")
    
    display_kpis = kpis.copy()
    display_kpis = display_kpis.rename(columns={
        'departement': 'Département',
        'nb_examens_planifies': 'Examens',
        'nb_modules_total': 'Modules',
        'nb_etudiants': 'Étudiants',
        'total_inscriptions': 'Inscriptions',
        'nb_lieux_utilises': 'Lieux',
        'capacite_moyenne_lieux': 'Cap. Moy.',
        'nb_conflits_non_resolus': 'Conflits'
    })
    
    st.dataframe(
        display_kpis,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Examens": st.column_config.NumberColumn(format="%d"),
            "Modules": st.column_config.NumberColumn(format="%d"),
            "Étudiants": st.column_config.NumberColumn(format="%d"),
            "Inscriptions": st.column_config.NumberColumn(format="%d"),
            "Cap. Moy.": st.column_config.NumberColumn(format="%.0f"),
            "Conflits": st.column_config.NumberColumn(
                format="%d",
                help="Nombre de conflits non résolus"
            )
        }
    )
    
    # Occupation des ressources
    st.markdown("---")
    st.markdown("### 🏢 Occupation des Ressources")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Distribution des examens dans le temps
        daily_dist = db.get_daily_exam_distribution(session_id=1)
        
        if not daily_dist.empty:
            fig_timeline = px.area(
                daily_dist,
                x='date_examen',
                y='nb_examens',
                title="Évolution du nombre d'examens par jour",
                labels={'date_examen': 'Date', 'nb_examens': 'Nombre d\'examens'}
            )
            st.plotly_chart(fig_timeline, use_container_width=True)
    
    with col2:
        # Occupation des salles
        room_occ = db.get_room_occupation(session_id=1)
        
        if not room_occ.empty:
            # Taux moyen par type de lieu
            avg_by_type = room_occ.groupby('type')['taux_occupation'].mean().reset_index()
            
            fig_rooms = px.bar(
                avg_by_type,
                x='type',
                y='taux_occupation',
                title="Taux d'occupation moyen par type de lieu",
                labels={'type': 'Type de lieu', 'taux_occupation': 'Taux d\'occupation (%)'},
                color='taux_occupation',
                color_continuous_scale='Viridis'
            )
            fig_rooms.add_hline(y=100, line_dash="dash", line_color="red")
            st.plotly_chart(fig_rooms, use_container_width=True)
    
    # Statistiques professeurs
    st.markdown("### 👨‍🏫 Mobilisation des Professeurs")
    
    prof_stats = db.get_professor_surveillance_stats(session_id=1)
    
    if not prof_stats.empty:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_profs_mobilises = len(prof_stats[prof_stats['nb_surveillances'] > 0])
            total_profs = len(prof_stats)
            taux_mobilisation = (total_profs_mobilises / total_profs * 100) if total_profs > 0 else 0
            st.metric("👨‍🏫 Taux de mobilisation", f"{taux_mobilisation:.1f}%", 
                     help=f"{total_profs_mobilises}/{total_profs} professeurs")
        
        with col2:
            avg_surveillance = prof_stats['nb_surveillances'].mean()
            st.metric("📊 Moyenne surveillances/prof", f"{avg_surveillance:.1f}")
        
        with col3:
            # Équité de répartition (écart-type)
            std_surveillance = prof_stats['nb_surveillances'].std()
            equite_score = max(0, 100 - (std_surveillance * 10))
            st.metric("⚖️ Équité de répartition", f"{equite_score:.0f}/100",
                     help="Plus le score est élevé, plus la répartition est équitable")
        
        # Distribution des surveillances
        surveillance_dist = prof_stats['nb_surveillances'].value_counts().sort_index().reset_index()
        surveillance_dist.columns = ['Nombre de surveillances', 'Nombre de professeurs']
        
        fig_dist = px.bar(
            surveillance_dist,
            x='Nombre de surveillances',
            y='Nombre de professeurs',
            title="Distribution du nombre de surveillances par professeur"
        )
        st.plotly_chart(fig_dist, use_container_width=True)
    
    # Actions recommandées
    st.markdown("---")
    st.markdown("### 💡 Actions Recommandées")
    
    # Analyser les problèmes
    warnings = []
    
    if total_conflits > 0:
        warnings.append(f"⚠️ **{total_conflits} conflits** détectés nécessitent une résolution")
    
    # Vérifier l'équilibrage entre départements
    if len(kpis) > 0:
        examens_par_etudiant = kpis['nb_examens_planifies'] / kpis['nb_etudiants']
        if examens_par_etudiant.std() > 0.5:
            warnings.append("⚠️ **Déséquilibre** dans la charge d'examens entre départements")
    
    # Vérifier les sur-capacités
    if not room_occ.empty:
        over_capacity = len(room_occ[room_occ['taux_occupation'] > 100])
        if over_capacity > 0:
            warnings.append(f"⚠️ **{over_capacity} lieu(x)** en sur-capacité")
    
    if warnings:
        for warning in warnings:
            st.warning(warning)
    else:
        st.success("✅ **Aucun problème majeur détecté** - Le planning est optimal")
    
    # Boutons d'action
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Exporter Rapport Complet", use_container_width=True):
            st.info("🚧 Fonctionnalité d'export en développement")
    
    with col2:
        if st.button("📧 Envoyer aux Chefs de Département", use_container_width=True):
            st.info("🚧 Fonctionnalité d'envoi en développement")
    
    with col3:
        if st.button("✅ Valider le Planning", type="primary", use_container_width=True):
            st.success("✅ Planning validé avec succès!")

except Exception as e:
    st.error(f"❌ Erreur lors du chargement des données: {e}")
    st.info("Assurez-vous qu'un planning a été généré et que la base de données est accessible.")