"""
Page Administrateur Examens
Génération automatique du planning et gestion des conflits
ACCÈS RESTREINT: Administrateur Examens uniquement
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db_connection import db
from src.optimizer import optimize_schedule

st.set_page_config(
    page_title="Administration Examens - Num_Exam",
    page_icon="⚙️",
    layout="wide"
)

# ===== VÉRIFICATION D'AUTORISATION =====
def check_auth():
    """Vérifier que l'utilisateur est bien Administrateur Examens"""
    if 'role' not in st.session_state or st.session_state.role != "Administrateur Examens":
        st.error("🚫 Accès non autorisé")
        st.warning("Cette page est réservée à l'Administrateur Examens uniquement")
        st.info("Veuillez vous connecter avec les bons identifiants")
        st.stop()

check_auth()
# ========================================

# En-tête
st.markdown("""
    <div style='text-align: center; padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
         color: white; border-radius: 10px; margin-bottom: 2rem;'>
        <h1>⚙️ Administration des Examens</h1>
        <p>Génération automatique et gestion des plannings</p>
    </div>
""", unsafe_allow_html=True)

# Tabs principales
tab1, tab2, tab3, tab4 = st.tabs([
    "🚀 Génération Automatique",
    "⚠️ Détection de Conflits",
    "📊 Statistiques",
    "✏️ Gestion Manuelle"
])

