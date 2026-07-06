-- ============================================================================
-- PF-LU Project 2 Database Schema
-- PostgreSQL
-- Based on Project 1 + Project 2 ERD Extension
-- ============================================================================

-- ============================================================================
-- DROP TABLES
-- ============================================================================

DROP TABLE IF EXISTS update_likes CASCADE;
DROP TABLE IF EXISTS update_comments CASCADE;
DROP TABLE IF EXISTS group_update_images CASCADE;
DROP TABLE IF EXISTS group_updates CASCADE;
DROP TABLE IF EXISTS knowledge_hub_revision CASCADE;
DROP TABLE IF EXISTS knowledge_hub CASCADE;
DROP TABLE IF EXISTS inventory_log CASCADE;
DROP TABLE IF EXISTS inventory_items CASCADE;
DROP TABLE IF EXISTS storage_area CASCADE;
DROP TABLE IF EXISTS bait_station_records CASCADE;
DROP TABLE IF EXISTS bait_stations CASCADE;
DROP TABLE IF EXISTS observation_notes CASCADE;
DROP TABLE IF EXISTS trap_catches CASCADE;
DROP TABLE IF EXISTS traps CASCADE;
DROP TABLE IF EXISTS operator_lines CASCADE;
DROP TABLE IF EXISTS lines CASCADE;
DROP TABLE IF EXISTS role_upgrade_requests CASCADE;
DROP TABLE IF EXISTS group_membership CASCADE;
DROP TABLE IF EXISTS groups CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS equipment_status CASCADE;
DROP TABLE IF EXISTS trap_condition CASCADE;
DROP TABLE IF EXISTS bait_type CASCADE;
DROP TABLE IF EXISTS trap_status CASCADE;
DROP TABLE IF EXISTS species CASCADE;
DROP TABLE IF EXISTS trap_type CASCADE;
DROP TABLE IF EXISTS bait_station_type CASCADE;
DROP TABLE IF EXISTS roles CASCADE;
DROP TABLE IF EXISTS bait_ingredients CASCADE;
DROP TABLE IF EXISTS bait_formulations CASCADE;

-- ============================================================================
-- DROP ENUM TYPES
-- ============================================================================

DROP TYPE IF EXISTS visibility_enum CASCADE;
DROP TYPE IF EXISTS group_status_enum CASCADE;
DROP TYPE IF EXISTS user_status_enum CASCADE;
DROP TYPE IF EXISTS line_type_enum CASCADE;
DROP TYPE IF EXISTS line_status_enum CASCADE;
DROP TYPE IF EXISTS sex_enum CASCADE;
DROP TYPE IF EXISTS maturity_enum CASCADE;

-- ============================================================================
-- ENUM TYPES
-- ============================================================================

CREATE TYPE visibility_enum AS ENUM ('public', 'private');
CREATE TYPE group_status_enum AS ENUM ('active', 'inactive', 'pending');

CREATE TYPE user_status_enum AS ENUM ('Active', 'Inactive', 'Suspended');

CREATE TYPE line_type_enum AS ENUM ('trap', 'bait_station');
CREATE TYPE line_status_enum AS ENUM ('active', 'inactive');

CREATE TYPE sex_enum AS ENUM ('Male', 'Female', 'Unknown');
CREATE TYPE maturity_enum AS ENUM ('Juvenile', 'Adult', 'Unknown');

-- ============================================================================
-- LOOKUP TABLES
-- ============================================================================

CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE trap_type (
    trap_type_id SERIAL PRIMARY KEY,
    trap_type_name VARCHAR(50) NOT NULL
);

CREATE TABLE bait_station_type (
    bait_station_type_id SERIAL PRIMARY KEY,
    bait_station_type_name VARCHAR(50) NOT NULL
);

CREATE TABLE species (
    species_id SERIAL PRIMARY KEY,
    species_name VARCHAR(50) NOT NULL,
    species_color VARCHAR(7)
);

CREATE TABLE trap_status (
    trap_status_id SERIAL PRIMARY KEY,
    status_name VARCHAR(50) NOT NULL
);

CREATE TABLE bait_type (
    bait_type_id SERIAL PRIMARY KEY,
    bait_type_name VARCHAR(50) NOT NULL
);

CREATE TABLE trap_condition (
    trap_condition_id SERIAL PRIMARY KEY,
    trap_condition_name TEXT NOT NULL
);

CREATE TABLE equipment_status (
    equipment_status_id SERIAL PRIMARY KEY,
    equipment_status_name VARCHAR(50) NOT NULL UNIQUE
);

-- ============================================================================
-- USERS
-- ============================================================================

CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    phone VARCHAR(50),
    email VARCHAR(255) UNIQUE,
    emergency_contact VARCHAR(50),
    password_hash TEXT NOT NULL,
    status user_status_enum,
    profile_photo TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- GROUPS
-- ============================================================================

CREATE TABLE groups (
    group_id SERIAL PRIMARY KEY,
    group_name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    branding_image TEXT DEFAULT 'default_group.png',
    geographic_area VARCHAR(100),
    visibility visibility_enum NOT NULL DEFAULT 'public',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INT REFERENCES users(user_id),
    status group_status_enum NOT NULL DEFAULT 'pending',
    primary_color VARCHAR(7) DEFAULT '#1a5e20',
    boundary_geojson TEXT,
    region TEXT,
    latitude FLOAT,
    longitude FLOAT
);

CREATE TABLE group_membership (
    membership_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id INT NOT NULL REFERENCES roles(role_id),
    group_id INT NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    membership_status VARCHAR(50) NOT NULL,
    UNIQUE(user_id, group_id)
);

-- Runtime-migrated table: role_upgrade_requests
CREATE TABLE role_upgrade_requests (
    request_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    group_id INT NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
    requested_role_id INT NOT NULL REFERENCES roles(role_id),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    UNIQUE(user_id, group_id, requested_role_id, status)
);

-- ============================================================================
-- LINES
-- ============================================================================

CREATE TABLE lines (
    line_id SERIAL PRIMARY KEY,
    group_id INT NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
    line_name VARCHAR(50),
    line_type line_type_enum,
    status line_status_enum,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE operator_lines (
    user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
    line_id INT REFERENCES lines(line_id) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, line_id)
);

-- ============================================================================
-- STORAGE / INVENTORY
-- ============================================================================

CREATE TABLE storage_area (
    storage_area_id SERIAL PRIMARY KEY,
    group_id INT NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
    storage_area_name VARCHAR(50) NOT NULL
);

CREATE TABLE inventory_items (
    item_id SERIAL PRIMARY KEY,
    group_id INT NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
    storage_area_id INT REFERENCES storage_area(storage_area_id) ON DELETE SET NULL,
    item_category VARCHAR(50) NOT NULL,
    item_name VARCHAR(50) NOT NULL,
    quantity FLOAT DEFAULT 0,
    unit_of_measure VARCHAR(50),
    threshold FLOAT DEFAULT 0,
    line_id INT REFERENCES lines(line_id),
    is_retired BOOLEAN DEFAULT FALSE,
    retired_at TIMESTAMP
);

