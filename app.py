"""
Application Principale - Plateforme Num_Exam
Interface multi-acteurs AMÉLIORÉE pour la gestion des emplois du temps d'examens
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import sys
import os

# Ajouter le répertoire src au path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.db_connection import db

# Configuration de la page
st.set_page_config(
    page_title="Num_Exam - Gestion des Examens",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé amélioré
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
        border-bottom: 3px solid #1f77b4;
        margin-bottom: 2rem;
        background: linear-gradient(135deg, #667eea22 0%, #764ba222 100%);
        border-radius: 10px;
    }
    .exam-card {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #2196f3;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .exam-card:hover {
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        transform: translateY(-2px);
        transition: all 0.3s ease;
    }
    .time-slot {
        background-color: #f5f5f5;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
        border-left: 3px solid #4caf50;
    }
    .stat-card {
        background: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        text-align: center;
    }
    .filter-section {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

def init_session_state():
    """Initialiser les variables de session"""
    if 'role' not in st.session_state:
        st.session_state.role = None
    if 'user_id' not in st.session_state:
        st.session_state.user_id = None
    if 'session_exam_id' not in st.session_state:
        st.session_state.session_exam_id = 1
    if 'view_mode' not in st.session_state:
        st.session_state.view_mode = 'calendar'

def show_login():
    """Afficher l'écran de connexion/sélection de rôle"""
    st.markdown('<div class="main-header">🎓 Plateforme Num_Exam</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 📊 Système Intelligent de Gestion")
        st.markdown("""
        - ✅ Optimisation automatique des plannings
        - ✅ Détection intelligente des conflits
        - ✅ Gestion multi-départements
        - ✅ Interface intuitive pour tous les acteurs
        """)
    
    with col2:
        st.markdown("### 👥 Accès Rapide")
        
        # Bouton étudiant en évidence
        if st.button("📅 Consulter les Emplois du Temps (Étudiants)", 
                     type="primary", use_container_width=True):
            st.session_state.role = "Étudiant"
            st.session_state.user_id = None
            st.rerun()
        
        st.markdown("---")
        st.markdown("#### 🔐 Connexion Personnel")
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        role = st.selectbox(
            "Sélectionnez votre rôle",
            ["", "Vice-Doyen", "Administrateur Examens", "Chef de Département", "Professeur"],
            index=0
        )
        
        if role == "Professeur":
            search = st.text_input("🔍 Rechercher par nom ou prénom", key="prof_search")
            
            if search and len(search) >= 2:
                profs = db.execute_to_dataframe("""
                    SELECT p.id, p.matricule, p.nom, p.prenom, d.nom as departement
                    FROM professeurs p
                    JOIN departements d ON p.dept_id = d.id
                    WHERE p.nom ILIKE %s OR p.prenom ILIKE %s
                    ORDER BY p.nom, p.prenom
                    LIMIT 10
                """, (f"%{search}%", f"%{search}%"))
                
                if not profs.empty:
                    prof_options = [
                        f"{row['nom']} {row['prenom']} - {row['departement']}"
                        for _, row in profs.iterrows()
                    ]
                    selected = st.selectbox("Sélectionnez votre profil", prof_options)
                    
                    if st.button("Se connecter", type="primary", use_container_width=True):
                        idx = prof_options.index(selected)
                        st.session_state.role = "Professeur"
                        st.session_state.user_id = profs.iloc[idx]['id']
                        st.session_state.user_name = f"{profs.iloc[idx]['prenom']} {profs.iloc[idx]['nom']}"
                        st.rerun()
                else:
                    st.info("Aucun professeur trouvé")
        
        elif role == "Chef de Département":
            depts = db.get_departments()
            dept_options = [f"{row['code']} - {row['nom']}" for _, row in depts.iterrows()]
            selected_dept = st.selectbox("Sélectionnez votre département", dept_options)
            
            if st.button("Se connecter", type="primary", use_container_width=True):
                idx = dept_options.index(selected_dept)
                st.session_state.role = "Chef de Département"
                st.session_state.user_id = depts.iloc[idx]['id']
                st.session_state.user_name = f"Chef {depts.iloc[idx]['nom']}"
                st.rerun()
        
        elif role in ["Vice-Doyen", "Administrateur Examens"]:
            if st.button("Se connecter", type="primary", use_container_width=True):
                st.session_state.role = role
                st.session_state.user_id = 1
                st.session_state.user_name = role
                st.rerun()

def display_schedule_calendar_view(schedule_df):
    """Afficher le planning en vue calendrier améliorée"""
    if schedule_df.empty:
        return
    
    df = schedule_df.copy()
    df['date_examen'] = pd.to_datetime(df['date_examen'])
    df['heure_str'] = df['heure_debut'].astype(str).str[:5]
    
    dates = sorted(df['date_examen'].unique())
    creneaux = ['08:00', '10:00', '14:00', '16:00']
    
    for date in dates:
        date_str = date.strftime('%A %d %B %Y')
        jour_examens = df[df['date_examen'] == date]
        
        if jour_examens.empty:
            continue
        
        with st.expander(f"📆 **{date_str}** - {len(jour_examens)} examen(s)", expanded=True):
            cols = st.columns(4)
            
            for idx, creneau in enumerate(creneaux):
                with cols[idx]:
                    examens_creneau = jour_examens[jour_examens['heure_str'] == creneau]
                    
                    st.markdown(f"**🕐 {creneau}**")
                    
                    if examens_creneau.empty:
                        st.markdown("_Aucun examen_")
                    else:
                        for _, examen in examens_creneau.iterrows():
                            st.markdown(f"""
                            <div class='exam-card'>
                                <strong style='font-size: 1.1em; color: #1976d2;'>
                                    {examen.get('code_module', 'N/A')}
                                </strong><br>
                                <small style='color: #666;'>{examen.get('formation', examen.get('nom_module', 'N/A'))}</small><br>
                                <div style='margin-top: 8px;'>
                                    📍 {examen.get('lieu', 'N/A')}<br>
                                    👥 {examen.get('nb_inscrits', 0)} étudiants<br>
                                    ⏱️ {examen.get('duree_minutes', 90)} min
                                </div>
                            </div>
                            """, unsafe_allow_html=True)

def display_schedule_table_view(schedule_df):
    """Afficher le planning en vue tableau"""
    if schedule_df.empty:
        return
    
    df = schedule_df.copy()
    df['Date'] = pd.to_datetime(df['date_examen']).dt.strftime('%d/%m/%Y')
    df['Jour'] = pd.to_datetime(df['date_examen']).dt.strftime('%A')
    df['Heure'] = df['heure_debut'].astype(str).str[:5]
    df['Durée'] = df['duree_minutes'].astype(str) + ' min'
    
    cols_to_show = ['Date', 'Jour', 'Heure', 'Durée']
    
    if 'code_module' in df.columns:
        cols_to_show.append('code_module')
    if 'nom_module' in df.columns:
        cols_to_show.append('nom_module')
    if 'formation' in df.columns:
        cols_to_show.append('formation')
    if 'departement' in df.columns:
        cols_to_show.append('departement')
    if 'lieu' in df.columns:
        cols_to_show.append('lieu')
    if 'nb_inscrits' in df.columns:
        cols_to_show.append('nb_inscrits')
    if 'surveillant' in df.columns:
        cols_to_show.append('surveillant')
    
    display_df = df[cols_to_show].copy()
    display_df.columns = [col.replace('_', ' ').title() for col in display_df.columns]
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=500
    )
    
    # Export
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        csv = display_df.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            "📥 Télécharger en CSV",
            csv,
            "emploi_du_temps.csv",
            "text/csv",
            use_container_width=True
        )

