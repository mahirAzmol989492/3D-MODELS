#  ------------------------------------------------------------------------
#  CONTROLS  (see also: press 'H' any time for this list on-screen)
#  MOVEMENT        W/S forward-back, A/D strafe, Q/E down-up
#                  LEFT/RIGHT/UP/DOWN arrows = look around (see note above)
#                  mouse wheel = zoom
#  CAMERA          1 free   2 orbit selected   3 DNA-follow   4 reset
#  QUICK LOCATIONS N nucleus  M mitochondria  R ribosome  G golgi  C cell overview
#                  / search-to-fly (type a name, Enter to fly there)
#  INTERACTION     left-click = select (whatever's centered in view)
#                  F interact   I info panel   J labels   Z focus/orbit selection
#                  TAB cycle selection (bonus)
#  DNA PROCESSES   T replication   Y transcription   U translation
#                  P pause/resume animation   +/- animation speed
#  VIEW MODES      X x-ray (approx.)   K cross-section (approx.)
#                  B Brownian motion   V ATP particle flow
#  ADVANCED        5 cytoskeleton   6 vesicle transport   7 trigger mutation
#                  8 cycle DNA packing level (DNA/Chromatin/Chromosome)
#                  9 protein folding   L advance cell cycle (drives mitosis)
#                  , minimap   ; export session summary
#  ENVIRONMENT     . cycle color theme (normal/microscope/dark)
#  MISC            O guided tour   0 quiz   H help   Esc quit (or cancel search)
# ====================================================================================

import math
import random
import time
import os

if os.environ.get("XDG_SESSION_TYPE") == "wayland":
    os.environ["PYOPENGL_PLATFORM"] = "glx"

from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *

# ==================================CONSTANTS=======================================

WINDOW_WIDTH, WINDOW_HEIGHT = 1320, 800
ASPECT = WINDOW_WIDTH / WINDOW_HEIGHT

CELL_RADIUS = 480.0
MOVE_SPEED = 220.0          
LOOK_STEP = 3.0             
TRAVEL_DURATION = 1.2       

ORGANELLES = {
    "nucleus":      {"pos": (0, 0, 0), "radius": 140, "color": (0.55, 0.35, 0.75),
                      "info": "Nucleus: houses the cell's DNA and controls gene expression."},
    "mitochondria": {"pos": (280, 180, 60), "radius": 55, "color": (0.85, 0.35, 0.25),
                      "info": "Mitochondria: the cell's powerhouse, produces ATP energy."},
    "ribosome":     {"pos": (-260, -200, 120), "radius": 22, "color": (0.30, 0.65, 0.95),
                      "info": "Ribosome: synthesizes proteins by translating mRNA."},
    "golgi":        {"pos": (200, -260, -90), "radius": 45, "color": (0.95, 0.75, 0.20),
                      "info": "Golgi Apparatus: modifies, sorts and packages proteins."},
    "er":           {"pos": (-280, 220, -100), "radius": 45, "color": (0.40, 0.85, 0.55),
                      "info": "Endoplasmic Reticulum: builds and transports proteins/lipids."},
   
    "nucleolus":    {"pos": (25, 15, 20), "radius": 30, "color": (0.75, 0.55, 0.90),
                      "info": "Nucleolus: assembles ribosomal subunits inside the nucleus."},
    "lysosome":     {"pos": (-100, 300, -150), "radius": 20, "color": (0.90, 0.40, 0.75),
                      "info": "Lysosome: breaks down waste using digestive enzymes."},
}
TOUR_ORDER = ["nucleus", "mitochondria", "ribosome", "golgi", "er", "lysosome"]

QUIZ_BANK = {
    "nucleus": [("What does the nucleus store?", ["DNA", "ATP", "Lipids"], 0)],
    "mitochondria": [("What does the mitochondria produce?", ["ATP", "mRNA", "Ribosomes"], 0)],
    "ribosome": [("What is a ribosome's job?", ["Protein synthesis", "Digestion", "Photosynthesis"], 0)],
    "golgi": [("What does the Golgi Apparatus do?", ["Packages proteins", "Stores water", "Makes ATP"], 0)],
    "er": [("What does the ER transport?", ["Proteins/lipids", "Oxygen", "Sound"], 0)],
    # --- NEW quiz entries, required so start_quiz() can't KeyError on the new organelles ---
    "nucleolus": [("What is made inside the nucleolus?", ["Ribosomal subunits", "ATP", "Lipids"], 0)],
    "lysosome": [("What do lysosomes contain?", ["Digestive enzymes", "DNA", "Chlorophyll"], 0)],
}

COLOR_THEMES = {
    "normal": 1.00,
    "microscope": 1.35,
    "dark": 0.45,
}

# --- NEW constants for chromosome packing / cell cycle / protein folding / cytoskeleton ---
CELL_CYCLE_PHASES = ["Interphase", "Prophase", "Metaphase", "Anaphase", "Telophase"]
PACKING_NAMES = ["DNA", "Chromatin", "Chromosome"]

PROTEIN_CHAIN_LEN = 10
PROTEIN_UNFOLDED_OFFSETS = [(0.0, 0.0, i * 8.0 - (PROTEIN_CHAIN_LEN - 1) * 4.0) for i in range(PROTEIN_CHAIN_LEN)]
PROTEIN_FOLDED_OFFSETS = []
for _i in range(PROTEIN_CHAIN_LEN):
    _t = _i / (PROTEIN_CHAIN_LEN - 1)
    _angle = _t * 4 * math.pi
    PROTEIN_FOLDED_OFFSETS.append((15 * math.cos(_angle), 15 * math.sin(_angle), _t * 60 - 30))

LYSOSOME_ENZYME_OFFSETS = []
for _i in range(10):
    _a = (2 * math.pi * _i) / 10
    _r = 8 + (_i % 3) * 3
    LYSOSOME_ENZYME_OFFSETS.append((_r * math.cos(_a), _r * math.sin(_a), (_i % 4) - 1.5))

CYTOSKELETON_FIBERS = 10

# ===================================  GAME STATE =====================================
# --- camera ---
camera_mode = "free"                      
free_pos = [0.0, -900.0, 300.0]
free_yaw, free_pitch = 0.0, 10.0      
fovY = 90.0

orbit_target_key = "nucleus"
orbit_angle, orbit_height, orbit_radius = 0.0, 250.0, 400.0

dna_follow_angle = 0.0

camera_travel = None                   

selected_key = "nucleus"
info_panel_visible = False
labels_visible = False
flash_message = ""
flash_message_timer = 0.0

# --- DNA processes ---
NUM_BASE_PAIRS = 42
HELIX_RADIUS = 45.0
HELIX_HEIGHT = 240.0
HELIX_TURNS = 4.0

dna_rotation = 0.0
replication_active, replication_progress = False, 0.0
transcription_active, transcription_progress = False, 0.0
translation_active, translation_progress = False, 0.0
animation_paused = False
process_speed = 1.0

# --- NEW: chromosome packing / cell cycle / mitosis ---
packing_level = 0           
cell_cycle_index = 0        
split_amount = 0.0          

