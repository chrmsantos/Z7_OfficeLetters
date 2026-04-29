"""
Testes unitários para auto_oficios.py
Executar com:  pytest tests/ -v
"""
import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import auto_oficios
from auto_oficios import (
    carregar_api_key,
    migrar_chave_do_registro,
    _salvar_api_key_no_ambiente,
    configurar_logging,
    construir_nome_arquivo,
    extrair_dados_com_ia,
    formatar_autores,
    ler_arquivo_mocoes,
    limpar_json_da_resposta,
    listar_proposituras,
    normalizar_numero_mocao,
    processar_destinatario,
    resolver_arquivo_preferencial,
    validar_dados_mocao,
)


# =============================================================================
# Helpers compartilhados
# =============================================================================
def _dados_mocao_validos(**overrides):
    base = {
        "tipo_mocao": "Aplauso",
        "numero_mocao": "123",
        "autores": ["Alex Dantas"],
        "destinatarios": [{"nome": "Fulano de Tal"}],
    }
    base.update(overrides)
    return base


def _dest_simples(**overrides):
    base = {
        "nome": "João Silva",
        "is_prefeito": False,
        "is_instituicao": False,
        "cargo_ou_tratamento": "",
        "endereco": "",
        "email": "",
    }
    base.update(overrides)
    return base


def _make_ai_response(payload: dict) -> MagicMock:
    """Returns a fake Gemini response whose .text is a compact JSON string."""
    mock = MagicMock()
    mock.text = json.dumps(payload)
    return mock


# =============================================================================
# limpar_json_da_resposta
# =============================================================================
class TestLimparJsonDaResposta:

    def test_json_puro_sem_marcador(self):
        assert limpar_json_da_resposta('{"k": 1}') == '{"k": 1}'

    def test_marcador_json(self):
        texto = '```json\n{"tipo_mocao": "Aplauso"}\n```'
        assert limpar_json_da_resposta(texto) == '{"tipo_mocao": "Aplauso"}'

    def test_marcador_generico(self):
        texto = '```\n{"tipo_mocao": "Apelo"}\n```'
        assert limpar_json_da_resposta(texto) == '{"tipo_mocao": "Apelo"}'

    def test_espacos_e_quebras_extras(self):
        texto = '  \n```json\n{"a": 1}\n```\n  '
        assert limpar_json_da_resposta(texto) == '{"a": 1}'

    def test_resultado_e_json_valido_apos_limpeza(self):
        texto = '```json\n{"tipo_mocao": "Aplauso", "numero_mocao": "42"}\n```'
        assert json.loads(limpar_json_da_resposta(texto))["numero_mocao"] == "42"

    def test_json_array_retornado_intacto(self):
        texto = '```json\n[{"tipo_mocao": "Apelo"}]\n```'
        parsed = json.loads(limpar_json_da_resposta(texto))
        assert isinstance(parsed, list) and parsed[0]["tipo_mocao"] == "Apelo"


