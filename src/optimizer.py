from ortools.sat.python import cp_model
import pandas as pd
from datetime import datetime, timedelta, time
import time as time_module
from src.db_connection import db

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
        
        self.solver.parameters.max_time_in_seconds = 30
        self.solver.parameters.num_search_workers = 8
        
        self.modules = None
        self.inscriptions = None
        self.lieux = None
        self.professeurs = None
        self.etudiants_par_module = {}
        self.module_dept = {}
        
        self.exam_vars = {}
        
    def load_data(self):
        print("📊 Chargement...")
        
        self.modules = db.execute_to_dataframe("""
            SELECT DISTINCT m.id, m.code, m.nom, m.formation_id, f.dept_id,
                   COUNT(i.id) as nb_inscrits
            FROM modules m
            JOIN formations f ON m.formation_id = f.id
            JOIN inscriptions i ON i.module_id = m.id
            WHERE i.session_id = %s
            GROUP BY m.id, m.code, m.nom, m.formation_id, f.dept_id
            ORDER BY nb_inscrits DESC
            LIMIT 150
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
            SELECT p.id, p.nom, p.prenom, p.dept_id
            FROM professeurs p
            ORDER BY p.dept_id
        """)
        
        module_counts = self.inscriptions.groupby('module_id').size()
        for module_id, count in module_counts.items():
            self.etudiants_par_module[module_id] = count
        
        print(f"✓ {len(self.modules)} modules, {len(self.lieux)} lieux, {len(self.professeurs)} profs")
    
    def create_variables(self):
        print("🔧 Variables...")
        
        total_slots = self.nb_jours * len(self.creneaux)
        
        for _, module in self.modules.iterrows():
            module_id = module['id']
            
            slot = self.model.NewIntVar(0, total_slots - 1, f's{module_id}')
            lieu = self.model.NewIntVar(0, len(self.lieux) - 1, f'l{module_id}')
            prof = self.model.NewIntVar(0, len(self.professeurs) - 1, f'p{module_id}')
            
            self.exam_vars[module_id] = {
                'slot': slot,
                'lieu': lieu,
                'prof': prof,
                'module': module
            }
        
        print(f"✓ {len(self.exam_vars)} vars")
    
    def add_constraints(self):
        print("⚙️  Contraintes...")
        
        self._constraint_capacity()
        self._constraint_students()
        self._constraint_rooms()
        self._constraint_profs()
        
        print("✓ OK")
    
    def _constraint_capacity(self):
        for module_id, v in self.exam_vars.items():
            nb = self.etudiants_par_module.get(module_id, 0)
            valid = [i for i, l in self.lieux.iterrows() if l['capacite_examen'] >= nb]
            if valid:
                self.model.AddAllowedAssignments([v['lieu']], [[i] for i in valid])
    
    def _constraint_students(self):
        etud_mods = self.inscriptions.groupby('etudiant_id')['module_id'].apply(list).to_dict()
        
        count = 0
        for mods in etud_mods.values():
            if len(mods) < 2:
                continue
            for i in range(len(mods)):
                for j in range(i + 1, len(mods)):
                    m1, m2 = mods[i], mods[j]
                    if m1 in self.exam_vars and m2 in self.exam_vars:
                        s1 = self.exam_vars[m1]['slot']
                        s2 = self.exam_vars[m2]['slot']
                        
                        d1 = self.model.NewIntVar(0, self.nb_jours - 1, f'd1_{count}')
                        d2 = self.model.NewIntVar(0, self.nb_jours - 1, f'd2_{count}')
                        
                        self.model.AddDivisionEquality(d1, s1, len(self.creneaux))
                        self.model.AddDivisionEquality(d2, s2, len(self.creneaux))
                        self.model.Add(d1 != d2)
                        count += 1
        
        print(f"   ✓ {count} étudiants")
    
    def _constraint_rooms(self):
        mods = list(self.exam_vars.keys())
        count = 0
        
        for i in range(len(mods)):
            for j in range(i + 1, min(i + 25, len(mods))):
                v1 = self.exam_vars[mods[i]]
                v2 = self.exam_vars[mods[j]]
                
                same_lieu = self.model.NewBoolVar(f'rl{i}{j}')
                self.model.Add(v1['lieu'] == v2['lieu']).OnlyEnforceIf(same_lieu)
                self.model.Add(v1['lieu'] != v2['lieu']).OnlyEnforceIf(same_lieu.Not())
                
                self.model.Add(v1['slot'] != v2['slot']).OnlyEnforceIf(same_lieu)
                count += 1
        
        print(f"   ✓ {count} salles")
    
    def _constraint_profs(self):
        mods = list(self.exam_vars.keys())
        count = 0
        
        for i in range(len(mods)):
            for j in range(i + 1, min(i + 25, len(mods))):
                v1 = self.exam_vars[mods[i]]
                v2 = self.exam_vars[mods[j]]
                
                same_prof = self.model.NewBoolVar(f'rp{i}{j}')
                self.model.Add(v1['prof'] == v2['prof']).OnlyEnforceIf(same_prof)
                self.model.Add(v1['prof'] != v2['prof']).OnlyEnforceIf(same_prof.Not())
                
                self.model.Add(v1['slot'] != v2['slot']).OnlyEnforceIf(same_prof)
                count += 1
        
        print(f"   ✓ {count} profs")
    
    def set_objective(self):
        print("🎯 Objectif...")
        
        obj = []
        
        for module_id, v in self.exam_vars.items():
            obj.append(-v['slot'])
            
            dept = self.module_dept.get(module_id)
            if dept:
                for idx, prof in self.professeurs.iterrows():
                    if prof['dept_id'] == dept:
                        b = self.model.NewBoolVar(f'o{module_id}{idx}')
                        self.model.Add(v['prof'] == idx).OnlyEnforceIf(b)
                        obj.append(b * 50)
        
        self.model.Maximize(sum(obj))
        print("✓ OK")
    
    def solve(self):
        print("\n🚀 RÉSOLUTION (max 30s)...")
        
        start = time_module.time()
        status = self.solver.Solve(self.model)
        elapsed = time_module.time() - start
        
        print(f"⏱️  {elapsed:.1f}s")
        
        if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            print("✅ SUCCÈS")
            return True, elapsed
        
        print(f"❌ {self.solver.StatusName(status)}")
        return False, elapsed
    
    def extract_solution(self):
        print("💾 Sauvegarde...")
        
        exams = []
        
        for module_id, v in self.exam_vars.items():
            slot_val = self.solver.Value(v['slot'])
            jour = slot_val // len(self.creneaux)
            creneau = slot_val % len(self.creneaux)
            
            date_exam = self.date_debut + timedelta(days=jour)
            heure = self.creneaux[creneau]
            
            exams.append({
                'module_id': int(module_id),
                'session_id': self.session_id,
                'date_examen': date_exam,
                'heure_debut': heure,
                'duree_minutes': 90,
                'lieu_id': int(self.lieux.iloc[self.solver.Value(v['lieu'])]['id']),
                'prof_surveillant_id': int(self.professeurs.iloc[self.solver.Value(v['prof'])]['id']),
                'nb_inscrits': int(self.etudiants_par_module.get(module_id, 0)),
                'statut': 'planifie'
            })
        
        db.execute_query("DELETE FROM examens WHERE session_id = %s", (self.session_id,), fetch=False)
        
        for exam in exams:
            db.execute_query("""
                INSERT INTO examens 
                (module_id, session_id, date_examen, heure_debut, duree_minutes, 
                 lieu_id, prof_surveillant_id, nb_inscrits, statut)
                VALUES (%(module_id)s, %(session_id)s, %(date_examen)s, %(heure_debut)s, 
                        %(duree_minutes)s, %(lieu_id)s, %(prof_surveillant_id)s, 
                        %(nb_inscrits)s, %(statut)s)
            """, exam, fetch=False)
        
        print(f"✅ {len(exams)} examens")
        return exams
    
    def stats(self):
        return {
            'nb_examens': len(self.exam_vars),
            'nb_jours': len(set(self.solver.Value(v['slot']) // len(self.creneaux) for v in self.exam_vars.values())),
            'nb_lieux': len(set(self.solver.Value(v['lieu']) for v in self.exam_vars.values())),
            'nb_profs': len(set(self.solver.Value(v['prof']) for v in self.exam_vars.values()))
        }

def optimize_schedule(session_id, date_debut, nb_jours=15):
    opt = ExamScheduleOptimizer(session_id, date_debut, nb_jours)
    
    try:
        opt.load_data()
        if len(opt.modules) == 0:
            return {'success': False, 'message': 'Aucun module', 'temps': 0}
        
        opt.create_variables()
        opt.add_constraints()
        opt.set_objective()
        
        success, temps = opt.solve()
        if not success:
            return {'success': False, 'message': 'Pas de solution', 'temps': temps}
        
        exams = opt.extract_solution()
        
        return {
            'success': True,
            'temps': temps,
            'nb_examens': len(exams),
            'stats': opt.stats(),
            'message': f'OK en {temps:.1f}s'
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'success': False, 'message': str(e), 'temps': 0}
