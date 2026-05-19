"""
Teste rápido do Inquisidor — 1 chamada LLM, sem Crew, sem GUI
"""
import os, sys
from dotenv import load_dotenv
load_dotenv()

PETICAO = """EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 1ª VARA CÍVEL DA COMARCA DE SÃO PAULO

JOÃO DA SILVA, nos autos da Ação de Cobrança que lhe move BANCO XYZ S.A., apresenta CONTESTAÇÃO.

I - DOS FATOS
O Autor alega que o Réu contratou empréstimo de R$ 50.000,00 em 02/01/2023 e desde ago/2023 deixou de pagar, gerando saldo de R$ 62.341,18. O Réu nunca celebrou contrato com o Banco. Não há assinatura válida.

II - DO DIREITO
a) Inexistência de relação contratual (CC Art. 104)
b) Nulidade por vício de consentimento (CC Art. 166)
c) Inversão do ônus da prova (CDC Art. 6º, VIII)
d) Súmula 297 STJ

III - DOS PEDIDOS
Improcedência da ação. Condenação por má-fé. Prova pericial grafotécnica."""

PROMPT = f"""Analise em português: {PETICAO}

Resuma em 3 linhas os pontos fracos da defesa do réu."""

print("=" * 60)
print("  INQUISIDOR — TESTE RÁPIDO v6.9")
print("=" * 60)

from litellm import completion

try:
    print("\n[LLM] Enviando...\n")
    resp = completion(
        model="openai/meta/llama-3.3-70b-instruct",
        api_key=os.getenv("NVIDIA_API_KEY"),
        api_base="https://integrate.api.nvidia.com/v1",
        messages=[{"role": "user", "content": PROMPT}],
        temperature=0.3,
        max_tokens=512,
        timeout=60,
    )
    resultado = resp.choices[0].message.content
    print(resultado)
    print("\n[OK] Concluído")
except Exception as e:
    print(f"\n[ERRO] {type(e).__name__}: {str(e)[:200]}")