# =============================================================================
# validar_dados_mocao
# =============================================================================
class TestValidarDadosMocao:

    def test_dados_completos_nao_levanta(self):
        validar_dados_mocao(_dados_mocao_validos())

    def test_tipo_apelo_valido(self):
        validar_dados_mocao(_dados_mocao_validos(tipo_mocao="Apelo"))

    def test_tipo_invalido(self):
        with pytest.raises(ValueError, match="tipo_mocao"):
            validar_dados_mocao(_dados_mocao_validos(tipo_mocao="Homenagem"))

    @pytest.mark.parametrize("campo", ["tipo_mocao", "numero_mocao", "autores", "destinatarios"])
    def test_campo_ausente_levanta(self, campo):
        d = _dados_mocao_validos()
        del d[campo]
        with pytest.raises(ValueError):
            validar_dados_mocao(d)

    def test_autores_lista_vazia(self):
        with pytest.raises(ValueError):
            validar_dados_mocao(_dados_mocao_validos(autores=[]))

    def test_destinatarios_lista_vazia(self):
        with pytest.raises(ValueError):
            validar_dados_mocao(_dados_mocao_validos(destinatarios=[]))

    def test_autores_nao_e_lista(self):
        with pytest.raises(ValueError, match="lista"):
            validar_dados_mocao(_dados_mocao_validos(autores="Alex Dantas"))

    def test_destinatarios_nao_e_lista(self):
        with pytest.raises(ValueError, match="lista"):
            validar_dados_mocao(_dados_mocao_validos(destinatarios={"nome": "X"}))

    def test_destinatario_sem_nome(self):
        with pytest.raises(ValueError, match="nome"):
            validar_dados_mocao(_dados_mocao_validos(destinatarios=[{"nome": ""}]))

    def test_destinatario_sem_chave_nome(self):
        with pytest.raises(ValueError, match="nome"):
            validar_dados_mocao(_dados_mocao_validos(destinatarios=[{"cargo": "X"}]))

    def test_multiplos_destinatarios_validos(self):
        validar_dados_mocao(_dados_mocao_validos(
            destinatarios=[{"nome": "Fulano"}, {"nome": "Ciclano"}]
        ))

    def test_segundo_destinatario_sem_nome_levanta(self):
        with pytest.raises(ValueError):
            validar_dados_mocao(_dados_mocao_validos(
                destinatarios=[{"nome": "Fulano"}, {"nome": ""}]
            ))


# =============================================================================
# normalizar_numero_mocao
# =============================================================================
class TestNormalizarNumeroMocao:

    def test_numero_puro_nao_alterado(self):
        assert normalizar_numero_mocao("124") == "124"

    def test_remove_espacos(self):
        assert normalizar_numero_mocao("  124  ") == "124"

    def test_sufixo_nao_numerico_preservado(self):
        assert normalizar_numero_mocao("124-A") == "124-A"

    @pytest.mark.parametrize("entrada,esperado", [
        ("124/2026", "124"),
        ("124-2026", "124"),
        ("124/26",   "124"),
        ("124-26",   "124"),
        ("001/2026", "001"),
        ("999-2025", "999"),
        ("7",        "7"),
    ])
    def test_variantes(self, entrada, esperado):
        assert normalizar_numero_mocao(entrada) == esperado


# =============================================================================
# construir_nome_arquivo
# =============================================================================
class TestConstruirNomeArquivo:

    def _nome(self, **overrides):
        params = dict(
            num_oficio_str="001", sigla_servidor="js",
            tipo_mocao="Aplauso", num_mocao="124",
            envio="E-mail", nome_dest="Fulano de Tal",
            sigla_autores="AD",
            ano=2026,
        )
        params.update(overrides)
        return construir_nome_arquivo(**params)

    def test_extensao_docx(self):
        assert self._nome().endswith(".docx")

    def test_contem_numero_oficio(self):
        assert "001" in self._nome()

    def test_contem_tipo_mocao(self):
        assert "Aplauso" in self._nome()

    def test_contem_numero_mocao_com_sufixo_26(self):
        assert "124-26" in self._nome()

    def test_sufixo_26_aparece_uma_vez(self):
        assert self._nome().count("-26") == 1

    def test_envio_convertido_para_minusculo(self):
        assert "e-mail" in self._nome(envio="E-mail")

    def test_sigla_servidor_refletida(self):
        assert "redator" in self._nome(sigla_servidor="redator")

    def test_sigla_autores_refletida(self):
        assert "ad e outros" in self._nome(sigla_autores="ad e outros")

    def test_remove_caracteres_invalidos_windows(self):
        nome = construir_nome_arquivo(
            num_oficio_str="001", sigla_servidor="js",
            tipo_mocao="Aplauso", num_mocao="124",
            envio="Em Mãos", nome_dest='Nome "Ilegal" <teste>',
            sigla_autores="AD",
            ano=2026,
        )
        for ch in r'\/*?:"<>|':
            assert ch not in nome


