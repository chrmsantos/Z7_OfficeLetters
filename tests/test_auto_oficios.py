"""
Testes unitários para auto_oficios.py
Executar com:  pytest tests/ -v
"""
import sys
import os
import json
import logging
import winreg
import pytest
from pathlib import Path
from logging.handlers import RotatingFileHandler
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_oficios import (
    limpar_json_da_resposta,
    validar_dados_mocao,
    formatar_autores,
    processar_destinatario,
    normalizar_numero_mocao,
    construir_nome_arquivo,
    resolver_arquivo_preferencial,
    listar_proposituras,
    ler_arquivo_mocoes,
    configurar_logging,
    _salvar_api_key_no_ambiente,
    obter_api_key,
)
import auto_oficios


# =============================================================================
# limpar_json_da_resposta
# =============================================================================
class TestLimparJsonDaResposta:

    def test_json_puro_sem_marcador(self):
        texto = '{"tipo_mocao": "Aplauso"}'
        assert limpar_json_da_resposta(texto) == '{"tipo_mocao": "Aplauso"}'

    def test_marcador_json(self):
        texto = '```json\n{"tipo_mocao": "Aplauso"}\n```'
        assert limpar_json_da_resposta(texto) == '{"tipo_mocao": "Aplauso"}'

    def test_marcador_generico(self):
        texto = '```\n{"tipo_mocao": "Apelo"}\n```'
        assert limpar_json_da_resposta(texto) == '{"tipo_mocao": "Apelo"}'

    def test_espacos_e_quebras_de_linha_extras(self):
        texto = '  \n```json\n{"a": 1}\n```\n  '
        assert limpar_json_da_resposta(texto) == '{"a": 1}'

    def test_resultado_e_json_valido_apos_limpeza(self):
        texto = '```json\n{"tipo_mocao": "Aplauso", "numero_mocao": "42"}\n```'
        resultado = json.loads(limpar_json_da_resposta(texto))
        assert resultado["numero_mocao"] == "42"


# =============================================================================
# validar_dados_mocao
# =============================================================================
class TestValidarDadosMocao:

    def _dados_validos(self):
        return {
            "tipo_mocao": "Aplauso",
            "numero_mocao": "123",
            "autores": ["Alex Dantas"],
            "destinatarios": [{"nome": "Fulano de Tal"}],
        }

    def test_dados_completos_nao_levanta_excecao(self):
        validar_dados_mocao(self._dados_validos())

    def test_tipo_apelo_valido(self):
        d = self._dados_validos()
        d["tipo_mocao"] = "Apelo"
        validar_dados_mocao(d)

    def test_tipo_mocao_invalido(self):
        d = self._dados_validos()
        d["tipo_mocao"] = "Homenagem"
        with pytest.raises(ValueError, match="tipo_mocao"):
            validar_dados_mocao(d)

    def test_campo_tipo_mocao_ausente(self):
        d = self._dados_validos()
        del d["tipo_mocao"]
        with pytest.raises(ValueError):
            validar_dados_mocao(d)

    def test_campo_autores_ausente(self):
        d = self._dados_validos()
        del d["autores"]
        with pytest.raises(ValueError):
            validar_dados_mocao(d)

    def test_campo_destinatarios_ausente(self):
        d = self._dados_validos()
        del d["destinatarios"]
        with pytest.raises(ValueError):
            validar_dados_mocao(d)

    def test_autores_lista_vazia(self):
        d = self._dados_validos()
        d["autores"] = []
        with pytest.raises(ValueError):
            validar_dados_mocao(d)

    def test_destinatarios_lista_vazia(self):
        d = self._dados_validos()
        d["destinatarios"] = []
        with pytest.raises(ValueError):
            validar_dados_mocao(d)

    def test_autores_nao_e_lista(self):
        d = self._dados_validos()
        d["autores"] = "Alex Dantas"
        with pytest.raises(ValueError, match="lista"):
            validar_dados_mocao(d)

    def test_destinatario_sem_nome(self):
        d = self._dados_validos()
        d["destinatarios"] = [{"nome": ""}]
        with pytest.raises(ValueError, match="nome"):
            validar_dados_mocao(d)

    def test_destinatario_sem_chave_nome(self):
        d = self._dados_validos()
        d["destinatarios"] = [{"cargo": "Secretário"}]
        with pytest.raises(ValueError, match="nome"):
            validar_dados_mocao(d)

    def test_multiplos_destinatarios_validos(self):
        d = self._dados_validos()
        d["destinatarios"] = [{"nome": "Fulano"}, {"nome": "Ciclano"}]
        validar_dados_mocao(d)

    def test_segundo_destinatario_sem_nome(self):
        d = self._dados_validos()
        d["destinatarios"] = [{"nome": "Fulano"}, {"nome": ""}]
        with pytest.raises(ValueError):
            validar_dados_mocao(d)


