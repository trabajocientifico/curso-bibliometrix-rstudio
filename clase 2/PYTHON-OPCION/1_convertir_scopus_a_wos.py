#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# Convierte exportacion de Scopus en texto plano al formato WoS etiquetado.
#
# Mapeo campos Scopus -> etiquetas WoS de 2 letras:
#   Authors (short)          -> AU
#   AUTHOR FULL NAMES        -> AF
#   Title                    -> TI
#   Journal (from ref line)  -> SO
#   ABSTRACT                 -> AB
#   AUTHOR KEYWORDS          -> DE
#   INDEX KEYWORDS           -> ID
#   AFFILIATIONS             -> C1
#   CORRESPONDENCE ADDRESS   -> RP
#   DOI                      -> DI
#   Year (from ref line)     -> PY
#   Volume (from ref line)   -> VL
#   Issue (from ref line)    -> IS
#   Start page (from ref)    -> BP
#   End page (from ref)      -> EP
#   REFERENCES               -> CR
#   FUNDING DETAILS/TEXT     -> FU / FX
#   PUBLISHER                -> PU
#   ISSN                     -> SN
#   ISBN                     -> BN
#   LANGUAGE OF ORIG DOC     -> LA
#   ABBREVIATED SOURCE TITLE -> J9/JI
#   DOCUMENT TYPE            -> DT
#   OPEN ACCESS              -> OA
#   PUBMED ID                -> PM
#   Scopus URL (EID)         -> UT (adaptado)
#   Article number           -> AR
#
# FIX: "SOURCE: Scopus" se usa como verdadero marcador de fin de registro.
#      Esto maneja exportaciones con y sin el campo OPEN ACCESS, que es
#      el caso al descargar sin filtros de open access.
#
# Uso:
#   python 1_convertir_scopus_a_wos.py
# ============================================================================

import os
import re

# ============================================================
# CONFIGURACION - Editar rutas segun necesidad
# ============================================================
INPUT_FILE  = "input/scopus.txt"
OUTPUT_DIR  = "output"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "scopus_formato_wos.txt")
# ============================================================


