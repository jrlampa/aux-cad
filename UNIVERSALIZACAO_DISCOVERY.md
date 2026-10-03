# Universalização — Relatório Técnico de Descoberta e Viabilidade

**Data da Auditoria:** 2026-10-03
**Status da Investigação:** CONCLUÍDA — BLOQUEIO ESTRUTURAL IDENTIFICADO
**Alvo Investigado:** `http://gtecprorio.enelint.global/sistemas/universalizacao/`
**Escopo:** Avaliação técnica da viabilidade de uso da Universalização como segunda fonte do módulo Consulta SOB.

---

## 1. Resposta Executiva

> **"É tecnicamente viável usar a Universalização como segunda fonte do Consulta SOB?"**
>
> **NÃO.**
> No modelo atual automatizado / headless via `requests.Session()` utilizando as credenciais do GOMNET, o acesso é **inviável**.
>
> **Motivo exato do bloqueio:**
> A Universalização não utiliza autenticação por formulário web (como o GOMNET), mas sim **Autenticação Integrada do Windows (NTLM / Kerberos / Negotiate)** atrelada ao controlador de domínio Active Directory corporativo `ENELINT.GLOBAL`. As credenciais do GOMNET são contas de aplicação web que não existem como contas de domínio no Active Directory `ENELINT`. Consequentemente, todas as tentativas de autenticação NTLM/Negotiate com credenciais GOMNET são rejeitadas pelo servidor IIS com erro **HTTP 401.2 (Unauthorized)**.

---

## 2. Classificação Sistemática das Descobertas Técnicas

| Item | Classificação | Evidência Técnica Observada |
| :--- | :--- | :--- |
| **Servidor Web e SO** | **CONFIRMADO** | `Microsoft-IIS/10.0` com módulo `ASP.NET` e `Microsoft-HTTPAPI/2.0`. |
| **Caminho Físico no Servidor** | **CONFIRMADO** | `D:\web\sistemas\GTEC\sistemas\universalizacao\` (revelado pelo manipulador de erro IIS 401.2). |
| **Mecanismo de Autenticação** | **CONFIRMADO** | Windows Integrated Authentication: cabeçalhos `WWW-Authenticate: Negotiate, NTLM`. |
| **Domínio Active Directory** | **CONFIRMADO** | NetBIOS: `ENELINT` \| FQDN: `enelint.global` (decodificado via NTLM Type 2 Challenge). |
| **Identidade do Host Remoto** | **CONFIRMADO** | NetBIOS: `EWAAZISDEF02` \| FQDN: `ewaazisdef02.enelint.global`. |
| **Incompatibilidade GOMNET** | **CONFIRMADO** | GOMNET utiliza formulário web HTTP POST; Universalização exige handshake de rede NTLM/Kerberos. As credenciais do GOMNET falham com HTTP 401 contra o domínio `ENELINT`. |
| **Formulário Web de Login** | **CONFIRMADO** | Não existe página pública de formulário de login (HTML com input de usuário/senha anônimo). O acesso ao endpoint raiz é bloqueado diretamente no pipeline do IIS (`AuthenticateRequest`, erro `0x80070005`). |
| **Página Principal da Aplicação** | **CONFIRMADO** | `principal.asp` (tecnologia ASP clássico rodando sob IIS 10.0). |
| **Campos de Consulta Visíveis** | **CONFIRMADO** | Rótulos históricos da interface: `Número Ordem de Projeto`, `Projetos Grupo`, `Status do Projeto`, `Pólo Técnico`. |
| **Endpoints Pós-Login** | **NÃO CONFIRMADO** | Rotas exatas de submissão da consulta (ex.: `consulta.asp`, `resultado.asp`) não puderam ser inspecionadas devido ao bloqueio prévio de autenticação. |
| **Pesquisa por SOB** | **PROVÁVEL** | Provavelmente mapeada no campo `Número Ordem de Projeto` ou busca textual, pendente de validação em sessão corporativa. |
| **Downloads e Anexos** | **NÃO TESTADO** | Estrutura de anexos da Universalização não testada devido ao bloqueio de acesso. |
| **Viabilidade via `requests.Session()`**| **CONFIRMADO** | Inviável com credenciais GOMNET. Tecnicamente viável via biblioteca `requests_ntlm` **somente** se fornecidas credenciais corporativas válidas do domínio `ENELINT\usuario`. |

---

## 3. Detalhamento da Investigação NTLM Type 2 Challenge

A sondagem direta ao endpoint `http://gtecprorio.enelint.global/sistemas/universalizacao/` revelou o seguinte ciclo de negociação:

