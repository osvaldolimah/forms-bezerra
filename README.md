# 🤖 Automação Google Forms com Streamlit + Selenium

Aplicação para automatizar o preenchimento e envio de formulários Google em massa, com seleção inteligente de rotas por bairro.

## 🎯 Funcionalidades

- ✅ **Mapeamento Automático de Rotas** - Detecta todas as rotas disponíveis no formulário
- ✅ **Filtro por Bairros** - Seleciona apenas rotas que contêm os bairros desejados
- ✅ **Ordenação por Preferência** - Prioriza bairros favoritos
- ✅ **Envio em Massa** - Preenche e envia múltiplos formulários automaticamente
- ✅ **Logs em Tempo Real** - Acompanha cada etapa do processo
- ✅ **Retry Automático** - Tenta novamente em caso de falha
- ✅ **Interface Web** - Streamlit para fácil uso

## 🛠️ Requisitos

### Local
- Python 3.8+
- Google Chrome instalado
- Git

### Streamlit Cloud
- Conta no [Streamlit Cloud](https://share.streamlit.io)
- Repositório GitHub

## 📦 Instalação Local

### 1. Clonar repositório
```bash
git clone <seu-repositorio>
cd automacao_forms
```

### 2. Criar ambiente virtual
```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux/Mac
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependências
```bash
pip install -r requirements.txt
```

### 4. Rodar localmente
```bash
streamlit run app.py
```

A aplicação abrirá em `http://localhost:8501`

## 🚀 Deploy no Streamlit Cloud

### Pré-requisitos
1. Arquivo `packages.txt` com dependências do sistema ✅
2. Arquivo `requirements.txt` com pacotes Python ✅
3. Arquivo `app.py` atualizado ✅

### Passo a Passo

#### 1. Push para GitHub
```bash
git add .
git commit -m "Deploy: Automação Google Forms"
git push origin main
```

#### 2. Conectar no Streamlit Cloud
- Acesse [https://share.streamlit.io](https://share.streamlit.io)
- Clique em "New app"
- Selecione seu repositório e arquivo `app.py`
- Clique em "Deploy"

#### 3. Acompanhar deployment
- Observe os logs de instalação
- Procure por mensagens de instalação de `chromium`
- Deployment completo quando ver "App is live"

#### 4. Testar
- Acesse a URL fornecida pelo Streamlit
- Preencha os dados e teste "Mapear Rotas"

### 🔍 Se não funcionar

#### Problema: "Chrome not found"
**Solução:**
1. Verificar que `packages.txt` tem exatamente `chromium`, `chromium-driver` e `fonts-liberation`
2. Fazer novo "Redeploy" (não apenas recarregar)
3. Aguardar o deployment completar

#### Problema: botão não encontrado
**Solução:**
1. Verificar se o formulário está em PT ou EN
2. Conferir os logs em "Ver Logs da Última Execução"
3. Confirmar que o botão pode aparecer como "Next" ou "Submit"

#### Problema: Timeout ou erro de conexão
**Solução:**
1. Aumentar `TIMEOUT_PADRAO` e `TIMEOUT_ENVIO` no código
2. Verificar a URL do formulário
3. Testar localmente primeiro

#### Problema: Rotas não encontradas
**Solução:**
1. Verificar se os nomes dos bairros batem com o formulário
2. Usar a função "Ver Logs" para diagnosticar
3. Ajustar a lista de bairros

## 🧪 Diagnóstico

### Executar script de diagnóstico
```bash
python diagnostico.py
```

Este script verifica:
- ✅ Versão do Python
- ✅ Pacotes Python instalados
- ✅ Chrome/Chromium disponível
- ✅ ChromeDriver disponível
- ✅ Selenium funcionando
- ✅ Arquivos de configuração

### Executar rotina de simulação
```bash
python teste_simulacao_forms.py --headless --rota "Fortaleza - Cambeba - E-27 - UTILITARIO"
```

Também é possível testar com HTML salvo localmente:
```bash
python teste_simulacao_forms.py --html caminho\para\form.html --headless
```

Essa rotina preenche nome, ID, rota e telefone sem fazer o envio final.

## 📋 Estrutura de Arquivos

```
automacao_forms/
├── app.py                    # Aplicação principal
├── diagnostico.py            # Script de diagnóstico
├── requirements.txt          # Dependências Python
├── packages.txt             # Dependências do sistema (Debian)
├── DEPLOY.md               # Guia de deployment
├── README.md               # Este arquivo
├── .streamlit/
│   └── config.toml         # Configuração do Streamlit
├── .git/                   # Controle de versão
├── .venv/                  # Ambiente virtual (local)
└── logs/                   # Logs da aplicação
```

## ⚙️ Configurações

### Timeouts (em segundos)
- **TIMEOUT_PADRAO**: 15s - Para esperar elementos na página
- **TIMEOUT_ENVIO**: 20s - Para enviar formulário
- **INTERVALO_ENTRE_ENVIOS**: 3s - Pausa entre cada formulário
- **MAX_TENTATIVAS**: 2 - Tentativas antes de desistir

Ajuste estes valores se:
- Formulário está lento → aumentar timeouts
- Rate limiting → aumentar intervalo entre envios

### Bairros
Edite os arrays `BAIRROS_DEFAULT` e `BAIRROS_PREFERIDOS_DEFAULT` no código para mudar os bairros padrão.

## 🔐 Segurança

- ⚠️ Dados de funcionário NOT salvos em nenhum lugar
- ⚠️ Não compartilhe URLs públicas do Streamlit Cloud
- ⚠️ Use credenciais reais apenas se confiar no formulário
- ✅ Todos os dados são processados apenas localmente/cloud temporariamente

## 📊 Como Funciona

### Fase 1: Mapeamento
1. Abre o formulário no navegador headless
2. Preenche dados do funcionário
3. Avança para seleção de rota
4. Extrai todas as opções do dropdown
5. Filtra apenas rotas que contêm os bairros selecionados

### Fase 2: Envio
1. Para cada rota selecionada:
   - Abre o formulário novamente
   - Preenche dados do funcionário
   - Seleciona a rota
   - Preenche telefone
   - Envia o formulário
   - Aguarda intervalo antes do próximo

## 🐛 Troubleshooting

| Problema | Causa | Solução |
|----------|-------|---------|
| Chrome not found | Dependências não instaladas | Redeploy no Streamlit Cloud |
| Timeout | Formulário carregando lento | Aumentar timeouts |
| Rota não encontrada | Nome do bairro errado | Atualizar lista de bairros |
| Erro de envio | Campo não preenchido corretamente | Verificar seletores XPath |
| Rate limited | Google Forms rejeitando | Aumentar intervalo entre envios |

## 📚 Documentação

- [Streamlit Docs](https://docs.streamlit.io)
- [Selenium Python](https://selenium-python.readthedocs.io/)
- [WebDriver Manager](https://github.com/SergeyPirogov/webdriver_manager)

## 📄 Licença

MIT License - Sinta-se livre para usar e modificar!

## 👨‍💻 Autor

Desenvolvido para automação de formulários Google Forms

---

**Última atualização:** 14 de maio de 2026  
**Status:** ✅ Testado e funcionando (local + Streamlit Cloud)

