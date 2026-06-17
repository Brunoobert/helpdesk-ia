# Troubleshooting – Outlook e Teams Travando ou Sem Sincronizar

**Público-alvo:** Equipe de Helpdesk (Nível 1)
**Última revisão:** Junho/2026

---

## 1. Outlook

### 1.1 Sintoma: Outlook congela ao abrir ou ao enviar/receber

**Causas comuns:**
- Arquivo de cache local (.OST) corrompido.
- Add-in de terceiros causando conflito (ex.: plugins de assinatura, antivírus).
- Caixa de e-mail muito grande sincronizando integralmente.

**Resolução:**
1. Abrir o Outlook em modo de segurança para isolar add-ins:
   ```
   outlook.exe /safe
   ```
2. Se estabilizar, desabilitar add-ins um a um em **Arquivo > Opções > Suplementos**.
3. Recriar o perfil do Outlook (recomendado quando o problema persiste):
   - Painel de Controle > Contas de Email > Mostrar Perfis > Remover e recriar.
4. Verificar integridade do arquivo .OST:
   ```
   "C:\Program Files\Microsoft Office\root\Office16\SCANPST.EXE"
   ```
5. Para caixas muito grandes, reduzir o período de sincronização local em **Configurações da Conta > Mais Configurações > Avançado > Sincronização de Pastas**.

### 1.2 Sintoma: E-mails não atualizam (sem erro aparente)

**Resolução:**
- Verificar status da conexão no canto inferior do Outlook ("Conectado" vs "Tentando conectar").
- Forçar reconexão: `Ctrl + Alt + F9` (Enviar/Receber forçado em todas as pastas).
- Verificar Service Health do Microsoft 365 antes de aprofundar o diagnóstico local:
  ```
  https://portal.office.com/servicestatus
  ```

---

## 2. Microsoft Teams

### 2.1 Sintoma: Teams travado, lento ou consumindo muita CPU

**Causas comuns:**
- Cache local corrompido (comum após atualizações do Teams).
- Aceleração de hardware (GPU) causando instabilidade em notebooks com drivers de vídeo desatualizados.

**Resolução:**
1. Fechar o Teams completamente (verificar na bandeja do sistema, pois ele continua em segundo plano).
2. Limpar o cache local:
   ```powershell
   Remove-Item "$env:APPDATA\Microsoft\Teams\Cache\*" -Recurse -Force
   Remove-Item "$env:APPDATA\Microsoft\Teams\blob_storage\*" -Recurse -Force
   ```
3. Reabrir o Teams e validar.
4. Se persistir, desabilitar aceleração de hardware: **Configurações > Geral > desmarcar "Desativar aceleração de hardware"** (testar com a opção marcada/desmarcada).

### 2.2 Sintoma: Falha de áudio/vídeo em chamadas

**Resolução:**
- Verificar se outro aplicativo está utilizando a câmera/microfone simultaneamente.
- Confirmar permissões em **Configurações de Privacidade do Windows > Câmera/Microfone**.
- Testar chamada de diagnóstico interna do Teams: ícone de perfil > **Configurações > Dispositivos > Fazer uma chamada de teste**.

---

## 3. Checklist Pós-Resolução

- [ ] Outlook sincroniza envio/recebimento sem erro.
- [ ] Teams abre sem travamento perceptível em até 10 segundos.
- [ ] Teste de chamada (áudio/vídeo) realizado com sucesso, se aplicável.
- [ ] Cache limpo registrado no histórico do chamado.

---

## 4. Quando Escalar para o Nível 2

- Falha confirmada no **Service Health do Microsoft 365** (problema do lado do provedor, não da estação).
- Corrupção recorrente do perfil do Outlook mesmo após recriação (possível problema na conta no Exchange Online).
- Lentidão do Teams afetando múltiplos usuários simultaneamente na mesma rede (possível gargalo de banda ou proxy/firewall).
- Necessidade de revisão de política de GPO relacionada a aceleração de hardware ou permissões de dispositivo aplicada via Intune.
