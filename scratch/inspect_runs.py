import docx
for f in ['templates/modelo_mocao.docx', 'templates/modelo_requer_pesar.docx']:
    d = docx.Document(f)
    print('===', f)
    for p in d.paragraphs:
        if 'num_mocao' in p.text or 'autoexplicativo' in p.text:
            print('PARA:', repr(p.text))
            for r in p.runs:
                print('   RUN:', repr(r.text))
