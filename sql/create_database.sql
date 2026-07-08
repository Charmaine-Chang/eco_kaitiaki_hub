-- ============================================================================
-- Eco Kaitiaki Hub Database Schema
-- MySQL 5.7+ / 8.0+
-- ============================================================================

SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================================
-- DROP TABLES
-- ============================================================================

DROP TABLE IF EXISTS update_likes;
DROP TABLE IF EXISTS update_comments;
DROP TABLE IF EXISTS group_update_images;
DROP TABLE IF EXISTS group_updates;
DROP TABLE IF EXISTS knowledge_hub_revision;
DROP TABLE IF EXISTS knowledge_hub;
DROP TABLE IF EXISTS inventory_log;
DROP TABLE IF EXISTS inventory_items;
DROP TABLE IF EXISTS storage_area;
DROP TABLE IF EXISTS bait_station_records;
DROP TABLE IF EXISTS bait_stations;
DROP TABLE IF EXISTS observation_notes;
DROP TABLE IF EXISTS trap_catches;
DROP TABLE IF EXISTS traps;
DROP TABLE IF EXISTS operator_lines;
DROP TABLE IF EXISTS `lines`;
DROP TABLE IF EXISTS role_upgrade_requests;
DROP TABLE IF EXISTS group_membership;
DROP TABLE IF EXISTS `groups`;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS equipment_status;
DROP TABLE IF EXISTS trap_condition;
DROP TABLE IF EXISTS bait_type;
DROP TABLE IF EXISTS trap_status;
DROP TABLE IF EXISTS species;
DROP TABLE IF EXISTS trap_type;
DROP TABLE IF EXISTS bait_station_type;
DROP TABLE IF EXISTS roles;
DROP TABLE IF EXISTS bait_ingredients;
DROP TABLE IF EXISTS bait_formulations;

-- ============================================================================
-- LOOKUP TABLES
-- ============================================================================