# =============================================================================
# formatar_autores
# =============================================================================
class TestFormatarAutores:

    def test_autor_unico_conhecido_texto(self):
        texto, _ = formatar_autores(["Alex Dantas"])
        assert texto == "do vereador Alex Dantas"

    def test_autor_unico_conhecido_sigla(self):
        _, sigla = formatar_autores(["Alex Dantas"])
        assert sigla == "AD"

    def test_autor_unico_desconhecido_sigla(self):
        _, sigla = formatar_autores(["Vereador Fantasma"])
        assert sigla == "INDEF"

    def test_dois_autores_texto(self):
        texto, _ = formatar_autores(["Alex Dantas", "Arnaldo Alves"])
        assert "dos vereadores" in texto
        assert "Alex Dantas" in texto
        assert "Arnaldo Alves" in texto

    def test_dois_autores_sigla(self):
        _, sigla = formatar_autores(["Alex Dantas", "Arnaldo Alves"])
        assert sigla == "AD-AA"

    def test_tres_autores_sigla(self):
        _, sigla = formatar_autores(["Alex Dantas", "Arnaldo Alves", "Cabo Dorigon"])
        assert sigla == "AD-AA-CD"

    def test_tres_autores_texto_usa_e(self):
        texto, _ = formatar_autores(["Alex Dantas", "Arnaldo Alves", "Cabo Dorigon"])
        assert " e " in texto

    def test_busca_sigla_case_insensitive(self):
        _, sigla = formatar_autores(["alex dantas"])
        assert sigla == "AD"

    def test_autor_com_acento_no_mapa(self):
        _, sigla = formatar_autores(["Celso Ávila"])
        assert sigla == "CLAB"

    def test_mistura_conhecido_desconhecido(self):
        _, sigla = formatar_autores(["Alex Dantas", "Vereador X"])
        assert sigla == "AD-INDEF"


# =============================================================================
# processar_destinatario
# =============================================================================
class TestProcessarDestinatario:

    def _dest_simples(self, **kwargs):
        base = {
            "nome": "João Silva",
            "is_prefeito": False,
            "is_instituicao": False,
            "cargo_ou_tratamento": "",
            "endereco": "",
            "email": "",
        }
        base.update(kwargs)
        return base

    def test_prefeito_por_flag(self):
        dest = self._dest_simples(nome="Rafael Piovezan", is_prefeito=True)
        r = processar_destinatario(dest)
        assert r["vocativo"] == "Excelentíssimo Senhor Prefeito"
        assert r["pronome_corpo"] == "Vossa Excelência"
        assert r["envio"] == "Protocolo"
        assert r["destinatario_nome"] == "RAFAEL PIOVEZAN"

    def test_prefeito_por_nome(self):
        dest = self._dest_simples(nome="o Prefeito Municipal")
        r = processar_destinatario(dest)
        assert r["pronome_corpo"] == "Vossa Excelência"

    def test_prefeito_endereco_fixo(self):
        dest = self._dest_simples(is_prefeito=True)
        r = processar_destinatario(dest)
        assert "Oeste/SP" in r["destinatario_endereco"]
        assert "Prefeito Municipal" in r["destinatario_endereco"]

    def test_envio_email_tem_prioridade(self):
        dest = self._dest_simples(endereco="Rua X, 123", email="teste@exemplo.com")
        r = processar_destinatario(dest)
        assert r["envio"] == "E-mail"

    def test_envio_carta_quando_endereco_sem_email(self):
        dest = self._dest_simples(endereco="Rua X, 123")
        r = processar_destinatario(dest)
        assert r["envio"] == "Carta"

    def test_envio_em_maos_sem_dados_contato(self):
        dest = self._dest_simples()
        r = processar_destinatario(dest)
        assert r["envio"] == "Em Mãos"

    def test_nome_convertido_para_maiusculas(self):
        dest = self._dest_simples(nome="João Silva")
        r = processar_destinatario(dest)
        assert r["destinatario_nome"] == "JOÃO SILVA"

    def test_pessoa_fisica_tratamento_rodape(self):
        dest = self._dest_simples()
        r = processar_destinatario(dest)
        assert r["tratamento_rodape"] == "Ao Ilustríssimo Senhor"

    def test_instituicao_tratamento_ao(self):
        dest = self._dest_simples(nome="Câmara Municipal", is_instituicao=True)
        r = processar_destinatario(dest)
        assert r["tratamento_rodape"] == "Ao"

    def test_instituicao_começa_com_a_tratamento_a(self):
        dest = self._dest_simples(nome="ABCD Fundação", is_instituicao=True)
        r = processar_destinatario(dest)
        assert r["tratamento_rodape"] == "À"

    def test_pronome_pessoa_fisica(self):
        dest = self._dest_simples()
        r = processar_destinatario(dest)
        assert r["pronome_corpo"] == "Vossa Senhoria"

    def test_endereco_concatena_cargo_e_endereco(self):
        dest = self._dest_simples(
            cargo_ou_tratamento="Secretário de Saúde",
            endereco="Av. das Flores, 100",
        )
        r = processar_destinatario(dest)
        assert "Secretário de Saúde" in r["destinatario_endereco"]
        assert "Av. das Flores, 100" in r["destinatario_endereco"]

    def test_endereco_inclui_email(self):
        dest = self._dest_simples(cargo_ou_tratamento="Diretor", email="dir@exemplo.com")
        r = processar_destinatario(dest)
        assert "dir@exemplo.com" in r["destinatario_endereco"]


