"""GUI smoke test: build every tab against a POPULATED database, under both
light and dark, so data-dependent crashes surface automatically.

The rest of the suite is headless and pure; this one needs Tk. It exists
because the bug that broke Money > Key Numbers (a tab using ``projectcost``
without importing it) only fired once a project existed — the pure tests could
never have caught it, but building the tab on the sample book does. If no
display is available (a headless CI box), the whole class skips rather than
fails.

It reuses ``sampledata`` — the same demo the app ships — so the tabs are built
against realistic rows (aged bills, a delayed programme, open NCRs, retention),
not an empty file where most code paths never run.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, 'construction_app'))

try:
    import tkinter as tk
    from tkinter import ttk
    _HAVE_TK = True
except Exception:                                          # noqa: BLE001
    _HAVE_TK = False


@unittest.skipUnless(_HAVE_TK, 'tkinter not importable')
class TestTabsBuildOnSampleData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import db
        fd, cls.path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        os.remove(cls.path)
        cls.db = db
        cls.orig = db.DB_PATH
        db.DB_PATH = cls.path
        db.init_db()
        import sampledata
        conn = db.get_conn()
        sampledata.seed(conn)
        conn.close()
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
        except tk.TclError as exc:                          # headless box
            raise unittest.SkipTest('no display: {}'.format(exc))

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception:                                   # noqa: BLE001
            pass
        cls.db.DB_PATH = cls.orig
        for ext in ('', '-wal', '-shm'):
            try:
                os.remove(cls.path + ext)
            except OSError:
                pass

    def test_every_tab_builds_under_both_themes(self):
        import theme
        import i18n
        from main import BUILDERS
        from tab_home import build_home_tab
        from tab_assistant import build_assistant_tab
        from tab_tools import build_tools_tab

        get = self.db.get_conn
        conn = get()
        i18n.load(conn)
        conn.close()

        always = {'Home': build_home_tab, 'Assistant': build_assistant_tab,
                  'Tools': build_tools_tab}
        builders = dict(BUILDERS)
        builders.update(always)

        for mode in ('light', 'dark'):
            theme.apply(self.root, mode)
            holder = ttk.Frame(self.root)
            for label, builder in builders.items():
                try:
                    builder(holder, get)
                except Exception as exc:                    # noqa: BLE001
                    self.fail('{} failed to build in {} mode: {!r}'.format(
                        label, mode, exc))
            self.root.update_idletasks()
            holder.destroy()

    def test_project_overview_gathers_for_a_real_project(self):
        from tab_projects import ProjectOverview
        ov = ProjectOverview(self.root, self.db.get_conn)
        conn = self.db.get_conn()
        pid = conn.execute('SELECT id FROM projects LIMIT 1').fetchone()[0]
        conn.close()
        m = ov._gather(pid)
        # the drill-down surfaces money, programme and risk together
        for key in ('budget', 'cost', 'billed', 'margin', 'slip', 'ld',
                    'retention', 'var_unbilled', 'snag_blockers', 'rfis_open',
                    'ncr_open', 'progress'):
            self.assertIn(key, m)
        ov.destroy()


if __name__ == '__main__':
    unittest.main(verbosity=2)
