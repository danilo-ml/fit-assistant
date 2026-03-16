"""Tests for static website pages content.

Validates that HTML pages contain required sections, branding,
data references, and proper HTML attributes per requirements.
"""

import os
import pytest

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "static-website")
PAGES = ["privacidade.html", "termos.html", "erro.html"]


@pytest.fixture
def privacidade_html():
    path = os.path.join(STATIC_DIR, "privacidade.html")
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def termos_html():
    path = os.path.join(STATIC_DIR, "termos.html")
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def erro_html():
    path = os.path.join(STATIC_DIR, "erro.html")
    with open(path, encoding="utf-8") as f:
        return f.read()


# --- File existence ---


class TestFilesExist:
    """Verify all expected HTML files exist in static-website/."""

    @pytest.mark.parametrize("filename", PAGES)
    def test_page_exists(self, filename):
        assert os.path.isfile(os.path.join(STATIC_DIR, filename)), (
            f"{filename} not found in static-website/"
        )


# --- Common HTML attributes ---


class TestHtmlAttributes:
    """Verify lang and viewport meta tag on all pages."""

    @pytest.mark.parametrize("filename", PAGES)
    def test_lang_pt_br(self, filename):
        path = os.path.join(STATIC_DIR, filename)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert 'lang="pt-BR"' in content, f'{filename} missing lang="pt-BR"'

    @pytest.mark.parametrize("filename", PAGES)
    def test_meta_viewport(self, filename):
        path = os.path.join(STATIC_DIR, filename)
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "viewport" in content, f"{filename} missing meta viewport"


# --- Privacidade page content ---


class TestPrivacidadeContent:
    """Validate required sections and data references in privacidade.html."""

    def test_secao_coleta_de_dados(self, privacidade_html):
        assert "Coleta de Dados" in privacidade_html

    def test_secao_uso_de_dados(self, privacidade_html):
        assert "Uso de Dados" in privacidade_html

    def test_secao_compartilhamento(self, privacidade_html):
        assert "Compartilhamento de Dados" in privacidade_html

    def test_secao_armazenamento_seguranca(self, privacidade_html):
        assert "Armazenamento e Segurança" in privacidade_html

    def test_secao_direitos_usuario(self, privacidade_html):
        assert "Direitos do Usuário" in privacidade_html

    def test_secao_contato(self, privacidade_html):
        assert "Informações de Contato" in privacidade_html

    def test_fitagent_responsavel(self, privacidade_html):
        assert "responsável pelo tratamento dos dados" in privacidade_html

    def test_dado_telefone(self, privacidade_html):
        assert "telefone" in privacidade_html.lower()

    def test_dado_nome(self, privacidade_html):
        assert "Nome" in privacidade_html

    def test_dado_mensagens(self, privacidade_html):
        assert "Mensagens" in privacidade_html

    def test_dado_comprovantes(self, privacidade_html):
        assert "comprovantes de pagamento" in privacidade_html.lower()

    def test_aws_criptografia(self, privacidade_html):
        assert "AWS" in privacidade_html
        assert "criptografia" in privacidade_html.lower()

    def test_integracao_twilio(self, privacidade_html):
        assert "Twilio" in privacidade_html

    def test_integracao_google_calendar(self, privacidade_html):
        assert "Google Calendar" in privacidade_html

    def test_integracao_microsoft_outlook(self, privacidade_html):
        assert "Microsoft Outlook" in privacidade_html


# --- Termos page content ---


class TestTermosContent:
    """Validate required sections and data references in termos.html."""

    def test_secao_descricao_servico(self, termos_html):
        assert "Descrição do Serviço" in termos_html

    def test_secao_condicoes_uso(self, termos_html):
        assert "Condições de Uso" in termos_html

    def test_secao_responsabilidades(self, termos_html):
        assert "Responsabilidades do Usuário" in termos_html

    def test_secao_limitacoes(self, termos_html):
        assert "Limitações de Responsabilidade" in termos_html

    def test_secao_propriedade_intelectual(self, termos_html):
        assert "Propriedade Intelectual" in termos_html

    def test_secao_disposicoes_gerais(self, termos_html):
        assert "Disposições Gerais" in termos_html

    def test_plataforma_personal_trainers(self, termos_html):
        assert "personal trainers" in termos_html.lower()

    def test_dependencia_servicos_terceiros(self, termos_html):
        content_lower = termos_html.lower()
        assert "whatsapp" in content_lower
        assert "AWS" in termos_html
        assert "calendário" in content_lower or "calendar" in content_lower
