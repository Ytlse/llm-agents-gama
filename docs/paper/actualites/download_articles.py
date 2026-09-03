#!/usr/bin/env python3
"""
Script de téléchargement et d'archivage local des 30 articles d'actualité toulousaine
pour le projet LLM-Agents GAMA (Manuscrit 2026).
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
import ssl

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "articles_html")
os.makedirs(OUTPUT_DIR, exist_ok=True)

ARTICLES = [
    {
        "id": 1,
        "title": "Insécurité & climat anxiogène Arnaud Bernard",
        "url": "https://www.ldh-france.org/wp-content/uploads/2021/04/rapport-toulouse-4-ans-dobservations-final-compresse.pdf",
        "media": "LDH / La Dépêche",
        "filename": "01_insecurite_arnaud_bernard.pdf"
    },
    {
        "id": 2,
        "title": "Insécurité nocturne couloirs Jean-Jaurès",
        "url": "https://www.evous.fr/toulouse.html?debut_articles=400",
        "media": "Évous / La Dépêche",
        "filename": "02_insecurite_jean_jaures.html"
    },
    {
        "id": 3,
        "title": "Agression & faune nocturne Parvis Matabiau",
        "url": "https://actu.fr/occitanie/toulouse_31555/toulouse-homme-blesse-deux-coups-couteau-pres-gare-matabiau_27383794.html",
        "media": "Actu Toulouse",
        "filename": "03_agression_gare_matabiau.html"
    },
    {
        "id": 4,
        "title": "Campagne Tisséo contre harcèlement sexuel",
        "url": "https://france3-regions.francetvinfo.fr/occitanie/haute-garonne/toulouse/nouvelle-campagne-tisseo-contre-harcelement-sexuel-transports-toulousains-1434817.html",
        "media": "France 3 Occitanie",
        "filename": "04_campagne_harcelement_tisseo.html"
    },
    {
        "id": 5,
        "title": "Poussière & marteaux-piqueurs Rue de Metz",
        "url": "https://metropole.toulouse.fr/actualites",
        "media": "Toulouse Métropole / La Dépêche",
        "filename": "05_travaux_rue_de_metz.html"
    },
    {
        "id": 6,
        "title": "Passerelles provisoires bois François Verdier",
        "url": "https://metropole.toulouse.fr/sites/toulouse-fr/files/2022-12/1.1_commission_de_quartier_projet_metro_francois_verdier_juin_2022.pdf",
        "media": "Toulouse Métropole",
        "filename": "06_passerelle_francois_verdier.pdf"
    },
    {
        "id": 7,
        "title": "Grève éboueurs : sacs et odeurs hypercentre",
        "url": "https://www.toulousefm.fr/news/toulouse-les-eboueurs-de-la-ville-en-greve-illimitee-a-partir-d-aujourd-hui-17762",
        "media": "Toulouse FM",
        "filename": "07_greve_eboueurs_hypercentre.html"
    },
    {
        "id": 8,
        "title": "Éboueurs : fin de collecte nocturne",
        "url": "https://www.ladepeche.fr/2023/02/13/les-eboueurs-ne-passeront-plus-de-nuit-dans-lhypercentre-de-toulouse-10994220.php",
        "media": "La Dépêche du Midi",
        "filename": "08_eboueurs_fin_nuit.html"
    },
    {
        "id": 9,
        "title": "Vent d'Autan : fermeture Jardin des Plantes",
        "url": "https://www.ladepeche.fr/2026/07/16/rafales-de-vent-a-plus-de-80-kmh-toulouse-ferme-en-urgence-ses-parcs-et-jardins-ce-jeudi-soir-13471686.php",
        "media": "La Dépêche du Midi",
        "filename": "09_vent_autan_fermeture_parcs.html"
    },
    {
        "id": 10,
        "title": "Menace chute platanes sous Autan",
        "url": "https://actu.fr/occitanie/toulouse_31555",
        "media": "Actu Toulouse",
        "filename": "10_menace_chute_arbres_autan.html"
    },
    {
        "id": 11,
        "title": "Rafales sur ponts Garonne & berges Daurade",
        "url": "https://pyrros.fr/galerie/galerie-orages-et-meteo/",
        "media": "Pyrros Météo",
        "filename": "11_rafales_ponts_garonne.html"
    },
    {
        "id": 12,
        "title": "Culture du Vent des fous et fatigue",
        "url": "https://www.ladepeche.fr/",
        "media": "La Dépêche du Midi",
        "filename": "12_vent_des_fous_fatigue.html"
    },
    {
        "id": 13,
        "title": "Psychose punaises de lit (Banquettes tissu)",
        "url": "https://www.punaise-de-lit-info.fr/actualites/la-possible-presence-de-punaises-de-lit-dans-le-metro-de-toulouse-suscite-des-questions",
        "media": "Punaise de Lit Info",
        "filename": "13_psychose_punaises_metro.html"
    },
    {
        "id": 14,
        "title": "Démenti ministre zéro cas avéré punaises",
        "url": "https://france3-regions.francetvinfo.fr/occitanie/haute-garonne/toulouse",
        "media": "France 3 Occitanie",
        "filename": "14_dementi_ministre_punaises.html"
    },
    {
        "id": 15,
        "title": "Surveillance spécialisée punaises Tisséo",
        "url": "https://www.punaise-de-lit-info.fr/actualites/la-possible-presence-de-punaises-de-lit-dans-le-metro-de-toulouse-suscite-des-questions",
        "media": "Punaise de Lit Info",
        "filename": "15_surveillance_punaises_tisseo.html"
    },
    {
        "id": 16,
        "title": "Tarif désinfection 240 € Métropole",
        "url": "https://metropole.toulouse.fr/sites/toulouse-fr/files/2023-08/telecharger_le_recueil_des_tarifs_septembre_2023_1.pdf",
        "media": "Toulouse Métropole",
        "filename": "16_recueil_tarifs_desinfection.pdf"
    },
    {
        "id": 17,
        "title": "Marée humaine Capitole (Bouclier de Brennus)",
        "url": "https://actu.fr/occitanie/toulouse_31555",
        "media": "Actu Toulouse",
        "filename": "17_maree_humaine_capitole.html"
    },
    {
        "id": 18,
        "title": "Le Minotaure / La Machine dans les ruelles",
        "url": "https://france3-regions.francetvinfo.fr/occitanie/haute-garonne/toulouse/le-minotaure-l-araignee-et-la-gardienne-des-teneberes-arrivent-a-toulouse-le-programme-du-nouveau-spectacle-des-machines-3049804.html",
        "media": "France 3 Occitanie",
        "filename": "18_minotaure_la_machine.html"
    },
    {
        "id": 19,
        "title": "Fête de la Musique (Rue des Paradoux saturée)",
        "url": "https://blog.culture31.com/2012/06/24/une-fete-de-la-musique-sous-la-ramure-protectrice-du-neflier-du-japon-de-la-rue-des-paradoux/",
        "media": "Culture 31",
        "filename": "19_fete_musique_paradoux.html"
    },
    {
        "id": 20,
        "title": "Grande Braderie : portants rue Saint-Rome",
        "url": "https://www.calameo.com/books/0073330388f2c9cc87274",
        "media": "Calaméo / La Dépêche",
        "filename": "20_grande_braderie_saint_rome.html"
    },
    {
        "id": 21,
        "title": "Ombrières dorées & fraîcheur Rue Alsace",
        "url": "https://france3-regions.francetvinfo.fr/occitanie/haute-garonne/toulouse/une-multitude-de-rubans-dores-pour-faire-baisser-la-temperature-les-ombrieres-font-leur-retour-au-c-ur-de-la-ville-3002567.html",
        "media": "France 3 Occitanie",
        "filename": "21_ombrieres_rue_alsace.html"
    },
    {
        "id": 22,
        "title": "Ramblas Jean-Jaurès : promenade paysagère",
        "url": "https://france3-regions.francetvinfo.fr/occitanie/haute-garonne/toulouse/toulouse-ramblas-jardins-belle-promenade-apres-1766681.html",
        "media": "France 3 Occitanie",
        "filename": "22_ramblas_jean_jaures.html"
    },
    {
        "id": 23,
        "title": "Passerelles dédiées Île du Ramier",
        "url": "https://france3-regions.francetvinfo.fr/occitanie/haute-garonne/toulouse/toulouse-deux-passerelles-rejoindront-l-ile-du-ramier-d-ici-2024-2446026.html",
        "media": "France 3 Occitanie",
        "filename": "23_passerelles_ile_du_ramier.html"
    },
    {
        "id": 24,
        "title": "Vélotour : balade atypique lieux interdits",
        "url": "https://france3-regions.francetvinfo.fr/occitanie/haute-garonne/toulouse/velotour-occitanie-une-balade-insolite-pour-explorer-des-lieux-habituellement-interdits-a-velo-2954129.html",
        "media": "France 3 Occitanie",
        "filename": "24_velotour_occitanie.html"
    },
    {
        "id": 25,
        "title": "VélôToulouse électrique & fin des côtes",
        "url": "https://www.ladepeche.fr/2024/06/22/mobilite-douce-a-toulouse-lancement-du-nouveau-service-velotoulouse-des-le-30-aout-12034444.php",
        "media": "La Dépêche du Midi",
        "filename": "25_velotoulouse_electrique.html"
    },
    {
        "id": 26,
        "title": "Noctambus avec médiateurs de sécurité",
        "url": "https://france3-regions.francetvinfo.fr/occitanie/haute-garonne/toulouse/toulouse-nouveau-dispositif-bus-nocturnes-fetards-1201791.html",
        "media": "France 3 Occitanie",
        "filename": "26_noctambus_tisseo.html"
    },
    {
        "id": 27,
        "title": "Enquête Tisséo : essor vélo & norme sociale",
        "url": "https://france3-regions.francetvinfo.fr/occitanie/haute-garonne/toulouse/la-voiture-delaissee-au-profit-du-velo-et-de-la-marche-tisseo-publie-sa-grande-enquete-sur-les-deplacements-3011477.html",
        "media": "France 3 Occitanie",
        "filename": "27_enquete_deplacements_tisseo.html"
    },
    {
        "id": 28,
        "title": "Concert Stadium Bigflo & Oli (Navettes)",
        "url": "https://france3-regions.francetvinfo.fr/occitanie/haute-garonne/toulouse/infos-pratiques-ce-qu-il-faut-savoir-si-vous-allez-voir-bigflo-oli-au-stadium-toulouse-1671505.html",
        "media": "France 3 Occitanie",
        "filename": "28_concert_stadium_bigflo_oli.html"
    },
    {
        "id": 29,
        "title": "Ça pue chez vous (Odeur isolée)",
        "url": "https://www.ladepeche.fr/2023/12/22/ca-pue-chez-vous-une-odeur-nauseabonde-envahit-une-rue-de-toulouse-les-habitants-se-sentent-demunis-11657388.php",
        "media": "La Dépêche du Midi",
        "filename": "29_odeur_nauseabonde_rue.html"
    },
    {
        "id": 30,
        "title": "Engouement vélo post-déconfinement 2020",
        "url": "https://france3-regions.francetvinfo.fr/occitanie/haute-garonne/toulouse/clients-reparateurs-vendeurs-expliquent-engouement-velo-toulouse-deconfinement-1832170.html",
        "media": "France 3 Occitanie",
        "filename": "30_engouement_velo_deconfinement.html"
    }
]

# Create SSL context allowing modern ciphers and ignoring self-signed/cert expiry
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"
}

summary = []

for item in ARTICLES:
    file_path = os.path.join(OUTPUT_DIR, item["filename"])
    print(f"[{item['id']}/30] Téléchargement de : {item['title']}...")
    try:
        req = urllib.request.Request(item["url"], headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            content = response.read()
            with open(file_path, "wb") as f:
                f.write(content)
            status = "OK"
            size_kb = round(len(content) / 1024, 1)
            print(f"   -> Succès ({size_kb} KB)")
    except Exception as e:
        status = f"Erreur: {e}"
        print(f"   -> Échec ({e})")
        # Write a fallback metadata placeholder html
        fallback_html = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>{item['title']}</title></head>
<body>
<h1>{item['title']}</h1>
<p><strong>Média :</strong> {item['media']}</p>
<p><strong>URL Source :</strong> <a href="{item['url']}">{item['url']}</a></p>
<p><em>Statut de téléchargement : {e}</em></p>
</body>
</html>"""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(fallback_html)

    summary.append({
        "id": item["id"],
        "title": item["title"],
        "media": item["media"],
        "url": item["url"],
        "filename": item["filename"],
        "status": status
    })
    time.sleep(0.3)

index_json = os.path.join(OUTPUT_DIR, "index_articles.json")
with open(index_json, "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

print("\n--- Téléchargement terminé. Index généré dans index_articles.json ---")
