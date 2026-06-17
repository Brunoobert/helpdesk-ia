# Manual de Suporte Técnico – VPN Corporativa

**Público-alvo:** Equipe de Helpdesk (Nível 1)
**Última revisão:** Junho/2026

---

## 1. Visão Geral

A VPN (Virtual Private Network) corporativa permite que colaboradores acessem remotamente recursos internos da empresa — servidores de arquivos, sistemas ERP, intranet e impressoras de rede — através de um túnel criptografado estabelecido sobre a internet pública.

Os protocolos homologados pela empresa são **IKEv2**, **SSTP** e, em casos legados, **L2TP/IPsec**. A autenticação ocorre via credenciais de domínio (Active Directory) e, quando habilitado, fator adicional de MFA (autenticador móvel ou token físico).

O objetivo deste manual é orientar o atendimento de Nível 1 na configuração, diagnóstico e triagem de chamados relacionados à VPN.

---

## 2. Pré-requisitos

Antes de iniciar qualquer configuração, confirme com o usuário:

- Conexão à internet ativa e estável (mínimo 5 Mbps recomendado).
- Credenciais de domínio válidas e não expiradas (`DOMINIO\usuario`).
- Conta do usuário incluída no grupo de segurança **VPN-Users** no AD.
- Sistema operacional Windows 10 (versão 1909+) ou Windows 11 atualizado.
- Antivírus/firewall local não bloqueando as portas necessárias (UDP 500/4500 para IKEv2; TCP 443 para SSTP).
- Certificado digital corporativo instalado, se o ambiente exigir autenticação baseada em certificado.
- MFA previamente cadastrado, caso a política exija segundo fator.

---

## 3. Passo a Passo – Configuração no Windows 10/11

1. Pressione **Win + I** para abrir **Configurações**.
2. Acesse **Rede e Internet > VPN**.
3. Clique em **Adicionar uma conexão VPN**.
4. Em **Provedor de VPN**, selecione **Windows (incorporado)**.
5. Em **Nome da conexão**, digite `VPN Corporativa`.
6. Em **Nome ou endereço do servidor**, insira o endereço fornecido pela TI (ex.: `vpn.empresa.com.br`).
7. Em **Tipo de VPN**, selecione o protocolo indicado para o usuário (recomenda-se **IKEv2**).
8. Em **Tipo de informações de login**, selecione **Nome de usuário e senha**.
9. Informe as credenciais de domínio do colaborador.
10. Clique em **Salvar**.
11. Na bandeja do sistema, clique no ícone de rede, selecione **VPN Corporativa** e clique em **Conectar**.
12. Valide a conexão executando `ipconfig /all` (deve aparecer um adaptador PPP) e testando o acesso a um recurso interno (ex.: `ping` no servidor de arquivos).

---

## 4. Erros Comuns

| Código | Descrição | Solução |
|---|---|---|
| **800** | Não foi possível estabelecer a conexão VPN | Verificar endereço do servidor e protocolo selecionado; testar conectividade básica à internet. |
| **809** | O computador remoto não respondeu | Portas UDP 500/4500 bloqueadas (firewall local ou roteador doméstico). Orientar troca do tipo de VPN para **SSTP** (porta 443). |
| **691** | Acesso negado — usuário/senha inválidos | Confirmar credenciais; verificar se a conta está bloqueada ou a senha expirada no AD. |
| **13801** | Falha na negociação IKE | Certificado ausente, expirado ou inválido. Reinstalar/atualizar o certificado corporativo. |
| **720** | Não foi possível negociar um conjunto de protocolos compatível | Remover e recriar o adaptador VPN; verificar atualizações pendentes do Windows. |
| **868** | O servidor VPN não pôde ser resolvido | Falha de DNS; testar resolução de nome (`nslookup`) e conexão com a internet. |

---

## 5. Quando Escalar para o Nível 2

Encaminhe o chamado ao Nível 2 quando:

- O erro persistir após validar credenciais, reiniciar o adaptador de rede e recriar a conexão VPN.
- Múltiplos usuários reportarem falhas simultâneas (possível indisponibilidade do concentrador VPN ou firewall).
- For necessário alterar regras de firewall, NAT ou liberação de portas na borda da rede.
- O certificado corporativo estiver expirado/corrompido e exigir reemissão pela equipe de PKI.
- Houver suspeita de comprometimento de conta (múltiplas tentativas de login falhas, acesso de localização incomum).
- For necessária análise de logs do servidor VPN ou do firewall perimetral, aos quais o N1 não possui acesso.

Ao escalar, registre no chamado: código de erro, horário das tentativas, protocolo utilizado e prints da tela de erro, quando disponíveis.