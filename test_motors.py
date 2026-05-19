"""
test_motors.py — Validação de Conectividade NVIDIA e Gemini
Uso: python test_motors.py
"""
import os
import sys
import traceback

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

NVIDIA_KEY = os.getenv("NVIDIA_API_KEY", "")
GEMINI_KEY = os.getenv("GOOGLE_API_KEY", "")


def testar(provider, model, api_key, api_base):
    print(f"\n[{provider.upper()}] Testando {model}...")
    if not api_key:
        print(f"[{provider.upper()}] Chave não configurada. Adicione ao .env")
        return False
    try:
        from litellm import completion
        response = completion(
            model=model,
            messages=[{"role": "user", "content": "Responda apenas: OK"}],
            api_key=api_key,
            api_base=api_base,
            max_tokens=10,
            timeout=30,
        )
        print(f"[{provider.upper()}] OK — {response.choices[0].message.content}")
        return True
    except Exception as e:
        erro = str(e).lower()
        if "401" in erro:
            print(f"[{provider.upper()}] ERRO: Autenticação (401) — chave inválida")
        elif "429" in erro:
            print(f"[{provider.upper()}] ERRO: Limite de taxa (429)")
        elif "timeout" in erro:
            print(f"[{provider.upper()}] ERRO: Timeout — conexão lenta")
        else:
            print(f"[{provider.upper()}] ERRO: {type(e).__name__}: {str(e)[:100]}")
        traceback.print_exc()
        return False


def main():
    print("=" * 50)
    print("  TESTE DE MOTORES — INQUISIDOR v7.0")
    print("=" * 50)

    resultados = {
        "NVIDIA": testar("NVIDIA", "openai/meta/llama-3.3-70b-instruct",
                         NVIDIA_KEY, "https://integrate.api.nvidia.com/v1"),
        "Gemini": testar("Gemini", "gemini/gemini-2.0-flash",
                         GEMINI_KEY, None),
    }

    print("\n" + "=" * 50)
    print("  RESUMO")
    print("=" * 50)
    for nome, ok in resultados.items():
        print(f"  {nome}: {'OK' if ok else 'FALHOU'}")

    if not any(resultados.values()):
        print("\n  ERRO: Nenhum motor disponível!")
        print("  Verifique:")
        print("  1. .env está configurado?")
        print("  2. Chaves de API são válidas?")
        print("  3. Conexão com internet está ativa?")
    elif resultados.get("NVIDIA"):
        print("\n  Sistema pronto: NVIDIA disponível")
    elif resultados.get("Gemini"):
        print("\n  Sistema em failover: usando Gemini")

    input("\nPressione ENTER para sair...")


if __name__ == "__main__":
    main()
