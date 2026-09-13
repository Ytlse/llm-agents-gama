import os
import sys
import time
import urllib.request
import urllib.error

DEST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "docs", "paper", "sources", "etat_de_lart")
os.makedirs(DEST_DIR, exist_ok=True)

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

papers = [
    # 1. Papier socle
    ("Vu_2025_Generative_Agents_Toulouse.pdf", [
        "https://arxiv.org/pdf/2510.19497",
    ]),
    
    # 2. Epistemologie & Agents Generatifs
    ("Park_2023_Generative_Agents.pdf", [
        "https://arxiv.org/pdf/2304.03442",
    ]),
    ("BinTareaf_2026_SILICA_Benchmark.pdf", [
        "https://raw.githubusercontent.com/raadbintareaf/silica-benchmark/main/paper.pdf",
        "https://raw.githubusercontent.com/raadbintareaf/silica-benchmark/main/SILICA_paper.pdf",
        "https://github.com/raadbintareaf/silica-benchmark/raw/main/paper.pdf",
    ]),
    ("Baronchelli_2025_Emergent_Conventions.pdf", [
        "https://www.science.org/doi/pdf/10.1126/sciadv.adp3456",
        "https://arxiv.org/pdf/2405.00000",
    ]),
    ("Baronchelli_2026_Group_Size_Effects.pdf", [
        "https://www.pnas.org/doi/pdf/10.1073/pnas.2519876123",
    ]),

    # 3. Econometrie du choix modal & Transport
    ("McFadden_1974_Conditional_Logit.pdf", [
        "https://eml.berkeley.edu/reprints/mcfadden/zarembka.pdf",
    ]),
    ("Train_2009_Discrete_Choice_Simulation.pdf", [
        "https://eml.berkeley.edu/books/train1201.pdf",
    ]),
    ("Horni_2016_MATSim_Book.pdf", [
        "https://raw.githubusercontent.com/matsim-org/matsim-book/master/matsim-book.pdf",
        "https://www.ubiquitypress.com/site/books/10.5334/bam/download/1220/",
    ]),
    ("Horl_2021_eqasim_synthetic_population.pdf", [
        "https://www.research-collection.ethz.ch/bitstream/handle/20.500.11850/463690/1/abm_paris_v6.pdf",
    ]),
    ("Taillandier_2019_GAMA_platform.pdf", [
        "https://hal.science/hal-02058315/document",
    ]),

    # 4. ML Tabulaire & Explicabilite
    ("Ke_2017_LightGBM.pdf", [
        "https://proceedings.neurips.cc/paper_files/paper/2017/file/6449f44a102fde8486beadc5bad6a247-Paper.pdf",
    ]),
    ("Lundberg_2017_SHAP.pdf", [
        "https://arxiv.org/pdf/1705.07874",
    ]),

    # 5. Alignement distributionnel & Silicon Sampling
    ("Meister_2024_Benchmarking_Distributional_Alignment.pdf", [
        "https://arxiv.org/pdf/2411.05403",
    ]),
    ("Argyle_2023_OutOfOneMany.pdf", [
        "https://arxiv.org/pdf/2209.06899",
    ]),
    ("Supervision_2025_Distributional_Alignment.pdf", [
        "https://arxiv.org/pdf/2507.00439",
    ]),
    ("DistShift_2025_Survey_Distributions.pdf", [
        "https://arxiv.org/pdf/2510.21977",
    ]),
    ("RADIUS_2026_Ranking_Distribution.pdf", [
        "https://arxiv.org/pdf/2603.19002",
    ]),
    ("PromptsToProxies_2025.pdf", [
        "https://arxiv.org/pdf/2509.11311",
    ]),
    ("BeyondTheMean_2026_ThreeAxisFidelity.pdf", [
        "https://arxiv.org/pdf/2606.28963",
    ]),

    # 6. Optimisation de prompts (APO / GA)
    ("Zhou_2022_APE.pdf", [
        "https://arxiv.org/pdf/2211.01910",
    ]),
    ("Yang_2023_OPRO.pdf", [
        "https://arxiv.org/pdf/2309.03409",
    ]),
    ("Pryzant_2023_ProTeGi.pdf", [
        "https://arxiv.org/pdf/2305.03495",
    ]),
    ("Guo_2023_EvoPrompt.pdf", [
        "https://arxiv.org/pdf/2309.08532",
    ]),
    ("Secheresse_2025_GAAPO.pdf", [
        "https://arxiv.org/pdf/2504.07157",
    ]),
    ("Fernando_2023_PromptBreeder.pdf", [
        "https://arxiv.org/pdf/2309.16797",
    ]),
    ("OpsahlOng_2024_DSPy_MIPROv2.pdf", [
        "https://arxiv.org/pdf/2406.11695",
    ]),
    ("GEPA_2025_Reflective_Prompt_Evolution.pdf", [
        "https://arxiv.org/pdf/2507.19457",
    ]),
    ("RePrompt_2024.pdf", [
        "https://arxiv.org/pdf/2406.11132",
    ]),
    ("MAPGD_2025.pdf", [
        "https://arxiv.org/pdf/2509.11361",
    ]),
    ("MASS_2025_MultiAgentDesign.pdf", [
        "https://arxiv.org/pdf/2502.02533",
    ]),
    ("ADOPT_2025_Adaptive_Dependency_Prompt.pdf", [
        "https://arxiv.org/pdf/2512.24933",
    ]),

    # 7. Attribution de credit Shapley
    ("OSPO_2026_Owen_Shapley.pdf", [
        "https://arxiv.org/pdf/2601.08403",
    ]),
    ("SCAR_2025_Shapley_RLHF.pdf", [
        "https://arxiv.org/pdf/2505.20417",
    ]),
    ("SHARP_2026_MultiAgent_Shapley.pdf", [
        "https://arxiv.org/pdf/2602.08335",
    ]),

    # 8. Mobilite & LLM
    ("Evaluating_LLMs_ABM_Urban_Mobility_2026.pdf", [
        "https://arxiv.org/pdf/2607.02716",
    ]),
    ("Prompt_Optimization_Diverse_Populations_2025.pdf", [
        "https://arxiv.org/pdf/2510.07064",
    ]),
    ("Toward_LLM_ABM_Transportation_2024.pdf", [
        "https://arxiv.org/pdf/2412.06681",
    ]),
    ("Cognitive_Agents_Urban_Mobility_2025.pdf", [
        "https://www.mdpi.com/1424-8220/25/18/5688/pdf",
    ]),
]

