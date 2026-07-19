"""Master-data CRUD: Sites, Clients, Materials, Labor, Equipment.

Every tab here is a thin ``CrudFrame`` wrapper. The ``*_options`` helpers are
the shared ``options_func`` callbacks used wherever another tab needs a foreign
key to one of these masters (each returns ``[(id, label), ...]``).
"""

from crud_frame import CrudFrame, Field


# ---------------------------------------------------------------- fk helpers
def site_options(conn):
    return [(r['id'], r['name'])
            for r in conn.execute('SELECT id, name FROM sites ORDER BY name')]


def client_options(conn):
    return [(r['id'], r['name'])
            for r in conn.execute('SELECT id, name FROM clients ORDER BY name')]


def vendor_options(conn):
    return [(r['id'], r['name'])
            for r in conn.execute('SELECT id, name FROM vendors ORDER BY name')]


def material_options(conn):
    return [(r['id'], r['name'])
            for r in conn.execute('SELECT id, name FROM materials ORDER BY name')]


def labor_options(conn):
    return [(r['id'], r['name'])
            for r in conn.execute('SELECT id, name FROM labor ORDER BY name')]


def project_options(conn):
    return [(r['id'], r['name'])
            for r in conn.execute('SELECT id, name FROM projects ORDER BY name')]


# ---------------------------------------------------------------- builders
def build_sites_tab(parent, db_getter):
    fields = [
        Field('name', 'Name'),
        Field('location', 'Location'),
        Field('site_type', 'Type', kind='combo',
              options=['Site', 'Warehouse'], default='Site'),
        Field('status', 'Status', kind='combo',
              options=['Active', 'Closed'], default='Active'),
    ]
    return CrudFrame(parent, db_getter, 'sites', fields, 'Sites / Warehouses')


def build_clients_tab(parent, db_getter):
    fields = [
        Field('name', 'Name'),
        Field('contact_person', 'Contact'),
        Field('phone', 'Phone'),
        Field('email', 'Email'),
        Field('address', 'Address', width=180),
    ]
    return CrudFrame(parent, db_getter, 'clients', fields, 'Clients')


def build_materials_tab(parent, db_getter):
    fields = [
        Field('name', 'Name'),
        Field('unit', 'Unit'),
        Field('category', 'Category'),
        Field('hsn_code', 'HSN Code'),
        Field('rate', 'Std Rate', kind='number', default='0'),
    ]
    return CrudFrame(parent, db_getter, 'materials', fields, 'Materials')


def build_labor_tab(parent, db_getter):
    fields = [
        Field('name', 'Name'),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('skill', 'Skill'),
        Field('daily_wage', 'Daily Wage', kind='number', default='0'),
        Field('phone', 'Phone'),
        Field('status', 'Status', kind='combo',
              options=['Active', 'Inactive'], default='Active'),
        # Optional statutory identifiers (blank for informal labour).
        Field('pf_no', 'PF No (optional)'),
        Field('esi_no', 'ESI No (optional)'),
    ]
    return CrudFrame(parent, db_getter, 'labor', fields, 'Labor')


def build_equipment_tab(parent, db_getter):
    fields = [
        Field('name', 'Name'),
        Field('category', 'Category'),
        Field('current_site_id', 'Current Site', kind='fk',
              options_func=site_options),
        Field('status', 'Status', kind='combo',
              options=['Available', 'In Use', 'Maintenance'],
              default='Available'),
    ]
    return CrudFrame(parent, db_getter, 'equipment', fields, 'Equipment')
