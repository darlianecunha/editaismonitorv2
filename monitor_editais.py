# -*- coding: utf-8 -*-
"""
Monitor de Editais - Cooperacao Brasil-Alemanha
Sustentabilidade, Maritime AI, Decarbonizacao e Mudancas Climaticas

Gera JSON para pagina web hospedada na Vercel.
Roda via GitHub Actions (cron diario) ou manualmente.
"""

import os
import re
import json
import datetime
from pathlib import Path
from urllib.parse import quote_plus
import feedparser

# Padroes de titulos genericos/invalidos que devem ser filtrados
# Ex: "Search - www.daad.de", "Suche - www.dfg.de"
INVALID_TITLE_PATTERNS = [
    re.compile(r'^Search\s*[-–—]\s*', re.IGNORECASE),
    re.compile(r'^Suche\s*[-–—]\s*', re.IGNORECASE),
    re.compile(r'^Busca\s*[-–—]\s*', re.IGNORECASE),
    re.compile(r'^Pesquisa\s*[-–—]\s*', re.IGNORECASE),
    re.compile(r'^www\.\w+\.\w+', re.IGNORECASE),
    re.compile(r'^\S+\.\w{2,3}$', re.IGNORECASE),  # titulos que sao apenas um dominio
]


def is_valid_title(title):
    """Verifica se o titulo e valido (nao e generico de pagina de busca)."""
    if not title or len(title.strip()) < 10:
        return False
    for pattern in INVALID_TITLE_PATTERNS:
        if pattern.search(title.strip()):
            return False
    return True

# ===== Parametros =====
DAYS = int(os.getenv("DAYS_INT", "14"))
MAX_PER_TERM = int(os.getenv("MAX_PER_TERM_INT", "8"))
OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "data"))

LANG_COUNTRY_PAIRS = [
    ("de", "DE"),
    ("en", "DE"),
    ("pt", "BR"),
]

# ===== Categorias de busca =====
SEARCH_CATEGORIES = {
    "DAAD": {
        "icon": "🇩🇪",
        "label": "DAAD (Alemanha)",
        "terms": [
            'site:daad.de "climate change" research',
            'site:daad.de "climate change" scholarship',
            'site:daad.de "sustainable development" research',
            'site:daad.de sustainability scholarship',
            'site:daad.de Nachhaltigkeit Forschung',
            'site:daad.de Klimawandel Forschung',
            'site:daad.de "climate action" research funding',
            'site:daad.de "maritime" OR "shipping" OR "port"',
            'site:daad.de "artificial intelligence" research',
        ],
    },
    "DFG": {
        "icon": "🇩🇪",
        "label": "DFG (Alemanha)",
        "terms": [
            'site:dfg.de "climate change" research funding',
            'site:dfg.de Klimawandel Forschungsfoerderung',
            'site:dfg.de Nachhaltigkeit Schwerpunktprogramm',
            'site:dfg.de "sustainability" research project',
            'site:dfg.de "climate and energy" call for proposals',
            'site:dfg.de "maritime" OR "shipping" Forschung',
            'site:dfg.de "artificial intelligence" sustainability',
        ],
    },
    "Humboldt": {
        "icon": "🇩🇪",
        "label": "Humboldt Foundation (Alemanha)",
        "terms": [
            'site:humboldt-foundation.de "climate change" fellowship',
            'site:humboldt-foundation.de climate sustainability research',
            'site:humboldt-foundation.de "sustainable development" research',
            'site:avh.de Klimawandel Stipendium',
            'site:avh.de Nachhaltigkeit Forschung',
        ],
    },
    "BMBF_UBA": {
        "icon": "🇩🇪",
        "label": "BMBF & UBA (Alemanha)",
        "terms": [
            'site:bmbf.de "climate change" research funding',
            'site:bmbf.de Klimawandel Foerderaufruf',
            'site:bmbf.de Nachhaltigkeit Forschungsfoerderung',
            'site:bmbf.de "sustainable development" research',
            'site:bmbf.de "maritime" OR "shipping" Forschung',
            'site:umweltbundesamt.de Klimawandel Forschung',
            'site:umweltbundesamt.de Nachhaltigkeit Forschungsprojekt',
        ],
    },
    "ThinkTanks": {
        "icon": "🏛️",
        "label": "Think Tanks & Organizacoes",
        "terms": [
            'site:emsa.europa.eu "sustainability" OR "emissions"',
            'site:itf-oecd.org "maritime" OR "shipping" OR "port"',
            'site:fraunhofer.de "maritime" OR "shipping" sustainability',
            'site:fraunhofer.de "decarbonisation" OR "decarbonization"',
            '"Fraunhofer" maritime sustainability research',
            '"Helmholtz" climate change research Germany',
        ],
    },
    "Maritime_AI": {
        "icon": "🚢",
        "label": "Maritime AI & Decarbonizacao",
        "terms": [
            'Germany "maritime decarbonisation" research',
            'Deutschland "shipping emissions" Forschung',
            'Germany "port sustainability" research grant',
            '"maritime AI" research position Germany',
            'Germany "shipping decarbonisation" research fellowship',
            'Deutschland "SDG 14" OR "life below water" Forschung',
            '"emission monitoring" vessels research Germany',
        ],
    },
    "Geral_DE": {
        "icon": "🔍",
        "label": "Geral Alemanha",
        "terms": [
            'Germany "climate change" research funding call',
            'Germany "sustainability" research grant',
            'Germany "sustainable development" postdoctoral fellowship',
            'Deutschland Nachhaltigkeit Forschungsfoerderung',
        ],
    },
    "BR_Coop": {
        "icon": "🇧🇷",
        "label": "Cooperacao Brasil-Alemanha",
        "terms": [
            'Brazil Germany "climate change" research programme',
            'Brazil Germany sustainability research call',
            'Brasil Alemanha "mudancas climaticas" cooperacao cientifica',
            'Alemanha "transicao energetica" oportunidades de pesquisa',
            'CAPES DAAD cooperation research',
            'CNPq Germany bilateral research',
            'FAPESP Germany research cooperation',
            'Brasil Alemanha cooperacao cientifica edital',
        ],
    },
}


