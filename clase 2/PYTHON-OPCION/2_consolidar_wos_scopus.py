#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# Fusiona archivos WoS y Scopus (ya convertido a formato WoS) en un unico
# archivo, detectando y eliminando registros duplicados.
#
# Correcciones aplicadas para compatibilidad con Tree of Science:
#   1. Cabecera FN = "Clarivate Analytics Web of Science"
#   2. Linea en blanco despues de cada ER (separador de registros)
#   3. Referencias CR de Scopus reformateadas al estilo WoS:
#      WoS:    Autor, Year, JOURNAL_ABBREV, Vvol, Ppage, DOI xxx
#      Scopus: Autor, Year, TITULO..., JOURNAL..., Vvol, Ppage
#      -> Quita el titulo, conserva solo Autor, Year, Journal, Vvol, Ppage
#
# Uso:
#   python 2_consolidar_wos_scopus.py
#
# Salidas:
#   - wos_scopus_consolidado.txt -> Archivo unificado sin duplicados
#   - reporte_consolidado.txt    -> Reporte resumen con detalle de duplicados
# ============================================================================

import os
import re
import unicodedata
from difflib import SequenceMatcher

# ============================================================
# CONFIGURACION - Editar rutas segun necesidad
# ============================================================
WOS_FILE      = "input/wos.txt"
SCOPUS_FILE   = "output/scopus_formato_wos.txt"
OUTPUT_FOLDER = "output"
OUTPUT_FILE   = os.path.join(OUTPUT_FOLDER, "wos_scopus_consolidado.txt")
REPORT_FILE   = os.path.join(OUTPUT_FOLDER, "reporte_consolidado.txt")

TITLE_SIMILARITY_THRESHOLD = 0.85
PRIORITY = "wos"   # "wos" o "scopus" - cual conservar en caso de duplicado
# ============================================================


def string_similarity(a, b):
    """Similitud de cadenas equivalente a difflib.SequenceMatcher.ratio."""
    if a == "" and b == "":
        return 1.0
    if a == "" or b == "":
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def parse_wos_records(filepath):
    """Parsea un archivo en formato WoS etiquetado y devuelve lista de dicts."""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        lines = f.read().splitlines()

    records = []
    current = {}
    current_tag = None

    for raw_line in lines:
        line = raw_line.rstrip("\r")

        if line.startswith("FN ") or line.startswith("VR ") or line.startswith("EF"):
            continue

        # Verificar si es una etiqueta WoS: 2 mayusculas seguidas de un espacio
        is_tag = (len(line) >= 3
                  and line[2] == " "
                  and re.match(r"^[A-Z][A-Z0-9]$", line[:2]))

        if is_tag:
            tag = line[:2]
            value = line[3:]

            if tag == "PT":
                if current:
                    records.append(current)
                current = {"PT": value}
                current_tag = "PT"
            elif tag == "ER":
                if current:
                    records.append(current)
                current = {}
                current_tag = None
            else:
                if tag in current:
                    current[tag] = current[tag] + "\n" + value
                else:
                    current[tag] = value
                current_tag = tag

        elif line.startswith("   ") and current_tag is not None and current:
            # Linea de continuacion
            current[current_tag] = current[current_tag] + "\n" + line[3:]

    if current:
        records.append(current)

    return records


def normalize_doi(doi):
    """Normaliza DOI para comparacion."""
    if not doi:
        return None
    doi = doi.strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    return doi


def normalize_title(title):
    """Normaliza titulo: minusculas, sin acentos, sin puntuacion, espacios colapsados."""
    if not title:
        return ""
    t = re.sub(r"\s+", " ", title).lower()
    # Quitar acentos
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    # Quitar caracteres no alfanumericos ni espacios
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def reformat_scopus_cr(cr_text):
    """Reformatea las referencias CR provenientes de Scopus al estilo WoS."""
    if not cr_text:
        return cr_text

    lines = cr_text.split("\n")
    reformatted = []

    for line in lines:
        line = line.strip()
        if line == "":
            continue

        # Buscar el patron: ..., Vdigits, ...
        v_match = re.search(r",\s*(V\d+)", line)

        if v_match:
            before_v = line[:v_match.start()]
            from_v = line[v_match.start():]

            parts = [p.strip() for p in before_v.split(",")]

            # Buscar anio (numero de 4 digitos)
            year_idx = None
            year_val = None
            for idx, part in enumerate(parts):
                if re.match(r"^\d{4}$", part.strip()):
                    year_val = part.strip()
                    year_idx = idx
                    break

            if year_idx is not None:
                # Autor = todo antes del anio
                author = ", ".join(parts[:year_idx]).strip()

                # Journal = ultimo segmento despues del anio (justo antes de Vxx)
                after_year = parts[year_idx + 1:] if year_idx < len(parts) - 1 else []
                journal = after_year[-1].strip() if after_year else None

                # Limpiar from_v
                from_v_clean = re.sub(r"^,\s*", "", from_v).strip()

                if author and journal:
                    new_cr = f"{author}, {year_val}, {journal}, {from_v_clean}"
                elif author:
                    new_cr = f"{author}, {year_val}, {from_v_clean}"
                else:
                    new_cr = line
                reformatted.append(new_cr)
            else:
                reformatted.append(line)
        else:
            reformatted.append(line)

    return "\n".join(reformatted)