# =============================================================================
# formatar_autores
# =============================================================================
class TestFormatarAutores:

    def test_autor_unico_texto(self):
        texto, _ = formatar_autores(["Alex Dantas"])
        assert texto == "do vereador Alex Dantas"

    def test_autor_unico_sigla_conhecida(self):
        _, sigla = formatar_autores(["Alex Dantas"])
        assert sigla == "ad"

    def test_autor_desconhecido_sigla_indef(self):
        _, sigla = formatar_autores(["Vereador Fantasma"])
        assert sigla == "indef"

    def test_dois_autores_texto_plural(self):
        texto, _ = formatar_autores(["Alex Dantas", "Arnaldo Alves"])
        assert "dos vereadores" in texto

    def test_dois_autores_sigla(self):
        _, sigla = formatar_autores(["Alex Dantas", "Arnaldo Alves"])
        assert sigla == "ad e outros"

    def test_tres_autores_sigla(self):
        _, sigla = formatar_autores(["Alex Dantas", "Arnaldo Alves", "Cabo Dorigon"])
        assert sigla == "ad e outros"

    def test_tres_autores_usa_e_no_final(self):
        texto, _ = formatar_autores(["Alex Dantas", "Arnaldo Alves", "Cabo Dorigon"])
        assert " e " in texto

    def test_busca_sigla_case_insensitive(self):
        _, sigla = formatar_autores(["alex dantas"])
        assert sigla == "ad"

    def test_autor_com_acento_no_mapa(self):
        _, sigla = formatar_autores(["Celso Ávila"])
        assert sigla == "clab"

    def test_mistura_conhecido_desconhecido(self):
        _, sigla = formatar_autores(["Alex Dantas", "Vereador X"])
        assert sigla == "ad e outros"

    def test_vereadora_unica_texto(self):
        texto, _ = formatar_autores(["Esther Moraes"])
        assert texto == "da vereadora Esther Moraes"

    def test_vereadora_unica_sigla(self):
        _, sigla = formatar_autores(["Esther Moraes"])
        assert sigla == "egsbm"

    def test_todas_vereadoras_plural(self):
        # hypothetical: two female councillors
        texto, _ = formatar_autores(["Esther Moraes", "Esther Moraes"])
        assert texto.startswith("das vereadoras")

    def test_misto_masculino_feminino_usa_masculino_plural(self):
        texto, _ = formatar_autores(["Alex Dantas", "Esther Moraes"])
        assert texto.startswith("dos vereadores")

    def test_vereadora_case_insensitive(self):
        texto, _ = formatar_autores(["esther moraes"])
        assert texto == "da vereadora esther moraes"


