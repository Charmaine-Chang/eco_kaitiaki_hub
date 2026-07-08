-- =========================================================================
-- Eco Kaitiaki Hub Database Population (Mock Data for Multi-Conservation Groups)
-- MySQL version
-- =========================================================================
-- Ensure you run `create_database.sql` before running this script.

-- 1. Insert Roles
INSERT INTO roles (role_name) VALUES
('Super Admin'), ('Group Coordinator'), ('Operator'), ('Observer');

-- 2. Insert Trap Types
INSERT INTO trap_type (trap_type_name) VALUES
('A24'), ('DOC 150'), ('DOC 200'), ('DOC 250'), ('Flipping Timmy'),
('Rat trap'), ('T-Rex Rat Trap'), ('Trapinator'), ('Victor');

-- 2.5 Insert Bait Station Types
INSERT INTO bait_station_type (bait_station_type_name) VALUES
('Bait Safe'), ('Chimney'), ('EnviroMate100'), ('Flowerpot'), ('Hockey stick'),
('KK'), ('Kilmore'), ('Mini Philproof'), ('PelGar Rat Station'), ('Philproof'),
('Pied Piper'), ('Protecta Ambush'), ('Protecta EVO Edge'), ('Protecta Sidekick'),
('Rodent Cafe'), ('Sentry'), ('Sentry Plus'), ('Striker'), ('Trakka'), ('Tunnel'),
('Wasptek'), ('ZIP tunnel'), ('Other');

-- 3. Insert Trap Statuses
INSERT INTO trap_status (status_name) VALUES
('Initial set'), ('Removed for Repair'), ('Sprung'), ('Still set, bait OK'),
('Still set, bait bad'), ('Still set, bait missing'), ('Trap Replaced'),
('Trap gone'), ('Trap interfered with');

-- 4. Insert Trap Conditions
INSERT INTO trap_condition (trap_condition_name) VALUES
('OK'), ('Needs maintenance'), ('Repaired'),
('Regassed'), ('Recurred'), ('Battery charge');

-- 5. Insert Species
INSERT INTO species (species_name) VALUES
('Ferret'), ('Hedgehog'), ('Mouse'), ('Possum'), ('Kiore Rat'),
('Norway Rat'), ('Ship Rat'), ('Stoat'), ('Weasel'), ('Unspecified'), ('None');

-- 6. Insert Bait Types
INSERT INTO bait_type (bait_type_name) VALUES
('Carrot'), ('Cereal'), ('Cheese'), ('Chocolate'), ('Dehydrated Rabbit'),
('Dried fruit'), ('Ferret bedding'), ('Fish'), ('Fresh Possum'), ('Fresh Rabbit'),
('Fresh fruit'), ('Fresh meat'), ('Golf ball'), ('Good Nature Chocolate'),
('Good Nature Meat Lovers'), ('Goodnature Blood'), ('Goodnature Cinnamon pre feed'),
('Goodnature Nut Butter'), ('Lure'), ('Lure-it Salmon Spray'), ('Mayo'),
('Mustelid and Cat Lure'), ('NARA Blocks'), ('NZAT Lure - Original'), ('None'),
('Nut'), ('Nutella'), ('Other'), ('Peanut butter'), ('PoaUku'), ('Possum Dough'),
('Rabbit oil'), ('Rat and Possum Lure'), ('Rat oil'), ('Salmon'), ('Salmon oil'),
('Salted Possum'), ('Salted Rabbit'), ('Salted meat'), ('Smooth'),
('Terracotta Lures'), ('Tinned Sardines'), ('Whole egg');

-- 6.5 Insert Bait Ingredients
INSERT INTO bait_ingredients (ingredient_name) VALUES
('Brodifacoum'), ('Cyanide'), ('Diphacinone'), ('Cholecalciferol'), ('Pindone');

-- 6.6 Insert Bait Formulations
INSERT INTO bait_formulations (formulation_name) VALUES
('Pellet'), ('Paste'), ('Block');

-- 7. Insert Equipment Status
INSERT INTO equipment_status (equipment_status_name) VALUES
('Active'), ('Deployed'), ('In Storage'), ('Under Repair'), ('Lost'), ('Damaged'), ('Retired');

