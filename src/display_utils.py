"""
Utilitaires d'affichage pour les emplois du temps
Fonctions réutilisables dans toute l'application
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

def format_schedule_dataframe(df):
    """
    Formater un DataFrame de planning pour l'affichage
    
    Args:
        df: DataFrame avec colonnes date_examen, heure_debut, etc.
    
    Returns:
        DataFrame formaté pour affichage
    """
    if df.empty:
        return df
    
    display_df = df.copy()
    
    # Formater les dates
    if 'date_examen' in display_df.columns:
        display_df['date_examen'] = pd.to_datetime(display_df['date_examen'])
        display_df['Date'] = display_df['date_examen'].dt.strftime('%d/%m/%Y')
        display_df['Jour'] = display_df['date_examen'].dt.strftime('%A')
    
    # Formater les heures
    if 'heure_debut' in display_df.columns:
        display_df['Heure'] = display_df['heure_debut'].astype(str).str[:5]
    
    # Formater la durée
    if 'duree_minutes' in display_df.columns:
        display_df['Durée'] = display_df['duree_minutes'].astype(str) + ' min'
    
    return display_df


def display_exam_card(exam_data, show_students=True):
    """
    Afficher une carte d'examen stylisée
    
    Args:
        exam_data: Dict ou Series avec les infos de l'examen
        show_students: Afficher le nombre d'étudiants
    """
    code = exam_data.get('code_module', 'N/A')
    nom = exam_data.get('nom_module', exam_data.get('formation', ''))
    lieu = exam_data.get('lieu', 'Non défini')
    nb_inscrits = exam_data.get('nb_inscrits', 0)
    duree = exam_data.get('duree_minutes', 90)
    surveillant = exam_data.get('surveillant', '')
    
    students_info = f"👥 {nb_inscrits} étudiants<br>" if show_students else ""
    surveillant_info = f"👨‍🏫 {surveillant}<br>" if surveillant else ""
    
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
                padding: 15px; border-radius: 8px; 
                border-left: 5px solid #2196f3; margin: 10px 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);'>
        <strong style='font-size: 1.1em; color: #1976d2;'>{code}</strong><br>
        <small style='color: #666;'>{nom}</small><br>
        <div style='margin-top: 8px; font-size: 0.9em;'>
            📍 {lieu}<br>
            {students_info}
            {surveillant_info}
            ⏱️ {duree} min
        </div>
    </div>
    """, unsafe_allow_html=True)


def display_statistics_cards(schedule_df):
    """
    Afficher des cartes de statistiques
    
    Args:
        schedule_df: DataFrame du planning
    """
    if schedule_df.empty:
        return
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        nb_examens = len(schedule_df)
        st.metric("📝 Examens", nb_examens)
    
    with col2:
        if 'date_examen' in schedule_df.columns:
            nb_jours = schedule_df['date_examen'].nunique()
            st.metric("📅 Jours", nb_jours)
    
    with col3:
        if 'formation' in schedule_df.columns:
            nb_formations = schedule_df['formation'].nunique()
            st.metric("🎓 Formations", nb_formations)
        elif 'lieu' in schedule_df.columns:
            nb_lieux = schedule_df['lieu'].nunique()
            st.metric("🏢 Lieux", nb_lieux)
    
    with col4:
        if 'nb_inscrits' in schedule_df.columns:
            total_inscrits = schedule_df['nb_inscrits'].sum()
            st.metric("👥 Total inscrits", f"{total_inscrits:,}")


def display_timeline_chart(schedule_df, title="Chronologie des examens"):
    """
    Afficher un graphique de timeline
    
    Args:
        schedule_df: DataFrame du planning
        title: Titre du graphique
    """
    if schedule_df.empty:
        st.info("Aucune donnée à afficher")
        return
    
    df = schedule_df.copy()
    df['date_examen'] = pd.to_datetime(df['date_examen'])
    
    # Grouper par
    group_by = 'formation' if 'formation' in df.columns else 'code_module'
    color_by = 'departement' if 'departement' in df.columns else group_by
    
    fig = px.timeline(
        df,
        x_start='date_examen',
        x_end='date_examen',
        y=group_by,
        color=color_by,
        hover_data=['code_module', 'lieu', 'heure_debut'] if 'code_module' in df.columns else None,
        title=title
    )
    
    fig.update_layout(
        height=max(400, len(df[group_by].unique()) * 30),
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)


