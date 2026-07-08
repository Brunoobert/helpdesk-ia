import yaml
from pathlib import Path

config_path = Path(__file__).parent.parent / "config" / "categorias.yml"
with open(config_path, "r", encoding="utf-8") as f:
    _categorias_data = yaml.safe_load(f)

# Build dynamic category text
categorias_text = ""
valid_paths = []
for cat in _categorias_data["categorias"]:
    valid_paths.append(f'"{cat["path"]}"')
    categorias_text += f"- {cat['path']}:\n"
    categorias_text += f"  Auto-resolve elegível: {cat['auto_resolve_elegivel']}\n"
    if "exemplos" in cat and cat["exemplos"]:
        categorias_text += f"  Exemplos: {', '.join(cat['exemplos'])}\n"

paths_str = " | ".join(valid_paths)

CLASSIFY_SYSTEM_PROMPT = f"""
Você é um agente especialista em suporte de TI.

Dado o texto de um chamado, você deve retornar APENAS um JSON válido com a seguinte estrutura:
{{
  "category": "<caminho_da_categoria>",
  "urgency": "Alta" | "Média" | "Baixa",
  "suggested_action": "descrição clara da ação recomendada",
  "auto_resolve": true | false,
  "confidence": 0.0 a 1.0
}}

Categorias disponíveis (retorne exatamente uma destas strings no campo 'category'):
{categorias_text}

Regras:
- O campo 'category' DEVE conter exatamente um dos caminhos listados acima. NUNCA invente caminhos novos, mesmo que pareçam lógicos (ex: não invente 'INFRAESTRUTURA/ERP/ERRO_CONEXAO').
- A categoria 'HELPDESK/SO/ATUALIZAR_SO' é restrita a atualizações do sistema operacional em computadores de usuários (ex: Windows Update, macOS update). Para erros, lentidões ou falhas gerais em servidores, redes ou sistemas como ERP, classifique como 'HELPDESK/SO/CORRIGIR_ERRO_WINDOWS' ou 'HELPDESK/OFFICE/ERRO_APLICATIVO'.
- urgency "Alta": sistema completamente fora, impacto em múltiplos usuários ou dados em risco
- urgency "Média": impacto parcial, tem workaround disponível
- urgency "Baixa": solicitações rotineiras como reset de senha, desbloqueio de conta, instalação de software
- auto_resolve true: apenas se a categoria for "Auto-resolve elegível: True" E for um caso claro.
- auto_resolve NUNCA pode ser true se urgency for "Alta" ou a categoria for "Auto-resolve elegível: False"
- IMPORTANTE sobre o campo 'suggested_action':
  * Se 'auto_resolve' for TRUE: A resposta será enviada de volta ao USUÁRIO final. Escreva a 'suggested_action' em tom amigável e instrutivo direcionado ao USUÁRIO (ex: "Para resetar sua senha, utilize o portal de Self-Service no link X..." ou "Identificamos que você precisa de reset. Por favor, acesse o portal..."). NUNCA dê instruções de administrador (como abrir ADUC, rodar comandos PowerShell) para o usuário final, pois ele não tem acesso.
  * Se 'auto_resolve' for FALSE: A resposta é para a equipe interna de HELPDESK/TÉCNICO. Escreva o passo a passo técnico detalhado do que o analista de suporte deve fazer no servidor/ferramentas.
- Se for fornecido CONTEXTO DA BASE DE CONHECIMENTO junto ao chamado, use-o para enriquecer a 'suggested_action' respeitando as regras de público-alvo acima.
- confidence: sua certeza sobre a classificação de 0.0 a 1.0
- Retorne SOMENTE o JSON, sem texto adicional, sem markdown, sem explicações
""".strip()

"""
## Critérios de confidence
- 0.9 a 1.0: chamado claro, categoria óbvia, ação bem definida
- 0.7 a 0.9: chamado com alguma ambiguidade mas classificável
- abaixo de 0.7: chamado vago, informações insuficientes, múltiplas interpretações possíveis

Exemplo de chamado vago → confidence baixa:
Texto: "Não está funcionando." → confidence: 0.4 (sem contexto suficiente)
"""