# --- NEW: health / mutation ---
cell_health = 100.0
mutation_count = 0
mutation_flash_timer = 0.0
mutation_highlight_indices = []

# --- NEW: protein folding ---
protein_folding_active = False
protein_folding_progress = 0.0

# --- view modes ---
xray_mode = False
cross_section_mode = False
brownian_mode = False
atp_mode = False
vesicle_mode = False        
cytoskeleton_visible = False 
color_theme = "normal"
help_visible = False

# --- particles ---
brownian_particles = []
atp_particles = []
vesicle_particles = []        # NEW

# --- NEW: minimap ---
minimap_visible = False

# --- NEW: search-to-fly ---
search_active = False
search_buffer = ""

# --- NEW: achievements ---
visited_organelles = set()
all_visited_announced = False

# --- guided tour ---
tour_active = False
tour_index = 0
tour_dwell_timer = 0.0

# --- quiz ---
quiz_active = False
quiz_question = None
quiz_choices = []
quiz_correct = 0
quiz_score = 0
quiz_asked = 0

last_time = time.time()
fps_display = 0.0
_fps_accum_time = 0.0
_fps_accum_frames = 0

# ==================================  MATH HELPERS  ====================================

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def forward_vector(yaw_deg, pitch_deg):
    yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
    return (math.sin(yaw) * math.cos(pitch),
            math.cos(yaw) * math.cos(pitch),
            math.sin(pitch))


def right_vector(yaw_deg):
    yaw = math.radians(yaw_deg)
    return math.cos(yaw), -math.sin(yaw), 0.0


def look_angles_from_direction(dx, dy, dz):
    yaw = math.degrees(math.atan2(dx, dy))
    horiz = math.hypot(dx, dy)
    pitch = math.degrees(math.atan2(dz, horiz))
    return yaw, pitch


def vec_sub(a, b):
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def vec_len(v):
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def lerp(a, b, t):
    return a + (b - a) * t


def theme_color(r, g, b):
    """Approximates 'lighting modes' as a palette multiplier (see header note)."""
    m = COLOR_THEMES[color_theme]
    return clamp(r * m, 0, 1), clamp(g * m, 0, 1), clamp(b * m, 0, 1)


# --(used by the protein-fold)---
def lerp_angle(a, b, t):
    """Shortest-path angle interpolation."""
    diff = (b - a + 180.0) % 360.0 - 180.0
    return a + diff * t


def ease_in_out_cubic(t):
    t = clamp(t, 0.0, 1.0)
    if t < 0.5:
        return 4 * t * t * t
    p = -2 * t + 2
    return 1 - (p * p * p) / 2

# ================================  TEXT (HUD) HELPER  =================================

def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    glColor3f(1, 1, 1)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


def draw_bar(x, y, w, h, fraction, fg_color, bg_color=(0.2, 0.2, 0.2)):
    """NEW: a real filled progress bar, built with GL_QUADS in screen space (the same
    ortho-overlay trick draw_text() uses). Used for the cell-health bar."""
    fraction = clamp(fraction, 0.0, 1.0)

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glColor3f(*bg_color)
    glBegin(GL_QUADS)
    glVertex3f(x, y, 0)
    glVertex3f(x + w, y, 0)
    glVertex3f(x + w, y + h, 0)
    glVertex3f(x, y + h, 0)
    glEnd()

    glColor3f(*fg_color)
    glBegin(GL_QUADS)
    glVertex3f(x, y, 0)
    glVertex3f(x + w * fraction, y, 0)
    glVertex3f(x + w * fraction, y + h, 0)
    glVertex3f(x, y + h, 0)
    glEnd()

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

# ================================  CAMERA  =============================================

def eye_and_target():
    """Returns (eye, target) world-space points for the active camera mode."""
    if camera_mode == "orbit":
        target = ORGANELLES[orbit_target_key]["pos"]
        rad = math.radians(orbit_angle)
        eye = (target[0] + orbit_radius * math.sin(rad),
               target[1] + orbit_radius * math.cos(rad),
               target[2] + orbit_height)
        return eye, target

    if camera_mode == "dna_follow":
        nucleus_pos = ORGANELLES["nucleus"]["pos"]
        rad = math.radians(dna_follow_angle)
        radius = HELIX_RADIUS + 90
        eye = (nucleus_pos[0] + radius * math.sin(rad),
               nucleus_pos[1] + radius * math.cos(rad),
               nucleus_pos[2] + 20)
        return eye, nucleus_pos

    # free camera
    fx, fy, fz = forward_vector(free_yaw, free_pitch)
    eye = tuple(free_pos)
    target = (eye[0] + fx * 200, eye[1] + fy * 200, eye[2] + fz * 200)
    return eye, target


def setup_camera():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(fovY, ASPECT, 0.1, 3000)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    eye, target = eye_and_target()
    gluLookAt(eye[0], eye[1], eye[2], target[0], target[1], target[2], 0, 0, 1)


def start_travel(target_eye, target_look, label):
    global camera_travel, camera_mode
    camera_mode = "free"
    yaw, pitch = look_angles_from_direction(*vec_sub(target_look, target_eye))
    camera_travel = {
        "start_pos": list(free_pos), "start_yaw": free_yaw, "start_pitch": free_pitch,
        "end_pos": list(target_eye), "end_yaw": yaw, "end_pitch": pitch,
        "start_time": time.time(), "duration": TRAVEL_DURATION, "label": label,
    }


def teleport_to(key):
    if key == "cell":
        start_travel((0, -CELL_RADIUS * 1.6, 250), (0, 0, 0), "Cell Overview")
        return
    org = ORGANELLES[key]
    pos = org["pos"]
    length = vec_len(pos) or 1.0
    dir_x, dir_y, dir_z = (pos[0] / length, pos[1] / length, pos[2] / length) if length > 1 else (0, -1, 0.3)
    dist = org["radius"] + 150
    viewpoint = (pos[0] + dir_x * dist, pos[1] + dir_y * dist, pos[2] + dir_z * dist)
    start_travel(viewpoint, pos, key.title())


def update_travel(dt):
    global camera_travel, free_pos, free_yaw, free_pitch
    if camera_travel is None:
        return
    t = clamp((time.time() - camera_travel["start_time"]) / camera_travel["duration"], 0, 1)
    free_pos[0] = lerp(camera_travel["start_pos"][0], camera_travel["end_pos"][0], t)
    free_pos[1] = lerp(camera_travel["start_pos"][1], camera_travel["end_pos"][1], t)
    free_pos[2] = lerp(camera_travel["start_pos"][2], camera_travel["end_pos"][2], t)
    free_yaw = lerp(camera_travel["start_yaw"], camera_travel["end_yaw"], t)
    free_pitch = lerp(camera_travel["start_pitch"], camera_travel["end_pitch"], t)
    if t >= 1.0:
        set_flash(f"Arrived: {camera_travel['label']}")
        camera_travel = None


def set_flash(msg, duration=2.5):
    global flash_message, flash_message_timer
    flash_message = msg
    flash_message_timer = duration


