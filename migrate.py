import sqlite3

DB_NAME = 'cotes.db'

def colonne_existe(cursor, table, colonne):
    cursor.execute(f"PRAGMA table_info({table})")
    colonnes = [info[1] for info in cursor.fetchall()]
    return colonne in colonnes

def ajouter_colonne_si_absente(cursor, table, colonne, definition):
    if not colonne_existe(cursor, table, colonne):
        print(f"Ajout de la colonne '{colonne}' à la table '{table}'...")
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {definition}")

def main():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    ajouter_colonne_si_absente(cursor, "cotes", "surface", "TEXT DEFAULT 'terre'")
    ajouter_colonne_si_absente(cursor, "cotes", "sexe", "TEXT DEFAULT 'homme'")

    conn.commit()
    conn.close()
    print("Migration terminée.")

if __name__ == "__main__":
    main()