# =============================================================================
# normalizar_numero_mocao
# =============================================================================
class TestNormalizarNumeroMocao:

    def test_numero_puro_nao_alterado(self):
        assert normalizar_numero_mocao("124") == "124"

    def test_remove_sufixo_barra_ano_longo(self):
        assert normalizar_numero_mocao("124/2026") == "124"

    def test_remove_sufixo_traco_ano_longo(self):
        assert normalizar_numero_mocao("124-2026") == "124"

    def test_remove_sufixo_barra_ano_curto(self):
        assert normalizar_numero_mocao("124/26") == "124"

    def test_remove_sufixo_traco_ano_curto(self):
        assert normalizar_numero_mocao("124-26") == "124"

    def test_remove_espacos_residuais(self):
        assert normalizar_numero_mocao("  124  ") == "124"

    def test_sufixo_nao_numerico_nao_removido(self):
        assert normalizar_numero_mocao("124-A") == "124-A"

    @pytest.mark.parametrize("entrada,esperado", [
        ("001/2026", "001"),
        ("999-2025", "999"),
        ("42/25", "42"),
        ("7", "7"),
        ("100/2026", "100"),
    ])
    def test_parametrizado(self, entrada, esperado):
        assert normalizar_numero_mocao(entrada) == esperado


# =============================================================================
# construir_nome_arquivo
# =============================================================================
class TestConstruirNomeArquivo:

    def _nome(self, **kwargs):
        params = dict(
            num_oficio_str="001",
            sigla_servidor="js",
            tipo_mocao="Aplauso",
            num_mocao="124",
            envio="E-mail",
            nome_dest="Fulano de Tal",
            sigla_autores="AD",
        )
        params.update(kwargs)
        return construir_nome_arquivo(**params)

    def test_extensao_docx(self):
        assert self._nome().endswith(".docx")

    def test_contem_numero_oficio(self):
        assert "001" in self._nome()

    def test_contem_tipo_mocao(self):
        assert "Aplauso" in self._nome()

    def test_contem_numero_mocao_com_ano(self):
        assert "124-26" in self._nome()

    def test_contem_sigla_autor(self):
        assert "AD" in self._nome()

    def test_envio_em_minusculo(self):
        assert "e-mail" in self._nome(envio="E-mail")

    def test_ano_aparece_exatamente_uma_vez(self):
        assert self._nome(num_mocao="124").count("-26") == 1

    def test_remove_caracteres_invalidos_windows(self):
        nome = construir_nome_arquivo(
            num_oficio_str="001", sigla_servidor="js",
            tipo_mocao="Aplauso", num_mocao="124",
            envio="Em Mãos", nome_dest='Nome "Ilegal" <teste>',
            sigla_autores="AD",
        )
        for char in r'\/*?:"<>|':
            assert char not in nome

    def test_sigla_servidor_refletida(self):
        assert "redator" in self._nome(sigla_servidor="redator")