def parse_scopus_records(filepath):
    """Parsea el archivo Scopus plaintext y devuelve lista de dicts (registros)."""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        lines = f.read().splitlines()

    records = []
    current_record = {}
    current_field = None
    in_record = False
    header_passed = False

    # Etiquetas que senalan el inicio de un campo conocido
    known_labels = [
        "AUTHOR FULL NAMES:", "DOI:", "AFFILIATIONS:", "ABSTRACT:",
        "AUTHOR KEYWORDS:", "INDEX KEYWORDS:", "FUNDING DETAILS:",
        "REFERENCES:", "CORRESPONDENCE ADDRESS:", "PUBLISHER:",
        "ISSN:", "ISBN:", "CODEN:", "LANGUAGE OF ORIGINAL DOCUMENT:",
        "ABBREVIATED SOURCE TITLE:", "DOCUMENT TYPE:", "PUBLICATION STAGE:",
        "PUBMED ID:", "MANUFACTURERS:", "TRADENAMES:", "OPEN ACCESS:",
        "SOURCE:"
    ]

    # Etiquetas que interrumpen la continuacion del ABSTRACT
    interrupt_labels = [
        "AUTHOR KEYWORDS:", "INDEX KEYWORDS:", "FUNDING",
        "REFERENCES:", "CORRESPONDENCE", "PUBLISHER:",
        "ISSN:", "ISBN:", "CODEN:", "LANGUAGE OF",
        "ABBREVIATED", "DOCUMENT TYPE:", "PUBLICATION STAGE:",
        "OPEN ACCESS:", "PUBMED ID:", "MANUFACTURERS:", "TRADENAMES:",
        "SOURCE:"
    ]

    # Etiquetas que interrumpen la continuacion del FUNDING_TEXT
    funding_interrupt = [
        "REFERENCES:", "CORRESPONDENCE", "PUBLISHER:",
        "ISSN:", "ISBN:", "FUNDING DETAILS:", "FUNDING TEXT",
        "SOURCE:"
    ]

    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # Saltar lineas de cabecera
        if not header_passed:
            if line.startswith("Scopus") or line.startswith("EXPORT DATE:") or line.strip() == "":
                i += 1
                continue
            else:
                header_passed = True

        stripped = line.strip()

        if not in_record:
            if stripped == "":
                i += 1
                continue
            in_record = True
            current_record = {}
            current_field = "AU_SHORT"
            current_record["AU_SHORT"] = stripped
            i += 1
            continue

        # --- Dentro de un registro ---

        if line.startswith("AUTHOR FULL NAMES:"):
            current_field = "AUTHOR_FULL_NAMES"
            current_record[current_field] = line[len("AUTHOR FULL NAMES:"):].strip()

        elif line.startswith("DOI:"):
            current_field = "DOI"
            current_record[current_field] = line[len("DOI:"):].strip()

        elif line.startswith("https://www.scopus.com/"):
            current_record["SCOPUS_URL"] = stripped
            current_field = "SCOPUS_URL"

        elif line.startswith("AFFILIATIONS:"):
            current_field = "AFFILIATIONS"
            current_record[current_field] = line[len("AFFILIATIONS:"):].strip()

        elif line.startswith("ABSTRACT:"):
            current_field = "ABSTRACT"
            current_record[current_field] = line[len("ABSTRACT:"):].strip()

        elif line.startswith("AUTHOR KEYWORDS:"):
            current_field = "AUTHOR_KEYWORDS"
            current_record[current_field] = line[len("AUTHOR KEYWORDS:"):].strip()

        elif line.startswith("INDEX KEYWORDS:"):
            current_field = "INDEX_KEYWORDS"
            current_record[current_field] = line[len("INDEX KEYWORDS:"):].strip()

        elif line.startswith("FUNDING DETAILS:"):
            current_field = "FUNDING_DETAILS"
            val = line[len("FUNDING DETAILS:"):].strip()
            if "FUNDING_DETAILS" in current_record:
                current_record["FUNDING_DETAILS"] = current_record["FUNDING_DETAILS"] + "; " + val
            else:
                current_record["FUNDING_DETAILS"] = val

        elif re.match(r"^FUNDING TEXT", line):
            current_field = "FUNDING_TEXT"
            val = re.sub(r"^FUNDING TEXT \d+:\s*", "", line).strip()
            if "FUNDING_TEXT" in current_record:
                current_record["FUNDING_TEXT"] = current_record["FUNDING_TEXT"] + " " + val
            else:
                current_record["FUNDING_TEXT"] = val

        elif line.startswith("REFERENCES:"):
            current_field = "REFERENCES"
            current_record[current_field] = line[len("REFERENCES:"):].strip()

        elif line.startswith("CORRESPONDENCE ADDRESS:"):
            current_field = "CORRESPONDENCE"
            current_record[current_field] = line[len("CORRESPONDENCE ADDRESS:"):].strip()

        elif line.startswith("PUBLISHER:"):
            current_field = "PUBLISHER"
            current_record[current_field] = line[len("PUBLISHER:"):].strip()

        elif line.startswith("ISSN:"):
            current_field = "ISSN"
            current_record[current_field] = line[len("ISSN:"):].strip()

        elif line.startswith("ISBN:"):
            current_field = "ISBN"
            current_record[current_field] = line[len("ISBN:"):].strip()

        elif line.startswith("CODEN:"):
            current_field = "CODEN"
            current_record[current_field] = line[len("CODEN:"):].strip()

        elif line.startswith("LANGUAGE OF ORIGINAL DOCUMENT:"):
            current_field = "LANGUAGE"
            current_record[current_field] = line[len("LANGUAGE OF ORIGINAL DOCUMENT:"):].strip()

        elif line.startswith("ABBREVIATED SOURCE TITLE:"):
            current_field = "ABBREV_SOURCE"
            current_record[current_field] = line[len("ABBREVIATED SOURCE TITLE:"):].strip()

        elif line.startswith("DOCUMENT TYPE:"):
            current_field = "DOCUMENT_TYPE"
            current_record[current_field] = line[len("DOCUMENT TYPE:"):].strip()

        elif line.startswith("PUBLICATION STAGE:"):
            current_field = "PUB_STAGE"
            current_record[current_field] = line[len("PUBLICATION STAGE:"):].strip()

        elif line.startswith("PUBMED ID:"):
            current_field = "PUBMED_ID"
            current_record[current_field] = line[len("PUBMED ID:"):].strip()

        elif line.startswith("MANUFACTURERS:"):
            current_field = "MANUFACTURERS"
            current_record[current_field] = line[len("MANUFACTURERS:"):].strip()

        elif line.startswith("TRADENAMES:"):
            current_field = "TRADENAMES"
            current_record[current_field] = line[len("TRADENAMES:"):].strip()

        elif line.startswith("OPEN ACCESS:"):
            # OPEN ACCESS ya NO cierra el registro; solo guarda el valor.
            current_field = "OPEN_ACCESS"
            current_record[current_field] = line[len("OPEN ACCESS:"):].strip()

        elif line.startswith("SOURCE:"):
            # SOURCE: Scopus es el verdadero marcador de fin de registro.
            current_record["SOURCE"] = line[len("SOURCE:"):].strip()
            records.append(current_record)
            current_record = {}
            in_record = False
            current_field = None

        elif re.match(r"^\d{8,}(;\s*\d{8,})*\s*$", stripped):
            # Linea de IDs de autores de Scopus
            current_record["AUTHOR_IDS"] = stripped
            current_field = "AUTHOR_IDS"

        elif re.match(r"^\(\d{4}\)\s", stripped):
            # Linea de referencia del journal
            current_record["JOURNAL_REF"] = stripped
            current_field = "JOURNAL_REF"

        elif current_field == "AU_SHORT" and "TITLE" not in current_record:
            if not stripped.startswith("(") and stripped != "" and \
                    current_field in ("AU_SHORT", "AUTHOR_IDS", "AUTHOR_FULL_NAMES"):
                current_record["TITLE"] = stripped
                current_field = "TITLE"

        elif current_field == "AUTHOR_FULL_NAMES" and "TITLE" not in current_record:
            if re.match(r"^\d{8,}", stripped):
                current_record["AUTHOR_IDS"] = stripped
                current_field = "AUTHOR_IDS"
            elif stripped != "" and not stripped.startswith("("):
                current_record["TITLE"] = stripped
                current_field = "TITLE"

        elif current_field == "AUTHOR_IDS" and "TITLE" not in current_record:
            if stripped != "" and not stripped.startswith("("):
                current_record["TITLE"] = stripped
                current_field = "TITLE"

        elif current_field == "TITLE" and "JOURNAL_REF" not in current_record:
            if re.match(r"^\(\d{4}\)\s", stripped):
                current_record["JOURNAL_REF"] = stripped
                current_field = "JOURNAL_REF"
            elif stripped != "":
                current_record["TITLE"] = current_record["TITLE"] + " " + stripped

        elif current_field == "REFERENCES" and stripped != "":
            current_record["REFERENCES"] = current_record["REFERENCES"] + " " + stripped

        elif current_field == "ABSTRACT" and stripped != "" and \
                not any(stripped.startswith(lbl) for lbl in interrupt_labels):
            current_record["ABSTRACT"] = current_record["ABSTRACT"] + " " + stripped

        elif current_field == "FUNDING_TEXT" and stripped != "" and \
                not any(stripped.startswith(lbl) for lbl in funding_interrupt):
            current_record["FUNDING_TEXT"] = current_record["FUNDING_TEXT"] + " " + stripped
        # else: lineas en blanco dentro de registros - saltar

        i += 1

    # Guardar el ultimo registro si el archivo no termina con SOURCE:
    if in_record and current_record:
        records.append(current_record)

    return records


