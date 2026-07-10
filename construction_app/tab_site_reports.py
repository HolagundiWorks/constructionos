"""Site reports & quality registers.

- Daily Progress Report (DPR): labour/plant/weather/work summary per site/day.
- Cube Tests: concrete cube compression register. ``strength_mpa`` and
  Pass/Fail ``result`` are auto-filled on save from the failure load, cube area,
  and grade via ``civil`` (best-effort ``on_save``; manual values are otherwise
  left alone, same pattern as the hire/duration auto-calcs).
- Material Tests: a free register for other material test results.
- Plant Log: machinery utilisation (hours run, diesel, downtime).

All four are thin ``CrudFrame`` wrappers; only Cube Tests carries an ``on_save``.
"""

from tkinter import ttk

import civil
from crud_frame import CrudFrame, Field
from tab_masters import site_options


def _compute_cube(conn, row_id, values):
    """Auto-fill strength_mpa and Pass/Fail result for a cube test."""
    try:
        strength = civil.cube_strength(values.get('load_kn', 0),
                                       values.get('area_mm2', 0))
        result = civil.cube_result(strength, values.get('grade', ''))
        conn.execute(
            'UPDATE cube_tests SET strength_mpa = ?, result = ? WHERE id = ?',
            (strength, result, row_id))
        conn.commit()
    except Exception:
        pass


def _build_daily_progress(parent, db_getter):
    fields = [
        Field('report_date', 'Date'),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('weather', 'Weather', kind='combo',
              options=['Clear', 'Cloudy', 'Rain', 'Heavy Rain'], default='Clear'),
        Field('labour_count', 'Labour', kind='number', default='0'),
        Field('plant_count', 'Plant', kind='number', default='0'),
        Field('work_summary', 'Work Summary', width=200),
        Field('remarks', 'Remarks', width=160),
    ]
    return CrudFrame(parent, db_getter, 'daily_progress', fields,
                     'Daily Progress Report',
                     order_by='report_date DESC, id DESC')


def _build_cube_tests(parent, db_getter):
    fields = [
        Field('cast_date', 'Cast Date'),
        Field('test_date', 'Test Date'),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('grade', 'Grade', kind='combo',
              options=['M10', 'M15', 'M20', 'M25', 'M30', 'M35', 'M40'],
              default='M25'),
        Field('location', 'Location'),
        Field('cube_id', 'Cube ID'),
        Field('age_days', 'Age (days)', kind='number', default='28'),
        Field('load_kn', 'Load (kN)', kind='number', default='0'),
        Field('area_mm2', 'Area (mm2)', kind='number', default='22500'),
        Field('strength_mpa', 'Strength (auto)', kind='number', default='0'),
        Field('result', 'Result (auto)'),
        Field('remarks', 'Remarks', width=160),
    ]
    return CrudFrame(parent, db_getter, 'cube_tests', fields,
                     'Cube Test Register', order_by='test_date DESC, id DESC',
                     on_save=_compute_cube)


def _build_material_tests(parent, db_getter):
    fields = [
        Field('test_date', 'Date'),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('material', 'Material'),
        Field('test_type', 'Test Type'),
        Field('sample_ref', 'Sample Ref'),
        Field('result', 'Result'),
        Field('remarks', 'Remarks', width=160),
    ]
    return CrudFrame(parent, db_getter, 'material_tests', fields,
                     'Material Test Register', order_by='test_date DESC, id DESC')


def _build_plant_log(parent, db_getter):
    fields = [
        Field('log_date', 'Date'),
        Field('site_id', 'Site', kind='fk', options_func=site_options),
        Field('equipment', 'Equipment'),
        Field('hours_run', 'Hours Run', kind='number', default='0'),
        Field('diesel_ltr', 'Diesel (L)', kind='number', default='0'),
        Field('downtime_hrs', 'Downtime (hrs)', kind='number', default='0'),
        Field('operator', 'Operator'),
        Field('remarks', 'Remarks', width=160),
    ]
    return CrudFrame(parent, db_getter, 'plant_logs', fields,
                     'Plant & Machinery Log', order_by='log_date DESC, id DESC')


def build_site_reports_tab(parent, db_getter):
    nb = ttk.Notebook(parent)
    nb.add(_build_daily_progress(nb, db_getter), text='Daily Progress')
    nb.add(_build_cube_tests(nb, db_getter), text='Cube Tests')
    nb.add(_build_material_tests(nb, db_getter), text='Material Tests')
    nb.add(_build_plant_log(nb, db_getter), text='Plant Log')
    return nb