# =============================================================================
# resolver_arquivo_preferencial
# =============================================================================
class TestResolverArquivoPreferencial:

    def test_retorna_proprio_quando_e_unico(self, tmp_path):
        f = tmp_path / "mocoes.txt"
        f.write_text("conteudo")
        assert resolver_arquivo_preferencial(str(f)) == str(f)

    def test_prefere_txt_sobre_docx(self, tmp_path):
        txt = tmp_path / "mocoes.txt"
        docx = tmp_path / "mocoes.docx"
        txt.write_text("c")
        docx.write_bytes(b"c")
        assert resolver_arquivo_preferencial(str(docx)) == str(txt)

    def test_prefere_docx_sobre_odt(self, tmp_path):
        docx = tmp_path / "mocoes.docx"
        odt = tmp_path / "mocoes.odt"
        docx.write_bytes(b"c")
        odt.write_bytes(b"c")
        assert resolver_arquivo_preferencial(str(odt)) == str(docx)

    def test_prefere_odt_sobre_pdf(self, tmp_path):
        odt = tmp_path / "mocoes.odt"
        pdf = tmp_path / "mocoes.pdf"
        odt.write_bytes(b"c")
        pdf.write_bytes(b"c")
        assert resolver_arquivo_preferencial(str(pdf)) == str(odt)

    def test_prefere_txt_sobre_pdf(self, tmp_path):
        txt = tmp_path / "arq.txt"
        pdf = tmp_path / "arq.pdf"
        txt.write_text("x")
        pdf.write_bytes(b"x")
        assert resolver_arquivo_preferencial(str(pdf)) == str(txt)

    def test_retorna_melhor_variante_existente_quando_superior_ausente(self, tmp_path):
        odt = tmp_path / "mocoes.odt"
        pdf = tmp_path / "mocoes.pdf"
        odt.write_bytes(b"c")
        pdf.write_bytes(b"c")
        # .txt e .docx e .doc não existem; deve retornar .odt
        assert resolver_arquivo_preferencial(str(pdf)) == str(odt)

    def test_retorna_original_quando_nenhuma_variante_existe(self, tmp_path):
        caminho = str(tmp_path / "naoexiste.pdf")
        assert resolver_arquivo_preferencial(caminho) == caminho

    def test_nao_cruza_diretorios(self, tmp_path):
        subdir = tmp_path / "sub"
        subdir.mkdir()
        odt = subdir / "arq.odt"
        odt.write_bytes(b"c")
        txt_outro_dir = tmp_path / "arq.txt"
        txt_outro_dir.write_text("x")
        # txt está em dir diferente; não deve ser retornado
        resultado = resolver_arquivo_preferencial(str(odt))
        assert resultado == str(odt)


# =============================================================================
# listar_proposituras
# =============================================================================
class TestListarProposituras:

    def _patch_pasta(self, monkeypatch, pasta: str):
        monkeypatch.setattr(auto_oficios, "PASTA_PROPOSITURAS", pasta)

    def test_pasta_inexistente_retorna_lista_vazia(self, tmp_path, monkeypatch):
        self._patch_pasta(monkeypatch, str(tmp_path / "naoexiste"))
        assert listar_proposituras() == []

    def test_pasta_vazia_retorna_lista_vazia(self, tmp_path, monkeypatch):
        self._patch_pasta(monkeypatch, str(tmp_path))
        assert listar_proposituras() == []

    def test_arquivo_txt_retornado(self, tmp_path, monkeypatch):
        self._patch_pasta(monkeypatch, str(tmp_path))
        (tmp_path / "mocoes.txt").write_text("x")
        resultado = listar_proposituras()
        assert len(resultado) == 1
        assert resultado[0].suffix == ".txt"

    def test_formatos_nao_suportados_ignorados(self, tmp_path, monkeypatch):
        self._patch_pasta(monkeypatch, str(tmp_path))
        (tmp_path / "mocoes.txt").write_text("x")
        (tmp_path / "imagem.png").write_bytes(b"x")
        (tmp_path / "dados.csv").write_text("x")
        resultado = listar_proposituras()
        assert len(resultado) == 1

    def test_multiplos_arquivos_distintos_retornados(self, tmp_path, monkeypatch):
        self._patch_pasta(monkeypatch, str(tmp_path))
        (tmp_path / "mocoes_marco.txt").write_text("x")
        (tmp_path / "mocoes_abril.docx").write_bytes(b"x")
        resultado = listar_proposituras()
        assert len(resultado) == 2

    def test_duplicata_retorna_apenas_preferencial(self, tmp_path, monkeypatch):
        self._patch_pasta(monkeypatch, str(tmp_path))
        (tmp_path / "mocoes.txt").write_text("x")
        (tmp_path / "mocoes.docx").write_bytes(b"x")
        (tmp_path / "mocoes.pdf").write_bytes(b"x")
        resultado = listar_proposituras()
        assert len(resultado) == 1
        assert resultado[0].suffix == ".txt"

    def test_duplicata_prefere_docx_quando_sem_txt(self, tmp_path, monkeypatch):
        self._patch_pasta(monkeypatch, str(tmp_path))
        (tmp_path / "mocoes.docx").write_bytes(b"x")
        (tmp_path / "mocoes.odt").write_bytes(b"x")
        resultado = listar_proposituras()
        assert len(resultado) == 1
        assert resultado[0].suffix == ".docx"

    def test_lista_ordenada_alfabeticamente(self, tmp_path, monkeypatch):
        self._patch_pasta(monkeypatch, str(tmp_path))
        (tmp_path / "z_ultimo.txt").write_text("x")
        (tmp_path / "a_primeiro.txt").write_text("x")
        (tmp_path / "m_meio.txt").write_text("x")
        nomes = [p.name for p in listar_proposituras()]
        assert nomes == sorted(nomes)

    def test_gitkeep_ignorado(self, tmp_path, monkeypatch):
        self._patch_pasta(monkeypatch, str(tmp_path))
        (tmp_path / ".gitkeep").write_bytes(b"")
        (tmp_path / "mocoes.txt").write_text("x")
        resultado = listar_proposituras()
        assert len(resultado) == 1
