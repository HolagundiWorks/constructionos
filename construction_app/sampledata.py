"""A realistic sample book, so the app can be seen working before a single real
record is entered.

``seed(conn)`` fills a freshly ``init_db``'d database with one contractor's
worth of live work — three projects mid-flight, aged receivables, retention past
its release date, an over-invoiced PO, overdue filings, a late programme — so
the Home dashboard, the KPI board and every register have something to show. It
is wired to a **separate** "Sample Data" company file from Tools, never the
user's own book.

Dates are relative (SQLite ``date('now', …)``) so the demo stays current
whenever it is opened. Pure SQL on stdlib sqlite3 — no tkinter, testable
headlessly. The row ids are deterministic because a fresh file autoincrements
from 1; the guard below refuses to seed a file that already holds masters, so it
can never double-insert or clash ids.
"""


def is_empty(conn):
    """True when the book has no masters yet — safe to seed."""
    try:
        return conn.execute('SELECT COUNT(*) FROM sites').fetchone()[0] == 0
    except Exception:                                       # noqa: BLE001
        return False


def seed(conn):
    """Populate an empty database. Returns True if it seeded, False if the book
    already had data (and was left untouched)."""
    if not is_empty(conn):
        return False
    c = conn.cursor()

    def ex(sql):
        c.execute(sql)

    # ---- settings
    ex("INSERT OR REPLACE INTO app_settings(key,value) "
       "VALUES('cash_opening','100000')")
    ex("INSERT OR REPLACE INTO app_settings(key,value) "
       "VALUES('company_name','Sahyadri Constructions (Sample)')")

    # ---- masters: sites
    ex("INSERT INTO sites(name,location,site_type,status) VALUES"
       "('Skyline Residency, Pune','Baner, Pune','Building','Active'),"
       "('NH-48 Widening Pkg-3','Khed Shivapur','Road','Active'),"
       "('Green Valley Villas, Nashik','Gangapur Rd','Building','Active')")

    # ---- clients
    ex("INSERT INTO clients(name,contact_person,phone) VALUES"
       "('Rajgad Developers Pvt Ltd','Mr. Kulkarni','9822012345'),"
       "('PMRDA','Executive Engineer','020-25510000'),"
       "('Sai Infra Pvt Ltd','Mr. Deshpande','9890056789')")

    # ---- vendors (approved flags feed vendor rating)
    ex("INSERT INTO vendors(name,contact_person,phone,gst_no) VALUES"
       "('UltraTech Cement','Dealer Desk','9011000001','27AAACL1234M1Z5'),"
       "('Tata Steel Processors','Sales','9011000002','27AAACT5678N1Z2'),"
       "('Balaji RMC','Plant','9011000003','27AABFB9012P1Z9'),"
       "('Deccan Equipment Hire','Yard','9011000004','27AAAFD3456Q1Z1')")
    ex("UPDATE vendors SET approved=1, quality=4.2, delivery=3.8, price=4.0 "
       "WHERE id IN (1,2,3)")

    # ---- materials
    ex("INSERT INTO materials(name,unit,category,rate) VALUES"
       "('OPC 53 Cement','bag','Cement',380),"
       "('TMT Steel 12mm','kg','Steel',62),"
       "('M20 RMC','cum','Concrete',5200),"
       "('Aggregate 20mm','cum','Aggregate',1400),"
       "('Red Bricks','nos','Masonry',9)")

    # ---- labour
    ex("INSERT INTO labor(name,site_id,skill,daily_wage,status) VALUES"
       "('Rajesh Pawar',1,'Mason',850,'Active'),"
       "('Suresh Yadav',1,'Bar bender',800,'Active'),"
       "('Imran Shaikh',2,'Operator',950,'Active'),"
       "('Lakhan Verma',3,'Helper',600,'Active')")

    # ---- equipment (one overdue for service, one due soon)
    ex("INSERT INTO equipment(name,category,current_site_id,status,"
       "service_interval_hours,service_interval_days,last_service_date,"
       "make_model) VALUES"
       "('JCB 3DX Backhoe','Excavator',2,'Available',250,90,"
       "date('now','-210 day'),'JCB 3DX'),"
       "('Transit Mixer','Concrete',1,'Available',300,90,"
       "date('now','-80 day'),'AMW 2518'),"
       "('Tower Crane TC-1','Crane',1,'Available',500,180,"
       "date('now','-30 day'),'Potain MC85')")
    ex("INSERT INTO plant_logs(site_id,log_date,equipment,equipment_id,"
       "hours_run,diesel_ltr,downtime_hrs,operator) VALUES"
       "(2,date('now','-3 day'),'JCB 3DX Backhoe',1,8,45,0,'Imran'),"
       "(2,date('now','-2 day'),'JCB 3DX Backhoe',1,7.5,70,1,'Imran'),"
       "(1,date('now','-2 day'),'Transit Mixer',2,6,30,0,'Rajesh')")

    # ---- projects (contract_value/LD terms for programme + margin)
    ex("INSERT INTO projects(name,client_id,site_id,start_date,end_date,budget,"
       "status,contract_value,ld_pct_per_week,ld_cap_pct) VALUES"
       "('Skyline Residency',1,1,date('now','-520 day'),date('now','-400 day'),"
       "22000000,'Active',25000000,0.5,10),"
       "('NH-48 Widening Pkg-3',2,2,date('now','-200 day'),date('now','+90 day'),"
       "78000000,'Active',80000000,0.5,10),"
       "('Green Valley Villas',3,3,date('now','-120 day'),date('now','+150 day'),"
       "30000000,'Active',32000000,0.5,10)")
    ex("INSERT INTO milestones(project_id,name,target_date,status,amount) VALUES"
       "(2,'Earthwork complete',date('now','-40 day'),'Done',0),"
       "(2,'GSB + WMM layer',date('now','-10 day'),'Pending',0),"
       "(3,'Plinth complete',date('now','+20 day'),'Pending',0)")

    # ---- contracts (C1 completed >12mo ago -> retention now due)
    ex("INSERT INTO contracts(contract_no,site_id,client_id,contract_value,"
       "retention_pct,start_date,end_date,status,project_id) VALUES"
       "('SC/2023/11',1,1,25000000,5,date('now','-520 day'),"
       "date('now','-400 day'),'Active',1),"
       "('SC/2025/04',2,2,80000000,5,date('now','-200 day'),"
       "date('now','+90 day'),'Active',2),"
       "('SC/2025/09',3,3,32000000,5,date('now','-120 day'),"
       "date('now','+150 day'),'Active',3)")

    # ---- client bills: aged + current + drafts (approvals) + retention held
    ex("INSERT INTO bills(contract_id,bill_no,bill_date,status,work_done_value,"
       "retention_amt,net_payable,remarks) VALUES"
       "(1,'RA-05',date('now','-130 day'),'Approved',4000000,200000,3600000,"
       "'Final wing A'),"
       "(2,'RA-01',date('now','-100 day'),'Approved',2600000,130000,2470000,"
       "'Earthwork'),"
       "(2,'RA-02',date('now','-18 day'),'Approved',1600000,80000,1520000,"
       "'GSB layer'),"
       "(3,'RA-01',date('now','-6 day'),'Draft',900000,45000,855000,"
       "'Foundation'),"
       "(2,'RA-03',date('now','-2 day'),'Submitted',1200000,60000,1140000,"
       "'WMM layer')")

    # ---- an RA (BOQ) bill, approved
    ex("INSERT INTO ra_bills(contract_id,bill_no,bill_date,status,this_bill_value,"
       "retention_pct,retention_amt,net_payable) VALUES"
       "(3,'BOQ-RA-01',date('now','-25 day'),'Approved',1800000,5,90000,1710000)")

    # ---- receipts (partial -> receivables remain; oldest stays 90+)
    ex("INSERT INTO payments(pay_date,direction,party_type,party_id,party_name,"
       "mode,amount,against_type,against_id,site_id) VALUES"
       "(date('now','-90 day'),'Receipt','Client',1,'Rajgad Developers Pvt Ltd',"
       "'Bank',2800000,'Bill',1,1),"
       "(date('now','-15 day'),'Receipt','Client',2,'PMRDA','Bank',2000000,"
       "'Bill',2,2),"
       "(date('now','-4 day'),'Receipt','Client',3,'Sai Infra Pvt Ltd','Cash',"
       "150000,'OnAccount',NULL,3)")

    # ---- purchase orders + GRN (one matched, one invoiced without receipt)
    ex("INSERT INTO purchase_orders(po_no,vendor_id,site_id,po_date,status,"
       "total_amount) VALUES"
       "('PO-101',3,1,date('now','-20 day'),'Sent',500000),"
       "('PO-102',2,2,date('now','-12 day'),'Sent',300000),"
       "('PO-103',1,3,date('now','-3 day'),'Draft',180000)")
    ex("INSERT INTO goods_receipts(grn_no,purchase_order_id,vendor_id,site_id,"
       "grn_date,status,received_by) VALUES"
       "('GRN-55',1,3,1,date('now','-18 day'),'Posted','Store')")
    ex("INSERT INTO grn_items(grn_id,material_id,description,unit,qty_received,"
       "qty_accepted,rate,amount) VALUES"
       "(1,3,'M20 RMC','cum',96,96,5200,499200)")

    # ---- vendor invoices: VI1 matched, VI2 no GRN (3-way risk), VI3 no PO
    ex("INSERT INTO vendor_invoices(invoice_no,vendor_id,purchase_order_id,"
       "invoice_date,subtotal,tax_amount,total_amount,net_payable,amount_paid,"
       "status) VALUES"
       "('BRMC/771',3,1,date('now','-16 day'),500000,90000,590000,590000,0,"
       "'Received'),"
       "('TATA/2231',2,2,date('now','-8 day'),300000,54000,354000,354000,0,"
       "'Received'),"
       "('UT/9087',1,NULL,date('now','-5 day'),180000,32400,212400,212400,0,"
       "'Received')")
    ex("INSERT INTO payments(pay_date,direction,party_type,party_id,party_name,"
       "mode,amount,against_type,against_id,site_id) VALUES"
       "(date('now','-10 day'),'Payment','Vendor',3,'Balaji RMC','Bank',400000,"
       "'VendorInvoice',1,1),"
       "(date('now','-6 day'),'Payment','Labour',NULL,'Site wages','Cash',80000,"
       "'OnAccount',NULL,1)")

    # ---- variations: approved-unbilled + one raised (pending decision)
    ex("INSERT INTO variations(contract_id,var_no,var_date,description,reason,"
       "unit,qty,rate,amount,status,approved_by,approved_date) VALUES"
       "(2,'VO-02',date('now','-30 day'),'Extra culvert','Site condition','no',"
       "1,150000,150000,'Approved','PM',date('now','-25 day')),"
       "(2,'VO-03',date('now','-5 day'),'Shifting of utility','Client instruction',"
       "'LS',1,90000,90000,'Raised',NULL,NULL)")

    # ---- weekly look-ahead (PPC ~60% last week; two weeks of history)
    ex("INSERT INTO commitments(site_id,week_start,task,responsible,status,reason)"
       " VALUES"
       "(2,date('now','-7 day'),'GSB 300m','Imran','Done',NULL),"
       "(2,date('now','-7 day'),'WMM 300m','Imran','Done',NULL),"
       "(2,date('now','-7 day'),'Culvert RCC','Rajesh','Done',NULL),"
       "(2,date('now','-7 day'),'Shoulder work','Suresh','Not done','Material late'),"
       "(2,date('now','-7 day'),'Line marking','Lakhan','Not done','Rain'),"
       "(2,date('now','-14 day'),'Earthwork 500m','Imran','Done',NULL),"
       "(2,date('now','-14 day'),'Subgrade','Rajesh','Not done','Material late')")

    # ---- RFIs (open, oldest 25 days)
    ex("INSERT INTO rfis(rfi_no,site_id,contract_id,raised_date,subject,status) "
       "VALUES"
       "('RFI-11',2,2,date('now','-25 day'),'Culvert invert level','Open'),"
       "('RFI-12',1,1,date('now','-8 day'),'Facade tile spec','Open'),"
       "('RFI-09',3,3,date('now','-40 day'),'Grade of concrete','Answered')")

    # ---- inspections + NCRs (one critical open, one major open, one closed)
    ex("INSERT INTO inspections(site_id,activity,element,stage,inspection_date,"
       "result) VALUES(1,'M25 Slab','2nd floor','Pre-pour',date('now','-12 day'),"
       "'Fail')")
    ex("INSERT INTO ncrs(ncr_no,site_id,inspection_id,raised_date,description,"
       "severity,status) VALUES"
       "('NCR-07',1,1,date('now','-12 day'),'Cover block spacing','Critical',"
       "'Open'),"
       "('NCR-06',2,NULL,date('now','-40 day'),'Compaction below spec','Major',"
       "'Open'),"
       "('NCR-05',1,NULL,date('now','-60 day'),'Honeycomb in column','Minor',"
       "'Closed')")

    # ---- snags (one blocker open at closeout)
    ex("INSERT INTO snags(site_id,snag_no,raised_date,description,trade,severity,"
       "status) VALUES"
       "(1,'S-21',date('now','-15 day'),'Lift not commissioned','Electrical',"
       "'Blocker','Open'),"
       "(1,'S-22',date('now','-15 day'),'Seepage in basement','Waterproofing',"
       "'Major','Open'),"
       "(1,'S-23',date('now','-15 day'),'Paint touch-up lobby','Painting','Minor',"
       "'Open'),"
       "(1,'S-20',date('now','-30 day'),'Door alignment','Carpentry','Minor',"
       "'Verified')")

    # ---- material requisitions (front of procurement chain)
    ex("INSERT INTO material_requisitions(req_no,site_id,req_date,requested_by,"
       "status) VALUES"
       "('MR-31',2,date('now','-6 day'),'Site Engr','Open'),"
       "('MR-32',3,date('now','-3 day'),'Site Engr','Open'),"
       "('MR-30',1,date('now','-10 day'),'Store','Ordered')")

    # ---- bid assessments (two not decided)
    ex("INSERT INTO bid_assessments(tender_ref,title,client_id,tender_value,"
       "submission_date,decision,outcome) VALUES"
       "('NHAI/2026/07','Flyover at Katraj',2,52000000,date('now','+12 day'),"
       "'Not decided','Pending'),"
       "('PMC/2026/03','STP civil works',2,12500000,date('now','+6 day'),"
       "'Not decided','Pending')")

    # ---- compliance filings (two overdue, one due soon)
    ex("INSERT INTO compliance_filings(obligation,period,due_date,filed_date) "
       "VALUES"
       "('gstr1',strftime('%Y-%m','now','-2 month'),date('now','-35 day'),NULL),"
       "('gstr3b',strftime('%Y-%m','now','-2 month'),date('now','-28 day'),NULL),"
       "('tds_26q',strftime('%Y-%m','now'),date('now','+5 day'),NULL)")

    # ---- NH-48 programme: a real dependency network for the scheduler + Gantt.
    # Ids autoincrement from 1 (this is the only insert into timeline_tasks), so
    # predecessors and parent_id can reference them by number. Working-day
    # durations, typed predecessors (SS on the culvert runs it in parallel), a
    # milestone, and a baselined slip on Earthwork so the delay advisory fires.
    ex("INSERT INTO timeline_tasks(site_id,project_id,task_name,duration_days,"
       "dependency,pct_complete,status,baseline_start,baseline_end,"
       "actual_start,actual_end,delay_cause) VALUES"
       "(2,2,'Site mobilisation',5,'',100,'Completed',NULL,NULL,NULL,NULL,NULL),"
       "(2,2,'Earthwork',20,'1',100,'Completed',date('now','-195 day'),"
       "date('now','-176 day'),date('now','-195 day'),date('now','-170 day'),"
       "'Contractor delay'),"
       "(2,2,'GSB layer',15,'2',80,'In Progress',NULL,NULL,NULL,NULL,NULL),"
       "(2,2,'WMM layer',12,'3',40,'In Progress',NULL,NULL,NULL,NULL,NULL),"
       "(2,2,'Culvert RCC',18,'2SS+3',30,'In Progress',NULL,NULL,NULL,NULL,NULL),"
       "(2,2,'DBM + BC (blacktop)',20,'4,5',0,'Not Started',NULL,NULL,NULL,"
       "NULL,NULL),"
       "(2,2,'Road handover',0,'6',0,'Not Started',NULL,NULL,NULL,NULL,NULL)")

    # ---- some site cost so project margins have inputs
    ex("INSERT INTO material_ledger(txn_date,site_id,material_id,txn_type,qty,"
       "rate) VALUES"
       "(date('now','-30 day'),2,4,'OUT',400,1400),"
       "(date('now','-20 day'),2,2,'OUT',12000,62)")

    conn.commit()

    # the CPWD reference library too, so the Rate Book / Rate Analysis /
    # Consumption tabs and the "From Rate Book" picker all have data in the demo.
    import refdata
    refdata.load(conn)
    return True