def parse_journal_ref(ref_line):
    """Parsea la linea de referencia del journal: (Year) Journal, Vol (Iss), pp. X-Y."""
    result = {}

    m = re.match(r"^\((\d{4})\)\s*(.*)", ref_line)
    if not m:
        return result

    result["PY"] = m.group(1)
    rest = m.group(2)

    # Quitar "Cited X times" al final
    rest = re.sub(r",?\s*Cited \d+ times\.?\s*$", "", rest)
    rest = re.sub(r",\s*$", "", rest).strip()

    # Patron 1: Journal, VOL (ISSUE), pp. START - END  o  art. no. XXX
    m1 = re.match(
        r"^(.+?),\s*(\d+)\s*\(([^)]+)\)\s*,\s*(?:pp\.\s*(\d+)\s*-\s*(\d+)|art\.\s*no\.\s*(\S+))",
        rest
    )
    if m1:
        result["SO"] = m1.group(1).strip()
        result["VL"] = m1.group(2)
        result["IS"] = m1.group(3)
        if m1.group(4) and m1.group(5):
            result["BP"] = m1.group(4)
            result["EP"] = m1.group(5)
        elif m1.group(6):
            result["AR"] = m1.group(6)
        return result

    # Patron 2: Journal, VOL, pp. START - END  o  art. no. XXX (sin issue)
    m2 = re.match(
        r"^(.+?),\s*(\d+)\s*,\s*(?:pp\.\s*(\d+)\s*-\s*(\d+)|art\.\s*no\.\s*(\S+))",
        rest
    )
    if m2:
        result["SO"] = m2.group(1).strip()
        result["VL"] = m2.group(2)
        if m2.group(3) and m2.group(4):
            result["BP"] = m2.group(3)
            result["EP"] = m2.group(4)
        elif m2.group(5):
            result["AR"] = m2.group(5)
        return result

    # Patron 3: Journal, VOL (ISSUE), sin paginas
    m3 = re.match(r"^(.+?),\s*(\d+)\s*\(([^)]+)\)\s*$", rest)
    if m3:
        result["SO"] = m3.group(1).strip()
        result["VL"] = m3.group(2)
        result["IS"] = m3.group(3)
        return result

    # Patron 4: Journal, VOL solamente
    m4 = re.match(r"^(.+?),\s*(\d+)\s*$", rest)
    if m4:
        result["SO"] = m4.group(1).strip()
        result["VL"] = m4.group(2)
        return result

    # Fallback: solo el nombre del journal
    result["SO"] = rest.split(",")[0].strip()
    return result


