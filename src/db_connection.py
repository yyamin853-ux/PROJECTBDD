"""
Gestionnaire de connexion à la base de données - VERSION CORRIGÉE
Gère la conversion des types numpy en types Python
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
from contextlib import contextmanager
import os
from dotenv import load_dotenv

load_dotenv()

def convert_numpy_to_python(params):
    """Convertir les types numpy en types Python standards"""
    if params is None:
        return None
    
    if isinstance(params, (list, tuple)):
        converted = []
        for p in params:
            if hasattr(p, 'item'):  # Type numpy (int64, float64, etc.)
                try:
                    converted.append(int(p))
                except (ValueError, TypeError):
                    converted.append(float(p))
            else:
                converted.append(p)
        return tuple(converted)
    elif hasattr(params, 'item'):  # Type numpy unique
        try:
            return (int(params),)
        except (ValueError, TypeError):
            return (float(params),)
    
    return params

class DatabaseManager:
    """Classe pour gérer les connexions et requêtes à la base de données"""
    
    def __init__(self):
        self.config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'database': os.getenv('DB_NAME', 'num_exam_db'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'password'),
            'port': os.getenv('DB_PORT', '5432')
        }
    
    @contextmanager
    def get_connection(self):
        """Context manager pour gérer les connexions"""
        conn = psycopg2.connect(**self.config)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def execute_query(self, query, params=None, fetch=True):
        """Exécuter une requête SQL"""
        params = convert_numpy_to_python(params)
        
        with self.get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query, params)
            
            if fetch:
                return cursor.fetchall()
            return None
    
    def execute_to_dataframe(self, query, params=None):
        """Exécuter une requête et retourner un DataFrame pandas"""
        params = convert_numpy_to_python(params)
        
        with self.get_connection() as conn:
            return pd.read_sql(query, conn, params=params)
    
    def execute_many(self, query, data):
        """Exécuter une requête pour plusieurs enregistrements"""
        # Convertir chaque ligne de données
        converted_data = []
        for row in data:
            if isinstance(row, (list, tuple)):
                converted_row = tuple(
                    int(p) if hasattr(p, 'item') else p 
                    for p in row
                )
                converted_data.append(converted_row)
            else:
                converted_data.append(row)
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(query, converted_data)
    
    # =====================================================
    # REQUÊTES SPÉCIFIQUES - ÉTUDIANTS
    # =====================================================
    
    def get_student_schedule(self, etudiant_id, session_id=1):
        """Récupérer le planning d'un étudiant"""
        etudiant_id = int(etudiant_id) if hasattr(etudiant_id, 'item') else etudiant_id
        session_id = int(session_id) if hasattr(session_id, 'item') else session_id
        
        query = """
            SELECT 
                e.date_examen,
                e.heure_debut,
                e.duree_minutes,
                m.code as code_module,
                m.nom as nom_module,
                l.nom as lieu,
                l.type as type_lieu,
                CONCAT(p.nom, ' ', p.prenom) as surveillant
            FROM inscriptions i
            JOIN examens e ON i.module_id = e.module_id
            JOIN modules m ON e.module_id = m.id
            LEFT JOIN lieux_examen l ON e.lieu_id = l.id
            LEFT JOIN professeurs p ON e.prof_surveillant_id = p.id
            WHERE i.etudiant_id = %s 
              AND e.session_id = %s
            ORDER BY e.date_examen, e.heure_debut
        """
        return self.execute_to_dataframe(query, (etudiant_id, session_id))
    
    def search_students(self, search_term, limit=50):
        """Rechercher des étudiants par nom/prénom/matricule"""
        query = """
            SELECT 
                e.id,
                e.matricule,
                e.nom,
                e.prenom,
                f.nom as formation,
                d.nom as departement
            FROM etudiants e
            JOIN formations f ON e.formation_id = f.id
            JOIN departements d ON f.dept_id = d.id
            WHERE 
                e.nom ILIKE %s OR 
                e.prenom ILIKE %s OR 
                e.matricule ILIKE %s
            LIMIT %s
        """
        pattern = f"%{search_term}%"
        return self.execute_to_dataframe(query, (pattern, pattern, pattern, limit))
    
    # =====================================================
    # REQUÊTES SPÉCIFIQUES - PROFESSEURS
    # =====================================================
    
    def get_professor_schedule(self, prof_id, session_id=1):
        """Récupérer le planning de surveillance d'un professeur"""
        prof_id = int(prof_id) if hasattr(prof_id, 'item') else prof_id
        session_id = int(session_id) if hasattr(session_id, 'item') else session_id
        
        query = """
            SELECT 
                e.date_examen,
                e.heure_debut,
                e.duree_minutes,
                m.code as code_module,
                m.nom as nom_module,
                l.nom as lieu,
                e.nb_inscrits,
                f.nom as formation
            FROM examens e
            JOIN modules m ON e.module_id = m.id
            JOIN formations f ON m.formation_id = f.id
            LEFT JOIN lieux_examen l ON e.lieu_id = l.id
            WHERE e.prof_surveillant_id = %s 
              AND e.session_id = %s
            ORDER BY e.date_examen, e.heure_debut
        """
        return self.execute_to_dataframe(query, (prof_id, session_id))
    
    def get_professor_surveillance_stats(self, session_id=1):
        """Statistiques de surveillance par professeur"""
        session_id = int(session_id) if hasattr(session_id, 'item') else session_id
        
        query = """
            SELECT 
                p.id,
                CONCAT(p.nom, ' ', p.prenom) as professeur,
                d.nom as departement,
                COUNT(e.id) as nb_surveillances,
                p.max_surveillance_jour,
                MAX(daily.nb_jour) as max_par_jour
            FROM professeurs p
            JOIN departements d ON p.dept_id = d.id
            LEFT JOIN examens e ON e.prof_surveillant_id = p.id AND e.session_id = %s
            LEFT JOIN LATERAL (
                SELECT COUNT(*) as nb_jour
                FROM examens e2
                WHERE e2.prof_surveillant_id = p.id 
                  AND e2.session_id = %s
                GROUP BY e2.date_examen
                ORDER BY COUNT(*) DESC
                LIMIT 1
            ) daily ON TRUE
            GROUP BY p.id, p.nom, p.prenom, d.nom, p.max_surveillance_jour
            ORDER BY nb_surveillances DESC
        """
        return self.execute_to_dataframe(query, (session_id, session_id))
    
    # =====================================================
    # REQUÊTES SPÉCIFIQUES - DÉPARTEMENTS
    # =====================================================
    
    def get_department_stats(self, dept_id, session_id=1):
        """Statistiques d'un département"""
        dept_id = int(dept_id) if hasattr(dept_id, 'item') else dept_id
        session_id = int(session_id) if hasattr(session_id, 'item') else session_id
        
        query = """
            SELECT 
                COUNT(DISTINCT f.id) as nb_formations,
                COUNT(DISTINCT m.id) as nb_modules,
                COUNT(DISTINCT et.id) as nb_etudiants,
                COUNT(DISTINCT e.id) as nb_examens_planifies,
                COUNT(DISTINCT CASE WHEN c.resolu = FALSE THEN c.id END) as nb_conflits
            FROM departements d
            LEFT JOIN formations f ON f.dept_id = d.id
            LEFT JOIN modules m ON m.formation_id = f.id
            LEFT JOIN etudiants et ON et.formation_id = f.id
            LEFT JOIN examens e ON e.module_id = m.id AND e.session_id = %s
            LEFT JOIN conflits_detectes c ON c.examen_id = e.id
            WHERE d.id = %s
            GROUP BY d.id
        """
        result = self.execute_query(query, (session_id, dept_id))
        return result[0] if result else None
    
    def get_department_schedule(self, dept_id, session_id=1):
        """Planning complet d'un département"""
        dept_id = int(dept_id) if hasattr(dept_id, 'item') else dept_id
        session_id = int(session_id) if hasattr(session_id, 'item') else session_id
        
        query = """
            SELECT 
                e.date_examen,
                e.heure_debut,
                e.duree_minutes,
                m.code as code_module,
                m.nom as nom_module,
                f.nom as formation,
                l.nom as lieu,
                e.nb_inscrits,
                CONCAT(p.nom, ' ', p.prenom) as surveillant,
                e.statut
            FROM examens e
            JOIN modules m ON e.module_id = m.id
            JOIN formations f ON m.formation_id = f.id
            LEFT JOIN lieux_examen l ON e.lieu_id = l.id
            LEFT JOIN professeurs p ON e.prof_surveillant_id = p.id
            WHERE f.dept_id = %s 
              AND e.session_id = %s
            ORDER BY e.date_examen, e.heure_debut
        """
        return self.execute_to_dataframe(query, (dept_id, session_id))
    
    # =====================================================
    # REQUÊTES SPÉCIFIQUES - VICE-DOYEN (VUES GLOBALES)
    # =====================================================
    
    def get_global_kpis(self):
        """KPIs globaux de la faculté"""
        query = "SELECT * FROM vue_kpis_globaux ORDER BY departement"
        return self.execute_to_dataframe(query)
    
    def get_room_occupation(self, session_id=1):
        """Taux d'occupation des salles"""
        session_id = int(session_id) if hasattr(session_id, 'item') else session_id
        
        query = """
            SELECT 
                date_examen,
                lieu,
                type,
                nb_examens,
                total_etudiants,
                capacite_examen,
                taux_occupation
            FROM vue_occupation_salles
            WHERE date_examen IN (
                SELECT DISTINCT date_examen 
                FROM examens 
                WHERE session_id = %s
            )
            ORDER BY date_examen, taux_occupation DESC
        """
        return self.execute_to_dataframe(query, (session_id,))
    
    def get_daily_exam_distribution(self, session_id=1):
        """Distribution des examens par jour"""
        session_id = int(session_id) if hasattr(session_id, 'item') else session_id
        
        query = """
            SELECT 
                date_examen,
                COUNT(*) as nb_examens,
                SUM(nb_inscrits) as total_etudiants,
                COUNT(DISTINCT lieu_id) as nb_lieux_utilises
            FROM examens
            WHERE session_id = %s
            GROUP BY date_examen
            ORDER BY date_examen
        """
        return self.execute_to_dataframe(query, (session_id,))
    
    # =====================================================
    # DÉTECTION DE CONFLITS
    # =====================================================
    
    def detect_student_conflicts(self, session_id=1):
        """Détecter les conflits étudiants (>1 examen/jour)"""
        session_id = int(session_id) if hasattr(session_id, 'item') else session_id
        query = "SELECT * FROM detecter_conflits_etudiants(%s)"
        return self.execute_to_dataframe(query, (session_id,))
    
    def detect_professor_conflicts(self, session_id=1):
        """Détecter les conflits professeurs (>3 examens/jour)"""
        session_id = int(session_id) if hasattr(session_id, 'item') else session_id
        query = "SELECT * FROM detecter_conflits_professeurs(%s)"
        return self.execute_to_dataframe(query, (session_id,))
    
    def detect_capacity_conflicts(self, session_id=1):
        """Détecter les dépassements de capacité"""
        session_id = int(session_id) if hasattr(session_id, 'item') else session_id
        query = "SELECT * FROM detecter_depassement_capacite(%s)"
        return self.execute_to_dataframe(query, (session_id,))
    
    def get_all_conflicts(self, session_id=1, resolved=False):
        """Récupérer tous les conflits détectés"""
        session_id = int(session_id) if hasattr(session_id, 'item') else session_id
        
        query = """
            SELECT 
                c.id,
                c.type_conflit,
                c.description,
                c.severite,
                c.resolu,
                c.date_detection,
                e.date_examen,
                m.code as code_module,
                m.nom as nom_module
            FROM conflits_detectes c
            JOIN examens e ON c.examen_id = e.id
            JOIN modules m ON e.module_id = m.id
            WHERE e.session_id = %s
              AND c.resolu = %s
            ORDER BY c.severite DESC, c.date_detection DESC
        """
        return self.execute_to_dataframe(query, (session_id, resolved))
    
    # =====================================================
    # GESTION DES EXAMENS
    # =====================================================
    
    def create_exam(self, module_id, session_id, date_examen, heure_debut, 
                   duree_minutes=90, lieu_id=None, prof_id=None):
        """Créer un nouvel examen"""
        # Conversion des types
        module_id = int(module_id) if hasattr(module_id, 'item') else module_id
        session_id = int(session_id) if hasattr(session_id, 'item') else session_id
        duree_minutes = int(duree_minutes) if hasattr(duree_minutes, 'item') else duree_minutes
        if lieu_id:
            lieu_id = int(lieu_id) if hasattr(lieu_id, 'item') else lieu_id
        if prof_id:
            prof_id = int(prof_id) if hasattr(prof_id, 'item') else prof_id
        
        query = """
            INSERT INTO examens 
            (module_id, session_id, date_examen, heure_debut, duree_minutes, lieu_id, prof_surveillant_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        result = self.execute_query(
            query, 
            (module_id, session_id, date_examen, heure_debut, duree_minutes, lieu_id, prof_id),
            fetch=True
        )
        return result[0]['id'] if result else None
    
    def update_exam(self, exam_id, **kwargs):
        """Mettre à jour un examen"""
        exam_id = int(exam_id) if hasattr(exam_id, 'item') else exam_id
        
        allowed_fields = ['date_examen', 'heure_debut', 'duree_minutes', 'lieu_id', 'prof_surveillant_id', 'statut']
        updates = []
        values = []
        
        for field, value in kwargs.items():
            if field in allowed_fields:
                # Convertir les types numpy
                if hasattr(value, 'item'):
                    value = int(value)
                updates.append(f"{field} = %s")
                values.append(value)
        
        if not updates:
            return False
        
        values.append(exam_id)
        query = f"UPDATE examens SET {', '.join(updates)} WHERE id = %s"
        self.execute_query(query, values, fetch=False)
        return True
    
    def delete_exam(self, exam_id):
        """Supprimer un examen"""
        exam_id = int(exam_id) if hasattr(exam_id, 'item') else exam_id
        query = "DELETE FROM examens WHERE id = %s"
        self.execute_query(query, (exam_id,), fetch=False)
        return True
    
    # =====================================================
    # UTILITAIRES
    # =====================================================
    
    def get_departments(self):
        """Liste de tous les départements"""
        query = "SELECT * FROM departements ORDER BY nom"
        return self.execute_to_dataframe(query)
    
    def get_formations_by_department(self, dept_id):
        """Formations d'un département"""
        dept_id = int(dept_id) if hasattr(dept_id, 'item') else dept_id
        
        query = """
            SELECT id, nom, code, niveau, nb_modules
            FROM formations
            WHERE dept_id = %s
            ORDER BY niveau, nom
        """
        return self.execute_to_dataframe(query, (dept_id,))
    
    def get_available_rooms(self, date_examen, heure_debut, duree_minutes, min_capacity=0):
        """Salles disponibles à une date/heure donnée"""
        duree_minutes = int(duree_minutes) if hasattr(duree_minutes, 'item') else duree_minutes
        min_capacity = int(min_capacity) if hasattr(min_capacity, 'item') else min_capacity
        
        query = """
            SELECT l.*
            FROM lieux_examen l
            WHERE l.disponible = TRUE
              AND l.capacite_examen >= %s
              AND l.id NOT IN (
                  SELECT lieu_id
                  FROM examens
                  WHERE date_examen = %s
                    AND lieu_id IS NOT NULL
                    AND (
                        (heure_debut <= %s AND heure_debut + (duree_minutes || ' minutes')::INTERVAL > %s)
                        OR
                        (heure_debut < %s + (%s || ' minutes')::INTERVAL AND heure_debut + (duree_minutes || ' minutes')::INTERVAL >= %s + (%s || ' minutes')::INTERVAL)
                    )
              )
            ORDER BY l.capacite_examen DESC
        """
        return self.execute_to_dataframe(query, (
            min_capacity, date_examen, heure_debut, heure_debut,
            heure_debut, duree_minutes, heure_debut, duree_minutes
        ))
    
    def get_available_professors(self, date_examen, dept_id=None):
        """Professeurs disponibles pour surveillance"""
        query = """
            SELECT 
                p.*,
                COALESCE(daily.nb_surveillances, 0) as surveillances_ce_jour
            FROM professeurs p
            LEFT JOIN LATERAL (
                SELECT COUNT(*) as nb_surveillances
                FROM examens e
                WHERE e.prof_surveillant_id = p.id
                  AND e.date_examen = %s
            ) daily ON TRUE
            WHERE daily.nb_surveillances < p.max_surveillance_jour
        """
        params = [date_examen]
        
        if dept_id:
            dept_id = int(dept_id) if hasattr(dept_id, 'item') else dept_id
            query += " AND p.dept_id = %s"
            params.append(dept_id)
        
        query += " ORDER BY daily.nb_surveillances, p.nom"
        
        return self.execute_to_dataframe(query, params)

# Instance globale
db = DatabaseManager()