def compute_in_view_selection():
    """Approximates 'click to select' (see header note): picks whichever organelle
    is closest to dead-center of the current view direction."""
    eye, target = eye_and_target()
    fx, fy, fz = (target[0] - eye[0], target[1] - eye[1], target[2] - eye[2])
    flen = vec_len((fx, fy, fz)) or 1.0
    fx, fy, fz = fx / flen, fy / flen, fz / flen

    best_key, best_dot = None, 0.75  # cos(~41 degrees) minimum "in view" threshold
    for key, org in ORGANELLES.items():
        dx, dy, dz = vec_sub(org["pos"], eye)
        dlen = vec_len((dx, dy, dz)) or 1.0
        dot = (dx * fx + dy * fy + dz * fz) / dlen
        if dot > best_dot:
            best_dot, best_key = dot, key
    return best_key


# --- NEW: achievements + search-to-fly ---
def track_visit(key):
    """Records that the player has looked at/selected an organelle, and announces
    an achievement once every organelle has been visited."""
    global all_visited_announced
    if key is None:
        return
    visited_organelles.add(key)
    if not all_visited_announced and len(visited_organelles) == len(ORGANELLES):
        all_visited_announced = True
        print("Achievement: explored every organelle in the cell!")
        set_flash("Achievement unlocked: Full Cell Tour!")


def search_match(query):
    """Finds the best organelle name match for a typed search query. No text-input
    widget exists under the function whitelist, so keyboardListener() captures
    letters directly into search_buffer instead (see below)."""
    query = query.lower().strip()
    if not query:
        return None
    for key in ORGANELLES:
        if key.startswith(query):
            return key
    for key in ORGANELLES:
        if query in key:
            return key
    return None


def submit_search():
    global search_active, search_buffer, selected_key, info_panel_visible
    match = search_match(search_buffer)
    if match:
        selected_key = match
        info_panel_visible = True
        track_visit(match)
        teleport_to(match)
        print(f"Search: flying to '{match}'")
    else:
        set_flash(f"No organelle matches '{search_buffer}'")
    search_active = False
    search_buffer = ""

# ==============================  CELL MEMBRANE / GRID  ================================

def draw_membrane():
    
    r, g, b = theme_color(0.55, 0.75, 0.95)

    if xray_mode or cross_section_mode:
        glColor3f(r, g, b)
        glPointSize(2)
        glBegin(GL_POINTS)
        lat_steps, lon_steps = 24, 36
        for i in range(lat_steps):
            theta = math.pi * i / (lat_steps - 1) - math.pi / 2
            for j in range(lon_steps):
                phi = 2 * math.pi * j / lon_steps
                x = CELL_RADIUS * math.cos(theta) * math.sin(phi)
                y = CELL_RADIUS * math.cos(theta) * math.cos(phi)
                z = CELL_RADIUS * math.sin(theta)
                if cross_section_mode and x > 0:
                    continue
                glVertex3f(x, y, z)
        glEnd()
    else:
        glColor3f(r, g, b)
        glPushMatrix()
        gluSphere(gluNewQuadric(), CELL_RADIUS, 24, 24)
        glPopMatrix()


# ==================================  ORGANELLES  ======================================

def draw_nucleus(org):
    r, g, b = theme_color(*org["color"])
    if xray_mode:
        draw_point_sphere(org["radius"], (r, g, b), lat_steps=14, lon_steps=20)
    else:
        glColor3f(r, g, b)
        gluSphere(gluNewQuadric(), org["radius"], 18, 18)


def draw_mitochondria(org):
    r, g, b = theme_color(*org["color"])
    glPushMatrix()
    glScalef(1.6, 1.0, 0.9)
    if xray_mode:
        draw_point_sphere(org["radius"], (r, g, b))
    else:
        glColor3f(r, g, b)
        gluSphere(gluNewQuadric(), org["radius"], 14, 14)
    glPopMatrix()
    # a couple of small inner "cristae" folds
    glColor3f(*theme_color(0.6, 0.2, 0.15))
    for i in (-1, 1):
        glPushMatrix()
        glTranslatef(i * org["radius"] * 0.5, 0, 0)
        glRotatef(90, 0, 1, 0)
        gluCylinder(gluNewQuadric(), org["radius"] * 0.25, org["radius"] * 0.25, org["radius"] * 0.4, 8, 4)
        glPopMatrix()


def draw_ribosome(org):
    r, g, b = theme_color(*org["color"])
    glColor3f(r, g, b)
    glPushMatrix()
    glTranslatef(0, 0, org["radius"] * 0.3)
    gluSphere(gluNewQuadric(), org["radius"], 10, 10)      # large subunit
    glPopMatrix()
    glColor3f(*theme_color(0.6, 0.85, 1.0))
    glPushMatrix()
    glTranslatef(0, 0, -org["radius"] * 0.6)
    gluSphere(gluNewQuadric(), org["radius"] * 0.65, 10, 10)  # small subunit
    glPopMatrix()


def draw_golgi(org):
    
    r, g, b = theme_color(*org["color"])
    glColor3f(r, g, b)
    layers = 6
    for i in range(layers):
        shrink = 1.0 - i * 0.1
        glPushMatrix()
        glTranslatef(0, 0, -org["radius"] * 0.5 + i * (org["radius"] * 0.18))
        glScalef(1.6 * shrink, 0.6 * shrink, 0.12)
        glutSolidCube(org["radius"])
        glPopMatrix()


def draw_er(org):

    r, g, b = theme_color(*org["color"])
    glColor3f(r, g, b)
    segments = 14
    for i in range(segments):
        t = i / (segments - 1)
        x = (t - 0.5) * org["radius"] * 3.2
        y = math.sin(t * 4 * math.pi) * org["radius"] * 0.7
        z = math.cos(t * 3 * math.pi) * org["radius"] * 0.4
        glPushMatrix()
        glTranslatef(x, y, z)
        gluSphere(gluNewQuadric(), org["radius"] * 0.3, 8, 8)
        glPopMatrix()


# --- NEW organelle drawers ---
def draw_nucleolus(org):
    r, g, b = theme_color(*org["color"])
    glColor3f(r, g, b)
    gluSphere(gluNewQuadric(), org["radius"], 10, 10)


def draw_lysosome(org):
    r, g, b = theme_color(*org["color"])
    glColor3f(r, g, b)
    gluSphere(gluNewQuadric(), org["radius"], 10, 10)
    glColor3f(*theme_color(1.0, 1.0, 1.0))
    glPointSize(2)
    glBegin(GL_POINTS)
    for ox, oy, oz in LYSOSOME_ENZYME_OFFSETS:
        glVertex3f(ox, oy, oz)
    glEnd()


ORGANELLE_DRAWERS = {
    "nucleus": draw_nucleus, "mitochondria": draw_mitochondria, "ribosome": draw_ribosome,
    "golgi": draw_golgi, "er": draw_er,
    "nucleolus": draw_nucleolus, "lysosome": draw_lysosome,   # NEW
}


