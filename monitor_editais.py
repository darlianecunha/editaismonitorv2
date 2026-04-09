# -*- coding: utf-8 -*-
"""
Monitor de Editais - Alemanha e Holanda
Sustentabilidade, Maritime AI, Decarbonizacao e Mudancas Climaticas

Gera JSON para pagina web hospedada na Vercel.
Roda via GitHub Actions (cron diario) ou manualmente.
"""

import os
import json
import datetime
from pathlib import Path
from urllib.parse import quote_plus
import re
import feedparser

# ===== Parametros =====
DAYS = int(os.getenv("DAYS_INT", "14"))
MAX_PER_TERM = int(os.getenv("MAX_PER_TERM_INT", "8"))
OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(os.path.dirname(__file__), "data"))

LANG_COUNTRY_PAIRS = [
    ("en", "US"),
    ("de", "DE"),
    ("nl", "NL"),
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
    "NWO_NL": {
        "icon": "🇳🇱",
        "label": "NWO (Holanda)",
        "terms": [
            'site:nwo.nl "climate change" research',
            'site:nwo.nl "sustainability" research grant',
            'site:nwo.nl "maritime" OR "shipping" research',
            'site:nwo.nl "artificial intelligence" sustainability',
            'site:nwo.nl "sustainable development" call',
        ],
    },
    "EUR_Leiden_NL": {
        "icon": "🇳🇱",
        "label": "Erasmus & Leiden (Holanda)",
        "terms": [
            'site:eur.nl "sustainability" research position',
            'site:eur.nl "maritime" OR "port" OR "shipping"',
            'site:eur.nl "postdoctoral" sustainability',
            'site:universiteitleiden.nl "climate change" research',
            'site:universiteitleiden.nl "sustainability" researcher',
            'site:tudelft.nl "maritime" OR "shipping" research',
            'site:tudelft.nl "decarbonisation" OR "decarbonization"',
        ],
    },
    "ThinkTanks": {
        "icon": "🏛️",
        "label": "Think Tanks & Organizacoes",
        "terms": [
            'site:cedelft.eu "maritime" OR "shipping"',
            'site:cedelft.eu "decarbonisation" OR "sustainability"',
            'site:tno.nl "maritime" OR "shipping" sustainability',
            'site:emsa.europa.eu "sustainability" OR "emissions"',
            'site:itf-oecd.org "maritime" OR "shipping" OR "port"',
            '"CE Delft" maritime decarbonisation researcher',
            '"TNO" maritime sustainability research vacancy',
        ],
    },
    "Maritime_AI": {
        "icon": "🚢",
        "label": "Maritime AI & Decarbonizacao",
        "terms": [
            'Germany Netherlands "maritime decarbonisation" research',
            'Europe "shipping emissions" research funding',
            'Europe "port sustainability" research grant',
            '"maritime AI" research position Europe',
            '"shipping decarbonisation" postdoctoral fellowship',
            'Europe "SDG 14" OR "life below water" research',
            '"emission monitoring" vessels research Europe',
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
    "Geral_NL": {
        "icon": "🔍",
        "label": "Geral Holanda",
        "terms": [
            'Netherlands "climate change" research funding',
            'Netherlands "sustainability" research grant',
            'Netherlands "postdoctoral" sustainability fellowship',
            'Nederland duurzaamheid onderzoek subsidie',
        ],
    },
    "BR_Coop": {
        "icon": "🇧🇷",
        "label": "Cooperacao Brasil",
        "terms": [
            'Brazil Germany "climate change" research programme',
            'Brazil Germany sustainability research call',
            'Brasil Alemanha "mudancas climaticas" cooperacao cientifica',
            'Brazil Netherlands sustainability research cooperation',
            'Brasil Holanda pesquisa sustentabilidade',
            'Alemanha "transicao energetica" oportunidades de pesquisa',
        ],
    },
}

# Publico-alvo por categoria (usado na aba Resumo)
TARGET_AUDIENCE = {
    "DAAD": "Pesquisadores internacionais, pos-doutorandos, professores visitantes",
    "DFG": "Pesquisadores com doutorado, grupos de pesquisa em universidades alemas",
    "Humboldt": "Pesquisadores experientes com doutorado (ate 12 anos), todas as areas",
    "BMBF_UBA": "Instituicoes de pesquisa, consorcio universidade-industria, pesquisadores seniors",
    "NWO_NL": "Pesquisadores em instituicoes holandesas, colaboracoes internacionais",
    "EUR_Leiden_NL": "Pos-doutorandos, pesquisadores visitantes, candidatos a posicoes academicas",
    "ThinkTanks": "Pesquisadores aplicados, consultores, analistas de politicas publicas",
    "Maritime_AI": "Pesquisadores em IA, engenharia maritima, sustentabilidade portuaria",
    "Geral_DE": "Pesquisadores internacionais com interesse em colaboracao com Alemanha",
    "Geral_NL": "Pesquisadores internacionais com interesse em colaboracao com Holanda",
    "BR_Coop": "Pesquisadores brasileiros, programas de cooperacao bilateral",
}


# Titulos genericos que devem ser filtrados (paginas de busca, nao editais reais)
TITLE_BLACKLIST_PATTERNS = [
    r"^search\s*[-–]\s*www\.",        # "Search - www.daad.de"
    r"^suche\s*[-–]\s*www\.",          # "Suche - www.daad.de" (alemao)
    r"^zoeken\s*[-–]\s*www\.",         # "Zoeken - www..." (holandes)
    r"^results?\s*[-–]\s*www\.",       # "Results - www..."
    r"^search results?\s",             # "Search results for..."
    r"^suchergebnisse\s",              # "Suchergebnisse" (alemao)
    r"^zoekresultaten\s",              # "Zoekresultaten" (holandes)
    r"^page not found",                # paginas 404
    r"^404\s",                         # paginas 404
    r"^error\s",                       # paginas de erro
    r"^login\s*[-–]",                  # paginas de login
    r"^home\s*[-–]\s*www\.",           # "Home - www.site.com"
    r"^startseite\s*[-–]",            # "Startseite - ..." (pagina inicial alemao)
    r"^homepage\s*[-–]",               # "Homepage - ..."
]
TITLE_BLACKLIST_RE = re.compile("|".join(TITLE_BLACKLIST_PATTERNS), re.IGNORECASE)


def is_generic_title(title):
    """Verifica se o titulo e generico (pagina de busca, 404, etc)."""
    if TITLE_BLACKLIST_RE.search(title):
        return True
    # Titulos muito curtos (menos de 15 chars) provavelmente nao sao uteis
    clean = title.strip()
    if len(clean) < 15:
        return True
    return False


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

                    # Filtrar titulos genericos (paginas de busca, 404, etc)
                    if is_generic_title(title):
                        continue

                    key_link = link.lower()
                    key_title = title.lower()
                    if key_link in vistos_link or key_title in vistos_titulo:
                        continue

                    vistos_link.add(key_link)
                    vistos_titulo.add(key_title)

                    # Capturar descricao/resumo do RSS
                    summary = ""
                    for field in ("summary", "description", "subtitle"):
                        raw = (getattr(e, field, "") or "").strip()
                        if raw:
                            clean = re.sub(r"<[^>]+>", " ", raw).strip()
                            clean = re.sub(r"\s+", " ", clean)
                            if len(clean) > 20:
                                summary = clean[:300]
                                break

                    # Extrair fonte (ex: "Title - Source Name")
                    source = ""
                    if " - " in title:
                        source = title.rsplit(" - ", 1)[-1].strip()

                    itens.append({
                        "date": d.strftime("%Y-%m-%d"),
                        "title": title,
                        "link": link,
                        "summary": summary,
                        "source": source,
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
            "target_audience": TARGET_AUDIENCE.get(cat_id, ""),
            "total": len(unique),
            "items": sorted(unique, key=lambda x: x["date"], reverse=True),
        }

    return resultados


def compute_cv_scores(resultados, cv_profile):
    """Calcula score de compatibilidade entre cada item e o perfil CV."""
    high_kw = [k.lower() for k in cv_profile.get("keywords_high", [])]
    med_kw = [k.lower() for k in cv_profile.get("keywords_medium", [])]
    low_kw = [k.lower() for k in cv_profile.get("keywords_low", [])]
    target_inst = [k.lower() for k in cv_profile.get("target_institutions", [])]

    all_items = []
    for cat_id, cat_data in resultados.items():
        for item in cat_data["items"]:
            text = (item["title"] + " " + item.get("search_term", "")).lower()

            score = 0
            matched = []

            for kw in high_kw:
                if kw in text:
                    score += 10
                    matched.append({"keyword": kw, "weight": "high"})

            for kw in med_kw:
                if kw in text:
                    score += 5
                    matched.append({"keyword": kw, "weight": "medium"})

            for kw in low_kw:
                if kw in text:
                    score += 2
                    matched.append({"keyword": kw, "weight": "low"})

            for inst in target_inst:
                if inst in text:
                    score += 8
                    matched.append({"keyword": inst, "weight": "institution"})

            # Normalizar para 0-100
            max_possible = 80  # estimativa razoavel
            normalized = min(100, round((score / max_possible) * 100))

            all_items.append({
                **item,
                "category": cat_id,
                "category_label": resultados[cat_id]["label"],
                "cv_score": normalized,
                "matched_keywords": matched,
            })

    # Ordenar por score
    all_items.sort(key=lambda x: x["cv_score"], reverse=True)
    return all_items


def generate_summary(resultados):
    """Gera resumo estatistico dos resultados."""
    total_items = sum(cat["total"] for cat in resultados.values())
    cats_with_results = sum(1 for cat in resultados.values() if cat["total"] > 0)
    cats_empty = sum(1 for cat in resultados.values() if cat["total"] == 0)

    by_country = {"DE": 0, "NL": 0, "BR": 0, "US": 0, "other": 0}
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


def build_json(resultados, cv_scores, summary, dias):
    """Constroi o JSON final."""
    return {
        "metadata": {
            "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "period_days": dias,
            "version": "2.0",
        },
        "summary": summary,
        "categories": resultados,
        "cv_matches": cv_scores[:50],  # top 50
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
    # Carregar perfil CV
    cv_path = os.path.join(os.path.dirname(__file__), "cv_profile.json")
    with open(cv_path, "r", encoding="utf-8") as f:
        cv_profile = json.load(f)

    print(f"Buscando editais dos ultimos {DAYS} dias...")
    print(f"Categorias: {len(SEARCH_CATEGORIES)}")
    total_terms = sum(len(c["terms"]) for c in SEARCH_CATEGORIES.values())
    print(f"Total de termos de busca: {total_terms}")

    # Buscar
    resultados = buscar_multilingue(SEARCH_CATEGORIES, LANG_COUNTRY_PAIRS, DAYS, MAX_PER_TERM)

    # CV matching
    cv_scores = compute_cv_scores(resultados, cv_profile)

    # Resumo
    summary = generate_summary(resultados)

    # Montar JSON
    data = build_json(resultados, cv_scores, summary, DAYS)

    # Salvar JSON
    save_json(data, OUTPUT_DIR)

    print(f"Concluido: {summary['total_results']} resultados em {summary['categories_with_results']} categorias")


if __name__ == "__main__":
    main()