CREATE TABLE inventory_log (
    log_id SERIAL PRIMARY KEY,
    group_id INT NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
    user_id INT REFERENCES users(user_id),
    action_type VARCHAR(50) NOT NULL,
    target_item_type VARCHAR(50) NOT NULL,
    target_item_id INT NOT NULL,
    previous_location VARCHAR(100),
    new_location VARCHAR(100),
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- TRAPS
-- ============================================================================

CREATE TABLE traps (
    trap_code VARCHAR(50) PRIMARY KEY,
    trap_type_id INT REFERENCES trap_type(trap_type_id),
    line_id INT REFERENCES lines(line_id),
    equipment_status_id INT REFERENCES equipment_status(equipment_status_id),
    storage_area_id INT REFERENCES storage_area(storage_area_id),
    latitude FLOAT,
    longitude FLOAT,
    status line_status_enum DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE trap_catches (
    catches_id SERIAL PRIMARY KEY,
    trap_code VARCHAR(50) REFERENCES traps(trap_code) ON DELETE CASCADE,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    recorded_by INT REFERENCES users(user_id),
    species_id INT REFERENCES species(species_id),
    sex sex_enum,
    maturity maturity_enum,
    trap_status_id INT REFERENCES trap_status(trap_status_id),
    rebaited BOOLEAN,
    bait_type_id INT REFERENCES bait_type(bait_type_id),
    bait_amount FLOAT,
    trap_condition_id INT REFERENCES trap_condition(trap_condition_id),
    strikes INT,
    note TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE observation_notes (
    note_id SERIAL PRIMARY KEY,
    catch_id INT REFERENCES trap_catches(catches_id) ON DELETE CASCADE,
    observation_type TEXT,
    description TEXT,
    related_line_id INT REFERENCES lines(line_id),
    user_id INT REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- BAIT STATIONS
-- ============================================================================

CREATE TABLE bait_stations (
    bait_station_code VARCHAR(50) PRIMARY KEY,
    line_id INT REFERENCES lines(line_id),
    bait_station_type_id INT REFERENCES bait_station_type(bait_station_type_id),
    equipment_status_id INT REFERENCES equipment_status(equipment_status_id),
    storage_area_id INT REFERENCES storage_area(storage_area_id),
    latitude FLOAT,
    longitude FLOAT,
    status line_status_enum DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE bait_station_records (
    record_id SERIAL PRIMARY KEY,
    bait_station_code VARCHAR(50) REFERENCES bait_stations(bait_station_code) ON DELETE CASCADE,
    recorded_by INT REFERENCES users(user_id),
    target_species_id INT REFERENCES species(species_id),
    bait_type_id INT REFERENCES bait_type(bait_type_id),
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active_ingredient VARCHAR(50),
    formulation VARCHAR(50),
    concentration FLOAT,
    bait_remaining FLOAT DEFAULT 0,
    bait_removed FLOAT DEFAULT 0,
    bait_added FLOAT DEFAULT 0,
    notes TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Runtime-migrated tables: bait_ingredients, bait_formulations
CREATE TABLE bait_ingredients (
    ingredient_id SERIAL PRIMARY KEY,
    ingredient_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE bait_formulations (
    formulation_id SERIAL PRIMARY KEY,
    formulation_name VARCHAR(50) NOT NULL UNIQUE
);

-- ============================================================================
-- KNOWLEDGE HUB
-- ============================================================================

CREATE TABLE knowledge_hub (
    entry_id SERIAL PRIMARY KEY,
    group_id INT NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(user_id),
    category VARCHAR(50) NOT NULL,
    title VARCHAR(100) NOT NULL,
    content TEXT,
    photo_url TEXT,
    is_featured BOOLEAN DEFAULT FALSE,
    is_published BOOLEAN DEFAULT FALSE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE knowledge_hub_revision (
    revision_id SERIAL PRIMARY KEY,
    entry_id INT NOT NULL REFERENCES knowledge_hub(entry_id) ON DELETE CASCADE,
    version_number INT NOT NULL,
    category VARCHAR(50) NOT NULL,
    title VARCHAR(100) NOT NULL,
    content TEXT,
    photo_url TEXT,
    is_featured BOOLEAN DEFAULT FALSE,
    is_published BOOLEAN DEFAULT TRUE,
    archived_by_user_id INT NOT NULL REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (entry_id, version_number)
);

CREATE INDEX idx_knowledge_hub_group ON knowledge_hub(group_id);
CREATE INDEX idx_knowledge_hub_revision_entry ON knowledge_hub_revision(entry_id);

CREATE TABLE group_updates (
    update_id SERIAL PRIMARY KEY,
    group_id INT NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(user_id),
    update_title TEXT NOT NULL,
    update_content TEXT NOT NULL,
    photo_url TEXT,
    is_published BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE group_update_images (
    image_id SERIAL PRIMARY KEY,
    update_id INT NOT NULL REFERENCES group_updates(update_id) ON DELETE CASCADE,
    photo_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE update_comments (
    comment_id SERIAL PRIMARY KEY,
    update_id INT NOT NULL REFERENCES group_updates(update_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(user_id),
    comment_content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE update_likes (
    like_id SERIAL PRIMARY KEY,
    update_id INT NOT NULL REFERENCES group_updates(update_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(update_id, user_id)
);

-- ============================================================================
-- Performance & Scalability Optimization
-- Adding Indexes to heavily queried tables
-- ============================================================================

-- 1. Trap Catches: Used extensively in Analytics (filters by date and trap code)
CREATE INDEX IF NOT EXISTS idx_trap_catches_date_trap_code 
ON trap_catches(date, trap_code);

-- 2. Bait Station Records: Used in Analytics (filters by date and bait station code)
CREATE INDEX IF NOT EXISTS idx_bait_station_records_date_code 
ON bait_station_records(date, bait_station_code);

-- 3. Traps: Used in Dashboards (filters by line_id and status)
CREATE INDEX IF NOT EXISTS idx_traps_line_id_status 
ON traps(line_id, status);

-- 4. Bait Stations: Used in Dashboards (filters by line_id and status)
CREATE INDEX IF NOT EXISTS idx_bait_stations_line_id_status 
ON bait_stations(line_id, status);

-- 5. Lines: Used everywhere to find lines within a group
CREATE INDEX IF NOT EXISTS idx_lines_group_id_status 
ON lines(group_id, status);

-- 6. Group Membership: Used across all routes to verify user access
CREATE INDEX IF NOT EXISTS idx_group_membership_user_status 
ON group_membership(group_id, membership_status, user_id);

-- 7. Operator Lines: Used for Operator Dashboards
CREATE INDEX IF NOT EXISTS idx_operator_lines_user_line 
ON operator_lines(user_id, line_id);

-- 8. Users: Used for login and group assignments
CREATE INDEX IF NOT EXISTS idx_users_status 
ON users(status);
