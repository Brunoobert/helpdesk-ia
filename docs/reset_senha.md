# Reset de Senha e Desbloqueio de Conta – AD / Azure AD / Intune

**Público-alvo:** Equipe de Helpdesk (Nível 1)
**Última revisão:** Junho/2026

---

## 1. Self-Service vs. Abertura de Chamado

**Self-service (SSPR – Self-Service Password Reset):**
- Usuário esqueceu a senha, mas ainda consegue acessar o portal `myaccount.microsoft.com` ou a tela de login do Windows com opção "Esqueci minha senha".
- Conta não está bloqueada por tentativas excessivas.
- Usuário possui métodos de verificação já cadastrados (telefone, e-mail alternativo, Authenticator).

**Abertura de chamado (atendimento N1):**
- Conta bloqueada após múltiplas tentativas incorretas.
- Usuário não possui métodos de SSPR cadastrados ou não tem mais acesso a eles.
- Conta de serviço, administrativa ou sem licença de SSPR habilitada.
- Dispositivo gerenciado por Intune apresentando erro de sincronização de credenciais após troca de senha.

---

## 2. Passo a Passo – Técnico (AD Users and Computers)

1. Abrir **Active Directory Users and Computers (ADUC)**.
2. Localizar o usuário pelo nome de login (`sAMAccountName`).
3. Clicar com o botão direito > **Reset Password**.
4. Definir senha temporária conforme política da Seção 3.
5. Marcar **"User must change password at next logon"**.
6. Verificar se a conta está marcada como **"Account is locked out"**; se sim, desmarcar a opção de desbloqueio na mesma tela.
7. Em ambientes **híbridos** (sincronizados com Azure AD via Azure AD Connect): aguardar o ciclo de sincronização (até 30 minutos) ou forçar com `Start-ADSyncSyncCycle -PolicyType Delta` no servidor de sincronização.
8. Para dispositivos gerenciados por **Intune**: orientar o usuário a reiniciar o equipamento ou executar **Configurações > Contas > Acessar trabalho ou escola > Sincronizar** para atualizar o cache de credenciais e evitar bloqueio por Windows Hello for Business desatualizado.

---

## 3. Política de Senha (requisitos mínimos)

- Mínimo de **12 caracteres**.
- Deve conter: letra maiúscula, letra minúscula, número e caractere especial.
- Não pode repetir as últimas **5 senhas** utilizadas.
- Validade máxima de **90 dias**.
- Bloqueio automático após **5 tentativas incorretas**, com duração de **15 minutos** ou liberação manual pelo helpdesk.

---

## 4. Erros Frequentes

| Erro | Causa provável | Solução |
|---|---|---|
| "Sua senha expirou" mesmo após reset | Cache de credenciais local desatualizado | Reiniciar a máquina ou desconectar/reconectar a VPN antes de tentar novamente. |
| Conta bloqueada novamente em poucos minutos | Dispositivo móvel ou aplicativo (e-mail antigo) usando credenciais antigas | Atualizar senha em todos os dispositivos sincronizados (Outlook mobile, Wi-Fi corporativo). |
| Erro de sincronização no Intune após reset | Token de autenticação do dispositivo não renovado | Forçar sincronização manual ou reingressar o dispositivo no Azure AD. |
| SSPR não disponível para o usuário | Métodos de verificação não cadastrados ou licença ausente | Verificar licenciamento no Azure AD e orientar cadastro em `aka.ms/ssprsetup`. |

---

## 5. Checklist de Verificação Pós-Reset

- [ ] Usuário confirmou login bem-sucedido com a nova senha.
- [ ] Senha temporária foi trocada no primeiro acesso.
- [ ] Sincronização com Azure AD concluída (sem erros no Azure AD Connect Health, se aplicável).
- [ ] Dispositivo Intune sincronizado e sem alertas de conformidade.
- [ ] Acesso testado a e-mail, VPN e sistemas internos críticos.
- [ ] Chamado encerrado com registro da causa raiz, se identificada.