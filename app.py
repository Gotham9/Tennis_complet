from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import csv
import io

app = Flask(__name__)
app.secret_key = 'secret_key'
DB_NAME = 'cotes.bd'  # <-- Changement ici
 
# --- Flask-Login setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- User class ---
class User(UserMixin):
    def __init__(self, id, username, is_admin):
        self.id = id
        self.username = username
        self.is_admin = is_admin

    @staticmethod
    def get(user_id):
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, is_admin FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return User(row['id'], row['username'], row['is_admin'])
        return None

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)
  
# --- Init DB ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Table cotes
    c.execute('''
    CREATE TABLE IF NOT EXISTS cotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL,
        cote REAL NOT NULL,
        surface TEXT DEFAULT 'terre',
        sexe TEXT DEFAULT 'homme',
        num_jeu INTEGER
    )
''')

    # Table users
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )
    ''')

    # Création admin par défaut si absent
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if c.fetchone() is None:
        hashed_pw = generate_password_hash("admin")
        c.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
                  ('admin', hashed_pw, 1))

    conn.commit()
    conn.close()

init_db()

# --- Fonctions utilitaires ---
def get_cote_by_id(cote_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM cotes WHERE id = ?", (cote_id,))
    cote = c.fetchone()
    conn.close()
    return cote

def update_cote(cote_id, type_, cote_val, surface, sexe):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        UPDATE cotes
        SET type = ?, cote = ?, surface = ?, sexe = ?
        WHERE id = ?
    """, (type_, cote_val, surface, sexe, cote_id))
    conn.commit()
    conn.close()

# --- Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id, username, password, is_admin FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            user_obj = User(user['id'], user['username'], user['is_admin'])
            login_user(user_obj)
            flash('Connexion réussie', 'success')
            return redirect(url_for('index'))
        flash('Identifiants invalides', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Déconnexion réussie', 'success')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    # Filtres (formulaire du haut)
    filtre_type = request.args.get('filtre_type', '')
    filtre_surface = request.args.get('filtre_surface', '')
    filtre_sexe = request.args.get('filtre_sexe', '')
    filtre_num_jeu = request.args.get('filtre_num_jeu', '')

    # Champs pour le formulaire d'ajout (formulaire du bas)
    last_type = request.args.get('last_type', '')
    last_surface = request.args.get('last_surface', 'terre')
    last_sexe = request.args.get('last_sexe', 'homme')
    last_num_jeu = request.args.get('last_num_jeu', '')
    last_cote = request.args.get('last_cote', '')
    ajout_reussi = request.args.get('ajout_reussi') == '1'

    # Requête SQL avec filtres
    query = "SELECT id, type, cote, surface, sexe, num_jeu FROM cotes WHERE 1=1"
    params = []

    if filtre_type:
        query += " AND type = ?"
        params.append(filtre_type)
    if filtre_surface:
        query += " AND surface = ?"
        params.append(filtre_surface)
    if filtre_sexe:
        query += " AND sexe = ?"
        params.append(filtre_sexe)
    if filtre_num_jeu:
        query += " AND num_jeu = ?"
        params.append(filtre_num_jeu)

    query += " ORDER BY id DESC"

    # Exécution
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    cotes = c.execute(query, params).fetchall()
    conn.close()

    return render_template('index.html',
        cotes=cotes,
        user=current_user,
        filtre_type=filtre_type,
        filtre_surface=filtre_surface,
        filtre_sexe=filtre_sexe,
        filtre_num_jeu=filtre_num_jeu,
        last_type=last_type,
        last_surface=last_surface,
        last_sexe=last_sexe,
        last_num_jeu=last_num_jeu,
        last_cote=last_cote,
        ajout_reussi=ajout_reussi
    )



@app.route('/ajouter', methods=['POST'])
@login_required
def ajouter():
    type_ = request.form.get('type')
    cote = request.form.get('cote')
    surface = request.form.get('surface', 'terre')
    sexe = request.form.get('sexe', 'homme')
    num_jeu = request.form.get('num_jeu')

    # Pour redirection avec valeurs conservées dans le formulaire d'ajout
    redirect_params = {
        'last_type': type_,
        'last_surface': surface,
        'last_sexe': sexe,
        'last_num_jeu': num_jeu or '',
        'last_cote': cote or '',
        'ajout_reussi': 0
    }

    types_valides = {'gagne_jeu', 'victoire_set', 'gagne_6_tiebreak', 'victoire_match'}

    if type_ not in types_valides:
        flash("Type de cote invalide.", "warning")
        return redirect(url_for('index', **redirect_params))

    if not cote:
        flash("La cote est obligatoire.", "warning")
        return redirect(url_for('index', **redirect_params))

    try:
        cote_val = float(cote)
    except ValueError:
        flash("La cote doit être un nombre valide.", "warning")
        return redirect(url_for('index', **redirect_params))

    if type_ == 'gagne_jeu':
        try:
            num_jeu_int = int(num_jeu)
            if not (1 <= num_jeu_int <= 13):
                flash("Le numéro du jeu doit être entre 1 et 13.", "warning")
                return redirect(url_for('index', **redirect_params))
        except (TypeError, ValueError):
            flash("Le numéro du jeu est requis et doit être un entier valide.", "warning")
            return redirect(url_for('index', **redirect_params))
    else:
        num_jeu_int = None

    # Enregistrement dans la base de données
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO cotes (type, cote, surface, sexe, num_jeu) VALUES (?, ?, ?, ?, ?)",
              (type_, cote_val, surface, sexe, num_jeu_int))
    conn.commit()
    conn.close()

    # Redirection après succès, on vide uniquement la cote
    redirect_params['last_cote'] = ''
    redirect_params['ajout_reussi'] = 1
    flash(f"Cote '{type_}' ajoutée avec succès.", "success")
    return redirect(url_for('index', **redirect_params))



from flask import session  # assure-toi que c'est déjà importé en haut

@app.route('/ajouter_victoire_match', methods=['GET', 'POST'])
@login_required
def ajouter_victoire_match():
    if request.method == 'POST':
        cote = request.form.get('cote')
        surface = request.form.get('surface', 'terre')
        sexe = request.form.get('sexe', 'homme')

        # Stocker les derniers choix
        session['last_surface'] = surface
        session['last_sexe'] = sexe

        if not cote:
            flash("La cote est obligatoire.", "warning")
            return redirect(url_for('ajouter_victoire_match'))

        try:
            cote = float(cote)
        except ValueError:
            flash("La cote doit être un nombre valide.", "warning")
            return redirect(url_for('ajouter_victoire_match'))

        type_ = 'victoire_match'

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT INTO cotes (type, cote, surface, sexe) VALUES (?, ?, ?, ?)",
                  (type_, cote, surface, sexe))
        conn.commit()
        conn.close()

        flash("Victoire Match ajoutée avec succès.", "success")
        return redirect(url_for('ajouter_victoire_match'))

    # Pré-remplissage avec les valeurs en session
    last_surface = session.get('last_surface', 'terre')
    last_sexe = session.get('last_sexe', 'homme')

    return render_template('ajouter_victoire_match.html',
                           user=current_user,
                           last_surface=last_surface,
                           last_sexe=last_sexe)


@app.route('/supprimer/<int:id>', methods=['POST'])
@login_required
def supprimer(id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM cotes WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Cote supprimée avec succès", "success")
    return redirect(url_for('index'))

@app.route('/modifier/<int:id>', methods=['GET', 'POST'])
@login_required
def modifier(id):
    cote = get_cote_by_id(id)
    if not cote:
        flash("Cote non trouvée", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        type_ = request.form['type']
        try:
            cote_val = float(request.form['cote'])
        except ValueError:
            flash("La cote doit être un nombre valide.", "warning")
            return redirect(url_for('modifier', id=id))
        surface = request.form['surface']
        sexe = request.form['sexe']
        
        num_jeu = request.form.get('num_jeu')
        if type_  == 'gagne_jeu':
            try:
                num_jeu = int(num_jeu)
                if not (1 <= num_jeu <= 13):
                    raise ValueError()
            except (TypeError, ValueError):
                flash("Le numéro du jeu doit être un entier entre 1 et 13.", "warning")
                return redirect(url_for('modifier', id=id))
        else:
            num_jeu = None

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""
            UPDATE cotes
            SET type = ?, cote = ?, surface = ?, sexe = ?, num_jeu = ?
            WHERE id = ?
        """, (type_, cote_val, surface, sexe, num_jeu, id))
        conn.commit()
        conn.close()

        flash("Cote modifiée avec succès", "success")
        return redirect(url_for('index'))

    return render_template('edit.html', cote=cote)

TYPES = {
    "gagne_jeu": "Gagne dans le jeu",
    "victoire_set": "Victoire Set",
    "gagne_6_tiebreak": "Qui gagnera après 6 jeux dans le tie-break",
    "victoire_match": "Victoire Match"
}

SURFACES = ["terre", "dur", "gazon"]
SEXES = ["homme", "femme"]

@app.route('/statistiques', methods=['GET', 'POST'])
@login_required
def statistiques():
    step = 1
    selected_type = None
    cote1 = None
    cote2 = None
    num_jeu = None
    surface = None
    sexe = None
    resultats = []

    if request.method == 'POST':
        step = int(request.form.get('step', 1))

        if step == 1:
            selected_type = request.form.get('type')
            if selected_type in TYPES:
                step = 2
            else:
                flash("Veuillez sélectionner un type valide.", "warning")
                step = 1

        elif step == 2:
            selected_type = request.form.get('type')
            cote1 = request.form.get('cote1')
            cote2 = request.form.get('cote2')
            num_jeu = request.form.get('num_jeu')
            surface = request.form.get('surface')
            sexe = request.form.get('sexe')

            try:
                cote1 = float(cote1)
                cote2 = float(cote2)
            except (TypeError, ValueError):
                flash("Les cotes doivent être des nombres valides.", "warning")
                step = 2
                return render_template('statistiques.html',
                                       step=step, types=TYPES, selected_type=selected_type,
                                       cote1=cote1, cote2=cote2,
                                       num_jeu=num_jeu, surface=surface, sexe=sexe)

            if cote1 > cote2:
                cote1, cote2 = cote2, cote1

            conn = sqlite3.connect(DB_NAME)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            # Construction dynamique
            query = """
            SELECT cote, COUNT(*) as count FROM cotes
            WHERE type = ?
              AND (cote = ? OR cote = ?)
            """
            params = [selected_type, cote1, cote2]

            if selected_type == 'gagne_jeu' and num_jeu:
                query += " AND num_jeu = ?"
                params.append(num_jeu)

            if surface and surface in SURFACES:
                query += " AND surface = ?"
                params.append(surface)

            if sexe and sexe in SEXES:
                query += " AND sexe = ?"
                params.append(sexe)

            query += " GROUP BY cote ORDER BY cote"

            c.execute(query, params)
            rows = c.fetchall()
            conn.close()

            total = sum(row['count'] for row in rows)
            for row in rows:
                pourcentage = (row['count'] / total * 100) if total > 0 else 0
                resultats.append({
                    'cote': row['cote'],
                    'count': row['count'],
                    'pourcentage': f"{pourcentage:.2f}"
                })

            step = 3

    return render_template('statistiques.html',
                           step=step,
                           types=TYPES,
                           selected_type=selected_type,
                           cote1=cote1,
                           cote2=cote2,
                           num_jeu=num_jeu,
                           surface=surface,
                           sexe=sexe,
                           resultats=resultats)



# --- Fréquences ---@app.route('/frequences')
@app.route('/frequences')
@login_required
def frequences():
    filtre_type = request.args.get('type', '').strip()
    filtre_surface = request.args.get('surface', '').strip()
    filtre_sexe = request.args.get('sexe', '').strip()
    filtre_num_jeu = request.args.get('num_jeu', '').strip()

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = """
        SELECT type, cote, COUNT(*) as freq
        FROM cotes
        WHERE 1=1
    """
    params = []

    if filtre_type:
        query += " AND type = ?"
        params.append(filtre_type)

    if filtre_surface:
        query += " AND surface = ?"
        params.append(filtre_surface)

    if filtre_sexe:
        query += " AND sexe = ?"
        params.append(filtre_sexe)

    # Le filtre num_jeu n’est appliqué que si type == 'gagne_jeu'
    if filtre_type == 'gagne_jeu' and filtre_num_jeu:
        try:
            num_jeu_int = int(filtre_num_jeu)
            if 1 <= num_jeu_int <= 13:
                query += " AND num_jeu = ?"
                params.append(num_jeu_int)
            else:
                flash("Numéro de jeu invalide (doit être entre 1 et 13).", "warning")
        except ValueError:
            flash("Numéro de jeu invalide (doit être un entier).", "warning")
    else:
        query += " AND (num_jeu IS NULL OR num_jeu = '')"

    query += " GROUP BY type, cote ORDER BY type, cote"

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    resultats = {}
    for row in rows:
        type_ = row['type']
        cote = row['cote']
        freq = row['freq']

        if type_ not in resultats:
            resultats[type_] = {'cotes': [], 'total': 0}
        resultats[type_]['cotes'].append({'cote': cote, 'freq': freq})
        resultats[type_]['total'] += freq

    for infos in resultats.values():
        total = infos['total']
        for cote_info in infos['cotes']:
            cote_info['pourcentage'] = round(cote_info['freq'] * 100 / total, 2) if total > 0 else 0

    return render_template(
        'frequences.html',
        resultats=resultats,
        filtre_type=filtre_type,
        filtre_surface=filtre_surface,
        filtre_sexe=filtre_sexe,
        filtre_num_jeu=filtre_num_jeu
    )



@app.route('/frequences_jeux')
@login_required
def frequences_jeux():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT num_jeu, cote, COUNT(*) as freq
        FROM cotes
        WHERE type = 'gagne_jeu' AND num_jeu IS NOT NULL AND num_jeu != ''
        GROUP BY num_jeu, cote
        ORDER BY num_jeu, cote
    """)
    rows = c.fetchall()
    conn.close()

    resultats = {}

    for row in rows:
        nj = row['num_jeu']
        cote = row['cote']
        freq = row['freq']

        if nj not in resultats:
            resultats[nj] = {
                'cotes': [],
                'total': 0
            }
        resultats[nj]['cotes'].append({
            'cote': cote,
            'freq': freq
        })
        resultats[nj]['total'] += freq

    for infos in resultats.values():
        total = infos['total']
        for cote_info in infos['cotes']:
            cote_info['pourcentage'] = round(cote_info['freq'] * 100 / total, 2) if total > 0 else 0

    return render_template('frequences_jeux.html', resultats=resultats)

@app.route('/repartition_globale')
@login_required
def repartition_globale():
    # Paramètres GET
    group_by = request.args.get('group_by', 'surface')  # surface, sexe ou type
    filtre_num_jeu = request.args.get('num_jeu', '').strip()

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    base_query = "SELECT {}, COUNT(*) as freq FROM cotes WHERE 1=1"
    params = []

    # Optionnel : filtre numéro de jeu si par type gagne_jeu
    if filtre_num_jeu:
        try:
            num = int(filtre_num_jeu)
            base_query += " AND num_jeu = ?"
            params.append(num)
        except ValueError:
            pass

    base_query = base_query.format(group_by) + " GROUP BY {} ORDER BY freq DESC".format(group_by)
    c.execute(base_query, params)
    rows = c.fetchall()
    conn.close()

    labels = [row[group_by] or 'N/A' for row in rows]
    freqs = [row['freq'] for row in rows]
    return render_template('repartition_globale.html',
                           group_by=group_by, filtre_num_jeu=filtre_num_jeu,
                           labels=labels, freqs=freqs)


from flask import render_template, request, redirect, url_for, flash

# Liste temporaire (à remplacer par ta BDD)
cotes_gagnantes = []
@app.route('/live', methods=['GET', 'POST'])
@login_required
def enregistrer_live():
    if request.method == 'POST':
        types_ = request.form.getlist('type[]')
        cotes_j1 = request.form.getlist('cote_joueur1[]')
        cotes_j2 = request.form.getlist('cote_joueur2[]')
        gagnants = request.form.getlist('gagnant[]')
        surfaces = request.form.getlist('surface[]')
        num_jeux = request.form.getlist('num_jeu[]')
        sexes = request.form.getlist('sexe[]')

        # Vérifier que toutes les listes ont la même longueur
        n = len(cotes_j1)
        if not (len(cotes_j2) == len(gagnants) == len(surfaces) == len(num_jeux) == len(sexes) == len(types_) == n):
            flash("Erreur dans les données soumises, les listes ne correspondent pas.", "danger")
            return redirect(url_for('enregistrer_live'))

        erreurs = []
        enregistrements = []

        for i in range(n):
            type_ = types_[i]
            cote_j1 = cotes_j1[i]
            cote_j2 = cotes_j2[i]
            gagnant = gagnants[i]
            surface = surfaces[i]
            num_jeu = num_jeux[i]
            sexe = sexes[i]

            # Validation basique
            if not all([cote_j1, cote_j2, surface, num_jeu, sexe, gagnant]):
                erreurs.append(f"Bloc {i+1} : Tous les champs sont requis.")
                continue

            try:
                cote_j1_val = float(cote_j1)
                cote_j2_val = float(cote_j2)
                num_jeu_val = int(num_jeu)
            except ValueError:
                erreurs.append(f"Bloc {i+1} : Valeurs incorrectes pour côtes ou numéro du jeu.")
                continue

            if gagnant not in ['1', '2']:
                erreurs.append(f"Bloc {i+1} : Joueur gagnant invalide.")
                continue

            cote_gagnante = cote_j1_val if gagnant == '1' else cote_j2_val

            enregistrements.append((type_, cote_gagnante, surface, sexe, num_jeu_val))

        if erreurs:
            for err in erreurs:
                flash(err, "danger")
            return redirect(url_for('enregistrer_live'))

        # Insertion en base SQLite
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.executemany(
            "INSERT INTO cotes (type, cote, surface, sexe, num_jeu) VALUES (?, ?, ?, ?, ?)",
            enregistrements
        )
        conn.commit()
        conn.close()

        flash(f"{len(enregistrements)} côtes gagnantes enregistrées avec succès.", "success")
        return redirect(url_for('enregistrer_live'))
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM cotes ORDER BY id DESC LIMIT 20")  # ou plus si tu veux
    cotes = c.fetchall()
    conn.close()

    return render_template(
    'live_cote.html',
    types=TYPES,
    surfaces=SURFACES,
    sexes=SEXES,
    cotes=cotes  # <-- nouveau
)



# --- Export CSV ---
@app.route('/export_csv')
@login_required
def export_csv():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT type, cote, surface, sexe FROM cotes ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Type', 'Cote', 'Surface', 'Sexe'])
    writer.writerows(rows)

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='cotes.csv'
    )

if __name__ == '__main__':
    app.run(debug=True)
