# Dockerfile para o Ecossistema AUX CAD
FROM python:3.12-slim

# Metadados
LABEL maintainer="IM3 Brasil <contato@im3brasil.com.br>"
LABEL description="Ambiente de Testes e Execução Contínua do Ecossistema AUX CAD"

# Variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONPATH=/app:/app/cqt:/app/ambiental:/app/orcamento:/app/topografia:/app/mapa_postes:/app/dados_tecnicos:/app/cpfc:/app/unifilar:/app/prancha:/app/sob

# Diretório de trabalho
WORKDIR /app

# Instalação de dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Instalação de dependências Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Cópia do código-fonte do projeto
COPY . /app/

# Exposição de porta para o servidor do estúdio de satélite/postes
EXPOSE 8000

# Comando padrão: Executa a suíte completa de testes com relatório de cobertura
CMD ["pytest", "tests/", "-v", "--cov=.", "--cov-report=term-missing"]
