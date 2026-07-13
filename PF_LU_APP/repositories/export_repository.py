from PF_LU_APP.db import get_cursor

def get_all_active_groups():
    """Fetches all active groups for super admin selection."""
    try:
        cur = get_cursor()
        cur.execute("SELECT group_id, group_name FROM `groups` WHERE status = 'active' ORDER BY group_name")
        return cur.fetchall()
    finally:
        cur.close()

def get_group_name_by_id(group_id):
    """Fetches the group name given a group_id."""
    if not group_id:
        return 'Unknown Group'
    try:
        cur = get_cursor()
        cur.execute('SELECT group_name FROM `groups` WHERE group_id = %s', (group_id,))
        group = cur.fetchone()
        return group['group_name'] if group else 'Unknown Group'
    finally:
        cur.close()

def get_traps_export_data(group_id, date_from=None, date_to=None):
    """Fetches trap catch data for exporting."""
    query = '''
        SELECT tc.trap_code AS code, DATE_FORMAT(tc.`date`, '%%Y-%%m-%%d %%H:%%i') AS date,
               l.line_name AS line, u.username AS recorded_by, sp.species_name AS species_caught, 
               tc.sex, tc.maturity, ts.status_name AS status, 
               CASE WHEN tc.rebaited THEN 'Yes' ELSE 'No' END AS rebaited, 
               bt.bait_type_name AS bait_type, tcon.trap_condition_name AS trap_condition, 
               tc.strikes, tc.note
        FROM trap_catches tc
        JOIN traps t ON tc.trap_code = t.trap_code
        JOIN `lines` l ON t.line_id = l.line_id
        LEFT JOIN users u ON tc.recorded_by = u.user_id
        LEFT JOIN species sp ON tc.species_id = sp.species_id
        LEFT JOIN trap_status ts ON tc.trap_status_id = ts.trap_status_id
        LEFT JOIN bait_type bt ON tc.bait_type_id = bt.bait_type_id
        LEFT JOIN trap_condition tcon ON tc.trap_condition_id = tcon.trap_condition_id
        WHERE l.group_id = %s
    '''
    params = [group_id]
    if date_from:
        query += " AND tc.`date` >= CAST(%s AS DATE)"
        params.append(date_from)
    if date_to:
        query += " AND tc.`date` < CAST(%s AS DATE) + INTERVAL 1 DAY"
        params.append(date_to)
    query += " ORDER BY tc.`date` ASC"

    try:
        cur = get_cursor()
        cur.execute(query, tuple(params))
        return cur.fetchall()
    finally:
        cur.close()

def get_bait_stations_export_data(group_id, date_from=None, date_to=None):
    """Fetches bait station records for exporting."""
    query = '''
        SELECT bsr.bait_station_code AS code, DATE_FORMAT(bsr.`date`, '%%Y-%%m-%%d %%H:%%i') AS date,
               l.line_name AS line, u.username AS recorded_by, sp.species_name AS target_species, 
               bt.bait_type_name AS bait_type,
               bsr.active_ingredient, bsr.formulation, bsr.concentration, 
               bsr.bait_remaining, bsr.bait_removed, bsr.bait_added, bsr.notes
        FROM bait_station_records bsr
        JOIN bait_stations bs ON bsr.bait_station_code = bs.bait_station_code
        JOIN `lines` l ON bs.line_id = l.line_id
        LEFT JOIN users u ON bsr.recorded_by = u.user_id
        LEFT JOIN species sp ON bsr.target_species_id = sp.species_id
        LEFT JOIN bait_type bt ON bsr.bait_type_id = bt.bait_type_id
        WHERE l.group_id = %s
    '''
    params = [group_id]
    if date_from:
        query += " AND bsr.`date` >= CAST(%s AS DATE)"
        params.append(date_from)
    if date_to:
        query += " AND bsr.`date` < CAST(%s AS DATE) + INTERVAL 1 DAY"
        params.append(date_to)
    query += " ORDER BY bsr.`date` ASC"

    try:
        cur = get_cursor()
        cur.execute(query, tuple(params))
        return cur.fetchall()
    finally:
        cur.close()
