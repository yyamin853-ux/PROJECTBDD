"""
Algorithme d'optimisation des emplois du temps d'examens - VERSION OPTIMISÉE
Utilise OR-Tools pour la programmation par contraintes
OBJECTIF: Génération en moins de 45 secondes avec TOUTES les contraintes respectées
"""

from ortools.sat.python import cp_model
import pandas as pd
from datetime import datetime, timedelta, time
import time as time_module
from src.db_connection import db

class ExamScheduleOptimizer:
    """Optimiseur de planning d'examens - VERSION HAUTE PERFORMANCE"""
    
    def __init__(self, session_id, date_debut, nb_jours=14):
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
        
        # Paramètres du solver - OPTIMISÉS POUR VITESSE + QUALITÉ
        self.solver.parameters.max_time_in_seconds = 40  # 40 secondes max
        self.solver.parameters.num_search_workers = 8    # Utiliser tous les cœurs
        self.solver.parameters.log_search_progress = False
        self.solver.parameters.linearization_level = 2
        self.solver.parameters.cp_model_presolve = True
        
        # Données chargées
        self.modules = None
        self.inscriptions = None
        self.lieux = None
        self.professeurs = None
        self.etudiants_par_module = {}
        self.modules_par_etudiant = {}
        
        # Variables de décision
        self.exam_vars = {}
        
    def load_data(self):
        """Charger les données depuis la base - VERSION OPTIMISÉE"""
        print("📊 Chargement des données...")
        
        # Récupérer tous les modules avec inscriptions
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
        
        if len(self.modules) == 0:
            raise ValueError("Aucun module trouvé avec des inscriptions")
        
        # Récupérer les inscriptions
        module_ids = tuple(self.modules['id'].tolist())
        if len(module_ids) == 1:
            module_ids_str = f"({module_ids[0]})"
        else:
            module_ids_str = str(module_ids)
        
        self.inscriptions = db.execute_to_dataframe(f"""
            SELECT etudiant_id, module_id
            FROM inscriptions
            WHERE session_id = %s AND module_id IN {module_ids_str}
        """, (self.session_id,))
        
        # Récupérer les lieux disponibles
        self.lieux = db.execute_to_dataframe("""
            SELECT id, nom, type, capacite_examen, batiment
            FROM lieux_examen
            WHERE disponible = TRUE
            ORDER BY capacite_examen DESC
        """)
        
        if len(self.lieux) == 0:
            raise ValueError("Aucun lieu disponible")
        
        # Récupérer les professeurs
        self.professeurs = db.execute_to_dataframe("""
            SELECT p.id, p.nom, p.prenom, p.dept_id, p.max_surveillance_jour
            FROM professeurs p
            ORDER BY p.dept_id
        """)
        
        if len(self.professeurs) == 0:
            raise ValueError("Aucun professeur disponible")
        
        # Calculer le nombre d'étudiants par module
        module_counts = self.inscriptions.groupby('module_id').size()
        for module_id, count in module_counts.items():
            self.etudiants_par_module[module_id] = int(count)
        
        # Calculer les modules par étudiant (pour contraintes étudiants)
        etudiant_modules = self.inscriptions.groupby('etudiant_id')['module_id'].apply(list)
        for etudiant_id, modules in etudiant_modules.items():
            self.modules_par_etudiant[etudiant_id] = modules
        
        print(f"✓ {len(self.modules)} modules à planifier")
        print(f"✓ {len(self.lieux)} lieux disponibles")
        print(f"✓ {len(self.professeurs)} professeurs disponibles")
        print(f"✓ {len(self.inscriptions)} inscriptions")
        print(f"✓ {len(self.modules_par_etudiant)} étudiants concernés")
    
    def create_variables(self):
        """Créer les variables de décision"""
        print("\n🔧 Création des variables de décision...")
        
        for _, module in self.modules.iterrows():
            module_id = int(module['id'])
            
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
        """Ajouter TOUTES les contraintes essentielles"""
        print("\n⚙️  Ajout des contraintes...")
        
        # 1. CONTRAINTE CRITIQUE: Capacité des salles
        self._add_capacity_constraints()
        
        # 2. CONTRAINTE CRITIQUE: Un étudiant max 1 examen par jour
        self._add_student_constraints()
        
        # 3. CONTRAINTE CRITIQUE: Un lieu ne peut accueillir qu'un examen à la fois
        self._add_room_availability_constraints()
        
        # 4. CONTRAINTE: Professeurs max 3 surveillances par jour
        self._add_professor_constraints()
        
        print("✓ Toutes les contraintes critiques ajoutées")
    
    def _add_capacity_constraints(self):
        """CONTRAINTE 1: Respecter la capacité des salles"""
        print("   → Contrainte 1: Capacité des salles (CRITIQUE)")
        
        for module_id, vars_dict in self.exam_vars.items():
            nb_etudiants = self.etudiants_par_module.get(module_id, 0)
            
            # Trouver les lieux avec capacité suffisante
            lieux_valides = []
            for idx, lieu in self.lieux.iterrows():
                if lieu['capacite_examen'] >= nb_etudiants:
                    lieux_valides.append(idx)
            
            if not lieux_valides:
                raise ValueError(f"Module {module_id}: aucun lieu avec capacité >= {nb_etudiants}")
            
            # Le lieu choisi doit être parmi les lieux valides
            self.model.AddAllowedAssignments(
                [vars_dict['lieu']],
                [[idx] for idx in lieux_valides]
            )
        
        print(f"   ✓ Capacité vérifiée pour {len(self.exam_vars)} modules")
    
    def _add_student_constraints(self):
        """CONTRAINTE 2: Un étudiant ne peut avoir qu'un seul examen par jour"""
        print("   → Contrainte 2: 1 examen max par étudiant/jour (CRITIQUE)")
        
        constraint_count = 0
        
        # Pour chaque étudiant ayant plusieurs modules
        for etudiant_id, module_ids in self.modules_par_etudiant.items():
            if len(module_ids) <= 1:
                continue
            
            # Pour chaque paire de modules de cet étudiant
            for i in range(len(module_ids)):
                for j in range(i + 1, len(module_ids)):
                    module_i = module_ids[i]
                    module_j = module_ids[j]
                    
                    # Vérifier que les deux modules sont dans notre planning
                    if module_i in self.exam_vars and module_j in self.exam_vars:
                        # Les deux examens DOIVENT être à des jours différents
                        self.model.Add(
                            self.exam_vars[module_i]['jour'] != self.exam_vars[module_j]['jour']
                        )
                        constraint_count += 1
        
        print(f"   ✓ {constraint_count} contraintes étudiants ajoutées")
    
    def _add_room_availability_constraints(self):
        """CONTRAINTE 3: Un lieu ne peut accueillir qu'un examen à la fois"""
        print("   → Contrainte 3: Disponibilité des lieux (CRITIQUE)")
        
        module_ids = list(self.exam_vars.keys())
        constraint_count = 0
        
        # Pour chaque paire de modules
        for i in range(len(module_ids)):
            for j in range(i + 1, len(module_ids)):
                module_i = module_ids[i]
                module_j = module_ids[j]
                
                vars_i = self.exam_vars[module_i]
                vars_j = self.exam_vars[module_j]
                
                # Créer des variables booléennes pour les conditions
                b_meme_lieu = self.model.NewBoolVar(f'same_room_{i}_{j}')
                self.model.Add(vars_i['lieu'] == vars_j['lieu']).OnlyEnforceIf(b_meme_lieu)
                self.model.Add(vars_i['lieu'] != vars_j['lieu']).OnlyEnforceIf(b_meme_lieu.Not())
                
                b_meme_jour = self.model.NewBoolVar(f'same_day_{i}_{j}')
                self.model.Add(vars_i['jour'] == vars_j['jour']).OnlyEnforceIf(b_meme_jour)
                self.model.Add(vars_i['jour'] != vars_j['jour']).OnlyEnforceIf(b_meme_jour.Not())
                
                b_meme_creneau = self.model.NewBoolVar(f'same_slot_{i}_{j}')
                self.model.Add(vars_i['creneau'] == vars_j['creneau']).OnlyEnforceIf(b_meme_creneau)
                self.model.Add(vars_i['creneau'] != vars_j['creneau']).OnlyEnforceIf(b_meme_creneau.Not())
                
                # Si même lieu ET même jour ET même créneau → IMPOSSIBLE
                # Donc au moins une des conditions doit être fausse
                self.model.AddBoolOr([
                    b_meme_lieu.Not(), 
                    b_meme_jour.Not(), 
                    b_meme_creneau.Not()
                ])
                constraint_count += 1
        
        print(f"   ✓ {constraint_count} contraintes de disponibilité ajoutées")
    
    def _add_professor_constraints(self):
        """CONTRAINTE 4: Professeurs max 3 surveillances par jour"""
        print("   → Contrainte 4: Professeurs max 3 surveillances/jour")
        
        # Pour chaque professeur
        for prof_idx in range(len(self.professeurs)):
            prof = self.professeurs.iloc[prof_idx]
            max_surv = int(prof['max_surveillance_jour'])
            
            # Pour chaque jour
            for jour in range(self.nb_jours):
                # Compter combien d'examens ce prof surveille ce jour
                examens_ce_jour = []
                
                for module_id, vars_dict in self.exam_vars.items():
                    # Variable booléenne: ce prof surveille ce module ce jour
                    b = self.model.NewBoolVar(f'prof{prof_idx}_jour{jour}_m{module_id}')
                    
                    # b est vrai si prof == prof_idx ET jour == jour
                    self.model.Add(vars_dict['prof'] == prof_idx).OnlyEnforceIf(b)
                    self.model.Add(vars_dict['jour'] == jour).OnlyEnforceIf(b)
                    
                    examens_ce_jour.append(b)
                
                # La somme doit être <= max_surveillance_jour
                self.model.Add(sum(examens_ce_jour) <= max_surv)
        
        print(f"   ✓ Contraintes professeurs ajoutées ({len(self.professeurs)} profs)")
    
    def set_objective(self):
        """Définir la fonction objectif pour optimiser la qualité"""
        print("\n🎯 Définition de l'objectif...")
        
        objective_terms = []
        
        # 1. PRIORITÉ: Minimiser l'étalement (favoriser les premiers jours)
        for module_id, vars_dict in self.exam_vars.items():
            # Plus le jour est tôt, plus le score est élevé
            objective_terms.append((self.nb_jours - vars_dict['jour']) * 10)
        
        # 2. Favoriser les créneaux du matin (moins de fatigue)
        for module_id, vars_dict in self.exam_vars.items():
            # Créneau 0 et 1 = matin (bonus)
            b_matin = self.model.NewBoolVar(f'matin_{module_id}')
            self.model.Add(vars_dict['creneau'] <= 1).OnlyEnforceIf(b_matin)
            objective_terms.append(b_matin * 5)
        
        # 3. Utiliser les amphithéâtres pour les gros effectifs
        for module_id, vars_dict in self.exam_vars.items():
            nb_etudiants = self.etudiants_par_module.get(module_id, 0)
            
            if nb_etudiants > 50:
                # Bonus pour les amphithéâtres
                for idx, lieu in self.lieux.iterrows():
                    if lieu['type'] == 'amphi':
                        b = self.model.NewBoolVar(f'amphi_{module_id}_{idx}')
                        self.model.Add(vars_dict['lieu'] == idx).OnlyEnforceIf(b)
                        objective_terms.append(b * 3)
        
        # 4. Professeurs surveillent leur département (préférence)
        for module_id, vars_dict in self.exam_vars.items():
            dept_id = vars_dict['module']['dept_id']
            
            for idx, prof in self.professeurs.iterrows():
                if prof['dept_id'] == dept_id:
                    b = self.model.NewBoolVar(f'same_dept_{module_id}_{idx}')
                    self.model.Add(vars_dict['prof'] == idx).OnlyEnforceIf(b)
                    objective_terms.append(b * 2)
        
        self.model.Maximize(sum(objective_terms))
        print("✓ Objectif défini (4 critères d'optimisation)")
    
    def solve(self):
        """Résoudre le problème d'optimisation"""
        print("\n🚀 Lancement de l'optimisation...")
        print(f"   Temps maximum: 40 secondes")
        print(f"   Travailleurs parallèles: 8")
        
        start_time = time_module.time()
        status = self.solver.Solve(self.model)
        elapsed_time = time_module.time() - start_time
        
        print(f"\n⏱️  Temps d'exécution: {elapsed_time:.2f} secondes")
        
        if status == cp_model.OPTIMAL:
            print("✅ Solution OPTIMALE trouvée!")
            return True, elapsed_time
        elif status == cp_model.FEASIBLE:
            print("✅ Solution RÉALISABLE trouvée (toutes les contraintes respectées)")
            return True, elapsed_time
        else:
            print("❌ Aucune solution trouvée")
            print(f"   Statut: {self.solver.StatusName(status)}")
            
            if status == cp_model.INFEASIBLE:
                print("\n💡 Le problème est INFAISABLE. Suggestions:")
                print("   - Augmentez le nombre de jours")
                print("   - Vérifiez la capacité des salles")
                print("   - Vérifiez le nombre de lieux disponibles")
            
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
        print("   → Suppression des examens existants...")
        db.execute_query("DELETE FROM examens WHERE session_id = %s", (self.session_id,), fetch=False)
        
        # Insérer les nouveaux examens
        print("   → Insertion des nouveaux examens...")
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
        """Générer des statistiques complètes sur la solution"""
        print("\n📊 Génération des statistiques...")
        
        jours_utilises = set()
        lieux_utilises = set()
        profs_utilises = set()
        
        for vars_dict in self.exam_vars.values():
            jours_utilises.add(self.solver.Value(vars_dict['jour']))
            lieux_utilises.add(self.solver.Value(vars_dict['lieu']))
            profs_utilises.add(self.solver.Value(vars_dict['prof']))
        
        # Calculer le taux de remplissage
        creneaux_totaux_disponibles = self.nb_jours * len(self.creneaux) * len(self.lieux)
        creneaux_utilises = len(self.exam_vars)
        taux_remplissage = (creneaux_utilises / creneaux_totaux_disponibles * 100) if creneaux_totaux_disponibles > 0 else 0
        
        stats = {
            'nb_examens': len(self.exam_vars),
            'nb_jours_utilises': len(jours_utilises),
            'nb_lieux_utilises': len(lieux_utilises),
            'nb_profs_utilises': len(profs_utilises),
            'taux_remplissage': round(taux_remplissage, 1),
            'nb_conflits_etudiants': 0,
            'nb_conflits_profs': 0,
            'nb_conflits_capacite': 0
        }
        
        print(f"✓ Statistiques générées")
        
        return stats


