# One-off migration: make templates plural-aware.
# Replaces the hardcoded "nº {{num_mocao}}" with "{{abrev_num}} {{num_mocao}}"
# and "cujo teor é autoexplicativo" with "{{cujo_teor}}" in the docx templates.
import docx

def patch(path):
    d = docx.Document(path)
    changed = 0
    for p in d.paragraphs:
        for r in p.runs:
            if "nº {{num_mocao}}" in r.text:
                r.text = r.text.replace("nº {{num_mocao}}", "{{abrev_num}} {{num_mocao}}")
                changed += 1
            if "cujo teor é autoexplicativo" in r.text:
                r.text = r.text.replace("cujo teor é autoexplicativo", "{{cujo_teor}}")
                changed += 1
    if changed:
        d.save(path)
    print(path, "->", changed, "runs alterados")

patch("templates/modelo_mocao.docx")
patch("templates/modelo_requer_pesar.docx")