def display_daily_distribution(schedule_df, title="Distribution par jour"):
    """
    Afficher la distribution des examens par jour
    
    Args:
        schedule_df: DataFrame du planning
        title: Titre du graphique
    """
    if schedule_df.empty:
        return
    
    df = schedule_df.copy()
    df['date_examen'] = pd.to_datetime(df['date_examen'])
    
    # Compter par jour
    daily_count = df.groupby('date_examen').size().reset_index(name='Nombre d\'examens')
    daily_count['Date'] = daily_count['date_examen'].dt.strftime('%d/%m')
    
    fig = px.bar(
        daily_count,
        x='Date',
        y='Nombre d\'examens',
        title=title,
        color='Nombre d\'examens',
        color_continuous_scale='Blues'
    )
    
    st.plotly_chart(fig, use_container_width=True)


def display_pie_chart(schedule_df, column, title=None):
    """
    Afficher un graphique en camembert
    
    Args:
        schedule_df: DataFrame du planning
        column: Colonne pour le groupement
        title: Titre du graphique
    """
    if schedule_df.empty or column not in schedule_df.columns:
        return
    
    count_df = schedule_df.groupby(column).size().reset_index(name='Nombre')
    
    if title is None:
        title = f"Répartition par {column}"
    
    fig = px.pie(
        count_df,
        values='Nombre',
        names=column,
        title=title
    )
    
    st.plotly_chart(fig, use_container_width=True)


def display_heatmap(schedule_df, title="Occupation par jour et créneau"):
    """
    Afficher une heatmap de l'occupation
    
    Args:
        schedule_df: DataFrame du planning
        title: Titre du graphique
    """
    if schedule_df.empty:
        return
    
    df = schedule_df.copy()
    df['date_examen'] = pd.to_datetime(df['date_examen'])
    df['Date'] = df['date_examen'].dt.strftime('%d/%m')
    df['Créneau'] = df['heure_debut'].astype(str).str[:5]
    
    # Créer une matrice de comptage
    heatmap_data = df.groupby(['Date', 'Créneau']).size().reset_index(name='Nombre')
    pivot_table = heatmap_data.pivot(index='Créneau', columns='Date', values='Nombre').fillna(0)
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot_table.values,
        x=pivot_table.columns,
        y=pivot_table.index,
        colorscale='Blues',
        text=pivot_table.values,
        texttemplate='%{text}',
        textfont={"size": 12}
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Créneau horaire",
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)


def export_to_csv(dataframe, filename="export.csv"):
    """
    Créer un bouton d'export CSV
    
    Args:
        dataframe: DataFrame à exporter
        filename: Nom du fichier
    """
    if dataframe.empty:
        return
    
    csv = dataframe.to_csv(index=False, encoding='utf-8-sig')
    
    st.download_button(
        label="📥 Télécharger en CSV",
        data=csv,
        file_name=filename,
        mime="text/csv",
        use_container_width=True
    )


def display_conflict_alert(nb_conflicts, severity="warning"):
    """
    Afficher une alerte de conflits
    
    Args:
        nb_conflicts: Nombre de conflits
        severity: "info", "warning", "error"
    """
    if nb_conflicts == 0:
        st.success("✅ Aucun conflit détecté")
        return
    
    if severity == "error":
        st.error(f"❌ {nb_conflicts} conflit(s) critique(s) détecté(s)")
    elif severity == "warning":
        st.warning(f"⚠️ {nb_conflicts} conflit(s) détecté(s)")
    else:
        st.info(f"ℹ️ {nb_conflicts} conflit(s) mineur(s) détecté(s)")