CREATE TABLE roles (
    role_id INT AUTO_INCREMENT PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE trap_type (
    trap_type_id INT AUTO_INCREMENT PRIMARY KEY,
    trap_type_name VARCHAR(50) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE bait_station_type (
    bait_station_type_id INT AUTO_INCREMENT PRIMARY KEY,
    bait_station_type_name VARCHAR(50) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE species (
    species_id INT AUTO_INCREMENT PRIMARY KEY,
    species_name VARCHAR(50) NOT NULL,
    species_color VARCHAR(7)
) ENGINE=InnoDB;

CREATE TABLE trap_status (
    trap_status_id INT AUTO_INCREMENT PRIMARY KEY,
    status_name VARCHAR(50) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE bait_type (
    bait_type_id INT AUTO_INCREMENT PRIMARY KEY,
    bait_type_name VARCHAR(50) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE trap_condition (
    trap_condition_id INT AUTO_INCREMENT PRIMARY KEY,
    trap_condition_name VARCHAR(100) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE equipment_status (
    equipment_status_id INT AUTO_INCREMENT PRIMARY KEY,
    equipment_status_name VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- ============================================================================
-- USERS
-- ============================================================================

CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    phone VARCHAR(50),
    email VARCHAR(255) UNIQUE,
    emergency_contact VARCHAR(50),
    password_hash VARCHAR(255) NOT NULL,
    status ENUM('Active', 'Inactive', 'Suspended') DEFAULT 'Active',
    profile_photo VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ============================================================================
-- GROUPS
-- ============================================================================

CREATE TABLE `groups` (
    group_id INT AUTO_INCREMENT PRIMARY KEY,
    group_name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    branding_image VARCHAR(255) DEFAULT 'default_group.png',
    geographic_area VARCHAR(100),
    visibility ENUM('public', 'private') NOT NULL DEFAULT 'public',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INT,
    status ENUM('active', 'inactive', 'pending') NOT NULL DEFAULT 'pending',
    primary_color VARCHAR(7) DEFAULT '#1a5e20',
    boundary_geojson TEXT,
    region TEXT,
    latitude DOUBLE,
    longitude DOUBLE,
    FOREIGN KEY (created_by) REFERENCES users(user_id)
) ENGINE=InnoDB;

CREATE TABLE group_membership (
    membership_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    role_id INT NOT NULL,
    group_id INT NOT NULL,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    membership_status VARCHAR(50) NOT NULL DEFAULT 'active',
    UNIQUE(user_id, group_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(role_id),
    FOREIGN KEY (group_id) REFERENCES `groups`(group_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE role_upgrade_requests (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    group_id INT NOT NULL,
    requested_role_id INT NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL,
    UNIQUE(user_id, group_id, requested_role_id, status),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES `groups`(group_id) ON DELETE CASCADE,
    FOREIGN KEY (requested_role_id) REFERENCES roles(role_id)
) ENGINE=InnoDB;

-- ============================================================================
-- LINES
-- ============================================================================

CREATE TABLE `lines` (
    line_id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    line_name VARCHAR(50),
    line_type ENUM('trap', 'bait_station') DEFAULT 'trap',
    status ENUM('active', 'inactive') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES `groups`(group_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE operator_lines (
    user_id INT,
    line_id INT,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, line_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (line_id) REFERENCES `lines`(line_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================================
-- STORAGE / INVENTORY
-- ============================================================================

CREATE TABLE storage_area (
    storage_area_id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    storage_area_name VARCHAR(50) NOT NULL,
    FOREIGN KEY (group_id) REFERENCES `groups`(group_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE inventory_items (
    item_id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    storage_area_id INT,
    item_category VARCHAR(50) NOT NULL,
    item_name VARCHAR(50) NOT NULL,
    quantity DOUBLE DEFAULT 0,
    unit_of_measure VARCHAR(50),
    threshold DOUBLE DEFAULT 0,
    line_id INT,
    is_retired TINYINT(1) DEFAULT 0,
    retired_at TIMESTAMP NULL,
    FOREIGN KEY (group_id) REFERENCES `groups`(group_id) ON DELETE CASCADE,
    FOREIGN KEY (storage_area_id) REFERENCES storage_area(storage_area_id) ON DELETE SET NULL,
    FOREIGN KEY (line_id) REFERENCES `lines`(line_id)
) ENGINE=InnoDB;

CREATE TABLE inventory_log (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    user_id INT,
    action_type VARCHAR(50) NOT NULL,
    target_item_type VARCHAR(50) NOT NULL,
    target_item_id INT NOT NULL,
    previous_location VARCHAR(100),
    new_location VARCHAR(100),
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES `groups`(group_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE=InnoDB;

-- ============================================================================
-- TRAPS
-- ============================================================================

CREATE TABLE traps (
    trap_code VARCHAR(50) PRIMARY KEY,
    trap_type_id INT,
    line_id INT,
    equipment_status_id INT,
    storage_area_id INT,
    latitude DOUBLE,
    longitude DOUBLE,
    status ENUM('active', 'inactive') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trap_type_id) REFERENCES trap_type(trap_type_id),
    FOREIGN KEY (line_id) REFERENCES `lines`(line_id),
    FOREIGN KEY (equipment_status_id) REFERENCES equipment_status(equipment_status_id),
    FOREIGN KEY (storage_area_id) REFERENCES storage_area(storage_area_id)
) ENGINE=InnoDB;

CREATE TABLE trap_catches (
    catches_id INT AUTO_INCREMENT PRIMARY KEY,
    trap_code VARCHAR(50),
    `date` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    recorded_by INT,
    species_id INT,
    sex ENUM('Male', 'Female', 'Unknown'),
    maturity ENUM('Juvenile', 'Adult', 'Unknown'),
    trap_status_id INT,
    rebaited TINYINT(1) DEFAULT 0,
    bait_type_id INT,
    bait_amount DOUBLE,
    trap_condition_id INT,
    strikes INT DEFAULT 0,
    note TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trap_code) REFERENCES traps(trap_code) ON DELETE CASCADE,
    FOREIGN KEY (recorded_by) REFERENCES users(user_id),
    FOREIGN KEY (species_id) REFERENCES species(species_id),
    FOREIGN KEY (trap_status_id) REFERENCES trap_status(trap_status_id),
    FOREIGN KEY (bait_type_id) REFERENCES bait_type(bait_type_id),
    FOREIGN KEY (trap_condition_id) REFERENCES trap_condition(trap_condition_id)
) ENGINE=InnoDB;

CREATE TABLE observation_notes (
    note_id INT AUTO_INCREMENT PRIMARY KEY,
    catch_id INT,
    observation_type VARCHAR(50),
    description TEXT,
    related_line_id INT,
    user_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (catch_id) REFERENCES trap_catches(catches_id) ON DELETE CASCADE,
    FOREIGN KEY (related_line_id) REFERENCES `lines`(line_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE=InnoDB;

-- ============================================================================
-- BAIT STATIONS
-- ============================================================================

CREATE TABLE bait_stations (
    bait_station_code VARCHAR(50) PRIMARY KEY,
    line_id INT,
    bait_station_type_id INT,
    equipment_status_id INT,
    storage_area_id INT,
    latitude DOUBLE,
    longitude DOUBLE,
    status ENUM('active', 'inactive') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (line_id) REFERENCES `lines`(line_id),
    FOREIGN KEY (bait_station_type_id) REFERENCES bait_station_type(bait_station_type_id),
    FOREIGN KEY (equipment_status_id) REFERENCES equipment_status(equipment_status_id),
    FOREIGN KEY (storage_area_id) REFERENCES storage_area(storage_area_id)
) ENGINE=InnoDB;

CREATE TABLE bait_station_records (
    record_id INT AUTO_INCREMENT PRIMARY KEY,
    bait_station_code VARCHAR(50),
    recorded_by INT,
    target_species_id INT,
    bait_type_id INT,
    `date` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active_ingredient VARCHAR(50),
    formulation VARCHAR(50),
    concentration DOUBLE,
    bait_remaining DOUBLE DEFAULT 0,
    bait_removed DOUBLE DEFAULT 0,
    bait_added DOUBLE DEFAULT 0,
    notes TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bait_station_code) REFERENCES bait_stations(bait_station_code) ON DELETE CASCADE,
    FOREIGN KEY (recorded_by) REFERENCES users(user_id),
    FOREIGN KEY (target_species_id) REFERENCES species(species_id),
    FOREIGN KEY (bait_type_id) REFERENCES bait_type(bait_type_id)
) ENGINE=InnoDB;

CREATE TABLE bait_ingredients (
    ingredient_id INT AUTO_INCREMENT PRIMARY KEY,
    ingredient_name VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE bait_formulations (
    formulation_id INT AUTO_INCREMENT PRIMARY KEY,
    formulation_name VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- ============================================================================
-- KNOWLEDGE HUB
-- ============================================================================

CREATE TABLE knowledge_hub (
    entry_id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    user_id INT NOT NULL,
    category VARCHAR(50) NOT NULL,
    title VARCHAR(100) NOT NULL,
    content TEXT,
    photo_url VARCHAR(255),
    is_featured TINYINT(1) DEFAULT 0,
    is_published TINYINT(1) DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL,
    FOREIGN KEY (group_id) REFERENCES `groups`(group_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE=InnoDB;

CREATE TABLE knowledge_hub_revision (
    revision_id INT AUTO_INCREMENT PRIMARY KEY,
    entry_id INT NOT NULL,
    version_number INT NOT NULL,
    category VARCHAR(50) NOT NULL,
    title VARCHAR(100) NOT NULL,
    content TEXT,
    photo_url VARCHAR(255),
    is_featured TINYINT(1) DEFAULT 0,
    is_published TINYINT(1) DEFAULT 1,
    archived_by_user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (entry_id, version_number),
    FOREIGN KEY (entry_id) REFERENCES knowledge_hub(entry_id) ON DELETE CASCADE,
    FOREIGN KEY (archived_by_user_id) REFERENCES users(user_id)
) ENGINE=InnoDB;

CREATE TABLE group_updates (
    update_id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    user_id INT NOT NULL,
    update_title TEXT NOT NULL,
    update_content TEXT NOT NULL,
    photo_url VARCHAR(255),
    is_published TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL,
    FOREIGN KEY (group_id) REFERENCES `groups`(group_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE=InnoDB;

CREATE TABLE group_update_images (
    image_id INT AUTO_INCREMENT PRIMARY KEY,
    update_id INT NOT NULL,
    photo_url VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (update_id) REFERENCES group_updates(update_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE update_comments (
    comment_id INT AUTO_INCREMENT PRIMARY KEY,
    update_id INT NOT NULL,
    user_id INT NOT NULL,
    comment_content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (update_id) REFERENCES group_updates(update_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE=InnoDB;

CREATE TABLE update_likes (
    like_id INT AUTO_INCREMENT PRIMARY KEY,
    update_id INT NOT NULL,
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(update_id, user_id),
    FOREIGN KEY (update_id) REFERENCES group_updates(update_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================================
-- Performance Indexes
-- ============================================================================

CREATE INDEX idx_trap_catches_date_trap_code ON trap_catches(`date`, trap_code);
CREATE INDEX idx_bait_station_records_date_code ON bait_station_records(`date`, bait_station_code);
CREATE INDEX idx_traps_line_id_status ON traps(line_id, status);
CREATE INDEX idx_bait_stations_line_id_status ON bait_stations(line_id, status);
CREATE INDEX idx_lines_group_id_status ON `lines`(group_id, status);
CREATE INDEX idx_group_membership_user_status ON group_membership(group_id, membership_status, user_id);
CREATE INDEX idx_operator_lines_user_line ON operator_lines(user_id, line_id);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_knowledge_hub_group ON knowledge_hub(group_id);
CREATE INDEX idx_knowledge_hub_revision_entry ON knowledge_hub_revision(entry_id);

SET FOREIGN_KEY_CHECKS = 1;