def draw_point_sphere(radius, color, lat_steps=14, lon_steps=20):
    """Shared X-Ray point-cloud renderer used by every organelle in X-Ray mode."""
    glColor3f(*color)
    glPointSize(3)
    glBegin(GL_POINTS)
    for i in range(lat_steps):
        theta = math.pi * i / (lat_steps - 1) - math.pi / 2
        for j in range(lon_steps):
            phi = 2 * math.pi * j / lon_steps
            x = radius * math.cos(theta) * math.sin(phi)
            y = radius * math.cos(theta) * math.cos(phi)
            z = radius * math.sin(theta)
            glVertex3f(x, y, z)
    glEnd()


def draw_organelle(key):
    org = ORGANELLES[key]
    if cross_section_mode and org["pos"][0] > 0:
        return
    glPushMatrix()
    glTranslatef(*org["pos"])
    if key == selected_key:
        glScalef(1.08, 1.08, 1.08)   # a gentle "highlight" pulse substitute (see note below)
    ORGANELLE_DRAWERS[key](org)
    glPopMatrix()


# ==================================== DNA============================================

def generate_dna_strands():
    """Builds the double-helix backbone points with a loop (dynamic, per spec)."""
    strand1, strand2 = [], []
    for i in range(NUM_BASE_PAIRS):
        frac = i / (NUM_BASE_PAIRS - 1)
        z = -HELIX_HEIGHT / 2 + frac * HELIX_HEIGHT
        angle = frac * HELIX_TURNS * 2 * math.pi
        strand1.append((HELIX_RADIUS * math.cos(angle), HELIX_RADIUS * math.sin(angle), z))
        strand2.append((HELIX_RADIUS * math.cos(angle + math.pi), HELIX_RADIUS * math.sin(angle + math.pi), z))
    return strand1, strand2


def draw_dna_rung(p1, p2, color):
    """A 'dotted rung' connecting two backbone points, drawn purely with GL_POINTS."""
    glColor3f(*color)
    glPointSize(2)
    glBegin(GL_POINTS)
    steps = 6
    for s in range(steps + 1):
        t = s / steps
        glVertex3f(lerp(p1[0], p2[0], t), lerp(p1[1], p2[1], t), lerp(p1[2], p2[2], t))
    glEnd()


def draw_dna_helix():
    """This is the ORIGINAL draw_dna() body, unchanged, just moved into its own
    function so packing levels (below) can choose between this / chromatin /
    chromosome. The only new line is the mutation-highlight color override on the
    rungs (marked below)."""
    strand1, strand2 = generate_dna_strands()

    fork = None
    if replication_active:
        fork = -HELIX_HEIGHT / 2 + replication_progress * HELIX_HEIGHT

    for i, (p1, p2) in enumerate(zip(strand1, strand2)):
        split = 0.0
        color1 = theme_color(0.25, 0.55, 0.95)
        color2 = theme_color(0.95, 0.35, 0.45)
        if fork is not None and p1[2] < fork:
            split = 26.0   # visually pull the two new strands apart behind the fork
            color1 = theme_color(0.3, 0.9, 0.4)
            color2 = theme_color(0.6, 1.0, 0.5)

        p1s = (p1[0] - split, p1[1], p1[2])
        p2s = (p2[0] + split, p2[1], p2[2])

        glColor3f(*color1)
        glPushMatrix(); glTranslatef(*p1s); gluSphere(gluNewQuadric(), 5, 8, 8); glPopMatrix()
        glColor3f(*color2)
        glPushMatrix(); glTranslatef(*p2s); gluSphere(gluNewQuadric(), 5, 8, 8); glPopMatrix()

        if i % 2 == 0:
            rung_color = theme_color(0.85, 0.85, 0.85)
            if mutation_flash_timer > 0 and i in mutation_highlight_indices:   # NEW
                rung_color = (1.0, 0.15, 0.15)                                  # NEW
            draw_dna_rung(p1s, p2s, rung_color)

    if replication_active and fork is not None:
        glColor3f(*theme_color(1.0, 0.85, 0.1))
        glPushMatrix()
        glTranslatef(HELIX_RADIUS + 20, 0, fork)
        glutSolidCube(14)
        glPopMatrix()

    if transcription_active:
        z = -HELIX_HEIGHT / 2 + transcription_progress * HELIX_HEIGHT
        glColor3f(*theme_color(1.0, 0.6, 0.1))
        glPushMatrix(); glTranslatef(HELIX_RADIUS + 15, 0, z); gluSphere(gluNewQuadric(), 9, 8, 8); glPopMatrix()
        # growing mRNA strand trailing behind the polymerase
        glColor3f(*theme_color(0.3, 1.0, 0.5))
        glPointSize(3)
        glBegin(GL_POINTS)
        trail_steps = int(40 * transcription_progress)
        for s in range(trail_steps):
            t = s / 40.0
            tz = -HELIX_HEIGHT / 2 + t * HELIX_HEIGHT
            glVertex3f(HELIX_RADIUS + 30, 0, tz)
        glEnd()

def draw_chromatin():
    
    beads = 16
    glColor3f(*theme_color(0.5, 0.4, 0.8))
    for i in range(beads):
        frac = i / (beads - 1)
        z = -HELIX_HEIGHT / 2 + frac * HELIX_HEIGHT
        angle = frac * 2 * 2 * math.pi
        radius = HELIX_RADIUS * 1.8
        x, y = radius * math.cos(angle), radius * math.sin(angle)
        glPushMatrix(); glTranslatef(x, y, z); gluSphere(gluNewQuadric(), 10, 8, 8); glPopMatrix()


def draw_chromosome():
   
    glColor3f(*theme_color(0.7, 0.25, 0.65))
    length = HELIX_HEIGHT * 0.5
    for side in (-1, 1):
        glPushMatrix()
        glRotatef(side * 20, 1, 0, 0)
        glTranslatef(0, 0, -length / 2)
        gluCylinder(gluNewQuadric(), 14, 14, length, 10, 4)
        glPopMatrix()
    glColor3f(*theme_color(0.95, 0.85, 0.3))
    glPushMatrix(); gluSphere(gluNewQuadric(), 16, 10, 10); glPopMatrix()


def draw_dna(nucleus_pos):
    glPushMatrix()
    glTranslatef(*nucleus_pos)
    glRotatef(dna_rotation, 0, 0, 1)

    if packing_level == 0:            
        draw_dna_helix()              
    elif packing_level == 1:
        draw_chromatin()
    else:
        draw_chromosome()

    glPopMatrix()


def draw_dividing_nucleus():
   
    base = ORGANELLES["nucleus"]["pos"]
    offset = split_amount * 180.0
    scale = 1.0 - split_amount * 0.35
    r, g, b = theme_color(*ORGANELLES["nucleus"]["color"])

    for side in (-1, 1):
        pos = (base[0] + side * offset, base[1], base[2])
        glPushMatrix()
        glTranslatef(*pos)
        glScalef(scale, scale, scale)
        glColor3f(r, g, b)
        gluSphere(gluNewQuadric(), ORGANELLES["nucleus"]["radius"], 16, 16)
        glPopMatrix()
        draw_dna(pos)

# ==============================  RIBOSOME / TRANSLATION  =============================

def draw_translation(ribosome_pos):
    if not translation_active:
        return
    chain_len = int(10 * translation_progress)
    glColor3f(*theme_color(0.9, 0.5, 0.9))
    for i in range(chain_len):
        glPushMatrix()
        glTranslatef(ribosome_pos[0], ribosome_pos[1] + 25 + i * 8, ribosome_pos[2])
        glutSolidCube(6)
        glPopMatrix()


