"""
╔══════════════════════════════════════════════════════════════╗
║   ☄  ASTEROID DETECTION AND TRACKING SYSTEM  v5.0           ║
║   Python GUI · SQLite · tkinter + matplotlib                 ║
║                                                              ║
║   Team: Shreyas G Kamath  (240953322)                        ║
║         Rahul Kumar Mahto (240953370)                        ║
║   Course: Database Systems (DBS) – IV Semester               ║
║                                                              ║
║   v5.0 Additions:                                            ║
║     ✔ SQLite Audit Log (all CRUD changes tracked)            ║
║     ✔ Audit Log Viewer tab                                   ║
║     ✔ Show/Hide password toggle on Login screen              ║
║     ✔ Risk alert popup delayed to 10 seconds                 ║
║     ✔ Map performance: OSM tiles + tile cache boost          ║
║     ✔ Asteroid Collision Simulator tab                       ║
║       · Click asteroid → impact location on map              ║
║       · 🔴 Impact / 🟡 Damage / 🟢 Safe zone rings           ║
║       · Blast radius calculated from asteroid diameter       ║
╚══════════════════════════════════════════════════════════════╝
"""

# ── Standard library ──────────────────────────────────────
import sqlite3, sys, datetime, logging, csv
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from collections import Counter

# ── Third-party ───────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import numpy as np
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False

try:
    import tkintermapview
    MAP_OK = True
except ImportError:
    MAP_OK = False

try:
    from PIL import Image, ImageTk, ImageDraw
    PIL_OK = True
except ImportError:
    PIL_OK = False

# ═══════════════════════════════════════════════════════════
# 0.  LOGGING
# ═══════════════════════════════════════════════════════════

logging.basicConfig(
    filename="asteroid_tracker.log",
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
def log(msg, level="info"):
    getattr(logging, level)(msg)

# ── Audit log (DB-level change tracking) ──────────────────
_CURRENT_USER = "system"   # updated after login

def audit_log(action: str, table: str, record_id, detail: str = ""):
    """Write a row to the Audit_Log table for every CRUD change."""
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            "INSERT INTO Audit_Log (Timestamp, Username, Action, Table_Name, Record_ID, Detail) "
            "VALUES (datetime('now','localtime'), ?, ?, ?, ?, ?)",
            (_CURRENT_USER, action, table, str(record_id), detail)
        )
        conn.commit()
        conn.close()
    except Exception as ex:
        log(f"audit_log error: {ex}", "warning")

# ═══════════════════════════════════════════════════════════
# 1.  DATABASE LAYER
# ═══════════════════════════════════════════════════════════

DB_FILE = "asteroid_tracker.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn

DDL = """
CREATE TABLE IF NOT EXISTS Users (
    Username  TEXT PRIMARY KEY,
    Password  TEXT NOT NULL,
    Role      TEXT NOT NULL CHECK(Role IN ('Admin','Researcher','Public'))
);
CREATE TABLE IF NOT EXISTS Audit_Log (
    Log_ID      INTEGER PRIMARY KEY AUTOINCREMENT,
    Timestamp   TEXT    NOT NULL,
    Username    TEXT    NOT NULL,
    Action      TEXT    NOT NULL,
    Table_Name  TEXT    NOT NULL,
    Record_ID   TEXT,
    Detail      TEXT
);
CREATE TABLE IF NOT EXISTS Observatories (
    Observatory_ID   INTEGER PRIMARY KEY,
    Name             TEXT    NOT NULL,
    Country          TEXT    NOT NULL,
    Established_Year INTEGER,
    Latitude         REAL,
    Longitude        REAL
);
CREATE TABLE IF NOT EXISTS Telescopes (
    Telescope_ID   INTEGER PRIMARY KEY,
    Name           TEXT    NOT NULL,
    Location       TEXT,
    Type           TEXT,
    Aperture_Size  REAL,
    Observatory_ID INTEGER REFERENCES Observatories(Observatory_ID) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS Scientists (
    Scientist_ID     INTEGER PRIMARY KEY,
    Name             TEXT    NOT NULL,
    Specialization   TEXT,
    Experience_Years INTEGER
);
CREATE TABLE IF NOT EXISTS Risk_Category (
    Risk_ID           INTEGER PRIMARY KEY,
    Category_Name     TEXT    NOT NULL,
    Probability_Range TEXT    NOT NULL,
    Description       TEXT
);
CREATE TABLE IF NOT EXISTS Asteroids (
    Asteroid_ID    INTEGER PRIMARY KEY,
    Name           TEXT    NOT NULL UNIQUE,
    Diameter       REAL,
    Orbital_Period REAL
);
CREATE TABLE IF NOT EXISTS Missions (
    Mission_ID   INTEGER PRIMARY KEY,
    Mission_Name TEXT    NOT NULL,
    Launch_Date  TEXT,
    Agency       TEXT
);
CREATE TABLE IF NOT EXISTS Asteroid_Mission (
    Asteroid_ID INTEGER REFERENCES Asteroids(Asteroid_ID) ON DELETE CASCADE,
    Mission_ID  INTEGER REFERENCES Missions(Mission_ID)   ON DELETE CASCADE,
    PRIMARY KEY (Asteroid_ID, Mission_ID)
);
CREATE TABLE IF NOT EXISTS Observations (
    Observation_ID   INTEGER PRIMARY KEY,
    Observation_Date TEXT    NOT NULL,
    Position         TEXT,
    Asteroid_ID      INTEGER REFERENCES Asteroids(Asteroid_ID)  ON DELETE CASCADE,
    Telescope_ID     INTEGER REFERENCES Telescopes(Telescope_ID) ON DELETE SET NULL,
    Scientist_ID     INTEGER REFERENCES Scientists(Scientist_ID) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS Detection_Events (
    Event_ID       INTEGER PRIMARY KEY,
    Asteroid_ID    INTEGER REFERENCES Asteroids(Asteroid_ID)   ON DELETE CASCADE,
    Detection_Date TEXT    NOT NULL,
    Probability    REAL    CHECK(Probability BETWEEN 0 AND 1),
    Risk_ID        INTEGER REFERENCES Risk_Category(Risk_ID)   ON DELETE SET NULL,
    Scientist_ID   INTEGER REFERENCES Scientists(Scientist_ID) ON DELETE SET NULL
);
"""

# ── Seed data ─────────────────────────────────────────────

SEED_OBSERVATORIES = [
    (1,'Mauna Kea Observatories','United States',1968),
    (2,'Paranal Observatory','Chile',1998),(3,'La Silla Observatory','Chile',1969),
    (4,'Roque de los Muchachos Observatory','Spain',1985),
    (5,'Kitt Peak National Observatory','United States',1958),
    (6,'Cerro Tololo Inter-American Observatory','Chile',1961),
    (7,'Very Large Telescope (VLT)','Chile',1998),
    (8,'Subaru Telescope','United States',1999),
    (9,'Gemini North Observatory','United States',1999),
    (10,'Gemini South Observatory','Chile',2001),
    (11,'Apache Point Observatory','United States',1997),
    (12,'Palomar Observatory','United States',1948),
    (13,'McDonald Observatory','United States',1939),
    (14,'Lowell Observatory','United States',1894),
    (15,'Lick Observatory','United States',1888),
    (16,'W. M. Keck Observatory','United States',1993),
    (17,'Large Binocular Telescope','United States',2005),
    (18,'MMT Observatory','United States',1979),
    (19,'Canada-France-Hawaii Telescope','United States',1979),
    (20,'Las Campanas Observatory','Chile',1971),
    (21,'Magellan Telescopes','Chile',2000),
    (22,'Vera C. Rubin Observatory','Chile',2025),
    (23,'Atacama Large Millimeter Array (ALMA)','Chile',2011),
    (24,'Teide Observatory','Spain',1964),
    (25,'South African Astronomical Observatory','South Africa',1972),
    (26,'Siding Spring Observatory','Australia',1964),
    (27,'Xinglong Observatory','China',1968),
    (28,'Devasthal Observatory','India',2016),
    (29,'Indian Astronomical Observatory (Hanle)','India',2001),
    (30,'San Pedro Martir Observatory','Mexico',1971),
    (31,'Calar Alto Observatory','Spain',1979),
    (32,'Okayama Astrophysical Observatory','Japan',1960),
    (33,'National Astronomical Observatory of Japan','Japan',1924),
    (34,'Brera Astronomical Observatory','Italy',1764),
    (35,'Observatoire de Haute-Provence','France',1937),
    (36,'Pic du Midi Observatory','France',1878),
    (37,'Observatoire de Paris','France',1667),
    (38,'Mount Wilson Observatory','United States',1904),
    (39,'Fred Lawrence Whipple Observatory','United States',1968),
    (40,'David Dunlap Observatory','Canada',1935),
    (41,'National Solar Observatory','United States',1984),
    (42,'Daniel K. Inouye Solar Telescope','United States',2020),
    (43,'MeerKAT Radio Telescope','South Africa',2018),
    (44,'FAST (Five-hundred-meter Aperture Spherical Telescope)','China',2016),
    (45,'Green Bank Telescope','United States',2000),
    (46,'Arecibo Observatory (historical)','Puerto Rico',1963),
    (47,'Parkes Observatory','Australia',1961),
    (48,'Jodrell Bank Observatory','United Kingdom',1957),
    (49,'Extremely Large Telescope (ELT site)','Chile',2028),
    (50,'Thirty Meter Telescope (planned)','United States',2030),
]

OBSERVATORY_COORDS = {
    1:  (19.8208, -155.4681),
    2:  (-24.6275, -70.4044),
    3:  (-29.2566, -70.7292),
    4:  (28.7624, -17.8896),
    5:  (31.9583, -111.6003),
    6:  (-30.1653, -70.8150),
    7:  (-24.6275, -70.4044),
    8:  (19.8256, -155.4760),
    9:  (19.8238, -155.4690),
    10: (-30.2408, -70.7367),
    11: (32.7803, -105.8203),
    12: (33.3564, -116.8650),
    13: (30.6714, -104.0225),
    14: (35.2029, -111.6647),
    15: (37.3414, -121.6429),
    16: (19.8283, -155.4783),
    17: (32.7016, -109.8892),
    18: (31.6883, -110.8850),
    19: (19.8255, -155.4717),
    20: (-29.0092, -70.6919),
    21: (-29.0146, -70.6926),
    22: (-30.2446, -70.7494),
    23: (-23.0193, -67.7532),
    24: (28.3004, -16.5126),
    25: (-32.3797, 20.8107),
    26: (-31.2733, 149.0617),
    27: (40.3958, 117.5753),
    28: (29.3606, 79.6869),
    29: (32.7794, 78.9642),
    30: (31.0444, -115.4611),
    31: (37.2236, -2.5461),
    32: (34.4756, 133.5942),
    33: (35.6762, 139.6503),
    34: (45.4654, 9.1866),
    35: (43.9317, 5.7133),
    36: (42.9367, 0.1425),
    37: (48.8356, 2.3364),
    38: (34.2236, -118.0567),
    39: (31.6808, -110.8783),
    40: (43.8647, -79.4225),
    41: (32.7875, -105.8203),
    42: (20.7068, -156.2561),
    43: (-30.7130, 21.4430),
    44: (25.6529, 106.8566),
    45: (38.4331, -79.8397),
    46: (18.3444, -66.7528),
    47: (-32.9994, 148.2592),
    48: (53.2367, -2.3086),
    49: (-24.5897, -70.1917),
    50: (19.8206, -155.4681),
}

SEED_TELESCOPES = [
    (1,'Antu (VLT UT1)','Paranal','Reflector',8.2,2),
    (2,'Kueyen (VLT UT2)','Paranal','Reflector',8.2,2),
    (3,'Melipal (VLT UT3)','Paranal','Reflector',8.2,2),
    (4,'Yepun (VLT UT4)','Paranal','Reflector',8.2,2),
    (5,'Subaru Telescope','Mauna Kea','Reflector',8.2,1),
    (6,'Gemini North','Mauna Kea','Reflector',8.1,1),
    (7,'Gemini South','Cerro Pachon','Reflector',8.1,20),
    (8,'Keck I','Mauna Kea','Reflector',10.0,1),
    (9,'Keck II','Mauna Kea','Reflector',10.0,1),
    (10,'Large Binocular Telescope (LBT)','Mount Graham','Reflector',8.4,17),
    (11,'MMT (Multiple Mirror Telescope)','Mount Hopkins','Reflector',6.5,18),
    (12,'Canada-France-Hawaii Telescope (CFHT)','Mauna Kea','Reflector',3.6,19),
    (13,'Blanco 4m Telescope','Cerro Tololo','Reflector',4.0,6),
    (14,'Mayall 4m Telescope','Kitt Peak','Reflector',4.0,5),
    (15,'Hale 200-inch Telescope','Palomar Mountain','Reflector',5.1,12),
    (16,'Shane 3m Telescope','Mount Hamilton','Reflector',3.0,13),
    (17,'WIYN 3.5m Telescope','Kitt Peak','Reflector',3.5,5),
    (18,'SOAR 4.1m Telescope','Cerro Pachon','Reflector',4.1,20),
    (19,'Magellan Clay 6.5m','Las Campanas','Reflector',6.5,20),
    (20,'Magellan Baade 6.5m','Las Campanas','Reflector',6.5,20),
    (21,'Gran Telescopio Canarias (GTC)','La Palma','Reflector',10.4,4),
    (22,'William Herschel Telescope','La Palma','Reflector',4.2,4),
    (23,'Isaac Newton Telescope','La Palma','Reflector',2.5,4),
    (24,'Nordic Optical Telescope','La Palma','Reflector',2.56,4),
    (25,'3.5m Telescope Calar Alto','Calar Alto','Reflector',3.5,31),
    (26,'2.2m Telescope Calar Alto','Calar Alto','Reflector',2.2,31),
    (27,'Devasthal Optical Telescope (DOT)','Nainital','Reflector',3.6,28),
    (28,'3.6m Telescope Devasthal','Devasthal','Reflector',3.6,28),
    (29,'2m HCT (Himalayan Chandra Telescope)','Hanle','Reflector',2.0,29),
    (30,'San Pedro Martir 2.12m','San Pedro Martir','Reflector',2.12,30),
    (31,'Harold Johnson 1.5m','San Pedro Martir','Reflector',1.5,30),
    (32,'Inouye Solar Telescope (DKIST)','Haleakala','Solar',4.0,42),
    (33,'NSO Dunn Solar Telescope','Sacramento Peak','Solar',1.6,41),
    (34,'ALMA 12m Antenna','Atacama','Radio',12.0,23),
    (35,'MeerKAT Dish','Karoo','Radio',13.5,43),
    (36,'FAST 500m Dish','Pingtang','Radio',500.0,44),
    (37,'Green Bank Telescope','West Virginia','Radio',100.0,45),
    (38,'Parkes 64m Dish','Parkes','Radio',64.0,47),
    (39,'Lovell 76m Telescope','Jodrell Bank','Radio',76.0,48),
    (40,'Very Large Array (VLA) Antenna','Socorro','Radio',25.0,5),
    (41,'IRTF (Infrared Telescope Facility)','Mauna Kea','Reflector',3.0,1),
    (42,'UKIRT','Mauna Kea','Reflector',3.8,1),
    (43,'James Clerk Maxwell Telescope (JCMT)','Mauna Kea','Sub-mm',15.0,1),
    (44,'Apache Point 3.5m Telescope','Apache Point','Reflector',3.5,11),
    (45,'Whipple Observatory 1.2m','Mount Hopkins','Reflector',1.2,39),
    (46,'McDonald 2.7m Harlan J. Smith','Mount Locke','Reflector',2.7,13),
    (47,'Lowell Discovery Channel Telescope','Happy Jack','Reflector',4.3,14),
    (48,'Pic du Midi 1m Telescope','Pic du Midi','Reflector',1.0,36),
    (49,'Haute-Provence 1.93m Telescope','Haute-Provence','Reflector',1.93,35),
    (50,'Teide IAC80 Telescope','Teide','Reflector',0.82,24),
]

SEED_SCIENTISTS = [
    (1,'Amy Mainzer','Near-Earth Object Detection',22),
    (2,'Paul Chodas','NEO Orbit Determination',32),
    (3,'Lindley Johnson','Planetary Defense Coordination',35),
    (4,'Alan Harris','Asteroid Physical Properties',38),
    (5,'Steven Chesley','NEO Impact Risk Assessment',28),
    (6,'Lance Benner','Radar Astrometry of NEOs',30),
    (7,'Jon Giorgini','JPL Horizons System & Ephemerides',34),
    (8,'David Jewitt','Trans-Neptunian Objects & Comets',40),
    (9,'Michael Brown','Dwarf Planets & Kuiper Belt',30),
    (10,'Scott Sheppard','Outer Solar System Discoveries',25),
    (11,'Chad Trujillo','Extreme Trans-Neptunian Objects',24),
    (12,'Megan Schwamb','Kuiper Belt & TNO Dynamics',20),
    (13,'Francesca DeMeo','Asteroid Taxonomy & Composition',18),
    (14,'Richard Binzel','Asteroid Spectroscopy & Families',42),
    (15,'Vishnu Reddy','Asteroid Surface Mineralogy',19),
    (16,'Nicholas Moskovitz','Asteroid Rotations & Phases',17),
    (17,'Josef Durech','Asteroid Shape Modeling',21),
    (18,'Marco Delbo','Asteroid Thermal Properties',23),
    (19,'Alberto Cellino','Asteroid Photometry & Polarimetry',36),
    (20,'Patrick Michel','Asteroid Impact Deflection & Hera',29),
    (21,'Nancy Chabot','DART Mission Science Lead',24),
    (22,'Angela Stickle','DART Impact Dynamics',16),
    (23,'Derek Richardson','Granular Asteroid Physics',27),
    (24,'Line Drube','Hera Mission Operations',15),
    (25,'Andrew Rivkin','Asteroid Spectroscopy for DART',22),
    (26,'Robert Jedicke','Pan-STARRS & Asteroid Surveys',26),
    (27,'Larry Denneau','ATLAS & Asteroid Alert System',23),
    (28,'Gareth Williams','Minor Planet Center Operations',29),
    (29,'Matthew Payne','Minor Planet Center Orbit Computation',18),
    (30,'Sonia Keys','Astrometric Reductions for MPC',20),
    (31,'Matthew Holman','Orbital Dynamics',31),
    (32,'Brett Gladman','Outer Solar System Stability',33),
    (33,'Martin Duncan','Celestial Mechanics Simulations',45),
    (34,'Harold Levison','Planet Formation & Dynamics',38),
    (35,'David Rabinowitz','Spacewatch NEO Survey',34),
    (36,'Roy Tucker','Amateur/Professional NEO Follow-up',28),
    (37,'Gordon Garradd','Comet & Asteroid Discoveries',30),
    (38,'Tim Lister','Las Cumbres Observatory Follow-up',19),
    (39,'Darin Ragozzine','Orbital Architectures of TNOs',17),
    (40,'Michele Bannister','Outer Solar System Spectroscopy',16),
    (41,'Wes Fraser','Kuiper Belt Surfaces',21),
    (42,'Henry Hsieh','Main-Belt Comets & Activity',18),
    (43,'Thomas Muller','Infrared Asteroid Observations',29),
    (44,'Daniel Hestroffer','Astrometry & Gaia Synergies',26),
    (45,'Jerome Berthier','Asteroid Occultations & Gaia',22),
    (46,'Anna Marciniak','Asteroid Spin Poles from Photometry',17),
    (47,'Tomasz Kwiatkowski','Asteroid Lightcurve Analysis',20),
    (48,'Przemyslaw Bartczak','Asteroid Shape Reconstruction',15),
    (49,'Karol Wlodarczyk','NEO Impact Probability Calculations',19),
    (50,'Shashank Gautam','NEO Follow-up Observations (India)',12),
]

SEED_RISK = [
    (1,'Zero','0','No collision possibility within foreseeable future'),
    (2,'Very Low','< 1 in 10^5','Extremely unlikely impact; negligible concern'),
    (3,'Low','1 in 10^4','Very low risk; routine monitoring'),
    (4,'Low-Moderate','1 in 10^3','Low concern; continued observations recommended'),
    (5,'Moderate','1 in 100','Moderate risk; merits attention and refinement'),
    (6,'Medium','1 in 10','Significant but not imminent; active follow-up needed'),
    (7,'Elevated','1 in 1','High enough to warrant detailed study'),
    (8,'High','1 in 100 to 10','Critical risk; international coordination required'),
    (9,'Very High','1 in 10 to 2','Imminent serious threat; mitigation essential'),
    (10,'Certain','> 0.5','Impact virtually certain; emergency response'),
]

PROB_RISK_MAP = [
    (0.0,      1),
    (1e-5,     2),
    (1e-4,     3),
    (1e-3,     4),
    (0.01,     5),
    (0.1,      6),
    (0.5,      7),
    (0.7,      8),
    (0.9,      9),
    (1.0,      10),
]

def probability_to_risk_id(prob: float) -> int:
    for threshold, risk_id in PROB_RISK_MAP:
        if prob <= threshold:
            return risk_id
    return 10

SEED_ASTEROIDS = [
    (1,'99942 Apophis',0.37,0.89),(2,'101955 Bennu',0.49,1.2),
    (3,'162173 Ryugu',0.9,1.3),(4,'433 Eros',34.4,1.76),
    (5,'25143 Itokawa',0.33,1.52),(6,'4179 Toutatis',2.45,4.03),
    (7,'216 Kleopatra',135.0,4.32),(8,'253 Mathilde',53.0,4.31),
    (9,'243 Ida',31.4,4.84),(10,'951 Gaspra',18.2,3.59),
    (11,'2867 Steins',5.3,3.54),(12,'21 Lutetia',100.0,3.8),
    (13,'1 Ceres',946.0,4.61),(14,'4 Vesta',525.0,3.63),
    (15,'2 Pallas',512.0,4.62),(16,'10 Hygiea',434.0,5.59),
    (17,'16 Psyche',226.0,5.0),(18,'65 Cybele',237.0,6.08),
    (19,'52 Europa',315.0,5.63),(20,'511 Davida',289.0,5.66),
    (21,'704 Interamnia',326.0,5.73),(22,'1580 Betulia',5.8,2.2),
    (23,'1566 Icarus',1.4,1.12),(24,'3200 Phaethon',5.1,1.43),
    (25,'3554 Amun',2.0,0.7),(26,'2100 Ra-Shalom',2.3,0.76),
    (27,'1862 Apollo',1.5,1.81),(28,'1620 Geographos',2.56,1.39),
    (29,'4769 Castalia',1.4,0.64),(30,'4660 Nereus',0.33,1.82),
    (31,'29075 1950 DA',1.3,2.39),(32,'33342 1998 WT24',0.41,0.57),
    (33,'341843 2008 EV5',0.45,0.96),(34,'136849 1998 CS1',1.2,2.38),
    (35,'136108 Haumea',1632.0,284.0),(36,'136472 Makemake',1430.0,306.0),
    (37,'225088 Gonggong',1230.0,550.0),(38,'50000 Quaoar',1086.0,285.0),
    (39,'90377 Sedna',995.0,11400.0),(40,'38628 Huya',406.0,250.0),
    (41,'28978 Ixion',710.0,250.0),(42,'55636 2002 TX300',320.0,283.0),
    (43,'84522 2002 TC302',590.0,410.0),(44,'15760 Albion',108.0,248.0),
    (45,'7066 Nessus',60.0,122.0),(46,'8405 Asbolus',84.0,76.0),
    (47,'54598 Bienor',200.0,67.0),(48,'120347 Salacia',870.0,284.0),
    (49,'2002 AW197',940.0,325.0),(50,'2002 MS4',730.0,270.0),
]