# =============================================================================
# processar_destinatario
# =============================================================================
class TestProcessarDestinatario:

    # --- Regra do Prefeito ---
    def test_prefeito_por_flag(self):
        r = processar_destinatario(_dest_simples(nome="Rafael", is_prefeito=True))
        assert r["vocativo"] == "Excelentíssimo Senhor Prefeito"
        assert r["pronome_corpo"] == "Vossa Excelência"
        assert r["envio"] == "Protocolo"
        assert r["destinatario_nome"] == "RAFAEL PIOVEZAN"

    def test_prefeito_por_nome(self):
        r = processar_destinatario(_dest_simples(nome="o Prefeito Municipal"))
        assert r["pronome_corpo"] == "Vossa Excelência"

    def test_prefeito_endereco_fixo(self):
        r = processar_destinatario(_dest_simples(is_prefeito=True))
        assert "Oeste/SP" in r["destinatario_endereco"]
        assert "Prefeito Municipal" in r["destinatario_endereco"]

    # --- Envio ---
    def test_envio_email_tem_prioridade_sobre_endereco(self):
        r = processar_destinatario(_dest_simples(endereco="Rua X", email="x@y.com"))
        assert r["envio"] == "E-mail"

    def test_envio_carta_sem_email(self):
        r = processar_destinatario(_dest_simples(endereco="Rua X"))
        assert r["envio"] == "Carta"

    def test_envio_em_maos_sem_contato(self):
        r = processar_destinatario(_dest_simples())
        assert r["envio"] == "Em Mãos"

    # --- Formatação ---
    def test_nome_em_maiusculas(self):
        r = processar_destinatario(_dest_simples(nome="João Silva"))
        assert r["destinatario_nome"] == "JOÃO SILVA"

    def test_pessoa_fisica_tratamento(self):
        r = processar_destinatario(_dest_simples())
        assert r["tratamento_rodape"] == "Ao Ilustríssimo Senhor"

    def test_pronome_pessoa_fisica(self):
        r = processar_destinatario(_dest_simples())
        assert r["pronome_corpo"] == "Vossa Senhoria"

    def test_instituicao_tratamento_ao(self):
        r = processar_destinatario(_dest_simples(nome="Câmara Municipal", is_instituicao=True))
        assert r["tratamento_rodape"] == "Ao"

    def test_instituicao_comeca_com_a_usa_crase(self):
        r = processar_destinatario(_dest_simples(nome="ABCD Fundação", is_instituicao=True))
        assert r["tratamento_rodape"] == "À"

    def test_endereco_concatena_cargo_e_logradouro(self):
        r = processar_destinatario(_dest_simples(
            cargo_ou_tratamento="Secretário de Saúde",
            endereco="Av. das Flores, 100",
        ))
        assert "Secretário de Saúde" in r["destinatario_endereco"]
        assert "Av. das Flores, 100" in r["destinatario_endereco"]

    def test_endereco_inclui_email(self):
        r = processar_destinatario(_dest_simples(cargo_ou_tratamento="Diretor", email="d@e.com"))
        assert "d@e.com" in r["destinatario_endereco"]