def draw_protein_folding(ribosome_pos):
    """NEW: a short amino-acid chain that animates from a straight line into a
    folded coil, eased with ease_in_out_cubic for a smoother finish than linear
    motion would give."""
    if protein_folding_progress <= 0:
        return
    t = ease_in_out_cubic(protein_folding_progress)
    base_x, base_y, base_z = ribosome_pos[0] - 70, ribosome_pos[1], ribosome_pos[2]
    glColor3f(*theme_color(0.95, 0.75, 0.15))
    for i in range(PROTEIN_CHAIN_LEN):
        ux, uy, uz = PROTEIN_UNFOLDED_OFFSETS[i]
        fx, fy, fz = PROTEIN_FOLDED_OFFSETS[i]
        x, y, z = lerp(ux, fx, t), lerp(uy, fy, t), lerp(uz, fz, t)
        glPushMatrix()
        glTranslatef(base_x + x, base_y + y, base_z + z)
        gluSphere(gluNewQuadric(), 6, 8, 8)
        glPopMatrix()

# ===============================  CYTOSKELETON (NEW)  =================================

def draw_cytoskeleton():
    """A dynamically-generated fiber network radiating from the nucleus toward the
    membrane, built with nested loops (not hardcoded), drawn purely with GL_POINTS."""
    if not cytoskeleton_visible:
        return
    glColor3f(*theme_color(0.5, 0.5, 0.55))
    glPointSize(1)
    glBegin(GL_POINTS)
    for i in range(CYTOSKELETON_FIBERS):
        theta = 2 * math.pi * i / CYTOSKELETON_FIBERS
        phi = math.pi * ((i * 37) % 10) / 10 - math.pi / 2   
        dx = math.cos(phi) * math.cos(theta)
        dy = math.cos(phi) * math.sin(theta)
        dz = math.sin(phi)
        steps = 40
        for s in range(steps):
            t = s / steps
            radius = 150 + t * (CELL_RADIUS - 160)
            glVertex3f(dx * radius, dy * radius, dz * radius)
    glEnd()

# ===================================  PARTICLES  ======================================

def init_brownian_particles(n=60):
    brownian_particles.clear()
    for _ in range(n):
        x = random.uniform(-CELL_RADIUS * 0.85, CELL_RADIUS * 0.85)
        y = random.uniform(-CELL_RADIUS * 0.85, CELL_RADIUS * 0.85)
        z = random.uniform(-CELL_RADIUS * 0.85, CELL_RADIUS * 0.85)
        brownian_particles.append({"x": x, "y": y, "z": z, "hx": x, "hy": y, "hz": z})


def update_brownian(dt):
    for p in brownian_particles:
        p["x"] += random.uniform(-1, 1) * 20 * dt + (p["hx"] - p["x"]) * 0.3 * dt
        p["y"] += random.uniform(-1, 1) * 20 * dt + (p["hy"] - p["y"]) * 0.3 * dt
        p["z"] += random.uniform(-1, 1) * 20 * dt + (p["hz"] - p["z"]) * 0.3 * dt


def draw_brownian():
    if not brownian_mode:
        return
    glColor3f(*theme_color(0.8, 0.8, 0.3))
    glPointSize(3)
    glBegin(GL_POINTS)
    for p in brownian_particles:
        glVertex3f(p["x"], p["y"], p["z"])
    glEnd()


def spawn_atp():
    start = ORGANELLES["mitochondria"]["pos"]
    dest_key = random.choice([k for k in ORGANELLES if k != "mitochondria"])
    dest = ORGANELLES[dest_key]["pos"]
    atp_particles.append({"start": start, "end": dest, "t": 0.0})


def update_atp(dt):
    if atp_mode and random.random() < dt * 1.5:
        spawn_atp()
    for p in atp_particles:
        p["t"] += dt * 0.4
    atp_particles[:] = [p for p in atp_particles if p["t"] < 1.0]


def draw_atp():
    glColor3f(*theme_color(1.0, 1.0, 0.2))
    glPointSize(6)
    glBegin(GL_POINTS)
    for p in atp_particles:
        x = lerp(p["start"][0], p["end"][0], p["t"])
        y = lerp(p["start"][1], p["end"][1], p["t"])
        z = lerp(p["start"][2], p["end"][2], p["t"])
        glVertex3f(x, y, z)
    glEnd()


# --- NEW: vesicle transport (Golgi/ER <-> membrane), same shape as ATP above ---
def spawn_vesicle():
    start_key = random.choice(["golgi", "er"])
    start = ORGANELLES[start_key]["pos"]
    if random.random() < 0.5:
        theta, phi = random.uniform(0, 2 * math.pi), random.uniform(-math.pi / 2, math.pi / 2)
        end = (CELL_RADIUS * math.cos(phi) * math.cos(theta),
               CELL_RADIUS * math.cos(phi) * math.sin(theta),
               CELL_RADIUS * math.sin(phi))
    else:
        other = "er" if start_key == "golgi" else "golgi"
        end = ORGANELLES[other]["pos"]
    vesicle_particles.append({"start": start, "end": end, "t": 0.0})


def update_vesicles(dt):
    if vesicle_mode and random.random() < dt * 1.2:
        spawn_vesicle()
    for p in vesicle_particles:
        p["t"] += dt * 0.3
    vesicle_particles[:] = [p for p in vesicle_particles if p["t"] < 1.0]


def draw_vesicles():
    glColor3f(*theme_color(0.9, 0.6, 0.2))
    glPointSize(5)
    glBegin(GL_POINTS)
    for p in vesicle_particles:
        x = lerp(p["start"][0], p["end"][0], p["t"])
        y = lerp(p["start"][1], p["end"][1], p["t"])
        z = lerp(p["start"][2], p["end"][2], p["t"])
        glVertex3f(x, y, z)
    glEnd()


# ==========================  HEALTH / MUTATION (NEW)  =================================

def trigger_mutation():
    global cell_health, mutation_count, mutation_flash_timer, mutation_highlight_indices
    dmg = random.uniform(5, 15)
    cell_health = clamp(cell_health - dmg, 0, 100)
    mutation_count += 1
    mutation_flash_timer = 1.0
    mutation_highlight_indices = random.sample(range(NUM_BASE_PAIRS), k=min(3, NUM_BASE_PAIRS))
    kind = random.choice(["Point mutation", "Insertion", "Deletion"])
    print(f"Mutation occurred: {kind}! Cell health: {cell_health:.0f}%")
    set_flash(f"{kind}! Health -{dmg:.0f}")


