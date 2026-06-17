# Política de Backup Corporativo

**Classificação:** Documento Interno
**Aplicabilidade:** Todos os colaboradores e setores
**Última revisão:** Junho/2026

---

## 1. Objetivo

Esta política estabelece as diretrizes, responsabilidades e procedimentos relativos à cópia de segurança (backup) e restauração de dados corporativos, visando garantir a continuidade das operações e a integridade das informações da empresa.

---

## 2. Escopo

### 2.1 O que é coberto

- Servidores de arquivos corporativos (compartilhamentos de rede).
- Bancos de dados de sistemas internos (ERP, CRM, sistemas legados).
- Caixas de e-mail corporativo hospedadas no ambiente Office 365.
- Máquinas virtuais e servidores de infraestrutura (Active Directory, aplicações).
- Diretórios de rede designados como "Meus Documentos" redirecionados ao servidor.

### 2.2 O que **não** é coberto

- Arquivos armazenados localmente em discos de notebooks/desktops (área de trabalho, "Downloads", pastas locais fora do redirecionamento).
- Dispositivos pessoais (BYOD) não homologados pela TI.
- Mídias removíveis (pendrives, HDs externos).
- Aplicações ou softwares não homologados/instalados sem autorização da TI.

---

## 3. Frequência de Backup por Tipo de Dado

| Tipo de dado | Frequência | Janela de execução |
|---|---|---|
| Bancos de dados críticos (ERP/CRM) | Diário | Madrugada (00h–04h) |
| Servidores de arquivos | Diário (incremental) / Semanal (completo) | Noturna |
| Caixas de e-mail (O365) | Diário (nativo do provedor) | Contínuo |
| Servidores de infraestrutura (AD, DNS, DHCP) | Semanal | Fim de semana |
| Arquivamento histórico/compliance | Mensal | Último dia útil do mês |

---

## 4. Retenção

- Backups diários: retidos por **30 dias**.
- Backups semanais: retidos por **90 dias**.
- Backups mensais: retidos por **12 meses**.
- Backups de encerramento de exercício fiscal: retidos por **5 anos**, conforme exigência legal/contábil.

---

## 5. Responsabilidades

### 5.1 Da TI

- Executar, monitorar e validar a integridade das rotinas de backup.
- Garantir a disponibilidade de mídias/armazenamento redundante (preferencialmente em local/nuvem distinto do ambiente primário).
- Realizar testes periódicos de restauração (trimestral) para validar a recuperabilidade dos dados.
- Atender solicitações de restauração conforme SLA definido nesta política.

### 5.2 Do Usuário

- Armazenar arquivos de trabalho exclusivamente em diretórios de rede cobertos por backup (Seção 2.1).
- Não depender de armazenamento local para informações críticas ou insubstituíveis.
- Solicitar restauração formalmente, conforme procedimento da Seção 6.

---

## 6. Procedimento de Solicitação de Restauração

1. Abrir chamado no sistema de helpdesk, categoria **"Restauração de Arquivo/Backup"**.
2. Informar: nome completo/caminho do arquivo ou pasta, data aproximada da última versão íntegra conhecida, e justificativa da solicitação.
3. A TI valida a existência do backup correspondente ao período solicitado.
4. Restauração realizada em ambiente de teste (quando aplicável) antes da entrega final.
5. Usuário confirma o recebimento e a integridade do arquivo restaurado, encerrando o chamado.

---

## 7. SLA de Atendimento

| Prioridade | Critério | Tempo de resposta | Tempo de resolução |
|---|---|---|---|
| Crítica | Indisponibilidade de sistema/servidor | 1 hora | 4 horas |
| Alta | Perda de arquivo essencial à operação do dia | 2 horas | 8 horas úteis |
| Normal | Restauração de arquivo individual | 4 horas | 24 horas úteis |

---

## 8. Penalidades por Não Conformidade

- O descumprimento desta política (ex.: armazenamento de dados críticos exclusivamente em local não coberto por backup) sujeita o colaborador a advertência formal, conforme normas de RH.
- Em caso de perda de dados decorrente de descumprimento comprovado, a área responsável poderá ser cobrada quanto aos impactos operacionais junto à gestão.
- Reincidências serão registradas no histórico funcional do colaborador e poderão escalar conforme política disciplinar da empresa.