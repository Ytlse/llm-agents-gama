"""cli.py — commandes d'exploitation : `llm-gateway serve | worker | config validate | config show | categories`.

Point d'entrée déclaré dans pyproject (`[project.scripts]`). Les commandes n'ajoutent aucune
logique : elles appellent les fabriques et impriment ce qu'un opérateur veut vérifier avant
de démarrer (configuration effective, secrets masqués ; catégories enregistrées).
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("llm_gateway.main:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def _cmd_worker(args: argparse.Namespace) -> int:
    from llm_gateway.worker.task_worker import celery_app

    argv = ["worker", f"--loglevel={args.loglevel}", f"--concurrency={args.concurrency}", "-P", args.pool]
    celery_app.worker_main(argv)
    return 0


def _redacted_settings() -> dict[str, Any]:
    from llm_gateway.config import get_settings, redacted_dump

    return redacted_dump(get_settings())


def _cmd_config_validate(_: argparse.Namespace) -> int:
    from llm_gateway.config import get_settings

    try:
        settings = get_settings()
    except Exception as exc:  # pydantic.ValidationError, YAML illisible…
        print(f"CONFIGURATION INVALIDE : {exc}", file=sys.stderr)
        return 1
    print(
        f"OK — fichier {settings.resolved_providers_file()} : {len(settings.declared_providers)} "
        f"déclaré(s), {len(settings.providers)} actif(s) avec clé : {', '.join(sorted(settings.providers)) or 'aucun'}"
    )
    return 0


def _cmd_config_schema(args: argparse.Namespace) -> int:
    if args.what == "providers":
        from llm_gateway.config import providers_schema_json_text

        print(providers_schema_json_text())
    else:
        from llm_gateway.config import GatewaySettings

        print(json.dumps(GatewaySettings.model_json_schema(), indent=2, ensure_ascii=False))
    return 0


def _cmd_config_show(_: argparse.Namespace) -> int:
    print(json.dumps(_redacted_settings(), indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_categories(_: argparse.Namespace) -> int:
    from llm_gateway.prompts.registry import get_registry

    registry = get_registry()
    cats = registry.categories()
    if not cats:
        print("Aucune catégorie enregistrée (aucun bundle sous l'entry point llm_gateway.categories).")
        return 1
    for name in cats:
        handle = registry.get(name)
        print(f"{name}\t(bundle={handle.bundle.name}, items={handle.spec.item_model.__name__})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="llm-gateway", description="Gateway LLM : service, worker, configuration.")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("serve", help="démarre l'API (uvicorn)")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--reload", action="store_true")
    s.set_defaults(func=_cmd_serve)

    w = sub.add_parser("worker", help="démarre un worker Celery")
    w.add_argument("--loglevel", default="info")
    w.add_argument("--concurrency", type=int, default=25)
    w.add_argument("--pool", default="threads")
    w.set_defaults(func=_cmd_worker)

    c = sub.add_parser("config", help="configuration effective")
    csub = c.add_subparsers(dest="config_command", required=True)
    csub.add_parser("validate", help="charge la configuration ; code 1 si invalide").set_defaults(func=_cmd_config_validate)
    csub.add_parser("show", help="affiche la configuration effective, secrets masqués").set_defaults(func=_cmd_config_show)
    sc = csub.add_parser("schema", help="JSON Schema du fichier des fournisseurs (défaut) ou des réglages")
    sc.add_argument("what", nargs="?", choices=["providers", "settings"], default="providers")
    sc.set_defaults(func=_cmd_config_schema)

    sub.add_parser("categories", help="liste les catégories enregistrées par les bundles").set_defaults(func=_cmd_categories)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