def export_session_summary():
    """NEW: writes a short text summary of the session to disk, using Python's
    built-in open() (not an OpenGL/GLUT function, so it's unaffected by the
    whitelist) -- the closest available substitute for a real screenshot, since
    glReadPixels isn't in the whitelist."""
    try:
        with open("session_summary.txt", "w") as f:
            f.write("3D DNA / Cell Explorer -- Session Summary\n")
            f.write("=" * 42 + "\n")
            f.write(f"Cell health: {cell_health:.0f}%\n")
            f.write(f"Mutations triggered: {mutation_count}\n")
            f.write(f"Quiz score: {quiz_score}/{quiz_asked}\n")
            f.write(f"Cell cycle phase: {CELL_CYCLE_PHASES[cell_cycle_index]}\n")
            f.write(f"DNA packing level: {PACKING_NAMES[packing_level]}\n")
            f.write(f"Organelles visited: {len(visited_organelles)}/{len(ORGANELLES)}\n")
            f.write(", ".join(sorted(visited_organelles)) + "\n")
        print("Session summary written to session_summary.txt")
        set_flash("Session summary saved!")
    except OSError as exc:
        print(f"Could not write session summary: {exc}")

# ========================  CELL CYCLE / MITOSIS (NEW)  ================================


def advance_cell_cycle():
    global cell_cycle_index, packing_level
    cell_cycle_index = (cell_cycle_index + 1) % len(CELL_CYCLE_PHASES)
    phase = CELL_CYCLE_PHASES[cell_cycle_index]
    if phase == "Interphase":
        packing_level = 0
    elif phase == "Prophase":
        packing_level = 1
    else:
        packing_level = 2
    print(f"Cell cycle phase: {phase}")
    set_flash(f"Phase: {phase}")

# ==================================  HUD / OVERLAY  ===================================

HELP_LINES = [
    "MOVEMENT: W/S forward-back  A/D strafe  Q/E down-up  Arrows=look  Wheel=zoom",
    "CAMERA: 1 free  2 orbit  3 dna-follow  4 reset",
    "LOCATIONS: N M R G  C=overview   / search-to-fly",
    "INTERACT: click/F=select+interact  I=info  J=labels  Z=focus  Tab=cycle",
    "DNA: T replication  Y transcription  U translation  P pause  +/- speed",
    "VIEW: X x-ray  K cross-section  B brownian  V atp flow  , minimap",
    "ADVANCED: 5 cytoskeleton  6 vesicles  7 mutate  8 packing level  9 fold protein  L cell cycle",
    "ENV: . cycle theme (normal/microscope/dark)   O tour   0 quiz   ; export   Esc quit",
]


def draw_minimap():
    
    if not minimap_visible:
        return

    panel_x, panel_y, panel_size = WINDOW_WIDTH - 170, 20, 150
    scale = (panel_size * 0.5) / CELL_RADIUS

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glColor3f(0.05, 0.05, 0.08)
    glBegin(GL_QUADS)
    glVertex3f(panel_x, panel_y, 0)
    glVertex3f(panel_x + panel_size, panel_y, 0)
    glVertex3f(panel_x + panel_size, panel_y + panel_size, 0)
    glVertex3f(panel_x, panel_y + panel_size, 0)
    glEnd()

    cx, cy = panel_x + panel_size / 2, panel_y + panel_size / 2

    glColor3f(0.35, 0.35, 0.45)
    glPointSize(1)
    glBegin(GL_POINTS)
    circle_steps = 60
    for i in range(circle_steps):
        a = 2 * math.pi * i / circle_steps
        glVertex3f(cx + math.cos(a) * panel_size * 0.48, cy + math.sin(a) * panel_size * 0.48, 0)
    glEnd()

    glPointSize(5)
    glBegin(GL_POINTS)
    for key, org in ORGANELLES.items():
        px = cx + org["pos"][0] * scale
        py = cy + org["pos"][1] * scale
        if key == selected_key:
            glColor3f(1.0, 1.0, 0.3)
        else:
            glColor3f(*theme_color(*org["color"]))
        glVertex3f(px, py, 0)
    glEnd()

    eye, target = eye_and_target()
    px, py = cx + eye[0] * scale, cy + eye[1] * scale
    glColor3f(1.0, 1.0, 1.0)
    glPointSize(6)
    glBegin(GL_POINTS)
    glVertex3f(px, py, 0)
    glEnd()

    heading_dx, heading_dy = target[0] - eye[0], target[1] - eye[1]
    hlen = math.hypot(heading_dx, heading_dy) or 1.0
    glBegin(GL_POINTS)
    for s in range(10):
        t = s / 10.0
        glVertex3f(px + heading_dx / hlen * 14 * t, py + heading_dy / hlen * 14 * t, 0)
    glEnd()

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


def draw_hud():
    draw_text(10, WINDOW_HEIGHT - 25, f"Mode: {camera_mode}   Zoom(FOV): {fovY:.0f}   FPS: {fps_display:.0f}")
    sel = selected_key or "-"
    draw_text(10, WINDOW_HEIGHT - 50, f"Selected: {sel}   Theme: {color_theme}   Speed: {process_speed:.1f}x")
    anim_bits = []
    if replication_active: anim_bits.append("Replication")
    if transcription_active: anim_bits.append("Transcription")
    if translation_active: anim_bits.append("Translation")
    if protein_folding_active: anim_bits.append("Folding")           # NEW
    if animation_paused: anim_bits.append("(PAUSED)")
    draw_text(10, WINDOW_HEIGHT - 75, "Active: " + (", ".join(anim_bits) if anim_bits else "-"))

    # --- NEW: packing level / cell cycle line ---
    draw_text(10, WINDOW_HEIGHT - 100,
              f"DNA View: {PACKING_NAMES[packing_level]}   Cycle: {CELL_CYCLE_PHASES[cell_cycle_index]}")

    # --- NEW: cell health bar ---
    draw_text(10, WINDOW_HEIGHT - 160, f"Cell Health: {cell_health:.0f}%   Mutations: {mutation_count}")
    bar_color = (0.85, 0.2, 0.2) if cell_health < 40 else (0.25, 0.8, 0.35)
    draw_bar(10, WINDOW_HEIGHT - 178, 200, 14, cell_health / 100.0, bar_color)

    if info_panel_visible and selected_key:
        org = ORGANELLES[selected_key]
        draw_text(10, WINDOW_HEIGHT - 210, f"[{selected_key.title()}] r={org['radius']}")
        draw_text(10, WINDOW_HEIGHT - 230, org["info"])

    if labels_visible:
        y = WINDOW_HEIGHT - 270
        draw_text(10, y, "Labels:")
        for i, key in enumerate(ORGANELLES):
            draw_text(20, y - 20 - i * 20, key.title())

    if xray_mode:
        draw_text(WINDOW_WIDTH - 160, WINDOW_HEIGHT - 25, "X-RAY MODE")
    if cross_section_mode:
        draw_text(WINDOW_WIDTH - 220, WINDOW_HEIGHT - 50, "CROSS-SECTION MODE")

    # --- NEW: view-mode status lines ---
    if cytoskeleton_visible:
        draw_text(WINDOW_WIDTH - 220, WINDOW_HEIGHT - 75, "CYTOSKELETON VISIBLE")
    if vesicle_mode:
        draw_text(WINDOW_WIDTH - 220, WINDOW_HEIGHT - 100, "VESICLE TRANSPORT ON")

    if tour_active:
        draw_text(WINDOW_WIDTH / 2 - 100, 40, "Guided Tour in progress...")

    if quiz_active and quiz_question:
        draw_text(WINDOW_WIDTH / 2 - 150, WINDOW_HEIGHT - 400, quiz_question)
        for i, choice in enumerate(quiz_choices):
            draw_text(WINDOW_WIDTH / 2 - 150, WINDOW_HEIGHT - 425 - i * 20, f"{i + 1}) {choice}")
    if quiz_asked:
        draw_text(WINDOW_WIDTH - 160, WINDOW_HEIGHT - 125, f"Quiz: {quiz_score}/{quiz_asked}")

    if flash_message_timer > 0:
        draw_text(WINDOW_WIDTH / 2 - 100, 20, flash_message)

    if help_visible:
        for i, line in enumerate(HELP_LINES):
            draw_text(20, WINDOW_HEIGHT - 450 - i * 22, line)

    # --- NEW: search box + minimap ---
    if search_active:
        draw_text(WINDOW_WIDTH / 2 - 100, WINDOW_HEIGHT / 2, f"Search: {search_buffer}_")
    draw_minimap()