def parse_authors_short(au_line):
    """Parsea la lista corta de autores (AU)."""
    # Separar por punto y coma si los hay
    parts = re.split(r";\s*", au_line)
    if len(parts) > 1:
        return [p.strip() for p in parts if p.strip() != ""]

    # Parseo por coma: cada autor es "Apellido, Iniciales"
    tokens = [t.strip() for t in au_line.split(",")]
    authors = []
    i = 0
    while i < len(tokens):
        if i + 1 < len(tokens):
            next_t = tokens[i + 1].strip()
            if re.match(r"^[A-Z]\.?[A-Z]?\.?[A-Z]?\.?\s*$", next_t):
                authors.append(tokens[i].strip() + ", " + next_t)
                i += 2
                continue
        authors.append(tokens[i].strip())
        i += 1
    return authors


def parse_authors_full(af_line):
    """Parsea la lista completa de autores (AF), quitando (id) al final."""
    parts = re.split(r";\s*", af_line)
    authors = []
    for p in parts:
        name = re.sub(r"\s*\(\d+\)\s*$", "", p.strip())
        if name:
            authors.append(name)
    return authors


def convert_references(ref_text):
    """Convierte las referencias Scopus a formato CR de WoS."""
    if not ref_text:
        return []

    refs = re.split(r";\s*\n?", ref_text)
    cr_lines = []

    for ref in refs:
        ref = ref.strip()
        if not ref:
            continue

        # Patron completo: Autor, Titulo, Journal, Vol, Issue?, pp. start-end, (Year)
        m = re.match(
            r"^(.+?),\s+(.+?),\s+(.+?),\s+(\d+)(?:,\s*(\d+))?,\s*(?:pp\.\s*(\d+)-(\d+))?,\s*\((\d{4})\)",
            ref
        )

        if m:
            author  = m.group(1).strip()
            journal = m.group(3).strip()
            vol     = m.group(4)
            year    = m.group(8)
            page    = m.group(6) if m.group(6) else ""
            cr = f"{author}, {year}, {journal.upper()}, V{vol}"
            if page:
                cr += f", P{page}"
            cr_lines.append(cr)
        else:
            # Fallback: extraer autor y anio
            year_m = re.search(r"\((\d{4})\)", ref)
            author_m = re.match(r"^([^,]+(?:,\s*[^,]+)?)", ref)
            if year_m and author_m:
                cr_lines.append(author_m.group(1).strip() + ", " + year_m.group(1))
            elif ref:
                cr_lines.append(ref[:100])

    return cr_lines


