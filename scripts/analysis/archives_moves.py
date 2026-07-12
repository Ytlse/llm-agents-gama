import pandas as pd
from pathlib import Path
import re

def analyser_archives_moves():
    # 1. Pointer vers le dossier des archives
    archive_dir = Path("../../experiments/archive")
    
    if not archive_dir.exists():
        print(f"Le dossier {archive_dir} n'existe pas.")
        return

    resultats = []

    # Chercher tous les fichiers moves.csv dans les sous-dossiers
    for move_file in archive_dir.rglob("moves.csv"):
        # On remonte l'arborescence pour trouver le nom du "run" (souvent le parent ou grand-parent)
        current_dir = move_file.parent
        run_name = current_dir.name if current_dir.name != "gama_results" else current_dir.parent.name
        
        # 2. Chercher la taille de la population (population_{n}.json)
        pop_size = "Inconnu"
        search_dir = current_dir
        # On cherche dans le dossier du CSV et ses parents (jusqu'au dossier archive)
        while search_dir != archive_dir.parent:
            pop_files = list(search_dir.glob("population_*.json"))
            if pop_files:
                # Extraction du "n" dans "population_{n}.json"
                match = re.search(r"population_(\d+)\.json", pop_files[0].name)
                if match:
                    pop_size = match.group(1)
                    break
            search_dir = search_dir.parent

        # Lecture du CSV
        try:
            df = pd.read_csv(move_file)
        except Exception as e:
            print(f"Erreur de lecture pour {move_file}: {e}")
            continue
            
        col_modele = "Fournisseur & Modèle"
        col_heure = "Heure de calcul"
        
        if col_modele not in df.columns or col_heure not in df.columns:
            print(f"Colonnes manquantes ({col_modele} ou {col_heure}) dans {move_file}")
            continue

        # 3 et 4. Filtrer pour exclure le cache sur "Fournisseur & Modèle"
        df_llm = df[~df[col_modele].astype(str).str.contains("cache:", case=False, na=False)].copy()
        
        if df_llm.empty:
            resultats.append({
                "Run": run_name,
                "Pop (n)": pop_size,
                "Début (hors cache)": "N/A",
                "Fin (hors cache)": "N/A",
                "Lignes/min (Moy)": 0
            })
            continue

        # Traitement du temps réel
        df_llm[col_heure] = pd.to_datetime(df_llm[col_heure], errors='coerce')
        df_llm = df_llm.dropna(subset=[col_heure])
        
        if df_llm.empty:
            continue
            
        heure_debut = df_llm[col_heure].min()
        heure_fin = df_llm[col_heure].max()
        
        # Calcul du nombre de lignes (requêtes) par minute
        df_llm['minute'] = df_llm[col_heure].dt.floor('min')
        lignes_par_minute = df_llm.groupby('minute').size()
        
        moyenne_req_min = lignes_par_minute.mean()

        resultats.append({
            "Run": run_name,
            "Pop (n)": pop_size,
            "Début (hors cache)": heure_debut.strftime('%H:%M:%S'),
            "Fin (hors cache)": heure_fin.strftime('%H:%M:%S'),
            "Lignes/min (Moy)": round(moyenne_req_min, 2)
        })

    # Affichage du tableau final
    df_resultats = pd.DataFrame(resultats)
    if not df_resultats.empty:
        df_resultats.sort_values(by="Run", inplace=True)
        print("\n=== Analyse de la performance d'inférence LLM (moves.csv) ===")
        print(df_resultats.to_string(index=False))
    else:
        print("Aucun fichier moves.csv valide trouvé ou analysable.")

if __name__ == "__main__":
    analyser_archives_moves()
