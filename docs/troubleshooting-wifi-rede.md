# Troubleshooting – Conectividade Wi-Fi e Rede

**Público-alvo:** Equipe de Helpdesk (Nível 1)
**Última revisão:** Junho/2026

---

## 1. Diagnóstico Inicial

```powershell
# Configuração de rede completa (IP, gateway, DNS)
ipconfig /all

# Teste de conectividade básica
ping 8.8.8.8
ping google.com

# Rota até o destino (identifica onde a conexão falha)
tracert google.com
```

Se o `ping` por IP funcionar mas por nome falhar → problema de **DNS**.
Se nenhum `ping` funcionar → problema de **conectividade física/Wi-Fi**.

---

## 2. Sem Conexão à Rede Wi-Fi

**Causas comuns e resolução:**

| Causa | Verificação | Resolução |
|---|---|---|
| Driver de rede desatualizado/com falha | Gerenciador de Dispositivos > Adaptadores de Rede | Atualizar ou reinstalar o driver. |
| Perfil de Wi-Fi corrompido | `netsh wlan show profiles` | `netsh wlan delete profile name="NomeDaRede"` e reconectar inserindo a senha novamente. |
| Endereço IP não obtido (DHCP) | `ipconfig` mostra IP 169.254.x.x | `ipconfig /release` seguido de `ipconfig /renew` |
| Limite de dispositivos no ponto de acesso | — | Verificar com Infraestrutura se o AP está no limite de conexões simultâneas. |

---

## 3. Conectado mas Sem Acesso à Internet/Intranet

**Causas comuns e resolução:**

1. **Problema de DNS:**
   ```powershell
   ipconfig /flushdns
   nslookup intranet.empresa.com.br
   ```
   Se o `nslookup` falhar, verificar se o DNS configurado corresponde ao padrão corporativo:
   ```powershell
   Get-DnsClientServerAddress
   ```

2. **Conflito de IP (mensagem "Endereço IP duplicado"):**
   ```powershell
   ipconfig /release
   ipconfig /renew
   ```
   Se persistir, verificar reserva DHCP duplicada com a equipe de Infraestrutura.

3. **Proxy ou política de rede bloqueando tráfego:**
   - Verificar configuração em **Configurações > Rede e Internet > Proxy**.
   - Confirmar se a estação está no grupo correto de política de rede (GPO).

4. **Reset completo da pilha de rede (último recurso antes de escalar):**
   ```powershell
   netsh int ip reset
   netsh winsock reset
   ```
   Requer reinicialização da máquina após execução.

---

## 4. Conexão Instável (cai e reconecta constantemente)

**Causas comuns:**
- Driver de Wi-Fi com gerenciamento de energia ativo (economia de energia desligando o adaptador).
- Interferência de sinal (distância do AP, múltiplos APs com mesmo SSID mal configurados).

**Resolução:**
- Desabilitar economia de energia do adaptador: Gerenciador de Dispositivos > Adaptador Wi-Fi > Propriedades > Gerenciamento de Energia > desmarcar "Permitir que o computador desligue este dispositivo".
- Orientar reposicionamento ou testar em outro ponto de acesso para isolar problema de cobertura.

---

## 5. Checklist Pós-Resolução

- [ ] `ping` por IP e por nome funcionando.
- [ ] Acesso validado a pelo menos um recurso interno (intranet/servidor de arquivos).
- [ ] Conexão estável testada por no mínimo 5 minutos sem queda.
- [ ] Causa raiz registrada no chamado.

---

## 6. Quando Escalar para o Nível 2

- Problema afeta múltiplos usuários no mesmo andar/segmento de rede (possível falha de AP, switch ou VLAN).
- Reset de pilha de rede e reinstalação de driver não resolvem a instabilidade.
- Suspeita de conflito de IP recorrente, indicando erro na configuração do servidor DHCP.
- Necessidade de alteração em política de proxy, firewall ou GPO de rede.