def format_wos_field(tag, value):
    """Formatea un campo WoS con indentacion de continuacion para listas."""
    if value is None or (isinstance(value, str) and value == ""):
        return ""
    if isinstance(value, list):
        if len(value) == 0:
            return ""
        lines = []
        for j, v in enumerate(value):
            if j == 0:
                lines.append(f"{tag} {v}")
            else:
                lines.append(f"   {v}")
        return "\n".join(lines)
    else:
        return f"{tag} {value}"


def record_to_wos(rec):
    """Convierte un diccionario de registro Scopus al texto formato WoS."""
    output_lines = []

    # PT
    output_lines.append("PT J")

    # AU
    if rec.get("AU_SHORT"):
        authors_short = parse_authors_short(rec["AU_SHORT"])
        if authors_short:
            output_lines.append(format_wos_field("AU", authors_short))

    # AF
    if rec.get("AUTHOR_FULL_NAMES"):
        authors_full = parse_authors_full(rec["AUTHOR_FULL_NAMES"])
        if authors_full:
            output_lines.append(format_wos_field("AF", authors_full))

    # TI
    if rec.get("TITLE"):
        output_lines.append(format_wos_field("TI", rec["TITLE"]))

    # SO (desde journal reference)
    journal_info = {}
    if rec.get("JOURNAL_REF"):
        journal_info = parse_journal_ref(rec["JOURNAL_REF"])
        if journal_info.get("SO"):
            output_lines.append(format_wos_field("SO", journal_info["SO"]))

    # LA
    if rec.get("LANGUAGE"):
        output_lines.append(format_wos_field("LA", rec["LANGUAGE"]))

    # DT
    if rec.get("DOCUMENT_TYPE"):
        output_lines.append(format_wos_field("DT", rec["DOCUMENT_TYPE"]))

    # DE
    if rec.get("AUTHOR_KEYWORDS"):
        output_lines.append(format_wos_field("DE", rec["AUTHOR_KEYWORDS"]))

    # ID
    if rec.get("INDEX_KEYWORDS"):
        output_lines.append(format_wos_field("ID", rec["INDEX_KEYWORDS"]))

    # AB
    if rec.get("ABSTRACT"):
        output_lines.append(format_wos_field("AB", rec["ABSTRACT"]))

    # C1
    if rec.get("AFFILIATIONS"):
        output_lines.append(format_wos_field("C1", rec["AFFILIATIONS"]))

    # RP
    if rec.get("CORRESPONDENCE"):
        output_lines.append(format_wos_field("RP", rec["CORRESPONDENCE"]))

    # EM
    if rec.get("CORRESPONDENCE"):
        email_m = re.search(r"email:\s*(\S+)", rec["CORRESPONDENCE"])
        if email_m:
            output_lines.append(format_wos_field("EM", email_m.group(1)))

    # FU
    if rec.get("FUNDING_DETAILS"):
        output_lines.append(format_wos_field("FU", rec["FUNDING_DETAILS"]))

    # FX
    if rec.get("FUNDING_TEXT"):
        output_lines.append(format_wos_field("FX", rec["FUNDING_TEXT"]))

    # CR
    cr_lines = []
    if rec.get("REFERENCES"):
        cr_lines = convert_references(rec["REFERENCES"])
        if cr_lines:
            output_lines.append(format_wos_field("CR", cr_lines))

    # NR
    if rec.get("REFERENCES"):
        output_lines.append(format_wos_field("NR", str(len(cr_lines))))

    # PU
    if rec.get("PUBLISHER"):
        output_lines.append(format_wos_field("PU", rec["PUBLISHER"]))

    # SN
    if rec.get("ISSN"):
        output_lines.append(format_wos_field("SN", rec["ISSN"]))

    # BN
    if rec.get("ISBN"):
        output_lines.append(format_wos_field("BN", rec["ISBN"]))

    # J9 / JI
    if rec.get("ABBREV_SOURCE"):
        output_lines.append(format_wos_field("J9", rec["ABBREV_SOURCE"]))
        output_lines.append(format_wos_field("JI", rec["ABBREV_SOURCE"]))

    # PY
    if journal_info.get("PY"):
        output_lines.append(format_wos_field("PY", journal_info["PY"]))

    # VL
    if journal_info.get("VL"):
        output_lines.append(format_wos_field("VL", journal_info["VL"]))

    # IS
    if journal_info.get("IS"):
        output_lines.append(format_wos_field("IS", journal_info["IS"]))

    # BP
    if journal_info.get("BP"):
        output_lines.append(format_wos_field("BP", journal_info["BP"]))

    # EP
    if journal_info.get("EP"):
        output_lines.append(format_wos_field("EP", journal_info["EP"]))

    # AR
    if journal_info.get("AR"):
        output_lines.append(format_wos_field("AR", journal_info["AR"]))

    # DI
    if rec.get("DOI"):
        output_lines.append(format_wos_field("DI", rec["DOI"]))

    # PG - numero de paginas
    if journal_info.get("BP") and journal_info.get("EP"):
        try:
            bp = int(journal_info["BP"])
            ep = int(journal_info["EP"])
            output_lines.append(format_wos_field("PG", str(ep - bp + 1)))
        except (ValueError, TypeError):
            pass

    # PM
    if rec.get("PUBMED_ID"):
        output_lines.append(format_wos_field("PM", rec["PUBMED_ID"]))

    # OA
    if rec.get("OPEN_ACCESS"):
        output_lines.append(format_wos_field("OA", rec["OPEN_ACCESS"].lower()))

    # UT - desde Scopus URL EID
    if rec.get("SCOPUS_URL"):
        eid_m = re.search(r"eid=(2-s2\.0-\d+)", rec["SCOPUS_URL"])
        if eid_m:
            output_lines.append(format_wos_field("UT", f"SCOPUS:{eid_m.group(1)}"))

    # ER
    output_lines.append("ER")

    # Quitar strings vacios que format_wos_field haya devuelto
    output_lines = [l for l in output_lines if l != ""]

    return "\n".join(output_lines)