SEED_MISSIONS = [
    (1,'NEAR Shoemaker','1996-02-17','NASA'),(2,'Hayabusa','2003-05-09','JAXA'),
    (3,'Hayabusa2','2014-12-03','JAXA'),(4,'OSIRIS-REx','2016-09-08','NASA'),
    (5,'DART','2021-11-24','NASA'),(6,'Hera','2024-10-07','ESA'),
    (7,'Lucy','2021-10-16','NASA'),(8,'Psyche','2023-10-13','NASA'),
    (9,'Dawn','2007-09-27','NASA'),(10,'Stardust','1999-02-07','NASA'),
    (11,'Deep Impact','2005-01-12','NASA'),(12,'Rosetta','2004-03-02','ESA'),
    (13,"Chang'e 2",'2010-10-01','CNSA'),(14,"Chang'e 5",'2020-11-23','CNSA'),
    (15,'New Horizons','2006-01-19','NASA'),(16,'NEOWISE','2009-12-14','NASA'),
    (17,'Pan-STARRS','2010-12-06','Univ. Hawaii / NASA'),
    (18,'ATLAS','2015-12-18','NASA / Univ. Hawaii'),
    (19,'Catalina Sky Survey','1998-01-01','NASA'),
    (20,'Spacewatch','1984-01-01','Univ. Arizona / NASA'),
    (21,'LINEAR','1996-01-01','MIT Lincoln Lab / NASA'),
    (22,'WISE','2009-12-14','NASA'),(23,'B612 Sentinel','2018-01-01','B612 Foundation'),
    (24,'NEO Surveyor','2028-06-01','NASA'),(25,'Tianwen-2','2025-05-01','CNSA'),
    (26,'DESTINY+','2025-01-01','JAXA'),(27,'Comet Interceptor','2029-01-01','ESA'),
    (28,'Janus','2022-11-10','NASA'),(29,'NEA Scout','2022-11-16','NASA'),
    (30,'LICIACube','2021-11-24','ASI (Italy)'),(31,'PROCYON','2014-12-03','JAXA'),
    (32,'IKAROS','2010-05-21','JAXA'),(33,'LightSail 2','2019-06-25','Planetary Society'),
    (34,'ARM (Asteroid Redirect Mission)','2013-01-01','NASA'),
    (35,'APEX','2030-01-01','ESA'),(36,'Caesar','2030-01-01','NASA'),
    (37,'Hayabusa3','2032-01-01','JAXA'),(38,'EXTREMA','2035-01-01','Private / ESA'),
    (39,'TransAstra Apis','2028-01-01','TransAstra'),
    (40,'Asteroid Redirect Robotic','2026-01-01','NASA concept'),
    (41,'Dragonfly','2028-01-01','NASA'),(42,'Europa Clipper','2024-10-10','NASA'),
    (43,'VERITAS','2031-01-01','NASA'),(44,'EnVision','2031-01-01','ESA'),
    (45,'CuSP','2022-11-16','NASA'),(46,'ArgoMoon','2022-11-16','ASI'),
    (47,'BioSentinel','2022-11-16','NASA'),(48,'Equuleus','2022-11-16','JAXA'),
    (49,'Starling','2023-07-02','NASA'),(50,'Blue Ghost','2025-01-01','Firefly / NASA CLPS'),
]

SEED_AST_MISSION = [
    (1,5),(1,6),(2,4),(3,3),(4,1),(5,2),(6,8),(7,7),(8,9),(9,10),
    (10,11),(13,14),(14,9),(15,9),(16,9),(17,8),(22,24),(23,19),(24,20),
    (25,21),(26,21),(27,19),(28,18),(29,17),(30,4),(31,5),(32,6),(33,16),
    (34,22),(35,15),(36,15),(37,25),(38,15),(39,15),(40,15),(41,15),(42,26),
    (43,27),(44,28),(45,29),(46,30),(47,31),(48,32),(49,33),(50,7),
    (1,24),(2,24),(3,24),
]

SEED_DETECTION_EVENTS = [
    (1,1,'2023-04-22',0.000034,3,1),(2,2,'2023-06-15',0.000012,2,2),
    (3,3,'2023-08-09',0.000089,3,3),(4,4,'2023-10-03',0.000005,2,4),
    (5,5,'2023-12-18',0.000067,3,5),(6,6,'2024-02-14',0.001245,4,6),
    (7,7,'2024-04-07',0.000023,3,7),(8,8,'2024-06-01',0.000008,2,8),
    (9,9,'2024-07-25',0.000145,3,9),(10,10,'2024-09-19',0.000041,3,10),
    (11,11,'2024-11-12',0.000019,2,11),(12,12,'2025-01-06',0.000056,3,12),
    (13,13,'2025-03-02',0.000003,1,13),(14,14,'2025-04-26',0.000012,2,14),
    (15,15,'2025-06-20',0.000078,3,15),(16,16,'2025-08-14',0.000034,3,1),
    (17,17,'2025-10-08',0.001670,5,2),(18,18,'2025-12-02',0.000009,2,3),
    (19,19,'2026-01-27',0.000045,3,4),(20,20,'2026-03-23',0.002200,5,5),
    (21,21,'2023-05-11',0.000089,3,6),(22,22,'2023-07-05',0.002134,5,7),
    (23,23,'2023-09-28',0.000067,3,8),(24,24,'2024-01-19',0.000312,4,9),
    (25,25,'2024-03-14',0.000018,2,10),(26,26,'2024-05-08',0.000054,3,11),
    (27,27,'2024-08-01',0.000007,2,12),(28,28,'2024-10-25',0.000123,3,13),
    (29,29,'2025-02-18',0.000041,3,14),(30,30,'2025-05-13',0.000089,3,15),
    (31,31,'2025-07-07',0.000015,2,1),(32,32,'2025-09-30',0.000234,4,2),
    (33,33,'2026-02-24',0.000067,3,3),(34,34,'2023-11-16',0.000012,2,4),
    (35,35,'2024-02-09',0.000003,1,5),(36,36,'2024-04-04',0.000045,3,6),
    (37,37,'2024-07-28',0.001890,5,7),(38,38,'2025-01-21',0.000078,3,8),
    (39,39,'2025-04-16',0.000023,3,9),(40,40,'2025-08-10',0.000056,3,10),
    (41,41,'2025-11-03',0.000134,3,11),(42,42,'2026-01-28',0.000009,2,12),
    (43,43,'2026-04-23',0.000067,3,13),(44,44,'2023-03-29',0.000189,4,14),
    (45,45,'2023-10-20',0.000034,3,15),(46,46,'2024-06-13',0.000012,2,1),
    (47,47,'2025-03-07',0.000045,3,2),(48,48,'2025-09-30',0.000078,3,3),
    (49,49,'2026-02-24',0.000023,2,4),(50,50,'2026-05-19',0.000156,4,5),
]

SEED_OBSERVATIONS = [
    (1,'2023-03-15','RA 14h52m33s Dec -12d45m22s',1,1,1),
    (2,'2023-04-02','RA 05h18m09s Dec +28d19m47s',2,8,2),
    (3,'2023-05-20','RA 09h44m21s Dec -35d01m15s',3,4,3),
    (4,'2023-07-08','RA 22h11m55s Dec +15d33m59s',4,14,4),
    (5,'2023-08-25','RA 03h29m47s Dec -48d22m14s',5,5,5),
    (6,'2023-10-12','RA 17h36m04s Dec +09d08m31s',6,9,6),
    (7,'2023-11-30','RA 11h23m18s Dec -20d55m40s',7,15,7),
    (8,'2024-01-19','RA 06h55m42s Dec +32d17m03s',8,10,8),
    (9,'2024-03-07','RA 20h04m59s Dec -05d44m12s',9,11,9),
    (10,'2024-04-24','RA 13h47m36s Dec +41d29m58s',10,5,10),
    (11,'2024-06-11','RA 01h15m22s Dec -18d03m27s',11,12,11),
    (12,'2024-07-29','RA 18h39m50s Dec +24d51m09s',12,12,12),
    (13,'2024-09-16','RA 08h22m14s Dec -30d12m45s',13,13,13),
    (14,'2024-11-03','RA 15h58m07s Dec +07d36m22s',14,14,14),
    (15,'2024-12-21','RA 04h41m33s Dec -42d19m51s',15,1,15),
    (16,'2025-02-08','RA 21h06m45s Dec +16d44m38s',1,7,1),
    (17,'2025-03-26','RA 10h33m19s Dec -25d08m14s',2,8,2),
    (18,'2025-05-13','RA 00h17m52s Dec +38d55m47s',3,5,3),
    (19,'2025-06-30','RA 16h49m01s Dec -09d22m03s',1,6,4),
    (20,'2025-08-17','RA 07h12m28s Dec +29d41m16s',2,11,5),
    (21,'2025-10-04','RA 23h55m44s Dec -14d17m59s',4,17,6),
    (22,'2025-11-21','RA 12h28m36s Dec +03d08m44s',5,3,7),
    (23,'2026-01-08','RA 02h03m19s Dec -36d50m21s',6,22,8),
    (24,'2026-02-25','RA 19h41m07s Dec +21d22m55s',7,2,9),
    (25,'2026-04-14','RA 09h17m52s Dec -27d33m08s',8,25,10),
    (26,'2023-02-10','RA 04h55m41s Dec +45d11m29s',9,8,11),
    (27,'2023-06-05','RA 20h33m14s Dec -02d47m36s',10,9,12),
    (28,'2024-02-18','RA 14h09m28s Dec +18d04m12s',11,10,13),
    (29,'2024-07-14','RA 05h22m03s Dec -39d19m50s',12,11,14),
    (30,'2025-01-27','RA 21h48m55s Dec +12d36m41s',13,12,15),
    (31,'2025-09-09','RA 11h04m17s Dec -31d22m05s',14,13,1),
    (32,'2026-03-22','RA 00h39m46s Dec +34d58m17s',15,14,2),
    (33,'2023-09-28','RA 17h25m59s Dec -08d15m44s',16,15,3),
    (34,'2024-05-03','RA 08h51m22s Dec +26d47m33s',17,1,4),
    (35,'2025-04-11','RA 23h12m08s Dec -20d09m51s',18,2,5),
    (36,'2026-06-05','RA 13h37m44s Dec +05d44m22s',19,3,6),
    (37,'2023-12-19','RA 06h18m31s Dec -44d33m09s',20,4,7),
    (38,'2024-10-16','RA 19h03m55s Dec +15d21m47s',1,5,8),
    (39,'2025-07-02','RA 10h29m12s Dec -28d56m14s',2,6,9),
    (40,'2026-01-30','RA 01h54m47s Dec +39d08m36s',3,7,10),
    (41,'2023-05-17','RA 16h46m03s Dec -11d27m58s',4,8,11),
    (42,'2024-03-29','RA 07h59m21s Dec +22d19m05s',5,9,12),
    (43,'2025-02-14','RA 22h34m16s Dec -16d44m31s',6,10,13),
    (44,'2026-05-08','RA 12h11m39s Dec +07d52m44s',7,11,14),
    (45,'2023-08-11','RA 04h27m52s Dec -35d18m22s',8,12,15),
    (46,'2024-12-04','RA 20h18m07s Dec +30d41m59s',9,13,1),
    (47,'2025-10-20','RA 09h45m28s Dec -24d03m17s',10,14,2),
    (48,'2026-02-07','RA 00h22m14s Dec +41d16m38s',11,15,3),
    (49,'2023-11-25','RA 18h07m33s Dec -06d29m50s',12,1,4),
    (50,'2024-09-19','RA 13h52m41s Dec +14d37m12s',13,2,5),
]


def init_database():
    conn = get_connection(); c = conn.cursor()
    c.executescript(DDL); conn.commit()

    if c.execute("SELECT COUNT(*) FROM Users").fetchone()[0] == 0:
        c.executemany("INSERT OR IGNORE INTO Users VALUES (?,?,?)", [
            ('admin',      'admin123', 'Admin'),
            ('researcher', 'res123',   'Researcher'),
            ('guest',      'guest123', 'Public'),
        ])
        conn.commit()

    if c.execute("SELECT COUNT(*) FROM Observatories").fetchone()[0] == 0:
        c.executemany("INSERT OR IGNORE INTO Observatories VALUES (?,?,?,?,NULL,NULL)",
                      SEED_OBSERVATORIES)
        c.executemany("INSERT OR IGNORE INTO Telescopes VALUES (?,?,?,?,?,?)",
                      SEED_TELESCOPES)
        c.executemany("INSERT OR IGNORE INTO Scientists VALUES (?,?,?,?)",
                      SEED_SCIENTISTS)
        c.executemany("INSERT OR IGNORE INTO Risk_Category VALUES (?,?,?,?)",
                      SEED_RISK)
        c.executemany("INSERT OR IGNORE INTO Asteroids VALUES (?,?,?,?)",
                      SEED_ASTEROIDS)
        c.executemany("INSERT OR IGNORE INTO Missions VALUES (?,?,?,?)",
                      SEED_MISSIONS)
        c.executemany("INSERT OR IGNORE INTO Asteroid_Mission VALUES (?,?)",
                      SEED_AST_MISSION)
        c.executemany("INSERT OR IGNORE INTO Detection_Events VALUES (?,?,?,?,?,?)",
                      SEED_DETECTION_EVENTS)
        c.executemany("INSERT OR IGNORE INTO Observations VALUES (?,?,?,?,?,?)",
                      SEED_OBSERVATIONS)
        conn.commit()

    try:
        c.execute("ALTER TABLE Observatories ADD COLUMN Latitude REAL")
        c.execute("ALTER TABLE Observatories ADD COLUMN Longitude REAL")
        conn.commit()
    except Exception:
        pass

    _populate_observatory_coords(conn)
    conn.close()
    log("Database initialised (DBS project v4.1)")


def _populate_observatory_coords(conn):
    c = conn.cursor()
    for oid, (lat, lon) in OBSERVATORY_COORDS.items():
        c.execute("UPDATE Observatories SET Latitude=?, Longitude=? WHERE Observatory_ID=? AND Latitude IS NULL",
                  (lat, lon, oid))
    c.execute("UPDATE Observatories SET Latitude=ROUND(CAST((RANDOM()%90000)/1000.0 AS REAL),4), "
              "Longitude=ROUND(CAST((RANDOM()%360000-180000)/1000.0 AS REAL),4) "
              "WHERE Latitude IS NULL")
    conn.commit()


def authenticate(username: str, password: str):
    conn = get_connection()
    row = conn.execute("SELECT Role FROM Users WHERE Username=? AND Password=?",
                       (username, password)).fetchone()
    conn.close()
    return row["Role"] if row else None


# ═══════════════════════════════════════════════════════════
# 2.  COLOUR PALETTE & STYLE HELPERS
# ═══════════════════════════════════════════════════════════

BG_DEEP     = "#020B18"
BG_SPACE    = "#060F1E"
BG_PANEL    = "#0A1628"
BG_CONTENT  = "#0D1B2A"

NEON_BLUE   = "#38BDF8"
NEON_CYAN   = "#22D3EE"
NEON_GREEN  = "#4ADE80"
NEON_PURPLE = "#A78BFA"
NEON_AMBER  = "#FCD34D"
NEON_RED    = "#F87171"
NEON_ORANGE = "#FB923C"

TXT_PRIMARY  = "#E2E8F0"
TXT_MUTED    = "#64748B"
TXT_BRIGHT   = "#F0F9FF"
TXT_DIM      = "#334155"

ROW_BASE    = BG_PANEL
ROW_ALT     = "#0F2137"
ROW_HIGH    = "#1C1040"
ROW_CRIT    = "#280A0A"

SIDEBAR_BG  = BG_DEEP
SIDEBAR_FG  = TXT_PRIMARY
SIDEBAR_SEL = "#0F2748"
CONTENT_BG  = BG_CONTENT
CARD_BG     = BG_PANEL
ACCENT      = NEON_BLUE
ACCENT2     = NEON_GREEN
DANGER      = NEON_RED
WARN        = NEON_AMBER
MUTED       = TXT_MUTED
HEADER_FG   = TXT_BRIGHT

RISK_ROW_COLORS = {
    1: "#081a0e", 2: "#091d10", 3: "#0e2010", 4: "#1a2610",
    5: "#201e06", 6: "#261806", 7: "#2a1006", 8: "#2a0808",
    9: "#300505", 10:"#3a0202",
}

FONT_TITLE   = ("Segoe UI", 14, "bold")
FONT_HEADER  = ("Segoe UI", 11, "bold")
FONT_BODY    = ("Segoe UI", 10)
FONT_SMALL   = ("Segoe UI", 9)
FONT_MONO    = ("Consolas", 10)
FONT_LOGO    = ("Segoe UI", 15, "bold")


def apply_global_style():
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Space.Treeview",
                    background=ROW_BASE, foreground=TXT_PRIMARY,
                    rowheight=26, fieldbackground=ROW_BASE,
                    font=FONT_BODY, borderwidth=0)
    style.configure("Space.Treeview.Heading",
                    background=BG_DEEP, foreground=NEON_CYAN,
                    font=("Segoe UI", 10, "bold"), relief="flat", padding=(8, 5))
    style.map("Space.Treeview",
              background=[("selected", "#163356")],
              foreground=[("selected", NEON_CYAN)])


def center_window(win, w, h):
    win.update_idletasks()
    x = (win.winfo_screenwidth()  - w) // 2
    y = (win.winfo_screenheight() - h) // 2
    win.geometry(f"{w}x{h}+{x}+{y}")


def make_treeview(parent, columns, show="headings", height=14):
    frame = tk.Frame(parent, bg=CONTENT_BG)
    frame.pack(fill=tk.BOTH, expand=True)
    tv = ttk.Treeview(frame, columns=columns, show=show,
                      style="Space.Treeview", height=height)
    vsb = ttk.Scrollbar(frame, orient="vertical",   command=tv.yview)
    hsb = ttk.Scrollbar(frame, orient="horizontal", command=tv.xview)
    tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    hsb.pack(side=tk.BOTTOM, fill=tk.X)
    vsb.pack(side=tk.RIGHT,  fill=tk.Y)
    tv.pack(side=tk.LEFT,    fill=tk.BOTH, expand=True)
    tv.tag_configure("alt",       background=ROW_ALT,  foreground=TXT_PRIMARY)
    tv.tag_configure("high_risk", background=ROW_HIGH, foreground=NEON_AMBER)
    tv.tag_configure("crit_risk", background=ROW_CRIT, foreground=NEON_RED)
    return tv


def labeled_entry(parent, label, row, col=0, width=28):
    tk.Label(parent, text=label, bg=CARD_BG, fg=TXT_MUTED,
             font=FONT_SMALL, anchor="w").grid(row=row, column=col,
             sticky="w", padx=(8, 2), pady=3)
    var = tk.StringVar()
    e = tk.Entry(parent, textvariable=var, width=width, font=FONT_BODY,
                 bg=BG_SPACE, fg=TXT_PRIMARY, insertbackground=NEON_BLUE,
                 relief="flat", bd=1, highlightthickness=1,
                 highlightcolor=NEON_BLUE, highlightbackground=TXT_DIM)
    e.grid(row=row, column=col+1, sticky="ew", padx=(2, 8), pady=3)
    return var


def btn(parent, text, cmd, color=NEON_BLUE, fg=BG_DEEP, **kw):
    b = tk.Button(parent, text=text, command=cmd,
                  bg=color, fg=fg, font=FONT_BODY,
                  relief="flat", bd=0, cursor="hand2",
                  activebackground=_lighten(color), activeforeground=BG_DEEP,
                  padx=12, pady=5, **kw)
    b.bind("<Enter>", lambda e: b.config(bg=_lighten(color)))
    b.bind("<Leave>", lambda e: b.config(bg=color))
    return b


def _lighten(hex_color):
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        return "#{:02x}{:02x}{:02x}".format(min(255,r+40), min(255,g+40), min(255,b+40))
    except Exception:
        return hex_color


def section_divider(parent):
    tk.Frame(parent, bg=TXT_DIM, height=1).pack(fill=tk.X, padx=16, pady=3)


def validate_int(val, name, min_val=None):
    try:
        v = int(val)
        if min_val is not None and v < min_val:
            raise ValueError(f"{name} must be ≥ {min_val}")
        return v
    except (ValueError, TypeError):
        raise ValueError(f"{name} must be a valid integer")

def validate_float(val, name, min_val=None, max_val=None):
    try:
        v = float(val)
        if min_val is not None and v < min_val:
            raise ValueError(f"{name} must be ≥ {min_val}")
        if max_val is not None and v > max_val:
            raise ValueError(f"{name} must be ≤ {max_val}")
        return v
    except (ValueError, TypeError):
        raise ValueError(f"{name} must be a valid number")

def validate_date(val, name):
    if not val: return val
    try:
        datetime.datetime.strptime(val.strip(), "%Y-%m-%d"); return val.strip()
    except ValueError:
        raise ValueError(f"{name} must be YYYY-MM-DD format")


