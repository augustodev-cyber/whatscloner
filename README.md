# WhatsCloner Professional

<p align="center">
  <img src="assets/banner.png" width="100%" alt="WhatsCloner Banner">
</p>

<h3 align="center">Framework de Pentest para Segurança do WhatsApp</h3>

<p align="center">
  <strong>Pentest • Red Team • Análise de Sessões • Segurança de Autenticação</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Categoria-Pentest-red?style=for-the-badge">
  <img src="https://img.shields.io/badge/Plataforma-Linux-black?style=for-the-badge&logo=linux">
  <img src="https://img.shields.io/badge/Linguagem-Python-blue?style=for-the-badge&logo=python">
  <img src="https://img.shields.io/badge/Versão-1.0-brightgreen?style=for-the-badge">
</p>

---

## Sobre o projeto

**WhatsCloner** é uma ferramenta de Pentest desenvolvida em Python, direcionada à avaliação de segurança dos mecanismos de autenticação, vinculação de dispositivos e gerenciamento de sessões do WhatsApp Web.

Desenvolvida com uma abordagem voltada a operações de Red Team e pesquisas em segurança ofensiva, a ferramenta explora conceitos relacionados a *WhatsApp Session Hijacking*, autenticação por QR Code e persistência de sessões.

A aplicação disponibiliza uma interface interativa no terminal, automação de navegador e um painel web para monitoramento do ambiente de testes.

Seu propósito é auxiliar profissionais de segurança da informação, pesquisadores e estudantes na compreensão de possíveis vetores de ataque e dos riscos associados aos mecanismos de autenticação do WhatsApp.

## Principais funcionalidades

- **Monitoramento de QR Code:** acompanhamento visual de códigos QR em ambientes autorizados.
- **Espelhamento de QR Code:** visualização dos códigos monitorados através de uma interface web.
- **Gerenciamento de sessões:** administração das sessões de teste registradas.
- **Persistência de sessões:** preservação de perfis e estados do navegador.
- **Automação de navegador:** integração com Playwright.
- **Painel web:** interface centralizada para acompanhamento da aplicação.
- **Configurações de rede:** suporte a diferentes modalidades de exposição.

### Menu principal

```text
WhatsCloner Professional ✔ | v1.0

Não nos responsabilizamos pelo uso indevido

Autor: augustodev-cyber ✔
GitHub: https://github.com/augustodev-cyber

MENU PRINCIPAL — SESSÕES

  > + Nova sessão / Inicializar ferramenta

    Configurações
    Gerenciar sessões
    Sobre o projeto
    Sair

↑/↓ Navegar    ENTER Selecionar    ESC Voltar
```

### Opções disponíveis

| Opção | Descrição |
|---|---|
| Nova sessão / Inicializar ferramenta | Inicialização de um novo ambiente de teste |
| Configurações | Acesso às configurações da aplicação |
| Gerenciar sessões | Gerenciamento das sessões registradas |
| Sobre o projeto | Informações sobre a ferramenta |
| Sair | Encerramento da aplicação |

## Demonstração visual

### Painel de monitoramento

<p align="center">
  <img src="assets/dashboard.png" width="100%" alt="Painel web">
</p>

### Monitoramento de QR Code

<p align="center">
  <img src="assets/monitor.png" width="100%" alt="Monitoramento de QR Code">
</p>

### Gerenciamento de sessões

<p align="center">
  <img src="assets/sessions.png" width="100%" alt="Gerenciamento de sessões">
</p>

## Tecnologias utilizadas

| Tecnologia | Aplicação |
|---|---|
| Python | Desenvolvimento principal |
| Flask | Servidor e interface web |
| Playwright | Automação de navegador |
| Chromium | Ambiente de navegação |
| HTML5 / CSS3 | Interface visual |
| JavaScript | Funcionalidades da interface |

## Instalação

Clone o repositório:

```bash
git clone https://github.com/augustodev-cyber/WhatsCloner.git
```

Entre no diretório:

```bash
cd WhatsCloner
```

Configure as permissões:

```bash
chmod +x install.sh run.sh
```

Instale as dependências:

```bash
./install.sh
```

## Como utilizar

Inicialize a ferramenta:

```bash
./run.sh
```

Utilize as teclas direcionais para navegar pelo menu:

- `↑ / ↓` — Navegar pelas opções.
- `ENTER` — Selecionar uma opção.
- `ESC` — Retornar ao menu anterior.

Siga as instruções apresentadas no terminal para inicializar o ambiente de testes e acessar a interface web.

## Aviso legal

O WhatsCloner foi desenvolvido para fins educacionais, auditorias de segurança autorizadas, pesquisas em cibersegurança e exercícios controlados de Red Team.

A utilização deve ser restrita a contas próprias, dispositivos de teste ou ambientes cujo proprietário tenha concedido autorização expressa.

O projeto não deve ser utilizado para obtenção de acesso não autorizado, captura de sessões de terceiros ou violação de privacidade.

O desenvolvedor não se responsabiliza por danos ou atividades ilícitas decorrentes do uso indevido da ferramenta.

O WhatsCloner é um projeto independente, sem vínculo oficial com WhatsApp ou Meta.

## Desenvolvedor

**AugustoDev-Cyber**

GitHub: https://github.com/augustodev-cyber

- **Projeto:** WhatsCloner Professional
- **Versão:** 1.0
- **Categoria:** Pentest / Segurança do WhatsApp
- **Linguagem:** Python

---

<p align="center">
  <strong>WhatsCloner Professional</strong>
  <br>
  <sub>Framework de Pesquisa e Avaliação de Segurança</sub>
  <br><br>
  <strong>Identificar. Avaliar. Proteger.</strong>
</p>