def show_student_interface():
    """Interface publique améliorée pour consulter les emplois du temps"""
    st.sidebar.markdown("### 📅 Consultation Publique")
    st.sidebar.markdown("**Accès:** Tous les étudiants")
    
    # Mode d'affichage
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 👁️ Mode d'affichage")
    view_mode = st.sidebar.radio(
        "Choisir la vue",
        ["📅 Calendrier", "📋 Tableau", "📊 Chronologie"],
        key="view_mode_selector"
    )
    
    if st.sidebar.button("🔙 Retour à l'accueil"):
        st.session_state.role = None
        st.rerun()
    
    st.markdown('<div class="main-header">📅 Emplois du Temps des Examens</div>', unsafe_allow_html=True)
    
    # Section filtres
    st.markdown('<div class="filter-section">', unsafe_allow_html=True)
    st.markdown("### 🔍 Filtrer les examens")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        depts = db.get_departments()
        dept_options = ["Tous"] + [f"{row['code']} - {row['nom']}" for _, row in depts.iterrows()]
        selected_dept = st.selectbox("🏛️ Département", dept_options)
    
    with col2:
        if selected_dept != "Tous":
            dept_idx = dept_options.index(selected_dept) - 1
            dept_id = depts.iloc[dept_idx]['id']
            formations = db.get_formations_by_department(dept_id)
            formation_options = ["Toutes"] + formations['nom'].tolist()
        else:
            formations = db.execute_to_dataframe("SELECT DISTINCT nom FROM formations ORDER BY nom")
            formation_options = ["Toutes"] + formations['nom'].tolist()
        
        selected_formation = st.selectbox("🎓 Formation", formation_options)
    
    with col3:
        dates = db.execute_to_dataframe("""
            SELECT DISTINCT date_examen 
            FROM examens 
            WHERE session_id = 1 
            ORDER BY date_examen
        """)
        if not dates.empty:
            date_options = ["Toutes"] + [d.strftime('%d/%m/%Y') for d in dates['date_examen']]
        else:
            date_options = ["Toutes"]
        selected_date = st.selectbox("📅 Date", date_options)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Construire la requête
    query = """
        SELECT 
            e.date_examen,
            e.heure_debut,
            e.duree_minutes,
            m.code as code_module,
            m.nom as nom_module,
            f.nom as formation,
            d.nom as departement,
            l.nom as lieu,
            e.nb_inscrits,
            CONCAT(p.nom, ' ', p.prenom) as surveillant
        FROM examens e
        JOIN modules m ON e.module_id = m.id
        JOIN formations f ON m.formation_id = f.id
        JOIN departements d ON f.dept_id = d.id
        LEFT JOIN lieux_examen l ON e.lieu_id = l.id
        LEFT JOIN professeurs p ON e.prof_surveillant_id = p.id
        WHERE e.session_id = 1
    """
    params = []
    
    if selected_dept != "Tous":
        query += " AND d.id = %s"
        params.append(dept_id)
    
    if selected_formation != "Toutes":
        query += " AND f.nom = %s"
        params.append(selected_formation)
    
    if selected_date != "Toutes":
        date_obj = datetime.strptime(selected_date, '%d/%m/%Y').date()
        query += " AND e.date_examen = %s"
        params.append(date_obj)
    
    query += " ORDER BY e.date_examen, e.heure_debut"
    
    schedule = db.execute_to_dataframe(query, tuple(params) if params else None)
    
    if schedule.empty:
        st.info("🔭 Aucun examen trouvé avec ces critères")
    else:
        # Statistiques
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📝 Examens", len(schedule))
        with col2:
            dates_uniques = schedule['date_examen'].nunique()
            st.metric("📅 Jours", dates_uniques)
        with col3:
            formations_uniques = schedule['formation'].nunique()
            st.metric("🎓 Formations", formations_uniques)
        with col4:
            total_etudiants = schedule['nb_inscrits'].sum()
            st.metric("👥 Total inscrits", f"{total_etudiants:,}")
        
        st.markdown("---")
        
        # Affichage selon le mode
        if view_mode == "📅 Calendrier":
            display_schedule_calendar_view(schedule)
        
        elif view_mode == "📋 Tableau":
            st.markdown("### 📋 Vue Tableau")
            display_schedule_table_view(schedule)
        
        else:  # Chronologie
            st.markdown("### 📊 Vue Chronologique")
            
            df = schedule.copy()
            df['date_examen'] = pd.to_datetime(df['date_examen'])
            
            fig = px.timeline(
                df,
                x_start='date_examen',
                x_end='date_examen',
                y='formation',
                color='departement',
                hover_data=['code_module', 'lieu', 'heure_debut', 'nb_inscrits'],
                title="Répartition des examens par formation"
            )
            fig.update_layout(height=max(400, len(df['formation'].unique()) * 30))
            st.plotly_chart(fig, use_container_width=True)