# =====================================================
# TAB 1: GÉNÉRATION AUTOMATIQUE
# =====================================================
with tab1:
    st.markdown("### 🤖 Génération Automatique du Planning")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        #### Configuration de la session d'examens
        L'algorithme d'optimisation va générer automatiquement le planning en respectant toutes les contraintes.
        """)
        
        # Paramètres de génération
        session_name = st.selectbox(
            "Session d'examens",
            ["Semestre 1 - 2024/2025", "Semestre 2 - 2024/2025", "Rattrapage S1 - 2024/2025"],
            index=0
        )
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            date_debut = st.date_input(
                "📅 Date de début",
                value=date(2026, 1, 25),
                min_value=date.today()
            )
        
        with col_b:
            nb_jours = st.number_input(
                "🗓️ Nombre de jours",
                min_value=5,
                max_value=30,
                value=10,
                help="Durée de la période d'examens"
            )
        
        # Contraintes supplémentaires
        st.markdown("#### ⚙️ Contraintes")
        
        col_c1, col_c2, col_c3 = st.columns(3)
        
        with col_c1:
            max_etudiant_jour = st.number_input("Max examens/jour (étudiant)", value=1, min_value=1, max_value=3)
        
        with col_c2:
            max_prof_jour = st.number_input("Max surveillances/jour (prof)", value=3, min_value=1, max_value=5)
        
        with col_c3:
            priorite_dept = st.checkbox("Priorité département", value=True, help="Les profs surveillent prioritairement leur département")
    
    with col2:
        st.markdown("#### 📋 Informations")
        
        # Récupérer le nombre de modules à planifier
        nb_modules = db.execute_query("""
            SELECT COUNT(DISTINCT m.id) as total
            FROM modules m
            JOIN inscriptions i ON i.module_id = m.id
            WHERE i.session_id = 1
        """)[0]['total']
        
        nb_etudiants = db.execute_query("SELECT COUNT(*) as total FROM etudiants")[0]['total']
        nb_profs = db.execute_query("SELECT COUNT(*) as total FROM professeurs")[0]['total']
        nb_lieux = db.execute_query("SELECT COUNT(*) as total FROM lieux_examen WHERE disponible = TRUE")[0]['total']
        
        st.info(f"""
        **Modules à planifier:** {nb_modules}
        
        **Étudiants:** {nb_etudiants:,}
        
        **Professeurs disponibles:** {nb_profs}
        
        **Lieux disponibles:** {nb_lieux}
        
        **Créneaux par jour:** 4
        (8h-10h, 10h-12h, 14h-16h, 16h-18h)
        """)
    
    st.markdown("---")
    
    # Bouton de génération
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
    
    with col_btn2:
        if st.button("⚡ GÉNÉRER LE PLANNING", type="primary", use_container_width=True):
            with st.spinner("🔄 Optimisation en cours... Cela peut prendre jusqu'à 45 secondes"):
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                status_text.text("📊 Chargement des données...")
                progress_bar.progress(20)
                
                # Lancer l'optimisation
                result = optimize_schedule(
                    session_id=1,
                    date_debut=date_debut.strftime('%Y-%m-%d'),
                    nb_jours=nb_jours
                )
                
                progress_bar.progress(100)
                
                if result['success']:
                    st.success(f"""
                    ✅ **Planning généré avec succès!**
                    
                    - ⏱️ Temps d'exécution: {result['temps']:.2f} secondes
                    - 📝 Examens planifiés: {result['nb_examens']}
                    - 📅 Jours utilisés: {result['stats']['nb_jours_utilises']}/{nb_jours}
                    - 🏢 Lieux utilisés: {result['stats']['nb_lieux_utilises']}
                    - 👨‍🏫 Professeurs mobilisés: {result['stats']['nb_profs_utilises']}
                    """)
                    
                    # Bouton pour voir le planning
                    if st.button("📊 Voir le planning généré"):
                        st.rerun()
                else:
                    st.error(f"""
                    ❌ **Échec de la génération**
                    
                    {result['message']}
                    
                    Suggestions:
                    - Augmenter le nombre de jours
                    - Vérifier les contraintes
                    - Vérifier la disponibilité des ressources
                    """)

# =====================================================
# TAB 2: DÉTECTION DE CONFLITS
# =====================================================
with tab2:
    st.markdown("### ⚠️ Détection et Résolution des Conflits")
    
    # Détecter tous les types de conflits
    col1, col2, col3 = st.columns(3)
    
    # Conflits étudiants
    conflits_etudiants = db.detect_student_conflicts(session_id=1)
    with col1:
        if conflits_etudiants.empty:
            st.success("✅ Aucun conflit étudiant")
        else:
            st.error(f"❌ {len(conflits_etudiants)} conflits étudiants détectés")
    
    # Conflits professeurs
    conflits_profs = db.detect_professor_conflicts(session_id=1)
    with col2:
        if conflits_profs.empty:
            st.success("✅ Aucun conflit professeur")
        else:
            st.error(f"❌ {len(conflits_profs)} conflits professeurs détectés")
    
    # Conflits de capacité
    conflits_capacite = db.detect_capacity_conflicts(session_id=1)
    with col3:
        if conflits_capacite.empty:
            st.success("✅ Aucun dépassement de capacité")
        else:
            st.error(f"❌ {len(conflits_capacite)} dépassements détectés")
    
    st.markdown("---")
    
    # Afficher les détails des conflits
    if not conflits_etudiants.empty:
        st.markdown("#### 👨‍🎓 Conflits Étudiants")
        st.markdown("*Étudiants ayant plus d'un examen le même jour*")
        
        with st.expander("📋 Voir les détails", expanded=True):
            display_df = conflits_etudiants.copy()
            display_df['Date'] = pd.to_datetime(display_df['date_examen']).dt.strftime('%d/%m/%Y')
            st.dataframe(
                display_df[['etudiant_id', 'Date', 'nb_examens', 'liste_modules']],
                use_container_width=True,
                hide_index=True
            )
    
    if not conflits_profs.empty:
        st.markdown("#### 👨‍🏫 Conflits Professeurs")
        st.markdown("*Professeurs ayant plus de 3 surveillances le même jour*")
        
        with st.expander("📋 Voir les détails", expanded=True):
            display_df = conflits_profs.copy()
            display_df['Date'] = pd.to_datetime(display_df['date_examen']).dt.strftime('%d/%m/%Y')
            st.dataframe(
                display_df[['nom_professeur', 'Date', 'nb_surveillances']],
                use_container_width=True,
                hide_index=True
            )
    
    if not conflits_capacite.empty:
        st.markdown("#### 🏢 Dépassements de Capacité")
        st.markdown("*Salles avec plus d'inscrits que la capacité maximale*")
        
        with st.expander("📋 Voir les détails", expanded=True):
            st.dataframe(
                conflits_capacite,
                use_container_width=True,
                hide_index=True
            )
    
    # Action de résolution automatique
    if not conflits_etudiants.empty or not conflits_profs.empty or not conflits_capacite.empty:
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col2:
            if st.button("🔄 Relancer l'optimisation pour résoudre", type="primary", use_container_width=True):
                st.info("Relancez la génération automatique avec des paramètres ajustés")

# =====================================================
# TAB 3: STATISTIQUES
# =====================================================
with tab3:
    st.markdown("### 📊 Statistiques du Planning")
    
    try:
        # Distribution quotidienne
        daily_dist = db.get_daily_exam_distribution(session_id=1)
        
        if not daily_dist.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📅 Examens par jour")
                fig = px.bar(
                    daily_dist,
                    x='date_examen',
                    y='nb_examens',
                    title="Nombre d'examens par jour",
                    labels={'date_examen': 'Date', 'nb_examens': 'Nombre d\'examens'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("#### 👨‍🎓 Étudiants par jour")
                fig = px.bar(
                    daily_dist,
                    x='date_examen',
                    y='total_etudiants',
                    title="Nombre total d'étudiants en examen par jour",
                    labels={'date_examen': 'Date', 'total_etudiants': 'Étudiants'}
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Occupation des salles
            st.markdown("#### 🏢 Taux d'occupation des lieux")
            
            room_occ = db.get_room_occupation(session_id=1)
            
            if not room_occ.empty:
                fig = px.bar(
                    room_occ,
                    x='lieu',
                    y='taux_occupation',
                    color='type',
                    title="Taux d'occupation par lieu",
                    labels={'lieu': 'Lieu', 'taux_occupation': 'Taux d\'occupation (%)'}
                )
                fig.add_hline(y=100, line_dash="dash", line_color="red", annotation_text="Capacité maximale")
                st.plotly_chart(fig, use_container_width=True)
                
                # Lieux sur-utilisés
                over_capacity = room_occ[room_occ['taux_occupation'] > 100]
                if not over_capacity.empty:
                    st.warning(f"⚠️ {len(over_capacity)} lieu(x) en sur-capacité détecté(s)")
            
            # Statistiques professeurs
            st.markdown("#### 👨‍🏫 Répartition des surveillances")
            
            prof_stats = db.get_professor_surveillance_stats(session_id=1)
            
            if not prof_stats.empty:
                # Top 10 professeurs avec le plus de surveillances
                top_profs = prof_stats.nlargest(10, 'nb_surveillances')
                
                fig = px.bar(
                    top_profs,
                    x='professeur',
                    y='nb_surveillances',
                    color='departement',
                    title="Top 10 - Professeurs avec le plus de surveillances",
                    labels={'professeur': 'Professeur', 'nb_surveillances': 'Nombre de surveillances'}
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Stats globales
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total surveillances", int(prof_stats['nb_surveillances'].sum()))
                with col2:
                    st.metric("Moyenne/professeur", f"{prof_stats['nb_surveillances'].mean():.1f}")
                with col3:
                    st.metric("Maximum", int(prof_stats['nb_surveillances'].max()))
                with col4:
                    st.metric("Minimum", int(prof_stats['nb_surveillances'].min()))
        
        else:
            st.info("🔭 Aucun examen planifié pour le moment. Générez d'abord un planning.")
    
    except Exception as e:
        st.error(f"Erreur lors du chargement des statistiques: {e}")

# =====================================================
# TAB 4: GESTION MANUELLE
# =====================================================
with tab4:
    st.markdown("### ✏️ Gestion Manuelle des Examens")
    
    action = st.radio("Action", ["Ajouter un examen", "Modifier un examen", "Supprimer un examen"], horizontal=True)
    
    if action == "Ajouter un examen":
        st.markdown("#### ➕ Ajouter un nouvel examen")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Sélection du département
            depts = db.get_departments()
            dept_selected = st.selectbox(
                "Département",
                options=depts['id'].tolist(),
                format_func=lambda x: depts[depts['id']==x]['nom'].values[0]
            )
            
            # Sélection de la formation
            formations = db.get_formations_by_department(dept_selected)
            if not formations.empty:
                formation_selected = st.selectbox(
                    "Formation",
                    options=formations['id'].tolist(),
                    format_func=lambda x: formations[formations['id']==x]['nom'].values[0]
                )
                
                # Sélection du module
                modules = db.execute_to_dataframe("""
                    SELECT id, code, nom FROM modules WHERE formation_id = %s
                """, (formation_selected,))
                
                if not modules.empty:
                    module_selected = st.selectbox(
                        "Module",
                        options=modules['id'].tolist(),
                        format_func=lambda x: f"{modules[modules['id']==x]['code'].values[0]} - {modules[modules['id']==x]['nom'].values[0]}"
                    )
        
        with col2:
            date_exam = st.date_input("Date de l'examen", value=date.today())
            heure_exam = st.time_input("Heure de début", value=datetime.strptime("08:00", "%H:%M").time())
            duree = st.number_input("Durée (minutes)", value=90, min_value=30, max_value=240, step=30)
        
        col3, col4 = st.columns(2)
        
        with col3:
            # Sélection du lieu
            nb_inscrits = db.execute_query("""
                SELECT COUNT(*) as nb FROM inscriptions WHERE module_id = %s AND session_id = 1
            """, (module_selected,))[0]['nb']
            
            lieux_dispo = db.get_available_rooms(date_exam, heure_exam, duree, nb_inscrits)
            
            if not lieux_dispo.empty:
                lieu_selected = st.selectbox(
                    f"Lieu (min. {nb_inscrits} places)",
                    options=lieux_dispo['id'].tolist(),
                    format_func=lambda x: f"{lieux_dispo[lieux_dispo['id']==x]['nom'].values[0]} ({lieux_dispo[lieux_dispo['id']==x]['capacite_examen'].values[0]} places)"
                )
            else:
                st.error("❌ Aucun lieu disponible avec capacité suffisante")
                lieu_selected = None
        
        with col4:
            # Sélection du professeur
            profs_dispo = db.get_available_professors(date_exam, dept_selected)
            
            if not profs_dispo.empty:
                prof_selected = st.selectbox(
                    "Surveillant",
                    options=profs_dispo['id'].tolist(),
                    format_func=lambda x: f"{profs_dispo[profs_dispo['id']==x]['nom'].values[0]} {profs_dispo[profs_dispo['id']==x]['prenom'].values[0]} ({int(profs_dispo[profs_dispo['id']==x]['surveillances_ce_jour'].values[0])} ce jour)"
                )
            else:
                st.error("❌ Aucun professeur disponible")
                prof_selected = None
        
        if st.button("➕ Ajouter l'examen", type="primary"):
            if lieu_selected and prof_selected:
                try:
                    exam_id = db.create_exam(
                        module_id=module_selected,
                        session_id=1,
                        date_examen=date_exam,
                        heure_debut=heure_exam,
                        duree_minutes=duree,
                        lieu_id=lieu_selected,
                        prof_id=prof_selected
                    )
                    st.success(f"✅ Examen créé avec succès (ID: {exam_id})")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Erreur: {e}")
    
    elif action == "Modifier un examen":
        st.info("🚧 Fonctionnalité en développement")
    
    else:  # Supprimer
        st.info("🚧 Fonctionnalité en développement")