def check_risk_alert(root):
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.Name, rc.Category_Name, printf('%.6f', de.Probability), rc.Risk_ID
        FROM Detection_Events de
        JOIN Asteroids a      ON de.Asteroid_ID = a.Asteroid_ID
        JOIN Risk_Category rc ON de.Risk_ID     = rc.Risk_ID
        WHERE de.Risk_ID >= 5 ORDER BY de.Probability DESC LIMIT 6
    """).fetchall()
    conn.close()
    if not rows: return

    top = tk.Toplevel(root)
    top.title("⚠  Planetary Defence Alert")
    top.configure(bg=BG_DEEP)
    center_window(top, 520, 360)
    top.grab_set()

    hdr = tk.Frame(top, bg="#200000")
    hdr.pack(fill=tk.X)
    tk.Label(hdr, text="⚠  RISK DETECTION ALERT",
             bg="#200000", fg=NEON_RED,
             font=("Segoe UI", 14, "bold")).pack(pady=12)

    tk.Label(top, text="The following asteroids have elevated impact probability:",
             bg=BG_DEEP, fg=TXT_MUTED, font=FONT_SMALL).pack(pady=(4, 8))

    f = tk.Frame(top, bg=BG_DEEP)
    f.pack(fill=tk.X, padx=20)
    for i, r in enumerate(rows):
        risk_id = r[3]
        bg = ROW_CRIT if risk_id >= 8 else ROW_HIGH
        fg = NEON_RED if risk_id >= 8 else NEON_AMBER
        row_f = tk.Frame(f, bg=bg)
        row_f.pack(fill=tk.X, pady=1)
        tk.Label(row_f, text=f"  {r[0]}", bg=bg, fg=fg, font=FONT_BODY,
                 width=28, anchor="w").pack(side=tk.LEFT, padx=4, pady=3)
        tk.Label(row_f, text=r[1], bg=bg, fg=NEON_PURPLE, font=FONT_SMALL,
                 width=12).pack(side=tk.LEFT)
        tk.Label(row_f, text=f"P={r[2]}", bg=bg, fg=TXT_MUTED, font=FONT_SMALL,
                 width=16).pack(side=tk.LEFT)

    btn(top, "  Acknowledge  ", top.destroy, NEON_RED, BG_DEEP).pack(pady=16)
    log("Risk alert displayed")


# ═══════════════════════════════════════════════════════════
# 3.  LOGIN WINDOW
# ═══════════════════════════════════════════════════════════

class LoginWindow(tk.Toplevel):
    ROLE_COLORS = {
        'Admin':      NEON_RED,
        'Researcher': NEON_CYAN,
        'Public':     NEON_GREEN,
    }
    ROLE_ICONS = {'Admin': '🔴', 'Researcher': '🔵', 'Public': '🟢'}

    def __init__(self, master):
        super().__init__(master)
        self.result = None
        self.title("☄  Asteroid Tracker — Login")
        self.configure(bg=BG_DEEP)
        center_window(self, 440, 480)
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg="#070F1E", pady=20)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="☄", bg="#070F1E", fg=NEON_CYAN,
                 font=("Segoe UI", 36)).pack()
        tk.Label(hdr, text="Asteroid Detection & Tracking", bg="#070F1E",
                 fg=TXT_BRIGHT, font=("Segoe UI", 13, "bold")).pack()
        tk.Label(hdr, text="Database Systems Project · IV Semester", bg="#070F1E",
                 fg=TXT_MUTED, font=FONT_SMALL).pack()

        form = tk.Frame(self, bg=BG_PANEL, pady=24, padx=32)
        form.pack(fill=tk.BOTH, expand=True, padx=28, pady=20)

        tk.Label(form, text="Username", bg=BG_PANEL, fg=TXT_MUTED,
                 font=FONT_SMALL, anchor="w").pack(fill=tk.X, pady=(0, 2))
        self.user_var = tk.StringVar()
        uentry = tk.Entry(form, textvariable=self.user_var, font=FONT_BODY,
                          bg=BG_SPACE, fg=TXT_PRIMARY, insertbackground=NEON_BLUE,
                          relief="flat", highlightthickness=1,
                          highlightcolor=NEON_BLUE, highlightbackground=TXT_DIM)
        uentry.pack(fill=tk.X, ipady=6, pady=(0, 14))
        uentry.focus_set()

        tk.Label(form, text="Password", bg=BG_PANEL, fg=TXT_MUTED,
                 font=FONT_SMALL, anchor="w").pack(fill=tk.X, pady=(0, 2))
        self.pass_var = tk.StringVar()
        pw_frame = tk.Frame(form, bg=BG_PANEL)
        pw_frame.pack(fill=tk.X, pady=(0, 6))
        self._pentry = tk.Entry(pw_frame, textvariable=self.pass_var, show="●",
                          font=FONT_BODY, bg=BG_SPACE, fg=TXT_PRIMARY,
                          insertbackground=NEON_BLUE, relief="flat",
                          highlightthickness=1, highlightcolor=NEON_BLUE,
                          highlightbackground=TXT_DIM)
        self._pentry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        self._pentry.bind("<Return>", lambda e: self._login())
        self._show_pw = False
        self._eye_btn = tk.Button(
            pw_frame, text="👁", bg=BG_SPACE, fg=TXT_MUTED,
            font=("Segoe UI", 11), relief="flat", bd=0, cursor="hand2",
            activebackground=BG_SPACE, activeforeground=NEON_CYAN,
            command=self._toggle_password, padx=6
        )
        self._eye_btn.pack(side=tk.LEFT)

        self.err_lbl = tk.Label(form, text="", bg=BG_PANEL, fg=NEON_RED,
                                font=FONT_SMALL)
        self.err_lbl.pack(anchor="w", pady=(0, 10))

        login_btn = tk.Button(form, text="  🔓  Login  ", command=self._login,
                              bg=NEON_BLUE, fg=BG_DEEP, font=("Segoe UI", 11, "bold"),
                              relief="flat", bd=0, cursor="hand2",
                              activebackground=_lighten(NEON_BLUE),
                              activeforeground=BG_DEEP, pady=8)
        login_btn.pack(fill=tk.X, pady=(4, 0))

        hint_f = tk.Frame(self, bg=BG_DEEP)
        hint_f.pack(fill=tk.X, padx=28, pady=(0, 14))
        tk.Label(hint_f, text="Default accounts:", bg=BG_DEEP, fg=TXT_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        for uname, pw, role in [('admin','admin123','Admin'),
                                 ('researcher','res123','Researcher'),
                                 ('guest','guest123','Public')]:
            color = self.ROLE_COLORS[role]
            icon  = self.ROLE_ICONS[role]
            tk.Label(hint_f,
                     text=f"{icon}  {uname} / {pw}   [{role}]",
                     bg=BG_DEEP, fg=color, font=("Segoe UI", 8),
                     cursor="hand2").pack(anchor="w", pady=1)

    def _toggle_password(self):
        self._show_pw = not self._show_pw
        self._pentry.config(show="" if self._show_pw else "●")
        self._eye_btn.config(fg=NEON_CYAN if self._show_pw else TXT_MUTED)

    def _login(self):
        username = self.user_var.get().strip()
        password = self.pass_var.get()
        if not username or not password:
            self.err_lbl.config(text="⚠  Please enter username and password.")
            return
        role = authenticate(username, password)
        if role:
            global _CURRENT_USER
            _CURRENT_USER = username
            self.result = (username, role)
            log(f"Login: {username} ({role})")
            audit_log("LOGIN", "Users", username, f"Role={role}")
            self.destroy()
        else:
            self.err_lbl.config(text="✖  Invalid username or password.")
            self.pass_var.set("")
            log(f"Failed login attempt: {username}", "warning")

    def _cancel(self):
        self.result = None
        self.destroy()


# ═══════════════════════════════════════════════════════════
# 4.  ROLE-BASED ACCESS CONTROL
# ═══════════════════════════════════════════════════════════

RBAC_DISABLE = {
    'Researcher': ['🗑', 'Delete', 'Risk Rule'],
    'Public':     ['🗑', 'Delete', '➕', 'Add', '✏', 'Update',
                   'Link', 'Unlink', 'Execute', 'Risk Rule'],
}

def apply_rbac(widget, role: str):
    if role == 'Admin':
        return
    patterns = RBAC_DISABLE.get(role, [])
    _recurse_rbac(widget, patterns)

def _recurse_rbac(widget, patterns):
    if isinstance(widget, tk.Button):
        label = widget.cget("text")
        if any(p in label for p in patterns):
            widget.config(state="disabled", bg=TXT_DIM, fg=BG_DEEP,
                          cursor="arrow", activebackground=TXT_DIM)
    for child in widget.winfo_children():
        _recurse_rbac(child, patterns)


# ═══════════════════════════════════════════════════════════
# 5.  BASE TAB
# ═══════════════════════════════════════════════════════════

class BaseTab(tk.Frame):
    def __init__(self, parent, role="Admin"):
        super().__init__(parent, bg=CONTENT_BG)
        self.role = role

    def section_label(self, text, subtitle=""):
        hdr = tk.Frame(self, bg=CONTENT_BG)
        hdr.pack(fill=tk.X, padx=16, pady=(14, 2))
        tk.Label(hdr, text=text, bg=CONTENT_BG, fg=TXT_BRIGHT,
                 font=FONT_TITLE).pack(anchor="w")
        if subtitle:
            tk.Label(hdr, text=subtitle, bg=CONTENT_BG, fg=TXT_MUTED,
                     font=FONT_SMALL).pack(anchor="w")

    def divider(self):
        section_divider(self)

    def status(self, msg, color=NEON_GREEN):
        if hasattr(self, "_status_lbl"):
            self._status_lbl.config(text=msg, fg=color)
            self.after(3500, lambda: self._status_lbl.config(text=""))

    def _make_form(self, title):
        f = tk.LabelFrame(self, text=f"  {title}  ",
                          bg=CARD_BG, fg=NEON_CYAN,
                          font=FONT_HEADER, bd=1, relief="groove",
                          labelanchor="nw")
        f.pack(fill=tk.X, padx=16, pady=6)
        f.columnconfigure(1, weight=1); f.columnconfigure(3, weight=1)
        return f

    def apply_role_restrictions(self):
        apply_rbac(self, self.role)


# ═══════════════════════════════════════════════════════════
# 6.  DASHBOARD
# ═══════════════════════════════════════════════════════════

class DashboardTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role)
        self.app = app
        self._fig = None
        self._build()

    def _build(self):
        self.section_label("🌌  Mission Control — Dashboard",
                           "Database Systems Project · IV Semester")
        self.divider()

        cards_frame = tk.Frame(self, bg=CONTENT_BG)
        cards_frame.pack(fill=tk.X, padx=16, pady=10)
        self.stat_labels = {}
        card_defs = [
            ("asteroids",  "☄  Asteroids",    "#112240", NEON_CYAN),
            ("missions",   "🚀  Missions",      "#0f2218", NEON_GREEN),
            ("scientists", "👩‍🔬  Scientists",   "#1a1040", NEON_PURPLE),
            ("events",     "⚡  Detections",    "#1f1500", NEON_AMBER),
            ("obs",        "📡  Observations",  "#0a1a2a", NEON_BLUE),
        ]
        for col, (key, title, card_bg, accent) in enumerate(card_defs):
            card = tk.Frame(cards_frame, bg=card_bg, width=150, height=90,
                            relief="flat", bd=0)
            card.pack(side=tk.LEFT, padx=6, pady=4, ipadx=12, ipady=8)
            card.pack_propagate(False)
            tk.Label(card, text=title, bg=card_bg, fg=TXT_MUTED,
                     font=FONT_SMALL).pack(anchor="w", padx=8, pady=(8, 0))
            lbl = tk.Label(card, text="…", bg=card_bg, fg=accent,
                           font=("Segoe UI", 24, "bold"))
            lbl.pack(anchor="w", padx=10)
            self.stat_labels[key] = lbl

        self.divider()

        ins_frame = tk.LabelFrame(self, text="  🔬  Intelligence Panel  ",
                                  bg=CARD_BG, fg=NEON_CYAN,
                                  font=FONT_HEADER, bd=1, relief="groove")
        ins_frame.pack(fill=tk.X, padx=16, pady=4)
        self.insight_labels = {}
        ins_defs = [
            ("largest",       "🪐  Largest Asteroid",   NEON_PURPLE),
            ("highest_risk",  "⚠  Highest Risk",        NEON_RED),
            ("most_observed", "📡  Most Observed",       NEON_BLUE),
            ("top_sci",       "👩‍🔬  Top Scientist",       NEON_GREEN),
        ]
        for col, (key, title, color) in enumerate(ins_defs):
            f = tk.Frame(ins_frame, bg=CARD_BG)
            f.grid(row=0, column=col, padx=18, pady=10, sticky="w")
            tk.Label(f, text=title, bg=CARD_BG, fg=TXT_MUTED,
                     font=FONT_SMALL).pack(anchor="w")
            lbl = tk.Label(f, text="—", bg=CARD_BG, fg=color,
                           font=("Segoe UI", 11, "bold"), wraplength=190,
                           justify="left")
            lbl.pack(anchor="w")
            self.insight_labels[key] = lbl
        ins_frame.columnconfigure((0, 1, 2, 3), weight=1)

        self.divider()

        # ── High-Risk Alert Table (v3 feature restored) ───
        hdr_f = tk.Frame(self, bg=CONTENT_BG)
        hdr_f.pack(fill=tk.X, padx=16, pady=(6, 2))
        tk.Label(hdr_f, text="⚠  Active Threat Board  (Risk ≥ Moderate)",
                 bg=CONTENT_BG, fg=NEON_RED, font=FONT_HEADER).pack(side=tk.LEFT)
        alert_cols = ("Asteroid", "Probability", "Risk Level", "Detection Date", "Scientist")
        self.alert_tv = make_treeview(self, alert_cols, height=5)
        for c, w in zip(alert_cols, (220, 120, 120, 130, 220)):
            self.alert_tv.heading(c, text=c)
            self.alert_tv.column(c, width=w, anchor="center")

        self.divider()

        self.chart_frame = tk.Frame(self, bg=BG_DEEP)
        self.chart_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        bf = tk.Frame(self, bg=CONTENT_BG)
        bf.pack(anchor="w", padx=16, pady=6)
        btn(bf, "🔄  Refresh", self.refresh, NEON_BLUE).pack(side=tk.LEFT, padx=4)
        btn(bf, "⚠  Show Alert Popup",
            lambda: check_risk_alert(self.winfo_toplevel()),
            NEON_RED).pack(side=tk.LEFT, padx=4)

        self.refresh()

    def refresh(self):
        conn = get_connection(); c = conn.cursor()

        for key, table in [("asteroids","Asteroids"),("missions","Missions"),
                            ("scientists","Scientists"),("events","Detection_Events"),
                            ("obs","Observations")]:
            n = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            self.stat_labels[key].config(text=str(n))

        r = c.execute("SELECT Name, Diameter FROM Asteroids ORDER BY Diameter DESC LIMIT 1").fetchone()
        self.insight_labels["largest"].config(text=f"{r[0]}\n{r[1]} km" if r else "—")

        r = c.execute("""SELECT a.Name, rc.Category_Name FROM Detection_Events de
                         JOIN Asteroids a ON de.Asteroid_ID=a.Asteroid_ID
                         JOIN Risk_Category rc ON de.Risk_ID=rc.Risk_ID
                         ORDER BY de.Risk_ID DESC LIMIT 1""").fetchone()
        self.insight_labels["highest_risk"].config(text=f"{r[0]}\n{r[1]}" if r else "—")

        r = c.execute("""SELECT a.Name, COUNT(*) cnt FROM Observations o
                         JOIN Asteroids a ON o.Asteroid_ID=a.Asteroid_ID
                         GROUP BY a.Name ORDER BY cnt DESC LIMIT 1""").fetchone()
        self.insight_labels["most_observed"].config(
            text=f"{r[0]}\n{r[1]} observations" if r else "—")

        r = c.execute("""SELECT s.Name, COUNT(*) cnt FROM Detection_Events de
                         JOIN Scientists s ON de.Scientist_ID=s.Scientist_ID
                         GROUP BY s.Name ORDER BY cnt DESC LIMIT 1""").fetchone()
        self.insight_labels["top_sci"].config(text=f"{r[0]}\n{r[1]} events" if r else "—")

        # Populate active threat board
        alert_rows = c.execute("""
            SELECT a.Name, printf('%.6f',de.Probability),
                   rc.Category_Name, de.Detection_Date, s.Name, de.Risk_ID
            FROM Detection_Events de
            JOIN Asteroids a      ON de.Asteroid_ID  = a.Asteroid_ID
            JOIN Risk_Category rc ON de.Risk_ID      = rc.Risk_ID
            JOIN Scientists s     ON de.Scientist_ID = s.Scientist_ID
            WHERE rc.Risk_ID >= 5 ORDER BY de.Probability DESC
        """).fetchall()
        self.alert_tv.delete(*self.alert_tv.get_children())
        for i, row in enumerate(alert_rows):
            rid = row[5]
            tag = "crit_risk" if rid >= 8 else "high_risk"
            self.alert_tv.insert("", tk.END, values=list(row[:5]), tags=(tag,))

        conn.close()
        self._redraw_charts()
        log("Dashboard refreshed")

    _DARK = {
        "figure.facecolor": "#030D1A", "axes.facecolor":  "#070F1E",
        "axes.edgecolor":   "#1E3A5F", "axes.labelcolor": "#94A3B8",
        "axes.titlecolor":  NEON_CYAN,  "text.color":      "#94A3B8",
        "xtick.color":      "#64748B",  "ytick.color":     "#64748B",
        "grid.color":       "#0F2137",  "grid.linestyle":  "--",
        "grid.alpha":       0.5,
    }

    def _redraw_charts(self):
        if not MATPLOTLIB_OK:
            return
        for w in self.chart_frame.winfo_children():
            w.destroy()
        if self._fig:
            try: plt.close(self._fig)
            except Exception: pass

        conn = get_connection()
        with plt.rc_context(self._DARK):
            fig, axes = plt.subplots(1, 3, figsize=(14, 3.6))
            fig.patch.set_facecolor("#030D1A")
            self._fig = fig

            PALETTE = [NEON_CYAN, NEON_GREEN, NEON_AMBER, NEON_PURPLE,
                       NEON_BLUE, NEON_RED, NEON_ORANGE, "#E879F9",
                       "#34D399", "#60A5FA"]

            ax = axes[0]
            rows = conn.execute("""SELECT rc.Category_Name, COUNT(*) FROM Detection_Events de
                JOIN Risk_Category rc ON de.Risk_ID=rc.Risk_ID
                GROUP BY rc.Category_Name ORDER BY rc.Risk_ID""").fetchall()
            if rows:
                wedges, texts, autotexts = ax.pie(
                    [r[1] for r in rows], labels=[r[0] for r in rows],
                    autopct="%1.0f%%", colors=PALETTE[:len(rows)],
                    startangle=140, pctdistance=0.80,
                    wedgeprops=dict(edgecolor="#030D1A", linewidth=1.2))
                for t in texts: t.set_fontsize(6); t.set_color("#94A3B8")
                for t in autotexts: t.set_fontsize(6); t.set_color("#030D1A")
            ax.set_title("Risk Distribution", fontsize=9, fontweight="bold", color=NEON_CYAN)

            ax = axes[1]
            rows = conn.execute("""SELECT Agency, COUNT(*) cnt FROM Missions
                WHERE Agency IS NOT NULL GROUP BY Agency
                ORDER BY cnt DESC LIMIT 8""").fetchall()
            if rows:
                agencies = [r[0] for r in rows]
                counts   = [r[1] for r in rows]
                bars = ax.barh(agencies, counts, color=NEON_GREEN, alpha=0.85)
                ax.invert_yaxis()
                ax.set_xlabel("Missions", fontsize=7)
                ax.grid(axis="x", alpha=0.4)
                for bar in bars:
                    ax.annotate(f"{int(bar.get_width())}",
                                xy=(bar.get_width(), bar.get_y()+bar.get_height()/2),
                                xytext=(3, 0), textcoords="offset points",
                                va="center", fontsize=6, color=NEON_GREEN)
                ax.tick_params(labelsize=6)
            ax.set_title("Missions per Agency", fontsize=9, fontweight="bold", color=NEON_CYAN)

            ax = axes[2]
            rows = conn.execute("""SELECT Diameter, Orbital_Period FROM Asteroids
                WHERE Diameter IS NOT NULL AND Orbital_Period IS NOT NULL
                AND Orbital_Period < 500""").fetchall()
            if rows:
                xs = [r[0] for r in rows]
                ys = [r[1] for r in rows]
                sc = ax.scatter(xs, ys, c=xs, cmap="plasma", s=40, alpha=0.8,
                                edgecolors="#030D1A", linewidths=0.4)
                ax.set_xlabel("Diameter (km)", fontsize=7)
                ax.set_ylabel("Orbital Period (yr)", fontsize=7)
                ax.grid(alpha=0.3)
                ax.tick_params(labelsize=6)
            ax.set_title("Diameter vs Orbital Period", fontsize=9, fontweight="bold", color=NEON_CYAN)

            conn.close()
            plt.tight_layout(pad=1.2)

            canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)


# ═══════════════════════════════════════════════════════════
# 7.  GLOBAL SEARCH
# ═══════════════════════════════════════════════════════════

class GlobalSearchTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role)
        self.app = app; self._build()

    def _build(self):
        self.section_label("🔎  Global Search",
                           "Search across asteroids, missions, scientists and observatories")
        self.divider()
        top = tk.Frame(self, bg=CONTENT_BG)
        top.pack(fill=tk.X, padx=16, pady=8)
        tk.Label(top, text="Search:", bg=CONTENT_BG,
                 fg=TXT_MUTED, font=FONT_BODY).pack(side=tk.LEFT)
        self.sv = tk.StringVar()
        e = tk.Entry(top, textvariable=self.sv, width=44,
                     font=FONT_BODY, bg=BG_PANEL, fg=TXT_PRIMARY,
                     insertbackground=NEON_BLUE, relief="flat",
                     highlightthickness=1, highlightcolor=NEON_BLUE,
                     highlightbackground=TXT_DIM)
        e.pack(side=tk.LEFT, padx=8, ipady=4)
        e.bind("<Return>", lambda ev: self._search())
        btn(top, "🔍  Search", self._search, NEON_BLUE).pack(side=tk.LEFT, padx=4)
        btn(top, "Clear", self._clear, MUTED).pack(side=tk.LEFT, padx=4)
        self._status_lbl = tk.Label(self, text="", bg=CONTENT_BG,
                                    fg=NEON_GREEN, font=FONT_SMALL)
        self._status_lbl.pack(anchor="w", padx=16, pady=2)
        cols = ("Type", "ID", "Name / Details", "Extra")
        self.tv = make_treeview(self, cols, height=16)
        for c, w in zip(cols, (120, 60, 380, 300)):
            self.tv.heading(c, text=c); self.tv.column(c, width=w, anchor="w")
        self.tv.bind("<Double-1>", self._on_double)

    def _search(self):
        kw = self.sv.get().strip()
        if not kw: return
        q = f"%{kw}%"
        conn = get_connection(); results = []
        for row in conn.execute("SELECT Asteroid_ID,Name,Diameter,Orbital_Period FROM Asteroids WHERE Name LIKE ?", (q,)):
            results.append(("☄  Asteroid", row[0], row[1], f"Ø={row[2]} km  T={row[3]} yr"))
        for row in conn.execute("SELECT Mission_ID,Mission_Name,Agency,Launch_Date FROM Missions WHERE Mission_Name LIKE ? OR Agency LIKE ?", (q,q)):
            results.append(("🚀  Mission", row[0], row[1], f"{row[2]}  ({row[3]})"))
        for row in conn.execute("SELECT Scientist_ID,Name,Specialization,Experience_Years FROM Scientists WHERE Name LIKE ? OR Specialization LIKE ?", (q,q)):
            results.append(("👩‍🔬  Scientist", row[0], row[1], f"{row[2]}  ({row[3]} yrs)"))
        for row in conn.execute("SELECT Observatory_ID,Name,Country,Established_Year FROM Observatories WHERE Name LIKE ? OR Country LIKE ?", (q,q)):
            results.append(("🏛  Observatory", row[0], row[1], f"{row[2]}  est.{row[3]}"))
        conn.close()
        self.tv.delete(*self.tv.get_children())
        for i, r in enumerate(results):
            self.tv.insert("", tk.END, values=r, tags=("alt" if i % 2 else "",))
        self.status(f"✔  {len(results)} result(s) for '{kw}'")

    def _clear(self):
        self.sv.set(""); self.tv.delete(*self.tv.get_children()); self.status("")

    def _on_double(self, event):
        sel = self.tv.focus()
        if not sel: return
        vals = self.tv.item(sel, "values")
        if vals and "Asteroid" in vals[0]:
            self.app.show_asteroid_detail(int(vals[1]))


# ═══════════════════════════════════════════════════════════
# 8.  ASTEROIDS TAB
# ═══════════════════════════════════════════════════════════

class AsteroidsTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role)
        self.app = app; self._build()
        self.apply_role_restrictions()

    def _build(self):
        self.section_label("☄  Asteroids",
                           "Manage asteroid catalogue — double-click to Fly-To on map")
        self.divider()
        form = self._make_form("Add / Edit Asteroid")
        self.v_id    = labeled_entry(form, "Asteroid ID *",       0, 0)
        self.v_name  = labeled_entry(form, "Name *",              0, 2, 34)
        self.v_diam  = labeled_entry(form, "Diameter (km > 0)",   1, 0)
        self.v_orbit = labeled_entry(form, "Orbital Period (yr)", 1, 2)
        bf = tk.Frame(form, bg=CARD_BG)
        bf.grid(row=2, column=0, columnspan=4, pady=6, padx=8, sticky="w")
        btn(bf, "➕  Add",     self._add,    NEON_GREEN).pack(side=tk.LEFT, padx=4)
        btn(bf, "✏  Update",  self._update, NEON_BLUE).pack(side=tk.LEFT, padx=4)
        btn(bf, "🗑  Delete",  self._delete, NEON_RED).pack(side=tk.LEFT, padx=4)
        btn(bf, "🔍  Details", self._detail, NEON_PURPLE).pack(side=tk.LEFT, padx=4)
        btn(bf, "🗺  Fly-To Map", self._fly_to_map, NEON_CYAN).pack(side=tk.LEFT, padx=4)
        btn(bf, "🧹  Clear",  self._clear,  MUTED).pack(side=tk.LEFT, padx=4)
        sf = tk.Frame(self, bg=CONTENT_BG)
        sf.pack(fill=tk.X, padx=16, pady=4)
        tk.Label(sf, text="Search:", bg=CONTENT_BG, fg=TXT_MUTED, font=FONT_BODY).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._load())
        tk.Entry(sf, textvariable=self.search_var, width=32, font=FONT_BODY,
                 bg=BG_PANEL, fg=TXT_PRIMARY, insertbackground=NEON_BLUE,
                 relief="flat", highlightthickness=1, highlightcolor=NEON_BLUE,
                 highlightbackground=TXT_DIM).pack(side=tk.LEFT, padx=6, ipady=3)
        self._status_lbl = tk.Label(self, text="", bg=CONTENT_BG,
                                    fg=NEON_GREEN, font=FONT_SMALL)
        self._status_lbl.pack(anchor="w", padx=16)
        cols = ("ID", "Name", "Diameter (km)", "Orbital Period (yr)")
        self.tv = make_treeview(self, cols)
        for c, w in zip(cols, (80, 300, 130, 160)):
            self.tv.heading(c, text=c, command=lambda col=c: self._sort(col))
            self.tv.column(c, width=w, anchor="center")
        self.tv.bind("<<TreeviewSelect>>", self._on_select)
        self.tv.bind("<Double-1>", self._on_double_click)
        self._load()

    def _load(self):
        kw = f"%{self.search_var.get()}%"
        conn = get_connection()
        rows = conn.execute(
            "SELECT Asteroid_ID,Name,Diameter,Orbital_Period FROM Asteroids "
            "WHERE Name LIKE ? ORDER BY Asteroid_ID", (kw,)).fetchall()
        conn.close()
        self.tv.delete(*self.tv.get_children())
        for i, r in enumerate(rows):
            self.tv.insert("", tk.END, iid=str(r[0]), values=list(r),
                           tags=("alt" if i % 2 else "",))

    def _on_select(self, _=None):
        sel = self.tv.focus()
        if not sel: return
        v = self.tv.item(sel, "values")
        self.v_id.set(v[0]); self.v_name.set(v[1])
        self.v_diam.set(v[2]); self.v_orbit.set(v[3])

    def _on_double_click(self, event):
        """Double-click: open details OR fly-to map depending on column."""
        self._fly_to_map()

    def _fly_to_map(self):
        """Switch to map tab and fly to the observatory that first observed this asteroid."""
        try:
            aid = validate_int(self.v_id.get(), "ID", 1)
        except ValueError:
            messagebox.showinfo("Select", "Select an asteroid first")
            return
        # Find observatory that has observed this asteroid (via telescope link)
        conn = get_connection()
        row = conn.execute("""
            SELECT ob.Observatory_ID, ob.Name, ob.Latitude, ob.Longitude
            FROM Observations o
            JOIN Telescopes t    ON o.Telescope_ID = t.Telescope_ID
            JOIN Observatories ob ON t.Observatory_ID = ob.Observatory_ID
            WHERE o.Asteroid_ID = ?
              AND ob.Latitude IS NOT NULL AND ob.Longitude IS NOT NULL
            LIMIT 1
        """, (aid,)).fetchone()
        conn.close()

        if not row:
            messagebox.showinfo("Fly-To",
                "No observatory with coordinates found for this asteroid.\n"
                "Switching to Map tab.")
            self.app.show("map")
            return

        obs_id, obs_name, lat, lon = row[0], row[1], row[2], row[3]
        # Switch to map and fly there
        self.app.show("map")
        map_tab = self.app.pages.get("map")
        if map_tab:
            map_tab.fly_to(lat, lon, zoom=12, label=f"🎯 Target: {obs_name}")
        self.status(f"🗺  Flying to {obs_name}", NEON_CYAN)

    def _validate(self):
        aid  = validate_int(self.v_id.get(), "Asteroid ID", 1)
        name = self.v_name.get().strip()
        if not name: raise ValueError("Name is required")
        d = validate_float(self.v_diam.get(), "Diameter", 0) if self.v_diam.get() else None
        o = validate_float(self.v_orbit.get(), "Orbital Period", 0) if self.v_orbit.get() else None
        return aid, name, d, o

    def _add(self):
        try: aid, name, d, o = self._validate()
        except ValueError as e: messagebox.showerror("Validation Error", str(e)); return
        conn = get_connection()
        try:
            conn.execute("INSERT INTO Asteroids VALUES (?,?,?,?)", (aid, name, d, o))
            conn.commit()
            audit_log("INSERT", "Asteroids", aid, f"Name={name}, Diameter={d}, OrbPeriod={o}")
            self.status(f"✔  Asteroid '{name}' added")
            self._clear(); self._load(); self.app.refresh_dashboard()
        except sqlite3.IntegrityError as e: messagebox.showerror("DB Error", str(e))
        finally: conn.close()

    def _update(self):
        try: aid, name, d, o = self._validate()
        except ValueError as e: messagebox.showerror("Validation Error", str(e)); return
        conn = get_connection()
        conn.execute("UPDATE Asteroids SET Name=?,Diameter=?,Orbital_Period=? WHERE Asteroid_ID=?",
                     (name, d, o, aid))
        conn.commit(); conn.close()
        audit_log("UPDATE", "Asteroids", aid, f"Name={name}, Diameter={d}, OrbPeriod={o}")
        self.status(f"✔  Asteroid {aid} updated")
        self._load(); self.app.refresh_dashboard()

    def _delete(self):
        try: aid = validate_int(self.v_id.get(), "Asteroid ID", 1)
        except ValueError as e: messagebox.showerror("Error", str(e)); return
        if not messagebox.askyesno("Confirm Delete",
                                   f"Delete Asteroid ID {aid}?\nAll linked data will be removed."): return
        conn = get_connection()
        conn.execute("DELETE FROM Asteroids WHERE Asteroid_ID=?", (aid,))
        conn.commit(); conn.close()
        self.status(f"🗑  Asteroid {aid} deleted", NEON_RED)
        self._clear(); self._load(); self.app.refresh_dashboard()

    def _detail(self):
        try: aid = validate_int(self.v_id.get(), "ID", 1)
        except ValueError: messagebox.showinfo("Select", "Select an asteroid first"); return
        self.app.show_asteroid_detail(aid)

    def _clear(self):
        for v in (self.v_id, self.v_name, self.v_diam, self.v_orbit): v.set("")

    def _sort(self, col):
        data = [(self.tv.set(k, col), k) for k in self.tv.get_children("")]
        try:   data.sort(key=lambda x: float(x[0]))
        except ValueError: data.sort()
        for i, (_, k) in enumerate(data):
            self.tv.move(k, "", i)
            self.tv.item(k, tags=("alt",) if i % 2 else ())


def show_asteroid_detail(root, asteroid_id):
    conn = get_connection()
    ast = conn.execute("SELECT * FROM Asteroids WHERE Asteroid_ID=?", (asteroid_id,)).fetchone()
    if not ast: conn.close(); messagebox.showinfo("Not found", f"Asteroid {asteroid_id} not found."); return
    missions    = conn.execute("""SELECT m.Mission_Name,m.Agency,m.Launch_Date
        FROM Asteroid_Mission am JOIN Missions m ON am.Mission_ID=m.Mission_ID
        WHERE am.Asteroid_ID=?""", (asteroid_id,)).fetchall()
    detections  = conn.execute("""SELECT de.Detection_Date,printf('%.6f',de.Probability),
        rc.Category_Name,s.Name FROM Detection_Events de
        JOIN Risk_Category rc ON de.Risk_ID=rc.Risk_ID
        JOIN Scientists s ON de.Scientist_ID=s.Scientist_ID
        WHERE de.Asteroid_ID=? ORDER BY de.Detection_Date""", (asteroid_id,)).fetchall()
    observations = conn.execute("""SELECT o.Observation_Date,o.Position,t.Name,s.Name
        FROM Observations o LEFT JOIN Telescopes t ON o.Telescope_ID=t.Telescope_ID
        LEFT JOIN Scientists s ON o.Scientist_ID=s.Scientist_ID
        WHERE o.Asteroid_ID=? ORDER BY o.Observation_Date""", (asteroid_id,)).fetchall()
    conn.close()
    top = tk.Toplevel(root)
    top.title(f"☄  {ast[1]}")
    top.configure(bg=BG_DEEP)
    center_window(top, 720, 560)
    top.grab_set()
    hdr = tk.Frame(top, bg=BG_PANEL); hdr.pack(fill=tk.X)
    tk.Label(hdr, text=f"☄  {ast[1]}", bg=BG_PANEL, fg=NEON_CYAN,
             font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=16, pady=(12, 2))
    tk.Label(hdr, text=f"Diameter: {ast[2]} km   ·   Orbital Period: {ast[3]} yr",
             bg=BG_PANEL, fg=TXT_MUTED, font=FONT_BODY).pack(anchor="w", padx=16, pady=(0, 10))
    nb = ttk.Notebook(top); nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)
    for title, data, cols in [
        ("🚀  Missions",     missions,     ("Mission", "Agency", "Launch Date")),
        ("⚡  Detections",   detections,   ("Date", "Probability", "Risk", "Scientist")),
        ("📡  Observations", observations, ("Date", "Position", "Telescope", "Scientist")),
    ]:
        f = tk.Frame(nb, bg=CONTENT_BG); nb.add(f, text=title)
        tv = make_treeview(f, cols, height=10)
        for c in cols: tv.heading(c, text=c); tv.column(c, width=172, anchor="center")
        for i, row in enumerate(data):
            tv.insert("", tk.END, values=list(row), tags=("alt" if i % 2 else "",))
    btn(top, "  Close  ", top.destroy, MUTED, TXT_PRIMARY).pack(pady=8)


# ═══════════════════════════════════════════════════════════
# 9.  OBSERVATORIES TAB
# ═══════════════════════════════════════════════════════════

class ObservatoriesTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role); self.app = app; self._build()
        self.apply_role_restrictions()

    def _build(self):
        self.section_label("🏛  Observatories",
                           "Includes real-world latitude / longitude coordinates")
        self.divider()
        form = self._make_form("Add / Edit Observatory")
        self.v_id      = labeled_entry(form, "Observatory ID *", 0, 0)
        self.v_name    = labeled_entry(form, "Name *",           0, 2, 34)
        self.v_country = labeled_entry(form, "Country *",        1, 0)
        self.v_year    = labeled_entry(form, "Est. Year",        1, 2)
        self.v_lat     = labeled_entry(form, "Latitude",         2, 0)
        self.v_lon     = labeled_entry(form, "Longitude",        2, 2)
        bf = tk.Frame(form, bg=CARD_BG)
        bf.grid(row=3, column=0, columnspan=4, pady=6, padx=8, sticky="w")
        btn(bf, "➕  Add",    self._add,    NEON_GREEN).pack(side=tk.LEFT, padx=4)
        btn(bf, "✏  Update", self._update, NEON_BLUE).pack(side=tk.LEFT, padx=4)
        btn(bf, "🗑  Delete", self._delete, NEON_RED).pack(side=tk.LEFT, padx=4)
        btn(bf, "🧹  Clear",  self._clear,  MUTED).pack(side=tk.LEFT, padx=4)
        self._status_lbl = tk.Label(self, text="", bg=CONTENT_BG, fg=NEON_GREEN, font=FONT_SMALL)
        self._status_lbl.pack(anchor="w", padx=16)
        cols = ("ID", "Name", "Country", "Est. Year", "Latitude", "Longitude")
        self.tv = make_treeview(self, cols)
        for c, w in zip(cols, (50, 280, 140, 80, 90, 90)):
            self.tv.heading(c, text=c); self.tv.column(c, width=w, anchor="center")
        self.tv.bind("<<TreeviewSelect>>", self._on_select)
        self._load()

    def _load(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT Observatory_ID,Name,Country,Established_Year,Latitude,Longitude "
            "FROM Observatories ORDER BY Observatory_ID").fetchall()
        conn.close()
        self.tv.delete(*self.tv.get_children())
        for i, r in enumerate(rows):
            self.tv.insert("", "end", iid=str(r[0]), values=list(r),
                           tags=("alt" if i % 2 else "",))

    def _on_select(self, _=None):
        sel = self.tv.focus()
        if not sel: return
        v = self.tv.item(sel, "values")
        self.v_id.set(v[0]); self.v_name.set(v[1]); self.v_country.set(v[2])
        self.v_year.set(v[3]); self.v_lat.set(v[4]); self.v_lon.set(v[5])

    def _add(self):
        try:
            oid  = validate_int(self.v_id.get(), "Observatory ID", 1)
            name = self.v_name.get().strip()
            ctry = self.v_country.get().strip()
            if not name or not ctry: raise ValueError("Name and Country required")
            yr  = validate_int(self.v_year.get(), "Year") if self.v_year.get() else None
            lat = validate_float(self.v_lat.get(), "Latitude", -90, 90) if self.v_lat.get() else None
            lon = validate_float(self.v_lon.get(), "Longitude", -180, 180) if self.v_lon.get() else None
        except ValueError as e: messagebox.showerror("Validation Error", str(e)); return
        conn = get_connection()
        try:
            conn.execute("INSERT INTO Observatories VALUES (?,?,?,?,?,?)",
                         (oid, name, ctry, yr, lat, lon))
            conn.commit()
            audit_log("INSERT", "Observatories", oid, f"Name={name}, Country={ctry}")
            self.status(f"✔  Observatory '{name}' added")
            self._clear(); self._load()
        except sqlite3.IntegrityError as e: messagebox.showerror("DB Error", str(e))
        finally: conn.close()

    def _update(self):
        try:
            oid = validate_int(self.v_id.get(), "ID", 1)
            yr  = validate_int(self.v_year.get(), "Year") if self.v_year.get() else None
            lat = validate_float(self.v_lat.get(), "Latitude", -90, 90) if self.v_lat.get() else None
            lon = validate_float(self.v_lon.get(), "Longitude", -180, 180) if self.v_lon.get() else None
        except ValueError as e: messagebox.showerror("Validation Error", str(e)); return
        conn = get_connection()
        conn.execute("UPDATE Observatories SET Name=?,Country=?,Established_Year=?,Latitude=?,Longitude=? WHERE Observatory_ID=?",
                     (self.v_name.get(), self.v_country.get(), yr, lat, lon, oid))
        conn.commit(); conn.close()
        audit_log("UPDATE", "Observatories", oid, f"Name={self.v_name.get()}")
        self.status("✔  Updated"); self._load()

    def _delete(self):
        try: oid = validate_int(self.v_id.get(), "ID", 1)
        except ValueError as e: messagebox.showerror("Error", str(e)); return
        if not messagebox.askyesno("Confirm", f"Delete Observatory {oid}?"): return
        conn = get_connection()
        conn.execute("DELETE FROM Observatories WHERE Observatory_ID=?", (oid,))
        conn.commit(); conn.close()
        audit_log("DELETE", "Observatories", oid)
        self.status("🗑  Deleted", NEON_RED); self._clear(); self._load()

    def _clear(self):
        for v in (self.v_id, self.v_name, self.v_country, self.v_year, self.v_lat, self.v_lon):
            v.set("")


# ═══════════════════════════════════════════════════════════
# 10.  TELESCOPES TAB
# ═══════════════════════════════════════════════════════════

class TelescopesTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role); self.app = app; self._build()
        self.apply_role_restrictions()

    def _build(self):
        self.section_label("🔭  Telescopes"); self.divider()
        form = self._make_form("Add / Edit Telescope")
        self.v_id   = labeled_entry(form, "Telescope ID *",    0, 0)
        self.v_name = labeled_entry(form, "Name *",            0, 2, 34)
        self.v_loc  = labeled_entry(form, "Location",          1, 0)
        self.v_type = labeled_entry(form, "Type",              1, 2)
        self.v_apt  = labeled_entry(form, "Aperture (m > 0)",  2, 0)
        self.v_obs  = labeled_entry(form, "Observatory ID",    2, 2)
        bf = tk.Frame(form, bg=CARD_BG); bf.grid(row=3, column=0, columnspan=4, pady=6, padx=8, sticky="w")
        btn(bf, "➕  Add",    self._add,    NEON_GREEN).pack(side=tk.LEFT, padx=4)
        btn(bf, "✏  Update", self._update, NEON_BLUE).pack(side=tk.LEFT, padx=4)
        btn(bf, "🗑  Delete", self._delete, NEON_RED).pack(side=tk.LEFT, padx=4)
        btn(bf, "🧹  Clear",  self._clear,  MUTED).pack(side=tk.LEFT, padx=4)
        self._status_lbl = tk.Label(self, text="", bg=CONTENT_BG, fg=NEON_GREEN, font=FONT_SMALL)
        self._status_lbl.pack(anchor="w", padx=16)
        cols = ("ID","Name","Location","Type","Aperture (m)","Obs ID")
        self.tv = make_treeview(self, cols)
        for c, w in zip(cols, (60, 260, 130, 90, 100, 80)):
            self.tv.heading(c, text=c); self.tv.column(c, width=w, anchor="center")
        self.tv.bind("<<TreeviewSelect>>", self._on_select); self._load()

    def _load(self):
        conn = get_connection()
        rows = conn.execute("SELECT Telescope_ID,Name,Location,Type,Aperture_Size,Observatory_ID FROM Telescopes ORDER BY Telescope_ID").fetchall()
        conn.close()
        self.tv.delete(*self.tv.get_children())
        for i, r in enumerate(rows):
            self.tv.insert("", "end", iid=str(r[0]), values=list(r), tags=("alt" if i % 2 else "",))

    def _on_select(self, _=None):
        sel = self.tv.focus()
        if not sel: return
        v = self.tv.item(sel, "values")
        self.v_id.set(v[0]); self.v_name.set(v[1]); self.v_loc.set(v[2])
        self.v_type.set(v[3]); self.v_apt.set(v[4]); self.v_obs.set(v[5])

    def _add(self):
        try:
            tid  = validate_int(self.v_id.get(), "Telescope ID", 1)
            name = self.v_name.get().strip()
            if not name: raise ValueError("Name required")
            apt = validate_float(self.v_apt.get(), "Aperture", 0) if self.v_apt.get() else None
            obs = validate_int(self.v_obs.get(), "Observatory ID", 1) if self.v_obs.get() else None
        except ValueError as e: messagebox.showerror("Validation Error", str(e)); return
        conn = get_connection()
        try:
            conn.execute("INSERT INTO Telescopes VALUES (?,?,?,?,?,?)",
                         (tid, name, self.v_loc.get(), self.v_type.get(), apt, obs))
            conn.commit()
            audit_log("INSERT", "Telescopes", tid, f"Name={name}")
            self.status(f"✔  Telescope '{name}' added")
            self._clear(); self._load()
        except sqlite3.IntegrityError as e: messagebox.showerror("DB Error", str(e))
        finally: conn.close()

    def _update(self):
        try:
            tid = validate_int(self.v_id.get(), "ID", 1)
            apt = validate_float(self.v_apt.get(), "Aperture", 0) if self.v_apt.get() else None
            obs = validate_int(self.v_obs.get(), "Obs ID", 1) if self.v_obs.get() else None
        except ValueError as e: messagebox.showerror("Error", str(e)); return
        conn = get_connection()
        conn.execute("UPDATE Telescopes SET Name=?,Location=?,Type=?,Aperture_Size=?,Observatory_ID=? WHERE Telescope_ID=?",
                     (self.v_name.get(), self.v_loc.get(), self.v_type.get(), apt, obs, tid))
        conn.commit(); conn.close()
        audit_log("UPDATE", "Telescopes", tid, f"Name={self.v_name.get()}")
        self.status("✔  Updated"); self._load()

    def _delete(self):
        try: tid = validate_int(self.v_id.get(), "ID", 1)
        except ValueError as e: messagebox.showerror("Error", str(e)); return
        if not messagebox.askyesno("Confirm", f"Delete Telescope {tid}?"): return
        conn = get_connection()
        conn.execute("DELETE FROM Telescopes WHERE Telescope_ID=?", (tid,))
        conn.commit(); conn.close()
        audit_log("DELETE", "Telescopes", tid)
        self.status("🗑  Deleted", NEON_RED)
        self._clear(); self._load()

    def _clear(self):
        for v in (self.v_id, self.v_name, self.v_loc, self.v_type, self.v_apt, self.v_obs): v.set("")


# ═══════════════════════════════════════════════════════════
# 11.  SCIENTISTS TAB
# ═══════════════════════════════════════════════════════════

class ScientistsTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role); self.app = app; self._build()
        self.apply_role_restrictions()

    def _build(self):
        self.section_label("👩‍🔬  Scientists"); self.divider()
        form = self._make_form("Add / Edit Scientist")
        self.v_id   = labeled_entry(form, "Scientist ID *",        0, 0)
        self.v_name = labeled_entry(form, "Name *",                0, 2, 34)
        self.v_spec = labeled_entry(form, "Specialization",        1, 0)
        self.v_exp  = labeled_entry(form, "Experience (yrs ≥ 0)",  1, 2)
        bf = tk.Frame(form, bg=CARD_BG); bf.grid(row=2, column=0, columnspan=4, pady=6, padx=8, sticky="w")
        btn(bf, "➕  Add",    self._add,    NEON_GREEN).pack(side=tk.LEFT, padx=4)
        btn(bf, "✏  Update", self._update, NEON_BLUE).pack(side=tk.LEFT, padx=4)
        btn(bf, "🗑  Delete", self._delete, NEON_RED).pack(side=tk.LEFT, padx=4)
        btn(bf, "🧹  Clear",  self._clear,  MUTED).pack(side=tk.LEFT, padx=4)
        self._status_lbl = tk.Label(self, text="", bg=CONTENT_BG, fg=NEON_GREEN, font=FONT_SMALL)
        self._status_lbl.pack(anchor="w", padx=16)
        cols = ("ID","Name","Specialization","Exp (yrs)")
        self.tv = make_treeview(self, cols)
        for c, w in zip(cols, (60, 200, 330, 100)):
            self.tv.heading(c, text=c); self.tv.column(c, width=w, anchor="center")
        self.tv.bind("<<TreeviewSelect>>", self._on_select); self._load()

    def _load(self):
        conn = get_connection()
        rows = conn.execute("SELECT Scientist_ID,Name,Specialization,Experience_Years FROM Scientists ORDER BY Scientist_ID").fetchall()
        conn.close()
        self.tv.delete(*self.tv.get_children())
        for i, r in enumerate(rows):
            self.tv.insert("", "end", iid=str(r[0]), values=list(r), tags=("alt" if i % 2 else "",))

    def _on_select(self, _=None):
        sel = self.tv.focus()
        if not sel: return
        v = self.tv.item(sel, "values")
        self.v_id.set(v[0]); self.v_name.set(v[1]); self.v_spec.set(v[2]); self.v_exp.set(v[3])

    def _add(self):
        try:
            sid  = validate_int(self.v_id.get(), "Scientist ID", 1)
            name = self.v_name.get().strip()
            if not name: raise ValueError("Name required")
            exp = validate_int(self.v_exp.get(), "Experience", 0) if self.v_exp.get() else None
        except ValueError as e: messagebox.showerror("Validation Error", str(e)); return
        conn = get_connection()
        try:
            conn.execute("INSERT INTO Scientists VALUES (?,?,?,?)", (sid, name, self.v_spec.get(), exp))
            conn.commit()
            audit_log("INSERT", "Scientists", sid, f"Name={name}")
            self.status(f"✔  Scientist '{name}' added")
            self._clear(); self._load(); self.app.refresh_dashboard()
        except sqlite3.IntegrityError as e: messagebox.showerror("DB Error", str(e))
        finally: conn.close()

    def _update(self):
        try:
            sid = validate_int(self.v_id.get(), "ID", 1)
            exp = validate_int(self.v_exp.get(), "Experience", 0) if self.v_exp.get() else None
        except ValueError as e: messagebox.showerror("Error", str(e)); return
        conn = get_connection()
        conn.execute("UPDATE Scientists SET Name=?,Specialization=?,Experience_Years=? WHERE Scientist_ID=?",
                     (self.v_name.get(), self.v_spec.get(), exp, sid))
        conn.commit(); conn.close()
        audit_log("UPDATE", "Scientists", sid, f"Name={self.v_name.get()}")
        self.status("✔  Updated"); self._load()

    def _delete(self):
        try: sid = validate_int(self.v_id.get(), "ID", 1)
        except ValueError as e: messagebox.showerror("Error", str(e)); return
        if not messagebox.askyesno("Confirm", f"Delete Scientist {sid}?"): return
        conn = get_connection()
        conn.execute("DELETE FROM Scientists WHERE Scientist_ID=?", (sid,))
        conn.commit(); conn.close()
        audit_log("DELETE", "Scientists", sid)
        self.status("🗑  Deleted", NEON_RED)
        self._clear(); self._load(); self.app.refresh_dashboard()

    def _clear(self):
        for v in (self.v_id, self.v_name, self.v_spec, self.v_exp): v.set("")


# ═══════════════════════════════════════════════════════════
# 12.  MISSIONS TAB
# ═══════════════════════════════════════════════════════════

class MissionsTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role); self.app = app; self._build()
        self.apply_role_restrictions()

    def _build(self):
        self.section_label("🚀  Missions"); self.divider()
        form = self._make_form("Add / Edit Mission")
        self.v_id     = labeled_entry(form, "Mission ID *",               0, 0)
        self.v_name   = labeled_entry(form, "Mission Name *",             0, 2, 34)
        self.v_launch = labeled_entry(form, "Launch Date (YYYY-MM-DD)",   1, 0)
        self.v_agency = labeled_entry(form, "Agency",                     1, 2)
        bf = tk.Frame(form, bg=CARD_BG); bf.grid(row=2, column=0, columnspan=4, pady=6, padx=8, sticky="w")
        btn(bf, "➕  Add",    self._add,    NEON_GREEN).pack(side=tk.LEFT, padx=4)
        btn(bf, "✏  Update", self._update, NEON_BLUE).pack(side=tk.LEFT, padx=4)
        btn(bf, "🗑  Delete", self._delete, NEON_RED).pack(side=tk.LEFT, padx=4)
        btn(bf, "🧹  Clear",  self._clear,  MUTED).pack(side=tk.LEFT, padx=4)
        self._status_lbl = tk.Label(self, text="", bg=CONTENT_BG, fg=NEON_GREEN, font=FONT_SMALL)
        self._status_lbl.pack(anchor="w", padx=16)
        cols = ("ID","Mission Name","Launch Date","Agency")
        self.tv = make_treeview(self, cols)
        for c, w in zip(cols, (60, 320, 120, 200)):
            self.tv.heading(c, text=c); self.tv.column(c, width=w, anchor="center")
        self.tv.bind("<<TreeviewSelect>>", self._on_select); self._load()

    def _load(self):
        conn = get_connection()
        rows = conn.execute("SELECT Mission_ID,Mission_Name,Launch_Date,Agency FROM Missions ORDER BY Mission_ID").fetchall()
        conn.close()
        self.tv.delete(*self.tv.get_children())
        for i, r in enumerate(rows):
            self.tv.insert("", "end", iid=str(r[0]), values=list(r), tags=("alt" if i % 2 else "",))

    def _on_select(self, _=None):
        sel = self.tv.focus()
        if not sel: return
        v = self.tv.item(sel, "values")
        self.v_id.set(v[0]); self.v_name.set(v[1]); self.v_launch.set(v[2]); self.v_agency.set(v[3])

    def _add(self):
        try:
            mid    = validate_int(self.v_id.get(), "Mission ID", 1)
            name   = self.v_name.get().strip()
            if not name: raise ValueError("Mission Name required")
            launch = validate_date(self.v_launch.get(), "Launch Date") if self.v_launch.get() else None
        except ValueError as e: messagebox.showerror("Validation Error", str(e)); return
        conn = get_connection()
        try:
            conn.execute("INSERT INTO Missions VALUES (?,?,?,?)",
                         (mid, name, launch, self.v_agency.get() or None))
            conn.commit()
            audit_log("INSERT", "Missions", mid, f"Name={name}, Agency={self.v_agency.get()}")
            self.status(f"✔  Mission '{name}' added")
            self._clear(); self._load(); self.app.refresh_dashboard()
        except sqlite3.IntegrityError as e: messagebox.showerror("DB Error", str(e))
        finally: conn.close()

    def _update(self):
        try:
            mid    = validate_int(self.v_id.get(), "ID", 1)
            launch = validate_date(self.v_launch.get(), "Launch Date") if self.v_launch.get() else None
        except ValueError as e: messagebox.showerror("Error", str(e)); return
        conn = get_connection()
        conn.execute("UPDATE Missions SET Mission_Name=?,Launch_Date=?,Agency=? WHERE Mission_ID=?",
                     (self.v_name.get(), launch, self.v_agency.get() or None, mid))
        conn.commit(); conn.close()
        audit_log("UPDATE", "Missions", mid, f"Name={self.v_name.get()}")
        self.status("✔  Updated"); self._load()

    def _delete(self):
        try: mid = validate_int(self.v_id.get(), "ID", 1)
        except ValueError as e: messagebox.showerror("Error", str(e)); return
        if not messagebox.askyesno("Confirm", f"Delete Mission {mid}?"): return
        conn = get_connection()
        conn.execute("DELETE FROM Missions WHERE Mission_ID=?", (mid,))
        conn.commit(); conn.close()
        audit_log("DELETE", "Missions", mid)
        self.status("🗑  Deleted", NEON_RED)
        self._clear(); self._load(); self.app.refresh_dashboard()

    def _clear(self):
        for v in (self.v_id, self.v_name, self.v_launch, self.v_agency): v.set("")


# ═══════════════════════════════════════════════════════════
# 13.  DETECTION EVENTS TAB
# ═══════════════════════════════════════════════════════════

class DetectionEventsTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role); self.app = app; self._build()
        self.apply_role_restrictions()

    def _build(self):
        self.section_label("⚡  Detection Events",
                           "Probability auto-maps to Risk Category · Smart alerts active")
        self.divider()
        form = self._make_form("Add / Edit Detection Event")
        self.v_eid   = labeled_entry(form, "Event ID *",                   0, 0)
        self.v_astid = labeled_entry(form, "Asteroid ID *",                0, 2)
        self.v_date  = labeled_entry(form, "Detection Date (YYYY-MM-DD) *",1, 0)
        self.v_prob  = labeled_entry(form, "Probability (0 – 1) *",        1, 2)
        self.v_risk  = labeled_entry(form, "Risk ID (auto-filled)",         2, 0)
        self.v_sci   = labeled_entry(form, "Scientist ID",                  2, 2)
        self.v_prob.trace_add("write", self._auto_risk)
        bf = tk.Frame(form, bg=CARD_BG); bf.grid(row=3, column=0, columnspan=4, pady=6, padx=8, sticky="w")
        btn(bf, "➕  Add",    self._add,    NEON_GREEN).pack(side=tk.LEFT, padx=4)
        btn(bf, "✏  Update", self._update, NEON_BLUE).pack(side=tk.LEFT, padx=4)
        btn(bf, "🗑  Delete", self._delete, NEON_RED).pack(side=tk.LEFT, padx=4)
        btn(bf, "🧹  Clear",  self._clear,  MUTED).pack(side=tk.LEFT, padx=4)
        self._status_lbl = tk.Label(self, text="", bg=CONTENT_BG, fg=NEON_GREEN, font=FONT_SMALL)
        self._status_lbl.pack(anchor="w", padx=16)
        cols = ("Event ID","Asteroid","Detection Date","Probability","Risk Level","Scientist")
        self.tv = make_treeview(self, cols, height=10)
        for c, w in zip(cols, (80, 200, 130, 110, 120, 200)):
            self.tv.heading(c, text=c); self.tv.column(c, width=w, anchor="center")
        self.tv.bind("<<TreeviewSelect>>", self._on_select); self._load()

    def _auto_risk(self, *_):
        try:
            prob = float(self.v_prob.get())
            rid  = probability_to_risk_id(prob)
            self.v_risk.set(str(rid))
        except (ValueError, TypeError):
            pass

    def _load(self):
        conn = get_connection()
        rows = conn.execute("""
            SELECT de.Event_ID,a.Name,de.Detection_Date,
                   printf('%.6f',de.Probability),rc.Category_Name,s.Name
            FROM Detection_Events de
            LEFT JOIN Asteroids a      ON de.Asteroid_ID=a.Asteroid_ID
            LEFT JOIN Risk_Category rc ON de.Risk_ID=rc.Risk_ID
            LEFT JOIN Scientists s     ON de.Scientist_ID=s.Scientist_ID
            ORDER BY de.Event_ID""").fetchall()
        risk_map = {r[0]: r[1] for r in conn.execute(
            "SELECT Event_ID,Risk_ID FROM Detection_Events").fetchall()}
        conn.close()
        self.tv.delete(*self.tv.get_children())
        for i, r in enumerate(rows):
            rid = risk_map.get(r[0], 0) or 0
            tag = "crit_risk" if rid >= 9 else ("high_risk" if rid >= 7 else ("alt" if i % 2 else ""))
            self.tv.insert("", "end", iid=str(r[0]), values=list(r), tags=(tag,))

    def _on_select(self, _=None):
        sel = self.tv.focus()
        if not sel: return
        conn = get_connection()
        r = conn.execute("SELECT * FROM Detection_Events WHERE Event_ID=?", (sel,)).fetchone()
        conn.close()
        if r:
            self.v_eid.set(r[0]); self.v_astid.set(r[1]); self.v_date.set(r[2])
            self.v_prob.set(r[3]); self.v_risk.set(r[4] or ""); self.v_sci.set(r[5] or "")

    def _add(self):
        try:
            eid  = validate_int(self.v_eid.get(), "Event ID", 1)
            aid  = validate_int(self.v_astid.get(), "Asteroid ID", 1)
            prob = validate_float(self.v_prob.get(), "Probability", 0, 1)
            date = validate_date(self.v_date.get(), "Detection Date")
            if not date: raise ValueError("Detection Date required")
            risk = probability_to_risk_id(prob)
            self.v_risk.set(str(risk))
            sci  = validate_int(self.v_sci.get(), "Scientist ID", 1) if self.v_sci.get() else None
        except ValueError as e: messagebox.showerror("Validation Error", str(e)); return

        conn = get_connection()
        try:
            conn.execute("INSERT INTO Detection_Events VALUES (?,?,?,?,?,?)",
                         (eid, aid, date, prob, risk, sci))
            conn.commit()

            if prob > 0.7:
                messagebox.showwarning(
                    "🔴  RED ALERT",
                    f"HIGH-RISK OBJECT DETECTED!\n\n"
                    f"Probability: {prob:.4f}  (Risk Level: {risk}/10)\n\n"
                    "Immediate tracking and assessment required.\n"
                    "Notify Planetary Defense Coordination Office.")
                log(f"RED ALERT: event={eid}, asteroid={aid}, prob={prob:.4f}", "warning")

            elif risk >= 5:
                aname = conn.execute("SELECT Name FROM Asteroids WHERE Asteroid_ID=?", (aid,)).fetchone()
                messagebox.showwarning("⚠  Risk Alert",
                    f"Elevated-risk detection recorded for\n"
                    f"'{aname[0] if aname else aid}'\n\n"
                    f"Risk Level: {risk}/10  ·  Probability: {prob:.6f}")

            if risk >= 7:
                linked = conn.execute(
                    "SELECT COUNT(*) FROM Asteroid_Mission WHERE Asteroid_ID=?", (aid,)
                ).fetchone()[0]
                if linked == 0:
                    aname = conn.execute("SELECT Name FROM Asteroids WHERE Asteroid_ID=?", (aid,)).fetchone()
                    want_link = messagebox.askyesno(
                        "🚀  Mission Required",
                        f"This is a high-risk object with NO assigned mission!\n\n"
                        f"Asteroid: {aname[0] if aname else aid}\n"
                        f"Risk Level: {risk}/10\n\n"
                        "Would you like to link a mission now?")
                    if want_link:
                        conn.close()
                        self.app.show("links")
                        self.app.pages["links"].v_ast.set(str(aid))
                        self.status(f"✔  Event {eid} added — navigate to Links tab", NEON_AMBER)
                        self._clear(); self._load(); self.app.refresh_dashboard()
                        return

            self.status(f"✔  Event {eid} added")
            log(f"Detection event added: {eid}")
            audit_log("INSERT", "Detection_Events", eid, f"AsteroidID={aid}, Prob={prob:.6f}, Risk={risk}")
            self._clear(); self._load(); self.app.refresh_dashboard()

        except sqlite3.IntegrityError as e:
            messagebox.showerror("DB Error", str(e))
        finally:
            try: conn.close()
            except Exception: pass

    def _update(self):
        try:
            eid  = validate_int(self.v_eid.get(), "Event ID", 1)
            aid  = validate_int(self.v_astid.get(), "Asteroid ID", 1)
            prob = validate_float(self.v_prob.get(), "Probability", 0, 1)
            date = validate_date(self.v_date.get(), "Detection Date")
            risk = probability_to_risk_id(prob)
            sci  = validate_int(self.v_sci.get(), "Scientist ID", 1) if self.v_sci.get() else None
        except ValueError as e: messagebox.showerror("Error", str(e)); return
        conn = get_connection()
        conn.execute("UPDATE Detection_Events SET Asteroid_ID=?,Detection_Date=?,Probability=?,Risk_ID=?,Scientist_ID=? WHERE Event_ID=?",
                     (aid, date, prob, risk, sci, eid))
        conn.commit(); conn.close()
        audit_log("UPDATE", "Detection_Events", eid, f"Prob={prob:.6f}, Risk={risk}")
        self.status("✔  Updated"); self._load(); self.app.refresh_dashboard()

    def _delete(self):
        try: eid = validate_int(self.v_eid.get(), "Event ID", 1)
        except ValueError as e: messagebox.showerror("Error", str(e)); return
        if not messagebox.askyesno("Confirm", f"Delete Event {eid}?"): return
        conn = get_connection()
        conn.execute("DELETE FROM Detection_Events WHERE Event_ID=?", (eid,))
        conn.commit(); conn.close()
        audit_log("DELETE", "Detection_Events", eid)
        self.status("🗑  Deleted", NEON_RED)
        self._clear(); self._load(); self.app.refresh_dashboard()

    def _clear(self):
        for v in (self.v_eid, self.v_astid, self.v_date, self.v_prob, self.v_risk, self.v_sci): v.set("")


# ═══════════════════════════════════════════════════════════
# 14.  OBSERVATIONS TAB
# ═══════════════════════════════════════════════════════════

class ObservationsTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role); self.app = app; self._build()
        self.apply_role_restrictions()

    def _build(self):
        self.section_label("📡  Observations"); self.divider()
        form = self._make_form("Add / Edit Observation")
        self.v_oid  = labeled_entry(form, "Obs ID *",              0, 0)
        self.v_date = labeled_entry(form, "Date (YYYY-MM-DD) *",   0, 2)
        self.v_pos  = labeled_entry(form, "Position (RA / Dec)",   1, 0, 36)
        self.v_ast  = labeled_entry(form, "Asteroid ID",           2, 0)
        self.v_tel  = labeled_entry(form, "Telescope ID",          2, 2)
        self.v_sci  = labeled_entry(form, "Scientist ID",          3, 0)
        bf = tk.Frame(form, bg=CARD_BG); bf.grid(row=4, column=0, columnspan=4, pady=6, padx=8, sticky="w")
        btn(bf, "➕  Add",    self._add,    NEON_GREEN).pack(side=tk.LEFT, padx=4)
        btn(bf, "✏  Update", self._update, NEON_BLUE).pack(side=tk.LEFT, padx=4)
        btn(bf, "🗑  Delete", self._delete, NEON_RED).pack(side=tk.LEFT, padx=4)
        btn(bf, "🧹  Clear",  self._clear,  MUTED).pack(side=tk.LEFT, padx=4)
        self._status_lbl = tk.Label(self, text="", bg=CONTENT_BG, fg=NEON_GREEN, font=FONT_SMALL)
        self._status_lbl.pack(anchor="w", padx=16)
        cols = ("Obs ID","Date","Position","Asteroid","Telescope","Scientist")
        self.tv = make_treeview(self, cols, height=9)
        for c, w in zip(cols, (70, 110, 220, 180, 200, 180)):
            self.tv.heading(c, text=c); self.tv.column(c, width=w, anchor="center")
        self.tv.bind("<<TreeviewSelect>>", self._on_select); self._load()

    def _load(self):
        conn = get_connection()
        rows = conn.execute("""SELECT o.Observation_ID,o.Observation_Date,o.Position,
            a.Name,t.Name,s.Name FROM Observations o
            LEFT JOIN Asteroids a  ON o.Asteroid_ID=a.Asteroid_ID
            LEFT JOIN Telescopes t ON o.Telescope_ID=t.Telescope_ID
            LEFT JOIN Scientists s ON o.Scientist_ID=s.Scientist_ID
            ORDER BY o.Observation_ID""").fetchall()
        conn.close()
        self.tv.delete(*self.tv.get_children())
        for i, r in enumerate(rows):
            self.tv.insert("", "end", iid=str(r[0]), values=list(r), tags=("alt" if i % 2 else "",))

    def _on_select(self, _=None):
        sel = self.tv.focus()
        if not sel: return
        conn = get_connection()
        r = conn.execute("SELECT * FROM Observations WHERE Observation_ID=?", (sel,)).fetchone()
        conn.close()
        if r:
            self.v_oid.set(r[0]); self.v_date.set(r[1]); self.v_pos.set(r[2] or "")
            self.v_ast.set(r[3] or ""); self.v_tel.set(r[4] or ""); self.v_sci.set(r[5] or "")

    def _add(self):
        try:
            oid  = validate_int(self.v_oid.get(), "Obs ID", 1)
            date = validate_date(self.v_date.get(), "Date")
            if not date: raise ValueError("Date required")
            ast = validate_int(self.v_ast.get(), "Asteroid ID", 1) if self.v_ast.get() else None
            tel = validate_int(self.v_tel.get(), "Telescope ID", 1) if self.v_tel.get() else None
            sci = validate_int(self.v_sci.get(), "Scientist ID", 1) if self.v_sci.get() else None
        except ValueError as e: messagebox.showerror("Validation Error", str(e)); return
        conn = get_connection()
        try:
            conn.execute("INSERT INTO Observations VALUES (?,?,?,?,?,?)",
                         (oid, date, self.v_pos.get() or None, ast, tel, sci))
            conn.commit()
            audit_log("INSERT", "Observations", oid, f"Date={date}, AsteroidID={ast}")
            self.status(f"✔  Observation {oid} added")
            self._clear(); self._load(); self.app.refresh_dashboard()
        except sqlite3.IntegrityError as e: messagebox.showerror("DB Error", str(e))
        finally: conn.close()

    def _update(self):
        try:
            oid  = validate_int(self.v_oid.get(), "Obs ID", 1)
            date = validate_date(self.v_date.get(), "Date")
            ast  = validate_int(self.v_ast.get(), "Asteroid ID", 1) if self.v_ast.get() else None
            tel  = validate_int(self.v_tel.get(), "Telescope ID", 1) if self.v_tel.get() else None
            sci  = validate_int(self.v_sci.get(), "Scientist ID", 1) if self.v_sci.get() else None
        except ValueError as e: messagebox.showerror("Error", str(e)); return
        conn = get_connection()
        conn.execute("UPDATE Observations SET Observation_Date=?,Position=?,Asteroid_ID=?,Telescope_ID=?,Scientist_ID=? WHERE Observation_ID=?",
                     (date, self.v_pos.get() or None, ast, tel, sci, oid))
        conn.commit(); conn.close()
        audit_log("UPDATE", "Observations", oid, f"Date={date}")
        self.status("✔  Updated")
        self._load(); self.app.refresh_dashboard()

    def _delete(self):
        try: oid = validate_int(self.v_oid.get(), "Obs ID", 1)
        except ValueError as e: messagebox.showerror("Error", str(e)); return
        if not messagebox.askyesno("Confirm", f"Delete Observation {oid}?"): return
        conn = get_connection()
        conn.execute("DELETE FROM Observations WHERE Observation_ID=?", (oid,))
        conn.commit(); conn.close()
        audit_log("DELETE", "Observations", oid)
        self.status("🗑  Deleted", NEON_RED)
        self._clear(); self._load(); self.app.refresh_dashboard()

    def _clear(self):
        for v in (self.v_oid, self.v_date, self.v_pos, self.v_ast, self.v_tel, self.v_sci): v.set("")


# ═══════════════════════════════════════════════════════════
# 15.  ASTEROID–MISSION LINKS
# ═══════════════════════════════════════════════════════════

class AstMissionTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role); self.app = app; self._build()
        self.apply_role_restrictions()

    def _build(self):
        self.section_label("🔗  Asteroid – Mission Links"); self.divider()
        form = self._make_form("Link / Unlink")
        self.v_ast = labeled_entry(form, "Asteroid ID *", 0, 0)
        self.v_mis = labeled_entry(form, "Mission ID *",  0, 2)
        bf = tk.Frame(form, bg=CARD_BG); bf.grid(row=1, column=0, columnspan=4, pady=6, padx=8, sticky="w")
        btn(bf, "🔗  Link",   self._link,   NEON_GREEN).pack(side=tk.LEFT, padx=4)
        btn(bf, "🔓  Unlink", self._unlink, NEON_RED).pack(side=tk.LEFT, padx=4)
        self._status_lbl = tk.Label(self, text="", bg=CONTENT_BG, fg=NEON_GREEN, font=FONT_SMALL)
        self._status_lbl.pack(anchor="w", padx=16)
        cols = ("Asteroid","Diameter (km)","Mission","Agency","Launch Date")
        self.tv = make_treeview(self, cols, height=12)
        for c, w in zip(cols, (200, 110, 280, 200, 110)):
            self.tv.heading(c, text=c); self.tv.column(c, width=w, anchor="center")
        self._load()

    def _load(self):
        conn = get_connection()
        rows = conn.execute("""SELECT a.Name,a.Diameter,m.Mission_Name,m.Agency,m.Launch_Date
            FROM Asteroid_Mission am JOIN Asteroids a ON am.Asteroid_ID=a.Asteroid_ID
            JOIN Missions m ON am.Mission_ID=m.Mission_ID ORDER BY a.Name""").fetchall()
        conn.close()
        self.tv.delete(*self.tv.get_children())
        for i, r in enumerate(rows):
            self.tv.insert("", tk.END, values=list(r), tags=("alt" if i % 2 else "",))

    def _link(self):
        try:
            aid = validate_int(self.v_ast.get(), "Asteroid ID", 1)
            mid = validate_int(self.v_mis.get(), "Mission ID", 1)
        except ValueError as e: messagebox.showerror("Error", str(e)); return
        conn = get_connection()
        try:
            conn.execute("INSERT OR IGNORE INTO Asteroid_Mission VALUES (?,?)", (aid, mid))
            conn.commit()
            audit_log("LINK", "Asteroid_Mission", f"{aid}-{mid}", f"Asteroid={aid}, Mission={mid}")
            self.status(f"✔  Linked  Asteroid {aid} ↔ Mission {mid}")
            self._load()
        except Exception as e: messagebox.showerror("DB Error", str(e))
        finally: conn.close()

    def _unlink(self):
        try:
            aid = validate_int(self.v_ast.get(), "Asteroid ID", 1)
            mid = validate_int(self.v_mis.get(), "Mission ID", 1)
        except ValueError as e: messagebox.showerror("Error", str(e)); return
        conn = get_connection()
        conn.execute("DELETE FROM Asteroid_Mission WHERE Asteroid_ID=? AND Mission_ID=?", (aid, mid))
        conn.commit(); conn.close()
        audit_log("UNLINK", "Asteroid_Mission", f"{aid}-{mid}", f"Asteroid={aid}, Mission={mid}")
        self.status("🔓  Unlinked", NEON_RED); self._load()


# ═══════════════════════════════════════════════════════════
# 16.  RISK CATEGORY TAB
# ═══════════════════════════════════════════════════════════

class RiskTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role); self.app = app; self._build()

    def _build(self):
        self.section_label("🎯  Risk Categories",
                           "Torino Impact Hazard Scale levels 0–10"); self.divider()
        cols = ("Risk ID","Category","Probability Range","Description")
        self.tv = make_treeview(self, cols, height=12)
        for c, w in zip(cols, (80, 120, 180, 520)):
            self.tv.heading(c, text=c); self.tv.column(c, width=w, anchor="w")
        self._load()

    def _load(self):
        conn = get_connection()
        rows = conn.execute("SELECT Risk_ID,Category_Name,Probability_Range,Description FROM Risk_Category ORDER BY Risk_ID").fetchall()
        conn.close()
        self.tv.delete(*self.tv.get_children())
        for r in rows:
            rid = r[0]; tag = f"risk{rid}"
            self.tv.tag_configure(tag,
                background=RISK_ROW_COLORS.get(rid, ROW_BASE),
                foreground=(NEON_RED if rid >= 8 else NEON_AMBER if rid >= 5 else NEON_GREEN))
            self.tv.insert("", "end", values=list(r), tags=(tag,))


# ═══════════════════════════════════════════════════════════
# 17.  ANALYTICAL QUERIES
# ═══════════════════════════════════════════════════════════

QUERIES = {
    "Q1 – High-Risk Asteroids (≥ Moderate)": """
        SELECT a.Name, printf('%.6f',de.Probability), rc.Category_Name,
               de.Detection_Date, s.Name
        FROM Detection_Events de
        JOIN Asteroids a      ON de.Asteroid_ID=a.Asteroid_ID
        JOIN Risk_Category rc ON de.Risk_ID=rc.Risk_ID
        JOIN Scientists s     ON de.Scientist_ID=s.Scientist_ID
        WHERE rc.Risk_ID>=5 ORDER BY de.Probability DESC""",
    "Q2 – Total Observations per Telescope": """
        SELECT t.Name,ob.Name,ob.Country,COUNT(o.Observation_ID) Total
        FROM Telescopes t JOIN Observatories ob ON t.Observatory_ID=ob.Observatory_ID
        LEFT JOIN Observations o ON t.Telescope_ID=o.Telescope_ID
        GROUP BY t.Name ORDER BY Total DESC""",
    "Q3 – Above-Average Impact Probability": """
        SELECT a.Name, printf('%.6f',de.Probability), rc.Category_Name
        FROM Detection_Events de JOIN Asteroids a ON de.Asteroid_ID=a.Asteroid_ID
        JOIN Risk_Category rc ON de.Risk_ID=rc.Risk_ID
        WHERE de.Probability>(SELECT AVG(Probability) FROM Detection_Events)
        ORDER BY de.Probability DESC""",
    "Q4 – Avg Probability per Risk Category": """
        SELECT rc.Category_Name, printf('%.6f',AVG(de.Probability)), COUNT(*)
        FROM Detection_Events de JOIN Risk_Category rc ON de.Risk_ID=rc.Risk_ID
        GROUP BY rc.Category_Name ORDER BY AVG(de.Probability) DESC""",
    "Q5 – Asteroids and Their Missions": """
        SELECT a.Name,a.Diameter,m.Mission_Name,m.Agency,m.Launch_Date
        FROM Asteroids a JOIN Asteroid_Mission am ON a.Asteroid_ID=am.Asteroid_ID
        JOIN Missions m ON am.Mission_ID=m.Mission_ID ORDER BY a.Name""",
    "Q6 – Scientists with Most Observations": """
        SELECT s.Name,s.Specialization,COUNT(DISTINCT o.Asteroid_ID)
        FROM Scientists s JOIN Observations o ON s.Scientist_ID=o.Scientist_ID
        GROUP BY s.Name ORDER BY 3 DESC""",
    "Q7 – Asteroids with No Detection Event": """
        SELECT a.Asteroid_ID,a.Name,a.Diameter,a.Orbital_Period
        FROM Asteroids a LEFT JOIN Detection_Events de ON a.Asteroid_ID=de.Asteroid_ID
        WHERE de.Event_ID IS NULL ORDER BY a.Asteroid_ID""",
    "Q8 – Most Experienced Scientist per Risk Category": """
        SELECT rc.Category_Name,s.Name,s.Experience_Years,printf('%.6f',de.Probability)
        FROM Detection_Events de JOIN Scientists s ON de.Scientist_ID=s.Scientist_ID
        JOIN Risk_Category rc ON de.Risk_ID=rc.Risk_ID
        WHERE s.Experience_Years=(SELECT MAX(s2.Experience_Years) FROM Detection_Events de2
            JOIN Scientists s2 ON de2.Scientist_ID=s2.Scientist_ID WHERE de2.Risk_ID=de.Risk_ID)
        ORDER BY rc.Risk_ID""",
    "Q9 – High Risk Summary View": """
        SELECT a.Name,a.Diameter,printf('%.6f',de.Probability),de.Detection_Date,
               s.Name,rc.Category_Name,rc.Description
        FROM Detection_Events de JOIN Asteroids a ON de.Asteroid_ID=a.Asteroid_ID
        JOIN Scientists s ON de.Scientist_ID=s.Scientist_ID
        JOIN Risk_Category rc ON de.Risk_ID=rc.Risk_ID WHERE rc.Risk_ID>=5
        ORDER BY de.Probability DESC""",
    "Q10 – Observations per Country (Chain)": """
        SELECT ob.Country,ob.Latitude,ob.Longitude,COUNT(o.Observation_ID),COUNT(DISTINCT o.Asteroid_ID)
        FROM Observations o JOIN Telescopes t ON o.Telescope_ID=t.Telescope_ID
        JOIN Observatories ob ON t.Observatory_ID=ob.Observatory_ID
        GROUP BY ob.Country ORDER BY 4 DESC""",
}


class QueriesTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role); self.app = app; self._build()
        self.apply_role_restrictions()

    def _build(self):
        self.section_label("🔍  Analytical SQL Queries",
                           "10 pre-built analytical queries + custom SQL executor")
        self.divider()
        top = tk.Frame(self, bg=CONTENT_BG); top.pack(fill=tk.X, padx=16, pady=6)
        tk.Label(top, text="Select Query:", bg=CONTENT_BG, fg=TXT_MUTED, font=FONT_BODY).pack(side=tk.LEFT)
        self.q_var = tk.StringVar()
        cb = ttk.Combobox(top, textvariable=self.q_var, values=list(QUERIES.keys()),
                          state="readonly", width=46, font=FONT_BODY)
        cb.pack(side=tk.LEFT, padx=8); cb.current(0)
        btn(top, "▶  Run",        self._run,    NEON_BLUE).pack(side=tk.LEFT, padx=4)
        btn(top, "💾  Export CSV", self._export, NEON_GREEN).pack(side=tk.LEFT, padx=4)

        cust = tk.LabelFrame(self, text="  Custom SQL  ", bg=CARD_BG, fg=NEON_CYAN,
                             font=FONT_HEADER, bd=1, relief="groove")
        cust.pack(fill=tk.X, padx=16, pady=4)
        self.sql_text = tk.Text(cust, height=3, font=FONT_MONO,
                                bg="#040D1A", fg="#7DD3FC",
                                insertbackground=NEON_CYAN, relief="flat",
                                padx=8, pady=6, selectbackground="#163356")
        self.sql_text.pack(fill=tk.X, padx=4, pady=4)
        btn(cust, "▶  Execute Custom SQL", self._run_custom, NEON_PURPLE, BG_DEEP).pack(anchor="w", padx=6, pady=(0, 6))

        self.result_frame = tk.Frame(self, bg=CONTENT_BG)
        self.result_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=4)
        self._status_lbl = tk.Label(self, text="", bg=CONTENT_BG, fg=TXT_MUTED, font=FONT_SMALL)
        self._status_lbl.pack(anchor="w", padx=16, pady=2)
        self._last_data = []; self._last_cols = []; self._run()

    def _run(self):
        self._execute(QUERIES.get(self.q_var.get(), ""))

    def _run_custom(self):
        sql = self.sql_text.get("1.0", tk.END).strip()
        if sql: self._execute(sql)

    def _execute(self, sql):
        for w in self.result_frame.winfo_children(): w.destroy()
        try:
            conn = get_connection(); c = conn.cursor(); c.execute(sql)
            cols = [d[0] for d in c.description] if c.description else []
            rows = c.fetchall(); conn.close()
        except Exception as e: messagebox.showerror("SQL Error", str(e)); return
        self._last_cols = cols; self._last_data = rows
        tv = make_treeview(self.result_frame, cols, height=12)
        w  = max(80, min(200, 960 // max(len(cols), 1)))
        for c in cols: tv.heading(c, text=c); tv.column(c, width=w, anchor="center")
        for i, row in enumerate(rows):
            tv.insert("", "end", values=list(row), tags=("alt" if i % 2 else "",))
        self.status(f"✔  {len(rows)} row(s) returned.")

    def _export(self):
        if not self._last_data: messagebox.showinfo("Nothing", "Run a query first."); return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if not path: return
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(self._last_cols)
            csv.writer(f).writerows(self._last_data)
        messagebox.showinfo("Exported", f"Saved to {path}")


# ═══════════════════════════════════════════════════════════
# 18.  ADVANCED FILTERING
# ═══════════════════════════════════════════════════════════

class FilterTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role); self.app = app; self._build()

    def _build(self):
        self.section_label("🔬  Advanced Filtering",
                           "Combine multiple conditions to drill into detection events")
        self.divider()
        form = self._make_form("Filter Criteria")
        self.v_diam_min  = labeled_entry(form, "Diameter Min (km)",         0, 0)
        self.v_diam_max  = labeled_entry(form, "Diameter Max (km)",         0, 2)
        self.v_risk_min  = labeled_entry(form, "Risk ID Min (1-10)",        1, 0)
        self.v_risk_max  = labeled_entry(form, "Risk ID Max (1-10)",        1, 2)
        self.v_date_from = labeled_entry(form, "Date From (YYYY-MM-DD)",    2, 0)
        self.v_date_to   = labeled_entry(form, "Date To   (YYYY-MM-DD)",    2, 2)
        self.v_prob_min  = labeled_entry(form, "Probability Min (0-1)",     3, 0)
        self.v_prob_max  = labeled_entry(form, "Probability Max (0-1)",     3, 2)
        bf = tk.Frame(form, bg=CARD_BG); bf.grid(row=4, column=0, columnspan=4, pady=8, padx=8, sticky="w")
        btn(bf, "🔬  Apply Filters", self._apply,  NEON_BLUE).pack(side=tk.LEFT, padx=4)
        btn(bf, "🧹  Reset",         self._reset,  MUTED).pack(side=tk.LEFT, padx=4)
        btn(bf, "💾  Export Results", self._export, NEON_GREEN).pack(side=tk.LEFT, padx=4)
        self._status_lbl = tk.Label(self, text="", bg=CONTENT_BG, fg=NEON_GREEN, font=FONT_SMALL)
        self._status_lbl.pack(anchor="w", padx=16)
        cols = ("Asteroid","Diameter","Detection Date","Probability","Risk","Scientist")
        self.tv = make_treeview(self, cols, height=12)
        for c, w in zip(cols, (200, 90, 120, 110, 110, 180)):
            self.tv.heading(c, text=c); self.tv.column(c, width=w, anchor="center")
        self._last_rows = []; self._apply()

    def _apply(self):
        conditions = ["1=1"]; params = []
        try:
            if self.v_diam_min.get():  conditions.append("a.Diameter>=?");        params.append(float(self.v_diam_min.get()))
            if self.v_diam_max.get():  conditions.append("a.Diameter<=?");        params.append(float(self.v_diam_max.get()))
            if self.v_risk_min.get():  conditions.append("de.Risk_ID>=?");        params.append(int(self.v_risk_min.get()))
            if self.v_risk_max.get():  conditions.append("de.Risk_ID<=?");        params.append(int(self.v_risk_max.get()))
            if self.v_date_from.get(): validate_date(self.v_date_from.get(),"From"); conditions.append("de.Detection_Date>=?"); params.append(self.v_date_from.get())
            if self.v_date_to.get():   validate_date(self.v_date_to.get(),"To");   conditions.append("de.Detection_Date<=?"); params.append(self.v_date_to.get())
            if self.v_prob_min.get():  conditions.append("de.Probability>=?");    params.append(float(self.v_prob_min.get()))
            if self.v_prob_max.get():  conditions.append("de.Probability<=?");    params.append(float(self.v_prob_max.get()))
        except ValueError as e: messagebox.showerror("Filter Error", str(e)); return
        sql = f"""SELECT a.Name,a.Diameter,de.Detection_Date,
            printf('%.6f',de.Probability),rc.Category_Name,s.Name
            FROM Detection_Events de
            LEFT JOIN Asteroids a      ON de.Asteroid_ID=a.Asteroid_ID
            LEFT JOIN Risk_Category rc ON de.Risk_ID=rc.Risk_ID
            LEFT JOIN Scientists s     ON de.Scientist_ID=s.Scientist_ID
            WHERE {' AND '.join(conditions)} ORDER BY de.Probability DESC"""
        conn = get_connection(); rows = conn.execute(sql, params).fetchall(); conn.close()
        self._last_rows = rows
        self.tv.delete(*self.tv.get_children())
        for i, r in enumerate(rows):
            self.tv.insert("", "end", values=list(r), tags=("alt" if i % 2 else "",))
        self.status(f"✔  {len(rows)} result(s) matching filters")

    def _reset(self):
        for v in (self.v_diam_min, self.v_diam_max, self.v_risk_min, self.v_risk_max,
                  self.v_date_from, self.v_date_to, self.v_prob_min, self.v_prob_max): v.set("")
        self._apply()

    def _export(self):
        if not self._last_rows: messagebox.showinfo("Nothing", "Apply filters first."); return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if not path: return
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["Asteroid","Diameter","Detection Date","Probability","Risk","Scientist"])
            csv.writer(f).writerows(self._last_rows)
        messagebox.showinfo("Exported", f"Saved: {path}")


# ═══════════════════════════════════════════════════════════
# 19.  TIMELINE VIEW
# ═══════════════════════════════════════════════════════════

class TimelineTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role); self.app = app; self._build()

    def _build(self):
        self.section_label("📅  Event Timeline",
                           "Chronological detection & observation events")
        self.divider()
        top = tk.Frame(self, bg=CONTENT_BG); top.pack(fill=tk.X, padx=16, pady=6)
        tk.Label(top, text="Asteroid ID:", bg=CONTENT_BG, fg=TXT_MUTED, font=FONT_BODY).pack(side=tk.LEFT)
        self.v_id = tk.StringVar()
        tk.Entry(top, textvariable=self.v_id, width=10, font=FONT_BODY,
                 bg=BG_PANEL, fg=TXT_PRIMARY, insertbackground=NEON_BLUE,
                 relief="flat", highlightthickness=1,
                 highlightcolor=NEON_BLUE, highlightbackground=TXT_DIM).pack(side=tk.LEFT, padx=6, ipady=3)
        btn(top, "📅  Show Timeline", self._show,     NEON_BLUE).pack(side=tk.LEFT, padx=4)
        btn(top, "🌌  Show All",      self._show_all, MUTED).pack(side=tk.LEFT, padx=4)
        self._status_lbl = tk.Label(self, text="", bg=CONTENT_BG, fg=NEON_GREEN, font=FONT_SMALL)
        self._status_lbl.pack(anchor="w", padx=16)
        cols = ("Date","Event Type","Asteroid","Details","Scientist")
        self.tv = make_treeview(self, cols, height=16)
        for c, w in zip(cols, (120, 140, 200, 280, 190)):
            self.tv.heading(c, text=c); self.tv.column(c, width=w, anchor="w")
        self._show_all()

    def _show(self):
        try: aid = validate_int(self.v_id.get(), "Asteroid ID", 1)
        except ValueError as e: messagebox.showerror("Error", str(e)); return
        self._load(aid)

    def _show_all(self): self._load(None)

    def _load(self, aid=None):
        conn = get_connection(); events = []
        filt  = " WHERE de.Asteroid_ID=?" if aid else ""
        filt2 = " WHERE o.Asteroid_ID=?"  if aid else ""
        params = (aid,) if aid else ()
        for r in conn.execute(f"""SELECT de.Detection_Date,'⚡  Detection',a.Name,
            'P='||printf('%.6f',de.Probability)||'  Risk='||rc.Category_Name,s.Name
            FROM Detection_Events de JOIN Asteroids a ON de.Asteroid_ID=a.Asteroid_ID
            JOIN Risk_Category rc ON de.Risk_ID=rc.Risk_ID
            JOIN Scientists s ON de.Scientist_ID=s.Scientist_ID{filt}""", params):
            events.append(list(r)+["det"])
        for r in conn.execute(f"""SELECT o.Observation_Date,'📡  Observation',a.Name,
            o.Position,s.Name FROM Observations o
            LEFT JOIN Asteroids a ON o.Asteroid_ID=a.Asteroid_ID
            LEFT JOIN Scientists s ON o.Scientist_ID=s.Scientist_ID{filt2}""", params):
            events.append(list(r)+["obs"])
        conn.close()
        events.sort(key=lambda x: x[0])
        self.tv.delete(*self.tv.get_children())
        for i, e in enumerate(events):
            tag = "high_risk" if e[5] == "det" else ("alt" if i % 2 else "")
            self.tv.insert("", "end", values=e[:5], tags=(tag,))
        self.status(f"✔  {len(events)} timeline events")


# ═══════════════════════════════════════════════════════════
# 20.  REPORT GENERATOR
# ═══════════════════════════════════════════════════════════

class ReportTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role); self.app = app; self._build()

    def _build(self):
        self.section_label("📄  Report Generator",
                           "Generate summary reports for asteroids, missions, and risk analysis")
        self.divider()
        bf = tk.Frame(self, bg=CONTENT_BG); bf.pack(anchor="w", padx=16, pady=10)
        btn(bf, "🪐  Asteroid Summary",  lambda: self._gen("asteroids"), NEON_BLUE).pack(side=tk.LEFT, padx=6)
        btn(bf, "🚀  Missions Report",   lambda: self._gen("missions"),  NEON_GREEN).pack(side=tk.LEFT, padx=6)
        btn(bf, "⚠  Risk Summary",       lambda: self._gen("risk"),      NEON_RED).pack(side=tk.LEFT, padx=6)
        btn(bf, "👩‍🔬  Scientists Report", lambda: self._gen("scientists"),NEON_PURPLE).pack(side=tk.LEFT, padx=6)
        btn(bf, "💾  Export Text",       self._export,                   NEON_AMBER, BG_DEEP).pack(side=tk.LEFT, padx=6)
        self.report_text = tk.Text(self, font=FONT_MONO,
                                   bg="#020C1A", fg="#67E8F9",
                                   insertbackground=NEON_CYAN,
                                   selectbackground="#163356",
                                   relief="flat", padx=12, pady=8, state="disabled")
        self.report_text.pack(fill=tk.BOTH, expand=True, padx=16, pady=8)
        self._last_report = ""; self._gen("asteroids")

    def _gen(self, report_type):
        conn = get_connection(); now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        star = "═"*64
        if report_type == "asteroids":
            rows = conn.execute("SELECT Asteroid_ID,Name,Diameter,Orbital_Period FROM Asteroids ORDER BY Diameter DESC").fetchall()
            lines = [star, f"  ☄  ASTEROID CATALOGUE — DBS PROJECT v4.1",
                     f"  Generated: {now}   ·   Total: {len(rows)} asteroids", star, ""]
            for r in rows: lines.append(f"  [{r[0]:3d}]  {r[1]:<34}  Ø={r[2]} km   T={r[3]} yr")
        elif report_type == "missions":
            rows = conn.execute("SELECT Mission_ID,Mission_Name,Agency,Launch_Date FROM Missions ORDER BY Launch_Date").fetchall()
            lines = [star, f"  🚀  SPACE MISSIONS REPORT — DBS PROJECT v4.1",
                     f"  Generated: {now}   ·   Total: {len(rows)} missions", star, ""]
            for r in rows: lines.append(f"  [{r[0]:3d}]  {r[1]:<44}  {r[2]}  ({r[3]})")
        elif report_type == "risk":
            rows = conn.execute("""SELECT rc.Category_Name,COUNT(*),printf('%.6f',AVG(de.Probability))
                FROM Detection_Events de JOIN Risk_Category rc ON de.Risk_ID=rc.Risk_ID
                GROUP BY rc.Category_Name ORDER BY AVG(de.Probability) DESC""").fetchall()
            lines = [star, "  ⚠  RISK ANALYSIS REPORT — DBS PROJECT v4.1",
                     f"  Generated: {now}", star, ""]
            for r in rows: lines.append(f"  {r[0]:<22}  Events={r[1]:<4}  Avg Probability={r[2]}")
        else:
            rows = conn.execute("SELECT Scientist_ID,Name,Specialization,Experience_Years FROM Scientists ORDER BY Experience_Years DESC").fetchall()
            lines = [star, "  👩‍🔬  SCIENTISTS REPORT — DBS PROJECT v4.1",
                     f"  Generated: {now}   ·   Total: {len(rows)} scientists", star, ""]
            for r in rows: lines.append(f"  [{r[0]:3d}]  {r[1]:<30}  {r[2]}  ({r[3]} yrs)")
        conn.close()
        lines += [""]
        self._last_report = "\n".join(lines)
        self.report_text.config(state="normal")
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert("1.0", self._last_report)
        self.report_text.config(state="disabled")

    def _export(self):
        if not self._last_report: return
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            filetypes=[("Text","*.txt"),("All","*.*")])
        if not path: return
        with open(path, "w", encoding="utf-8") as f: f.write(self._last_report)
        messagebox.showinfo("Exported", f"Report saved to:\n{path}")


# ═══════════════════════════════════════════════════════════
# 21.  CHARTS
# ═══════════════════════════════════════════════════════════

class ChartsTab(BaseTab):
    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role); self.app = app; self._build()

    def _build(self):
        if not MATPLOTLIB_OK:
            tk.Label(self, text="⚠  matplotlib not installed.\npip install matplotlib numpy",
                     bg=CONTENT_BG, fg=NEON_RED, font=FONT_HEADER).pack(pady=40); return

        self.section_label("📊  Data Visualizations",
                           "13 interactive chart types · dark-mode · filters")
        self.divider()
        top = tk.Frame(self, bg=CONTENT_BG); top.pack(fill=tk.X, padx=16, pady=6)
        tk.Label(top, text="Chart:", bg=CONTENT_BG, fg=TXT_MUTED, font=FONT_BODY).pack(side=tk.LEFT)
        self.chart_var = tk.StringVar()
        self.options = [
            "Bar – Top 15 Asteroids by Diameter",
            "Horizontal Bar – Scientist Experience",
            "Pie – Risk Category Distribution",
            "Pie – Observations by Country",
            "Line – Detection Events Over Time",
            "Line – Missions Launched per Year",
            "Scatter – Diameter vs Impact Probability",
            "Scatter – Orbital Period vs Diameter",
            "Histogram – Asteroid Diameter Distribution",
            "Stacked Bar – Detections by Risk per Year",
            "Area – Cumulative Detections Over Time",
            "Box Plot – Telescope Aperture by Type",
            "Heatmap – Risk Level vs Year",
        ]
        cb = ttk.Combobox(top, textvariable=self.chart_var, values=self.options,
                          state="readonly", width=42, font=FONT_BODY)
        cb.pack(side=tk.LEFT, padx=8); cb.current(0)
        ff = tk.Frame(top, bg=CONTENT_BG); ff.pack(side=tk.LEFT, padx=8)
        tk.Label(ff, text="Year:", bg=CONTENT_BG, fg=TXT_MUTED, font=FONT_SMALL).pack(side=tk.LEFT)
        self.f_year = tk.StringVar()
        tk.Entry(ff, textvariable=self.f_year, width=6, font=FONT_SMALL,
                 bg=BG_PANEL, fg=TXT_PRIMARY, insertbackground=NEON_BLUE,
                 relief="flat", highlightthickness=1,
                 highlightcolor=NEON_BLUE, highlightbackground=TXT_DIM).pack(side=tk.LEFT, padx=2)
        tk.Label(ff, text="Risk≥:", bg=CONTENT_BG, fg=TXT_MUTED, font=FONT_SMALL).pack(side=tk.LEFT, padx=(10, 0))
        self.f_risk = tk.StringVar()
        tk.Entry(ff, textvariable=self.f_risk, width=4, font=FONT_SMALL,
                 bg=BG_PANEL, fg=TXT_PRIMARY, insertbackground=NEON_BLUE,
                 relief="flat", highlightthickness=1,
                 highlightcolor=NEON_BLUE, highlightbackground=TXT_DIM).pack(side=tk.LEFT, padx=2)
        btn(top, "📊  Draw",     self._draw, NEON_BLUE).pack(side=tk.LEFT, padx=4)
        btn(top, "💾  Save PNG", self._save, MUTED, TXT_PRIMARY).pack(side=tk.LEFT, padx=4)

        self.canvas_frame = tk.Frame(self, bg=BG_DEEP)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self._fig = None; self._draw()

    _SPACE_STYLE = {
        "figure.facecolor": "#030D1A", "axes.facecolor":  "#070F1E",
        "axes.edgecolor":   "#1E3A5F", "axes.labelcolor": "#94A3B8",
        "axes.titlecolor":  "#E2E8F0", "text.color":      "#94A3B8",
        "xtick.color":      "#64748B", "ytick.color":     "#64748B",
        "grid.color":       "#0F2137", "grid.linestyle":  "--", "grid.alpha": 0.5,
    }

    def _draw(self):
        for w in self.canvas_frame.winfo_children(): w.destroy()
        conn = get_connection()
        choice      = self.chart_var.get()
        year_filter = self.f_year.get().strip()
        risk_filter = int(self.f_risk.get()) if self.f_risk.get().strip().isdigit() else 1

        with plt.rc_context(self._SPACE_STYLE):
            fig, ax = plt.subplots(figsize=(9, 4.6))
            self._fig = fig
            PALETTE = [NEON_BLUE, NEON_GREEN, NEON_AMBER, NEON_PURPLE,
                       NEON_CYAN, NEON_RED, NEON_ORANGE, "#E879F9",
                       "#34D399", "#60A5FA"]
            try:
                if "Bar – Top" in choice:
                    rows = conn.execute("SELECT Name,Diameter FROM Asteroids ORDER BY Diameter DESC LIMIT 15").fetchall()
                    names = [r[0] for r in rows]; vals = [r[1] for r in rows]
                    bars = ax.barh(names, vals, color=NEON_BLUE, alpha=0.85); ax.invert_yaxis()
                    ax.set_xlabel("Diameter (km)"); ax.set_title("Top 15 Asteroids by Diameter", fontweight="bold")
                    ax.grid(axis="x"); ax.axvline(sum(vals)/len(vals), color=NEON_AMBER, linestyle="--", alpha=0.7, label="Mean")
                    ax.legend(fontsize=8)
                    for bar in bars:
                        ax.annotate(f"{bar.get_width():.0f}", xy=(bar.get_width(), bar.get_y()+bar.get_height()/2),
                                    xytext=(3, 0), textcoords="offset points", va="center", fontsize=7, color=TXT_MUTED)
                elif "Horizontal Bar" in choice:
                    rows = conn.execute("SELECT Name,Experience_Years FROM Scientists ORDER BY Experience_Years DESC LIMIT 15").fetchall()
                    ax.barh([r[0] for r in rows], [r[1] for r in rows], color=NEON_PURPLE, alpha=0.85)
                    ax.invert_yaxis(); ax.set_xlabel("Years")
                    ax.set_title("Scientist Experience (Top 15)", fontweight="bold"); ax.grid(axis="x")
                elif "Pie – Risk" in choice:
                    rows = conn.execute("""SELECT rc.Category_Name,COUNT(*) FROM Detection_Events de
                        JOIN Risk_Category rc ON de.Risk_ID=rc.Risk_ID WHERE de.Risk_ID>=?
                        GROUP BY rc.Category_Name""", (risk_filter,)).fetchall()
                    wedges, texts, autotexts = ax.pie(
                        [r[1] for r in rows], labels=[r[0] for r in rows],
                        autopct="%1.1f%%", colors=PALETTE[:len(rows)],
                        startangle=140, pctdistance=0.82,
                        wedgeprops=dict(edgecolor=BG_DEEP, linewidth=1.5))
                    for t in texts: t.set_color(TXT_MUTED); t.set_fontsize(8)
                    for t in autotexts: t.set_color(BG_DEEP); t.set_fontsize(7)
                    ax.set_title("Detection Events by Risk Category", fontweight="bold")
                elif "Pie – Obs" in choice:
                    rows = conn.execute("""SELECT ob.Country,COUNT(*) FROM Observations o
                        JOIN Telescopes t ON o.Telescope_ID=t.Telescope_ID
                        JOIN Observatories ob ON t.Observatory_ID=ob.Observatory_ID
                        GROUP BY ob.Country ORDER BY 2 DESC LIMIT 8""").fetchall()
                    ax.pie([r[1] for r in rows], labels=[r[0] for r in rows],
                           autopct="%1.1f%%", colors=PALETTE, startangle=140,
                           wedgeprops=dict(edgecolor=BG_DEEP, linewidth=1.5))
                    ax.set_title("Observations by Country", fontweight="bold")
                elif "Line – Detection" in choice:
                    sql = ("SELECT substr(Detection_Date,1,4),COUNT(*) FROM Detection_Events "
                           + ("WHERE substr(Detection_Date,1,4)=? " if year_filter else "")
                           + "GROUP BY 1 ORDER BY 1")
                    params = (year_filter,) if year_filter else ()
                    rows = conn.execute(sql, params).fetchall()
                    xs = [r[0] for r in rows]; ys = [r[1] for r in rows]
                    ax.plot(xs, ys, marker="o", color=NEON_CYAN, linewidth=2, markersize=7)
                    ax.fill_between(xs, ys, alpha=0.12, color=NEON_CYAN)
                    ax.set_xlabel("Year"); ax.set_ylabel("Events"); ax.grid()
                    ax.set_title("Detection Events Over Time", fontweight="bold")
                elif "Line – Mission" in choice:
                    rows = conn.execute("""SELECT substr(Launch_Date,1,4),COUNT(*) FROM Missions
                        WHERE Launch_Date IS NOT NULL GROUP BY 1 ORDER BY 1""").fetchall()
                    xs = [r[0] for r in rows]; ys = [r[1] for r in rows]
                    ax.plot(xs, ys, marker="s", color=NEON_GREEN, linewidth=2, markersize=7)
                    ax.fill_between(xs, ys, alpha=0.12, color=NEON_GREEN)
                    ax.set_xlabel("Year"); ax.set_ylabel("Missions"); ax.grid()
                    ax.set_title("Missions Launched per Year", fontweight="bold")
                elif "Scatter – Diameter vs" in choice:
                    rows = conn.execute("""SELECT a.Diameter,de.Probability FROM Asteroids a
                        JOIN Detection_Events de ON a.Asteroid_ID=de.Asteroid_ID
                        WHERE a.Diameter IS NOT NULL AND de.Risk_ID>=?""", (risk_filter,)).fetchall()
                    xs = [r[0] for r in rows]; ys = [r[1] for r in rows]
                    sc = ax.scatter(xs, ys, c=ys, cmap="plasma", s=70, alpha=0.85, edgecolors=BG_PANEL, linewidths=0.5)
                    plt.colorbar(sc, ax=ax, label="Probability")
                    ax.axhline(sum(ys)/max(len(ys),1), color=NEON_RED, linestyle="--", alpha=0.7, label="Mean")
                    ax.legend(fontsize=8); ax.grid()
                    ax.set_xlabel("Diameter (km)"); ax.set_ylabel("Probability")
                    ax.set_title("Diameter vs Impact Probability", fontweight="bold")
                elif "Scatter – Orbital" in choice:
                    rows = conn.execute("SELECT Orbital_Period,Diameter FROM Asteroids WHERE Orbital_Period<400").fetchall()
                    xs = [r[0] for r in rows]; ys = [r[1] for r in rows]
                    sc = ax.scatter(xs, ys, c=ys, cmap="plasma", s=70, alpha=0.85, edgecolors=BG_PANEL, linewidths=0.5)
                    plt.colorbar(sc, ax=ax, label="Diameter (km)"); ax.grid()
                    ax.set_xlabel("Orbital Period (yr)"); ax.set_ylabel("Diameter (km)")
                    ax.set_title("Orbital Period vs Diameter", fontweight="bold")
                elif "Histogram" in choice:
                    vals = [r[0] for r in conn.execute("SELECT Diameter FROM Asteroids WHERE Diameter IS NOT NULL").fetchall()]
                    ax.hist(vals, bins=15, color=NEON_BLUE, edgecolor=BG_DEEP, alpha=0.85)
                    avg = sum(vals)/len(vals)
                    ax.axvline(avg, color=NEON_RED, linestyle="--", label=f"Mean={avg:.1f} km")
                    ax.set_xlabel("Diameter (km)"); ax.set_ylabel("Count"); ax.grid(axis="y")
                    ax.set_title("Asteroid Diameter Distribution", fontweight="bold"); ax.legend(fontsize=9)
                elif "Stacked Bar" in choice:
                    rows = conn.execute("""SELECT substr(Detection_Date,1,4),Risk_ID,COUNT(*) FROM Detection_Events
                        GROUP BY 1,2 ORDER BY 1""").fetchall()
                    years = sorted(set(r[0] for r in rows))
                    risk_groups = sorted(set(r[1] for r in rows))
                    data = {rg: [0]*len(years) for rg in risk_groups}
                    for yr, rg, cnt in rows:
                        if yr in years: data[rg][years.index(yr)] = cnt
                    bottom = [0]*len(years)
                    for rg, color in zip(risk_groups, PALETTE):
                        vals = data[rg]
                        ax.bar(years, vals, bottom=bottom, label=f"Risk {rg}", color=color, alpha=0.85)
                        bottom = [b+v for b, v in zip(bottom, vals)]
                    ax.set_xlabel("Year"); ax.set_ylabel("Events")
                    ax.set_title("Detection Events by Risk Level per Year", fontweight="bold")
                    ax.legend(loc="upper left", fontsize=7, ncol=2)
                elif "Area" in choice:
                    rows = conn.execute("SELECT Detection_Date FROM Detection_Events ORDER BY Detection_Date").fetchall()
                    cnt = Counter(r[0][:4] for r in rows)
                    years = sorted(cnt.keys())
                    cumul = [sum(cnt[y] for y in years[:i+1]) for i in range(len(years))]
                    ax.fill_between(years, cumul, alpha=0.25, color=NEON_CYAN)
                    ax.plot(years, cumul, color=NEON_CYAN, linewidth=2, marker="o", markersize=6)
                    ax.set_xlabel("Year"); ax.set_ylabel("Cumulative Detections"); ax.grid()
                    ax.set_title("Cumulative Detections Over Time", fontweight="bold")
                elif "Box Plot" in choice:
                    rows = conn.execute("SELECT Type,Aperture_Size FROM Telescopes WHERE Aperture_Size IS NOT NULL").fetchall()
                    types = sorted(set(r[0] for r in rows))
                    grouped = [[r[1] for r in rows if r[0] == t] for t in types]
                    bp = ax.boxplot(grouped, labels=types, patch_artist=True,
                                   medianprops=dict(color=NEON_RED, linewidth=2))
                    for patch, color in zip(bp["boxes"], PALETTE):
                        patch.set_facecolor(color); patch.set_alpha(0.4)
                    ax.set_ylabel("Aperture Size (m)"); ax.grid(axis="y")
                    ax.set_title("Telescope Aperture Distribution by Type", fontweight="bold")
                elif "Heatmap" in choice:
                    rows = conn.execute("""SELECT substr(Detection_Date,1,4),Risk_ID,COUNT(*)
                        FROM Detection_Events GROUP BY 1,2""").fetchall()
                    years = sorted(set(r[0] for r in rows))
                    mat = np.zeros((10, len(years)))
                    for yr, rg, cnt in rows:
                        if yr in years and 1 <= rg <= 10:
                            mat[rg-1][years.index(yr)] = cnt
                    im = ax.imshow(mat, cmap="YlOrRd", aspect="auto", interpolation="nearest")
                    ax.set_xticks(range(len(years))); ax.set_xticklabels(years, rotation=45, ha="right", fontsize=8)
                    ax.set_yticks(range(10)); ax.set_yticklabels([f"Risk {r}" for r in range(1, 11)], fontsize=8)
                    plt.colorbar(im, ax=ax, label="Event Count")
                    ax.set_title("Detection Events: Risk Level × Year", fontweight="bold")
            except Exception as e:
                ax.text(0.5, 0.5, f"Chart error:\n{e}", transform=ax.transAxes,
                        ha="center", va="center", color=NEON_RED, fontsize=11)
            finally:
                conn.close()

            plt.tight_layout(pad=1.0)
            canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            annot = ax.annotate("", xy=(0,0), xytext=(12,12), textcoords="offset points",
                                bbox=dict(boxstyle="round,pad=0.4", fc=BG_PANEL, ec=NEON_BLUE, alpha=0.95),
                                fontsize=8, color=TXT_PRIMARY, visible=False)
            def on_hover(event):
                if event.inaxes == ax and event.xdata is not None:
                    annot.set_text(f"x = {event.xdata:.3f}\ny = {event.ydata:.3f}")
                    annot.xy = (event.xdata, event.ydata); annot.set_visible(True)
                else:
                    annot.set_visible(False)
                canvas.draw_idle()
            canvas.mpl_connect("motion_notify_event", on_hover)

    def _save(self):
        if not self._fig: return
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            filetypes=[("PNG","*.png"),("All","*.*")])
        if path:
            self._fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG_DEEP)
            messagebox.showinfo("Saved", f"Chart saved to:\n{path}")


# ═══════════════════════════════════════════════════════════
# 22a.  AUDIT LOG VIEWER TAB
# ═══════════════════════════════════════════════════════════

class AuditLogTab(BaseTab):
    """Browse and filter all database changes tracked in Audit_Log."""

    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role)
        self.app = app
        self._build()

    def _build(self):
        self.section_label("📋  Audit Log", "Full history of all database changes")
        self.divider()

        fbar = tk.Frame(self, bg=CONTENT_BG)
        fbar.pack(fill=tk.X, padx=16, pady=(4, 2))
        tk.Label(fbar, text="Filter:", bg=CONTENT_BG, fg=TXT_MUTED,
                 font=FONT_SMALL).pack(side=tk.LEFT)
        self._filter_var = tk.StringVar()
        self._filter_var.trace_add("write", lambda *_: self._load())
        tk.Entry(fbar, textvariable=self._filter_var, width=28,
                 font=FONT_BODY, bg=BG_PANEL, fg=TXT_PRIMARY,
                 insertbackground=NEON_BLUE, relief="flat",
                 highlightthickness=1, highlightcolor=NEON_BLUE,
                 highlightbackground=TXT_DIM).pack(side=tk.LEFT, padx=6, ipady=3)
        tk.Label(fbar, text="Action:", bg=CONTENT_BG, fg=TXT_MUTED,
                 font=FONT_SMALL).pack(side=tk.LEFT, padx=(10, 2))
        self._action_var = tk.StringVar(value="ALL")
        action_cb = ttk.Combobox(fbar, textvariable=self._action_var, width=12,
                                 values=["ALL","LOGIN","INSERT","UPDATE","DELETE",
                                         "LINK","UNLINK","SIMULATE"],
                                 state="readonly", font=FONT_SMALL)
        action_cb.pack(side=tk.LEFT, padx=4)
        action_cb.bind("<<ComboboxSelected>>", lambda _: self._load())
        btn(fbar, "🔄 Refresh",  self._load,      NEON_BLUE).pack(side=tk.LEFT, padx=8)
        btn(fbar, "🗑 Clear Log", self._clear_log, NEON_RED).pack(side=tk.LEFT, padx=4)

        self._status_lbl = tk.Label(self, text="", bg=CONTENT_BG,
                                    fg=NEON_GREEN, font=FONT_SMALL)
        self._status_lbl.pack(anchor="w", padx=16)

        cols = ("ID", "Timestamp", "User", "Action", "Table", "Record ID", "Detail")
        self.tv = make_treeview(self, cols, height=18)
        for c, w in zip(cols, (55, 155, 100, 80, 160, 90, 380)):
            self.tv.heading(c, text=c)
            self.tv.column(c, width=w, anchor="w")

        self.tv.tag_configure("act_INSERT",   background="#061a10", foreground=NEON_GREEN)
        self.tv.tag_configure("act_UPDATE",   background="#0a1628", foreground=NEON_BLUE)
        self.tv.tag_configure("act_DELETE",   background="#200808", foreground=NEON_RED)
        self.tv.tag_configure("act_LOGIN",    background="#0c0c20", foreground=NEON_PURPLE)
        self.tv.tag_configure("act_LINK",     background="#0a1a10", foreground=NEON_CYAN)
        self.tv.tag_configure("act_UNLINK",   background="#1a0a08", foreground=NEON_ORANGE)
        self.tv.tag_configure("act_SIMULATE", background="#1a0510", foreground=NEON_AMBER)
        self._load()

    def _load(self):
        kw     = self._filter_var.get().strip()
        action = self._action_var.get()
        conn   = get_connection()
        q      = ("SELECT Log_ID,Timestamp,Username,Action,Table_Name,Record_ID,Detail "
                  "FROM Audit_Log")
        params, conds = [], []
        if kw:
            conds.append("(Username LIKE ? OR Table_Name LIKE ? OR Detail LIKE ? OR Record_ID LIKE ?)")
            params += [f"%{kw}%"] * 4
        if action != "ALL":
            conds.append("Action = ?"); params.append(action)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY Log_ID DESC LIMIT 500"
        rows = conn.execute(q, params).fetchall()
        conn.close()
        self.tv.delete(*self.tv.get_children())
        _valid_tags = {"act_INSERT","act_UPDATE","act_DELETE",
                       "act_LOGIN","act_LINK","act_UNLINK","act_SIMULATE"}
        for r in rows:
            tag = f"act_{r[3]}"
            self.tv.insert("", "end", values=list(r),
                           tags=(tag,) if tag in _valid_tags else ())
        self.status(f"✔  {len(rows)} log entries")

    def _clear_log(self):
        if self.role != "Admin":
            messagebox.showwarning("Access Denied", "Only Admins can clear the audit log.")
            return
        if not messagebox.askyesno("Confirm",
                "Clear ALL audit log entries?\nThis cannot be undone."):
            return
        conn = get_connection()
        conn.execute("DELETE FROM Audit_Log")
        conn.commit(); conn.close()
        self._load()
        self.status("🗑  Audit log cleared", NEON_RED)


# ═══════════════════════════════════════════════════════════
# 22b.  ASTEROID COLLISION SIMULATOR TAB
# ═══════════════════════════════════════════════════════════

import math, random

def _haversine_offset(lat, lon, bearing_deg, distance_km):
    """Return (lat2, lon2) distance_km from (lat,lon) along bearing_deg."""
    R   = 6371.0
    d   = distance_km / R
    b   = math.radians(bearing_deg)
    la1 = math.radians(lat)
    lo1 = math.radians(lon)
    la2 = math.asin(math.sin(la1)*math.cos(d) +
                    math.cos(la1)*math.sin(d)*math.cos(b))
    lo2 = lo1 + math.atan2(math.sin(b)*math.sin(d)*math.cos(la1),
                            math.cos(d) - math.sin(la1)*math.sin(la2))
    return math.degrees(la2), math.degrees(lo2)


class CollisionSimTab(BaseTab):
    """
    ☄ Asteroid Collision Simulator
    Select an asteroid → click Simulate Impact → see concentric blast rings:
        🔴  Impact zone  (total destruction)
        🟡  Damage zone  (blast & thermal)
        🟢  Safe zone    (evacuation boundary)
    Ring radii scale with sqrt(diameter) for area-based realism.
    """
    IMPACT_FACTOR = 15    # km per sqrt(km) of diameter
    DAMAGE_FACTOR = 60
    SAFE_FACTOR   = 150
    RING_STEPS    = 72    # polygon resolution

    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role)
        self.app        = app
        self._map       = None
        self._polygons  = []
        self._markers   = []
        self._marker_imgs = {}
        self._ast_data  = []
        self._build()

    def _build(self):
        self.section_label(
            "☄  Asteroid Collision Simulator",
            "Select an asteroid · simulate impact · visualise blast zones on the map")
        self.divider()

        if not MAP_OK:
            tk.Label(self, text="⚠  tkintermapview required for the Collision Simulator.",
                     bg=CONTENT_BG, fg=NEON_AMBER, font=FONT_BODY).pack(pady=40)
            return

        # Controls bar
        ctrl = tk.Frame(self, bg=BG_PANEL, pady=6)
        ctrl.pack(fill=tk.X, padx=16, pady=(0, 4))
        tk.Label(ctrl, text="Asteroid:", bg=BG_PANEL, fg=TXT_MUTED,
                 font=FONT_BODY).pack(side=tk.LEFT, padx=(8, 4))
        self._ast_var = tk.StringVar()
        self._ast_cb  = ttk.Combobox(ctrl, textvariable=self._ast_var,
                                     width=32, state="readonly", font=FONT_BODY)
        self._ast_cb.pack(side=tk.LEFT, padx=4)
        btn(ctrl, "☄  Simulate Impact",  self._simulate,    NEON_RED,   BG_DEEP).pack(side=tk.LEFT, padx=8)
        btn(ctrl, "🌐  Reset View",       self._reset_view,  NEON_BLUE,  BG_DEEP).pack(side=tk.LEFT, padx=4)
        btn(ctrl, "✖  Clear Zones",       self._clear_zones, NEON_AMBER, BG_DEEP).pack(side=tk.LEFT, padx=4)

        # Legend
        leg = tk.Frame(self, bg=BG_SPACE, pady=4)
        leg.pack(fill=tk.X, padx=16, pady=(0, 2))
        for sym, lbl, col in [
            ("🔴", " Impact Zone   (total destruction)",   NEON_RED),
            ("🟡", " Damage Zone   (blast & thermal)",     NEON_AMBER),
            ("🟢", " Safe Zone     (evacuation boundary)", NEON_GREEN),
        ]:
            tk.Label(leg, text=sym, bg=BG_SPACE, font=("Segoe UI",13)).pack(side=tk.LEFT, padx=(12,0))
            tk.Label(leg, text=lbl, bg=BG_SPACE, fg=col,
                     font=("Consolas",9)).pack(side=tk.LEFT, padx=(0,16))

        # Telemetry bar
        info_frame = tk.Frame(self, bg=BG_SPACE, pady=6)
        info_frame.pack(fill=tk.X, padx=16, pady=(0, 2))
        tk.Label(info_frame, text="IMPACT DATA ›", bg=BG_SPACE, fg=TXT_DIM,
                 font=("Consolas", 9, "bold")).pack(side=tk.LEFT, padx=(8, 4))
        self._info_lbl = tk.Label(
            info_frame,
            text="SELECT AN ASTEROID AND PRESS  ☄ SIMULATE IMPACT …",
            bg=BG_SPACE, fg=NEON_GREEN,
            font=("Consolas", 9, "bold"), anchor="w")
        self._info_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Status
        self._status_lbl = tk.Label(self, text="", bg=CONTENT_BG,
                                    fg=TXT_MUTED, font=FONT_SMALL)
        self._status_lbl.pack(anchor="w", padx=16, pady=1)

        # Map
        map_container = tk.Frame(self, bg=BG_DEEP)
        map_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        self._map = tkintermapview.TkinterMapView(
            map_container, width=1100, height=510, corner_radius=0)
        self._map.pack(fill=tk.BOTH, expand=True)
        self._map.set_tile_server(
            "https://tile.openstreetmap.org/{z}/{x}/{y}.png", max_zoom=19)
        self._map.set_position(20, 0)
        self._map.set_zoom(2)

        self.after(400, self._populate_asteroids)

    def _populate_asteroids(self):
        conn = get_connection()
        rows = conn.execute(
            "SELECT Asteroid_ID, Name, Diameter FROM Asteroids "
            "WHERE Diameter IS NOT NULL ORDER BY Diameter DESC").fetchall()
        conn.close()
        self._ast_data = list(rows)
        self._ast_cb["values"] = [f"{r[1]}  (Ø {r[2]} km)" for r in rows]
        if rows:
            self._ast_cb.current(0)
        self.status(f"✔  {len(rows)} asteroids ready")

    def _simulate(self):
        if not self._ast_data:
            messagebox.showinfo("No Data", "No asteroids with diameter data."); return
        idx = self._ast_cb.current()
        if idx < 0:
            messagebox.showinfo("Select", "Please select an asteroid."); return
        ast_id, ast_name, diameter = self._ast_data[idx]
        if not diameter or diameter <= 0:
            messagebox.showwarning("No Size", f"{ast_name} has no diameter data."); return

        impact_lat = random.uniform(-55, 65)
        impact_lon = random.uniform(-170, 170)

        scale    = math.sqrt(max(diameter, 0.01))
        r_impact = max(5,   self.IMPACT_FACTOR * scale)
        r_damage = max(20,  self.DAMAGE_FACTOR * scale)
        r_safe   = max(50,  self.SAFE_FACTOR   * scale)

        self._clear_zones()

        # Draw rings outer→inner so inner renders on top
        self._draw_ring(impact_lat, impact_lon, r_safe,   "#145214", "#4ade80", 0.20)
        self._draw_ring(impact_lat, impact_lon, r_damage, "#7a5c00", "#fcd34d", 0.30)
        self._draw_ring(impact_lat, impact_lon, r_impact, "#7a0000", "#ff4444", 0.45)

        # Impact pin
        try:
            img = _make_neon_marker_image(NEON_RED, 28)
            kw  = dict(text=f"☄ {ast_name}", text_color=NEON_RED,
                       font=("Consolas", 9, "bold"))
            if img:
                self._marker_imgs["impact"] = img
                m = self._map.set_marker(impact_lat, impact_lon,
                                         icon=img, icon_anchor="center", **kw)
            else:
                m = self._map.set_marker(impact_lat, impact_lon,
                                         marker_color_circle=NEON_RED,
                                         marker_color_outside=BG_DEEP, **kw)
            self._markers.append(m)
        except Exception as ex:
            log(f"CollisionSim marker error: {ex}", "warning")

        # Zoom to fit safe zone
        zoom = 3 if r_safe > 1500 else 4 if r_safe > 600 else 5 if r_safe > 200 else 6
        self._map.set_position(impact_lat, impact_lon)
        self._map.set_zoom(zoom)

        self._info_lbl.config(fg=NEON_RED, text=(
            f"ASTEROID: {ast_name}   │   DIAMETER: {diameter} km   │   "
            f"IMPACT: {impact_lat:.3f}°  {impact_lon:.3f}°   │   "
            f"🔴 r={r_impact:.0f} km   🟡 r={r_damage:.0f} km   🟢 r={r_safe:.0f} km"))

        audit_log("SIMULATE", "CollisionSim", ast_id,
                  f"Asteroid={ast_name}, Lat={impact_lat:.3f}, Lon={impact_lon:.3f}, "
                  f"ImpactR={r_impact:.0f}km DamageR={r_damage:.0f}km SafeR={r_safe:.0f}km")
        self.status(
            f"☄  Impact simulated for {ast_name}  ·  "
            f"🔴 {r_impact:.0f} km  🟡 {r_damage:.0f} km  🟢 {r_safe:.0f} km",
            NEON_RED)

    def _draw_ring(self, lat, lon, radius_km, fill_color, outline_color, alpha=0.35):
        if not self._map: return
        pts = []
        for i in range(self.RING_STEPS + 1):
            bearing = (360.0 / self.RING_STEPS) * i
            pt = _haversine_offset(lat, lon, bearing, radius_km)
            pts.append(pt)
        try:
            poly = self._map.set_polygon(
                pts,
                fill_color=fill_color,
                outline_color=outline_color,
                border_width=2,
                fill_color_alpha=alpha,
            )
            self._polygons.append(poly)
        except Exception as ex:
            log(f"CollisionSim polygon error: {ex}", "warning")

    def _clear_zones(self):
        for p in self._polygons:
            try: p.delete()
            except Exception: pass
        self._polygons.clear()
        for m in self._markers:
            try: m.delete()
            except Exception: pass
        self._markers.clear()
        self._info_lbl.config(fg=NEON_GREEN,
            text="SELECT AN ASTEROID AND PRESS  ☄ SIMULATE IMPACT …")
        self.status("✖  Zones cleared", TXT_MUTED)

    def _reset_view(self):
        if self._map:
            self._map.set_position(20, 0)
            self._map.set_zoom(2)


# ═══════════════════════════════════════════════════════════
# 22.  GLOBAL DEFENSE MAP TAB  (NEW in v4.1)
# ═══════════════════════════════════════════════════════════

def _make_neon_marker_image(color_hex: str, size: int = 18) -> "ImageTk.PhotoImage | None":
    """
    Create a circular neon marker as a PhotoImage using PIL.
    Falls back to None if PIL is unavailable.
    """
    if not PIL_OK:
        return None
    try:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Outer glow ring
        h = color_hex.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        glow_color = (r, g, b, 80)
        draw.ellipse([1, 1, size-2, size-2], fill=glow_color)
        # Inner solid circle
        margin = size // 4
        draw.ellipse([margin, margin, size-margin, size-margin], fill=(r, g, b, 230))
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


class GlobalMapTab(BaseTab):
    """
    Global Defense Map — shows all observatories on an interactive world map.

    Requires:  pip install tkintermapview Pillow

    Features:
      · Satellite tile server by default (toggle to OSM standard)
      · Neon-green markers for safe observatories
      · Neon-red markers for observatories that detected Risk ≥ 7
      · Click marker → popup card with Consolas monospace stats
      · fly_to(lat, lon, zoom, label) for cross-tab Fly-To from Asteroids tab
      · Floating controls overlay (tile toggle, reload, legend)
    """

    TILE_SATELLITE = "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga"
    TILE_STANDARD  = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    # Use standard OSM by default — much faster than satellite; user can switch
    TILE_DEFAULT   = TILE_STANDARD

    def __init__(self, parent, app, role="Admin"):
        super().__init__(parent, role)
        self.app = app
        self._map_widget   = None
        self._markers      = []          # list of active marker objects
        self._target_marker = None       # temporary fly-to pin
        self._satellite_mode = True
        self._map_data     = []          # cached query results
        self._marker_imgs  = {}          # PhotoImage cache (prevent GC)
        self._popup_win    = None        # current popup Toplevel

        if not MAP_OK:
            self._build_fallback()
        else:
            self._build_map()

    # ── Fallback UI when tkintermapview is missing ────────
    def _build_fallback(self):
        self.section_label("🗺  Global Defense Map", "tkintermapview library not installed")
        self.divider()
        card = tk.Frame(self, bg=BG_PANEL)
        card.pack(expand=True, fill=tk.BOTH, padx=60, pady=40)
        tk.Label(card, text="🗺", bg=BG_PANEL, fg=NEON_CYAN,
                 font=("Segoe UI", 48)).pack(pady=(30, 8))
        tk.Label(card, text="Global Defense Map requires tkintermapview",
                 bg=BG_PANEL, fg=TXT_BRIGHT,
                 font=("Segoe UI", 14, "bold")).pack()
        tk.Label(card, text="Install it once with:\n\npip install tkintermapview Pillow",
                 bg=BG_PANEL, fg=NEON_AMBER,
                 font=("Consolas", 12), justify="center").pack(pady=16)
        tk.Label(card,
                 text="After installing, restart the application.\n"
                      "The map will display all 50 observatories with\n"
                      "risk-coded neon markers and click-to-view popup cards.",
                 bg=BG_PANEL, fg=TXT_MUTED,
                 font=FONT_SMALL, justify="center").pack(pady=(0, 24))

        # Show a static data table as fallback
        self._build_static_table()

    def _build_static_table(self):
        """Show observatory data as a table when map is unavailable."""
        tk.Label(self, text="Observatory Data (static view — map requires tkintermapview)",
                 bg=CONTENT_BG, fg=TXT_MUTED, font=FONT_SMALL).pack(anchor="w", padx=16, pady=(4, 2))
        cols = ("ID", "Name", "Country", "Lat", "Lon", "Discoveries", "High-Risk?", "Largest Find")
        self.tv_fallback = make_treeview(self, cols, height=14)
        for c, w in zip(cols, (50, 240, 120, 80, 80, 90, 90, 200)):
            self.tv_fallback.heading(c, text=c)
            self.tv_fallback.column(c, width=w, anchor="center")
        self._load_table_data()

    def _load_table_data(self):
        data = self._query_map_data()
        if not hasattr(self, "tv_fallback"):
            return
        self.tv_fallback.delete(*self.tv_fallback.get_children())
        for i, row in enumerate(data):
            hr = "⚠ YES" if row["high_risk"] else "—"
            tag = "crit_risk" if row["high_risk"] else ("alt" if i % 2 else "")
            self.tv_fallback.insert("", "end", tags=(tag,), values=(
                row["obs_id"], row["name"], row["country"],
                f"{row['lat']:.4f}" if row["lat"] else "—",
                f"{row['lon']:.4f}" if row["lon"] else "—",
                row["discoveries"],
                hr,
                row["largest_asteroid"] or "—",
            ))

    # ── Main map build ────────────────────────────────────
    def _build_map(self):
        # Header row
        hdr = tk.Frame(self, bg=CONTENT_BG)
        hdr.pack(fill=tk.X, padx=16, pady=(10, 4))
        tk.Label(hdr, text="🗺  Global Defense Map", bg=CONTENT_BG,
                 fg=TXT_BRIGHT, font=FONT_TITLE).pack(side=tk.LEFT, anchor="w")
        tk.Label(hdr, text="  All observatories · risk-coded markers · click for details",
                 bg=CONTENT_BG, fg=TXT_MUTED, font=FONT_SMALL).pack(side=tk.LEFT, anchor="w")

        # Controls bar (styled overlay)
        ctrl = tk.Frame(self, bg=BG_PANEL, pady=4)
        ctrl.pack(fill=tk.X, padx=16, pady=(0, 4))

        btn(ctrl, "🛰  Satellite", self._use_satellite, NEON_CYAN, BG_DEEP).pack(side=tk.LEFT, padx=4)
        btn(ctrl, "🌍  Standard",  self._use_standard,  TXT_MUTED,  BG_DEEP).pack(side=tk.LEFT, padx=4)

        tk.Frame(ctrl, bg=TXT_DIM, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)

        btn(ctrl, "🔄  Reload Markers", self._reload_markers, NEON_GREEN, BG_DEEP).pack(side=tk.LEFT, padx=4)
        btn(ctrl, "🌐  Reset View",     self._reset_view,     NEON_BLUE,  BG_DEEP).pack(side=tk.LEFT, padx=4)
        btn(ctrl, "✖  Clear Target",   self._clear_target,   NEON_AMBER, BG_DEEP).pack(side=tk.LEFT, padx=4)

        tk.Frame(ctrl, bg=TXT_DIM, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)

        # Legend
        tk.Label(ctrl, text="●", bg=BG_PANEL, fg=NEON_GREEN,
                 font=("Segoe UI", 14)).pack(side=tk.LEFT, padx=(4, 1))
        tk.Label(ctrl, text="Safe", bg=BG_PANEL, fg=TXT_MUTED,
                 font=FONT_SMALL).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(ctrl, text="●", bg=BG_PANEL, fg=NEON_RED,
                 font=("Segoe UI", 14)).pack(side=tk.LEFT, padx=(4, 1))
        tk.Label(ctrl, text="High-Risk", bg=BG_PANEL, fg=TXT_MUTED,
                 font=FONT_SMALL).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(ctrl, text="⊕", bg=BG_PANEL, fg=NEON_AMBER,
                 font=("Segoe UI", 14)).pack(side=tk.LEFT, padx=(4, 1))
        tk.Label(ctrl, text="Fly-To Target", bg=BG_PANEL, fg=TXT_MUTED,
                 font=FONT_SMALL).pack(side=tk.LEFT)

        # HUD Telemetry bar (v3 feature — shows live station data on marker click)
        hud_frame = tk.Frame(self, bg=BG_SPACE, pady=4)
        hud_frame.pack(fill=tk.X, padx=16, pady=(0, 2))
        tk.Label(hud_frame, text="TELEMETRY ›", bg=BG_SPACE, fg=TXT_DIM,
                 font=("Consolas", 9, "bold")).pack(side=tk.LEFT, padx=(8, 4))
        self.hud_label = tk.Label(
            hud_frame,
            text="SELECT A STATION MARKER TO INITIALIZE TELEMETRY…",
            bg=BG_SPACE, fg=NEON_GREEN,
            font=("Consolas", 9, "bold"),
            anchor="w",
        )
        self.hud_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # Status bar
        self._status_lbl = tk.Label(self, text="Loading map…",
                                    bg=CONTENT_BG, fg=TXT_MUTED, font=FONT_SMALL)
        self._status_lbl.pack(anchor="w", padx=16, pady=2)

        # Map widget container
        map_container = tk.Frame(self, bg=BG_DEEP, bd=0)
        map_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))

        # Instantiate TkinterMapView with larger tile cache for performance
        self._map_widget = tkintermapview.TkinterMapView(
            map_container,
            width=1100, height=580,
            corner_radius=0,
            max_zoom=19,
            use_database_only=False,
        )
        self._map_widget.pack(fill=tk.BOTH, expand=True)

        # Default to OSM standard tiles (faster load); user can switch to satellite
        self._map_widget.set_tile_server(self.TILE_DEFAULT, max_zoom=19)
        self._satellite_mode = False
        self._map_widget.set_position(20, 0)   # centered globally
        self._map_widget.set_zoom(2)

        # Defer marker loading so the map renders first
        self.after(400, self._reload_markers)

    # ── Tile toggle ───────────────────────────────────────
    def _use_satellite(self):
        if self._map_widget:
            self._map_widget.set_tile_server(self.TILE_SATELLITE, max_zoom=19)
            self._satellite_mode = True
            self.status("🛰  Satellite view active", NEON_CYAN)

    def _use_standard(self):
        if self._map_widget:
            self._map_widget.set_tile_server(self.TILE_STANDARD, max_zoom=19)
            self._satellite_mode = False
            self.status("🌍  Standard / OpenStreetMap view active", NEON_GREEN)

    # ── SQL data load ─────────────────────────────────────
    def _query_map_data(self) -> list:
        """
        Comprehensive JOIN query:
          · Observatories ↔ Telescopes ↔ Observations ↔ Asteroids
          · Discovery count per observatory
          · Has ever detected High-Risk asteroid (Risk_ID ≥ 7)?
          · Largest Asteroid (by Diameter) observed from that observatory
          · Lead Scientist (most observations from that observatory)
        """
        conn = get_connection()
        rows = conn.execute("""
            SELECT
                ob.Observatory_ID,
                ob.Name               AS obs_name,
                ob.Country,
                ob.Latitude,
                ob.Longitude,
                COUNT(DISTINCT o.Asteroid_ID)  AS discoveries,
                MAX(CASE WHEN de.Risk_ID >= 7 THEN 1 ELSE 0 END) AS high_risk,
                (
                    SELECT a2.Name
                    FROM Observations o2
                    JOIN Asteroids a2 ON o2.Asteroid_ID = a2.Asteroid_ID
                    JOIN Telescopes t2 ON o2.Telescope_ID = t2.Telescope_ID
                    WHERE t2.Observatory_ID = ob.Observatory_ID
                      AND a2.Diameter IS NOT NULL
                    ORDER BY a2.Diameter DESC
                    LIMIT 1
                ) AS largest_asteroid,
                (
                    SELECT s2.Name
                    FROM Observations o3
                    JOIN Scientists s2 ON o3.Scientist_ID = s2.Scientist_ID
                    JOIN Telescopes t3 ON o3.Telescope_ID = t3.Telescope_ID
                    WHERE t3.Observatory_ID = ob.Observatory_ID
                    GROUP BY s2.Name
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                ) AS lead_scientist
            FROM Observatories ob
            LEFT JOIN Telescopes t     ON t.Observatory_ID = ob.Observatory_ID
            LEFT JOIN Observations o   ON o.Telescope_ID   = t.Telescope_ID
            LEFT JOIN Detection_Events de ON (
                de.Asteroid_ID = o.Asteroid_ID
            )
            WHERE ob.Latitude IS NOT NULL AND ob.Longitude IS NOT NULL
            GROUP BY ob.Observatory_ID
            ORDER BY discoveries DESC, ob.Name
        """).fetchall()
        conn.close()
        result = []
        for r in rows:
            result.append({
                "obs_id":          r[0],
                "name":            r[1],
                "country":         r[2],
                "lat":             r[3],
                "lon":             r[4],
                "discoveries":     r[5],
                "high_risk":       bool(r[6]),
                "largest_asteroid": r[7],
                "lead_scientist":  r[8],
            })
        return result

    # ── Place markers on map ──────────────────────────────
    def _reload_markers(self):
        if not self._map_widget:
            return
        # Clear existing markers
        for m in self._markers:
            try: m.delete()
            except Exception: pass
        self._markers.clear()
        self._marker_imgs.clear()

        self._map_data = self._query_map_data()

        # Pre-build marker images if PIL available
        img_safe    = _make_neon_marker_image(NEON_GREEN, 20)
        img_danger  = _make_neon_marker_image(NEON_RED,   20)
        if img_safe:   self._marker_imgs["safe"]   = img_safe
        if img_danger: self._marker_imgs["danger"] = img_danger

        for obs in self._map_data:
            lat, lon = obs["lat"], obs["lon"]
            is_danger = obs["high_risk"]

            # Build marker text (short)
            marker_text = f"{obs['name'][:22]}"

            # Marker colour string for tkintermapview text markers
            marker_color = NEON_RED if is_danger else NEON_GREEN

            try:
                if PIL_OK and img_safe:
                    icon = self._marker_imgs["danger"] if is_danger else self._marker_imgs["safe"]
                    m = self._map_widget.set_marker(
                        lat, lon,
                        text=marker_text,
                        icon=icon,
                        icon_anchor="center",
                        text_color=marker_color,
                        font=("Consolas", 8),
                        command=lambda marker, data=obs: self._on_marker_click(data),
                    )
                else:
                    m = self._map_widget.set_marker(
                        lat, lon,
                        text=marker_text,
                        marker_color_circle=marker_color,
                        marker_color_outside=BG_DEEP,
                        text_color=marker_color,
                        font=("Consolas", 8),
                        command=lambda marker, data=obs: self._on_marker_click(data),
                    )
                self._markers.append(m)
            except Exception as ex:
                log(f"Marker error for {obs['name']}: {ex}", "warning")

        n_danger = sum(1 for o in self._map_data if o["high_risk"])
        n_safe   = len(self._map_data) - n_danger
        self.status(
            f"✔  {len(self._map_data)} observatories loaded  ·  "
            f"🟢 {n_safe} safe  ·  🔴 {n_danger} high-risk",
            NEON_GREEN
        )
        log(f"Map markers loaded: {len(self._map_data)} observatories")

    # ── Marker popup card ─────────────────────────────────
    def _on_marker_click(self, obs: dict):
        """Show a dark-theme popup card with Consolas monospace stats and update HUD bar."""
        # Update HUD telemetry bar (v3 feature)
        risk_flag = "⚠ HIGH-RISK" if obs["high_risk"] else "✓ NOMINAL"
        hud_text = (
            f"STATION: {obs['name'][:30]}  │  "
            f"COUNTRY: {obs['country']}  │  "
            f"TARGETS: {obs['discoveries']}  │  "
            f"STATUS: {risk_flag}  │  "
            f"LAT: {obs['lat']:.4f}  LON: {obs['lon']:.4f}"
        )
        if hasattr(self, "hud_label"):
            self.hud_label.config(
                text=hud_text,
                fg=NEON_RED if obs["high_risk"] else NEON_GREEN
            )

        # Close any existing popup
        if self._popup_win and self._popup_win.winfo_exists():
            self._popup_win.destroy()

        top = tk.Toplevel(self)
        self._popup_win = top
        top.title(f"📡  {obs['name']}")
        top.configure(bg=BG_PANEL)
        top.resizable(False, False)
        center_window(top, 420, 300)

        # Header band
        is_danger = obs["high_risk"]
        hdr_color = "#200000" if is_danger else "#092010"
        accent    = NEON_RED if is_danger else NEON_GREEN
        icon      = "🔴" if is_danger else "🟢"

        hdr = tk.Frame(top, bg=hdr_color)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text=f"{icon}  {obs['name']}",
                 bg=hdr_color, fg=accent,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(10, 2))
        tk.Label(hdr, text=f"{obs['country']}",
                 bg=hdr_color, fg=TXT_MUTED,
                 font=FONT_SMALL).pack(anchor="w", padx=14, pady=(0, 8))

        # Stats in Consolas
        body = tk.Frame(top, bg=BG_PANEL)
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=10)

        def stat_row(label, value, val_color=TXT_PRIMARY):
            row = tk.Frame(body, bg=BG_PANEL)
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=f"{label:<22}", bg=BG_PANEL, fg=TXT_MUTED,
                     font=("Consolas", 10), anchor="w", width=22).pack(side=tk.LEFT)
            tk.Label(row, text=str(value), bg=BG_PANEL, fg=val_color,
                     font=("Consolas", 10, "bold"), anchor="w").pack(side=tk.LEFT, padx=(4, 0))

        stat_row("Observatory ID:",   obs["obs_id"],       NEON_BLUE)
        stat_row("Coordinates:",
                 f"{obs['lat']:.4f}°N  {obs['lon']:.4f}°E",
                 NEON_CYAN)
        stat_row("Discoveries:",      obs["discoveries"],  NEON_GREEN)
        stat_row("Lead Scientist:",
                 obs["lead_scientist"] or "—",             NEON_PURPLE)
        stat_row("Flagship Discovery:",
                 obs["largest_asteroid"] or "—",           NEON_AMBER)
        stat_row("High-Risk Detected:",
                 "⚠  YES" if is_danger else "✓  No",
                 NEON_RED if is_danger else NEON_GREEN)

        tk.Frame(top, bg=TXT_DIM, height=1).pack(fill=tk.X, padx=14, pady=4)

        # Fly-to button inside popup
        def fly_here():
            top.destroy()
            self.fly_to(obs["lat"], obs["lon"], zoom=10,
                        label=f"📡 {obs['name']}")

        bf = tk.Frame(top, bg=BG_PANEL)
        bf.pack(pady=6)
        btn(bf, "🎯  Fly Here", fly_here, NEON_CYAN, BG_DEEP).pack(side=tk.LEFT, padx=6)
        btn(bf, "  Close  ", top.destroy, MUTED, TXT_PRIMARY).pack(side=tk.LEFT, padx=6)

        log(f"Map popup shown for: {obs['name']}")

    # ── Fly-To (called from Asteroids tab) ───────────────
    def fly_to(self, lat: float, lon: float, zoom: int = 12, label: str = "🎯 Target"):
        """
        Animate the map to (lat, lon) at the given zoom level and
        drop a highlighted temporary 'Target' pin.
        """
        if not self._map_widget:
            return
        # Clear previous target marker
        self._clear_target()

        self._map_widget.set_position(lat, lon)
        self._map_widget.set_zoom(zoom)

        try:
            img_target = _make_neon_marker_image(NEON_AMBER, 24)
            if img_target:
                self._marker_imgs["target"] = img_target
                self._target_marker = self._map_widget.set_marker(
                    lat, lon,
                    text=label,
                    icon=img_target,
                    icon_anchor="center",
                    text_color=NEON_AMBER,
                    font=("Consolas", 9, "bold"),
                )
            else:
                self._target_marker = self._map_widget.set_marker(
                    lat, lon,
                    text=label,
                    marker_color_circle=NEON_AMBER,
                    marker_color_outside=BG_DEEP,
                    text_color=NEON_AMBER,
                    font=("Consolas", 9, "bold"),
                )
        except Exception as ex:
            log(f"fly_to marker error: {ex}", "warning")

        self.status(f"🎯  Flew to {label}  ({lat:.4f}, {lon:.4f})", NEON_AMBER)
        log(f"Map fly-to: {label} ({lat}, {lon}) zoom={zoom}")

    # ── Helper buttons ────────────────────────────────────
    def _reset_view(self):
        if self._map_widget:
            self._map_widget.set_position(20, 0)
            self._map_widget.set_zoom(2)
            self.status("🌐  View reset to global", NEON_BLUE)

    def _clear_target(self):
        if self._target_marker:
            try:
                self._target_marker.delete()
            except Exception:
                pass
            self._target_marker = None
            self.status("✖  Target pin cleared", TXT_MUTED)


# ═══════════════════════════════════════════════════════════
# 23.  MAIN APPLICATION
# ═══════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self, username: str, role: str):
        super().__init__()
        self.username = username
        self.role     = role
        self.title("☄  Asteroid Detection & Tracking System — DBS Project v5.0")
        center_window(self, 1300, 840)
        self.configure(bg=BG_DEEP)
        self.minsize(980, 680)
        apply_global_style()
        self._build_layout()
        self.after(10000, lambda: check_risk_alert(self))

    def _build_layout(self):
        # ── Sidebar ────────────────────────────────────────
        sidebar = tk.Frame(self, bg=BG_DEEP, width=226)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        logo_f = tk.Frame(sidebar, bg=BG_DEEP)
        logo_f.pack(fill=tk.X, pady=(16, 4))
        tk.Label(logo_f, text="☄", bg=BG_DEEP, fg=NEON_CYAN,
                 font=("Segoe UI", 28)).pack()
        tk.Label(logo_f, text="Asteroid Tracker", bg=BG_DEEP, fg=TXT_BRIGHT,
                 font=("Segoe UI", 12, "bold")).pack()
        tk.Label(logo_f, text="Database Systems · IV Sem", bg=BG_DEEP, fg=TXT_MUTED,
                 font=("Segoe UI", 8)).pack(pady=(0, 2))

        tk.Frame(sidebar, bg=TXT_DIM, height=1).pack(fill=tk.X, padx=12, pady=4)

        # ── Content area ───────────────────────────────────
        self.content = tk.Frame(self, bg=CONTENT_BG)
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.pages = {}; self.nav_btns = {}; self._current = "dashboard"

        role = self.role
        nav_items = [
            ("🏠  Dashboard",        "dashboard",  lambda: DashboardTab(self.content, self, role)),
            ("🔎  Global Search",    "search",     lambda: GlobalSearchTab(self.content, self, role)),
            ("☄   Asteroids",        "asteroids",  lambda: AsteroidsTab(self.content, self, role)),
            ("🏛   Observatories",   "obs",        lambda: ObservatoriesTab(self.content, self, role)),
            ("🔭  Telescopes",        "tel",        lambda: TelescopesTab(self.content, self, role)),
            ("👩‍🔬  Scientists",        "sci",        lambda: ScientistsTab(self.content, self, role)),
            ("🚀  Missions",          "mis",        lambda: MissionsTab(self.content, self, role)),
            ("🔗  Ast–Mission Links", "links",      lambda: AstMissionTab(self.content, self, role)),
            ("⚡  Detection Events",  "events",     lambda: DetectionEventsTab(self.content, self, role)),
            ("📡  Observations",      "obs2",       lambda: ObservationsTab(self.content, self, role)),
            ("🎯  Risk Categories",   "risk",       lambda: RiskTab(self.content, self, role)),
            ("🔍  SQL Queries",       "queries",    lambda: QueriesTab(self.content, self, role)),
            ("🔬  Advanced Filter",   "filter",     lambda: FilterTab(self.content, self, role)),
            ("📅  Timeline",          "timeline",   lambda: TimelineTab(self.content, self, role)),
            ("📄  Report Generator",  "report",     lambda: ReportTab(self.content, self, role)),
            ("📊  Charts",            "charts",     lambda: ChartsTab(self.content, self, role)),
            ("🗺  Global Map",        "map",        lambda: GlobalMapTab(self.content, self, role)),
            ("📋  Audit Log",         "audit",      lambda: AuditLogTab(self.content, self, role)),
            ("💥  Collision Sim",     "collision",  lambda: CollisionSimTab(self.content, self, role)),
        ]

        for label, key, factory in nav_items:
            p = factory()
            p.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.pages[key] = p

            nb = tk.Button(
                sidebar, text=label,
                bg=BG_DEEP, fg=SIDEBAR_FG,
                font=("Segoe UI", 10), anchor="w",
                relief="flat", bd=0,
                activebackground=SIDEBAR_SEL, activeforeground=NEON_CYAN,
                padx=16, pady=7, cursor="hand2",
                command=lambda k=key: self.show(k)
            )
            nb.bind("<Enter>", lambda e, b=nb: b.config(bg=SIDEBAR_SEL, fg=NEON_CYAN))
            nb.bind("<Leave>", lambda e, b=nb, k=key: b.config(
                bg=SIDEBAR_SEL if k == self._current else BG_DEEP,
                fg=NEON_CYAN if k == self._current else SIDEBAR_FG))
            nb.pack(fill=tk.X, padx=4, pady=1)
            self.nav_btns[key] = nb

        tk.Frame(sidebar, bg=TXT_DIM, height=1).pack(fill=tk.X, padx=12, pady=6)

        # ── User info & role badge ─────────────────────────
        ROLE_COLORS_MAP = {'Admin': NEON_RED, 'Researcher': NEON_CYAN, 'Public': NEON_GREEN}
        ROLE_ICONS_MAP  = {'Admin': '🔴', 'Researcher': '🔵', 'Public': '🟢'}
        role_color = ROLE_COLORS_MAP.get(self.role, TXT_MUTED)

        user_f = tk.Frame(sidebar, bg=BG_PANEL)
        user_f.pack(fill=tk.X, padx=8, pady=4, ipadx=4, ipady=6)
        tk.Label(user_f, text=f"{ROLE_ICONS_MAP.get(self.role,'')}  {self.username}",
                 bg=BG_PANEL, fg=TXT_BRIGHT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8)
        tk.Label(user_f, text=self.role, bg=BG_PANEL, fg=role_color,
                 font=("Segoe UI", 9)).pack(anchor="w", padx=8)

        tk.Label(sidebar, text="Shreyas G Kamath\nRahul Kumar Mahto\n2024-25",
                 bg=BG_DEEP, fg=TXT_DIM, font=("Segoe UI", 7),
                 justify="center").pack(pady=4)

        self.show("dashboard")

    def show(self, key):
        self._current = key
        for k, p in self.pages.items(): p.lower()
        self.pages[key].lift()
        for k, b in self.nav_btns.items():
            active = k == key
            b.config(bg=SIDEBAR_SEL if active else BG_DEEP,
                     fg=NEON_CYAN if active else SIDEBAR_FG)

    def refresh_dashboard(self):
        if "dashboard" in self.pages:
            try: self.pages["dashboard"].refresh()
            except Exception: pass

    def show_asteroid_detail(self, asteroid_id):
        show_asteroid_detail(self, asteroid_id)


# ═══════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    init_database()

    root = tk.Tk()
    root.withdraw()
    apply_global_style()

    login = LoginWindow(root)
    root.wait_window(login)

    if login.result is None:
        root.destroy()
        sys.exit(0)

    username, role = login.result
    root.destroy()

    app = App(username, role)
    app.mainloop()