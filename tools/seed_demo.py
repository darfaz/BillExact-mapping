import os, sqlite3, datetime, pathlib
db=os.environ.get("BILLEXACT_DB","data/billexact.db")
pathlib.Path(db).parent.mkdir(parents=True, exist_ok=True)
conn=sqlite3.connect(db); c=conn.cursor()
c.executescript(open("db/init.sql","r",encoding="utf-8").read())
today=datetime.date.today().isoformat()
c.execute("INSERT OR IGNORE INTO clients(client_id,name) VALUES(?,?)",("CLIENT1","Acme Insurance"))
c.execute("INSERT OR IGNORE INTO matters(matter_id,client_id,description) VALUES(?,?,?)",("MATTER1","CLIENT1","Smith v. Acme"))
c.execute("INSERT OR IGNORE INTO timekeepers(id,name) VALUES(?,?)",("TK1","Alice Attorney"))
rows=c.execute("SELECT COUNT(*) FROM time_entries").fetchone()[0]
if rows==0:
    c.executemany("INSERT INTO time_entries(date,description,duration,utbms_code,matter_id,client_id,timekeeper_id) VALUES (?,?,?,?,?,?,?)",[
        (today,"Draft motion for summary judgment; emails to client",0.8,"L310","MATTER1","CLIENT1","TK1"),
        (today,"Review docs",0.2,"","MATTER1","CLIENT1","TK1"),
        (today,"Travel to deposition",1.0,"","MATTER1","CLIENT1","TK1"),
    ])
conn.commit(); conn.close()
print("DB ready at:", db)
