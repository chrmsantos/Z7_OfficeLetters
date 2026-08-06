from docxtpl import DocxTemplate
import docx

ctx = {
    "num_oficio": "460", "data_extenso": "6 de agosto de 2026",
    "tipo_mocao": "Aplauso", "num_mocao": "350 e 351",
    "falecido": "", "tipo_propositura": "mocao", "sigla_redator": "cms",
    "vocativo": "Reverendíssimo Senhor", "pronome_corpo": "Vossa Reverendíssima",
    "texto_autoria": "do Vereador X", "tratamento_rodape": "Ao Reverendíssimo Senhor",
    "destinatario_nome": "PADRE AGNALDO", "destinatario_endereco": "Pároco",
    "designacao_propositura": "Moções de Aplauso", "copia_art": "cópias das",
    "aprovada_s": "aprovadas", "abrev_num": "nºs",
    "cujo_teor": "cujos teores são autoexplicativos",
}

doc = DocxTemplate("templates/modelo_mocao.docx")
doc.render(ctx)
doc.save("scratch/smoke_out.docx")

d = docx.Document("scratch/smoke_out.docx")
for p in d.paragraphs:
    if p.text.strip():
        print(p.text)
