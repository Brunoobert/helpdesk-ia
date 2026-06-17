# Guia de Troubleshooting – Impressoras Corporativas

**Público-alvo:** Equipe de Helpdesk (Nível 1)
**Última revisão:** Junho/2026

---

## Árvore de Decisão

```
Usuário não consegue imprimir
│
├─ Impressora aparece OFFLINE? ───────────────► Seção 4
├─ Erro de conexão/não encontrada? ───────────► Seção 1
├─ Erro relacionado a driver? ────────────────► Seção 2
└─ Trabalho preso na fila de impressão? ──────► Seção 3
```

---

## 1. Problema de Conexão

**Sintoma:** Impressora não aparece na lista, ou erro "Não foi possível conectar à impressora".

**Causa provável:**
- Impressora desligada ou desconectada da rede.
- IP da impressora alterado (DHCP) sem atualização no servidor de impressão.
- Cabo de rede ou porta de switch com falha.

**Resolução:**
1. Verificar se a impressora está ligada e com luz de rede ativa.
2. Testar conectividade:
   ```powershell
   Test-Connection -ComputerName 10.10.20.50 -Count 4
   ```
3. Se o IP não responder, verificar se foi alterado no painel da impressora e atualizar a porta no servidor:
   ```powershell
   Get-PrinterPort -Name "IP_10.10.20.50"
   Set-PrinterPort -Name "IP_10.10.20.50" -PrinterHostAddress "10.10.20.51"
   ```
4. Reiniciar o spooler de impressão no servidor:
   ```powershell
   Restart-Service -Name Spooler -Force
   ```

**Escalar quando:** O IP for fixo e a impressora não responder mesmo após reinício físico — indício de falha de hardware ou problema de rede/switch (acionar equipe de Infraestrutura).

---

## 2. Problema de Driver

**Sintoma:** Erro "0x0000011b" ao imprimir via rede, ou impressão sai com caracteres corrompidos.

**Causa provável:**
- Driver desatualizado, corrompido ou incompatível após atualização do Windows (comum com o KB relacionado ao Point and Print).
- Driver divergente entre o servidor de impressão e a estação.

**Resolução:**
1. Verificar o driver instalado:
   ```powershell
   Get-PrinterDriver
   ```
2. Remover a impressora e o driver da estação:
   ```powershell
   Remove-Printer -Name "Impressora_RH"
   Remove-PrinterDriver -Name "HP Universal Printing PCL 6"
   ```
3. Reinstalar a partir do servidor de impressão com driver atualizado.
4. Caso o erro **0x0000011b** persista, verificar se a chave de registro `RpcAuthnLevelPrivacyEnabled` está configurada corretamente no servidor (alteração introduzida por atualização de segurança da Microsoft).

**Escalar quando:** O driver mais recente do fabricante já estiver instalado e o erro persistir, indicando necessidade de revisão da configuração do servidor de impressão (Nível 2/Infraestrutura).

---

## 3. Fila de Impressão Travada

**Sintoma:** Documentos acumulam na fila e não imprimem; status "Status: Erro" ou "Excluindo".

**Resolução:**
1. Parar o serviço de spooler:
   ```powershell
   Stop-Service -Name Spooler -Force
   ```
2. Limpar a pasta de spool manualmente:
   ```powershell
   Remove-Item "C:\Windows\System32\spool\PRINTERS\*" -Force
   ```
3. Reiniciar o serviço:
   ```powershell
   Start-Service -Name Spooler
   ```
4. Reenviar o documento de teste.

**Escalar quando:** O travamento ocorrer repetidamente no mesmo servidor de impressão em múltiplas impressoras simultaneamente, sugerindo problema no serviço de spooler do servidor (não apenas da estação local).

---

## 4. Impressora Offline

**Sintoma:** Ícone da impressora exibe "Offline" mesmo com o equipamento ligado e na rede.

**Causa provável:**
- Configuração incorreta de "Usar impressora offline" habilitada no Windows.
- Spooler local com cache inconsistente.

**Resolução:**
1. Verificar status:
   ```powershell
   Get-Printer -Name "Impressora_RH" | Select-Object PrinterStatus
   ```
2. Forçar status online:
   ```powershell
   Set-Printer -Name "Impressora_RH" -PrinterStatus Normal
   ```
3. Reiniciar o spooler local na estação do usuário.
4. Confirmar que a opção **"Usar Impressora Offline"** está desmarcada no menu da fila de impressão.

**Escalar quando:** O status retornar para "Offline" repetidamente após as correções, ou afetar múltiplos usuários no mesmo segmento de rede — possível falha de VLAN ou política de QoS bloqueando a comunicação (acionar Infraestrutura de Rede).