class TestLerArquivoMocoes:

    def test_le_arquivo_txt_utf8(self, tmp_path):
        f = tmp_path / "mocoes.txt"
        f.write_text("MOÇÃO Nº 1\nTexto da moção.", encoding="utf-8")
        assert ler_arquivo_mocoes(str(f)) == "MOÇÃO Nº 1\nTexto da moção."

    def test_formato_invalido_levanta_value_error(self, tmp_path):
        f = tmp_path / "mocoes.xyz"
        f.write_text("x")
        with pytest.raises(ValueError, match="suportado"):
            ler_arquivo_mocoes(str(f))

    def test_le_arquivo_docx_via_mock(self, tmp_path):
        caminho = str(tmp_path / "mocoes.docx")
        mock_doc = MagicMock()
        mock_doc.paragraphs = [
            MagicMock(text="MOÇÃO Nº 1"),
            MagicMock(text="Texto da moção."),
        ]
        with patch("docx.Document", return_value=mock_doc):
            resultado = ler_arquivo_mocoes(caminho)
        assert resultado == "MOÇÃO Nº 1\nTexto da moção."

    def test_pdf_sem_pypdf_levanta_import_error(self, tmp_path):
        f = tmp_path / "mocoes.pdf"
        f.write_bytes(b"%PDF-1.4")
        with patch.dict("sys.modules", {"pypdf": None}):
            with pytest.raises(ImportError, match="pypdf"):
                ler_arquivo_mocoes(str(f))

    def test_txt_preserva_conteudo_completo(self, tmp_path):
        conteudo = "MOÇÃO Nº 1\n\nMOÇÃO Nº 2\nSegundo texto."
        f = tmp_path / "mocoes.txt"
        f.write_text(conteudo, encoding="utf-8")
        assert ler_arquivo_mocoes(str(f)) == conteudo


