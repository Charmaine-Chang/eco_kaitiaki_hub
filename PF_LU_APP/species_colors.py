DEFAULT_SPECIES_COLORS = {
    'Ferret':        {'hex': '#D35400', 'rgb': '211, 84, 0'},
    'Hedgehog':      {'hex': '#8E44AD', 'rgb': '142, 68, 173'},
    'Mouse':         {'hex': '#7F8C8D', 'rgb': '127, 140, 141'},
    'Possum':        {'hex': '#1E8449', 'rgb': '30, 132, 73'},
    'Kiore Rat':     {'hex': '#B7950B', 'rgb': '183, 149, 11'},
    'Norway Rat':    {'hex': '#CB4335', 'rgb': '203, 67, 53'},
    'Ship Rat':      {'hex': '#922B21', 'rgb': '146, 43, 33'},
    'Stoat':         {'hex': '#2E86C1', 'rgb': '46, 134, 193'},
    'Weasel':        {'hex': '#1A5276', 'rgb': '26, 82, 118'},
    'Unspecified':   {'hex': '#717D7E', 'rgb': '113, 125, 126'},
    'None':          {'hex': '#95A5A6', 'rgb': '149, 165, 166'},
    'Empty':         {'hex': '#95A5A6', 'rgb': '149, 165, 166'},
}

_SPECIES_COLORS_CACHE = None


def _hex_to_rgb(hex_color):
    h = hex_color.lstrip('#')
    rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    return f'{rgb[0]}, {rgb[1]}, {rgb[2]}'


def _load_from_db():
    try:
        from PF_LU_APP.db import get_cursor
        cursor = get_cursor()
        cursor.execute(
            "SELECT species_name, species_color FROM species WHERE species_color IS NOT NULL"
        )
        results = cursor.fetchall()
        cursor.close()
        colors = {}
        for row in results:
            colors[row['species_name']] = {
                'hex': row['species_color'],
                'rgb': _hex_to_rgb(row['species_color']),
            }
        merged = DEFAULT_SPECIES_COLORS.copy()
        merged.update(colors)
        return merged
    except Exception:
        return DEFAULT_SPECIES_COLORS.copy()


def get_species_colors():
    global _SPECIES_COLORS_CACHE
    if _SPECIES_COLORS_CACHE is None:
        _SPECIES_COLORS_CACHE = _load_from_db()
    return _SPECIES_COLORS_CACHE


def refresh_cache():
    global _SPECIES_COLORS_CACHE
    _SPECIES_COLORS_CACHE = None


def get_species_color(species_name):
    c = get_species_colors()
    if not species_name:
        return c['None']
    return c.get(species_name, c.get('Unspecified', c['None']))


def species_badge_style(species_name):
    col = get_species_color(species_name)
    return f'background-color: rgba({col["rgb"]}, 0.12); color: {col["hex"]};'


def species_chart_dataset(template_labels, species_data_map):
    labels = []
    data = []
    bg = []
    colors = get_species_colors()
    for s_name in template_labels:
        c = colors.get(s_name, colors.get('Unspecified', colors['None']))
        labels.append(s_name)
        data.append(species_data_map.get(s_name, 0))
        bg.append(c['hex'])
    return labels, data, bg
