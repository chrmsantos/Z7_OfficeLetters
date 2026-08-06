import docx
for f in ['templates/modelo_mocao.docx','templates/modelo_requer_pesar.docx']:
    d = docx.Document(f)
    print('===', f)
    for p in d.paragraphs:
        t = p.text.strip()
        if t:
            print(repr(t))