1. **GET anônimo inicial:**
   - Retorno: `HTTP 401 Unauthorized`
   - Cabeçalhos: `Server: Microsoft-IIS/10.0`, `WWW-Authenticate: Negotiate`, `WWW-Authenticate: NTLM`.
2. **Envio de mensagem NTLMSSP Type 1 (Negotiate):**
   - O servidor respondeu com `HTTP 401` contendo o cabeçalho NTLMSSP Type 2 Challenge:
     `WWW-Authenticate: NTLM TlRMTVNTUAACAAAADgAOADgAAAA1gonij46Tig/+lcYAAAAAAAAAALgAuABGAAAACgB8TwAAAA9FAE4ARQBMAEkATgBUAAIADgBFAE4ARQBMAEkATgBUAAEAGABFAFcAQQBBAFoASQBTAEQARQBGADAAMgAEABwAZQBuAGUAbABpAG4AdAAuAGcAbABvAGIAYQBsAAMANgBlAHcAYQBhAHoAaQBzAGQAZQBmADAAMgAuAGUAbgBlAGwAaQBuAHQALgBnAGwAbwBiAGEAbAAFABwAZQBuAGUAbABpAG4AdAAuAGcAbABvAGIAYQBsAAcACAAL2y48glPdAQAAAAA=`
3. **Decodificação binária dos blocos de atributo (Target Info):**
   - **Target Name:** `ENELINT`
   - **Domain NetBIOS:** `ENELINT`
   - **Server NetBIOS:** `EWAAZISDEF02`
   - **Domain FQDN:** `enelint.global`
   - **Server FQDN:** `ewaazisdef02.enelint.global`
4. **Submissão de credenciais GOMNET (Type 3 Authenticate):**
   - O IIS repassou a autenticação ao controlador de domínio `ENELINT.GLOBAL`.
   - O controlador de domínio rejeitou a autenticação (`Notification: AuthenticateRequest`, `Error Code: 0x80070005 - Access Denied`).

---

## 4. Requisitos para Viabilidade Futura

Para que o Sistema de Universalização possa ser utilizado no OXCAD / Consulta SOB:

1. **Credencial de Domínio Windows:** Uma conta de serviço registrada no Active Directory `ENELINT.GLOBAL` com permissão de leitura no IIS `EWAAZISDEF02`.
2. **Autenticação NTLM em Python:** O cliente precisará utilizar `requests_ntlm.HttpNtlmAuth('ENELINT\\usuario', 'senha')` ou autenticação SSPI via SSO local em estação corporativa conectada ao domínio.
3. **Não misturar credenciais:** As variáveis de ambiente devem ser estritamente separadas:
   - `UNIVERSALIZACAO_DOMINIO=ENELINT`
   - `UNIVERSALIZACAO_USER=...`
   - `UNIVERSALIZACAO_SENHA=...`
   (Nunca reaproveitar `GOMNET_LOGIN`).

---

## 5. Recomendação

**Manter a Universalização DESATIVADA no Consulta SOB nesta etapa.**
Não criar providers fictícios ou conectores artificiais. A autoridade de consulta remota do SOB permanece restrita aos canais homologados e operacionais: **SharePoint corporativo** e **GOMNET**.