# ==================================  SCENE / DRAW  ====================================
def draw_scene():

    eye, _ = eye_and_target()

    items = [(vec_len(vec_sub(ORGANELLES["nucleus"]["pos"], eye)) + CELL_RADIUS, "membrane", None)]
    for key, org in ORGANELLES.items():
        items.append((vec_len(vec_sub(org["pos"], eye)), "organelle", key))
    if brownian_mode:
        items.append((CELL_RADIUS, "brownian", None))
    if atp_mode:
        items.append((CELL_RADIUS, "atp", None))
    if vesicle_mode:                                          # NEW
        items.append((CELL_RADIUS, "vesicles", None))
    if cytoskeleton_visible:                                    # NEW
        items.append((CELL_RADIUS * 1.2, "cytoskeleton", None))

    items.sort(key=lambda it: it[0], reverse=True)

    for _, kind, key in items:
        if kind == "membrane":
            draw_membrane()
        elif kind == "organelle":
            if key == "nucleus":
                if split_amount > 0.01:
                    draw_dividing_nucleus()
                else:
                    draw_organelle("nucleus")
                    draw_dna(ORGANELLES["nucleus"]["pos"])
            else:
                draw_organelle(key)
                if key == "ribosome":
                    draw_translation(ORGANELLES["ribosome"]["pos"])
                    draw_protein_folding(ORGANELLES["ribosome"]["pos"])   # NEW
        elif kind == "brownian":
            draw_brownian()
        elif kind == "atp":
            draw_atp()
        elif kind == "vesicles":            # NEW
            draw_vesicles()
        elif kind == "cytoskeleton":        # NEW
            draw_cytoskeleton()

# ====================================UPDATE========================================

def start_quiz():
    global quiz_active, quiz_question, quiz_choices, quiz_correct
    key = selected_key or random.choice(list(ORGANELLES))
    q, choices, correct = random.choice(QUIZ_BANK[key])
    quiz_active = True
    quiz_question, quiz_choices, quiz_correct = q, choices, correct


def answer_quiz(choice_index):
    global quiz_active, quiz_score, quiz_asked
    quiz_asked += 1
    if choice_index == quiz_correct:
        quiz_score += 1
        set_flash("Correct!")
    else:
        set_flash(f"Not quite. Correct: {quiz_choices[quiz_correct]}")
    quiz_active = False


def update_tour(dt):
    global tour_active, tour_index, tour_dwell_timer
    if not tour_active:
        return
    if camera_travel is not None:
        return
    tour_dwell_timer -= dt
    if tour_dwell_timer > 0:
        return
    if tour_index >= len(TOUR_ORDER):
        tour_active = False
        set_flash("Guided tour complete!")
        return
    key = TOUR_ORDER[tour_index]
    teleport_to(key)
    set_flash(f"Tour: {ORGANELLES[key]['info']}")
    tour_dwell_timer = 3.5
    tour_index += 1


def idle():
    global last_time, dna_rotation, flash_message_timer
    global replication_active, replication_progress
    global transcription_active, transcription_progress
    global translation_active, translation_progress
    global fps_display, _fps_accum_time, _fps_accum_frames
    global protein_folding_active, protein_folding_progress   
    global mutation_flash_timer, split_amount                 

    now = time.time()
    dt = min(now - last_time, 0.05)
    last_time = now

    _fps_accum_time += dt
    _fps_accum_frames += 1
    if _fps_accum_time >= 0.5:
        fps_display = _fps_accum_frames / _fps_accum_time
        _fps_accum_time, _fps_accum_frames = 0.0, 0

    if flash_message_timer > 0:
        flash_message_timer -= dt
    if mutation_flash_timer > 0:              
        mutation_flash_timer -= dt

    update_travel(dt)
    update_tour(dt)

    global selected_key
    if camera_travel is None:
        auto = compute_in_view_selection()
        if auto is not None:
            selected_key = auto
            track_visit(auto)  

    if not animation_paused:
        dna_rotation = (dna_rotation + 12 * dt) % 360

        if replication_active:
            replication_progress += 0.15 * process_speed * dt
            if replication_progress >= 1.0:
                replication_active, replication_progress = False, 0.0
                print("Replication complete!")

        if transcription_active:
            transcription_progress += 0.2 * process_speed * dt
            if transcription_progress >= 1.0:
                transcription_active, transcription_progress = False, 0.0
                print("Transcription complete! mRNA formed.")

        if translation_active:
            translation_progress += 0.25 * process_speed * dt
            if translation_progress >= 1.0:
                translation_active, translation_progress = False, 0.0
                print("Translation complete! Protein synthesized.")

        
        if protein_folding_active:
            protein_folding_progress += 0.3 * process_speed * dt
            if protein_folding_progress >= 1.0:
                protein_folding_active, protein_folding_progress = False, 1.0
                print("Protein folding complete!")

        
        target_split = 1.0 if CELL_CYCLE_PHASES[cell_cycle_index] in ("Anaphase", "Telophase") else 0.0
        split_amount += (target_split - split_amount) * clamp(dt * 1.5, 0, 1)

        if camera_mode == "dna_follow":
            global dna_follow_angle
            dna_follow_angle = (dna_follow_angle + 25 * dt) % 360

        if brownian_mode:
            update_brownian(dt)
        if atp_mode:
            update_atp(dt)
        if vesicle_mode:             
            update_vesicles(dt)

    glutPostRedisplay()