print(f"Total papers to process: {len(papers)}")
print(f"Destination folder: {DEST_DIR}\n")

successes = []
failures = []

for filename, urls in papers:
    out_path = os.path.join(DEST_DIR, filename)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
        print(f"✓ Already exists: {filename} ({os.path.getsize(out_path)} bytes)")
        successes.append((filename, "already exists"))
        continue

    downloaded = False
    for url in urls:
        print(f"Downloading {filename} from {url}...")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status == 200:
                    data = resp.read()
                    # Check if response is actually a PDF or error page
                    if data.startswith(b"%PDF") or len(data) > 10000:
                        with open(out_path, "wb") as f:
                            f.write(data)
                        print(f"  ✓ Success ({len(data)} bytes) saved to {filename}")
                        successes.append((filename, url))
                        downloaded = True
                        break
                    else:
                        print(f"  ✗ Returned non-PDF content ({len(data)} bytes)")
                else:
                    print(f"  ✗ Status: {resp.status}")
        except urllib.error.HTTPError as e:
            print(f"  ✗ HTTP Error {e.code}: {e.reason}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
        time.sleep(1)

    if not downloaded:
        failures.append((filename, urls))

print("\n" + "="*50)
print(f"Downloaded: {len(successes)} / {len(papers)}")
if failures:
    print(f"Failures ({len(failures)}):")
    for f, u in failures:
        print(f"  - {f}: {u}")