def show_professor_interface():
    """Interface professeur améliorée"""
    st.sidebar.markdown(f"### 👨‍🏫 {st.session_state.user_name}")
    st.sidebar.markdown(f"**Rôle:** Professeur")
    
    # Mode d'affichage
    st.sidebar.markdown("---")
    view_mode = st.sidebar.radio(
        "👁️ Mode d'affichage",
        ["📅 Calendrier", "📋 Liste", "📊 Statistiques"],
        key="prof_view"
    )
    
    if st.sidebar.button("🚪 Déconnexion"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    st.markdown('<div class="main-header">📋 Mes Surveillances d\'Examens</div>', unsafe_allow_html=True)
    
    # Récupérer le planning
    schedule = db.get_professor_schedule(st.session_state.user_id, st.session_state.session_exam_id)
    
    if schedule.empty:
        st.info("🔭 Aucune surveillance planifiée pour le moment")
    else:
        # Statistiques
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("👁️ Surveillances", len(schedule))
        with col2:
            dates_uniques = schedule['date_examen'].nunique()
            st.metric("📅 Jours", dates_uniques)
        with col3:
            max_par_jour = schedule.groupby('date_examen').size().max()
            st.metric("📊 Max/jour", int(max_par_jour))
        with col4:
            total_etudiants = schedule['nb_inscrits'].sum()
            st.metric("👥 Étudiants surveillés", f"{total_etudiants:,}")
        
        st.markdown("---")
        
        if view_mode == "📅 Calendrier":
            display_schedule_calendar_view(schedule)
        
        elif view_mode == "📋 Liste":
            st.markdown("### 📋 Liste des surveillances")
            display_schedule_table_view(schedule)
        
        else:  # Statistiques
            st.markdown("### 📊 Mes Statistiques")
            
            # Distribution par jour
            daily_count = schedule.groupby('date_examen').size().reset_index(name='Nombre')
            daily_count['Date'] = daily_count['date_examen'].dt.strftime('%d/%m')
            
            fig = px.bar(
                daily_count,
                x='Date',
                y='Nombre',
                title="Nombre de surveillances par jour",
                color='Nombre',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Par formation
            formation_count = schedule.groupby('formation').size().reset_index(name='Nombre')
            
            fig2 = px.pie(
                formation_count,
                values='Nombre',
                names='formation',
                title="Répartition par formation"
            )
            st.plotly_chart(fig2, use_container_width=True)

def main():
    """Fonction principale"""
    init_session_state()
    
    if st.session_state.role is None:
        show_login()
    else:
        if st.session_state.role == "Étudiant":
            show_student_interface()
        elif st.session_state.role == "Professeur":
            show_professor_interface()
        else:
            # Pour les autres rôles (Vice-Doyen, Admin, Chef Dept)
            st.sidebar.markdown(f"### 👤 {st.session_state.user_name}")
            st.sidebar.markdown(f"**Rôle:** {st.session_state.role}")
            
            if st.sidebar.button("🚪 Déconnexion"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
            
            st.markdown('<div class="main-header">🎓 Plateforme Num_Exam</div>', unsafe_allow_html=True)
            st.markdown("### Bienvenue sur la plateforme de gestion des emplois du temps d'examens")
            
            st.info("👈 Utilisez le menu latéral pour accéder aux différentes fonctionnalités")
            
            # Dashboard selon le rôle
            try:
                kpis = db.get_global_kpis()
                
                st.markdown("### 📊 Vue d'ensemble")
                
                col1, col2, col3, col4 = st.columns(4)
                
                total_examens = int(kpis['nb_examens_planifies'].sum())
                total_etudiants = int(kpis['nb_etudiants'].sum())
                total_modules = int(kpis['nb_modules_total'].sum())
                total_conflits = int(kpis['nb_conflits_non_resolus'].sum())
                
                with col1:
                    st.metric("📝 Examens planifiés", f"{total_examens:,}")
                with col2:
                    st.metric("👨‍🎓 Étudiants", f"{total_etudiants:,}")
                with col3:
                    st.metric("📚 Modules", f"{total_modules}")
                with col4:
                    color = "normal" if total_conflits == 0 else "inverse"
                    st.metric("⚠️ Conflits", f"{total_conflits}", delta_color=color)
                
                st.markdown("---")
                
                # Graphiques
                col1, col2 = st.columns(2)
                
                with col1:
                    fig = px.bar(
                        kpis,
                        x='departement',
                        y='nb_examens_planifies',
                        title="Examens par département",
                        color='nb_examens_planifies',
                        color_continuous_scale='Blues'
                    )
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    fig = px.pie(
                        kpis,
                        values='nb_etudiants',
                        names='departement',
                        title="Répartition des étudiants"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.warning(f"Impossible de charger les statistiques: {e}")

if __name__ == "__main__":
    main()
