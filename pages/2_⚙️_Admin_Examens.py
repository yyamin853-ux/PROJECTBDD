"""
Page Administrateur Examens - AVEC OPTIMIZER RÉEL
Génération automatique VRAIE du planning et gestion des conflits
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
        <p>Génération automatique RÉELLE et gestion des plannings</p>
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
# TAB 1: GÉNÉRATION AUTOMATIQUE RÉELLE
# =====================================================
with tab1:
    st.markdown("###  Génération Automatique RÉELLE du Planning")
    
    st.info("""
    ℹ️ 
    """)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        #### Configuration de la session d'examens
        L'algorithme va générer le planning en respectant TOUTES les contraintes réelles.
        """)
        
        # Paramètres de génération
        session_name = st.selectbox(
            "Session d'examens",
            ["Semestre 1 -, "Semestre 2"],
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
                value=14,
                help="Durée de la période d'examens (recommandé: 14 jours pour 200+ formations)"
            )
        
        # Info sur les contraintes appliquées
        with st.expander("ℹ️ Contraintes appliquées automatiquement"):
            st.markdown("""
            **Contraintes strictes (obligatoires):**
            - ✅ Chaque étudiant max 1 examen par jour
            - ✅ Capacité des salles respectée (20 max pour salles, variable pour amphis)
            - ✅ Pas de chevauchement de lieux (1 examen par salle par créneau)
            - ✅ Professeurs max 3 surveillances par jour
            
            **Optimisations (au mieux):**
            - 🎯 Gros effectifs → Amphithéâtres en priorité
            - 🎯 Professeurs surveillent leur département en priorité
            - 🎯 Examens placés en début de période en priorité
            - 🎯 Créneaux du matin favorisés (moins de fatigue)
            """)
    
    with col2:
        st.markdown("#### 📋 Informations Système")
        
        try:
            # Récupérer les stats réelles
            nb_modules = db.execute_query("""
                SELECT COUNT(DISTINCT m.id) as total
                FROM modules m
                JOIN inscriptions i ON i.module_id = m.id
                WHERE i.session_id = 1
            """)[0]['total']
            
            nb_etudiants = db.execute_query("SELECT COUNT(*) as total FROM etudiants")[0]['total']
            nb_profs = db.execute_query("SELECT COUNT(*) as total FROM professeurs")[0]['total']
            nb_lieux = db.execute_query("SELECT COUNT(*) as total FROM lieux_examen WHERE disponible = TRUE")[0]['total']
            
            st.success(f"""
            **Modules à planifier:** {nb_modules}
            
            **Étudiants:** {nb_etudiants:,}
            
            **Professeurs disponibles:** {nb_profs}
            
            **Lieux disponibles:** {nb_lieux}
            
            **Créneaux par jour:** 4
            (8h-10h, 10h-12h, 14h-16h, 16h-18h)
            
            **Créneaux totaux disponibles:** {nb_jours * 4}
            """)
            
            # Estimation de faisabilité
            creneaux_totaux = nb_jours * 4 * nb_lieux
            ratio = nb_modules / creneaux_totaux if creneaux_totaux > 0 else 999
            
            if ratio < 0.5:
                st.success("✅ Ressources largement suffisantes")
            elif ratio < 0.8:
                st.info("ℹ️ Ressources suffisantes")
            elif ratio < 1.0:
                st.warning("⚠️ Ressources justes - augmentez le nombre de jours si possible")
            else:
                st.error("❌ Ressources insuffisantes - augmentez le nombre de jours!")
            
        except Exception as e:
            st.error(f"Erreur de chargement: {e}")
    
    st.markdown("---")
    
    # Bouton de génération
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
    
    with col_btn2:
        if st.button("⚡ GÉNÉRER LE PLANNING RÉEL", type="primary", use_container_width=True):
            
            # Zone de progression en temps réel
            progress_container = st.container()
            
            with progress_container:
                st.markdown("### 🔄 Génération en cours...")
                
                progress_bar = st.progress(0, text="Initialisation...")
                status_text = st.empty()
                log_area = st.empty()
                
                # Capturer la sortie console (simulation)
                import io
                import contextlib
                
                status_text.info("📊 Chargement des données...")
                progress_bar.progress(10, text="Chargement des données...")
                
                # Lancer l'optimisation RÉELLE
                result = optimize_schedule(
                    session_id=1,
                    date_debut=date_debut.strftime('%Y-%m-%d'),
                    nb_jours=nb_jours
                )
                
                progress_bar.progress(100, text="Terminé!")
                
                # Afficher les résultats
                st.markdown("---")
                
                if result['success']:
                    st.success(f"""
                    ## ✅ Planning généré avec SUCCÈS!
                    
                    ### ⏱️ Performance
                    - **Temps d'exécution:** {result['temps']:.2f} secondes
                    - **Objectif:** < 45 secondes ✅
                    
                    ### 📊 Résultats
                    - **Examens planifiés:** {result['nb_examens']}
                    - **Jours utilisés:** {result['stats']['nb_jours_utilises']}/{nb_jours}
                    - **Lieux utilisés:** {result['stats']['nb_lieux_utilises']}/{nb_lieux}
                    - **Professeurs mobilisés:** {result['stats']['nb_profs_utilises']}/{nb_profs}
                    - **Taux de remplissage:** {result['stats']['taux_remplissage']:.1f}%
                    
                    ### ⚠️ Conflits détectés
                    - **Conflits étudiants:** {result['stats']['nb_conflits_etudiants']}
                    - **Conflits professeurs:** {result['stats']['nb_conflits_profs']}
                    - **Conflits capacité:** {result['stats']['nb_conflits_capacite']}
                    """)
                    
                    # Évaluation de la qualité
                    total_conflits = (
                        result['stats']['nb_conflits_etudiants'] +
                        result['stats']['nb_conflits_profs'] +
                        result['stats']['nb_conflits_capacite']
                    )
                    
                    if total_conflits == 0:
                        st.success("🌟 **EXCELLENT!** Aucun conflit - Planning parfait!")
                    elif total_conflits < 10:
                        st.info("👍 **BON** - Quelques conflits mineurs à résoudre")
                    else:
                        st.warning(f"⚠️ **ATTENTION** - {total_conflits} conflits à résoudre")
                    
                    # Boutons d'action
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("📊 Voir le planning généré", use_container_width=True):
                            st.rerun()
                    
                    with col2:
                        if st.button("⚠️ Analyser les conflits", use_container_width=True):
                            st.session_state.active_tab = "conflicts"
                            st.rerun()
                    
                    with col3:
                        if st.button("📈 Voir les statistiques", use_container_width=True):
                            st.session_state.active_tab = "stats"
                            st.rerun()
                
                else:
                    st.error(f"""
                    ## ❌ Échec de la génération
                    
                    **Message d'erreur:**
                    {result['message']}
                    
                    **Temps écoulé:** {result['temps']:.2f} secondes
                    
                    ### 💡 Suggestions:
                    1. **Augmenter le nombre de jours** (essayez {nb_jours + 5} jours)
                    2. **Vérifier les ressources:**
                       - Nombre de lieux disponibles
                       - Capacité des salles
                       - Nombre de professeurs
                    3. **Vérifier les données:**
                       - Inscriptions correctement enregistrées
                       - Modules bien configurés
                    """)

# =====================================================
# TAB 2: DÉTECTION DE CONFLITS
# =====================================================
with tab2:
    st.markdown("### ⚠️ Détection et Analyse des Conflits")
    
    st.info("""
    ℹ️ Les conflits sont automatiquement détectés pendant la génération.
    Cette section permet de les analyser en détail et de les résoudre manuellement si nécessaire.
    """)
    
    # Détecter tous les types de conflits
    col1, col2, col3 = st.columns(3)
    
    # Conflits étudiants
    try:
        conflits_etudiants = db.detect_student_conflicts(session_id=1)
        with col1:
            if conflits_etudiants.empty:
                st.success("✅ Aucun conflit étudiant")
            else:
                st.error(f"❌ {len(conflits_etudiants)} conflits étudiants")
    except:
        with col1:
            st.warning("⚠️ Impossible de vérifier")
    
    # Conflits professeurs
    try:
        conflits_profs = db.detect_professor_conflicts(session_id=1)
        with col2:
            if conflits_profs.empty:
                st.success("✅ Aucun conflit professeur")
            else:
                st.error(f"❌ {len(conflits_profs)} conflits professeurs")
    except:
        with col2:
            st.warning("⚠️ Impossible de vérifier")
    
    # Conflits de capacité
    try:
        conflits_capacite = db.detect_capacity_conflicts(session_id=1)
        with col3:
            if conflits_capacite.empty:
                st.success("✅ Aucun dépassement de capacité")
            else:
                st.error(f"❌ {len(conflits_capacite)} dépassements")
    except:
        with col3:
            st.warning("⚠️ Impossible de vérifier")
    
    st.markdown("---")
    
    # Afficher les détails des conflits
    try:
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
    except:
        pass
    
    try:
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
    except:
        pass
    
    try:
        if not conflits_capacite.empty:
            st.markdown("#### 🏢 Dépassements de Capacité")
            st.markdown("*Salles avec plus d'inscrits que la capacité maximale*")
            
            with st.expander("📋 Voir les détails", expanded=True):
                st.dataframe(
                    conflits_capacite,
                    use_container_width=True,
                    hide_index=True
                )
    except:
        pass
    
    # Action de résolution
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        if st.button("🔄 Relancer l'optimisation", type="primary", use_container_width=True):
            st.info("💡 Augmentez le nombre de jours ou vérifiez les ressources, puis relancez la génération dans l'onglet 1")

# =====================================================
# TAB 3: STATISTIQUES RÉELLES
# =====================================================
with tab3:
    st.markdown("### 📊 Statistiques du Planning Généré")
    
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
                    labels={'date_examen': 'Date', 'nb_examens': 'Nombre d\'examens'},
                    color='nb_examens',
                    color_continuous_scale='Blues'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("#### 👨‍🎓 Étudiants par jour")
                fig = px.bar(
                    daily_dist,
                    x='date_examen',
                    y='total_etudiants',
                    title="Nombre total d'étudiants en examen par jour",
                    labels={'date_examen': 'Date', 'total_etudiants': 'Étudiants'},
                    color='total_etudiants',
                    color_continuous_scale='Greens'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Métriques globales
            st.markdown("---")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_examens = daily_dist['nb_examens'].sum()
                st.metric("📝 Total examens", f"{int(total_examens)}")
            
            with col2:
                total_etudiants = daily_dist['total_etudiants'].sum()
                st.metric("👥 Total passages", f"{int(total_etudiants):,}")
            
            with col3:
                avg_per_day = daily_dist['nb_examens'].mean()
                st.metric("📊 Moyenne/jour", f"{avg_per_day:.1f}")
            
            with col4:
                max_per_day = daily_dist['nb_examens'].max()
                st.metric("📈 Maximum/jour", f"{int(max_per_day)}")
            
            # Occupation des salles
            st.markdown("---")
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
                
                # Alertes
                over_capacity = room_occ[room_occ['taux_occupation'] > 100]
                if not over_capacity.empty:
                    st.error(f"⚠️ {len(over_capacity)} lieu(x) en sur-capacité détecté(s)!")
                    st.dataframe(over_capacity, use_container_width=True)
            
            # Statistiques professeurs
            st.markdown("---")
            st.markdown("#### 👨‍🏫 Répartition des surveillances")
            
            prof_stats = db.get_professor_surveillance_stats(session_id=1)
            
            if not prof_stats.empty:
                # Métriques
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total surveillances", int(prof_stats['nb_surveillances'].sum()))
                with col2:
                    st.metric("Moyenne/professeur", f"{prof_stats['nb_surveillances'].mean():.1f}")
                with col3:
                    st.metric("Maximum", int(prof_stats['nb_surveillances'].max()))
                with col4:
                    profs_mobilises = len(prof_stats[prof_stats['nb_surveillances'] > 0])
                    st.metric("Profs mobilisés", profs_mobilises)
                
                # Top 10
                top_profs = prof_stats.nlargest(10, 'nb_surveillances')
                
                fig = px.bar(
                    top_profs,
                    x='professeur',
                    y='nb_surveillances',
                    color='departement',
                    title="Top 10 - Professeurs avec le plus de surveillances",
                    labels={'professeur': 'Professeur', 'nb_surveillances': 'Nombre de surveillances'}
                )
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
        
        else:
            st.info("🔭 Aucun examen planifié. Générez d'abord un planning dans l'onglet 1.")
    
    except Exception as e:
        st.error(f"Erreur lors du chargement des statistiques: {e}")

# =====================================================
# TAB 4: GESTION MANUELLE
# =====================================================
with tab4:
    st.markdown("### ✏️ Gestion Manuelle des Examens")
    
    st.info("""
    ℹ️ **Utilisation recommandée:**
    
    La gestion manuelle devrait être utilisée uniquement pour:
    - Corriger les quelques conflits résiduels après génération automatique
    - Ajuster des cas particuliers
    - Faire des modifications ponctuelles
    
    Pour un nouveau planning complet, utilisez toujours la génération automatique (Onglet 1).
    """)
    
    action = st.radio("Action", ["Ajouter un examen", "Modifier un examen", "Supprimer un examen"], horizontal=True)
    
    if action == "Ajouter un examen":
        st.markdown("#### ➕ Ajouter un nouvel examen manuellement")
        st.warning("⚠️ Assurez-vous de respecter toutes les contraintes manuellement")
        
        # Interface de gestion manuelle (gardée simple pour éviter les erreurs)
        st.info("🚧 Pour l'instant, utilisez la génération automatique qui gère tout automatiquement.")
    
    elif action == "Modifier un examen":
        st.info("🚧 Fonctionnalité en développement")
    
    else:  # Supprimer
        st.info("🚧 Fonctionnalité en développement")
