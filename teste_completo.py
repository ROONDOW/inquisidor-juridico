"""
Teste completo do Inquisidor — prompt real do Analista + Revisor
"""
import os, sys, time
from dotenv import load_dotenv
load_dotenv()

PETICAO = """EXCELENTÍSSIMO SENHOR DOUTOR JUIZ DE DIREITO DA 1ª VARA CÍVEL

Processo nº 2025.012345-6

JOÃO DA SILVA, nos autos da Ação de Cobrança que lhe move BANCO XYZ S.A., apresenta CONTESTAÇÃO.

I - DOS FATOS
O Autor alega que o Réu contratou empréstimo de R$ 50.000,00 em 02/01/2023, com parcelas de R$ 2.847,33 em 24 meses, e que desde a 6ª parcela (ago/2023) deixou de pagar, gerando saldo devedor de R$ 62.341,18. O Réu nunca celebrou contrato de empréstimo com o Banco XYZ. Não há assinatura do Réu no contrato.

II - DO DIREITO
a) Inexistência de relação contratual - Ausência de manifestação de vontade (CC Art. 104)
b) Nulidade do contrato por vício de consentimento (CC Art. 166)
c) Inversão do ônus da prova - Cabe ao Autor comprovar (CDC Art. 6º, VIII)
d) Súmula 297 STJ

III - DOS PEDIDOS
Total improcedência. Condenação por má-fé. Prova pericial grafotécnica."""

PROMPT_ANALISTA = f"""Você é um promotor de justiça com 30 anos de experiência.

Analise a petição abaixo:

{PETICAO}

Para cada argumento do adversário:
1. IDENTIFIQUE a tese central
2. AVALIE a solidez jurídica
3. APONTE vulnerabilidades
4. CITE artigos (CPC, CC, CF) e precedentes STJ/STF aplicáveis

Formato obrigatório:
- Resumo Executivo (3 linhas)
- Quadro de Vulnerabilidades
- Teses de Defesa com artigos
- Precedentes Recomendados"""

PROMPT_REVISOR = """Revise o relatório abaixo como desembargador:

{relatorio}

1. Elimine contradições
2. Verifique se os artigos citados são aplicáveis
3. Garanta tom profissional e coesão
4. Versão final em formato de relatório jurídico"""

from litellm import completion

API_KW = dict(
    model="openai/meta/llama-3.3-70b-instruct",
    api_key=os.getenv("NVIDIA_API_KEY"),
    api_base="https://integrate.api.nvidia.com/v1",
    temperature=0.3,
)

def chamar(prompt, max_tokens=2048, label=""):
    print(f"\n>>> AGENTE: {label}")
    print("-" * 60)
    t0 = time.time()
    try:
        resp = completion(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            timeout=90,
            **API_KW,
        )
        texto = resp.choices[0].message.content
        dt = time.time() - t0
        print(f"[{dt:.0f}s] {len(texto)} caracteres\n")
        print(texto)
        return texto
    except Exception as e:
        print(f"[ERRO] {type(e).__name__}: {str(e)[:200]}")
        return f"[ERRO: {str(e)[:100]}]"

print("=" * 60)
print("  INQUISIDOR — TESTE COMPLETO v6.9")
print("=" * 60)

# Etapa 1: Analista
r1 = chamar(PROMPT_ANALISTA, label="Analista Jurídico")

# Etapa 2: Revisor
if r1 and not r1.startswith("[ERRO"):
    r2 = chamar(PROMPT_REVISOR.format(relatorio=r1), label="Revisor de Consistência")
else:
    r2 = None

print("\n" + "=" * 60)
print("  RELATÓRIO FINAL")
print("=" * 60)
print(r1)
print("\n---")
print(r2 if r2 else "(sem revisão)")
print("\n[OK] Teste concluído")