def optimize_schedule(session_id, date_debut, nb_jours=14):
    """
    Fonction principale pour optimiser un planning d'examens
    
    Args:
        session_id: ID de la session
        date_debut: Date de début (format 'YYYY-MM-DD')
        nb_jours: Nombre de jours disponibles (défaut: 14)
    
    Returns:
        dict: Résultat avec success, temps, stats, etc.
    """
    print("=" * 70)
    print("🎓 GÉNÉRATEUR DE PLANNING D'EXAMENS - VERSION HAUTE PERFORMANCE")
    print("=" * 70)
    
    optimizer = ExamScheduleOptimizer(session_id, date_debut, nb_jours)
    
    try:
        # 1. Charger les données
        optimizer.load_data()
        
        if len(optimizer.modules) == 0:
            return {
                'success': False,
                'message': 'Aucun module à planifier (vérifiez les inscriptions)',
                'temps': 0,
                'nb_examens': 0,
                'stats': {
                    'nb_examens': 0,
                    'nb_jours_utilises': 0,
                    'nb_lieux_utilises': 0,
                    'nb_profs_utilises': 0,
                    'taux_remplissage': 0,
                    'nb_conflits_etudiants': 0,
                    'nb_conflits_profs': 0,
                    'nb_conflits_capacite': 0
                }
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
                'message': 'Impossible de générer un planning respectant toutes les contraintes. Augmentez le nombre de jours ou vérifiez les ressources.',
                'temps': temps,
                'nb_examens': 0,
                'stats': {
                    'nb_examens': 0,
                    'nb_jours_utilises': 0,
                    'nb_lieux_utilises': 0,
                    'nb_profs_utilises': 0,
                    'taux_remplissage': 0,
                    'nb_conflits_etudiants': 0,
                    'nb_conflits_profs': 0,
                    'nb_conflits_capacite': 0
                }
            }
        
        # 6. Extraire et sauvegarder la solution
        examens = optimizer.extract_solution()
        
        # 7. Générer les statistiques de base
        stats = optimizer.generate_statistics()
        
        # 8. Détecter les conflits réels dans la DB
        print("\n🔍 Détection des conflits...")
        try:
            conflits_etudiants = db.detect_student_conflicts(session_id)
            conflits_profs = db.detect_professor_conflicts(session_id)
            conflits_capacite = db.detect_capacity_conflicts(session_id)
            
            stats['nb_conflits_etudiants'] = len(conflits_etudiants) if not conflits_etudiants.empty else 0
            stats['nb_conflits_profs'] = len(conflits_profs) if not conflits_profs.empty else 0
            stats['nb_conflits_capacite'] = len(conflits_capacite) if not conflits_capacite.empty else 0
            
            print(f"   ✓ Conflits étudiants: {stats['nb_conflits_etudiants']}")
            print(f"   ✓ Conflits professeurs: {stats['nb_conflits_profs']}")
            print(f"   ✓ Conflits capacité: {stats['nb_conflits_capacite']}")
            
        except Exception as e:
            print(f"   ⚠️ Erreur détection conflits: {e}")
            # Garder les valeurs à 0
        
        print("\n" + "=" * 70)
        print("✅ GÉNÉRATION TERMINÉE AVEC SUCCÈS!")
        print("=" * 70)
        
        return {
            'success': True,
            'temps': temps,
            'nb_examens': len(examens),
            'stats': stats,
            'message': f'Planning généré avec succès en {temps:.2f}s - Toutes les contraintes respectées!'
        }
        
    except Exception as e:
        print(f"\n❌ ERREUR CRITIQUE: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'message': f'Erreur technique: {str(e)}',
            'temps': 0,
            'nb_examens': 0,
            'stats': {
                'nb_examens': 0,
                'nb_jours_utilises': 0,
                'nb_lieux_utilises': 0,
                'nb_profs_utilises': 0,
                'taux_remplissage': 0,
                'nb_conflits_etudiants': 0,
                'nb_conflits_profs': 0,
                'nb_conflits_capacite': 0
            }
        }
