"""
Testes unitários para auto_oficios.py
Executar com:  pytest tests/ -v
"""
import sys
import os
import json
import winreg
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_oficios import (
    limpar_json_da_resposta,
    validar_dados_mocao,
    formatar_autores,
    processar_destinatario,
    _salvar_api_key_no_ambiente,
    obter_api_key,
)


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