# =============================================================================
# configurar_logging
# =============================================================================
class TestConfigurarLogging:

    def setup_method(self):
        auto_oficios.logger.handlers.clear()

    def teardown_method(self):
        auto_oficios.logger.handlers.clear()
        sys.excepthook = sys.__excepthook__

    def test_cria_arquivo_de_log(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        log_path = configurar_logging()
        assert Path(log_path).exists()

    def test_nome_arquivo_contem_sessao_id(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        log_path = configurar_logging()
        assert auto_oficios.SESSAO_ID in log_path

    def test_usa_rotating_file_handler(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        file_handlers = [
            h for h in auto_oficios.logger.handlers
            if isinstance(h, RotatingFileHandler)
        ]
        assert len(file_handlers) == 1

    def test_rotating_handler_max_bytes(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        fh = next(h for h in auto_oficios.logger.handlers if isinstance(h, RotatingFileHandler))
        assert fh.maxBytes == 2 * 1024 * 1024

    def test_rotating_handler_backup_count(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        fh = next(h for h in auto_oficios.logger.handlers if isinstance(h, RotatingFileHandler))
        assert fh.backupCount == 5

    def test_console_level_warning_por_padrao(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging(verbose=False)
        console_handlers = [
            h for h in auto_oficios.logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        ]
        assert console_handlers[0].level == logging.WARNING

    def test_console_level_info_quando_verbose(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging(verbose=True)
        console_handlers = [
            h for h in auto_oficios.logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        ]
        assert console_handlers[0].level == logging.INFO

    def test_chamadas_repetidas_nao_duplicam_handlers(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        configurar_logging()
        assert len(auto_oficios.logger.handlers) == 2  # 1 file + 1 console

    def test_excepthook_instalado(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        assert sys.excepthook is not sys.__excepthook__

    def test_excepthook_delega_keyboard_interrupt_ao_original(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        with patch("sys.__excepthook__") as mock_orig:
            sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
            mock_orig.assert_called_once()

    def test_excepthook_loga_excecao_nao_tratada(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        with patch.object(auto_oficios.logger, "critical") as mock_crit:
            try:
                raise RuntimeError("erro de teste")
            except RuntimeError:
                exc_info = sys.exc_info()
            sys.excepthook(*exc_info)
            mock_crit.assert_called_once()

    def test_arquivo_de_log_recebe_mensagem_debug(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        log_path = configurar_logging()
        auto_oficios.logger.debug("mensagem de teste debug")
        conteudo = Path(log_path).read_text(encoding="utf-8")
        assert "mensagem de teste debug" in conteudo

    def test_sessao_id_aparece_nas_linhas_de_log(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        log_path = configurar_logging()
        auto_oficios.logger.info("linha de info")
        conteudo = Path(log_path).read_text(encoding="utf-8")
        assert auto_oficios.SESSAO_ID in conteudo


# =============================================================================
# _salvar_api_key_no_ambiente / obter_api_key
# =============================================================================
class TestApiKey:

    def test_salvar_escreve_no_registro(self):
        mock_key = MagicMock()
        with patch("winreg.OpenKey", return_value=mock_key.__enter__.return_value), \
             patch("winreg.SetValueEx") as mock_set, \
             patch.dict(os.environ, {}, clear=False):
            _salvar_api_key_no_ambiente("chave-teste")
            mock_set.assert_called_once()
            assert os.environ.get("GEMINI_API_KEY") == "chave-teste"

    def test_obter_api_key_lê_do_ambiente(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "chave-existente"}):
            chave = obter_api_key()
        assert chave == "chave-existente"

    def test_obter_api_key_solicita_e_salva_quando_ausente(self):
        env_sem_chave = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict(os.environ, env_sem_chave, clear=True), \
             patch("getpass.getpass", return_value="nova-chave"), \
             patch("auto_oficios._salvar_api_key_no_ambiente") as mock_salvar:
            chave = obter_api_key()
        assert chave == "nova-chave"
        mock_salvar.assert_called_once_with("nova-chave")

    def test_obter_api_key_rejeita_chave_vazia(self):
        env_sem_chave = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict(os.environ, env_sem_chave, clear=True), \
             patch("getpass.getpass", side_effect=["", "chave-valida"]), \
             patch("auto_oficios._salvar_api_key_no_ambiente"):
            chave = obter_api_key()
        assert chave == "chave-valida"



# =============================================================================
# limpar_json_da_resposta
# =============================================================================
class TestLimparJsonDaResposta:

    def test_json_puro_sem_marcador(self):
        texto = '{"tipo_mocao": "Aplauso"}'
        assert limpar_json_da_resposta(texto) == '{"tipo_mocao": "Aplauso"}'

    def test_marcador_json(self):
        texto = '```json\n{"tipo_mocao": "Aplauso"}\n```'
        assert limpar_json_da_resposta(texto) == '{"tipo_mocao": "Aplauso"}'

    def test_marcador_generico(self):
        texto = '```\n{"tipo_mocao": "Apelo"}\n```'
        assert limpar_json_da_resposta(texto) == '{"tipo_mocao": "Apelo"}'

    def test_espacos_e_quebras_de_linha_extras(self):
        texto = '  \n```json\n{"a": 1}\n```\n  '
        assert limpar_json_da_resposta(texto) == '{"a": 1}'

    def test_resultado_e_json_valido_apos_limpeza(self):
        texto = '```json\n{"tipo_mocao": "Aplauso", "numero_mocao": "42"}\n```'
        resultado = json.loads(limpar_json_da_resposta(texto))
        assert resultado["numero_mocao"] == "42"


# =============================================================================
# validar_dados_mocao
# =============================================================================
class TestValidarDadosMocao:

    def _dados_validos(self):
        return {
            "tipo_mocao": "Aplauso",
            "numero_mocao": "123",
            "autores": ["Alex Dantas"],
            "destinatarios": [{"nome": "Fulano de Tal"}],
        }

    def test_dados_completos_nao_levanta_excecao(self):
        validar_dados_mocao(self._dados_validos())  # não deve lançar

    def test_tipo_apelo_valido(self):
        d = self._dados_validos()
        d["tipo_mocao"] = "Apelo"
        validar_dados_mocao(d)  # não deve lançar

    def test_tipo_mocao_invalido(self):
        d = self._dados_validos()
        d["tipo_mocao"] = "Homenagem"
        with pytest.raises(ValueError, match="tipo_mocao"):
            validar_dados_mocao(d)

    def test_campo_tipo_mocao_ausente(self):
        d = self._dados_validos()
        del d["tipo_mocao"]
        with pytest.raises(ValueError):
            validar_dados_mocao(d)

    def test_campo_autores_ausente(self):
        d = self._dados_validos()
        del d["autores"]
        with pytest.raises(ValueError):
            validar_dados_mocao(d)

    def test_campo_destinatarios_ausente(self):
        d = self._dados_validos()
        del d["destinatarios"]
        with pytest.raises(ValueError):
            validar_dados_mocao(d)

    def test_autores_lista_vazia(self):
        d = self._dados_validos()
        d["autores"] = []
        with pytest.raises(ValueError):
            validar_dados_mocao(d)

    def test_destinatarios_lista_vazia(self):
        d = self._dados_validos()
        d["destinatarios"] = []
        with pytest.raises(ValueError):
            validar_dados_mocao(d)

    def test_autores_nao_e_lista(self):
        d = self._dados_validos()
        d["autores"] = "Alex Dantas"
        with pytest.raises(ValueError, match="lista"):
            validar_dados_mocao(d)

    def test_destinatario_sem_nome(self):
        d = self._dados_validos()
        d["destinatarios"] = [{"nome": ""}]
        with pytest.raises(ValueError, match="nome"):
            validar_dados_mocao(d)

    def test_destinatario_sem_chave_nome(self):
        d = self._dados_validos()
        d["destinatarios"] = [{"cargo": "Secretário"}]
        with pytest.raises(ValueError, match="nome"):
            validar_dados_mocao(d)

    def test_multiplos_destinatarios_validos(self):
        d = self._dados_validos()
        d["destinatarios"] = [{"nome": "Fulano"}, {"nome": "Ciclano"}]
        validar_dados_mocao(d)  # não deve lançar

    def test_segundo_destinatario_sem_nome(self):
        d = self._dados_validos()
        d["destinatarios"] = [{"nome": "Fulano"}, {"nome": ""}]
        with pytest.raises(ValueError):
            validar_dados_mocao(d)


# =============================================================================
# formatar_autores
# =============================================================================
class TestFormatarAutores:

    def test_autor_unico_conhecido_texto(self):
        texto, _ = formatar_autores(["Alex Dantas"])
        assert texto == "do vereador Alex Dantas"

    def test_autor_unico_conhecido_sigla(self):
        _, sigla = formatar_autores(["Alex Dantas"])
        assert sigla == "AD"

    def test_autor_unico_desconhecido_sigla(self):
        _, sigla = formatar_autores(["Vereador Fantasma"])
        assert sigla == "INDEF"

    def test_dois_autores_texto(self):
        texto, _ = formatar_autores(["Alex Dantas", "Arnaldo Alves"])
        assert "dos vereadores" in texto
        assert "Alex Dantas" in texto
        assert "Arnaldo Alves" in texto

    def test_dois_autores_sigla(self):
        _, sigla = formatar_autores(["Alex Dantas", "Arnaldo Alves"])
        assert sigla == "AD-AA"

    def test_tres_autores_sigla(self):
        _, sigla = formatar_autores(["Alex Dantas", "Arnaldo Alves", "Cabo Dorigon"])
        assert sigla == "AD-AA-CD"

    def test_tres_autores_texto_usa_e(self):
        texto, _ = formatar_autores(["Alex Dantas", "Arnaldo Alves", "Cabo Dorigon"])
        assert " e " in texto

    def test_busca_sigla_case_insensitive(self):
        _, sigla = formatar_autores(["alex dantas"])
        assert sigla == "AD"

    def test_autor_com_acento_no_mapa(self):
        _, sigla = formatar_autores(["Celso Ávila"])
        assert sigla == "CLAB"

    def test_mistura_conhecido_desconhecido(self):
        _, sigla = formatar_autores(["Alex Dantas", "Vereador X"])
        assert sigla == "AD-INDEF"


# =============================================================================
# processar_destinatario
# =============================================================================
class TestProcessarDestinatario:

    def _dest_simples(self, **kwargs):
        base = {
            "nome": "João Silva",
            "is_prefeito": False,
            "is_instituicao": False,
            "cargo_ou_tratamento": "",
            "endereco": "",
            "email": "",
        }
        base.update(kwargs)
        return base

    # --- Regra do Prefeito ---
    def test_prefeito_por_flag(self):
        dest = self._dest_simples(nome="Rafael Piovezan", is_prefeito=True)
        r = processar_destinatario(dest)
        assert r["vocativo"] == "Excelentíssimo Senhor Prefeito"
        assert r["pronome_corpo"] == "Vossa Excelência"
        assert r["envio"] == "Protocolo"
        assert r["destinatario_nome"] == "RAFAEL PIOVEZAN"

    def test_prefeito_por_nome(self):
        dest = self._dest_simples(nome="o Prefeito Municipal")
        r = processar_destinatario(dest)
        assert r["pronome_corpo"] == "Vossa Excelência"

    def test_prefeito_endereco_fixo(self):
        dest = self._dest_simples(is_prefeito=True)
        r = processar_destinatario(dest)
        assert "Oeste/SP" in r["destinatario_endereco"]
        assert "Prefeito Municipal" in r["destinatario_endereco"]

    # --- Envio ---
    def test_envio_email_tem_prioridade(self):
        dest = self._dest_simples(
            endereco="Rua X, 123", email="teste@exemplo.com"
        )
        r = processar_destinatario(dest)
        assert r["envio"] == "E-mail"

    def test_envio_carta_quando_endereco_sem_email(self):
        dest = self._dest_simples(endereco="Rua X, 123")
        r = processar_destinatario(dest)
        assert r["envio"] == "Carta"

    def test_envio_em_maos_sem_dados_contato(self):
        dest = self._dest_simples()
        r = processar_destinatario(dest)
        assert r["envio"] == "Em Mãos"

    # --- Tratamento e formatação ---
    def test_nome_convertido_para_maiusculas(self):
        dest = self._dest_simples(nome="João Silva")
        r = processar_destinatario(dest)
        assert r["destinatario_nome"] == "JOÃO SILVA"

    def test_pessoa_fisica_tratamento_rodape(self):
        dest = self._dest_simples()
        r = processar_destinatario(dest)
        assert r["tratamento_rodape"] == "Ao Ilustríssimo Senhor"

    def test_instituicao_tratamento_ao(self):
        dest = self._dest_simples(nome="Câmara Municipal", is_instituicao=True)
        r = processar_destinatario(dest)
        assert r["tratamento_rodape"] == "Ao"

    def test_instituicao_começa_com_a_tratamento_a(self):
        dest = self._dest_simples(nome="ABCD Fundação", is_instituicao=True)
        r = processar_destinatario(dest)
        assert r["tratamento_rodape"] == "À"

    def test_pronome_pessoa_fisica(self):
        dest = self._dest_simples()
        r = processar_destinatario(dest)
        assert r["pronome_corpo"] == "Vossa Senhoria"

    def test_endereco_concatena_cargo_e_endereco(self):
        dest = self._dest_simples(
            cargo_ou_tratamento="Secretário de Saúde",
            endereco="Av. das Flores, 100",
        )
        r = processar_destinatario(dest)
        assert "Secretário de Saúde" in r["destinatario_endereco"]
        assert "Av. das Flores, 100" in r["destinatario_endereco"]

    def test_endereco_inclui_email(self):
        dest = self._dest_simples(
            cargo_ou_tratamento="Diretor",
            email="dir@exemplo.com",
        )
        r = processar_destinatario(dest)
        assert "dir@exemplo.com" in r["destinatario_endereco"]


# =============================================================================
# _salvar_api_key_no_ambiente / obter_api_key
# =============================================================================
class TestApiKey:

    def test_salvar_escreve_no_registro(self):
        """_salvar_api_key_no_ambiente grava a chave no registro e em os.environ."""
        mock_key = MagicMock()
        with patch("winreg.OpenKey", return_value=mock_key.__enter__.return_value), \
             patch("winreg.SetValueEx") as mock_set, \
             patch.dict(os.environ, {}, clear=False):
            _salvar_api_key_no_ambiente("chave-teste")
            mock_set.assert_called_once()
            assert os.environ.get("GEMINI_API_KEY") == "chave-teste"

    def test_obter_api_key_lê_do_ambiente(self):
        """Se GEMINI_API_KEY já está no ambiente, retorna sem solicitar input."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "chave-existente"}):
            chave = obter_api_key()
        assert chave == "chave-existente"

    def test_obter_api_key_solicita_e_salva_quando_ausente(self):
        """Se a variável está ausente, solicita ao usuário e persiste."""
        env_sem_chave = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict(os.environ, env_sem_chave, clear=True), \
             patch("getpass.getpass", return_value="nova-chave"), \
             patch("auto_oficios._salvar_api_key_no_ambiente") as mock_salvar:
            chave = obter_api_key()
        assert chave == "nova-chave"
        mock_salvar.assert_called_once_with("nova-chave")

    def test_obter_api_key_rejeita_chave_vazia(self):
        """Loop até entrada válida: primeira tentativa vazia, segunda com valor."""
        env_sem_chave = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict(os.environ, env_sem_chave, clear=True), \
             patch("getpass.getpass", side_effect=["", "chave-valida"]), \
             patch("auto_oficios._salvar_api_key_no_ambiente"):
            chave = obter_api_key()
        assert chave == "chave-valida"
