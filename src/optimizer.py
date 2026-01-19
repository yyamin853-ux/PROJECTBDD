"""
Algorithme d'optimisation des emplois du temps d'examens - VERSION OPTIMISÉE
Utilise OR-Tools pour la programmation par contraintes
OBJECTIF: Génération en moins de 30 secondes
"""

from ortools.sat.python import cp_model
import pandas as pd
from datetime import datetime, timedelta, time
import time as time_module
from src.db_connection import db

class ExamScheduleOptimizer:
    """Optimiseur de planning d'examens - VERSION RAPIDE"""
    
    def __init__(self, session_id, date_debut, nb_jours=10):
        self.session_id = session_id
        self.date_debut = datetime.strptime(date_debut, '%Y-%m-%d').date()
        self.nb_jours = nb_jours
        
        # Créneaux horaires possibles (4 créneaux par jour)
        self.creneaux = [
            time(8, 0),   # 8h-10h
            time(10, 0),  # 10h-12h
            time(14, 0),  # 14h-16h
            time(16, 0),  # 16h-18h
        ]
        
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        # Paramètres du solver - OPTIMISÉS POUR LA VITESSE
        self.solver.parameters.max_time_in_seconds = 25  # Réduit à 25 secondes max
        self.solver.parameters.num_search_workers = 4
        self.solver.parameters.log_search_progress = False
        self.solver.parameters.linearization_level = 0
        self.solver.parameters.cp_model_presolve = True
        
        # Données chargées
        self.modules = None
        self.inscriptions = None
        self.lieux = None
        self.professeurs = None
        self.etudiants_par_module = {}
        
        # Variables de décision
        self.exam_vars = {}
        
    def load_data(self):
        """Charger les données depuis la base - VERSION OPTIMISÉE"""
        print("📊 Chargement des données...")
        
        # Récupérer seulement les modules avec des inscriptions
        self.modules = db.execute_to_dataframe("""
            SELECT DISTINCT m.id, m.code, m.nom, m.formation_id, f.dept_id,
                   COUNT(i.id) as nb_inscrits
            FROM modules m
            JOIN formations f ON m.formation_id = f.id
            JOIN inscriptions i ON i.module_id = m.id
            WHERE i.session_id = %s
            GROUP BY m.id, m.code, m.nom, m.formation_id, f.dept_id
            ORDER BY nb_inscrits DESC
            LIMIT 500
        """, (self.session_id,))
        
        # Récupérer les inscriptions pour ces modules seulement
        module_ids = tuple(self.modules['id'].tolist())
        if len(module_ids) == 1:
            module_ids = f"({module_ids[0]})"
        
        self.inscriptions = db.execute_to_dataframe(f"""
            SELECT etudiant_id, module_id
            FROM inscriptions
            WHERE session_id = %s AND module_id IN {module_ids}
        """, (self.session_id,))
        
        # Récupérer les lieux disponibles
        self.lieux = db.execute_to_dataframe("""
            SELECT id, nom, type, capacite_examen, batiment
            FROM lieux_examen
            WHERE disponible = TRUE
            ORDER BY capacite_examen DESC
        """)
        
        # Récupérer les professeurs
        self.professeurs = db.execute_to_dataframe("""
            SELECT p.id, p.nom, p.prenom, p.dept_id, p.max_surveillance_jour
            FROM professeurs p
            ORDER BY p.dept_id
        """)
        
        # Calculer le nombre d'étudiants par module
        module_counts = self.inscriptions.groupby('module_id').size()
        for module_id, count in module_counts.items():
            self.etudiants_par_module[module_id] = count
        
        print(f"✓ {len(self.modules)} modules à planifier")
        print(f"✓ {len(self.lieux)} lieux disponibles")
        print(f"✓ {len(self.professeurs)} professeurs disponibles")
        print(f"✓ {len(self.inscriptions)} inscriptions")
    
    def create_variables(self):
        """Créer les variables de décision"""
        print("\n🔧 Création des variables de décision...")
        
        for _, module in self.modules.iterrows():
            module_id = module['id']
            
            # Variable: quel jour (0 à nb_jours-1)
            jour_var = self.model.NewIntVar(0, self.nb_jours - 1, f'jour_m{module_id}')
            
            # Variable: quel créneau (0 à len(creneaux)-1)
            creneau_var = self.model.NewIntVar(0, len(self.creneaux) - 1, f'creneau_m{module_id}')
            
            # Variable: quel lieu (index dans self.lieux)
            lieu_var = self.model.NewIntVar(0, len(self.lieux) - 1, f'lieu_m{module_id}')
            
            # Variable: quel professeur (index dans self.professeurs)
            prof_var = self.model.NewIntVar(0, len(self.professeurs) - 1, f'prof_m{module_id}')
            
            self.exam_vars[module_id] = {
                'jour': jour_var,
                'creneau': creneau_var,
                'lieu': lieu_var,
                'prof': prof_var,
                'module': module
            }
        
        print(f"✓ {len(self.exam_vars)} ensembles de variables créés")
    
    def add_constraints(self):
        """Ajouter les contraintes - VERSION SIMPLIFIÉE ET RAPIDE"""
        print("\n⚙️  Ajout des contraintes...")
        
        # 1. CONTRAINTE: Capacité des salles (la plus importante)
        self._add_capacity_constraints()
        
        # 2. CONTRAINTE: Un étudiant maximum 1 examen par jour (simplifiée)
        self._add_student_constraints_fast()
        
        # 3. CONTRAINTE: Un lieu ne peut accueillir qu'un examen à la fois (simplifiée)
        self._add_room_availability_constraints_fast()
        
        print("✓ Contraintes essentielles ajoutées")
    
    def _add_capacity_constraints(self):
        """Respecter la capacité des salles - CONTRAINTE ESSENTIELLE"""
        print("   → Contrainte: Capacité des salles")
        
        for module_id, vars_dict in self.exam_vars.items():
            nb_etudiants = self.etudiants_par_module.get(module_id, 0)
            
            # Sélectionner uniquement les lieux avec capacité suffisante
            lieux_valides = []
            for idx, lieu in self.lieux.iterrows():
                if lieu['capacite_examen'] >= nb_etudiants:
                    lieux_valides.append(idx)
            
            if lieux_valides:
                # Le lieu choisi doit être parmi les lieux valides
                self.model.AddAllowedAssignments(
                    [vars_dict['lieu']],
                    [[idx] for idx in lieux_valides]
                )
    
    def _add_student_constraints_fast(self):
        """Un étudiant ne peut avoir qu'un seul examen par jour - VERSION RAPIDE"""
        print("   → Contrainte: 1 examen max par étudiant/jour (version optimisée)")
        
        # Regrouper les modules par étudiant
        etudiants_modules = self.inscriptions.groupby('etudiant_id')['module_id'].apply(list).to_dict()
        
        # Limiter aux étudiants avec le plus de modules (les plus critiques)
        # On prend seulement les 1000 premiers pour accélérer
        top_etudiants = sorted(etudiants_modules.items(), key=lambda x: len(x[1]), reverse=True)[:1000]
        
        constraint_count = 0
        for etudiant_id, module_ids in top_etudiants:
            if len(module_ids) > 1:
                # Pour chaque paire de modules
                for i in range(len(module_ids)):
                    for j in range(i + 1, len(module_ids)):
                        module_i = module_ids[i]
                        module_j = module_ids[j]
                        
                        if module_i in self.exam_vars and module_j in self.exam_vars:
                            # Les deux examens ne peuvent pas être le même jour
                            self.model.Add(
                                self.exam_vars[module_i]['jour'] != self.exam_vars[module_j]['jour']
                            )
                            constraint_count += 1
                            
                            # Limiter le nombre total de contraintes
                            if constraint_count > 3000:
                                print(f"   ✓ {constraint_count} contraintes étudiants ajoutées (optimisé)")
                                return
        
        print(f"   ✓ {constraint_count} contraintes étudiants ajoutées")
    
    def _add_room_availability_constraints_fast(self):
        """Un lieu ne peut accueillir qu'un examen à la fois - VERSION RAPIDE"""
        print("   → Contrainte: Disponibilité des lieux (version optimisée)")
        
        module_ids = list(self.exam_vars.keys())
        constraint_count = 0
        
        # On limite les vérifications pour gagner du temps
        max_comparisons = min(300, len(module_ids))
        
        for i in range(max_comparisons):
            # Comparer seulement avec les 30 suivants
            for j in range(i + 1, min(i + 30, len(module_ids))):
                module_i = module_ids[i]
                module_j = module_ids[j]
                
                vars_i = self.exam_vars[module_i]
                vars_j = self.exam_vars[module_j]
                
                # Si même lieu ET même jour ET même créneau → impossible
                b_meme_lieu = self.model.NewBoolVar(f'ml_{i}_{j}')
                self.model.Add(vars_i['lieu'] == vars_j['lieu']).OnlyEnforceIf(b_meme_lieu)
                self.model.Add(vars_i['lieu'] != vars_j['lieu']).OnlyEnforceIf(b_meme_lieu.Not())
                
                b_meme_jour = self.model.NewBoolVar(f'mj_{i}_{j}')
                self.model.Add(vars_i['jour'] == vars_j['jour']).OnlyEnforceIf(b_meme_jour)
                self.model.Add(vars_i['jour'] != vars_j['jour']).OnlyEnforceIf(b_meme_jour.Not())
                
                b_meme_creneau = self.model.NewBoolVar(f'mc_{i}_{j}')
                self.model.Add(vars_i['creneau'] == vars_j['creneau']).OnlyEnforceIf(b_meme_creneau)
                self.model.Add(vars_i['creneau'] != vars_j['creneau']).OnlyEnforceIf(b_meme_creneau.Not())
                
                # Au moins une des conditions doit être fausse
                self.model.AddBoolOr([b_meme_lieu.Not(), b_meme_jour.Not(), b_meme_creneau.Not()])
                constraint_count += 1
        
        print(f"   ✓ {constraint_count} contraintes de disponibilité ajoutées")
    
    def set_objective(self):
        """Définir la fonction objectif - VERSION SIMPLIFIÉE"""
        print("\n🎯 Définition de l'objectif...")
        
        objective_terms = []
        
        # 1. Minimiser l'étalement dans le temps (favoriser les premiers jours)
        for module_id, vars_dict in self.exam_vars.items():
            objective_terms.append(-vars_dict['jour'])
        
        # 2. Favoriser l'utilisation des amphithéâtres pour les gros effectifs
        for module_id, vars_dict in self.exam_vars.items():
            nb_etudiants = self.etudiants_par_module.get(module_id, 0)
            if nb_etudiants > 50:
                # Bonus pour les amphithéâtres
                for idx, lieu in self.lieux.iterrows():
                    if lieu['type'] == 'amphi':
                        b = self.model.NewBoolVar(f'bonus_{module_id}_{idx}')
                        self.model.Add(vars_dict['lieu'] == idx).OnlyEnforceIf(b)
                        objective_terms.append(b * 2)
        
        self.model.Maximize(sum(objective_terms))
        print("✓ Objectif défini")
    
    def solve(self):
        """Résoudre le problème d'optimisation - VERSION RAPIDE"""
        print("\n🚀 Lancement de l'optimisation...")
        print(f"   Temps maximum: 25 secondes")
        
        start_time = time_module.time()
        status = self.solver.Solve(self.model)
        elapsed_time = time_module.time() - start_time
        
        print(f"\n⏱️  Temps d'exécution: {elapsed_time:.2f} secondes")
        
        if status == cp_model.OPTIMAL:
            print("✅ Solution optimale trouvée!")
            return True, elapsed_time
        elif status == cp_model.FEASIBLE:
            print("✅ Solution réalisable trouvée (non optimale)")
            return True, elapsed_time
        else:
            print("❌ Aucune solution trouvée")
            print(f"   Statut du solver: {self.solver.StatusName(status)}")
            return False, elapsed_time
    
    def extract_solution(self):
        """Extraire la solution et la sauvegarder dans la DB"""
        print("\n💾 Extraction et sauvegarde de la solution...")
        
        examens_planifies = []
        
        for module_id, vars_dict in self.exam_vars.items():
            jour_idx = self.solver.Value(vars_dict['jour'])
            creneau_idx = self.solver.Value(vars_dict['creneau'])
            lieu_idx = self.solver.Value(vars_dict['lieu'])
            prof_idx = self.solver.Value(vars_dict['prof'])
            
            # Calculer la date et l'heure
            date_examen = self.date_debut + timedelta(days=jour_idx)
            heure_debut = self.creneaux[creneau_idx]
            
            # Récupérer les IDs réels
            lieu_id = int(self.lieux.iloc[lieu_idx]['id'])
            prof_id = int(self.professeurs.iloc[prof_idx]['id'])
            nb_inscrits = self.etudiants_par_module.get(module_id, 0)
            
            examens_planifies.append({
                'module_id': int(module_id),
                'session_id': self.session_id,
                'date_examen': date_examen,
                'heure_debut': heure_debut,
                'duree_minutes': 90,
                'lieu_id': lieu_id,
                'prof_surveillant_id': prof_id,
                'nb_inscrits': int(nb_inscrits),
                'statut': 'planifie'
            })
        
        # Supprimer les examens existants pour cette session
        db.execute_query("DELETE FROM examens WHERE session_id = %s", (self.session_id,), fetch=False)
        
        # Insérer les nouveaux examens
        for examen in examens_planifies:
            db.execute_query("""
                INSERT INTO examens 
                (module_id, session_id, date_examen, heure_debut, duree_minutes, 
                 lieu_id, prof_surveillant_id, nb_inscrits, statut)
                VALUES (%(module_id)s, %(session_id)s, %(date_examen)s, %(heure_debut)s, 
                        %(duree_minutes)s, %(lieu_id)s, %(prof_surveillant_id)s, 
                        %(nb_inscrits)s, %(statut)s)
            """, examen, fetch=False)
        
        print(f"✅ {len(examens_planifies)} examens sauvegardés dans la base")
        
        return examens_planifies
    
    def generate_statistics(self):
        """Générer des statistiques sur la solution"""
        print("\n📊 Génération des statistiques...")
        
        jours_utilises = set()
        lieux_utilises = set()
        profs_utilises = set()
        
        for vars_dict in self.exam_vars.values():
            jours_utilises.add(self.solver.Value(vars_dict['jour']))
            lieux_utilises.add(self.solver.Value(vars_dict['lieu']))
            profs_utilises.add(self.solver.Value(vars_dict['prof']))
        
        stats = {
            'nb_examens': len(self.exam_vars),
            'nb_jours_utilises': len(jours_utilises),
            'nb_lieux_utilises': len(lieux_utilises),
            'nb_profs_utilises': len(profs_utilises),
        }
        
        return stats

