from ortools.sat.python import cp_model
import pandas as pd
from datetime import datetime, timedelta, time
import time as time_module
from src.db_connection import db
from collections import defaultdict

class ExamScheduleOptimizer:
    
    def __init__(self, session_id, date_debut, nb_jours=10):
        self.session_id = session_id
        self.date_debut = datetime.strptime(date_debut, '%Y-%m-%d').date()
        self.nb_jours = nb_jours
        
        self.creneaux = [
            time(8, 0),
            time(10, 0),
            time(14, 0),
            time(16, 0),
        ]
        
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        
        self.solver.parameters.max_time_in_seconds = 40
        self.solver.parameters.num_search_workers = 8
        self.solver.parameters.log_search_progress = False
        self.solver.parameters.cp_model_presolve = True
        self.solver.parameters.linearization_level = 2
        
        self.modules = None
        self.inscriptions = None
        self.lieux = None
        self.professeurs = None
        self.etudiants_par_module = {}
        self.module_dept = {}
        self.prof_dept = {}
        
        self.exam_vars = {}
        
    def load_data(self):
        print("📊 Chargement des données...")
        
        self.modules = db.execute_to_dataframe("""
            SELECT DISTINCT m.id, m.code, m.nom, m.formation_id, f.dept_id,
                   COUNT(i.id) as nb_inscrits
            FROM modules m
            JOIN formations f ON m.formation_id = f.id
            JOIN inscriptions i ON i.module_id = m.id
            WHERE i.session_id = %s
            GROUP BY m.id, m.code, m.nom, m.formation_id, f.dept_id
            ORDER BY nb_inscrits DESC
        """, (self.session_id,))
        
        for _, module in self.modules.iterrows():
            self.module_dept[module['id']] = module['dept_id']
        
        module_ids = tuple(self.modules['id'].tolist())
        if len(module_ids) == 0:
            return
        if len(module_ids) == 1:
            module_ids = f"({module_ids[0]})"
        
        self.inscriptions = db.execute_to_dataframe(f"""
            SELECT etudiant_id, module_id
            FROM inscriptions
            WHERE session_id = %s AND module_id IN {module_ids}
        """, (self.session_id,))
        
        self.lieux = db.execute_to_dataframe("""
            SELECT id, nom, type, capacite_examen, batiment
            FROM lieux_examen
            WHERE disponible = TRUE
            ORDER BY capacite_examen DESC
        """)
        
        self.professeurs = db.execute_to_dataframe("""
            SELECT p.id, p.nom, p.prenom, p.dept_id, p.max_surveillance_jour
            FROM professeurs p
            ORDER BY p.dept_id
        """)
        
        for _, prof in self.professeurs.iterrows():
            self.prof_dept[prof['id']] = prof['dept_id']
        
        module_counts = self.inscriptions.groupby('module_id').size()
        for module_id, count in module_counts.items():
            self.etudiants_par_module[module_id] = count
        
        print(f"✓ {len(self.modules)} modules")
        print(f"✓ {len(self.lieux)} lieux")
        print(f"✓ {len(self.professeurs)} professeurs")
        print(f"✓ {len(self.inscriptions)} inscriptions")
    
    def create_variables(self):
        print("\n🔧 Création des variables...")
        
        total_timeslots = self.nb_jours * len(self.creneaux)
        
        for _, module in self.modules.iterrows():
            module_id = module['id']
            
            timeslot_var = self.model.NewIntVar(0, total_timeslots - 1, f'ts_{module_id}')
            lieu_var = self.model.NewIntVar(0, len(self.lieux) - 1, f'l_{module_id}')
            prof_var = self.model.NewIntVar(0, len(self.professeurs) - 1, f'p_{module_id}')
            
            self.exam_vars[module_id] = {
                'timeslot': timeslot_var,
                'lieu': lieu_var,
                'prof': prof_var,
                'module': module
            }
        
        print(f"✓ {len(self.exam_vars)} variables créées")
    
    def add_constraints(self):
        print("\n⚙️  Ajout des contraintes...")
        
        self._add_capacity_constraints()
        self._add_student_one_exam_per_day()
        self._add_professor_max_3_per_day()
        self._add_room_availability_constraints()
        self._add_professor_availability_constraints()
        self._add_balanced_surveillance()
        
        print("✓ Toutes les contraintes ajoutées")
    
    def _add_capacity_constraints(self):
        print("   → Capacité des salles")
        
        for module_id, vars_dict in self.exam_vars.items():
            nb_etudiants = self.etudiants_par_module.get(module_id, 0)
            
            lieux_valides = []
            for idx, lieu in self.lieux.iterrows():
                if lieu['capacite_examen'] >= nb_etudiants:
                    lieux_valides.append(idx)
            
            if lieux_valides:
                self.model.AddAllowedAssignments(
                    [vars_dict['lieu']],
                    [[idx] for idx in lieux_valides]
                )
    
    def _add_student_one_exam_per_day(self):
        print("   → Max 1 examen/jour par étudiant")
        
        etudiants_modules = self.inscriptions.groupby('etudiant_id')['module_id'].apply(list).to_dict()
        
        constraint_count = 0
        for etudiant_id, module_ids in etudiants_modules.items():
            if len(module_ids) > 1:
                for i in range(len(module_ids)):
                    for j in range(i + 1, len(module_ids)):
                        module_i = module_ids[i]
                        module_j = module_ids[j]
                        
                        if module_i in self.exam_vars and module_j in self.exam_vars:
                            ts_i = self.exam_vars[module_i]['timeslot']
                            ts_j = self.exam_vars[module_j]['timeslot']
                            
                            jour_i = self.model.NewIntVar(0, self.nb_jours - 1, f'j_i_{constraint_count}')
                            jour_j = self.model.NewIntVar(0, self.nb_jours - 1, f'j_j_{constraint_count}')
                            
                            self.model.AddDivisionEquality(jour_i, ts_i, len(self.creneaux))
                            self.model.AddDivisionEquality(jour_j, ts_j, len(self.creneaux))
                            
                            self.model.Add(jour_i != jour_j)
                            constraint_count += 1
        
        print(f"   ✓ {constraint_count} contraintes étudiants")
    
    def _add_professor_max_3_per_day(self):
        print("   → Max 3 examens/jour par professeur")
        
        for prof_idx in range(len(self.professeurs)):
            for jour in range(self.nb_jours):
                exams_this_day = []
                
                for module_id, vars_dict in self.exam_vars.items():
                    b_prof = self.model.NewBoolVar(f'bp_{prof_idx}_{module_id}_{jour}')
                    self.model.Add(vars_dict['prof'] == prof_idx).OnlyEnforceIf(b_prof)
                    self.model.Add(vars_dict['prof'] != prof_idx).OnlyEnforceIf(b_prof.Not())
                    
                    ts_min = jour * len(self.creneaux)
                    ts_max = (jour + 1) * len(self.creneaux) - 1
                    
                    b_day = self.model.NewBoolVar(f'bd_{module_id}_{jour}')
                    self.model.Add(vars_dict['timeslot'] >= ts_min).OnlyEnforceIf(b_day)
                    self.model.Add(vars_dict['timeslot'] <= ts_max).OnlyEnforceIf(b_day)
                    
                    b_out_low = self.model.NewBoolVar(f'ol_{module_id}_{jour}')
                    b_out_high = self.model.NewBoolVar(f'oh_{module_id}_{jour}')
                    self.model.Add(vars_dict['timeslot'] < ts_min).OnlyEnforceIf(b_out_low)
                    self.model.Add(vars_dict['timeslot'] >= ts_min).OnlyEnforceIf(b_out_low.Not())
                    self.model.Add(vars_dict['timeslot'] > ts_max).OnlyEnforceIf(b_out_high)
                    self.model.Add(vars_dict['timeslot'] <= ts_max).OnlyEnforceIf(b_out_high.Not())
                    
                    self.model.AddBoolOr([b_out_low, b_out_high]).OnlyEnforceIf(b_day.Not())
                    
                    b_both = self.model.NewBoolVar(f'bb_{prof_idx}_{module_id}_{jour}')
                    self.model.AddBoolAnd([b_prof, b_day]).OnlyEnforceIf(b_both)
                    
                    exams_this_day.append(b_both)
                
                if exams_this_day:
                    self.model.Add(sum(exams_this_day) <= 3)
        
        print(f"   ✓ Contraintes max 3/jour ajoutées")
    
    def _add_room_availability_constraints(self):
        print("   → Disponibilité des salles")
        
        module_ids = list(self.exam_vars.keys())
        constraint_count = 0
        max_comparisons = min(300, len(module_ids))
        
        for i in range(max_comparisons):
            for j in range(i + 1, min(i + 40, len(module_ids))):
                module_i = module_ids[i]
                module_j = module_ids[j]
                
                vars_i = self.exam_vars[module_i]
                vars_j = self.exam_vars[module_j]
                
                b_same_room = self.model.NewBoolVar(f'sr_{i}_{j}')
                self.model.Add(vars_i['lieu'] == vars_j['lieu']).OnlyEnforceIf(b_same_room)
                self.model.Add(vars_i['lieu'] != vars_j['lieu']).OnlyEnforceIf(b_same_room.Not())
                
                self.model.Add(vars_i['timeslot'] != vars_j['timeslot']).OnlyEnforceIf(b_same_room)
                
                constraint_count += 1
        
        print(f"   ✓ {constraint_count} contraintes salles")
    
    def _add_professor_availability_constraints(self):
        print("   → Disponibilité des professeurs")
        
        module_ids = list(self.exam_vars.keys())
        constraint_count = 0
        max_comparisons = min(300, len(module_ids))
        
        for i in range(max_comparisons):
            for j in range(i + 1, min(i + 40, len(module_ids))):
                module_i = module_ids[i]
                module_j = module_ids[j]
                
                vars_i = self.exam_vars[module_i]
                vars_j = self.exam_vars[module_j]
                
                b_same_prof = self.model.NewBoolVar(f'sp_{i}_{j}')
                self.model.Add(vars_i['prof'] == vars_j['prof']).OnlyEnforceIf(b_same_prof)
                self.model.Add(vars_i['prof'] != vars_j['prof']).OnlyEnforceIf(b_same_prof.Not())
                
                self.model.Add(vars_i['timeslot'] != vars_j['timeslot']).OnlyEnforceIf(b_same_prof)
                
                constraint_count += 1
        
        print(f"   ✓ {constraint_count} contraintes professeurs")
    
    def _add_balanced_surveillance(self):
        print("   → Équilibrage des surveillances")
        
        surveillance_counts = []
        
        for prof_idx in range(len(self.professeurs)):
            prof_exams = []
            for module_id, vars_dict in self.exam_vars.items():
                b = self.model.NewBoolVar(f'surv_{prof_idx}_{module_id}')
                self.model.Add(vars_dict['prof'] == prof_idx).OnlyEnforceIf(b)
                self.model.Add(vars_dict['prof'] != prof_idx).OnlyEnforceIf(b.Not())
                prof_exams.append(b)
            
            count = self.model.NewIntVar(0, len(self.exam_vars), f'count_{prof_idx}')
            self.model.Add(count == sum(prof_exams))
            surveillance_counts.append(count)
        
        if len(surveillance_counts) > 1:
            avg_surveillances = len(self.exam_vars) // len(self.professeurs)
            for count in surveillance_counts:
                self.model.Add(count >= max(0, avg_surveillances - 2))
                self.model.Add(count <= avg_surveillances + 2)
        
        print(f"   ✓ Équilibrage ajouté")
    
    def set_objective(self):
        print("\n🎯 Définition de l'objectif...")
        
        objective_terms = []
        
        for module_id, vars_dict in self.exam_vars.items():
            objective_terms.append(-vars_dict['timeslot'])
        
        for module_id, vars_dict in self.exam_vars.items():
            module_dept = self.module_dept.get(module_id)
            if module_dept:
                for prof_idx, prof in self.professeurs.iterrows():
                    if prof['dept_id'] == module_dept:
                        b = self.model.NewBoolVar(f'dept_{module_id}_{prof_idx}')
                        self.model.Add(vars_dict['prof'] == prof_idx).OnlyEnforceIf(b)
                        objective_terms.append(b * 10)
        
        for module_id, vars_dict in self.exam_vars.items():
            nb_etudiants = self.etudiants_par_module.get(module_id, 0)
            if nb_etudiants > 50:
                for idx, lieu in self.lieux.iterrows():
                    if lieu['type'] == 'amphi':
                        b = self.model.NewBoolVar(f'amphi_{module_id}_{idx}')
                        self.model.Add(vars_dict['lieu'] == idx).OnlyEnforceIf(b)
                        objective_terms.append(b * 3)
        
        self.model.Maximize(sum(objective_terms))
        print("✓ Objectif: priorité département + minimiser créneaux")
    
    def solve(self):
        print("\n🚀 Optimisation...")
        print(f"   Temps max: 40 secondes")
        
        start_time = time_module.time()
        status = self.solver.Solve(self.model)
        elapsed_time = time_module.time() - start_time
        
        print(f"\n⏱️  Temps: {elapsed_time:.2f}s")
        
        if status == cp_model.OPTIMAL:
            print("✅ Solution optimale!")
            return True, elapsed_time
        elif status == cp_model.FEASIBLE:
            print("✅ Solution réalisable!")
            return True, elapsed_time
        else:
            print("❌ Aucune solution")
            print(f"   Statut: {self.solver.StatusName(status)}")
            return False, elapsed_time
    
    def extract_solution(self):
        print("\n💾 Extraction...")
        
        examens_planifies = []
        
        for module_id, vars_dict in self.exam_vars.items():
            timeslot_val = self.solver.Value(vars_dict['timeslot'])
            lieu_idx = self.solver.Value(vars_dict['lieu'])
            prof_idx = self.solver.Value(vars_dict['prof'])
            
            jour_idx = timeslot_val // len(self.creneaux)
            creneau_idx = timeslot_val % len(self.creneaux)
            
            date_examen = self.date_debut + timedelta(days=jour_idx)
            heure_debut = self.creneaux[creneau_idx]
            
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
        
        db.execute_query("DELETE FROM examens WHERE session_id = %s", (self.session_id,), fetch=False)
        
        for examen in examens_planifies:
            db.execute_query("""
                INSERT INTO examens 
                (module_id, session_id, date_examen, heure_debut, duree_minutes, 
                 lieu_id, prof_surveillant_id, nb_inscrits, statut)
                VALUES (%(module_id)s, %(session_id)s, %(date_examen)s, %(heure_debut)s, 
                        %(duree_minutes)s, %(lieu_id)s, %(prof_surveillant_id)s, 
                        %(nb_inscrits)s, %(statut)s)
            """, examen, fetch=False)
        
        print(f"✅ {len(examens_planifies)} examens sauvegardés")
        
        return examens_planifies
    
    def generate_statistics(self):
        print("\n📊 Statistiques...")
        
        jours_utilises = set()
        lieux_utilises = set()
        profs_utilises = set()
        prof_counts = defaultdict(int)
        dept_match = 0
        total_exams = 0
        
        for module_id, vars_dict in self.exam_vars.items():
            timeslot_val = self.solver.Value(vars_dict['timeslot'])
            jour_idx = timeslot_val // len(self.creneaux)
            prof_idx = self.solver.Value(vars_dict['prof'])
            
            jours_utilises.add(jour_idx)
            lieux_utilises.add(self.solver.Value(vars_dict['lieu']))
            profs_utilises.add(prof_idx)
            prof_counts[prof_idx] += 1
            
            prof_dept = self.professeurs.iloc[prof_idx]['dept_id']
            module_dept = self.module_dept.get(module_id)
            if prof_dept == module_dept:
                dept_match += 1
            total_exams += 1
        
        stats = {
            'nb_examens': len(self.exam_vars),
            'nb_jours_utilises': len(jours_utilises),
            'nb_lieux_utilises': len(lieux_utilises),
            'nb_profs_utilises': len(profs_utilises),
            'dept_match_rate': f"{(dept_match/total_exams*100):.1f}%" if total_exams > 0 else "0%",
            'avg_surveillance': sum(prof_counts.values()) / len(prof_counts) if prof_counts else 0
        }
        
        return stats

def optimize_schedule(session_id, date_debut, nb_jours=10):
    optimizer = ExamScheduleOptimizer(session_id, date_debut, nb_jours)
    
    try:
        optimizer.load_data()
        
        if len(optimizer.modules) == 0:
            return {
                'success': False,
                'message': 'Aucun module à planifier',
                'temps': 0
            }
        
        optimizer.create_variables()
        optimizer.add_constraints()
        optimizer.set_objective()
        
        success, temps = optimizer.solve()
        
        if not success:
            return {
                'success': False,
                'message': 'Aucune solution - Augmentez les jours ou vérifiez les ressources',
                'temps': temps
            }
        
        examens = optimizer.extract_solution()
        stats = optimizer.generate_statistics()
        
        return {
            'success': True,
            'temps': temps,
            'nb_examens': len(examens),
            'stats': stats,
            'message': f'Planning généré en {temps:.2f}s'
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