-- 8. Insert Users
-- Default password: Password123! (bcrypt hash for local dev only)
INSERT INTO users (username, first_name, last_name, phone, email, emergency_contact, password_hash, status) VALUES
-- Super Admin
('superadmin', 'Super', 'Admin', '0210000000', 'admin@example.co.nz', '0219990000', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
-- Group Coordinators
('coord_Alice', 'Alice', 'Smith', '0210000001', 'alice@example.co.nz', '0219990001', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('coord_Bob', 'Bob', 'Jones', '0210000002', 'bob@example.co.nz', '0219990002', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('coord_Charlie', 'Charlie', 'Brown', '0210000003', 'charlie@example.co.nz', '0219990003', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
-- Operators
('op_Dave', 'Dave', 'Williams', '0210000004', 'dave@example.co.nz', '0219990004', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('op_Eve', 'Eve', 'Taylor', '0210000005', 'eve@example.co.nz', '0219990005', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('op_Frank', 'Frank', 'Thomas', '0210000006', 'frank@example.co.nz', '0219990006', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('op_Grace', 'Grace', 'White', '0210000007', 'grace@example.co.nz', '0219990007', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('op_Heidi', 'Heidi', 'Harris', '0210000008', 'heidi@example.co.nz', '0219990008', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('op_Ivan', 'Ivan', 'Martin', '0210000009', 'ivan@example.co.nz', '0219990009', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
-- Observers
('obs_Judy', 'Judy', 'Thompson', '0210000010', 'judy@example.co.nz', '0219990010', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('obs_Ken', 'Ken', 'Garcia', '0210000011', 'ken@example.co.nz', '0219990011', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('obs_Leo', 'Leo', 'Martinez', '0210000012', 'leo@example.co.nz', '0219990012', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active');

-- 9. Insert Groups
INSERT INTO `groups` (group_name, description, visibility, created_by, status, branding_image, geographic_area, primary_color) VALUES
('System Management', 'System administration group', 'private', 1, 'active', 'admin_icon.png', 'System Wide', '#1a5e20'),
('Darfield Possum Catch Group', 'Darfield community pest control', 'public', 1, 'active', 'darfield_logo.png', 'Darfield Plains', '#1a5e20'),
('West Melton Predator-Free', 'West Melton predator free initiative', 'private', 1, 'active', 'west_melton_logo.png', 'West Melton River Area', '#2e7d32'),
('Springston Conservation Group', 'Springston conservation project', 'public', 1, 'active', 'springston_logo.png', 'Springston Reserve', '#388e3c');

-- 10. Insert Group Memberships
INSERT INTO group_membership (user_id, role_id, group_id, membership_status) VALUES
(1, 1, 1, 'active'),
(1, 1, 2, 'active'),
(1, 1, 3, 'active'),
(1, 1, 4, 'active'),
(2, 2, 2, 'active'),
(3, 2, 3, 'active'),
(4, 2, 4, 'active'),
(5, 3, 2, 'active'),
(6, 3, 2, 'active'),
(7, 3, 3, 'active'),
(8, 3, 3, 'active'),
(9, 3, 4, 'active'),
(10, 3, 4, 'active'),
(11, 4, 2, 'active'),
(12, 4, 3, 'active'),
(13, 4, 4, 'active');

INSERT INTO group_membership (user_id, role_id, group_id, membership_status) VALUES
(5, 4, 3, 'active'),
(3, 4, 4, 'active');

-- 11. Insert Lines
INSERT INTO `lines` (group_id, line_name, line_type, status) VALUES
(2, 'Darfield Main Track', 'trap', 'active'),
(2, 'Darfield Bait Line', 'bait_station', 'active'),
(3, 'West Melton River', 'trap', 'active'),
(4, 'Springston Reserve', 'trap', 'active'),
(4, 'Springston Perimeter', 'bait_station', 'active'),
(2, 'Darfield North Ridge', 'trap', 'active'),
(3, 'West Melton Forest', 'trap', 'active'),
(4, 'Springston Riverbank', 'bait_station', 'active');

-- 12. Map Operators to Lines
INSERT INTO operator_lines (user_id, line_id) VALUES
(5, 1), (6, 1),
(5, 2),
(7, 3), (8, 3),
(9, 4), (10, 4),
(9, 5),
(6, 6),
(8, 7),
(10, 8);

-- 13. Storage Areas
INSERT INTO storage_area (group_id, storage_area_name) VALUES
(2, 'Darfield Base Shed'),
(3, 'West Melton Lockbox'),
(4, 'Springston HQ');

-- 14. Inventory Items
INSERT INTO inventory_items (group_id, item_category, item_name, quantity, unit_of_measure, threshold, storage_area_id) VALUES
(2, 'Bait', 'Peanut butter', 0.5, 'kg', 1.0, 1),
(2, 'Equipment', 'Gloves', 20, 'pairs', 5, 1),
(3, 'Bait', 'GN Nut Butter', 1.0, 'kg', 2.0, 2),
(4, 'Bait', 'Possum Dough', 15.0, 'units', 5.0, 3),
(2, 'Equipment', 'Safety Glasses', 10, 'units', 2, 1),
(3, 'Bait', 'Salmon oil', 5.0, 'L', 1.0, 2),
(3, 'Equipment', 'Trap Key', 5, 'units', 1, 2),
(4, 'Bait', 'Whole egg', 30, 'units', 10, 3);

-- 15. Inventory Log
INSERT INTO inventory_log (group_id, user_id, action_type, target_item_type, target_item_id) VALUES
(2, 2, 'add', 'item', 1),
(2, 2, 'add', 'item', 2),
(3, 3, 'add', 'item', 3),
(4, 4, 'add', 'item', 4),
(2, 2, 'add', 'item', 5),
(3, 3, 'add', 'item', 6),
(3, 3, 'add', 'item', 7),
(4, 4, 'add', 'item', 8);

-- 16. Insert Traps
INSERT INTO traps (trap_code, trap_type_id, line_id, equipment_status_id, storage_area_id, latitude, longitude) VALUES
('D-T1', 1, 1, 1, 1, -43.4885, 172.1100),
('D-T2', 2, 1, 1, 1, -43.4886, 172.1101),
('D-T3', 3, 1, 1, 1, -43.4887, 172.1102),
('D-T4', 4, 1, 1, 1, -43.4888, 172.1103),
('W-T1', 3, 3, 1, 2, -43.5200, 172.3600),
('W-T2', 4, 3, 1, 2, -43.5201, 172.3601),
('W-T3', 5, 3, 1, 2, -43.5202, 172.3602),
('S-T1', 5, 4, 1, 3, -43.6300, 172.4600),
('S-T2', 6, 4, 1, 3, -43.6301, 172.4601),
('S-T3', 7, 4, 1, 3, -43.6302, 172.4602),
('D-T5', 1, 6, 1, 1, -43.4890, 172.1105),
('D-T6', 2, 6, 1, 1, -43.4891, 172.1106),
('W-T4', 3, 7, 1, 2, -43.5203, 172.3603),
('W-T5', 4, 7, 1, 2, -43.5204, 172.3604),
('S-T4', 5, 4, 1, 3, -43.6304, 172.4604),
('S-T5', 6, 4, 1, 3, -43.6305, 172.4605);

-- 17. Insert Trap Catches
INSERT INTO trap_catches (trap_code, `date`, recorded_by, species_id, sex, maturity, trap_status_id, rebaited, bait_type_id, trap_condition_id, strikes, note) VALUES
('D-T1', '2026-03-01 08:30:00', 5, 4, 'Male', 'Adult', 3, 1, 29, 1, 1, 'Caught a large Possum in Darfield'),
('D-T2', '2026-03-01 08:45:00', 6, 11, NULL, NULL, 4, 0, 25, 1, 0, 'Checked, all clear'),
('D-T3', '2026-03-02 09:00:00', 5, 2, 'Unknown', 'Adult', 3, 1, 29, 1, 1, 'Hedgehog found'),
('D-T1', '2026-03-05 08:30:00', 5, 3, 'Female', 'Juvenile', 3, 1, 29, 1, 1, 'Mouse in DOC 150'),
('D-T4', '2026-03-06 09:15:00', 6, 11, NULL, NULL, 4, 0, 25, 1, 0, 'All clear'),
('D-T2', '2026-03-08 08:20:00', 5, 4, 'Male', 'Adult', 3, 1, 29, 1, 1, 'Another possum.'),
('D-T3', '2026-03-10 09:10:00', 6, 11, NULL, NULL, 6, 1, 29, 1, 0, 'Bait missing, set again.'),
('W-T1', '2026-03-02 08:30:00', 7, 8, 'Male', 'Juvenile', 3, 1, 29, 1, 1, 'Stoat caught near river'),
('W-T2', '2026-03-03 10:00:00', 8, 4, 'Female', 'Adult', 3, 1, 29, 1, 1, 'Possum caught'),
('W-T3', '2026-03-04 11:30:00', 7, 11, NULL, NULL, 4, 0, 25, 1, 0, 'Checked, all clear'),
('W-T1', '2026-03-08 09:00:00', 8, 3, 'Male', 'Adult', 3, 1, 29, 1, 1, 'Small mouse'),
('W-T2', '2026-03-10 10:15:00', 7, 11, NULL, NULL, 5, 1, 29, 2, 0, 'Bait rotten, trap needs maintenance'),
('S-T1', '2026-03-03 08:45:00', 9, 11, NULL, NULL, 4, 0, 25, 1, 0, 'Checked, all clear'),
('S-T2', '2026-03-05 09:45:00', 10, 6, 'Male', 'Adult', 3, 1, 29, 1, 1, 'Norway rat caught'),
('S-T3', '2026-03-07 08:00:00', 9, 11, NULL, NULL, 5, 1, 29, 2, 0, 'Bait was bad, replaced it. Trap needs slight oiling.'),
('S-T1', '2026-03-09 08:30:00', 10, 4, 'Female', 'Juvenile', 3, 1, 29, 1, 1, 'Small possum'),
('S-T2', '2026-03-12 09:00:00', 9, 6, 'Female', 'Adult', 3, 1, 29, 1, 1, 'Another rat'),
('S-T3', '2026-03-14 08:15:00', 10, 11, NULL, NULL, 4, 0, 25, 1, 0, 'All clear after oiling'),
('D-T5', '2026-03-05 08:30:00', 6, 4, 'Female', 'Adult', 3, 1, 29, 1, 1, 'Possum caught on new ridge line'),
('D-T6', '2026-03-05 08:45:00', 6, 11, NULL, NULL, 4, 0, 25, 1, 0, 'No catch'),
('W-T4', '2026-03-07 10:00:00', 8, 8, 'Male', 'Juvenile', 3, 1, 29, 1, 1, 'Stoat caught'),
('W-T5', '2026-03-07 10:15:00', 8, 11, NULL, NULL, 5, 1, 29, 2, 0, 'Bait taken, no catch'),
('S-T4', '2026-03-10 09:30:00', 10, 6, 'Male', 'Adult', 3, 1, 29, 1, 1, 'Rat'),
('S-T5', '2026-03-10 09:45:00', 10, 3, 'Female', 'Adult', 3, 1, 29, 1, 1, 'Mouse'),
('D-T5', '2026-03-12 08:30:00', 6, 11, NULL, NULL, 4, 0, 25, 1, 0, 'Checked, all clear'),
('W-T4', '2026-03-14 10:00:00', 8, 2, 'Unknown', 'Adult', 3, 1, 29, 1, 1, 'Hedgehog');

-- 18. Observation Notes
INSERT INTO observation_notes (catch_id, observation_type, description, related_line_id, user_id) VALUES
(1, 'Weather', 'Heavy rain overnight, might have affected catches', 1, 5),
(3, 'Sign', 'Lots of hedgehog droppings around the trap area', 1, 5),
(6, 'Sign', 'Stoat tracks seen near the river bank', 3, 7),
(11, 'Maintenance', 'Trap mechanism feels a bit stiff, will bring WD40 next time', 4, 9),
(19, 'Flora', 'Native orchids flowering nearby', 6, 6),
(21, 'Sign', 'Possum scratches on tree near trap', 7, 8),
(23, 'Weather', 'Very muddy access track', 4, 10),
(24, 'Maintenance', 'Trap box is rotting, needs replacement soon', 4, 10);

-- 19. Bait Stations
INSERT INTO bait_stations (bait_station_code, line_id, bait_station_type_id, equipment_status_id, storage_area_id, latitude, longitude) VALUES
('D-BS1', 2, 10, 1, 1, -43.4887, 172.1102),
('D-BS2', 2, 12, 1, 1, -43.4888, 172.1103),
('D-BS3', 2, 10, 1, 1, -43.4889, 172.1104),
('S-BS1', 5, 20, 1, 3, -43.6302, 172.4602),
('S-BS2', 5, 22, 1, 3, -43.6303, 172.4603),
('D-BS4', 2, 10, 1, 1, -43.4890, 172.1105),
('D-BS5', 2, 12, 1, 1, -43.4891, 172.1106),
('S-BS3', 8, 20, 1, 3, -43.6304, 172.4604),
('S-BS4', 8, 22, 1, 3, -43.6305, 172.4605);

-- 20. Bait Station Records
INSERT INTO bait_station_records (bait_station_code, recorded_by, target_species_id, active_ingredient, formulation, concentration, bait_remaining, bait_removed, bait_added, notes) VALUES
('D-BS1', 5, 11, 'Brodifacoum', 'Pellet', 0.05, 100, 0, 50, 'Topped up bait station'),
('D-BS2', 6, 4, 'Cyanide', 'Paste', 0.1, 50, 50, 100, 'Lots of possum sign around, bait was half eaten'),
('D-BS3', 5, 11, 'Brodifacoum', 'Pellet', 0.05, 150, 0, 0, 'Bait station full, no signs of activity'),
('D-BS1', 5, 4, 'Brodifacoum', 'Pellet', 0.05, 20, 0, 100, 'Second check. High possum activity, almost all bait gone.'),
('D-BS2', 6, 11, 'Cyanide', 'Paste', 0.1, 150, 0, 0, 'Second check. No activity.'),
('D-BS3', 5, 4, 'Brodifacoum', 'Pellet', 0.05, 0, 150, 200, 'All bait gone, rat prints clearly visible.'),
('S-BS1', 9, 6, 'Diphacinone', 'Block', 0.005, 0, 100, 150, 'Bait completely gone, rat signs visible'),
('S-BS2', 10, 11, 'Diphacinone', 'Block', 0.005, 150, 0, 0, 'No activity noted.'),
('S-BS1', 9, 11, 'Diphacinone', 'Block', 0.005, 150, 0, 0, 'Second check. Full.'),
('S-BS2', 10, 3, 'Diphacinone', 'Block', 0.005, 50, 100, 100, 'Mice sign present.'),
('D-BS4', 6, 11, 'Brodifacoum', 'Pellet', 0.05, 100, 0, 50, 'Initial fill'),
('D-BS5', 6, 4, 'Cyanide', 'Paste', 0.1, 50, 0, 100, 'Initial fill'),
('S-BS3', 10, 6, 'Diphacinone', 'Block', 0.005, 0, 0, 150, 'Initial fill'),
('S-BS4', 10, 11, 'Diphacinone', 'Block', 0.005, 150, 0, 0, 'Initial fill'),
('D-BS4', 6, 4, 'Brodifacoum', 'Pellet', 0.05, 0, 150, 150, 'Bait totally gone'),
('S-BS3', 10, 6, 'Diphacinone', 'Block', 0.005, 50, 100, 100, 'Some rat activity');

-- 21. Knowledge Hub
INSERT INTO knowledge_hub (group_id, user_id, category, title, content, is_featured, is_published, status) VALUES
((SELECT group_id FROM `groups` WHERE group_name = 'Darfield Possum Catch Group'), 1, 'Guide', 'How to set a DOC 200', 'Always use the safety clip when setting the trap to avoid injury.', 1, 1, 'approved'),
((SELECT group_id FROM `groups` WHERE group_name = 'West Melton Predator-Free'), 3, 'Resource', 'Common pests in West Melton', 'Rats and stoats are very common. Watch out for nesting areas.', 0, 1, 'approved'),
((SELECT group_id FROM `groups` WHERE group_name = 'Darfield Possum Catch Group'), 2, 'Guide', 'Bait Station Best Practices', 'Ensure bait is secured properly to avoid non-target species taking it.', 1, 1, 'approved'),
((SELECT group_id FROM `groups` WHERE group_name = 'Springston Conservation Group'), 4, 'Species Info', 'Identifying Ship Rats vs Norway Rats', 'Ship rats have larger ears and a tail longer than their body.', 0, 1, 'approved'),
((SELECT group_id FROM `groups` WHERE group_name = 'Darfield Possum Catch Group'), 1, 'Safety', 'Handling toxins', 'Always wear gloves and wash hands thoroughly after handling bait.', 1, 1, 'approved'),
((SELECT group_id FROM `groups` WHERE group_name = 'Darfield Possum Catch Group'), 2, 'Guide', 'Seasonal Trapping Strategies', 'Winter brings more rodents looking for shelter. Increase bait checks.', 0, 1, 'approved'),
((SELECT group_id FROM `groups` WHERE group_name = 'Darfield Possum Catch Group'), 1, 'Species Info', 'Hedgehogs: Friend or Foe?', 'While cute, hedgehogs eat native bird eggs and insects. They are a pest.', 1, 1, 'approved'),
((SELECT group_id FROM `groups` WHERE group_name = 'West Melton Predator-Free'), 3, 'Safety', 'Riverbank Safety Protocol', 'The recent floods have eroded some tracks. Stay 2m away from the edge.', 1, 1, 'approved');

-- 22. Group Updates & Comments
INSERT INTO group_updates (group_id, user_id, update_title, update_content, is_published) VALUES
(2, 2, 'Welcome to Darfield Trappers', 'Let''s get out there and catch some pests!', 1),
(3, 3, 'West Melton River Cleanup', 'Meet at the main carpark at 9am.', 1),
(4, 4, 'Springston Update', 'We had a great catch rate this month, keep up the good work team!', 1),
(2, 2, 'Monthly meeting next week', 'We will be discussing trap placements for the new ridge line.', 1),
(4, 4, 'New bait stations deployed', 'Check out the new stations on the riverbank line.', 1),
(2, 2, 'Trap Box Maintenance Day', 'We need volunteers this weekend to help repair some of the older wooden trap boxes. Pizza provided!', 1),
(3, 3, 'Stoat Sighting Alert', 'A large stoat was spotted near the north bridge. Please ensure all DOC200s in that sector are freshly baited.', 1),
(4, 4, 'Welcome New Members!', 'Great to see so many new faces joining the Springston effort this week.', 1),
(2, 2, 'Draft: End of Year Stats', 'Draft post, please ignore for now.', 0);

INSERT INTO update_comments (update_id, user_id, comment_content) VALUES
(1, 5, 'Excited to start my first line!'),
(2, 7, 'I will bring extra gloves.'),
(3, 9, 'Awesome results!'),
(4, 6, 'I''ll be there!'),
(4, 5, 'Can''t make it this time, please share notes.'),
(5, 10, 'They look great.'),
(6, 5, 'I can help on Saturday morning.'),
(6, 11, 'I''ll bring my drill.'),
(7, 8, 'Rebaited my sector this morning. Fingers crossed!'),
(8, 13, 'Glad to be here!');

-- 23. Update Likes
INSERT INTO update_likes (update_id, user_id) VALUES
(1, 5), (1, 6), (1, 11),
(2, 7), (2, 8), (2, 12),
(3, 9), (3, 10), (3, 13),
(4, 5), (4, 6),
(5, 9), (5, 10),
(6, 5), (6, 6), (6, 11),
(7, 7), (7, 8),
(8, 9), (8, 10), (8, 13);

-- =========================================================================
-- ADDITIONAL MOCK DATA (Phase 2 Population)
-- =========================================================================

-- 24. Additional Users
INSERT INTO users (username, first_name, last_name, phone, email, emergency_contact, password_hash, status) VALUES
('coord_Dan', 'Dan', 'Miller', '0210000014', 'dan@example.co.nz', '0219990014', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('coord_Erin', 'Erin', 'Wilson', '0210000015', 'erin@example.co.nz', '0219990015', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('op_Liam', 'Liam', 'Davis', '0210000016', 'liam@example.co.nz', '0219990016', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('op_Mia', 'Mia', 'Anderson', '0210000017', 'mia@example.co.nz', '0219990017', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('op_Noah', 'Noah', 'Taylor', '0210000018', 'noah@example.co.nz', '0219990018', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('op_Olivia', 'Olivia', 'Thomas', '0210000019', 'olivia@example.co.nz', '0219990019', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('op_Paul', 'Paul', 'White', '0210000020', 'paul@example.co.nz', '0219990020', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('op_Quinn', 'Quinn', 'Harris', '0210000021', 'quinn@example.co.nz', '0219990021', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('obs_Ryan', 'Ryan', 'Martin', '0210000022', 'ryan@example.co.nz', '0219990022', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active'),
('obs_Sara', 'Sara', 'Thompson', '0210000023', 'sara@example.co.nz', '0219990023', '$2b$12$VnnvK2V9Onm3XypDfSWiseo.hp0FymbzDowkfkZ4spmqDw5/JX5cS', 'Active');

-- 25. Additional Groups
INSERT INTO `groups` (group_name, description, visibility, created_by, status, branding_image, geographic_area, primary_color) VALUES
('Kaikoura Coastal Protection', 'Protecting native birds along the Kaikoura coastline.', 'public', 1, 'active', 'kaikoura_logo.png', 'Kaikoura Peninsula', '#0277bd'),
('Port Hills Restoration Trust', 'Restoring native bush and controlling predators in the Port Hills.', 'public', 1, 'active', 'porthills_logo.png', 'Port Hills, Christchurch', '#4e342e'),
('Selwyn District Pests', 'Coordinated pest control across Selwyn farmlands.', 'private', 1, 'active', 'selwyn_logo.png', 'Selwyn Plains', '#ef6c00');

-- 26. Additional Memberships
INSERT INTO group_membership (user_id, role_id, group_id, membership_status) VALUES
(1, 1, 5, 'active'), (1, 1, 6, 'active'), (1, 1, 7, 'active'),
(14, 2, 5, 'active'),
(15, 2, 6, 'active'),
(2, 2, 7, 'active'),
(16, 3, 5, 'active'), (17, 3, 5, 'active'),
(18, 3, 6, 'active'), (19, 3, 6, 'active'),
(20, 3, 7, 'active'), (21, 3, 7, 'active'),
(22, 4, 5, 'active'), (23, 4, 6, 'active');

-- 27. Additional Lines
INSERT INTO `lines` (group_id, line_name, line_type, status) VALUES
(5, 'Coastal Dune Track', 'trap', 'active'),
(5, 'Lookout Ridge', 'trap', 'active'),
(6, 'Summit Walk', 'trap', 'active'),
(6, 'Valley Stream', 'bait_station', 'active'),
(7, 'Farmland Perimeter', 'trap', 'active'),
(7, 'Shelter Belt A', 'bait_station', 'active');

-- 28. Map Operators to New Lines
INSERT INTO operator_lines (user_id, line_id) VALUES
(16, 9), (17, 9),
(16, 10),
(18, 11), (19, 11),
(19, 12),
(20, 13), (21, 13),
(20, 14);

-- 29. Additional Storage Areas
INSERT INTO storage_area (group_id, storage_area_name) VALUES
(5, 'Kaikoura Boat Shed'),
(6, 'Port Hills Ranger Station'),
(7, 'Selwyn Farm Barn');

-- 30. Additional Traps
INSERT INTO traps (trap_code, trap_type_id, line_id, equipment_status_id, storage_area_id, latitude, longitude) VALUES
('K-T1', 2, 9, 1, 4, -42.4200, 173.6800),
('K-T2', 2, 9, 1, 4, -42.4210, 173.6810),
('K-T3', 3, 10, 1, 4, -42.4220, 173.6820),
('P-T1', 1, 11, 1, 5, -43.5900, 172.6400),
('P-T2', 1, 11, 1, 5, -43.5910, 172.6410),
('P-T3', 8, 11, 1, 5, -43.5920, 172.6420),
('S-T6', 4, 13, 1, 6, -43.6000, 172.1000),
('S-T7', 4, 13, 1, 6, -43.6010, 172.1010),
('S-T8', 5, 13, 1, 6, -43.6020, 172.1020);

-- 31. Additional Trap Catches
INSERT INTO trap_catches (trap_code, `date`, recorded_by, species_id, sex, maturity, trap_status_id, rebaited, bait_type_id, trap_condition_id, strikes, note) VALUES
('K-T1', '2026-04-01 10:00:00', 16, 7, 'Male', 'Adult', 3, 1, 29, 1, 1, 'Ship rat caught on dunes'),
('K-T2', '2026-04-01 10:15:00', 17, 11, NULL, NULL, 4, 0, 25, 1, 0, 'Checked, all clear'),
('K-T3', '2026-04-05 11:00:00', 16, 8, 'Female', 'Adult', 3, 1, 43, 1, 1, 'Stoat caught with egg bait'),
('P-T1', '2026-04-02 09:00:00', 18, 4, 'Male', 'Adult', 3, 1, 29, 1, 1, 'Possum in Port Hills'),
('P-T2', '2026-04-02 09:15:00', 19, 11, NULL, NULL, 4, 0, 25, 1, 0, 'No activity'),
('P-T3', '2026-04-06 10:30:00', 18, 5, 'Male', 'Juvenile', 3, 1, 29, 1, 1, 'Kiore rat found'),
('S-T6', '2026-04-03 08:00:00', 20, 1, 'Male', 'Adult', 3, 1, 42, 1, 1, 'Ferret caught near farm perimeter'),
('S-T7', '2026-04-03 08:15:00', 21, 6, 'Female', 'Adult', 3, 1, 29, 1, 1, 'Norway rat'),
('S-T8', '2026-04-07 09:00:00', 20, 11, NULL, NULL, 4, 0, 25, 1, 0, 'Clean check'),
('K-T1', '2026-04-10 10:00:00', 16, 7, 'Female', 'Adult', 3, 1, 29, 1, 1, 'Another ship rat'),
('P-T1', '2026-04-12 09:00:00', 18, 4, 'Female', 'Adult', 3, 1, 29, 1, 1, 'Large female possum'),
('S-T6', '2026-04-15 08:00:00', 20, 1, 'Female', 'Juvenile', 3, 1, 42, 1, 1, 'Young ferret caught');

-- 32. Additional Bait Stations
INSERT INTO bait_stations (bait_station_code, line_id, bait_station_type_id, equipment_status_id, storage_area_id, latitude, longitude) VALUES
('P-BS1', 12, 10, 1, 5, -43.5930, 172.6430),
('S-BS5', 14, 20, 1, 6, -43.6030, 172.1030);

-- 33. Additional Bait Station Records
INSERT INTO bait_station_records (bait_station_code, recorded_by, target_species_id, active_ingredient, formulation, concentration, bait_remaining, bait_removed, bait_added, notes) VALUES
('P-BS1', 19, 6, 'Diphacinone', 'Block', 0.005, 0, 100, 150, 'All bait gone in valley station'),
('S-BS5', 20, 11, 'Brodifacoum', 'Pellet', 0.05, 150, 0, 50, 'Topped up farm shelter belt station');

-- 34. Additional Inventory Items
INSERT INTO inventory_items (group_id, storage_area_id, item_category, item_name, quantity, unit_of_measure, threshold) VALUES
(5, 4, 'Bait', 'Salmon oil', 8.0, 'L', 2.0),
(5, 4, 'Equipment', 'Binoculars', 5, 'units', 1),
(6, 5, 'Bait', 'Good Nature Chocolate', 12.0, 'kg', 3.0),
(6, 5, 'Equipment', 'GPS Device', 3, 'units', 1),
(7, 6, 'Bait', 'Peanut butter', 15.0, 'kg', 5.0),
(7, 6, 'Equipment', 'Field Notebook', 20, 'units', 5);

-- 35. Additional Knowledge Hub Entries
INSERT INTO knowledge_hub (group_id, user_id, category, title, content, is_featured, is_published, status) VALUES
((SELECT group_id FROM `groups` WHERE group_name = 'Kaikoura Coastal Protection'), 14, 'Species Info', 'Kaikoura Peninsula Seabirds', 'We are protecting the Hutton''s shearwater nesting sites.', 1, 1, 'approved'),
((SELECT group_id FROM `groups` WHERE group_name = 'Port Hills Restoration Trust'), 15, 'Guide', 'Port Hills Native Planting', 'How to plant natives that provide habitat for birds but not cover for pests.', 0, 1, 'approved');

-- 36. Additional Group Updates
INSERT INTO group_updates (group_id, user_id, update_title, update_content, is_published) VALUES
(5, 14, 'Coastal Project Launch', 'Welcome everyone to the Kaikoura coastal protection project!', 1),
(6, 15, 'Summit Line Survey', 'We completed the survey for the new Summit Walk line.', 1),
(7, 2, 'Farm Safety Notice', 'Please watch out for electric fences on the south boundary.', 1);
