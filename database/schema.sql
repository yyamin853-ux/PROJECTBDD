-- =====================================================
-- SCHÉMA COMPLET - PLATEFORME NUM_EXAM
-- =====================================================

-- Supprimer les tables existantes (pour réinitialisation)
DROP TABLE IF EXISTS conflits_detectes CASCADE;
DROP TABLE IF EXISTS examens CASCADE;
DROP TABLE IF EXISTS inscriptions CASCADE;
DROP TABLE IF EXISTS enseignements CASCADE;
DROP TABLE IF EXISTS professeurs CASCADE;
DROP TABLE IF EXISTS lieux_examen CASCADE;
DROP TABLE IF EXISTS modules CASCADE;
DROP TABLE IF EXISTS etudiants CASCADE;
DROP TABLE IF EXISTS formations CASCADE;
DROP TABLE IF EXISTS departements CASCADE;
DROP TABLE IF EXISTS sessions_examen CASCADE;

-- =====================================================
-- TABLE: sessions_examen
-- Périodes d'examens (semestre 1, semestre 2, rattrapage)
-- =====================================================
CREATE TABLE sessions_examen (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL,
    annee_universitaire VARCHAR(10) NOT NULL,
    date_debut DATE NOT NULL,
    date_fin DATE NOT NULL,
    statut VARCHAR(20) DEFAULT 'planification',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLE: departements
-- Les 7 départements de la faculté
-- =====================================================
CREATE TABLE departements (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL UNIQUE,
    code VARCHAR(10) NOT NULL UNIQUE,
    responsable VARCHAR(100),
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- TABLE: formations
-- 200+ offres de formation
-- =====================================================
CREATE TABLE formations (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(200) NOT NULL,
    code VARCHAR(20) NOT NULL UNIQUE,
    dept_id INT NOT NULL REFERENCES departements(id) ON DELETE CASCADE,
    niveau VARCHAR(50) NOT NULL, -- L1, L2, L3, M1, M2
    nb_modules INT DEFAULT 6,
    annee_creation INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_formations_dept ON formations(dept_id);

-- =====================================================
-- TABLE: etudiants
-- ~13,000 étudiants
-- =====================================================
CREATE TABLE etudiants (
    id SERIAL PRIMARY KEY,
    matricule VARCHAR(20) NOT NULL UNIQUE,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    formation_id INT NOT NULL REFERENCES formations(id) ON DELETE CASCADE,
    promo INT NOT NULL, -- Année d'entrée (2021, 2022, etc.)
    email VARCHAR(100),
    telephone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_etudiants_formation ON etudiants(formation_id);
CREATE INDEX idx_etudiants_promo ON etudiants(promo);
CREATE INDEX idx_etudiants_matricule ON etudiants(matricule);

-- =====================================================
-- TABLE: modules
-- Modules d'enseignement (6-9 par formation)
-- =====================================================
CREATE TABLE modules (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(200) NOT NULL,
    code VARCHAR(20) NOT NULL UNIQUE,
    credits INT NOT NULL DEFAULT 6,
    formation_id INT NOT NULL REFERENCES formations(id) ON DELETE CASCADE,
    semestre INT NOT NULL CHECK (semestre IN (1, 2)),
    type_module VARCHAR(50) DEFAULT 'fondamental', -- fondamental, transversal, optionnel
    coefficient INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_modules_formation ON modules(formation_id);
CREATE INDEX idx_modules_semestre ON modules(semestre);

-- =====================================================
-- TABLE: professeurs
-- Enseignants et surveillants
-- =====================================================
CREATE TABLE professeurs (
    id SERIAL PRIMARY KEY,
    matricule VARCHAR(20) NOT NULL UNIQUE,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    dept_id INT NOT NULL REFERENCES departements(id) ON DELETE CASCADE,
    grade VARCHAR(50), -- Professeur, MCA, MCB, MAA, MAB
    specialite VARCHAR(100),
    email VARCHAR(100),
    telephone VARCHAR(20),
    max_surveillance_jour INT DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_professeurs_dept ON professeurs(dept_id);

-- =====================================================
-- TABLE: enseignements
-- Qui enseigne quoi (relation prof-module)
-- =====================================================
CREATE TABLE enseignements (
    id SERIAL PRIMARY KEY,
    prof_id INT NOT NULL REFERENCES professeurs(id) ON DELETE CASCADE,
    module_id INT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    annee_universitaire VARCHAR(10) NOT NULL,
    role VARCHAR(50) DEFAULT 'titulaire', -- titulaire, vacataire
    UNIQUE(prof_id, module_id, annee_universitaire)
);

CREATE INDEX idx_enseignements_prof ON enseignements(prof_id);
CREATE INDEX idx_enseignements_module ON enseignements(module_id);

-- =====================================================
-- TABLE: lieux_examen
-- Amphithéâtres et salles d'examen
-- =====================================================
CREATE TABLE lieux_examen (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(100) NOT NULL UNIQUE,
    type VARCHAR(20) NOT NULL CHECK (type IN ('amphi', 'salle', 'labo')),
    capacite INT NOT NULL,
    capacite_examen INT NOT NULL, -- Capacité réduite en période d'examen (max 20 pour salles)
    batiment VARCHAR(50) NOT NULL,
    etage INT,
    equipements TEXT[], -- {projecteur, tableau, climatisation}
    disponible BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_lieux_type ON lieux_examen(type);
CREATE INDEX idx_lieux_capacite ON lieux_examen(capacite_examen);

-- =====================================================
-- TABLE: inscriptions
-- ~130,000 inscriptions (étudiants x modules)
-- =====================================================
CREATE TABLE inscriptions (
    id SERIAL PRIMARY KEY,
    etudiant_id INT NOT NULL REFERENCES etudiants(id) ON DELETE CASCADE,
    module_id INT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    session_id INT NOT NULL REFERENCES sessions_examen(id) ON DELETE CASCADE,
    annee_universitaire VARCHAR(10) NOT NULL,
    note DECIMAL(5,2),
    statut VARCHAR(20) DEFAULT 'inscrit', -- inscrit, validé, ajourné
    UNIQUE(etudiant_id, module_id, session_id)
);

CREATE INDEX idx_inscriptions_etudiant ON inscriptions(etudiant_id);
CREATE INDEX idx_inscriptions_module ON inscriptions(module_id);
CREATE INDEX idx_inscriptions_session ON inscriptions(session_id);

-- =====================================================
-- TABLE: examens
-- Planning des examens
-- =====================================================
CREATE TABLE examens (
    id SERIAL PRIMARY KEY,
    module_id INT NOT NULL REFERENCES modules(id) ON DELETE CASCADE,
    session_id INT NOT NULL REFERENCES sessions_examen(id) ON DELETE CASCADE,
    prof_surveillant_id INT REFERENCES professeurs(id) ON DELETE SET NULL,
    lieu_id INT REFERENCES lieux_examen(id) ON DELETE SET NULL,
    date_examen DATE NOT NULL,
    heure_debut TIME NOT NULL,
    duree_minutes INT DEFAULT 90,
    nb_inscrits INT DEFAULT 0,
    statut VARCHAR(20) DEFAULT 'planifie', -- planifie, confirme, termine, annule
    observations TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_examens_date ON examens(date_examen);
CREATE INDEX idx_examens_module ON examens(module_id);
CREATE INDEX idx_examens_session ON examens(session_id);
CREATE INDEX idx_examens_prof ON examens(prof_surveillant_id, date_examen);
CREATE INDEX idx_examens_lieu ON examens(lieu_id, date_examen, heure_debut);

-- =====================================================
-- TABLE: conflits_detectes
-- Détection automatique des conflits
-- =====================================================
CREATE TABLE conflits_detectes (
    id SERIAL PRIMARY KEY,
    examen_id INT NOT NULL REFERENCES examens(id) ON DELETE CASCADE,
    type_conflit VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    severite INT DEFAULT 1 CHECK (severite BETWEEN 1 AND 5),
    resolu BOOLEAN DEFAULT FALSE,
    date_detection TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date_resolution TIMESTAMP
);

CREATE INDEX idx_conflits_examen ON conflits_detectes(examen_id);
CREATE INDEX idx_conflits_type ON conflits_detectes(type_conflit);
CREATE INDEX idx_conflits_resolu ON conflits_detectes(resolu);

-- =====================================================
-- VUES ANALYTIQUES
-- =====================================================

-- Vue: Planning complet avec toutes les informations
CREATE OR REPLACE VIEW vue_planning_complet AS
SELECT 
    e.id as examen_id,
    e.date_examen,
    e.heure_debut,
    e.duree_minutes,
    m.code as code_module,
    m.nom as nom_module,
    f.nom as formation,
    d.nom as departement,
    l.nom as lieu,
    l.type as type_lieu,
    l.capacite_examen,
    e.nb_inscrits,
    CONCAT(p.nom, ' ', p.prenom) as surveillant,
    e.statut,
    s.nom as session
FROM examens e
JOIN modules m ON e.module_id = m.id
JOIN formations f ON m.formation_id = f.id
JOIN departements d ON f.dept_id = d.id
LEFT JOIN lieux_examen l ON e.lieu_id = l.id
LEFT JOIN professeurs p ON e.prof_surveillant_id = p.id
JOIN sessions_examen s ON e.session_id = s.id;

-- Vue: KPIs globaux pour le vice-doyen
CREATE OR REPLACE VIEW vue_kpis_globaux AS
SELECT 
    d.nom as departement,
    COUNT(DISTINCT e.id) as nb_examens_planifies,
    COUNT(DISTINCT m.id) as nb_modules_total,
    COUNT(DISTINCT et.id) as nb_etudiants,
    SUM(e.nb_inscrits) as total_inscriptions,
    COUNT(DISTINCT l.id) as nb_lieux_utilises,
    AVG(l.capacite_examen) as capacite_moyenne_lieux,
    COUNT(DISTINCT CASE WHEN c.resolu = FALSE THEN c.id END) as nb_conflits_non_resolus
FROM departements d
LEFT JOIN formations f ON f.dept_id = d.id
LEFT JOIN modules m ON m.formation_id = f.id
LEFT JOIN examens e ON e.module_id = m.id
LEFT JOIN lieux_examen l ON e.lieu_id = l.id
LEFT JOIN etudiants et ON et.formation_id = f.id
LEFT JOIN conflits_detectes c ON c.examen_id = e.id
GROUP BY d.id, d.nom;

-- Vue: Occupation des salles par jour
CREATE OR REPLACE VIEW vue_occupation_salles AS
SELECT 
    e.date_examen,
    l.nom as lieu,
    l.type,
    COUNT(*) as nb_examens,
    SUM(e.nb_inscrits) as total_etudiants,
    l.capacite_examen,
    ROUND((SUM(e.nb_inscrits)::DECIMAL / l.capacite_examen) * 100, 2) as taux_occupation
FROM examens e
JOIN lieux_examen l ON e.lieu_id = l.id
GROUP BY e.date_examen, l.id, l.nom, l.type, l.capacite_examen
ORDER BY e.date_examen, l.nom;

-- =====================================================
-- FONCTIONS POUR DÉTECTION DE CONFLITS
-- =====================================================

-- Fonction: Détecter les conflits étudiants (plus d'1 examen/jour)
CREATE OR REPLACE FUNCTION detecter_conflits_etudiants(session_exam_id INT)
RETURNS TABLE (
    etudiant_id INT,
    date_examen DATE,
    nb_examens BIGINT,
    liste_modules TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        i.etudiant_id,
        e.date_examen,
        COUNT(DISTINCT e.id) as nb_examens,
        STRING_AGG(m.code, ', ') as liste_modules
    FROM inscriptions i
    JOIN examens e ON i.module_id = e.module_id
    JOIN modules m ON e.module_id = m.id
    WHERE e.session_id = session_exam_id
    GROUP BY i.etudiant_id, e.date_examen
    HAVING COUNT(DISTINCT e.id) > 1;
END;
$$ LANGUAGE plpgsql;

-- Fonction: Détecter les conflits professeurs (plus de 3 examens/jour)
CREATE OR REPLACE FUNCTION detecter_conflits_professeurs(session_exam_id INT)
RETURNS TABLE (
    professeur_id INT,
    nom_professeur TEXT,
    date_examen DATE,
    nb_surveillances BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.prof_surveillant_id,
        CONCAT(p.nom, ' ', p.prenom) as nom_professeur,
        e.date_examen,
        COUNT(*) as nb_surveillances
    FROM examens e
    JOIN professeurs p ON e.prof_surveillant_id = p.id
    WHERE e.session_id = session_exam_id
      AND e.prof_surveillant_id IS NOT NULL
    GROUP BY e.prof_surveillant_id, p.nom, p.prenom, e.date_examen
    HAVING COUNT(*) > 3;
END;
$$ LANGUAGE plpgsql;

-- Fonction: Détecter les dépassements de capacité
CREATE OR REPLACE FUNCTION detecter_depassement_capacite(session_exam_id INT)
RETURNS TABLE (
    examen_id INT,
    lieu_nom VARCHAR,
    capacite_max INT,
    nb_inscrits INT,
    depassement INT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.id,
        l.nom,
        l.capacite_examen,
        e.nb_inscrits,
        (e.nb_inscrits - l.capacite_examen) as depassement
    FROM examens e
    JOIN lieux_examen l ON e.lieu_id = l.id
    WHERE e.session_id = session_exam_id
      AND e.nb_inscrits > l.capacite_examen;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- TRIGGERS
-- =====================================================

-- Trigger: Mettre à jour nb_inscrits automatiquement
CREATE OR REPLACE FUNCTION update_nb_inscrits()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE examens
    SET nb_inscrits = (
        SELECT COUNT(*)
        FROM inscriptions
        WHERE module_id = NEW.module_id
          AND session_id = (SELECT session_id FROM examens WHERE id = NEW.examen_id LIMIT 1)
    )
    WHERE module_id = NEW.module_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger: Mettre à jour updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_examens_timestamp
BEFORE UPDATE ON examens
FOR EACH ROW
EXECUTE FUNCTION update_updated_at();

-- =====================================================
-- COMMENTAIRES SUR LES TABLES
-- =====================================================
COMMENT ON TABLE departements IS 'Les 7 départements de la faculté';
COMMENT ON TABLE formations IS '200+ offres de formation (L1-M2)';
COMMENT ON TABLE etudiants IS '~13,000 étudiants inscrits';
COMMENT ON TABLE modules IS 'Modules d''enseignement (6-9 par formation)';
COMMENT ON TABLE inscriptions IS '~130,000 inscriptions étudiants-modules';
COMMENT ON TABLE examens IS 'Planning des examens avec contraintes';
COMMENT ON TABLE lieux_examen IS 'Salles et amphithéâtres (capacité réduite en examen)';
COMMENT ON TABLE professeurs IS 'Enseignants et surveillants';
COMMENT ON TABLE conflits_detectes IS 'Détection automatique des conflits de planning';