# ============================================================
# MAIN
# ============================================================
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Parseando archivo Scopus: {INPUT_FILE}")
    records = parse_scopus_records(INPUT_FILE)
    print(f"Registros encontrados: {len(records)}")

    # Escribir formato WoS con BOM UTF-8
    with open(OUTPUT_FILE, "wb") as f:
        # BOM
        f.write(b"\xEF\xBB\xBF")
        f.write("FN Converted from Scopus to WoS Format\n".encode("utf-8"))
        f.write("VR 1.0\n".encode("utf-8"))

        for i, rec in enumerate(records, 1):
            wos_text = record_to_wos(rec)
            f.write((wos_text + "\n").encode("utf-8"))
            if i % 50 == 0:
                print(f"  Convertidos {i}/{len(records)} registros...")

        f.write("EF\n".encode("utf-8"))

    print(f"\n¡Conversion completa! Salida: {OUTPUT_FILE}")
    print(f"Total de registros convertidos: {len(records)}")

    # Validacion rapida
    with open(OUTPUT_FILE, "r", encoding="utf-8-sig") as f:
        content_text = f.read()
    pt_count = len(re.findall(r"\nPT J", content_text))
    er_count = len(re.findall(r"\nER\n", content_text))
    print(f"Validacion: PT count={pt_count}, ER count={er_count}")


if __name__ == "__main__":
    main()