# ===================================CALLBACKS======================================
def keyboardListener(key, x, y):
    global camera_mode, selected_key, info_panel_visible, labels_visible, help_visible
    global replication_active, transcription_active, translation_active
    global animation_paused, process_speed
    global xray_mode, cross_section_mode, brownian_mode, atp_mode, color_theme
    global tour_active, tour_index, tour_dwell_timer
    global quiz_active
    global free_yaw, free_pitch, orbit_target_key
    global cytoskeleton_visible, vesicle_mode, packing_level       
    global protein_folding_active, protein_folding_progress         
    global minimap_visible, search_active, search_buffer            


    if search_active:
        if key == b'\x1b':
            search_active, search_buffer = False, ""
            set_flash("Search cancelled")
        elif key in (b'\r', b'\n'):
            submit_search()
        elif key == b'\x08' or key == b'\x7f':
            search_buffer = search_buffer[:-1]
        elif key.isalpha():
            search_buffer += key.decode("utf-8")
        glutPostRedisplay()
        return

    if key == b'\x1b':  
        print("Exiting 3D DNA Explorer.")
        os._exit(0)   

    if key == b'/':     
        search_active, search_buffer = True, ""
        glutPostRedisplay()
        return

    if quiz_active and key in (b'1', b'2', b'3'):
        answer_quiz(int(key) - 1)
        glutPostRedisplay()
        return

    fx, fy, _ = forward_vector(free_yaw, 0)
    rx, ry, _ = right_vector(free_yaw)

    if key == b'w':
        free_pos[0] += fx * MOVE_SPEED * 0.05; free_pos[1] += fy * MOVE_SPEED * 0.05
    elif key == b's':
        free_pos[0] -= fx * MOVE_SPEED * 0.05; free_pos[1] -= fy * MOVE_SPEED * 0.05
    elif key == b'a':
        free_pos[0] -= rx * MOVE_SPEED * 0.05; free_pos[1] -= ry * MOVE_SPEED * 0.05
    elif key == b'd':
        free_pos[0] += rx * MOVE_SPEED * 0.05; free_pos[1] += ry * MOVE_SPEED * 0.05
    elif key == b'q':
        free_pos[2] -= MOVE_SPEED * 0.05
    elif key == b'e':
        free_pos[2] += MOVE_SPEED * 0.05

    elif key in (b'1', b'2', b'3', b'4'):
        camera_mode = {b'1': "free", b'2': "orbit", b'3': "dna_follow", b'4': "free"}[key]
        if key == b'2':
            orbit_target_key = selected_key or "nucleus"
        if key == b'4':
            free_pos[0], free_pos[1], free_pos[2] = 0.0, -900.0, 300.0
            free_yaw, free_pitch = 0.0, 10.0

    elif key == b'n':
        teleport_to("nucleus")
    elif key == b'm':
        teleport_to("mitochondria")
    elif key == b'r':
        teleport_to("ribosome")
    elif key == b'g':
        teleport_to("golgi")
    elif key == b'c':
        teleport_to("cell")

    elif key == b'f':
        if selected_key:
            print(f"[{selected_key.title()}] {ORGANELLES[selected_key]['info']}")
            set_flash(f"{selected_key.title()}: {ORGANELLES[selected_key]['info']}")
    elif key == b'i':
        info_panel_visible = not info_panel_visible
    elif key == b'j':
        labels_visible = not labels_visible
    elif key == b'z':
        if selected_key:
            camera_mode = "orbit"
            orbit_target_key = selected_key

    elif key == b'\t':  # Tab: cycle selection (bonus)
        keys = list(ORGANELLES)
        idx = keys.index(selected_key) if selected_key in keys else -1
        selected_key = keys[(idx + 1) % len(keys)]
        track_visit(selected_key)   # NEW

    elif key == b't':
        replication_active = not replication_active
    elif key == b'y':
        transcription_active = not transcription_active
    elif key == b'u':
        translation_active = not translation_active
    elif key == b'p':
        animation_paused = not animation_paused
    elif key == b'+' or key == b'=':
        process_speed = clamp(process_speed + 0.25, 0.25, 5.0)
    elif key == b'-':
        process_speed = clamp(process_speed - 0.25, 0.25, 5.0)

    elif key == b'x':
        xray_mode = not xray_mode
    elif key == b'k':
        cross_section_mode = not cross_section_mode
    elif key == b'b':
        brownian_mode = not brownian_mode
        if brownian_mode and not brownian_particles:
            init_brownian_particles()
    elif key == b'v':
        atp_mode = not atp_mode
    elif key == b'.':
       
        _theme_order = ["normal", "microscope", "dark"]
        color_theme = _theme_order[(_theme_order.index(color_theme) + 1) % len(_theme_order)]
        print(f"Color theme: {color_theme}")

    # --- NEW keys ---
    elif key == b'5':
        cytoskeleton_visible = not cytoskeleton_visible
    elif key == b'6':
        vesicle_mode = not vesicle_mode
    elif key == b'7':
        trigger_mutation()
    elif key == b'8':
        packing_level = (packing_level + 1) % 3
        print(f"DNA packing level: {PACKING_NAMES[packing_level]}")
    elif key == b'9':
        protein_folding_active = True
        protein_folding_progress = 0.0
    elif key == b'l':
        advance_cell_cycle()
    elif key == b',':
        minimap_visible = not minimap_visible
    elif key == b';':
        export_session_summary()

    elif key == b'o':
        tour_active = True
        tour_index = 0
        tour_dwell_timer = 0.0
    elif key == b'0':
        start_quiz()
    elif key == b'h':
        help_visible = not help_visible

    glutPostRedisplay()


def specialKeyListener(key, x, y):
    global free_yaw, free_pitch, orbit_angle, orbit_height, fovY

    if camera_mode == "orbit":
        if key == GLUT_KEY_LEFT: orbit_angle -= LOOK_STEP * 2
        elif key == GLUT_KEY_RIGHT: orbit_angle += LOOK_STEP * 2
        elif key == GLUT_KEY_UP: orbit_height = clamp(orbit_height + 15, -300, 600)
        elif key == GLUT_KEY_DOWN: orbit_height = clamp(orbit_height - 15, -300, 600)
    else:
    
        if key == GLUT_KEY_LEFT: free_yaw -= LOOK_STEP
        elif key == GLUT_KEY_RIGHT: free_yaw += LOOK_STEP
        elif key == GLUT_KEY_UP: free_pitch = clamp(free_pitch + LOOK_STEP, -85, 85)
        elif key == GLUT_KEY_DOWN: free_pitch = clamp(free_pitch - LOOK_STEP, -85, 85)

    glutPostRedisplay()


def mouseListener(button, state, x, y):
    global selected_key, fovY, info_panel_visible

    if state != GLUT_DOWN:
        return

    if button == GLUT_LEFT_BUTTON:
      
        picked = compute_in_view_selection()
        if picked:
            selected_key = picked
            info_panel_visible = True
            track_visit(picked)   
            print(f"Selected: {picked.title()}")

    elif button == GLUT_RIGHT_BUTTON:
        info_panel_visible = not info_panel_visible

    elif button == 3:  
        fovY = clamp(fovY - 5, 30, 130)
    elif button == 4: 
        fovY = clamp(fovY + 5, 30, 130)

    glutPostRedisplay()


def showScreen():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)

    setup_camera()
    draw_scene()
    draw_hud()

    glutSwapBuffers()

# ====================================MAIN==========================================

def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WINDOW_WIDTH, WINDOW_HEIGHT)
    glutInitWindowPosition(0, 0)
    glutCreateWindow(b"3D DNA / Cell Explorer")

    init_brownian_particles()

    glutDisplayFunc(showScreen)
    glutKeyboardFunc(keyboardListener)
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    glutIdleFunc(idle)

    glutMainLoop()


if __name__ == "__main__":
    main()
