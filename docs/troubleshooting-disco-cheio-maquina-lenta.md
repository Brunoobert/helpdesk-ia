# Troubleshooting – Disco Cheio e Máquina Lenta

**Público-alvo:** Equipe de Helpdesk (Nível 1)
**Última revisão:** Junho/2026

---

## 1. Diagnóstico Inicial

Antes de aplicar qualquer correção, colete as informações abaixo para identificar se o problema é de espaço em disco, desempenho geral, ou ambos.

```powershell
# Espaço livre por unidade
Get-PSDrive -PSProvider FileSystem

# Uso de CPU e memória em tempo real
Get-Counter '\Processor(_Total)\% Processor Time'
Get-Counter '\Memory\Available MBytes'
```

---

## 2. Disco Cheio

**Sintoma:** Alerta "Espaço em disco baixo", lentidão ao salvar arquivos, impossibilidade de instalar atualizações.

**Causas comuns e resolução:**

| Causa | Comando/Passo de verificação | Resolução |
|---|---|---|
| Arquivos temporários acumulados | `cleanmgr /sageset:1` | Executar Limpeza de Disco, incluindo arquivos do sistema. |
| Cache do Windows Update | — | `Stop-Service wuauserv; Remove-Item C:\Windows\SoftwareDistribution\Download\* -Recurse -Force; Start-Service wuauserv` |
| Pasta OneDrive sincronizando tudo localmente | Verificar status do ícone do OneDrive | Habilitar **Arquivos Sob Demanda** (Files On-Demand) nas configurações do OneDrive. |
| Pasta de usuário com arquivos grandes esquecidos | `Get-ChildItem C:\Users\<usuario> -Recurse \| Sort-Object Length -Descending \| Select-Object -First 10 FullName, Length` | Orientar o usuário a mover arquivos grandes para o servidor de arquivos ou SharePoint. |
| Pontos de restauração do sistema acumulados | `vssadmin list shadowstorage` | `vssadmin resize shadowstorage /for=C: /on=C: /maxsize=10%` |

---

## 3. Máquina Lenta (sem problema de disco)

**Sintoma:** Boot demorado, aplicativos travando ao abrir, ventilador em alta rotação constante.

**Causas comuns e resolução:**

1. **Excesso de programas na inicialização:**
   ```powershell
   Get-CimInstance Win32_StartupCommand | Select-Object Name, Command, Location
   ```
   Desabilitar itens não essenciais via Gerenciador de Tarefas > Inicializar.

2. **Antivírus em varredura completa simultânea ao uso:** verificar agendamento e reprogramar para horário de menor uso.

3. **Disco mecânico (HDD) em máquina com mais de 4 anos:** verificar se já houve avaliação de upgrade para SSD — item recorrente em chamados de lentidão.

4. **Memória RAM insuficiente para a carga de trabalho atual (ex.: múltiplas abas + Teams + Office):**
   ```powershell
   Get-Counter '\Memory\Available MBytes'
   ```
   Se consistentemente abaixo de 500 MB disponíveis, registrar necessidade de upgrade.

5. **Verificação de integridade do disco (possível falha de hardware):**
   ```powershell
   Get-PhysicalDisk | Select-Object FriendlyName, HealthStatus, OperationalStatus
   ```

---

## 4. Checklist Pós-Resolução

- [ ] Espaço livre em C: acima de 15% da capacidade total.
- [ ] Uso de CPU em repouso (sem aplicativos abertos) abaixo de 20%.
- [ ] Reinicialização realizada após limpeza/ajustes.
- [ ] Usuário confirmou melhora perceptível no desempenho.
- [ ] Registro no chamado da causa raiz identificada.

---

## 5. Quando Escalar para o Nível 2

- `HealthStatus` do disco retornar **Warning** ou **Unhealthy** (indício de falha física iminente).
- Lentidão persistir mesmo após liberação de espaço, fechamento de processos e reinicialização.
- Suspeita de processo malicioso consumindo recursos (verificar com a equipe de Segurança antes de qualquer ação).
- Necessidade de upgrade de hardware (RAM/SSD), que exige abertura de chamado de aquisição/patrimônio.