def is_scopus_record(rec):
    """Indica si el registro proviene de Scopus segun el campo UT."""
    ut = rec.get("UT")
    if not ut:
        return False
    return "SCOPUS:" in ut


def record_to_wos_text(rec):
    """Convierte un dict de registro a texto en formato WoS etiquetado."""
    lines = []
    lines.append("PT " + rec.get("PT", "J"))

    field_order = [
        "AU", "AF", "TI", "SO", "LA", "DT", "DE", "ID", "AB",
        "C1", "C3", "RP", "EM", "RI", "OI",
        "FU", "FX", "CR", "NR", "TC", "Z9", "U1", "U2",
        "PU", "PI", "PA", "SN", "EI", "BN",
        "J9", "JI", "PD", "PY", "VL", "IS", "SI",
        "BP", "EP", "AR", "DI", "EA", "PG",
        "PM", "WC", "WE", "SC", "GA", "UT", "OA", "HC", "HP", "DA"
    ]

    written = {"PT"}

    for tag in field_order:
        if tag in rec:
            value = rec[tag]

            # Reformatear CR para registros de origen Scopus
            if tag == "CR" and is_scopus_record(rec):
                value = reformat_scopus_cr(value)

            value_lines = value.split("\n")
            lines.append(f"{tag} {value_lines[0]}")
            for vl in value_lines[1:]:
                lines.append(f"   {vl}")
            written.add(tag)

    # Escribir cualquier etiqueta restante fuera del orden predefinido
    for tag, value in rec.items():
        if tag not in written:
            value_lines = value.split("\n")
            lines.append(f"{tag} {value_lines[0]}")
            for vl in value_lines[1:]:
                lines.append(f"   {vl}")

    lines.append("ER")
    return "\n".join(lines)


def merge_records(wos_records, scopus_records, threshold=0.85, priority="wos"):
    """Fusiona registros detectando duplicados por DOI y similitud de titulo."""
    # Construir indice por DOI para registros WoS
    wos_by_doi = {}
    for rec in wos_records:
        doi = normalize_doi(rec.get("DI"))
        if doi:
            wos_by_doi[doi] = rec

    # Lista de titulos WoS
    wos_titles = [(normalize_title(rec.get("TI", "")), rec) for rec in wos_records]

    merged = list(wos_records)
    duplicates = []
    added_from_scopus = 0
    skipped_doi = 0
    skipped_title = 0

    for s_rec in scopus_records:
        s_doi = normalize_doi(s_rec.get("DI"))
        is_dup = False

        # Verificar coincidencia por DOI
        if s_doi and s_doi in wos_by_doi:
            w_rec = wos_by_doi[s_doi]
            duplicates.append({
                "wos": w_rec,
                "scopus": s_rec,
                "match_type": "DOI",
                "score": 1.0
            })
            skipped_doi += 1
            is_dup = True

        # Verificar similitud por titulo
        if not is_dup:
            s_title = normalize_title(s_rec.get("TI", ""))
            if s_title:
                best_score = 0
                best_match = None

                for w_title, w_rec in wos_titles:
                    if not w_title:
                        continue
                    len_ratio = len(s_title) / max(len(w_title), 1)
                    if len_ratio < 0.7 or len_ratio > 1.4:
                        continue
                    score = string_similarity(s_title, w_title)
                    if score > best_score:
                        best_score = score
                        best_match = w_rec

                if best_score >= threshold:
                    duplicates.append({
                        "wos": best_match,
                        "scopus": s_rec,
                        "match_type": "TITLE",
                        "score": best_score
                    })
                    skipped_title += 1
                    is_dup = True

        if not is_dup:
            merged.append(s_rec)
            added_from_scopus += 1

    stats = {
        "wos_total":         len(wos_records),
        "scopus_total":      len(scopus_records),
        "duplicates_doi":    skipped_doi,
        "duplicates_title":  skipped_title,
        "added_from_scopus": added_from_scopus,
        "merged_total":      len(merged),
        "priority":          priority
    }

    return merged, duplicates, stats