def display_progress_indicator(current, total, message=""):
    """
    Afficher un indicateur de progression
    
    Args:
        current: Valeur actuelle
        total: Valeur totale
        message: Message à afficher
    """
    progress = current / total if total > 0 else 0
    percentage = int(progress * 100)
    
    st.progress(progress, text=f"{message} {percentage}%")


def display_quality_score(stats):
    """
    Afficher un score de qualité du planning
    
    Args:
        stats: Dict avec les statistiques (conflits, taux_remplissage, etc.)
    """
    # Calculer le score
    score = 100
    
    # Pénalités
    score -= stats.get('nb_conflits_etudiants', 0) * 5
    score -= stats.get('nb_conflits_profs', 0) * 3
    score -= stats.get('nb_conflits_capacite', 0) * 10
    
    # Bonus pour bon taux de remplissage
    taux_remplissage = stats.get('taux_remplissage', 0)
    if taux_remplissage > 95:
        score += 10
    elif taux_remplissage < 70:
        score -= 20
    
    score = max(0, min(100, score))
    
    # Affichage
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if score >= 90:
            st.success(f"🌟 **Score de Qualité: {score}/100** - Excellent!")
        elif score >= 70:
            st.info(f"👍 **Score de Qualité: {score}/100** - Bon")
        elif score >= 50:
            st.warning(f"⚠️ **Score de Qualité: {score}/100** - Acceptable")
        else:
            st.error(f"❌ **Score de Qualité: {score}/100** - Insuffisant")
        
        # Barre de progression
        progress_color = "green" if score >= 70 else "orange" if score >= 50 else "red"
        st.progress(score / 100)


def display_calendar_grid(schedule_df, show_details=True):
    """
    Afficher une grille calendrier avec créneaux horaires
    
    Args:
        schedule_df: DataFrame du planning
        show_details: Afficher les détails de chaque examen
    """
    if schedule_df.empty:
        st.info("Aucun examen à afficher")
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
                        st.markdown("_Libre_")
                    else:
                        for _, examen in examens_creneau.iterrows():
                            if show_details:
                                display_exam_card(examen)
                            else:
                                st.markdown(f"• {examen.get('code_module', 'N/A')}")


def display_filter_section(show_dept=True, show_formation=True, show_date=True):
    """
    Afficher une section de filtres réutilisable
    
    Args:
        show_dept: Afficher filtre département
        show_formation: Afficher filtre formation
        show_date: Afficher filtre date
    
    Returns:
        Dict avec les valeurs sélectionnées
    """
    from src.db_connection import db
    
    st.markdown("### 🔍 Filtres")
    
    cols = st.columns(3)
    filters = {}
    
    if show_dept:
        with cols[0]:
            depts = db.get_departments()
            dept_options = ["Tous"] + [f"{row['code']} - {row['nom']}" for _, row in depts.iterrows()]
            selected_dept = st.selectbox("Département", dept_options, key="filter_dept")
            filters['departement'] = selected_dept
            
            if selected_dept != "Tous":
                dept_idx = dept_options.index(selected_dept) - 1
                filters['dept_id'] = depts.iloc[dept_idx]['id']
    
    if show_formation:
        with cols[1]:
            if 'dept_id' in filters:
                formations = db.get_formations_by_department(filters['dept_id'])
                formation_options = ["Toutes"] + formations['nom'].tolist()
            else:
                formations = db.execute_to_dataframe("SELECT DISTINCT nom FROM formations ORDER BY nom")
                formation_options = ["Toutes"] + formations['nom'].tolist()
            
            selected_formation = st.selectbox("Formation", formation_options, key="filter_formation")
            filters['formation'] = selected_formation
    
    if show_date:
        with cols[2]:
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
            
            selected_date = st.selectbox("Date", date_options, key="filter_date")
            filters['date'] = selected_date
    
    return filters
