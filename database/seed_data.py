"""
Script de génération de données réalistes pour la plateforme Num_Exam
Génère ~13,000 étudiants, 200+ formations, ~130,000 inscriptions
"""

import psycopg2
from faker import Faker
import random
from datetime import datetime, timedelta

fake = Faker('fr_FR')

# Configuration de connexion (à adapter)
DB_CONFIG = {
    'host': 'localhost',
    'database': 'num_exam_db',
    'user': 'postgres',
    'password': '1234'
}

class DataGenerator:
    def __init__(self, db_config):
        self.conn = psycopg2.connect(**db_config)
        self.cursor = self.conn.cursor()
        
    def clear_all_data(self):
        """Nettoyer toutes les données existantes"""
        print("🗑️  Nettoyage des données existantes...")
        tables = [
            'conflits_detectes', 'examens', 'inscriptions', 
            'enseignements', 'professeurs', 'lieux_examen',
            'modules', 'etudiants', 'formations', 
            'departements', 'sessions_examen'
        ]
        for table in tables:
            self.cursor.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
        self.conn.commit()
        print("✅ Nettoyage terminé\n")
    
    def generate_sessions(self):
        """Créer les sessions d'examens"""
        print("📅 Création des sessions d'examens...")
        sessions = [
            ('Semestre 1 - 2024/2025', '2024/2025', '2025-01-15', '2025-01-30', 'planification'),
            ('Semestre 2 - 2024/2025', '2024/2025', '2025-06-10', '2025-06-25', 'future'),
            ('Rattrapage S1 - 2024/2025', '2024/2025', '2025-02-10', '2025-02-15', 'future')
        ]
        
        for nom, annee, debut, fin, statut in sessions:
            self.cursor.execute("""
                INSERT INTO sessions_examen (nom, annee_universitaire, date_debut, date_fin, statut)
                VALUES (%s, %s, %s, %s, %s)
            """, (nom, annee, debut, fin, statut))
        
        self.conn.commit()
        print(f"✅ {len(sessions)} sessions créées\n")
    
    def generate_departments(self):
        """Créer les 7 départements"""
        print("🏛️  Création des départements...")
        departments = [
            ('Informatique', 'INFO'),
            ('Mathématiques', 'MATH'),
            ('Physique', 'PHYS'),
            ('Chimie', 'CHIM'),
            ('Biologie', 'BIO'),
            ('Génie Civil', 'GC'),
            ('Électronique', 'ELEC')
        ]
        
        for nom, code in departments:
            responsable = fake.name()
            email = f"{code.lower()}@university.dz"
            self.cursor.execute("""
                INSERT INTO departements (nom, code, responsable, email)
                VALUES (%s, %s, %s, %s)
            """, (nom, code, responsable, email))
        
        self.conn.commit()
        print(f"✅ {len(departments)} départements créés\n")
        return len(departments)
    
    def generate_formations(self, nb_depts=7):
        """Créer 200+ formations"""
        print("🎓 Création des formations...")
        niveaux = ['L1', 'L2', 'L3', 'M1', 'M2']
        specialites = {
            1: ['Développement Web', 'IA et Data Science', 'Cybersécurité', 'Réseaux', 'Systèmes Embarqués'],
            2: ['Algèbre', 'Analyse', 'Probabilités', 'Mathématiques Appliquées', 'Statistiques'],
            3: ['Physique Fondamentale', 'Physique des Matériaux', 'Astrophysique', 'Énergies Renouvelables'],
            4: ['Chimie Organique', 'Chimie Analytique', 'Chimie Industrielle', 'Pétrochimie'],
            5: ['Génétique', 'Microbiologie', 'Écologie', 'Biotechnologie', 'Biologie Moléculaire'],
            6: ['Construction', 'Géotechnique', 'Hydraulique', 'Structures'],
            7: ['Télécommunications', 'Automatique', 'Électronique Embarquée', 'Instrumentation']
        }
        
        formation_count = 0
        for dept_id in range(1, nb_depts + 1):
            dept_specialites = specialites.get(dept_id, ['Générale'])
            
            for niveau in niveaux:
                for spec in dept_specialites:
                    nb_modules = random.randint(6, 9)
                    code = f"{niveau}-{dept_id:02d}-{formation_count:03d}"
                    nom = f"{niveau} {spec}"
                    annee = random.randint(2015, 2023)
                    
                    self.cursor.execute("""
                        INSERT INTO formations (nom, code, dept_id, niveau, nb_modules, annee_creation)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (nom, code, dept_id, niveau, nb_modules, annee))
                    
                    formation_count += 1
        
        self.conn.commit()
        print(f"✅ {formation_count} formations créées\n")
        return formation_count
    
    def generate_students(self, target=13000):
        """Créer ~13,000 étudiants"""
        print(f"👨‍🎓 Création de {target} étudiants...")
        
        # Récupérer les formations
        self.cursor.execute("SELECT id FROM formations")
        formation_ids = [row[0] for row in self.cursor.fetchall()]
        
        promos = [2020, 2021, 2022, 2023, 2024]
        
        for i in range(target):
            matricule = f"E{2024}{i+1:06d}"
            nom = fake.last_name().upper()
            prenom = fake.first_name()
            formation_id = random.choice(formation_ids)
            promo = random.choice(promos)
            email = f"{prenom.lower()}.{nom.lower()}@etu.university.dz"
            telephone = fake.phone_number()
            
            self.cursor.execute("""
                INSERT INTO etudiants (matricule, nom, prenom, formation_id, promo, email, telephone)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (matricule, nom, prenom, formation_id, promo, email, telephone))
            
            if (i + 1) % 1000 == 0:
                self.conn.commit()
                print(f"   ✓ {i + 1}/{target} étudiants créés")
        
        self.conn.commit()
        print(f"✅ {target} étudiants créés\n")
    
    def generate_modules(self):
        """Créer les modules pour chaque formation"""
        print("📚 Création des modules...")
        
        # Récupérer toutes les formations
        self.cursor.execute("SELECT id, nb_modules FROM formations")
        formations = self.cursor.fetchall()
        
        types_modules = ['fondamental', 'transversal', 'optionnel']
        module_count = 0
        
        for formation_id, nb_modules in formations:
            for i in range(nb_modules):
                semestre = 1 if i < nb_modules // 2 else 2
                code = f"MOD-{formation_id:03d}-{i+1:02d}"
                nom = f"Module {i+1} - {fake.catch_phrase()}"
                credits = random.choice([4, 5, 6, 7])
                type_module = random.choice(types_modules)
                coefficient = random.randint(1, 3)
                
                self.cursor.execute("""
                    INSERT INTO modules (nom, code, credits, formation_id, semestre, type_module, coefficient)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (nom, code, credits, formation_id, semestre, type_module, coefficient))
                
                module_count += 1
        
        self.conn.commit()
        print(f"✅ {module_count} modules créés\n")
        return module_count
    
    def generate_professors(self, nb_per_dept=30):
        """Créer les professeurs"""
        print(f"👨‍🏫 Création des professeurs ({nb_per_dept} par département)...")
        
        grades = ['Professeur', 'MCA', 'MCB', 'MAA', 'MAB']
        prof_count = 0
        
        for dept_id in range(1, 8):  # 7 départements
            for i in range(nb_per_dept):
                matricule = f"P{dept_id:02d}{i+1:04d}"
                nom = fake.last_name().upper()
                prenom = fake.first_name()
                grade = random.choice(grades)
                specialite = fake.job()
                email = f"{prenom.lower()}.{nom.lower()}@university.dz"
                telephone = fake.phone_number()
                max_surveillance = random.choice([2, 3, 4])
                
                self.cursor.execute("""
                    INSERT INTO professeurs 
                    (matricule, nom, prenom, dept_id, grade, specialite, email, telephone, max_surveillance_jour)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (matricule, nom, prenom, dept_id, grade, specialite, email, telephone, max_surveillance))
                
                prof_count += 1
        
        self.conn.commit()
        print(f"✅ {prof_count} professeurs créés\n")
        return prof_count
    
    def generate_exam_locations(self):
        """Créer les lieux d'examen"""
        print("🏢 Création des lieux d'examen...")
        
        # Amphithéâtres (grandes capacités)
        amphis = []
        for i in range(1, 16):  # 15 amphithéâtres
            capacite = random.choice([200, 250, 300, 350, 400, 500])
            capacite_examen = min(capacite, random.randint(150, 300))
            amphis.append((
                f"Amphithéâtre {i}",
                'amphi',
                capacite,
                capacite_examen,
                f"Bâtiment {chr(65 + (i-1)//3)}",  # A, B, C, D, E
                random.randint(0, 3),
                ['projecteur', 'tableau', 'sonorisation']
            ))
        
        # Salles (capacité limitée à 20 en examen)
        salles = []
        for i in range(1, 51):  # 50 salles
            capacite = random.choice([30, 35, 40, 45, 50])
            capacite_examen = 20  # Limité à 20 en période d'examen
            salles.append((
                f"Salle {i}",
                'salle',
                capacite,
                capacite_examen,
                f"Bâtiment {chr(65 + random.randint(0, 4))}",
                random.randint(1, 4),
                ['tableau', 'climatisation']
            ))
        
        # Laboratoires
        labos = []
        for i in range(1, 11):  # 10 laboratoires
            capacite = random.choice([20, 25, 30])
            capacite_examen = 15
            labos.append((
                f"Laboratoire {i}",
                'labo',
                capacite,
                capacite_examen,
                f"Bâtiment {chr(65 + random.randint(0, 4))}",
                random.randint(1, 3),
                ['equipements_specialises', 'ordinateurs']
            ))
        
        all_locations = amphis + salles + labos
        
        for nom, type_lieu, cap, cap_exam, bat, etage, equip in all_locations:
            self.cursor.execute("""
                INSERT INTO lieux_examen 
                (nom, type, capacite, capacite_examen, batiment, etage, equipements)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (nom, type_lieu, cap, cap_exam, bat, etage, equip))
        
        self.conn.commit()
        print(f"✅ {len(all_locations)} lieux créés\n")
        return len(all_locations)
    
    def generate_inscriptions(self, target=130000):
        """Créer ~130,000 inscriptions"""
        print(f"📝 Création de {target} inscriptions...")
        
        self.cursor.execute("SELECT id, formation_id FROM etudiants")
        etudiants = self.cursor.fetchall()
        
        self.cursor.execute("SELECT id, formation_id FROM modules")
        modules = self.cursor.fetchall()
        
        # Regrouper modules par formation
        modules_by_formation = {}
        for module_id, formation_id in modules:
            if formation_id not in modules_by_formation:
                modules_by_formation[formation_id] = []
            modules_by_formation[formation_id].append(module_id)
        
        inscription_count = 0
        for etudiant_id, formation_id in etudiants:
            # Chaque étudiant s'inscrit à 6-9 modules de sa formation
            available_modules = modules_by_formation.get(formation_id, [])
            if not available_modules:
                continue
            
            nb_inscriptions = min(random.randint(6, 9), len(available_modules))
            selected_modules = random.sample(available_modules, nb_inscriptions)
            
            for module_id in selected_modules:
                self.cursor.execute("""
                    INSERT INTO inscriptions 
                    (etudiant_id, module_id, session_id, annee_universitaire, statut)
                    VALUES (%s, %s, %s, %s, %s)
                """, (etudiant_id, module_id, 1, '2024/2025', 'inscrit'))
                
                inscription_count += 1
            
            if inscription_count % 10000 == 0:
                self.conn.commit()
                print(f"   ✓ {inscription_count} inscriptions créées")
        
        self.conn.commit()
        print(f"✅ {inscription_count} inscriptions créées\n")
        return inscription_count
    
    def close(self):
        """Fermer la connexion"""
        self.cursor.close()
        self.conn.close()

def main():
    print("\n" + "="*60)
    print("🚀 GÉNÉRATION DES DONNÉES - PLATEFORME NUM_EXAM")
    print("="*60 + "\n")
    
    generator = DataGenerator(DB_CONFIG)
    
    try:
        # Nettoyer les données existantes
        generator.clear_all_data()
        
        # Générer les données
        generator.generate_sessions()
        generator.generate_departments()
        generator.generate_formations()
        generator.generate_students(13000)
        generator.generate_modules()
        generator.generate_professors(30)
        generator.generate_exam_locations()
        generator.generate_inscriptions(130000)
        
        print("\n" + "="*60)
        print("✅ GÉNÉRATION TERMINÉE AVEC SUCCÈS!")
        print("="*60 + "\n")
        
        # Statistiques finales
        generator.cursor.execute("SELECT COUNT(*) FROM etudiants")
        nb_etudiants = generator.cursor.fetchone()[0]
        
        generator.cursor.execute("SELECT COUNT(*) FROM formations")
        nb_formations = generator.cursor.fetchone()[0]
        
        generator.cursor.execute("SELECT COUNT(*) FROM modules")
        nb_modules = generator.cursor.fetchone()[0]
        
        generator.cursor.execute("SELECT COUNT(*) FROM inscriptions")
        nb_inscriptions = generator.cursor.fetchone()[0]
        
        generator.cursor.execute("SELECT COUNT(*) FROM professeurs")
        nb_profs = generator.cursor.fetchone()[0]
        
        generator.cursor.execute("SELECT COUNT(*) FROM lieux_examen")
        nb_lieux = generator.cursor.fetchone()[0]
        
        print("📊 STATISTIQUES FINALES:")
        print(f"   • Étudiants: {nb_etudiants:,}")
        print(f"   • Formations: {nb_formations}")
        print(f"   • Modules: {nb_modules}")
        print(f"   • Inscriptions: {nb_inscriptions:,}")
        print(f"   • Professeurs: {nb_profs}")
        print(f"   • Lieux d'examen: {nb_lieux}")
        print()
        
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        generator.conn.rollback()
    
    finally:
        generator.close()

if __name__ == "__main__":
    main()