def generate_report(stats, duplicates, report_path):
    """Genera el reporte de texto con el detalle de los duplicados."""
    lines = []

    sep_eq = "=" * 70
    sep_dash = "-" * 70

    lines.append(sep_eq)
    lines.append("  REPORTE DE CONSOLIDACION Y DESDUPLICACION")
    lines.append(sep_eq)
    lines.append("")
    lines.append(f"  Registros WoS:                  {stats['wos_total']}")
    lines.append(f"  Registros Scopus:               {stats['scopus_total']}")
    lines.append(f"  Total antes de desduplicar:     {stats['wos_total'] + stats['scopus_total']}")
    lines.append("")
    lines.append(f"  Duplicados por DOI:             {stats['duplicates_doi']}")
    lines.append(f"  Duplicados por similitud titulo:{stats['duplicates_title']}")
    lines.append(f"  Total duplicados eliminados:    {stats['duplicates_doi'] + stats['duplicates_title']}")
    lines.append("")
    lines.append(f"  Unicos anadidos desde Scopus:   {stats['added_from_scopus']}")
    lines.append(f"  Prioridad en duplicado:         {stats['priority'].upper()}")
    lines.append("")
    lines.append(f"  REGISTROS FINALES:              {stats['merged_total']}")
    lines.append(sep_eq)
    lines.append("")

    if duplicates:
        lines.append(sep_dash)
        lines.append("  DETALLE DE DUPLICADOS")
        lines.append(sep_dash)
        lines.append("")

        for i, dup in enumerate(duplicates, 1):
            w_title = re.sub(r"\s+", " ", dup["wos"].get("TI", "N/A"))[:100]
            s_title = re.sub(r"\s+", " ", dup["scopus"].get("TI", "N/A"))[:100]
            doi = dup["wos"].get("DI") or dup["scopus"].get("DI") or "N/A"

            match_info = f"  [{i:3d}] Match: {dup['match_type']}"
            if dup["match_type"] == "TITLE":
                match_info += f" (similitud: {dup['score'] * 100:.2f}%)"
            lines.append(match_info)
            lines.append(f"        DOI:    {doi}")
            lines.append(f"        WoS:    {w_title}")
            lines.append(f"        Scopus: {s_title}")
            lines.append("")

    # Escribir con BOM
    with open(report_path, "wb") as f:
        f.write(b"\xEF\xBB\xBF")
        f.write("\n".join(lines).encode("utf-8"))

    return report_path


# ============================================================
# MAIN
# ============================================================
def main():
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    print(f"Cargando archivo WoS: {WOS_FILE}")
    wos_records = parse_wos_records(WOS_FILE)
    print(f"  -> {len(wos_records)} registros\n")

    print(f"Cargando archivo Scopus: {SCOPUS_FILE}")
    scopus_records = parse_wos_records(SCOPUS_FILE)
    print(f"  -> {len(scopus_records)} registros\n")

    print("Fusionando y desduplicando...")
    merged, duplicates, stats = merge_records(
        wos_records, scopus_records,
        threshold=TITLE_SIMILARITY_THRESHOLD,
        priority=PRIORITY
    )

    # Escribir archivo fusionado con formato WoS exacto
    print(f"\nEscribiendo archivo consolidado: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "wb") as f:
        f.write(b"\xEF\xBB\xBF")  # BOM
        f.write("FN Clarivate Analytics Web of Science\n".encode("utf-8"))
        f.write("VR 1.0\n".encode("utf-8"))

        for rec in merged:
            wos_text = record_to_wos_text(rec)
            # Linea en blanco despues de cada ER (compatibilidad Tree of Science)
            f.write((wos_text + "\n\n").encode("utf-8"))

        f.write("EF\n".encode("utf-8"))

    report_path = generate_report(stats, duplicates, REPORT_FILE)

    # Validacion
    with open(OUTPUT_FILE, "r", encoding="utf-8-sig") as f:
        content = f.read()
    pt_count = len(re.findall(r"\nPT ", content))
    er_count = len(re.findall(r"\nER\n", content))

    print()
    sep = "=" * 50
    print(sep)
    print("  RESUMEN DE CONSOLIDACION")
    print(sep)
    print(f"  Registros WoS:            {stats['wos_total']}")
    print(f"  Registros Scopus:         {stats['scopus_total']}")
    print(f"  Duplicados (DOI):         {stats['duplicates_doi']}")
    print(f"  Duplicados (titulo):      {stats['duplicates_title']}")
    print(f"  Unicos desde Scopus:      {stats['added_from_scopus']}")
    print(f"  TOTAL CONSOLIDADO:        {stats['merged_total']}")
    print(f"  Validacion: PT={pt_count}, ER={er_count}")
    print(sep)
    print(f"\n  Salida:  {OUTPUT_FILE}")
    print(f"  Reporte: {report_path}")


if __name__ == "__main__":
    main()