# =============================================================================
# resolver_arquivo_preferencial
# =============================================================================
class TestResolverArquivoPreferencial:

    def test_retorna_proprio_quando_unico(self, tmp_path):
        f = tmp_path / "mocoes.txt"
        f.write_text("c")
        assert resolver_arquivo_preferencial(str(f)) == str(f)

    def test_prefere_txt_sobre_docx(self, tmp_path):
        (tmp_path / "mocoes.txt").write_text("c")
        docx = tmp_path / "mocoes.docx"
        docx.write_bytes(b"c")
        assert resolver_arquivo_preferencial(str(docx)) == str(tmp_path / "mocoes.txt")

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

    def test_retorna_melhor_variante_sem_superior(self, tmp_path):
        # .txt/.docx/.doc ausentes â€” deve retornar .odt
        odt = tmp_path / "mocoes.odt"
        pdf = tmp_path / "mocoes.pdf"
        odt.write_bytes(b"c")
        pdf.write_bytes(b"c")
        assert resolver_arquivo_preferencial(str(pdf)) == str(odt)

    def test_retorna_original_sem_variante(self, tmp_path):
        caminho = str(tmp_path / "naoexiste.pdf")
        assert resolver_arquivo_preferencial(caminho) == caminho

    def test_nao_cruza_diretorios(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        odt = sub / "arq.odt"
        odt.write_bytes(b"c")
        (tmp_path / "arq.txt").write_text("x")
        assert resolver_arquivo_preferencial(str(odt)) == str(odt)


# =============================================================================
# listar_proposituras
# =============================================================================
class TestListarProposituras:

    def _set_pasta(self, monkeypatch, pasta: str):
        monkeypatch.setattr(auto_oficios, "PASTA_PROPOSITURAS", pasta)

    def test_pasta_inexistente_retorna_vazio(self, tmp_path, monkeypatch):
        self._set_pasta(monkeypatch, str(tmp_path / "nao_existe"))
        assert listar_proposituras() == []

    def test_pasta_vazia_retorna_vazio(self, tmp_path, monkeypatch):
        self._set_pasta(monkeypatch, str(tmp_path))
        assert listar_proposituras() == []

    def test_arquivo_txt_retornado(self, tmp_path, monkeypatch):
        self._set_pasta(monkeypatch, str(tmp_path))
        (tmp_path / "mocoes.txt").write_text("x")
        resultado = listar_proposituras()
        assert len(resultado) == 1 and resultado[0].suffix == ".txt"

    def test_formatos_nao_suportados_ignorados(self, tmp_path, monkeypatch):
        self._set_pasta(monkeypatch, str(tmp_path))
        (tmp_path / "mocoes.txt").write_text("x")
        (tmp_path / "imagem.png").write_bytes(b"x")
        (tmp_path / "dados.csv").write_text("x")
        assert len(listar_proposituras()) == 1

    def test_multiplos_arquivos_distintos(self, tmp_path, monkeypatch):
        self._set_pasta(monkeypatch, str(tmp_path))
        (tmp_path / "mocoes_marco.txt").write_text("x")
        (tmp_path / "mocoes_abril.docx").write_bytes(b"x")
        assert len(listar_proposituras()) == 2

    def test_duplicata_retorna_apenas_preferencial(self, tmp_path, monkeypatch):
        self._set_pasta(monkeypatch, str(tmp_path))
        (tmp_path / "mocoes.txt").write_text("x")
        (tmp_path / "mocoes.docx").write_bytes(b"x")
        (tmp_path / "mocoes.pdf").write_bytes(b"x")
        resultado = listar_proposituras()
        assert len(resultado) == 1 and resultado[0].suffix == ".txt"

    def test_duplicata_prefere_docx_sem_txt(self, tmp_path, monkeypatch):
        self._set_pasta(monkeypatch, str(tmp_path))
        (tmp_path / "mocoes.docx").write_bytes(b"x")
        (tmp_path / "mocoes.odt").write_bytes(b"x")
        resultado = listar_proposituras()
        assert len(resultado) == 1 and resultado[0].suffix == ".docx"

    def test_lista_ordenada_alfabeticamente(self, tmp_path, monkeypatch):
        self._set_pasta(monkeypatch, str(tmp_path))
        (tmp_path / "z_ultimo.txt").write_text("x")
        (tmp_path / "a_primeiro.txt").write_text("x")
        (tmp_path / "m_meio.txt").write_text("x")
        nomes = [p.name for p in listar_proposituras()]
        assert nomes == sorted(nomes)

    def test_gitkeep_ignorado(self, tmp_path, monkeypatch):
        self._set_pasta(monkeypatch, str(tmp_path))
        (tmp_path / ".gitkeep").write_bytes(b"")
        (tmp_path / "mocoes.txt").write_text("x")
        assert len(listar_proposituras()) == 1


# =============================================================================
# ler_arquivo_mocoes
# =============================================================================
class TestLerArquivoMocoes:

    def test_le_txt_utf8(self, tmp_path):
        f = tmp_path / "mocoes.txt"
        f.write_text("MOÃ‡ÃO NÂº 1\nTexto.", encoding="utf-8")
        assert ler_arquivo_mocoes(str(f)) == "MOÃ‡ÃO NÂº 1\nTexto."

    def test_txt_preserva_conteudo_completo(self, tmp_path):
        conteudo = "MOÃ‡ÃO NÂº 1\n\nMOÃ‡ÃO NÂº 2\nSegundo texto."
        f = tmp_path / "mocoes.txt"
        f.write_text(conteudo, encoding="utf-8")
        assert ler_arquivo_mocoes(str(f)) == conteudo

    def test_formato_invalido_levanta_value_error(self, tmp_path):
        f = tmp_path / "mocoes.xyz"
        f.write_text("x")
        with pytest.raises(ValueError, match="suportado"):
            ler_arquivo_mocoes(str(f))

    def test_le_docx_via_mock(self, tmp_path):
        mock_doc = MagicMock()
        mock_doc.paragraphs = [
            MagicMock(text="MOÃ‡ÃO NÂº 1"),
            MagicMock(text="Texto."),
        ]
        with patch("docx.Document", return_value=mock_doc):
            resultado = ler_arquivo_mocoes(str(tmp_path / "mocoes.docx"))
        assert resultado == "MOÃ‡ÃO NÂº 1\nTexto."

    def test_pdf_sem_pypdf_levanta_import_error(self, tmp_path):
        f = tmp_path / "mocoes.pdf"
        f.write_bytes(b"%PDF-1.4")
        with patch.dict("sys.modules", {"pypdf": None}):
            with pytest.raises(ImportError, match="pypdf"):
                ler_arquivo_mocoes(str(f))


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
        assert Path(configurar_logging()).exists()

    def test_nome_arquivo_contem_sessao_id(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        assert auto_oficios.SESSAO_ID in configurar_logging()

    def test_usa_rotating_file_handler(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        rfhs = [h for h in auto_oficios.logger.handlers if isinstance(h, RotatingFileHandler)]
        assert len(rfhs) == 1

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
        stream_hs = [
            h for h in auto_oficios.logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        ]
        assert stream_hs[0].level == logging.WARNING

    def test_console_level_info_quando_verbose(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging(verbose=True)
        stream_hs = [
            h for h in auto_oficios.logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler)
        ]
        assert stream_hs[0].level == logging.INFO

    def test_chamadas_repetidas_nao_duplicam_handlers(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        configurar_logging()
        assert len(auto_oficios.logger.handlers) == 2  # 1 file + 1 console

    def test_excepthook_instalado(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        assert sys.excepthook is not sys.__excepthook__

    def test_excepthook_delega_keyboard_interrupt(self, tmp_path, monkeypatch):
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
                sys.excepthook(*sys.exc_info())
            mock_crit.assert_called_once()

    def test_mensagem_debug_gravada_no_arquivo(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        log_path = configurar_logging()
        auto_oficios.logger.debug("mensagem-debug-xyz")
        assert "mensagem-debug-xyz" in Path(log_path).read_text(encoding="utf-8")

    def test_sessao_id_aparece_nas_linhas_de_log(self, tmp_path, monkeypatch):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        log_path = configurar_logging()
        auto_oficios.logger.info("linha qualquer")
        assert auto_oficios.SESSAO_ID in Path(log_path).read_text(encoding="utf-8")


# =============================================================================
# _salvar_api_key_no_ambiente
# =============================================================================
class TestSalvarApiKey:

    def test_escreve_no_keyring_e_no_ambiente(self):
        with patch("keyring.set_password") as mock_set, \
                patch.dict(os.environ, {}, clear=False):
            _salvar_api_key_no_ambiente("minha-chave")
            mock_set.assert_called_once_with(
                auto_oficios._KEYRING_SERVICE,
                auto_oficios._KEYRING_USERNAME,
                "minha-chave",
            )
            assert os.environ["GEMINI_API_KEY"] == "minha-chave"

    def test_chave_diferente_sobrescreve_ambiente(self):
        with patch("keyring.set_password"), \
                patch.dict(os.environ, {"GEMINI_API_KEY": "velha"}, clear=False):
            _salvar_api_key_no_ambiente("nova-chave")
            assert os.environ["GEMINI_API_KEY"] == "nova-chave"

    def test_loga_apos_salvar(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        with patch("keyring.set_password"), caplog.at_level(logging.INFO, logger="auto_oficios"):
            _salvar_api_key_no_ambiente("x")
        assert any("GEMINI_API_KEY" in r.message for r in caplog.records)


# =============================================================================
# _carregar_api_key
# =============================================================================
class TestCarregarApiKey:

    def test_retorna_chave_do_keyring(self):
        with patch("keyring.get_password", return_value="chave-secreta"):
            assert carregar_api_key() == "chave-secreta"

    def test_retorna_string_vazia_quando_nao_ha_chave(self):
        with patch("keyring.get_password", return_value=None):
            assert carregar_api_key() == ""

    def test_consulta_servico_e_usuario_corretos(self):
        with patch("keyring.get_password") as mock_get:
            mock_get.return_value = "k"
            carregar_api_key()
            mock_get.assert_called_once_with(
                auto_oficios._KEYRING_SERVICE,
                auto_oficios._KEYRING_USERNAME,
            )


# =============================================================================
# _migrar_chave_do_registro
# =============================================================================
class TestMigrarChaveDoRegistro:

    def _patch_winreg(self, key_value: str | None):
        """Returns context managers that simulate a registry with the given value."""
        mock_reg = MagicMock()
        mock_reg.__enter__ = MagicMock(return_value=mock_reg)
        mock_reg.__exit__ = MagicMock(return_value=False)

        if key_value is None:
            mock_reg.side_effect = None  # reset
            query_side_effect = FileNotFoundError
        else:
            query_side_effect = None

        def fake_query(reg, name):
            if query_side_effect:
                raise query_side_effect()
            return (key_value, 1)

        import winreg
        p_open = patch("winreg.OpenKey", return_value=mock_reg)
        p_query = patch("winreg.QueryValueEx", side_effect=fake_query)
        p_delete = patch("winreg.DeleteValue")
        p_set = patch("keyring.set_password")
        return p_open, p_query, p_delete, p_set, mock_reg

    def test_migra_chave_existente(self):
        p_open, p_query, p_delete, p_set, _ = self._patch_winreg("chave-antiga")
        with p_open, p_query, p_delete as mock_del, p_set as mock_set:
            migrar_chave_do_registro()
            mock_set.assert_called_once()
            mock_del.assert_called_once()

    def test_nao_faz_nada_se_chave_ausente(self):
        p_open, p_query, p_delete, p_set, _ = self._patch_winreg(None)
        with p_open, p_query, p_delete as mock_del, p_set as mock_set:
            migrar_chave_do_registro()
            mock_set.assert_not_called()
            mock_del.assert_not_called()

    def test_tolerante_a_falha_no_registro(self, caplog):
        with patch("winreg.OpenKey", side_effect=OSError("sem acesso")), \
                caplog.at_level(logging.WARNING, logger="auto_oficios"):
            migrar_chave_do_registro()  # must not raise
        assert any("Falha" in r.message for r in caplog.records)


# =============================================================================
# extrair_dados_com_ia
# =============================================================================
class TestExtrairDadosComIA:
    """Testa a extração de dados â€” todas as chamadas Gemini são mockadas."""

    def _client(self, *responses):
        """Returns a mock Gemini client that yields the given responses in order."""
        client = MagicMock()
        client.models.generate_content.side_effect = list(responses)
        return client

    # --- Caminho feliz ---
    def test_retorna_dados_validos_na_primeira_tentativa(self):
        client = self._client(_make_ai_response(_dados_mocao_validos()))
        r = extrair_dados_com_ia("MOÃ‡ÃO NÂº 1 texto", client)
        assert r["tipo_mocao"] == "Aplauso"
        assert r["numero_mocao"] == "123"

    def test_aceita_resposta_com_markdown_json_fence(self):
        payload = _dados_mocao_validos()
        mock_resp = MagicMock()
        mock_resp.text = f"```json\n{json.dumps(payload)}\n```"
        client = self._client(mock_resp)
        assert extrair_dados_com_ia("MOÃ‡ÃO", client)["tipo_mocao"] == "Aplauso"

    def test_aceita_resposta_em_lista(self):
        mock_resp = MagicMock()
        mock_resp.text = json.dumps([_dados_mocao_validos()])
        client = self._client(mock_resp)
        assert extrair_dados_com_ia("MOÃ‡ÃO", client)["tipo_mocao"] == "Aplauso"

    # --- Retry em resposta inválida ---
    def test_retenta_quando_json_invalido(self):
        bad = MagicMock()
        bad.text = "não é json"
        good = _make_ai_response(_dados_mocao_validos())
        client = self._client(bad, good)
        r = extrair_dados_com_ia("MOÃ‡ÃO", client)
        assert r["tipo_mocao"] == "Aplauso"
        assert client.models.generate_content.call_count == 2

    def test_retenta_quando_tipo_mocao_invalido(self):
        bad = _make_ai_response(_dados_mocao_validos(tipo_mocao="Homenagem"))
        good = _make_ai_response(_dados_mocao_validos())
        client = self._client(bad, good)
        r = extrair_dados_com_ia("MOÃ‡ÃO", client)
        assert r["tipo_mocao"] == "Aplauso"
        assert client.models.generate_content.call_count == 2

    def test_levanta_apos_todas_as_tentativas_falharem(self):
        bad = MagicMock()
        bad.text = "não é json"
        client = self._client(*([bad] * 5))
        with pytest.raises((ValueError, json.JSONDecodeError)):
            extrair_dados_com_ia("MOÃ‡ÃO", client)
        assert client.models.generate_content.call_count == 5

    # --- Rate limit (429) ---
    def test_aguarda_e_retenta_em_rate_limit(self):
        good = _make_ai_response(_dados_mocao_validos())
        client = self._client(
            Exception("Error 429: retry_delay { seconds: 1 }"),
            good,
        )
        with patch("time.sleep") as mock_sleep:
            r = extrair_dados_com_ia("MOÃ‡ÃO", client)
        mock_sleep.assert_called_once()
        assert r["tipo_mocao"] == "Aplauso"

    def test_extrai_espera_do_retry_delay(self):
        good = _make_ai_response(_dados_mocao_validos())
        client = self._client(
            Exception("Error 429: retry_delay { seconds: 10 }"),
            good,
        )
        with patch("time.sleep") as mock_sleep:
            extrair_dados_com_ia("MOÃ‡ÃO", client)
        # espera = 10 + 2 = 12
        mock_sleep.assert_called_once_with(12)

    def test_erro_nao_429_relancado_imediatamente(self):
        client = self._client(ConnectionError("falha de rede"))
        with pytest.raises(ConnectionError):
            extrair_dados_com_ia("MOÃ‡ÃO", client)
        assert client.models.generate_content.call_count == 1

    # --- Logging ---
    def test_loga_resposta_bruta_em_debug(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        client = self._client(_make_ai_response(_dados_mocao_validos()))
        with caplog.at_level(logging.DEBUG, logger="auto_oficios"):
            extrair_dados_com_ia("MOÃ‡ÃO", client)
        assert any("Resposta bruta" in r.message for r in caplog.records)

    def test_loga_warning_em_resposta_invalida(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        bad = MagicMock()
        bad.text = "não é json"
        good = _make_ai_response(_dados_mocao_validos())
        client = self._client(bad, good)
        with caplog.at_level(logging.WARNING, logger="auto_oficios"):
            extrair_dados_com_ia("MOÃ‡ÃO", client)
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_resposta_longa_nao_aparece_inteira_no_log(self, tmp_path, monkeypatch, caplog):
        monkeypatch.setattr(auto_oficios, "PASTA_LOGS", str(tmp_path))
        configurar_logging()
        long_text = "x" * 2000
        bad = MagicMock()
        bad.text = long_text
        good = _make_ai_response(_dados_mocao_validos())
        client = self._client(bad, good)
        with caplog.at_level(logging.DEBUG, logger="auto_oficios"):
            extrair_dados_com_ia("MOÃ‡ÃO", client)
        # The raw-response log messages must all be shorter than the original string
        bruta_msgs = [r.message for r in caplog.records if "Resposta bruta" in r.message]
        assert all(len(m) < len(long_text) for m in bruta_msgs)
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

