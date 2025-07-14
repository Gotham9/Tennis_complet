import sqlite3
import hashlib

DB_NAME = 'cotes.db'  # Remplace par le nom de ta base

def hash_password(password):
    # Simple hash SHA256 (à améliorer en prod avec bcrypt par exemple)
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def create_user_table_and_admin():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Création de la table users si elle n'existe pas
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            is_admin BOOLEAN NOT NULL DEFAULT 0
        )
    ''')

    # Insérer un admin si pas déjà présent
    admin_username = 'admin'
    admin_password = 'motdepasse'  # CHANGE ce mot de passe !
    hashed_pw = hash_password(admin_password)

    c.execute("SELECT * FROM users WHERE username = ?", (admin_username,))
    if c.fetchone() is None:
        c.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
                  (admin_username, hashed_pw, 1))
        print(f"Admin '{admin_username}' créé avec mot de passe '{admin_password}' (hashé).")
    else:
        print("L'utilisateur admin existe déjà.")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    create_user_table_and_admin()