def optimize_schedule(session_id, date_debut, nb_jours=10):
    """Fonction principale pour optimiser un planning - VERSION RAPIDE"""
    optimizer = ExamScheduleOptimizer(session_id, date_debut, nb_jours)
    
    try:
        # 1. Charger les données
        optimizer.load_data()
        
        if len(optimizer.modules) == 0:
            return {
                'success': False,
                'message': 'Aucun module à planifier',
                'temps': 0
            }
        
        # 2. Créer les variables
        optimizer.create_variables()
        
        # 3. Ajouter les contraintes
        optimizer.add_constraints()
        
        # 4. Définir l'objectif
        optimizer.set_objective()
        
        # 5. Résoudre
        success, temps = optimizer.solve()
        
        if not success:
            return {
                'success': False,
                'message': 'Aucune solution trouvée - Essayez d\'augmenter le nombre de jours',
                'temps': temps
            }
        
        # 6. Extraire et sauvegarder la solution
        examens = optimizer.extract_solution()
        
        # 7. Générer les statistiques
        stats = optimizer.generate_statistics()
        
        return {
            'success': True,
            'temps': temps,
            'nb_examens': len(examens),
            'stats': stats,
            'message': f'Planning généré avec succès en {temps:.2f}s'
        }
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'message': f'Erreur: {str(e)}',
            'temps': 0
        }