def buscar_multilingue(categorias, pairs, dias, max_per_termo):
    """Busca em varios idiomas/paises e consolida resultados por categoria."""
    hoje = datetime.date.today()
    limite = hoje - datetime.timedelta(days=dias)
    resultados = {}

    for cat_id, cat_info in categorias.items():
        cat_results = []

        for termo in cat_info["terms"]:
            vistos_link = set()
            vistos_titulo = set()
            itens = []

            for lang, country in pairs:
                q = quote_plus(termo)
                url = (
                    f"https://news.google.com/rss/search?"
                    f"q={q}&hl={lang}&gl={country}&ceid={country}:{lang}"
                )
                try:
                    feed = feedparser.parse(url)
                except Exception:
                    continue

                for e in feed.entries:
                    dp = e.get("published_parsed")
                    if not dp:
                        continue
                    d = datetime.date(*dp[:3])
                    if d < limite:
                        continue

                    title = (e.title or "").strip()
                    link = (e.link or "").strip()
                    if not title or not link:
                        continue

                    # Filtrar titulos genericos (ex: "Search - www.daad.de")
                    if not is_valid_title(title):
                        continue

                    key_link = link.lower()
                    key_title = title.lower()
                    if key_link in vistos_link or key_title in vistos_titulo:
                        continue

                    vistos_link.add(key_link)
                    vistos_titulo.add(key_title)

                    itens.append({
                        "date": d.strftime("%Y-%m-%d"),
                        "title": title,
                        "link": link,
                        "lang": f"{lang.upper()}-{country.upper()}",
                        "search_term": termo,
                    })

            itens = sorted(itens, key=lambda x: x["date"], reverse=True)[:max_per_termo]
            cat_results.extend(itens)

        # Deduplicar dentro da categoria
        seen = set()
        unique = []
        for item in cat_results:
            key = item["link"].lower()
            if key not in seen:
                seen.add(key)
                unique.append(item)

        resultados[cat_id] = {
            "icon": cat_info["icon"],
            "label": cat_info["label"],
            "total": len(unique),
            "items": sorted(unique, key=lambda x: x["date"], reverse=True),
        }

    return resultados


def generate_summary(resultados):
    """Gera resumo estatistico dos resultados."""
    total_items = sum(cat["total"] for cat in resultados.values())
    cats_with_results = sum(1 for cat in resultados.values() if cat["total"] > 0)
    cats_empty = sum(1 for cat in resultados.values() if cat["total"] == 0)

    by_country = {"DE": 0, "BR": 0, "other": 0}
    by_lang = {}
    recent_dates = []

    for cat_data in resultados.values():
        for item in cat_data["items"]:
            lang = item.get("lang", "")
            country_code = lang.split("-")[-1] if "-" in lang else "other"
            if country_code in by_country:
                by_country[country_code] += 1
            else:
                by_country["other"] += 1
            by_lang[lang] = by_lang.get(lang, 0) + 1
            recent_dates.append(item["date"])

    return {
        "total_results": total_items,
        "categories_with_results": cats_with_results,
        "categories_empty": cats_empty,
        "by_country": by_country,
        "by_language": by_lang,
        "date_range": {
            "newest": max(recent_dates) if recent_dates else None,
            "oldest": min(recent_dates) if recent_dates else None,
        },
    }


def build_json(resultados, summary, dias):
    """Constroi o JSON final."""
    return {
        "metadata": {
            "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "period_days": dias,
            "version": "2.0",
        },
        "summary": summary,
        "categories": resultados,
    }


def save_json(data, output_dir):
    """Salva o JSON no diretorio de saida."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filepath = os.path.join(output_dir, "results.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"JSON salvo em: {filepath}")
    return filepath


def main():
    print(f"Buscando editais dos ultimos {DAYS} dias...")
    print(f"Categorias: {len(SEARCH_CATEGORIES)}")
    total_terms = sum(len(c["terms"]) for c in SEARCH_CATEGORIES.values())
    print(f"Total de termos de busca: {total_terms}")

    # Buscar
    resultados = buscar_multilingue(SEARCH_CATEGORIES, LANG_COUNTRY_PAIRS, DAYS, MAX_PER_TERM)

    # Resumo
    summary = generate_summary(resultados)

    # Montar JSON
    data = build_json(resultados, summary, DAYS)

    # Salvar JSON
    save_json(data, OUTPUT_DIR)

    print(f"Concluido: {summary['total_results']} resultados em {summary['categories_with_results']} categorias")


if __name__ == "__main__":
    main()
