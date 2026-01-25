from ortools.sat.python import cp_model
import pandas as pd
from datetime import datetime, timedelta, time
import time as time_module
from src.db_connection import db
from collections import defaultdict

class ExamScheduleOptimizer:
    
    def __init__(self, session_id, date_debut, nb_jours=15):
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
        
        self.solver.parameters.max_time_in_seconds = 35
        self.solver.parameters.num_search_workers = 8
        self.solver.parameters.log_search_progress = False
        self.solver.parameters.cp_model_presolve = True
        self.solver.parameters.linearization_level = 2
        self.solver.parameters.search_branching = cp_model.FIXED_SEARCH
        
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
            LIMIT 200
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
        print("\n🔧 Variables...")
        
        for _, module in self.modules.iterrows():
            module_id = module['id']
            
            jour_var = self.model.NewIntVar(0, self.nb_jours - 1, f'j_{module_id}')
            creneau_var = self.model.NewIntVar(0, len(self.creneaux) - 1, f'c_{module_id}')
            lieu_var = self.model.NewIntVar(0, len(self.lieux) - 1, f'l_{module_id}')
            prof_var = self.model.NewIntVar(0, len(self.professeurs) - 1, f'p_{module_id}')
            
            self.exam_vars[module_id] = {
                'jour': jour_var,
                'creneau': creneau_var,
                'lieu': lieu_var,
                'prof': prof_var,
                'module': module
            }
        
        print(f"✓ {len(self.exam_vars)} variables")
    
    def add_constraints(self):
        print("\n⚙️  Contraintes...")
        
        self._add_capacity_constraints()
        self._add_student_constraints()
        self._add_room_constraints()
        self._add_prof_constraints()
        self._add_prof_max_per_day()
        
        print("✓ Contraintes OK")
    
    def _add_capacity_constraints(self):
        print("   → Capacité salles")
        
        for module_id, vars_dict in self.exam_vars.items():
            nb_etudiants = self.etudiants_par_module.get(module_id, 0)
            
            lieux_valides = []
            for idx, lieu in self.lieux.iterrows():
                if lieu['capacite_examen'] >= nb_etudiants:
                    lieux_valides.append(idx)
            
            if lieux_valides:
                self.model.AddAllowedAssignments([vars_dict['lieu']], [[idx] for idx in lieux_valides])
    
    def _add_student_constraints(self):
        print("   → Conflits étudiants (1 exam/jour)")
        
        etudiants_modules = self.inscriptions.groupby('etudiant_id')['module_id'].apply(list).to_dict()
        
        count = 0
        for etudiant_id, module_ids in etudiants_modules.items():
            if len(module_ids) > 1:
                for i in range(len(module_ids)):
                    for j in range(i + 1, len(module_ids)):
                        m_i = module_ids[i]
                        m_j = module_ids[j]
                        
                        if m_i in self.exam_vars and m_j in self.exam_vars:
                            self.model.Add(self.exam_vars[m_i]['jour'] != self.exam_vars[m_j]['jour'])
                            count += 1
        
        print(f"   ✓ {count} contraintes")
    
    def _add_room_constraints(self):
        print("   → Salles uniques/créneau")
        
        module_list = list(self.exam_vars.keys())
        count = 0
        
        for i in range(len(module_list)):
            for j in range(i + 1, min(i + 30, len(module_list))):
                m_i = module_list[i]
                m_j = module_list[j]
                
                v_i = self.exam_vars[m_i]
                v_j = self.exam_vars[m_j]
                
                b_same_lieu = self.model.NewBoolVar(f'sl_{i}_{j}')
                self.model.Add(v_i['lieu'] == v_j['lieu']).OnlyEnforceIf(b_same_lieu)
                self.model.Add(v_i['lieu'] != v_j['lieu']).OnlyEnforceIf(b_same_lieu.Not())
                
                b_same_jour = self.model.NewBoolVar(f'sj_{i}_{j}')
                self.model.Add(v_i['jour'] == v_j['jour']).OnlyEnforceIf(b_same_jour)
                self.model.Add(v_i['jour'] != v_j['jour']).OnlyEnforceIf(b_same_jour.Not())
                
                b_same_creneau = self.model.NewBoolVar(f'sc_{i}_{j}')
                self.model.Add(v_i['creneau'] == v_j['creneau']).OnlyEnforceIf(b_same_creneau)
                self.model.Add(v_i['creneau'] != v_j['creneau']).OnlyEnforceIf(b_same_creneau.Not())
                
                self.model.AddBoolOr([b_same_lieu.Not(), b_same_jour.Not(), b_same_creneau.Not()])
                count += 1
        
        print(f"   ✓ {count} contraintes")
    
    def _add_prof_constraints(self):
        print("   → Profs uniques/créneau")
        
        module_list = list(self.exam_vars.keys())
        count = 0
        
        for i in range(len(module_list)):
            for j in range(i + 1, min(i + 30, len(module_list))):
                m_i = module_list[i]
                m_j = module_list[j]
                
                v_i = self.exam_vars[m_i]
                v_j = self.exam_vars[m_j]
                
                b_same_prof = self.model.NewBoolVar(f'sp_{i}_{j}')
                self.model.Add(v_i['prof'] == v_j['prof']).OnlyEnforceIf(b_same_prof)
                self.model.Add(v_i['prof'] != v_j['prof']).OnlyEnforceIf(b_same_prof.Not())
                
                b_same_jour = self.model.NewBoolVar(f'spj_{i}_{j}')
                self.model.Add(v_i['jour'] == v_j['jour']).OnlyEnforceIf(b_same_jour)
                self.model.Add(v_i['jour'] != v_j['jour']).OnlyEnforceIf(b_same_jour.Not())
                
                b_same_creneau = self.model.NewBoolVar(f'spc_{i}_{j}')
                self.model.Add(v_i['creneau'] == v_j['creneau']).OnlyEnforceIf(b_same_creneau)
                self.model.Add(v_i['creneau'] != v_j['creneau']).OnlyEnforceIf(b_same_creneau.Not())
                
                self.model.AddBoolOr([b_same_prof.Not(), b_same_jour.Not(), b_same_creneau.Not()])
                count += 1
        
        print(f"   ✓ {count} contraintes")
    
    def _add_prof_max_per_day(self):
        print("   → Max 3 exams/prof/jour")
        
        for prof_idx in range(len(self.professeurs)):
            for jour in range(self.nb_jours):
                prof_day_exams = []
                
                for module_id, vars_dict in self.exam_vars.items():
                    b = self.model.NewBoolVar(f'pd_{prof_idx}_{jour}_{module_id}')
                    
                    self.model.Add(vars_dict['prof'] == prof_idx).OnlyEnforceIf(b)
                    self.model.Add(vars_dict['jour'] == jour).OnlyEnforceIf(b)
                    self.model.AddBoolOr([
                        vars_dict['prof'] != prof_idx,
                        vars_dict['jour'] != jour
                    ]).OnlyEnforceIf(b.Not())
                    
                    prof_day_exams.append(b)
                
                self.model.Add(sum(prof_day_exams) <= 3)
        
        print(f"   ✓ Contrainte ajoutée")
    
    def set_objective(self):
        print("\n🎯 Objectif...")
        
        objective_terms = []
        
        for module_id, vars_dict in self.exam_vars.items():
            objective_terms.append(-vars_dict['jour'] * 10)
            objective_terms.append(-vars_dict['creneau'])
        
        for module_id, vars_dict in self.exam_vars.items():
            module_dept = self.module_dept.get(module_id)
            if module_dept:
                for prof_idx, prof in self.professeurs.iterrows():
                    if prof['dept_id'] == module_dept:
                        b = self.model.NewBoolVar(f'd_{module_id}_{prof_idx}')
                        self.model.Add(vars_dict['prof'] == prof_idx).OnlyEnforceIf(b)
                        objective_terms.append(b * 20)
        
        for module_id, vars_dict in self.exam_vars.items():
            nb_etudiants = self.etudiants_par_module.get(module_id, 0)
            if nb_etudiants > 50:
                for idx, lieu in self.lieux.iterrows():
                    if lieu['type'] == 'amphi':
                        b = self.model.NewBoolVar(f'a_{module_id}_{idx}')
                        self.model.Add(vars_dict['lieu'] == idx).OnlyEnforceIf(b)
                        objective_terms.append(b * 5)
        
        self.model.Maximize(sum(objective_terms))
        print("✓ OK")
    
    def solve(self):
        print("\n🚀 OPTIMISATION...")
        print(f"   MAX: 35 secondes")
        
        start = time_module.time()
        status = self.solver.Solve(self.model)
        elapsed = time_module.time() - start
        
        print(f"\n⏱️  {elapsed:.2f}s")
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print("✅ SUCCÈS!")
            return True, elapsed
        else:
            print(f"❌ ÉCHEC: {self.solver.StatusName(status)}")
            return False, elapsed
    
    def extract_solution(self):
        print("\n💾 Sauvegarde...")
        
        examens = []
        
        for module_id, vars_dict in self.exam_vars.items():
            jour_idx = self.solver.Value(vars_dict['jour'])
            creneau_idx = self.solver.Value(vars_dict['creneau'])
            lieu_idx = self.solver.Value(vars_dict['lieu'])
            prof_idx = self.solver.Value(vars_dict['prof'])
            
            date_examen = self.date_debut + timedelta(days=jour_idx)
            heure_debut = self.creneaux[creneau_idx]
            
            examens.append({
                'module_id': int(module_id),
                'session_id': self.session_id,
                'date_examen': date_examen,
                'heure_debut': heure_debut,
                'duree_minutes': 90,
                'lieu_id': int(self.lieux.iloc[lieu_idx]['id']),
                'prof_surveillant_id': int(self.professeurs.iloc[prof_idx]['id']),
                'nb_inscrits': int(self.etudiants_par_module.get(module_id, 0)),
                'statut': 'planifie'
            })
        
        db.execute_query("DELETE FROM examens WHERE session_id = %s", (self.session_id,), fetch=False)
        
        for examen in examens:
            db.execute_query("""
                INSERT INTO examens 
                (module_id, session_id, date_examen, heure_debut, duree_minutes, 
                 lieu_id, prof_surveillant_id, nb_inscrits, statut)
                VALUES (%(module_id)s, %(session_id)s, %(date_examen)s, %(heure_debut)s, 
                        %(duree_minutes)s, %(lieu_id)s, %(prof_surveillant_id)s, 
                        %(nb_inscrits)s, %(statut)s)
            """, examen, fetch=False)
        
        print(f"✅ {len(examens)} examens")
        return examens
    
    def generate_statistics(self):
        stats = {
            'nb_examens': len(self.exam_vars),
            'nb_jours_utilises': len(set(self.solver.Value(v['jour']) for v in self.exam_vars.values())),
            'nb_lieux_utilises': len(set(self.solver.Value(v['lieu']) for v in self.exam_vars.values())),
            'nb_profs_utilises': len(set(self.solver.Value(v['prof']) for v in self.exam_vars.values()))
        }
        return stats

def optimize_schedule(session_id, date_debut, nb_jours=15):
    optimizer = ExamScheduleOptimizer(session_id, date_debut, nb_jours)
    
    try:
        optimizer.load_data()
        
        if len(optimizer.modules) == 0:
            return {'success': False, 'message': 'Aucun module', 'temps': 0}
        
        optimizer.create_variables()
        optimizer.add_constraints()
        optimizer.set_objective()
        
        success, temps = optimizer.solve()
        
        if not success:
            return {'success': False, 'message': 'Aucune solution', 'temps': temps}
        
        examens = optimizer.extract_solution()
        stats = optimizer.generate_statistics()
        
        return {
            'success': True,
            'temps': temps,
            'nb_examens': len(examens),
            'stats': stats,
            'message': f'✅ {temps:.2f}s'
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'message': str(e), 'temps': 0}
